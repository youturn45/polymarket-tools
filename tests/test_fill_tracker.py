"""Tests for fill tracking across tranches."""

from core.fill_tracker import FillTracker, TrancheFill


def test_fill_tracker_initialization():
    """Test FillTracker initialization."""
    tracker = FillTracker(total_size=1000)

    assert tracker.total_size == 1000
    assert tracker.fills == []
    assert tracker.total_filled == 0
    assert tracker.total_remaining == 1000
    assert tracker.tranche_count == 0


def test_record_single_tranche_fill():
    """Test recording a single tranche fill."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)

    assert tracker.tranche_count == 1
    assert tracker.total_filled == 200
    assert tracker.total_remaining == 800


def test_record_multiple_tranche_fills():
    """Test recording multiple tranche fills."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)
    tracker.record_tranche_fill(tranche_number=2, size=200, filled=150, price=0.51)
    tracker.record_tranche_fill(tranche_number=3, size=200, filled=200, price=0.49)

    assert tracker.tranche_count == 3
    assert tracker.total_filled == 550
    assert tracker.total_remaining == 450


def test_total_filled_calculation():
    """Test total filled amount calculation."""
    tracker = FillTracker(total_size=1000)

    # No fills yet
    assert tracker.total_filled == 0

    # Add fills
    tracker.record_tranche_fill(tranche_number=1, size=100, filled=100, price=0.50)
    assert tracker.total_filled == 100

    tracker.record_tranche_fill(tranche_number=2, size=100, filled=75, price=0.51)
    assert tracker.total_filled == 175

    tracker.record_tranche_fill(tranche_number=3, size=100, filled=100, price=0.52)
    assert tracker.total_filled == 275


def test_total_remaining_calculation():
    """Test remaining amount calculation."""
    tracker = FillTracker(total_size=500)

    assert tracker.total_remaining == 500

    tracker.record_tranche_fill(tranche_number=1, size=100, filled=100, price=0.50)
    assert tracker.total_remaining == 400

    tracker.record_tranche_fill(tranche_number=2, size=100, filled=100, price=0.50)
    assert tracker.total_remaining == 300


def test_total_remaining_never_negative():
    """Test that remaining never goes negative."""
    tracker = FillTracker(total_size=100)

    # Overfill (edge case, shouldn't happen in practice)
    tracker.record_tranche_fill(tranche_number=1, size=150, filled=150, price=0.50)

    # Should be 0, not negative
    assert tracker.total_remaining == 0


def test_average_fill_price_no_fills():
    """Test average price with no fills."""
    tracker = FillTracker(total_size=1000)

    assert tracker.average_fill_price == 0.0


def test_average_fill_price_single_fill():
    """Test average price with single fill."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)

    assert tracker.average_fill_price == 0.50


def test_average_fill_price_multiple_fills():
    """Test volume-weighted average price calculation."""
    tracker = FillTracker(total_size=1000)

    # 100 shares @ 0.50 = 50.00
    tracker.record_tranche_fill(tranche_number=1, size=100, filled=100, price=0.50)

    # 200 shares @ 0.60 = 120.00
    tracker.record_tranche_fill(tranche_number=2, size=200, filled=200, price=0.60)

    # Total: 300 shares, 170.00 value
    # Average: 170.00 / 300 = 0.5666...
    expected_avg = (100 * 0.50 + 200 * 0.60) / 300
    assert abs(tracker.average_fill_price - expected_avg) < 0.0001


def test_average_fill_price_partial_fills():
    """Test average price with partial fills."""
    tracker = FillTracker(total_size=1000)

    # 50 filled out of 100 @ 0.50
    tracker.record_tranche_fill(tranche_number=1, size=100, filled=50, price=0.50)

    # 75 filled out of 150 @ 0.60
    tracker.record_tranche_fill(tranche_number=2, size=150, filled=75, price=0.60)

    # Average: (50 * 0.50 + 75 * 0.60) / 125
    expected_avg = (50 * 0.50 + 75 * 0.60) / 125
    assert abs(tracker.average_fill_price - expected_avg) < 0.0001


def test_fill_rate_calculation():
    """Test fill rate percentage calculation."""
    tracker = FillTracker(total_size=1000)

    # No fills
    assert tracker.fill_rate == 0.0

    # 200 filled
    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)
    assert tracker.fill_rate == 0.2  # 200/1000 = 0.2

    # 400 filled total
    tracker.record_tranche_fill(tranche_number=2, size=200, filled=200, price=0.50)
    assert tracker.fill_rate == 0.4  # 400/1000 = 0.4

    # 1000 filled total (complete)
    tracker.record_tranche_fill(tranche_number=3, size=600, filled=600, price=0.50)
    assert tracker.fill_rate == 1.0  # 1000/1000 = 1.0


def test_fill_rate_zero_total_size():
    """Test fill rate with zero total size (edge case)."""
    tracker = FillTracker(total_size=0)

    assert tracker.fill_rate == 0.0


def test_is_complete_empty():
    """Test is_complete with no fills."""
    tracker = FillTracker(total_size=1000)

    assert not tracker.is_complete()


def test_is_complete_partial():
    """Test is_complete with partial fills."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)

    assert not tracker.is_complete()


