"""Tests for utility functions in scrapers.base."""

import pytest

from scrapers.base import normalize_count, clean_text, get_first_n_words


class TestNormalizeCount:
    """Tests for normalize_count() number formatting."""

    def test_empty_string(self):
        assert normalize_count("") == ""

    def test_plain_number(self):
        assert normalize_count("516") == "516"

    def test_comma_separated(self):
        assert normalize_count("3,000,000") == "3000000"

    def test_plus_suffix(self):
        assert normalize_count("2,800,000+") == "2800000"

    def test_k_suffix(self):
        assert normalize_count("1.3K") == "1300"

    def test_k_suffix_whole(self):
        assert normalize_count("30.3K") == "30300"

    def test_m_suffix(self):
        assert normalize_count("4.5M") == "4500000"

    def test_b_suffix(self):
        assert normalize_count("1.2B") == "1200000000"

    def test_lowercase_suffix(self):
        assert normalize_count("1.3k") == "1300"

    def test_directional_marks_stripped(self):
        assert normalize_count("\u202a3,000\u202c") == "3000"

    def test_non_numeric_passthrough(self):
        assert normalize_count("unknown") == "unknown"


class TestCleanText:
    """Tests for clean_text() text cleaning."""

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_none(self):
        assert clean_text(None) == ""

    def test_plain_text_unchanged(self):
        assert clean_text("Hello World") == "Hello World"

    def test_preserves_unicode_accents(self):
        assert clean_text("Müller") == "Müller"

    def test_preserves_german_characters(self):
        assert clean_text("Ä Ö Ü ä ö ü ß") == "Ä Ö Ü ä ö ü ß"

    def test_preserves_french_characters(self):
        assert clean_text("café résumé naïve") == "café résumé naïve"

    def test_removes_directional_marks(self):
        assert clean_text("\u202aHello\u202c") == "Hello"

    def test_collapses_multiple_spaces(self):
        assert clean_text("Hello    World") == "Hello World"

    def test_strips_surrounding_whitespace(self):
        assert clean_text("  Hello  ") == "Hello"

    def test_preserves_newlines_and_tabs(self):
        result = clean_text("Line1\nLine2\tTabbed")
        assert "Line1\nLine2\tTabbed" == result

    def test_removes_control_characters(self):
        result = clean_text("Hello\x00\x01World")
        assert result == "HelloWorld"


class TestGetFirstNWords:
    """Tests for get_first_n_words() text truncation."""

    def test_empty_string(self):
        assert get_first_n_words("") == ""

    def test_none(self):
        assert get_first_n_words(None) == ""

    def test_fewer_words_than_n(self):
        assert get_first_n_words("Hello World", 50) == "Hello World"

    def test_exact_n_words(self):
        assert get_first_n_words("one two three", 3) == "one two three"

    def test_truncates_to_n_words(self):
        text = "one two three four five six"
        assert get_first_n_words(text, 3) == "one two three"

    def test_default_is_50_words(self):
        text = " ".join(f"word{i}" for i in range(100))
        result = get_first_n_words(text)
        assert len(result.split()) == 50

    def test_handles_extra_whitespace(self):
        text = "one   two   three   four"
        assert get_first_n_words(text, 2) == "one two"
