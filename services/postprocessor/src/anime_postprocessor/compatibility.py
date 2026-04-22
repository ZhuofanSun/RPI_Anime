from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .models import ParsedMedia
from .selector import SelectionDecision

_SAFE_EXTENSIONS = {".mp4", ".m4v", ".mov"}
_SAFE_VIDEO_CODECS = {"h264"}
_CONDITIONAL_VIDEO_CODECS = {"hevc"}
_SAFE_AUDIO_CODECS = {"aac", "ac3", "eac3"}
_SAFE_TEXT_SUBTITLE_CODECS = {"webvtt", "subrip", "mov_text"}
_STYLE_SUBTITLE_CODECS = {"ass", "ssa"}
_IMAGE_SUBTITLE_CODECS = {
    "hdmv_pgs_subtitle",
    "pgs",
    "xsub",
    "dvd_subtitle",
    "dvb_subtitle",
}
_AUDIO_TRANSCODE_CODECS = {"opus", "flac", "vorbis", "dts", "truehd", "pcm_s16le"}
_ACTION_ORDER = {
    "transcode_audio_to_aac": 1,
    "convert_subtitles_to_webvtt": 2,
    "normalize_text_subtitles": 2,
    "remux_to_mp4_or_fmp4": 3,
    "publish_direct": 4,
    "verify_hevc_on_target_devices": 5,
    "device_gate_hevc_or_generate_h264_fallback": 6,
    "offline_video_transcode": 7,
    "manual_review_image_subtitles": 8,
}
_ACTION_LABELS = {
    "publish_direct": "publish_direct",
    "transcode_audio_to_aac": "audio_to_aac",
    "convert_subtitles_to_webvtt": "subtitles_to_webvtt",
    "normalize_text_subtitles": "normalize_text_subtitles",
    "remux_to_mp4_or_fmp4": "remux_to_mp4_or_fmp4",
    "verify_hevc_on_target_devices": "verify_hevc_on_target_devices",
    "device_gate_hevc_or_generate_h264_fallback": "hevc_gate_or_h264_fallback",
    "offline_video_transcode": "offline_video_transcode",
    "manual_review_image_subtitles": "manual_review_image_subtitles",
}
_QUEUE_NOTES = {
    "publish_direct": "Publish as-is. No offline preprocessing is required for the current iOS-safe target.",
    "transcode_audio_to_aac": "Normalize audio to AAC first, then keep the rest of the asset unchanged.",
    "convert_subtitles_to_webvtt": "Convert styled subtitles to a stable text subtitle format before publish.",
    "normalize_text_subtitles": "Normalize text subtitles into the iOS-safe text subtitle set before publish.",
    "remux_to_mp4_or_fmp4": "Remux the container without touching video when possible.",
    "verify_hevc_on_target_devices": "Keep the HEVC master and confirm stable AVPlayer playback on the target iPhone/iPad before escalating to an H.264 fallback.",
    "device_gate_hevc_or_generate_h264_fallback": "Keep the HEVC master if AVPlayer/device gate passes; otherwise queue an H.264 fallback later.",
    "offline_video_transcode": "Offline video transcode is required before this asset can be considered iOS-safe.",
    "manual_review_image_subtitles": "Image subtitles need manual review before deciding between OCR, burn-in, or an external subtitle strategy.",
}

_GENERIC_IOS_PROFILE = "generic_ios"
_PERSONAL_APPLE_PROFILE = "personal_modern_apple"
_TARGET_PROFILES = {_GENERIC_IOS_PROFILE, _PERSONAL_APPLE_PROFILE}


@dataclass(frozen=True)
class ActionQueue:
    key: str
    steps: list[str]
    summary: str
    note: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "steps": self.steps,
            "summary": self.summary,
            "note": self.note,
        }


@dataclass(frozen=True)
class MediaProbe:
    path: Path
    container: str
    video_codec: str | None
    video_profile: str | None
    pixel_format: str | None
    bit_depth: int | None
    audio_codecs: list[str]
    subtitle_codecs: list[str]
    audio_track_count: int
    subtitle_track_count: int

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "container": self.container,
            "video_codec": self.video_codec,
            "video_profile": self.video_profile,
            "pixel_format": self.pixel_format,
            "bit_depth": self.bit_depth,
            "audio_codecs": self.audio_codecs,
            "subtitle_codecs": self.subtitle_codecs,
            "audio_track_count": self.audio_track_count,
            "subtitle_track_count": self.subtitle_track_count,
        }


@dataclass(frozen=True)
class CompatibilityAssessment:
    classification: str
    reasons: list[str]
    suggested_actions: list[str]
    action_queue: ActionQueue
    device_validation_required: bool
    device_validation_notes: list[str]
    sync_risk: str
    quality_risk: str

    def to_dict(self) -> dict:
        return {
            "classification": self.classification,
            "reasons": self.reasons,
            "suggested_actions": self.suggested_actions,
            "action_queue": self.action_queue.to_dict(),
            "device_validation_required": self.device_validation_required,
            "device_validation_notes": self.device_validation_notes,
            "sync_risk": self.sync_risk,
            "quality_risk": self.quality_risk,
        }


