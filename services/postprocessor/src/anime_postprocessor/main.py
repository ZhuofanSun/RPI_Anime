from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .compatibility import build_compatibility_report
from .preprocess import (
    apply_preprocess_entries,
    build_preprocess_entries,
    filter_preprocess_decisions,
    summarize_preprocess_entries,
)
from .publisher import (
    apply_publish_plan,
    build_publish_plan,
    build_target_path,
    write_library_nfo,
)
from .scanner import scan_root
from .watch import watch_from_env


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

    classify = subparsers.add_parser(
        "classify",
        help="Classify selected winners into iOS playback compatibility buckets.",
    )
    classify.add_argument(
        "--source-root",
        type=Path,
        help="Download root to scan. Defaults to $ANIME_DOWNLOAD_ROOT or downloads/Bangumi.",
    )
    classify.add_argument(
        "--target-root",
        type=Path,
        help="Library root for resolved target paths. Defaults to $ANIME_LIBRARY_ROOT or library/seasonal.",
    )
    classify.add_argument(
        "--review-root",
        type=Path,
        help="Manual review root. Defaults to $ANIME_REVIEW_ROOT or processing/manual_review.",
    )
    classify.add_argument(
        "--ffprobe-bin",
        default="ffprobe",
        help="ffprobe binary to use for media inspection. Defaults to ffprobe.",
    )
    classify.add_argument(
        "--target-profile",
        choices=("personal_modern_apple", "generic_ios"),
        default="personal_modern_apple",
        help="Compatibility target profile. Defaults to personal_modern_apple.",
    )
    classify.add_argument(
        "--json",
        action="store_true",
        help="Emit the compatibility report as JSON.",
    )

    preprocess = subparsers.add_parser(
        "preprocess",
        help="Build or apply lightweight iOS preprocessing entries for supported queues.",
    )
    preprocess.add_argument(
        "--source-root",
        type=Path,
        help="Root to scan. Defaults to $ANIME_DOWNLOAD_ROOT or downloads/Bangumi.",
    )
    preprocess.add_argument(
        "--target-root",
        type=Path,
        help="Library root used for target path resolution. Defaults to $ANIME_LIBRARY_ROOT or library/seasonal.",
    )
    preprocess.add_argument(
        "--review-root",
        type=Path,
        help="Manual review root. Defaults to $ANIME_REVIEW_ROOT or processing/manual_review.",
    )
    preprocess.add_argument(
        "--target-profile",
        choices=("personal_modern_apple", "generic_ios"),
        default="personal_modern_apple",
        help="Compatibility target profile. Defaults to personal_modern_apple.",
    )
    preprocess.add_argument(
        "--staging-root",
        type=Path,
        help="Preprocess staging root. Defaults to $ANIME_PREPROCESS_ROOT or processing/ios_preprocess.",
    )
    preprocess.add_argument(
        "--backup-root",
        type=Path,
        help="Backup root when replacing library files. Defaults to $ANIME_PREPROCESS_BACKUP_ROOT or processing/ios_preprocess_backups.",
    )
    preprocess.add_argument(
        "--ffmpeg-bin",
        default="ffmpeg",
        help="ffmpeg binary to use for preprocessing. Defaults to ffmpeg.",
    )
    preprocess.add_argument(
        "--queue-key",
        action="append",
        help="Only include matching action queues. Can be passed multiple times.",
    )
    preprocess.add_argument(
        "--series-title",
        action="append",
        help="Only include matching series titles. Can be passed multiple times.",
    )
    preprocess.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of entries to include.",
    )
    preprocess.add_argument(
        "--replace-library",
        action="store_true",
        help="After preprocessing, move the original file to backup and replace the library file with the processed MP4.",
    )
    preprocess.add_argument(
        "--apply",
        action="store_true",
        help="Run ffmpeg and materialize the preprocess entries. Without this flag, only print the manifest.",
    )
    preprocess.add_argument(
        "--json",
        action="store_true",
        help="Emit the preprocess manifest or result as JSON.",
    )

    watch = subparsers.add_parser(
        "watch",
        help="Poll qBittorrent for completed Bangumi torrents and process them automatically.",
    )
    watch.add_argument(
        "--source-root",
        type=Path,
        help="Download root to scan. Defaults to $ANIME_DOWNLOAD_ROOT or downloads/Bangumi.",
    )
    watch.add_argument(
        "--target-root",
        type=Path,
        help="Library root for published media. Defaults to $ANIME_LIBRARY_ROOT or library/seasonal.",
    )
    watch.add_argument(
        "--review-root",
        type=Path,
        help="Manual review root. Defaults to $ANIME_REVIEW_ROOT or processing/manual_review.",
    )
    watch.add_argument(
        "--once",
        action="store_true",
        help="Run one polling iteration and exit.",
    )
    watch.add_argument(
        "--poll-interval",
        type=int,
        help="Polling interval in seconds. Defaults to $POSTPROCESSOR_POLL_INTERVAL or 60.",
    )
    watch.add_argument(
        "--keep-losers",
        action="store_true",
        help="Keep unselected duplicate files instead of deleting them.",
    )
    watch.add_argument(
        "--wait-timeout",
        type=int,
        help="Seconds to wait for higher-priority incomplete candidates after the first completion. Defaults to $POSTPROCESSOR_WAIT_TIMEOUT or 1800.",
    )

    nfo = subparsers.add_parser(
        "write-nfo",
        help="Write tvshow.nfo files for mapped series already present in the library.",
    )
    nfo.add_argument(
        "--root",
        type=Path,
        help="Library root to scan. Defaults to $ANIME_LIBRARY_ROOT or library/seasonal.",
    )
    nfo.add_argument(
        "--json",
        action="store_true",
        help="Emit written nfo files as JSON.",
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


def _default_preprocess_root(anime_data_root: Path) -> Path:
    return Path(
        os.environ.get(
            "ANIME_PREPROCESS_ROOT",
            anime_data_root / "processing" / "ios_preprocess",
        )
    )


def _default_preprocess_backup_root(anime_data_root: Path) -> Path:
    return Path(
        os.environ.get(
            "ANIME_PREPROCESS_BACKUP_ROOT",
            anime_data_root / "processing" / "ios_preprocess_backups",
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
            target = build_target_path(
                plan.library_root,
                decision.winner,
                resolver=plan.resolver,
            )
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


def _print_compatibility_report(report, *, target_root: Path, resolver) -> None:
    summary = report.summary
    print(f"classification total: {summary['total']}")
    print(f"green: {summary['green']}")
    print(f"yellow: {summary['yellow']}")
    print(f"red: {summary['red']}")
    if report.queue_summary:
        print("\naction queues:")
        for queue_key, queue in report.queue_summary.items():
            print(f"- {queue_key}: {queue['count']}")
            print(f"  steps: {', '.join(queue['steps'])}")
            print(f"  summary: {queue['summary']}")

    if not report.decisions:
        return

    print("\ncompatibility decisions:")
    for item in report.decisions:
        decision = item.decision
        target = build_target_path(
            target_root,
            decision.winner,
            resolver=resolver,
        )
        print(
            f"- {decision.key.normalized_title} "
            f"S{decision.key.season:02d}E{decision.key.episode:02d}"
        )
        print(f"  winner: {decision.winner.relative_path}")
        print(f"  target: {target}")
        print(f"  classification: {item.assessment.classification}")
        print(f"  action_queue: {item.assessment.action_queue.summary}")
        print(
            f"  device_validation_required: "
            f"{'yes' if item.assessment.device_validation_required else 'no'}"
        )
        print(f"  sync_risk: {item.assessment.sync_risk}")
        print(f"  quality_risk: {item.assessment.quality_risk}")
        print(
            "  probe: "
            f"container={item.probe.container or 'unknown'}, "
            f"video={item.probe.video_codec or 'unknown'} "
            f"{item.probe.video_profile or ''}".strip()
        )
        print(
            "  tracks: "
            f"audio={item.probe.audio_track_count} "
            f"({', '.join(item.probe.audio_codecs) or 'none'}), "
            f"subtitle={item.probe.subtitle_track_count} "
            f"({', '.join(item.probe.subtitle_codecs) or 'none'})"
        )
        for reason in item.assessment.reasons:
            print(f"  reason: {reason}")
        for note in item.assessment.device_validation_notes:
            print(f"  validation_note: {note}")
        for action in item.assessment.suggested_actions:
            print(f"  action: {action}")


def _build_series_queue_summary(compatibility, *, target_root: Path, resolver) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for item in compatibility.decisions:
        target = build_target_path(
            target_root,
            item.decision.winner,
            resolver=resolver,
        )
        relative_target = target.relative_to(target_root)
        series_title = relative_target.parts[0] if relative_target.parts else item.decision.winner.title
        bucket = summary.setdefault(
            series_title,
            {
                "total": 0,
                "classification_counts": {"green": 0, "yellow": 0, "red": 0},
                "queues": {},
            },
        )
        bucket["total"] += 1
        bucket["classification_counts"][item.assessment.classification] += 1
        queue = item.assessment.action_queue
        queue_bucket = bucket["queues"].setdefault(
            queue.key,
            {
                "count": 0,
                "steps": queue.steps,
                "summary": queue.summary,
                "note": queue.note,
            },
        )
        queue_bucket["count"] += 1

    return dict(sorted(summary.items()))


def _print_preprocess_entries(entries) -> None:
    summary = summarize_preprocess_entries(entries)
    print(f"preprocess entries: {summary['total']}")
    if summary["strategy_counts"]:
        print("strategy counts:")
        for strategy, count in summary["strategy_counts"].items():
            print(f"- {strategy}: {count}")
    if summary["title_counts"]:
        print("series counts:")
        for title, count in summary["title_counts"].items():
            print(f"- {title}: {count}")
    if summary["requires_jellyfin_refresh_count"]:
        print(
            "follow-up: "
            f"{summary['requires_jellyfin_refresh_count']} entries will need Jellyfin metadata refresh after replace."
        )
    for entry in entries:
        print(f"- {entry.title} S{entry.season:02d}E{entry.episode:02d}")
        print(f"  queue: {entry.queue_key}")
        print(f"  strategy: {entry.strategy}")
        print(f"  strategy_note: {entry.strategy_note}")
        print(f"  source: {entry.source_path}")
        print(f"  staging_output: {entry.staging_output_path}")
        print(f"  library_output: {entry.library_output_path}")
        print(f"  backup: {entry.backup_path}")
        print(f"  note: {entry.note}")
        if entry.requires_jellyfin_refresh:
            print("  follow_up: refresh_jellyfin_metadata_for_replaced_library_items")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    anime_data_root = Path(os.environ.get("ANIME_DATA_ROOT", "/srv/anime-data"))
    anime_collection_root = Path(
        os.environ.get("ANIME_COLLECTION_ROOT", "/srv/anime-collection")
    )
    download_root = getattr(args, "root", None) or _default_download_root(anime_data_root)

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
            summary = summarize_preprocess_entries(entries)
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
                                        build_target_path(
                                            target_root,
                                            decision.winner,
                                            resolver=plan.resolver,
                                        )
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
        return

    if args.command == "watch":
        source_root = args.source_root or _default_download_root(anime_data_root)
        target_root = args.target_root or _default_library_root(anime_data_root)
        review_root = args.review_root or _default_review_root(anime_data_root)
        print(f"ANIME_DATA_ROOT={anime_data_root}")
        print(f"watch source root={source_root}")
        print(f"watch target root={target_root}")
        print(f"watch review root={review_root}")
        watch_from_env(
            anime_data_root=anime_data_root,
            source_root=source_root,
            target_root=target_root,
            review_root=review_root,
            once=args.once,
            poll_interval=args.poll_interval,
            delete_losers=not args.keep_losers,
            wait_timeout=args.wait_timeout,
        )
        return

    if args.command == "write-nfo":
        library_root = args.root or _default_library_root(anime_data_root)
        report = scan_root(library_root)
        written = write_library_nfo(
            library_root=library_root,
            parsed_files=report.parsed_files,
        )
        if getattr(args, "json", False):
            print(json.dumps(written, ensure_ascii=False, indent=2))
            return
        print(f"library root: {library_root}")
        print(f"nfo written: {len(written)}")
        for item in written:
            print(f"- {item['show_dir']} -> {item['nfo']}")
        return

    if args.command == "classify":
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
        compatibility = build_compatibility_report(
            plan.decisions,
            ffprobe_bin=args.ffprobe_bin,
            target_profile=args.target_profile,
        )
        if getattr(args, "json", False):
            series_queue_summary = _build_series_queue_summary(
                compatibility,
                target_root=target_root,
                resolver=plan.resolver,
            )
            print(
                json.dumps(
                    {
                        "source_root": str(source_root),
                        "target_root": str(target_root),
                        "review_root": str(review_root),
                        "target_profile": args.target_profile,
                        "report": report.to_dict(),
                        "compatibility": compatibility.to_dict(),
                        "series_queue_summary": series_queue_summary,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(f"source root: {source_root}")
        print(f"target root: {target_root}")
        print(f"review root: {review_root}")
        _print_compatibility_report(
            compatibility,
            target_root=target_root,
            resolver=plan.resolver,
        )
        if report.unparsed_files:
            print("\nunparsed files:")
            for item in report.unparsed_files:
                print(f"- {item.relative_path} ({item.reason})")
        return

    if args.command == "preprocess":
        source_root = args.source_root or _default_download_root(anime_data_root)
        target_root = args.target_root or _default_library_root(anime_data_root)
        review_root = args.review_root or _default_review_root(anime_data_root)
        staging_root = args.staging_root or _default_preprocess_root(anime_data_root)
        backup_root = args.backup_root or _default_preprocess_backup_root(anime_data_root)
        report = scan_root(source_root)
        plan = build_publish_plan(
            report=report,
            download_root=source_root,
            library_root=target_root,
            review_root=review_root,
        )
        filtered_decisions = filter_preprocess_decisions(
            plan.decisions,
            title_filters=set(args.series_title or []),
        )
        compatibility = build_compatibility_report(
            filtered_decisions,
            ffprobe_bin="ffprobe",
            target_profile=args.target_profile,
        )
        entries = build_preprocess_entries(
            compatibility,
            library_root=target_root,
            resolver=plan.resolver,
            staging_root=staging_root,
            backup_root=backup_root,
            queue_filters=set(args.queue_key or []),
            limit=args.limit,
        )
        summary = summarize_preprocess_entries(entries)
        if not args.apply:
            if getattr(args, "json", False):
                print(
                    json.dumps(
                        {
                            "source_root": str(source_root),
                            "target_root": str(target_root),
                            "review_root": str(review_root),
                            "staging_root": str(staging_root),
                            "backup_root": str(backup_root),
                            "target_profile": args.target_profile,
                            "summary": summary,
                            "entries": [entry.to_dict() for entry in entries],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return
            _print_preprocess_entries(entries)
            return

        result = apply_preprocess_entries(
            entries,
            ffmpeg_bin=args.ffmpeg_bin,
            replace_library=args.replace_library,
        )
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        **result,
                        "summary": summarize_preprocess_entries(entries),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(f"processed entries: {len(result['processed'])}")
        for item in result["processed"]:
            print(
                f"- {item['title']} S{item['season']:02d}E{item['episode']:02d}: "
                f"{item['strategy']}"
            )
            if item.get("replaced_library"):
                print(f"  backup: {item['backup_path']}")
                print(f"  library_output: {item['library_output_path']}")
        for action in result.get("post_apply_actions", []):
            print(f"follow-up: {action}")
        return


if __name__ == "__main__":
    main()
