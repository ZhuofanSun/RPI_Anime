from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

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


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    anime_data_root = Path(os.environ.get("ANIME_DATA_ROOT", "/srv/anime-data"))
    anime_collection_root = Path(
        os.environ.get("ANIME_COLLECTION_ROOT", "/srv/anime-collection")
    )
    download_root = args.root or _default_download_root(anime_data_root)

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


if __name__ == "__main__":
    main()
