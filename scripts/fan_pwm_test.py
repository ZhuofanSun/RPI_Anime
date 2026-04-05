#!/usr/bin/env python3

from __future__ import annotations

import argparse
import signal
import sys
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cycle a Raspberry Pi fan through several PWM duty levels."
    )
    parser.add_argument("--pin", type=int, default=18, help="GPIO pin for PWM control (default: 18)")
    parser.add_argument(
        "--frequency",
        type=int,
        default=25_000,
        help="PWM frequency in Hz (default: 25000)",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=4.0,
        help="Seconds to hold each duty level (default: 4)",
    )
    parser.add_argument(
        "--boost-seconds",
        type=float,
        default=3.0,
        help="Initial full-speed spin-up time in seconds (default: 3)",
    )
    parser.add_argument(
        "--duty",
        default="100,80,60,40,25",
        help="Comma-separated duty levels in percent (default: 100,80,60,40,25)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle only and exit.",
    )
    return parser.parse_args()


def parse_duty_levels(raw: str) -> list[int]:
    levels: list[int] = []
    for chunk in raw.split(","):
        text = chunk.strip()
        if not text:
            continue
        value = int(text)
        if value < 0 or value > 100:
            raise ValueError(f"invalid duty value: {value}")
        levels.append(value)
    if not levels:
        raise ValueError("no duty levels provided")
    return levels


class PWMDriver:
    label = "unknown"

    def set_percent(self, percent: int) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class PigpioHardwarePWM(PWMDriver):
    label = "pigpio hardware PWM"

    def __init__(self, *, pin: int, frequency: int) -> None:
        import pigpio

        self._pigpio = pigpio
        self._pin = pin
        self._frequency = frequency
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("pigpio daemon is not running")

    def set_percent(self, percent: int) -> None:
        duty = max(0, min(percent, 100)) * 10_000
        self._pi.hardware_PWM(self._pin, self._frequency, duty)

    def stop(self) -> None:
        try:
            self._pi.hardware_PWM(self._pin, self._frequency, 0)
        finally:
            self._pi.stop()


class GpiozeroPWM(PWMDriver):
    label = "gpiozero software PWM"

    def __init__(self, *, pin: int, frequency: int) -> None:
        from gpiozero import PWMOutputDevice

        self._device = PWMOutputDevice(pin, frequency=frequency, initial_value=0)

    def set_percent(self, percent: int) -> None:
        self._device.value = max(0.0, min(percent / 100.0, 1.0))

    def stop(self) -> None:
        self._device.off()
        self._device.close()


def build_driver(pin: int, frequency: int) -> PWMDriver:
    try:
        return PigpioHardwarePWM(pin=pin, frequency=frequency)
    except Exception as pigpio_error:
        print(f"[fan-pwm] hardware PWM unavailable: {pigpio_error}", file=sys.stderr)

    try:
        return GpiozeroPWM(pin=pin, frequency=frequency)
    except Exception as gpiozero_error:
        raise RuntimeError(
            "neither pigpio nor gpiozero PWM is available; "
            "install `pigpio` or `python3-gpiozero` on the Raspberry Pi"
        ) from gpiozero_error


def main() -> int:
    args = parse_args()
    try:
        levels = parse_duty_levels(args.duty)
    except Exception as exc:
        print(f"[fan-pwm] {exc}", file=sys.stderr)
        return 2

    try:
        driver = build_driver(args.pin, args.frequency)
    except Exception as exc:
        print(f"[fan-pwm] failed to initialize PWM: {exc}", file=sys.stderr)
        return 1

    running = True

    def handle_signal(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(
        f"[fan-pwm] using {driver.label} on GPIO{args.pin} at {args.frequency}Hz; "
        f"duty cycle loop: {levels}"
    )
    print("[fan-pwm] press Ctrl+C to stop")

    try:
        if args.boost_seconds > 0:
            print(f"[fan-pwm] startup boost: 100% for {args.boost_seconds:.1f}s")
            driver.set_percent(100)
            time.sleep(args.boost_seconds)

        first_pass = True
        while running:
            for duty in levels:
                if not running:
                    break
                print(f"[fan-pwm] duty -> {duty}%")
                driver.set_percent(duty)
                time.sleep(args.hold)
            if args.once and first_pass:
                break
            first_pass = False
    finally:
        print("[fan-pwm] stopping PWM")
        driver.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
