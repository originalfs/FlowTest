import json

import pytest

from localflow.config import Config, load_config, save_config


def test_defaults_are_valid():
    Config().validate()


def test_roundtrip(tmp_path):
    cfg = Config(model="small", hotkey="ctrl+shift+d", dictionary={"a b": "AB"})
    path = save_config(cfg, tmp_path / "config.json")
    loaded = load_config(path)
    assert loaded == cfg


def test_missing_file_returns_defaults(tmp_path):
    assert load_config(tmp_path / "nope.json") == Config()


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "tiny", "future_option": 1}))
    assert load_config(path).model == "tiny"


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "hold"),
        ("injection", "telepathy"),
        ("sample_rate", 0),
        ("hotkey", "  "),
    ],
)
def test_invalid_values_rejected(field, value):
    cfg = Config(**{field: value})
    with pytest.raises(ValueError):
        cfg.validate()


def test_env_override_for_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALFLOW_CONFIG_DIR", str(tmp_path / "cfg"))
    from localflow.config import config_path

    assert str(config_path()).startswith(str(tmp_path / "cfg"))
