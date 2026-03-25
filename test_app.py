import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from nexcode.app import NexCodeApp

def test_app_startup_no_workspace(mocker):
    # Setup
    app = NexCodeApp()

    # Mock display
    app.display = MagicMock()

    # Mock workspace_file.is_file() to return False
    mocker.patch.object(Path, 'is_file', return_value=False)

    # Execute
    app.startup()

    # Verify
    app.display.show_banner.assert_called_once()
    app.display.system.assert_not_called()
    app.display.show_ready.assert_called_once_with(
        model=app.provider.current_model,
        provider=app.provider.current_provider,
    )

def test_app_startup_with_workspace(mocker):
    # Setup
    app = NexCodeApp()

    # Mock display
    app.display = MagicMock()

    # Mock workspace_file.is_file() to return True
    mocker.patch.object(Path, 'is_file', return_value=True)

    # Execute
    app.startup()

    # Verify
    app.display.show_banner.assert_called_once()
    app.display.system.assert_called_once_with(
        f"Loaded workspace instructions from {app.config.workspace_file}"
    )
    app.display.show_ready.assert_called_once_with(
        model=app.provider.current_model,
        provider=app.provider.current_provider,
    )
