import sys
from unittest.mock import patch, MagicMock
import pytest

# We import main from run_web.py
from run_web import main

def test_run_web_default_args():
    """Test main() with default arguments."""
    # We must patch sys.modules to simulate uvicorn since it might not be installed
    mock_uvicorn = MagicMock()
    with patch("sys.argv", ["run_web.py"]), \
         patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
        main()
        mock_uvicorn.run.assert_called_once_with(
            "nexcode.server.api:create_app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            factory=True,
            log_level="info",
        )

def test_run_web_custom_args():
    """Test main() with custom arguments."""
    mock_uvicorn = MagicMock()
    with patch("sys.argv", ["run_web.py", "--host", "127.0.0.1", "--port", "3000", "--reload"]), \
         patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
        main()
        mock_uvicorn.run.assert_called_once_with(
            "nexcode.server.api:create_app",
            host="127.0.0.1",
            port=3000,
            reload=True,
            factory=True,
            log_level="info",
        )

def test_run_web_uvicorn_import_error(capsys):
    """Test main() when uvicorn is not installed."""
    # We need to simulate ImportError when `import uvicorn` is called inside main()
    # Mock sys.modules to return None for uvicorn, which triggers ImportError
    with patch("sys.argv", ["run_web.py"]), \
         patch.dict("sys.modules", {"uvicorn": None}):
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify the exit code is 1
        assert exc_info.value.code == 1

        # Verify the error message is printed
        captured = capsys.readouterr()
        assert "uvicorn not installed" in captured.out
