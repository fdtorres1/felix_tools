#!/usr/bin/env python3
"""
Tests for handwrytten-cli

Run with: python -m pytest tests/test_handwrytten.py -v
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from handwrytten import (
    HandwryttenClient,
    HandwryttenError,
    build_parser,
    format_output,
    split_name,
)


class TestSplitName:
    """Tests for the split_name helper function."""

    def test_full_name(self):
        """Test splitting a full name with first and last."""
        first, last = split_name("John Doe")
        assert first == "John"
        assert last == "Doe"

    def test_name_with_multiple_parts(self):
        """Test name with multiple last name parts."""
        first, last = split_name("John van der Berg")
        assert first == "John"
        assert last == "van der Berg"

    def test_single_name(self):
        """Test with only one name."""
        first, last = split_name("Madonna")
        assert first == "Madonna"
        assert last == ""

    def test_empty_name(self):
        """Test with empty string."""
        first, last = split_name("")
        assert first == ""
        assert last == ""

    def test_whitespace_name(self):
        """Test with whitespace."""
        first, last = split_name("   Jane   Smith   ")
        assert first == "Jane"
        assert last == "Smith"


class TestFormatOutput:
    """Tests for output formatting."""

    def test_json_format(self):
        """Test JSON output format."""
        data = {"key": "value", "number": 42}
        output = format_output(data, "json")
        parsed = json.loads(output)
        assert parsed == data

    def test_table_format_cards(self):
        """Test table format for cards list."""
        data = {
            "cards": [
                {"id": 1, "card_name": "Birthday Card", "description": "A birthday card", "price": "5.99"},
                {"id": 2, "card_name": "Thank You", "description": "Thank you card", "price": "4.99"},
            ]
        }
        output = format_output(data, "table")
        assert "Birthday Card" in output
        assert "Thank You" in output
        assert "5.99" in output

    def test_table_format_fonts(self):
        """Test table format for fonts list."""
        data = {
            "fonts": [
                {"id": "font1", "label": "Chill Charles", "line_spacing": 1.2},
                {"id": "font2", "label": "Friendly Frank", "line_spacing": 1.0},
            ]
        }
        output = format_output(data, "table")
        assert "Chill Charles" in output
        assert "Friendly Frank" in output

    def test_table_format_categories(self):
        """Test table format for categories list."""
        data = {
            "categories": [
                {"id": 1, "name": "Birthday"},
                {"id": 2, "name": "Thank You"},
            ]
        }
        output = format_output(data, "table")
        assert "Birthday" in output
        assert "Thank You" in output


class TestHandwryttenClient:
    """Tests for the Handwrytten API client."""

    def test_country_to_id_usa(self):
        """Test US country ID mapping."""
        assert HandwryttenClient._country_to_id("United States") == 1
        assert HandwryttenClient._country_to_id("USA") == 1
        assert HandwryttenClient._country_to_id("us") == 1

    def test_country_to_id_canada(self):
        """Test Canada country ID mapping."""
        assert HandwryttenClient._country_to_id("Canada") == 2

    def test_country_to_id_uk(self):
        """Test UK country ID mapping."""
        assert HandwryttenClient._country_to_id("United Kingdom") == 3
        assert HandwryttenClient._country_to_id("UK") == 3

    def test_country_to_id_unknown(self):
        """Test unknown country defaults to US."""
        assert HandwryttenClient._country_to_id("Unknown Country") == 1

    @patch("handwrytten.requests.Session")
    def test_list_cards_basic(self, mock_session_class):
        """Test basic card listing."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "cards": []}
        mock_session.request.return_value = mock_response

        client = HandwryttenClient("test-api-key")
        result = client.list_cards()

        assert result["status"] == "success"
        mock_session.request.assert_called_once()

    @patch("handwrytten.requests.Session")
    def test_list_cards_with_params(self, mock_session_class):
        """Test card listing with parameters."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "cards": []}
        mock_session.request.return_value = mock_response

        client = HandwryttenClient("test-api-key")
        client.list_cards(category_id=5, with_images=True, page=2)

        call_args = mock_session.request.call_args
        params = call_args.kwargs["params"]
        assert params["category_id"] == 5
        assert params["with_images"] == "true"
        assert params["page"] == 2

    @patch("handwrytten.requests.Session")
    def test_api_error_handling(self, mock_session_class):
        """Test API error response handling."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "message": "Invalid API key"}
        mock_session.request.return_value = mock_response

        client = HandwryttenClient("bad-api-key")
        
        with pytest.raises(HandwryttenError) as exc_info:
            client.list_cards()
        
        assert "Invalid API key" in str(exc_info.value)


class TestParser:
    """Tests for the argument parser."""

    def test_parser_creation(self):
        """Test that parser can be created."""
        parser = build_parser()
        assert parser is not None

    def test_cards_list_command(self):
        """Test parsing cards list command."""
        parser = build_parser()
        args = parser.parse_args(["cards", "list", "--category-id", "5", "--with-images"])
        assert args.command == "cards"
        assert args.subcommand == "list"
        assert args.category_id == 5
        assert args.with_images is True

    def test_fonts_list_command(self):
        """Test parsing fonts list command."""
        parser = build_parser()
        args = parser.parse_args(["fonts", "list"])
        assert args.command == "fonts"
        assert args.subcommand == "list"

    def test_orders_send_command(self):
        """Test parsing orders send command."""
        parser = build_parser()
        args = parser.parse_args([
            "orders", "send",
            "--card-id", "3404",
            "--message", "Test message",
            "--recipient-name", "John Doe",
            "--recipient-address1", "123 Main St",
            "--recipient-city", "Phoenix",
            "--recipient-state", "AZ",
            "--recipient-zip", "85001",
        ])
        assert args.command == "orders"
        assert args.subcommand == "send"
        assert args.card_id == 3404
        assert args.message == "Test message"
        assert args.recipient_name == "John Doe"

    def test_output_format_option(self):
        """Test output format option."""
        parser = build_parser()
        args = parser.parse_args(["--format", "table", "cards", "list"])
        assert args.format == "table"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