@dataclass(frozen=True)
class DecisionCompatibility:
    decision: SelectionDecision
    probe: MediaProbe
    assessment: CompatibilityAssessment

    def to_dict(self) -> dict:
        return {
            "title": self.decision.key.normalized_title,
            "season": self.decision.key.season,
            "episode": self.decision.key.episode,
            "winner": str(self.decision.winner.relative_path),
            "winner_score": self.decision.winner_score.summary,
            "probe": self.probe.to_dict(),
            "assessment": self.assessment.to_dict(),
        }


@dataclass(frozen=True)
class CompatibilityReport:
    decisions: list[DecisionCompatibility]

    @property
    def summary(self) -> dict[str, int]:
        counts = Counter(item.assessment.classification for item in self.decisions)
        return {
            "green": counts.get("green", 0),
            "yellow": counts.get("yellow", 0),
            "red": counts.get("red", 0),
            "total": len(self.decisions),
        }

    @property
    def queue_summary(self) -> dict[str, dict]:
        queues: dict[str, dict] = {}
        for item in self.decisions:
            queue = item.assessment.action_queue
            bucket = queues.setdefault(
                queue.key,
                {
                    "count": 0,
                    "steps": queue.steps,
                    "summary": queue.summary,
                    "note": queue.note,
                },
            )
            bucket["count"] += 1
        return dict(sorted(queues.items()))

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "queue_summary": self.queue_summary,
            "decisions": [item.to_dict() for item in self.decisions],
        }


def build_compatibility_report(
    decisions: list[SelectionDecision],
    *,
    ffprobe_bin: str = "ffprobe",
    target_profile: str = _PERSONAL_APPLE_PROFILE,
) -> CompatibilityReport:
    return CompatibilityReport(
        decisions=[
            DecisionCompatibility(
                decision=decision,
                probe=(probe := probe_media(decision.winner.path, ffprobe_bin=ffprobe_bin)),
                assessment=classify_media_for_ios(
                    decision.winner,
                    probe,
                    target_profile=target_profile,
                ),
            )
            for decision in decisions
        ]
    )


def probe_media(path: Path, *, ffprobe_bin: str = "ffprobe") -> MediaProbe:
    payload = subprocess.check_output(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
    )
    return media_probe_from_ffprobe(path, json.loads(payload))


def media_probe_from_ffprobe(path: Path, payload: dict) -> MediaProbe:
    streams = payload.get("streams") or []
    primary_video = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
            and not (stream.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )

    audio_codecs = [str(stream.get("codec_name") or "unknown") for stream in streams if stream.get("codec_type") == "audio"]
    subtitle_codecs = [str(stream.get("codec_name") or "unknown") for stream in streams if stream.get("codec_type") == "subtitle"]
    format_name = str((payload.get("format") or {}).get("format_name") or "")
    container = format_name.split(",")[0] if format_name else ""

    bit_depth = None
    if primary_video is not None:
        raw_bit_depth = (
            primary_video.get("bits_per_raw_sample")
            or primary_video.get("bits_per_sample")
        )
        if raw_bit_depth is not None:
            try:
                bit_depth = int(raw_bit_depth)
            except (TypeError, ValueError):
                bit_depth = None
        if bit_depth is None:
            profile = str(primary_video.get("profile") or "")
            pixel_format = str(primary_video.get("pix_fmt") or "")
            if "10" in profile or "10" in pixel_format:
                bit_depth = 10

    return MediaProbe(
        path=path,
        container=container,
        video_codec=(
            str(primary_video.get("codec_name"))
            if primary_video is not None and primary_video.get("codec_name")
            else None
        ),
        video_profile=(
            str(primary_video.get("profile"))
            if primary_video is not None and primary_video.get("profile")
            else None
        ),
        pixel_format=(
            str(primary_video.get("pix_fmt"))
            if primary_video is not None and primary_video.get("pix_fmt")
            else None
        ),
        bit_depth=bit_depth,
        audio_codecs=audio_codecs,
        subtitle_codecs=subtitle_codecs,
        audio_track_count=len(audio_codecs),
        subtitle_track_count=len(subtitle_codecs),
    )


