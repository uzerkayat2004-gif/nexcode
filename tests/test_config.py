import pytest
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from nexcode.config import NexCodeConfig, save_config

def test_save_config_explicit_path(tmp_path: Path):
    """Test saving config to an explicit path."""
    config = NexCodeConfig(
        default_model="test-model",
        theme="light",
        api_keys={"openai": "test-key"}
    )
    test_path = tmp_path / "test_config.toml"

    returned_path = save_config(config, test_path)

    assert returned_path == test_path
    assert test_path.exists()

    with open(test_path, "rb") as f:
        data = tomllib.load(f)

    assert data["default_model"] == "test-model"
    assert data["theme"] == "light"
    assert data["api_keys"] == {"openai": "test-key"}

def test_save_config_default_path(monkeypatch, tmp_path: Path):
    """Test saving config to the default path (mocked home directory)."""
    # Mock Path.home() to return tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config = NexCodeConfig(default_model="default-test-model")
    expected_path = tmp_path / ".nexcode.toml"

    returned_path = save_config(config)

    assert returned_path == expected_path
    assert expected_path.exists()

    with open(expected_path, "rb") as f:
        data = tomllib.load(f)

    assert data["default_model"] == "default-test-model"

def test_save_config_no_api_keys(tmp_path: Path):
    """Test saving config without api_keys omits the api_keys section."""
    config = NexCodeConfig()
    config.api_keys = {}  # Explicitly empty

    test_path = tmp_path / "no_keys.toml"
    save_config(config, test_path)

    with open(test_path, "rb") as f:
        data = tomllib.load(f)

    assert "api_keys" not in data

def test_save_config_creates_parent_directories(tmp_path: Path):
    """Test saving config creates necessary parent directories."""
    config = NexCodeConfig()
    test_path = tmp_path / "deep" / "nested" / "dir" / "config.toml"

    returned_path = save_config(config, test_path)

    assert returned_path == test_path
    assert test_path.exists()
    assert test_path.parent.exists()