def test_is_complete_full():
    """Test is_complete when fully filled."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=500, filled=500, price=0.50)
    tracker.record_tranche_fill(tranche_number=2, size=500, filled=500, price=0.50)

    assert tracker.is_complete()


def test_is_complete_overfilled():
    """Test is_complete when overfilled (edge case)."""
    tracker = FillTracker(total_size=100)

    tracker.record_tranche_fill(tranche_number=1, size=150, filled=150, price=0.50)

    # Should be complete even if overfilled
    assert tracker.is_complete()


def test_get_tranche_summary_empty():
    """Test tranche summary with no fills."""
    tracker = FillTracker(total_size=1000)

    summary = tracker.get_tranche_summary()

    assert summary == []


def test_get_tranche_summary_single_fill():
    """Test tranche summary with single fill."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)

    summary = tracker.get_tranche_summary()

    assert len(summary) == 1
    assert summary[0]["tranche"] == 1
    assert summary[0]["size"] == 200
    assert summary[0]["filled"] == 200
    assert summary[0]["price"] == 0.50
    assert summary[0]["fill_rate"] == 1.0


def test_get_tranche_summary_multiple_fills():
    """Test tranche summary with multiple fills."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)
    tracker.record_tranche_fill(tranche_number=2, size=200, filled=150, price=0.51)
    tracker.record_tranche_fill(tranche_number=3, size=200, filled=200, price=0.49)

    summary = tracker.get_tranche_summary()

    assert len(summary) == 3

    # Check first tranche
    assert summary[0]["tranche"] == 1
    assert summary[0]["size"] == 200
    assert summary[0]["filled"] == 200
    assert summary[0]["fill_rate"] == 1.0

    # Check second tranche (partial fill)
    assert summary[1]["tranche"] == 2
    assert summary[1]["size"] == 200
    assert summary[1]["filled"] == 150
    assert summary[1]["fill_rate"] == 0.75

    # Check third tranche
    assert summary[2]["tranche"] == 3
    assert summary[2]["filled"] == 200


def test_get_tranche_summary_includes_timestamp():
    """Test that tranche summary includes timestamp."""
    tracker = FillTracker(total_size=1000)

    tracker.record_tranche_fill(tranche_number=1, size=200, filled=200, price=0.50)

    summary = tracker.get_tranche_summary()

    assert "timestamp" in summary[0]
    # Timestamp should be ISO format string
    assert isinstance(summary[0]["timestamp"], str)


def test_tranche_fill_dataclass():
    """Test TrancheFill dataclass creation."""
    from datetime import datetime

    fill = TrancheFill(
        tranche_number=1,
        size=100,
        filled=100,
        price=0.50,
        timestamp=datetime.now(),
    )

    assert fill.tranche_number == 1
    assert fill.size == 100
    assert fill.filled == 100
    assert fill.price == 0.50
    assert isinstance(fill.timestamp, datetime)
