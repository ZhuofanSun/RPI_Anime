from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import EpisodeKey, ParsedMedia, UnparsedMedia
from .parser import MEDIA_EXTENSIONS, parse_media_file


@dataclass(frozen=True)
class ScanReport:
    root: Path
    total_files: int
    parsed_files: list[ParsedMedia]
    unparsed_files: list[UnparsedMedia]
    duplicate_groups: dict[EpisodeKey, list[ParsedMedia]]
    target_collisions: dict[str, list[ParsedMedia]]

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "total_files": self.total_files,
            "parsed_count": len(self.parsed_files),
            "unparsed_count": len(self.unparsed_files),
            "duplicate_group_count": len(self.duplicate_groups),
            "target_collision_count": len(self.target_collisions),
            "duplicates": [
                {
                    "title": key.normalized_title,
                    "season": key.season,
                    "episode": key.episode,
                    "files": [str(item.relative_path) for item in items],
                }
                for key, items in sorted(
                    self.duplicate_groups.items(),
                    key=lambda item: (
                        item[0].normalized_title,
                        item[0].season,
                        item[0].episode,
                    ),
                )
            ],
            "target_collisions": [
                {
                    "target_name": target_name,
                    "files": [str(item.relative_path) for item in items],
                }
                for target_name, items in sorted(self.target_collisions.items())
            ],
            "unparsed": [
                {
                    "path": str(item.relative_path),
                    "reason": item.reason,
                }
                for item in self.unparsed_files
            ],
        }


def _iter_media_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    )


def build_report(
    root: Path,
    *,
    parsed_files: list[ParsedMedia],
    unparsed_files: list[UnparsedMedia],
) -> ScanReport:
    duplicate_groups: dict[EpisodeKey, list[ParsedMedia]] = defaultdict(list)
    target_collisions: dict[str, list[ParsedMedia]] = defaultdict(list)

    for parsed in parsed_files:
        duplicate_groups[parsed.key].append(parsed)
        target_collisions[parsed.default_target_name].append(parsed)

    duplicate_groups = {
        key: items for key, items in duplicate_groups.items() if len(items) > 1
    }
    target_collisions = {
        key: items for key, items in target_collisions.items() if len(items) > 1
    }

    return ScanReport(
        root=root,
        total_files=len(parsed_files) + len(unparsed_files),
        parsed_files=parsed_files,
        unparsed_files=unparsed_files,
        duplicate_groups=duplicate_groups,
        target_collisions=target_collisions,
    )


def scan_root(root: Path) -> ScanReport:
    parsed_files: list[ParsedMedia] = []
    unparsed_files: list[UnparsedMedia] = []

    files = _iter_media_files(root)
    for path in files:
        parsed = parse_media_file(root=root, path=path)
        if isinstance(parsed, UnparsedMedia):
            unparsed_files.append(parsed)
            continue
        parsed_files.append(parsed)
    return build_report(
        root=root,
        parsed_files=parsed_files,
        unparsed_files=unparsed_files,
    )
