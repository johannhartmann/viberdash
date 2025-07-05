"""SQLite-based storage for ViberDash metrics history."""

import json
import sqlite3
from pathlib import Path
from typing import Any


class MetricsStorage:
    """Handles persistence of code metrics in SQLite database."""

    def __init__(self, db_path: Path | None = None):
        """Initialize storage with database path."""
        if db_path is None:
            db_path = Path.cwd() / "viberdash.db"
        self.db_path = db_path
        self.init_db()

    def init_db(self) -> None:
        """Create database and tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    avg_complexity REAL,
                    maintainability_index REAL,
                    test_coverage REAL,
                    code_duplication REAL,
                    total_functions INTEGER,
                    total_classes INTEGER,
                    total_lines INTEGER,
                    raw_data TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON metrics(timestamp DESC)
            """
            )
            conn.commit()

    def save_metrics(self, metrics: dict[str, Any]) -> int:
        """Save metrics to database.

        Args:
            metrics: Dictionary containing metric values

        Returns:
            ID of inserted record

        """
        # Extract main metrics
        record = {
            "avg_complexity": metrics.get("avg_complexity", 0.0),
            "maintainability_index": metrics.get("maintainability_index", 0.0),
            "test_coverage": metrics.get("test_coverage", 0.0),
            "code_duplication": metrics.get("code_duplication", 0.0),
            "total_functions": metrics.get("total_functions", 0),
            "total_classes": metrics.get("total_classes", 0),
            "total_lines": metrics.get("total_lines", 0),
            "raw_data": json.dumps(metrics),  # Store complete data as JSON
        }

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO metrics (
                    avg_complexity, maintainability_index, test_coverage,
                    code_duplication, total_functions, total_classes,
                    total_lines, raw_data
                ) VALUES (
                    :avg_complexity, :maintainability_index, :test_coverage,
                    :code_duplication, :total_functions, :total_classes,
                    :total_lines, :raw_data
                )
            """,
                record,
            )
            conn.commit()
            lastrowid = cursor.lastrowid
            return lastrowid if lastrowid is not None else 0

    def get_latest(self) -> dict[str, Any] | None:
        """Get the most recent metrics entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM metrics
                ORDER BY timestamp DESC
                LIMIT 1
            """
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get historical metrics entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of metric dictionaries, newest first

        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM metrics
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_previous(self) -> dict[str, Any] | None:
        """Get the second most recent metrics entry (for delta calculation)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM metrics
                ORDER BY timestamp DESC
                LIMIT 1 OFFSET 1
            """
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert database row to dictionary."""
        result = dict(row)
        # Parse raw_data JSON if present
        if result.get("raw_data"):
            try:
                raw_data = json.loads(result["raw_data"])
                result["raw_data"] = raw_data
                # Extract dead_code from raw_data if present
                if "dead_code" in raw_data:
                    result["dead_code"] = raw_data["dead_code"]
                # Extract style metrics from raw_data if present
                if "style_issues" in raw_data:
                    result["style_issues"] = raw_data["style_issues"]
                if "style_violations" in raw_data:
                    result["style_violations"] = raw_data["style_violations"]
                # Extract documentation metrics from raw_data if present
                if "doc_issues" in raw_data:
                    result["doc_issues"] = raw_data["doc_issues"]
                if "doc_coverage" in raw_data:
                    result["doc_coverage"] = raw_data["doc_coverage"]
            except json.JSONDecodeError:
                result["raw_data"] = {}
        return result

    def cleanup_old_entries(self, keep_days: int = 30) -> int:
        """Remove entries older than specified days.

        Args:
            keep_days: Number of days of history to keep

        Returns:
            Number of deleted entries

        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM metrics
                WHERE timestamp < datetime('now', ? || ' days')
            """,
                (-keep_days,),
            )
            conn.commit()
            return cursor.rowcount
