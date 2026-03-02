"""Tests for CSVHandler read/write and resume capability."""

import csv

import pytest

from utils.csv_handler import CSVHandler, ExtensionInput


@pytest.fixture
def input_csv(tmp_path):
    """Create a sample input CSV file."""
    path = tmp_path / "input.csv"
    path.write_text("extension_id\nabc\ndef\nghi\n")
    return str(path)


@pytest.fixture
def output_csv(tmp_path):
    """Return a path for the output CSV (does not exist yet)."""
    return str(tmp_path / "output.csv")


class TestCSVHandlerInit:
    """Tests for CSVHandler initialization."""

    def test_raises_on_missing_input_when_reading(self, tmp_path):
        handler = CSVHandler(str(tmp_path / "missing.csv"), str(tmp_path / "output.csv"))
        with pytest.raises(FileNotFoundError):
            handler.count_total()

    def test_loads_with_valid_input(self, input_csv, output_csv):
        handler = CSVHandler(input_csv, output_csv)
        assert handler.count_total() == 3
        assert handler.count_processed() == 0


class TestGetPendingExtensions:
    """Tests for the pending extensions generator."""

    def test_yields_all_when_no_output(self, input_csv, output_csv):
        handler = CSVHandler(input_csv, output_csv)
        pending = list(handler.get_pending_extensions())
        assert len(pending) == 3
        assert pending[0].extension_id == "abc"

    def test_skips_processed_ids(self, input_csv, tmp_path):
        output_path = tmp_path / "output.csv"
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSVHandler.OUTPUT_FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "extension_id": "abc", "browser": "chrome", "name": "Test",
                "type": "", "developer": "", "category": "",
                "user_count": "", "rating": "", "rating_count": "",
                "overview": "", "link": "", "status": "success",
            })

        handler = CSVHandler(input_csv, str(output_path))
        pending = list(handler.get_pending_extensions())
        assert len(pending) == 2
        assert pending[0].extension_id == "def"

    def test_skips_empty_rows(self, tmp_path, output_csv):
        input_path = tmp_path / "input.csv"
        input_path.write_text("extension_id\nabc\n\ndef\n")
        handler = CSVHandler(str(input_path), output_csv)
        pending = list(handler.get_pending_extensions())
        assert len(pending) == 2


class TestWriteResult:
    """Tests for writing results to the output CSV."""

    def test_creates_output_with_header(self, input_csv, output_csv):
        handler = CSVHandler(input_csv, output_csv)
        handler.write_result({
            "extension_id": "abc", "browser": "chrome", "name": "Test Ext",
            "type": "Extension", "developer": "Dev", "category": "Tools",
            "user_count": "1000", "rating": "4.5", "rating_count": "100",
            "overview": "A test extension", "link": "https://example.com",
            "status": "success",
        })

        with open(output_csv, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["name"] == "Test Ext"
        assert rows[0]["extension_id"] == "abc"

    def test_appends_to_existing_output(self, input_csv, output_csv):
        handler = CSVHandler(input_csv, output_csv)
        base_row = {
            "extension_id": "", "browser": "chrome", "name": "",
            "type": "", "developer": "", "category": "",
            "user_count": "", "rating": "", "rating_count": "",
            "overview": "", "link": "", "status": "success",
        }

        handler.write_result({**base_row, "extension_id": "abc", "name": "First"})
        handler.write_result({**base_row, "extension_id": "def", "name": "Second"})

        with open(output_csv, "r") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2
        assert rows[1]["name"] == "Second"

    def test_tracks_processed_ids(self, input_csv, output_csv):
        handler = CSVHandler(input_csv, output_csv)
        assert handler.count_processed() == 0

        handler.write_result({
            "extension_id": "abc", "browser": "chrome", "name": "Test",
            "type": "", "developer": "", "category": "",
            "user_count": "", "rating": "", "rating_count": "",
            "overview": "", "link": "", "status": "success",
        })

        assert handler.count_processed() == 1


class TestResume:
    """Tests for resume capability across handler instances."""

    def test_new_handler_picks_up_processed(self, input_csv, output_csv):
        handler1 = CSVHandler(input_csv, output_csv)
        handler1.write_result({
            "extension_id": "abc", "browser": "chrome", "name": "Test",
            "type": "", "developer": "", "category": "",
            "user_count": "", "rating": "", "rating_count": "",
            "overview": "", "link": "", "status": "success",
        })

        handler2 = CSVHandler(input_csv, output_csv)
        assert handler2.count_processed() == 1
        pending = list(handler2.get_pending_extensions())
        assert len(pending) == 2
        assert all(p.extension_id != "abc" for p in pending)
