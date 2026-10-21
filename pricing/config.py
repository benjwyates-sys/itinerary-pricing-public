"""Where everything lives. One file, one source of truth for paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    root: Path
    costing_workbook: Path | None = None
    config_error: str | None = None

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.json"

    @property
    def aliases_path(self) -> Path:
        return self.data_dir / "aliases.json"

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def template_path(self) -> Path:
        return self.profiles_dir / "itinerary_template.json"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(root: Path | None = None) -> Config:
    config = Config(root=Path(root) if root else _default_root())
    if config.config_path.exists():
        try:
            data = json.loads(config.config_path.read_text(encoding="utf-8"))
            raw = data.get("costing_workbook")
            config.costing_workbook = Path(raw) if raw else None
        except (json.JSONDecodeError, AttributeError, TypeError, OSError) as e:
            config.config_error = (
                f"Your settings file couldn't be read, so I've forgotten where your workbook is. "
                f"Run /profile to point me at it again."
            )
    return config


def save_config(config: Config) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "costing_workbook": str(config.costing_workbook) if config.costing_workbook else None
    }
    config.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
