"""
Tests for the storage module.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from viberdash.storage import MetricsStorage


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def storage(temp_db):
    """Create a MetricsStorage instance with temporary database."""
    return MetricsStorage(db_path=temp_db)


def test_init_db_creates_table(temp_db):
    """Test that init_db creates the metrics table."""
    MetricsStorage(db_path=temp_db)

    # Check table exists
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        assert cursor.fetchone() is not None


def test_save_metrics(storage):
    """Test saving metrics to database."""
    metrics = {
        "avg_complexity": 5.5,
        "maintainability_index": 75.0,
        "test_coverage": 85.5,
        "code_duplication": 3.2,
        "total_functions": 10,
        "total_classes": 5,
        "total_lines": 500,
    }

    record_id = storage.save_metrics(metrics)
    assert record_id > 0


def test_get_latest(storage):
    """Test retrieving the latest metrics."""
    import time
    
    # Save some metrics
    metrics1 = {"avg_complexity": 5.0}
    metrics2 = {"avg_complexity": 6.0}

    id1 = storage.save_metrics(metrics1)
    time.sleep(1.1)  # Ensure different timestamps (SQLite CURRENT_TIMESTAMP has second precision)
    id2 = storage.save_metrics(metrics2)
    
    latest = storage.get_latest()
    assert latest is not None
    assert latest["avg_complexity"] == 6.0


def test_get_history(storage):
    """Test retrieving metrics history."""
    import time
    
    # Save multiple metrics
    for i in range(5):
        storage.save_metrics({"avg_complexity": float(i)})
        time.sleep(1.1)  # Ensure different timestamps (SQLite CURRENT_TIMESTAMP has second precision)

    history = storage.get_history(limit=3)
    assert len(history) == 3
    # Should be in descending order (newest first)
    assert history[0]["avg_complexity"] == 4.0
    assert history[1]["avg_complexity"] == 3.0
    assert history[2]["avg_complexity"] == 2.0


def test_get_previous(storage):
    """Test retrieving the previous metrics entry."""
    import time
    
    # Save two metrics
    storage.save_metrics({"avg_complexity": 5.0})
    time.sleep(1.1)  # Ensure different timestamps (SQLite CURRENT_TIMESTAMP has second precision)
    storage.save_metrics({"avg_complexity": 6.0})

    previous = storage.get_previous()
    assert previous is not None
    assert previous["avg_complexity"] == 5.0


def test_cleanup_old_entries(storage):
    """Test cleaning up old entries."""
    # This test would require mocking datetime or waiting
    # For now, just test that the method doesn't error
    deleted = storage.cleanup_old_entries(keep_days=30)
    assert deleted >= 0


def test_row_to_dict_with_raw_data(storage):
    """Test _row_to_dict with raw_data JSON parsing."""
    import json
    import sqlite3
    
    # Create metrics with nested raw_data
    metrics = {
        "avg_complexity": 5.0,
        "dead_code": 5.0,
        "style_issues": 10,
        "style_violations": 2.5,
    }
    
    # Save metrics
    storage.save_metrics(metrics)
    
    # Get the latest entry
    latest = storage.get_latest()
    
    # Verify raw_data was parsed correctly
    assert isinstance(latest["raw_data"], dict)
    # Check that the metrics are in raw_data
    assert latest["raw_data"]["dead_code"] == 5.0
    assert latest["raw_data"]["style_issues"] == 10
    assert latest["raw_data"]["style_violations"] == 2.5
    # And also extracted to top level
    assert latest["dead_code"] == 5.0
    assert latest["style_issues"] == 10
    assert latest["style_violations"] == 2.5


def test_row_to_dict_invalid_json(storage):
    """Test _row_to_dict with invalid JSON in raw_data."""
    import sqlite3
    
    # Manually insert a record with invalid JSON
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute("""
            INSERT INTO metrics (avg_complexity, raw_data)
            VALUES (?, ?)
        """, (5.0, "invalid json {"))
        conn.commit()
    
    # Get the latest entry
    latest = storage.get_latest()
    
    # Should handle invalid JSON gracefully
    assert latest is not None
    assert latest["avg_complexity"] == 5.0
    assert latest["raw_data"] == {}  # Should default to empty dict


def test_get_latest_empty_db(storage):
    """Test get_latest with empty database."""
    # Don't save any metrics
    latest = storage.get_latest()
    assert latest is None


def test_get_previous_single_entry(storage):
    """Test get_previous with only one entry."""
    storage.save_metrics({"avg_complexity": 5.0})
    
    previous = storage.get_previous()
    assert previous is None  # No second entry exists
