from pathlib import Path

from anime_postprocessor.parser import parse_media_file


def _parse(relative_path: str, *, root: Path):
    path = root / relative_path
    return parse_media_file(root=root, path=path)


def test_parse_media_file_recognizes_bracketed_split_season_episode(tmp_path):
    parsed = _parse(
        "金牌得主/Season 2/[MoezakuraSub]Medalist[S2][09][WebRip][HEVC_AAC][CHS_JP].mkv",
        root=tmp_path,
    )

    assert parsed.title == "Medalist"
    assert parsed.season == 2
    assert parsed.episode == 9


def test_parse_media_file_infers_season_from_relative_path_when_name_only_has_episode(tmp_path):
    parsed = _parse(
        "金牌得主/Season 2/[MoezakuraSub]Medalist[09][WebRip][HEVC_AAC][CHS_JP].mkv",
        root=tmp_path,
    )

    assert parsed.title == "Medalist"
    assert parsed.season == 2
    assert parsed.episode == 9


def test_parse_media_file_supports_common_separated_season_episode_forms(tmp_path):
    season_dash_episode = _parse(
        "金牌得主/Season 2/Medalist Season 2 - 09.mkv",
        root=tmp_path,
    )
    short_dash_episode = _parse(
        "金牌得主/Season 2/Medalist S2-09.mkv",
        root=tmp_path,
    )

    assert season_dash_episode.season == 2
    assert season_dash_episode.episode == 9
    assert short_dash_episode.season == 2
    assert short_dash_episode.episode == 9


def test_parse_media_file_prefers_explicit_filename_season_over_parent_folder(tmp_path):
    parsed = _parse(
        "金牌得主/Season 2/Medalist S01E09.mkv",
        root=tmp_path,
    )

    assert parsed.season == 1
    assert parsed.episode == 9
