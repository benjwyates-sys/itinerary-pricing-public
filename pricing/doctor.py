"""The health check. Its entire audience is a non-technical operator on the
phone to a developer, so every message must be readable aloud.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import openpyxl

from pricing.config import Config


@dataclass
class Check:
    name: str
    ok: bool
    message: str


def run_checks(config: Config) -> list[Check]:
    return [
        _config_check(config),
        _python_check(),
        _openpyxl_check(),
        _workbook_check(config),
        _data_dir_check(config),
    ]


def _config_check(config: Config) -> Check:
    if config.config_error:
        return Check("config", False, config.config_error)
    return Check("config", True, "Your settings file is good.")


def _python_check() -> Check:
    ok = sys.version_info >= (3, 12)
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    return Check(
        "python", ok,
        f"Python {version} is installed and working." if ok
        else f"Python {version} is too old. Ask for help reinstalling — we need 3.12 or newer.",
    )


def _openpyxl_check() -> Check:
    return Check("openpyxl", True,
                 "Excel support is working.")


def _workbook_check(config: Config) -> Check:
    if config.costing_workbook is None:
        return Check("workbook", False,
                     "You haven't told me where your costing workbook is yet. "
                     "Run /profile and point me at it.")
    if not config.costing_workbook.exists():
        return Check("workbook", False,
                     f"I can't find your costing workbook — I was looking for "
                     f"{config.costing_workbook.name}. Has it been moved or renamed? "
                     "Run /profile to point me at it again.")
    try:
        openpyxl.load_workbook(config.costing_workbook, read_only=True).close()
    except Exception:
        return Check("workbook", False,
                     f"I found {config.costing_workbook.name} but couldn't open it. "
                     "It might be open in Excel, or the folder might be read-only. "
                     "Please close the file (if open) and try again, or ask for help with permissions.")
    return Check("workbook", True,
                 f"Found and opened your costing workbook ({config.costing_workbook.name}).")


def _data_dir_check(config: Config) -> Check:
    try:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        # Use a unique name with process ID to avoid collisions
        probe_name = f".write-test-{os.getpid()}"
        probe = config.data_dir / probe_name
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        finally:
            probe.unlink(missing_ok=True)
    except Exception:
        return Check("data", False,
                     "I can't save anything to the pricing folder. "
                     "Ask for help — the folder's permissions need changing.")
    return Check("data", True, "I can save your mappings and quotes.")
