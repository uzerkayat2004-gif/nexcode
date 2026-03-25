from unittest.mock import MagicMock
from nexcode.app import NexCodeApp
from nexcode.config import NexCodeConfig


def test_shutdown_with_auto_save():
    """Test shutdown when auto_save_session is True."""
    config = NexCodeConfig(auto_save_session=True)
    app = NexCodeApp(config=config)
    app.display.system = MagicMock()

    app.shutdown()

    # Should print two system messages: "Session saved." and "Goodbye! 👋"
    assert app.display.system.call_count == 2
    app.display.system.assert_any_call("Session saved.")
    app.display.system.assert_any_call("Goodbye! 👋")


def test_shutdown_without_auto_save():
    """Test shutdown when auto_save_session is False."""
    config = NexCodeConfig(auto_save_session=False)
    app = NexCodeApp(config=config)
    app.display.system = MagicMock()

    app.shutdown()

    # Should only print one system message: "Goodbye! 👋"
    app.display.system.assert_called_once_with("Goodbye! 👋")
