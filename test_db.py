"""Regression tests for db.py — covers the two fixed bugs.

Run: python3 -m pytest test_db.py -v   (or: python3 test_db.py)
"""

import tempfile
from pathlib import Path

import pytest

import memory.db as db


@pytest.fixture
def conn():
    with tempfile.TemporaryDirectory() as d:
        c = db.init_db(Path(d) / "test.db")
        yield c
        c.close()


def test_insert_pattern_writes_to_patterns_table(conn):
    """Regression: insert_pattern used to INSERT INTO decisions (wrong table)."""
    pid = db.insert_pattern(conn, {
        "session_id": "s1",
        "pattern_type": "retry",
        "description": "exponential backoff",
        "code_example": "for i in range(3): ...",
        "related_files": ["a.py"],
    })
    assert pid is not None

    rows = conn.execute("SELECT pattern_type, description FROM patterns").fetchall()
    assert len(rows) == 1
    assert rows[0]["pattern_type"] == "retry"

    # And it did NOT leak into decisions
    assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0

    # get_stats should count it
    assert db.get_stats(conn)["patterns"] == 1


def test_get_entity_graph_missing_entity_returns_empty(conn):
    """Regression: used to crash (dict(None)) on a non-existent entity."""
    assert db.get_entity_graph(conn, "does-not-exist") == {}


def test_get_entity_graph_existing_entity(conn):
    db.insert_entity(conn, "Stella", "tech", "memory topology")
    db.insert_entity(conn, "Cartesia", "tech", "tts")
    conn.execute(
        "INSERT INTO entity_links (entity_a, entity_b, strength) VALUES (?, ?, ?)",
        ("Stella", "Cartesia", 0.8),
    )
    conn.commit()

    graph = db.get_entity_graph(conn, "Stella")
    assert graph["entity"]["name"] == "Stella"
    assert any(n["name"] == "Cartesia" for n in graph["neighbors"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