def classify_media_for_ios(
    media: ParsedMedia,
    probe: MediaProbe,
    *,
    target_profile: str = _PERSONAL_APPLE_PROFILE,
) -> CompatibilityAssessment:
    if target_profile not in _TARGET_PROFILES:
        raise ValueError(f"unknown target profile: {target_profile}")

    reasons: list[str] = []
    actions: list[str] = []
    classification = "green"
    device_validation_required = False
    device_validation_notes: list[str] = []
    sync_risk = "low"
    quality_risk = "low"

    if media.extension not in _SAFE_EXTENSIONS:
        classification = "yellow"
        reasons.append(f"container {media.extension} is not in the direct iOS-safe set")
        actions.append("remux_to_mp4_or_fmp4")

    video_codec = (probe.video_codec or "").lower()
    if video_codec not in _SAFE_VIDEO_CODECS | _CONDITIONAL_VIDEO_CODECS:
        classification = "red"
        reasons.append(f"video codec {probe.video_codec or 'unknown'} requires offline video transcode")
        actions.append("offline_video_transcode")
        quality_risk = "high"
    elif video_codec == "hevc":
        if target_profile == _GENERIC_IOS_PROFILE:
            classification = max_classification(classification, "yellow")
            reasons.append("HEVC delivery should be device-gated and preflighted for AVPlayer")
            actions.append("device_gate_hevc_or_generate_h264_fallback")
        else:
            reasons.append("HEVC is allowed for the current target devices, but it should be validated once on the real iPhone/iPad before we treat it as stable")
            actions.append("verify_hevc_on_target_devices")
            device_validation_required = True
            device_validation_notes.append(
                "Validate HEVC startup, seek, resume, and track switching on the target iPhone/iPad before escalating to an H.264 fallback."
            )

    if probe.bit_depth and probe.bit_depth > 8:
        if target_profile == _GENERIC_IOS_PROFILE or video_codec != "hevc":
            classification = max_classification(classification, "yellow")
            reasons.append(f"{probe.bit_depth}-bit video should be treated as conditional AVPlayer input")
            if "device_gate_hevc_or_generate_h264_fallback" not in actions:
                actions.append("device_gate_hevc_or_generate_h264_fallback")
        else:
            reasons.append(f"{probe.bit_depth}-bit HEVC should be verified on the target devices before we rely on it long-term")
            device_validation_required = True
            device_validation_notes.append(
                "Main10/10-bit HEVC should be checked on the target devices for startup stability and seek latency."
            )

    unsupported_audio = sorted({codec for codec in probe.audio_codecs if codec not in _SAFE_AUDIO_CODECS})
    if unsupported_audio:
        classification = max_classification(classification, "yellow")
        reasons.append(f"audio codecs {', '.join(unsupported_audio)} should be normalized for iOS")
        actions.append("transcode_audio_to_aac")
        quality_risk = max_risk(quality_risk, "medium")

    subtitle_codecs = {codec.lower() for codec in probe.subtitle_codecs}
    if subtitle_codecs & _IMAGE_SUBTITLE_CODECS:
        classification = "red"
        reasons.append("image subtitles need OCR or burn-in before reliable iOS delivery")
        actions.append("manual_review_image_subtitles")
        sync_risk = "high"
        quality_risk = max_risk(quality_risk, "medium")
    elif subtitle_codecs & _STYLE_SUBTITLE_CODECS:
        classification = max_classification(classification, "yellow")
        reasons.append("ASS/SSA subtitles should be converted to WebVTT/SRT for stable AVPlayer delivery")
        actions.append("convert_subtitles_to_webvtt")
        sync_risk = max_risk(sync_risk, "medium")
    elif subtitle_codecs and not subtitle_codecs.issubset(_SAFE_TEXT_SUBTITLE_CODECS):
        classification = max_classification(classification, "yellow")
        reasons.append(f"subtitle codecs {', '.join(sorted(subtitle_codecs))} should be normalized")
        actions.append("normalize_text_subtitles")
        sync_risk = max_risk(sync_risk, "medium")

    if classification == "green":
        reasons.append("matches the current direct iOS-safe target without offline preprocessing")
        actions.append("publish_direct")

    action_queue = build_action_queue(actions)

    return CompatibilityAssessment(
        classification=classification,
        reasons=dedupe(actions_to_reasons(reasons)),
        suggested_actions=dedupe(actions),
        action_queue=action_queue,
        device_validation_required=device_validation_required,
        device_validation_notes=dedupe(device_validation_notes),
        sync_risk=sync_risk,
        quality_risk=quality_risk,
    )


def build_action_queue(actions: list[str]) -> ActionQueue:
    ordered_actions = normalize_actions_for_queue(actions)
    key = "__then__".join(_ACTION_LABELS[action] for action in ordered_actions)
    summary = " -> ".join(_ACTION_LABELS[action] for action in ordered_actions)
    note = " ".join(_QUEUE_NOTES[action] for action in ordered_actions)
    return ActionQueue(
        key=key,
        steps=ordered_actions,
        summary=summary,
        note=note,
    )


def normalize_actions_for_queue(actions: list[str]) -> list[str]:
    ordered = dedupe(actions)
    return sorted(ordered, key=lambda action: (_ACTION_ORDER[action], action))


def actions_to_reasons(reasons: list[str]) -> list[str]:
    return [reason for reason in reasons if reason]


def dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def max_classification(current: str, candidate: str) -> str:
    order = {"green": 0, "yellow": 1, "red": 2}
    return candidate if order[candidate] > order[current] else current


def max_risk(current: str, candidate: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return candidate if order[candidate] > order[current] else current
