import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from nexcode.config import (
    load_config,
    NexCodeConfig,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_MAX_TOKENS,
    DEFAULT_THEME,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_WORKSPACE_FILE,
)


class TestLoadConfig(unittest.TestCase):

    @patch("nexcode.config._find_config_paths")
    def test_load_config_no_files(self, mock_find_paths):
        """Test load_config when no configuration files exist."""
        mock_find_paths.return_value = []

        config = load_config()

        self.assertEqual(config.default_model, DEFAULT_MODEL)
        self.assertEqual(config.default_provider, DEFAULT_PROVIDER)
        self.assertEqual(config.api_keys, {})
        self.assertEqual(config.permission_mode, DEFAULT_PERMISSION_MODE)
        self.assertEqual(config.max_tokens, DEFAULT_MAX_TOKENS)
        self.assertEqual(config.theme, DEFAULT_THEME)
        self.assertEqual(config.auto_save_session, True)
        self.assertEqual(config.workspace_file, DEFAULT_WORKSPACE_FILE)
        self.assertEqual(config._loaded_from, [])

    @patch("nexcode.config._parse_toml")
    @patch("nexcode.config._find_config_paths")
    def test_load_config_single_file(self, mock_find_paths, mock_parse_toml):
        """Test load_config overriding values from a single config file."""
        mock_path = Path("/home/user/.nexcode.toml")
        mock_find_paths.return_value = [mock_path]

        mock_parse_toml.return_value = {
            "default_model": "test-model-1",
            "theme": "light",
            "max_tokens": 1000,
            "api_keys": {"openai": "test-key"}
        }

        config = load_config()

        self.assertEqual(config.default_model, "test-model-1")
        self.assertEqual(config.theme, "light")
        self.assertEqual(config.max_tokens, 1000)
        self.assertEqual(config.api_keys, {"openai": "test-key"})
        self.assertEqual(config._loaded_from, [str(mock_path)])

    @patch("nexcode.config._parse_toml")
    @patch("nexcode.config._find_config_paths")
    def test_load_config_multiple_files_merge(self, mock_find_paths, mock_parse_toml):
        """Test load_config merging values from multiple config files (user vs project priorities)."""
        user_path = Path("/home/user/.nexcode.toml")
        project_path = Path("/home/user/project/.nexcode.toml")
        mock_find_paths.return_value = [user_path, project_path]

        def parse_toml_side_effect(path):
            if path == user_path:
                return {
                    "default_model": "user-model",
                    "theme": "light",
                    "api_keys": {"openai": "user-key", "anthropic": "user-anthropic"}
                }
            elif path == project_path:
                return {
                    "default_model": "project-model",
                    "max_tokens": 500,
                    "api_keys": {"openai": "project-key"}
                }
            return {}

        mock_parse_toml.side_effect = parse_toml_side_effect

        config = load_config()

        # Project should override user
        self.assertEqual(config.default_model, "project-model")
        self.assertEqual(config.theme, "light")  # from user
        self.assertEqual(config.max_tokens, 500)  # from project

        # Dictionaries should be merged
        self.assertEqual(config.api_keys, {"openai": "project-key", "anthropic": "user-anthropic"})

        self.assertEqual(config._loaded_from, [str(user_path), str(project_path)])

    @patch("nexcode.config._parse_toml")
    @patch("nexcode.config._find_config_paths")
    def test_load_config_invalid_permission_mode(self, mock_find_paths, mock_parse_toml):
        """Test load_config invalid permission_mode raises ValueError."""
        mock_path = Path("/home/user/.nexcode.toml")
        mock_find_paths.return_value = [mock_path]
        mock_parse_toml.return_value = {"permission_mode": "invalid-mode"}

        with self.assertRaises(ValueError) as context:
            load_config()

        self.assertTrue("Invalid permission_mode 'invalid-mode'" in str(context.exception))

    @patch("nexcode.config._parse_toml")
    @patch("nexcode.config._find_config_paths")
    def test_load_config_invalid_theme(self, mock_find_paths, mock_parse_toml):
        """Test load_config invalid theme raises ValueError."""
        mock_path = Path("/home/user/.nexcode.toml")
        mock_find_paths.return_value = [mock_path]
        mock_parse_toml.return_value = {"theme": "invalid-theme"}

        with self.assertRaises(ValueError) as context:
            load_config()

        self.assertTrue("Invalid theme 'invalid-theme'" in str(context.exception))

    @patch("nexcode.config._parse_toml")
    @patch("nexcode.config._find_config_paths")
    def test_load_config_invalid_max_tokens(self, mock_find_paths, mock_parse_toml):
        """Test load_config invalid max_tokens raises ValueError."""
        mock_path = Path("/home/user/.nexcode.toml")
        mock_find_paths.return_value = [mock_path]
        mock_parse_toml.return_value = {"max_tokens": "not-an-int"}

        with self.assertRaises(ValueError) as context:
            load_config()

        self.assertTrue("max_tokens must be an integer" in str(context.exception))


if __name__ == "__main__":
    unittest.main()
