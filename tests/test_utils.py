"""Tests for utility functions."""


def test_gamma_parse_imports():
    """Test that gamma_parse can be imported."""
    from utils import gamma_parse

    # Verify key functions exist
    assert hasattr(gamma_parse, "fetch_market_data")
    assert hasattr(gamma_parse, "parse_token_ids")
    assert hasattr(gamma_parse, "format_price")


def test_format_price():
    """Test price formatting."""
    from utils.gamma_parse import format_price

    assert format_price("0.5") == "0.500"
    assert format_price("0.12345") == "0.123"
    assert format_price("invalid") == "invalid"


def test_parse_token_ids():
    """Test token ID parsing."""
    from utils.gamma_parse import parse_token_ids

    # Valid JSON
    result = parse_token_ids('["token1", "token2"]')
    assert result == ["token1", "token2"]

    # Invalid JSON
    result = parse_token_ids("invalid")
    assert result == []

    # Empty
    result = parse_token_ids("[]")
    assert result == []
