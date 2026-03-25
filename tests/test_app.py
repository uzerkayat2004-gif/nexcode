from unittest.mock import MagicMock, patch

import pytest

from nexcode.app import NexCodeApp


@pytest.fixture
def mock_app():
    with patch("nexcode.app.load_config"), \
         patch("nexcode.app.Display"), \
         patch("nexcode.app.ConversationHistory"), \
         patch("nexcode.app.AuthManager"), \
         patch("nexcode.app.AIProvider"), \
         patch("nexcode.app.CommandRegistry"), \
         patch("nexcode.app.ToolRegistry"):

        app = NexCodeApp()

        app.startup = MagicMock()
        app.shutdown = MagicMock()
        app._loop = MagicMock()

        yield app


def test_run_success(mock_app):
    """Test that NexCodeApp.run calls startup, asyncio.run(_loop()), and shutdown."""
    with patch("nexcode.app.asyncio.run") as mock_run:
        mock_app.run()

        # Ensure startup is called first
        mock_app.startup.assert_called_once()

        # Ensure _loop is executed via asyncio.run
        # The mock_run call evaluates mock_app._loop() once as an argument
        mock_app._loop.assert_called_once()
        mock_run.assert_called_once_with(mock_app._loop.return_value)

        # Ensure shutdown is called last
        mock_app.shutdown.assert_called_once()


def test_run_keyboard_interrupt(mock_app):
    """Test that NexCodeApp.run gracefully handles KeyboardInterrupt."""
    with patch("nexcode.app.asyncio.run", side_effect=KeyboardInterrupt) as mock_run:
        # Calling run should not raise an exception, as KeyboardInterrupt is caught
        mock_app.run()

        # Ensure startup is called first
        mock_app.startup.assert_called_once()

        # Ensure _loop is executed via asyncio.run
        mock_app._loop.assert_called_once()
        mock_run.assert_called_once_with(mock_app._loop.return_value)

        # Ensure shutdown is still called in finally block
        mock_app.shutdown.assert_called_once()


def test_run_other_exception(mock_app):
    """Test that NexCodeApp.run propagates other exceptions, but still calls shutdown."""
    class TestError(Exception):
        pass

    with patch("nexcode.app.asyncio.run", side_effect=TestError) as mock_run:
        # Calling run should propagate the TestError
        with pytest.raises(TestError):
            mock_app.run()

        # Ensure startup is called first
        mock_app.startup.assert_called_once()

        # Ensure _loop is executed via asyncio.run
        mock_app._loop.assert_called_once()
        mock_run.assert_called_once_with(mock_app._loop.return_value)

        # Ensure shutdown is still called in finally block
        mock_app.shutdown.assert_called_once()
