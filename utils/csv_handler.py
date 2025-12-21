import csv
import os
from dataclasses import dataclass
from typing import Generator


@dataclass
class ExtensionInput:
    """Input row from CSV."""
    extension_id: str


class CSVHandler:
    """Handles CSV reading/writing with resume capability."""

    OUTPUT_FIELDNAMES = [
        "extension_id",
        "browser",
        "name",
        "type",
        "developer",
        "category",
        "user_count",
        "rating",
        "rating_count",
        "overview",
        "link",
        "status",
    ]

    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file
        self._processed_ids: set[str] = set()
        self._load_processed()

    def _load_processed(self) -> None:
        """Load already-processed extension IDs from output file."""
        if not os.path.exists(self.output_file):
            return

        with open(self.output_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._processed_ids.add(row['extension_id'])

    def get_pending_extensions(self) -> Generator[ExtensionInput, None, None]:
        """
        Yield extensions that haven't been processed yet.
        Reads only the first column as extension_id.

        Yields:
            ExtensionInput objects for unprocessed extensions.
        """
        with open(self.input_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)

            if not header:
                raise ValueError("Input CSV is empty")

            for row in reader:
                if not row:
                    continue
                ext_id = row[0].strip()
                if ext_id and ext_id not in self._processed_ids:
                    yield ExtensionInput(extension_id=ext_id)

    def count_total(self) -> int:
        """Count total extensions in input file."""
        with open(self.input_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            return sum(1 for row in reader if row and row[0].strip())

    def count_processed(self) -> int:
        """Count already-processed extensions."""
        return len(self._processed_ids)

    def write_result(self, result: dict) -> None:
        """
        Append a single result to the output file.

        Args:
            result: Dictionary with extension metadata.
        """
        file_exists = os.path.exists(self.output_file)

        with open(self.output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.OUTPUT_FIELDNAMES)

            if not file_exists:
                writer.writeheader()

            writer.writerow(result)

        self._processed_ids.add(result['extension_id'])
