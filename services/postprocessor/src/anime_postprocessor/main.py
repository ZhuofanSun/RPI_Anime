from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .publisher import apply_publish_plan, build_publish_plan, build_target_path
from .scanner import scan_root


def _default_download_root(anime_data_root: Path) -> Path:
    return Path(
        os.environ.get(
            "ANIME_DOWNLOAD_ROOT",
            anime_data_root / "downloads" / "Bangumi",
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anime postprocessor tools")
    subparsers = parser.add_subparsers(dest="command")

    scan = subparsers.add_parser(
        "scan",
        help="Scan the download directory and report duplicate episodes and name collisions.",
    )
    scan.add_argument(
        "--root",
        type=Path,
        help="Root directory to scan. Defaults to $ANIME_DOWNLOAD_ROOT or downloads/Bangumi.",
    )
    scan.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of human-readable text.",
    )

    publish = subparsers.add_parser(
        "publish",
        help="Select one version per episode and plan or apply publishing actions.",
    )
    publish.add_argument(
        "--source-root",
        type=Path,
        help="Download root to scan. Defaults to $ANIME_DOWNLOAD_ROOT or downloads/Bangumi.",
    )
    publish.add_argument(
        "--target-root",
        type=Path,
        help="Library root for published media. Defaults to $ANIME_LIBRARY_ROOT or library/seasonal.",
    )
    publish.add_argument(
        "--review-root",
        type=Path,
        help="Manual review root. Defaults to $ANIME_REVIEW_ROOT or processing/manual_review.",
    )
    publish.add_argument(
        "--apply",
        action="store_true",
        help="Apply moves and deletions. Without this flag, only print the plan.",
    )
    publish.add_argument(
        "--delete-losers",
        action="store_true",
        help="Delete unselected duplicates after publishing the winner.",
    )
    publish.add_argument(
        "--json",
        action="store_true",
        help="Emit the plan or result as JSON.",
    )
    return parser


def _print_text_report(report) -> None:
    print(f"scan root: {report.root}")
    print(f"total media files: {report.total_files}")
    print(f"parsed media files: {len(report.parsed_files)}")
    print(f"unparsed media files: {len(report.unparsed_files)}")
    print(f"duplicate episode groups: {len(report.duplicate_groups)}")
    print(f"default target collisions: {len(report.target_collisions)}")

    if report.duplicate_groups:
        print("\nduplicate episode groups:")
        for key, items in sorted(
            report.duplicate_groups.items(),
            key=lambda item: (
                item[0].normalized_title,
                item[0].season,
                item[0].episode,
            ),
        ):
            print(f"- {key.normalized_title} S{key.season:02d}E{key.episode:02d}")
            for item in items:
                print(f"  {item.relative_path}")

    if report.target_collisions:
        print("\ndefault target collisions:")
        for target_name, items in sorted(report.target_collisions.items()):
            print(f"- {target_name}")
            for item in items:
                print(f"  {item.relative_path}")

    if report.unparsed_files:
        print("\nunparsed media files:")
        for item in report.unparsed_files:
            print(f"- {item.relative_path} ({item.reason})")


def _default_library_root(anime_data_root: Path) -> Path:
    return Path(
        os.environ.get(
            "ANIME_LIBRARY_ROOT",
            anime_data_root / "library" / "seasonal",
        )
    )


def _default_review_root(anime_data_root: Path) -> Path:
    return Path(
        os.environ.get(
            "ANIME_REVIEW_ROOT",
            anime_data_root / "processing" / "manual_review",
        )
    )


def _print_publish_plan(plan) -> None:
    print(f"source root: {plan.download_root}")
    print(f"target root: {plan.library_root}")
    print(f"review root: {plan.review_root}")
    print(f"episode decisions: {len(plan.decisions)}")
    print(f"unparsed files: {len(plan.report.unparsed_files)}")

    if plan.decisions:
        print("\nselected winners:")
        for decision in plan.decisions:
            target = build_target_path(plan.library_root, decision.winner)
            print(
                f"- {decision.key.normalized_title} "
                f"S{decision.key.season:02d}E{decision.key.episode:02d}"
            )
            print(f"  winner: {decision.winner.relative_path}")
            print(f"  score: {decision.winner_score.summary}")
            print(f"  publish_to: {target}")
            for loser in decision.losers:
                loser_score = decision.loser_scores[str(loser.relative_path)]
                print(f"  loser: {loser.relative_path}")
                print(f"  loser_score: {loser_score.summary}")

    if plan.report.unparsed_files:
        print("\nunparsed files:")
        for item in plan.report.unparsed_files:
            print(f"- {item.relative_path} ({item.reason})")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    anime_data_root = Path(os.environ.get("ANIME_DATA_ROOT", "/srv/anime-data"))
    anime_collection_root = Path(
        os.environ.get("ANIME_COLLECTION_ROOT", "/srv/anime-collection")
    )
    download_root = getattr(args, "root", None) or _default_download_root(
        anime_data_root
    )

    if args.command is None:
        args.command = "scan"
        args.json = False

    if args.command == "scan":
        report = scan_root(download_root)
        if getattr(args, "json", False):
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            return
        print(f"ANIME_DATA_ROOT={anime_data_root}")
        print(f"ANIME_COLLECTION_ROOT={anime_collection_root}")
        _print_text_report(report)
        print(
            "\nnext: use this report to define publish, duplicate resolution, and manual_review rules."
        )
        return

    if args.command == "publish":
        source_root = args.source_root or _default_download_root(anime_data_root)
        target_root = args.target_root or _default_library_root(anime_data_root)
        review_root = args.review_root or _default_review_root(anime_data_root)
        report = scan_root(source_root)
        plan = build_publish_plan(
            report=report,
            download_root=source_root,
            library_root=target_root,
            review_root=review_root,
        )
        if not args.apply:
            if getattr(args, "json", False):
                print(
                    json.dumps(
                        {
                            "source_root": str(source_root),
                            "target_root": str(target_root),
                            "review_root": str(review_root),
                            "report": report.to_dict(),
                            "decisions": [
                                {
                                    "title": decision.key.normalized_title,
                                    "season": decision.key.season,
                                    "episode": decision.key.episode,
                                    "winner": str(decision.winner.relative_path),
                                    "winner_score": decision.winner_score.summary,
                                    "target": str(
                                        build_target_path(target_root, decision.winner)
                                    ),
                                    "losers": [
                                        {
                                            "path": str(loser.relative_path),
                                            "score": decision.loser_scores[
                                                str(loser.relative_path)
                                            ].summary,
                                        }
                                        for loser in decision.losers
                                    ],
                                }
                                for decision in plan.decisions
                            ],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return
            _print_publish_plan(plan)
            print(
                "\ndry-run only. Re-run with 'publish --apply' to move winners."
            )
            if not args.delete_losers:
                print("losers will only be deleted when '--delete-losers' is also set.")
            return

        result = apply_publish_plan(
            plan,
            delete_losers=args.delete_losers,
            move_unparsed_to_review=True,
        )
        if getattr(args, "json", False):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        print("apply complete")
        print(f"published: {len(result['published'])}")
        print(f"deleted losers: {len(result['deleted'])}")
        print(f"moved to review: {len(result['reviewed'])}")
        for item in result["published"]:
            print(f"- publish {item['source']} -> {item['target']}")
        for item in result["deleted"]:
            print(f"- delete {item}")
        for item in result["reviewed"]:
            print(f"- review {item['source']} -> {item['target']}")


if __name__ == "__main__":
    main()
