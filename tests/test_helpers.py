import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from nexcode.utils.helpers import (
    timestamp_iso,
    timestamp_short,
    slugify,
    truncate,
    file_size_human,
    resolve_path,
    Timer
)

def test_timestamp_iso():
    fixed_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    with patch("nexcode.utils.helpers.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        assert timestamp_iso() == "2024-01-15T12:00:00+00:00"

def test_timestamp_short():
    fixed_now = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
    with patch("nexcode.utils.helpers.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        assert timestamp_short() == "2024-01-15 12:30"

@pytest.mark.parametrize("text, expected", [
    ("Hello World", "hello-world"),
    ("  Hello World  ", "hello-world"),
    ("Hello_World", "hello-world"),
    ("Hello---World", "hello-world"),
    ("Hello! @World#", "hello-world"),
    ("Python 3.11", "python-311"),
])
def test_slugify(text, expected):
    assert slugify(text) == expected

def test_slugify_max_length():
    assert slugify("a" * 100, max_length=10) == "a" * 10

@pytest.mark.parametrize("text, max_length, suffix, expected", [
    ("Hello World", 20, "...", "Hello World"),
    ("Hello World", 11, "...", "Hello World"),
    ("Hello World", 10, "...", "Hello W..."),
    ("Hello World", 5, "...", "He..."),
    ("Hello World", 10, "!", "Hello Wor!"),
])
def test_truncate(text, max_length, suffix, expected):
    assert truncate(text, max_length=max_length, suffix=suffix) == expected

@pytest.mark.parametrize("size, expected", [
    (500, "500.0 B"),
    (1024, "1.0 KB"),
    (1024**2, "1.0 MB"),
    (1024**3, "1.0 GB"),
    (1024**4, "1.0 TB"),
    (1024**5, "1.0 PB"),
    (-1024, "-1.0 KB"),
])
def test_file_size_human(size, expected):
    assert file_size_human(size) == expected

def test_resolve_path_absolute():
    abs_path = os.path.abspath("/tmp/test")
    assert resolve_path(abs_path) == Path(abs_path)

def test_resolve_path_relative():
    rel_path = "test.txt"
    expected = Path.cwd() / rel_path
    assert resolve_path(rel_path) == expected

def test_resolve_path_with_base():
    base = Path("/home/user")
    rel_path = "docs/file.pdf"
    # Note: resolve() will try to resolve symlinks and real path.
    # Since /home/user might not exist, we just check if it's joined correctly
    # But resolve_path calls .resolve() which might be tricky in a mock-less way if path doesn't exist
    # Actually Path("/home/user/docs/file.pdf").resolve() works even if it doesn't exist on some systems,
    # but it usually resolves based on current FS.

    # Let's use current directory to be safe
    base = Path.cwd()
    rel_path = "test_file.tmp"
    assert resolve_path(rel_path, base=base) == (base / rel_path).resolve()

def test_resolve_path_home():
    home_path = Path.home()
    assert resolve_path("~") == home_path

def test_timer():
    with patch("time.perf_counter") as mock_perf:
        mock_perf.side_effect = [10.0, 12.5]
        with Timer() as t:
            pass
        assert t.elapsed == 2.5
