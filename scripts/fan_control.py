#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
import tomllib
from pathlib import Path


DEFAULT_CONFIG: dict[str, object] = {
    "pwm": {
        "pin": 18,
        "frequency_hz": 25_000,
    },
    "control": {
        "poll_seconds": 3.0,
        "boost_seconds": 3.0,
        "min_duty": 30,
        "max_duty": 100,
        "smoothing_alpha": 0.32,
        "ramp_up_step": 12,
        "ramp_down_step": 6,
        "emergency_temp_c": 75.0,
        "log_every_seconds": 60.0,
    },
    "curve": [
        {"temp_c": 35.0, "duty": 30},
        {"temp_c": 42.0, "duty": 30},
        {"temp_c": 48.0, "duty": 38},
        {"temp_c": 52.0, "duty": 48},
        {"temp_c": 56.0, "duty": 60},
        {"temp_c": 60.0, "duty": 72},
        {"temp_c": 64.0, "duty": 84},
        {"temp_c": 68.0, "duty": 92},
        {"temp_c": 72.0, "duty": 100},
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drive a Raspberry Pi case fan from CPU temperature using pigpio hardware PWM."
    )
    parser.add_argument(
        "--config",
        default="deploy/fan_control.toml",
        help="Path to TOML config file (default: deploy/fan_control.toml)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single control tick after startup boost and exit.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print the merged runtime config and exit.",
    )
    return parser.parse_args()


def merge_dicts(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = merge_dicts(base[key], value)  # type: ignore[index]
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> dict[str, object]:
    config = dict(DEFAULT_CONFIG)
    if not path.exists():
        return config
    with path.open("rb") as handle:
        loaded = tomllib.load(handle)
    merged = merge_dicts(DEFAULT_CONFIG, loaded)
    if "curve" not in loaded:
        merged["curve"] = DEFAULT_CONFIG["curve"]
    return merged


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def read_cpu_temp_c() -> float:
    raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="utf-8").strip()
    return float(raw) / 1000.0


def interpolate_curve(points: list[tuple[float, float]], temp_c: float) -> float:
    if not points:
        return 30.0
    sorted_points = sorted(points, key=lambda item: item[0])
    if temp_c <= sorted_points[0][0]:
        return sorted_points[0][1]
    if temp_c >= sorted_points[-1][0]:
        return sorted_points[-1][1]

    for (left_temp, left_duty), (right_temp, right_duty) in zip(sorted_points, sorted_points[1:]):
        if left_temp <= temp_c <= right_temp:
            span = right_temp - left_temp or 1.0
            ratio = (temp_c - left_temp) / span
            return left_duty + (right_duty - left_duty) * ratio
    return sorted_points[-1][1]


class PigpioDriver:
    def __init__(self, *, pin: int, frequency_hz: int) -> None:
        import pigpio

        self._pin = pin
        self._frequency_hz = frequency_hz
        self._pigpio = pigpio
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("pigpio daemon is not running")

    def set_percent(self, percent: float) -> None:
        duty = int(clamp(percent, 0, 100) * 10_000)
        self._pi.hardware_PWM(self._pin, self._frequency_hz, duty)

    def close(self) -> None:
        self._pi.stop()


class FanController:
    def __init__(self, config: dict[str, object], *, state_path: Path) -> None:
        pwm = config["pwm"]  # type: ignore[index]
        control = config["control"]  # type: ignore[index]
        curve = config["curve"]  # type: ignore[index]

        self.pin = int(pwm["pin"])  # type: ignore[index]
        self.frequency_hz = int(pwm["frequency_hz"])  # type: ignore[index]
        self.poll_seconds = float(control["poll_seconds"])  # type: ignore[index]
        self.boost_seconds = float(control["boost_seconds"])  # type: ignore[index]
        self.min_duty = int(control["min_duty"])  # type: ignore[index]
        self.max_duty = int(control["max_duty"])  # type: ignore[index]
        self.smoothing_alpha = float(control["smoothing_alpha"])  # type: ignore[index]
        self.ramp_up_step = float(control["ramp_up_step"])  # type: ignore[index]
        self.ramp_down_step = float(control["ramp_down_step"])  # type: ignore[index]
        self.emergency_temp_c = float(control["emergency_temp_c"])  # type: ignore[index]
        self.log_every_seconds = float(control["log_every_seconds"])  # type: ignore[index]
        self.state_path = state_path
        self.curve = [
            (float(item["temp_c"]), float(item["duty"]))  # type: ignore[index]
            for item in curve
            if isinstance(item, dict)
        ]

        self.driver = PigpioDriver(pin=self.pin, frequency_hz=self.frequency_hz)
        self.running = True
        self.last_duty: float | None = None
        self.smoothed_temp_c: float | None = None
        self.last_log_ts = 0.0

    def stop(self) -> None:
        self.running = False

    def _log(self, message: str) -> None:
        print(f"[fan-control] {message}", flush=True)

    def _target_duty_for_temp(self, temp_c: float) -> float:
        if temp_c >= self.emergency_temp_c:
            return float(self.max_duty)
        target = interpolate_curve(self.curve, temp_c)
        return clamp(target, self.min_duty, self.max_duty)

    def _smoothed_temp(self, current_temp_c: float) -> float:
        if self.smoothed_temp_c is None:
            self.smoothed_temp_c = current_temp_c
            return current_temp_c
        alpha = clamp(self.smoothing_alpha, 0.01, 1.0)
        self.smoothed_temp_c = alpha * current_temp_c + (1.0 - alpha) * self.smoothed_temp_c
        return self.smoothed_temp_c

    def _apply_ramp(self, target_duty: float) -> float:
        if self.last_duty is None:
            return clamp(target_duty, self.min_duty, self.max_duty)
        if target_duty > self.last_duty:
            return min(target_duty, self.last_duty + self.ramp_up_step)
        if target_duty < self.last_duty:
            return max(target_duty, self.last_duty - self.ramp_down_step)
        return target_duty

    def _set_duty(self, duty: float, *, reason: str) -> None:
        applied = clamp(duty, self.min_duty, self.max_duty)
        if self.last_duty is not None and math.isclose(applied, self.last_duty, abs_tol=0.5):
            return
        self.driver.set_percent(applied)
        self.last_duty = applied
        self._log(f"duty -> {applied:.0f}% ({reason})")

    def _write_state(self, *, cpu_temp_c: float, smooth_temp_c: float, target_duty: float) -> None:
        payload = {
            "updated_ts": time.time(),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "pin": self.pin,
            "frequency_hz": self.frequency_hz,
            "cpu_temp_c": round(cpu_temp_c, 2),
            "smooth_temp_c": round(smooth_temp_c, 2),
            "target_duty_percent": round(target_duty, 1),
            "applied_duty_percent": round(float(self.last_duty or 0.0), 1),
            "min_duty_percent": self.min_duty,
            "max_duty_percent": self.max_duty,
            "poll_seconds": self.poll_seconds,
            "emergency_temp_c": self.emergency_temp_c,
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temp_path.replace(self.state_path)
        except Exception as exc:
            self._log(f"state write skipped: {exc}")

    def startup_boost(self) -> None:
        self.driver.set_percent(100)
        self.last_duty = 100.0
        self._log(
            f"startup boost 100% for {self.boost_seconds:.1f}s on GPIO{self.pin} at {self.frequency_hz}Hz"
        )
        if self.boost_seconds > 0:
            time.sleep(self.boost_seconds)

    def tick(self) -> None:
        temp_c = read_cpu_temp_c()
        smooth_c = self._smoothed_temp(temp_c)
        target_duty = self._target_duty_for_temp(smooth_c)
        applied_duty = self._apply_ramp(target_duty)
        self._set_duty(
            applied_duty,
            reason=f"cpu {temp_c:.1f}C, smooth {smooth_c:.1f}C, target {target_duty:.0f}%",
        )
        now = time.time()
        if now - self.last_log_ts >= self.log_every_seconds:
            self.last_log_ts = now
            self._log(
                f"status cpu={temp_c:.1f}C smooth={smooth_c:.1f}C duty={self.last_duty:.0f}%"
            )
        self._write_state(cpu_temp_c=temp_c, smooth_temp_c=smooth_c, target_duty=target_duty)

    def close(self) -> None:
        self.driver.close()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path)

    if args.print_config:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return 0

    controller = FanController(config, state_path=config_path.with_name("state.json"))

    def handle_signal(_signum: int, _frame: object) -> None:
        controller.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        controller.startup_boost()
        controller.tick()
        if args.once:
            return 0
        while controller.running:
            time.sleep(controller.poll_seconds)
            controller.tick()
    except Exception as exc:
        print(f"[fan-control] fatal error: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        controller.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
