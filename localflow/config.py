"""Configuration for LocalFlow, stored as JSON in the user's config directory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

VALID_MODES = ("push_to_talk", "toggle")
VALID_INJECTION = ("type", "paste")


def config_dir() -> Path:
    base = os.environ.get("LOCALFLOW_CONFIG_DIR")
    if base:
        return Path(base)
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "localflow"


def data_dir() -> Path:
    base = os.environ.get("LOCALFLOW_DATA_DIR")
    if base:
        return Path(base)
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "localflow"


@dataclass
class Config:
    # Whisper model: tiny/base/small/medium/large-v3, or a path to a local model dir.
    model: str = "base"
    # "auto" picks CUDA if available, else CPU.
    device: str = "auto"
    compute_type: str = "auto"
    # None = autodetect language from speech.
    language: str | None = None
    # Hotkey combo, e.g. "ctrl+alt+space".
    hotkey: str = "ctrl+alt+space"
    # "push_to_talk": record while held. "toggle": press to start, press to stop.
    mode: str = "push_to_talk"
    # "type": simulate keystrokes. "paste": clipboard + Ctrl/Cmd+V (faster for long text).
    injection: str = "type"
    sample_rate: int = 16000
    remove_fillers: bool = True
    capitalize_sentences: bool = True
    # Personal dictionary: spoken form -> written form, e.g. {"local flow": "LocalFlow"}.
    dictionary: dict[str, str] = field(default_factory=dict)
    save_history: bool = True

    def validate(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {self.mode!r}")
        if self.injection not in VALID_INJECTION:
            raise ValueError(
                f"injection must be one of {VALID_INJECTION}, got {self.injection!r}"
            )
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if not self.hotkey.strip():
            raise ValueError("hotkey must not be empty")


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        return Config()
    raw = json.loads(path.read_text(encoding="utf-8"))
    known = {f for f in Config.__dataclass_fields__}
    cfg = Config(**{k: v for k, v in raw.items() if k in known})
    cfg.validate()
    return cfg


def save_config(cfg: Config, path: Path | None = None) -> Path:
    cfg.validate()
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8")
    return path
