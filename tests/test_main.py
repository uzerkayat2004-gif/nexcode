"""Tests for the main NexCode CLI entry point."""

import sys
from unittest.mock import MagicMock, patch

from main import main


@patch("nexcode.app.NexCodeApp")
@patch("nexcode.config.load_config")
def test_main_success(mock_load_config, mock_nexcode_app):
    """Test successful bootstrap and launch of NexCode."""
    mock_config = MagicMock()
    mock_load_config.return_value = mock_config

    mock_app_instance = MagicMock()
    mock_nexcode_app.return_value = mock_app_instance

    main()

    mock_load_config.assert_called_once_with()
    mock_nexcode_app.assert_called_once_with(config=mock_config)
    mock_app_instance.run.assert_called_once_with()


@patch("sys.exit")
@patch("builtins.print")
@patch("nexcode.config.load_config")
def test_main_keyboard_interrupt(mock_load_config, mock_print, mock_sys_exit):
    """Test handling of KeyboardInterrupt during startup."""
    mock_load_config.side_effect = KeyboardInterrupt()

    main()

    mock_print.assert_called_once_with("\n  Interrupted. Goodbye! 👋")
    mock_sys_exit.assert_called_once_with(0)


@patch("sys.exit")
@patch("builtins.print")
@patch("nexcode.config.load_config")
def test_main_exception(mock_load_config, mock_print, mock_sys_exit):
    """Test handling of unexpected exceptions during startup."""
    mock_load_config.side_effect = Exception("Test exception")

    main()

    mock_print.assert_called_once_with(
        "\n  ✗ Fatal error during startup: Test exception", file=sys.stderr
    )
    mock_sys_exit.assert_called_once_with(1)
