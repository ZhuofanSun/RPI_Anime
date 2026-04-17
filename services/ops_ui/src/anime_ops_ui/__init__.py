"""Anime operations UI package."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def runtime_main_module(
    *,
    sys_modules: dict[str, Any] | None = None,
    package_main_path: Path | None = None,
) -> ModuleType:
    modules = sys_modules if sys_modules is not None else sys.modules
    candidate = modules.get("__main__")
    target_path = package_main_path or Path(__file__).resolve().with_name("main.py")
    candidate_file = getattr(candidate, "__file__", None)
    if candidate_file:
        try:
            candidate_path = Path(candidate_file).resolve()
        except OSError:
            candidate_path = None
        if candidate_path == target_path:
            return candidate

    from anime_ops_ui import main as main_module

    return main_module
