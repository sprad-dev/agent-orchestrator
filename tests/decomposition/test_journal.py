"""Tests for DecompositionJournal."""

import json
from pathlib import Path

import pytest

from src.decomposition.dag import TaskNode, TaskDAG, TaskStatus
from src.decomposition.journal import DecompositionJournal, JournalEntry


class TestJournalEntry:
    """Tests for JournalEntry dataclass."""

    def test_create_entry(self):
        entry = JournalEntry(
            timestamp="2026-02-08T12:00:00.000000",
            task_description="Test task",
            subtask_count=3,
            file_ownership_map={"src/foo.py": ["task1", "task2"]},
            outcome="success",
            notes="All good",
        )
        assert entry.timestamp == "2026-02-08T12:00:00.000000"
        assert entry.task_description == "Test task"
        assert entry.subtask_count == 3
        assert entry.outcome == "success"
        assert entry.notes == "All good"

    def test_entry_to_dict(self):
        entry = JournalEntry(
            timestamp="2026-02-08T12:00:00.000000",
            task_description="Test task",
            subtask_count=2,
            file_ownership_map={"a.py": ["t1"]},
            outcome="success",
        )
        d = entry.to_dict()
        assert d["timestamp"] == "2026-02-08T12:00:00.000000"
        assert d["task_description"] == "Test task"
        assert d["subtask_count"] == 2
        assert d["outcome"] == "success"
        assert d["notes"] == ""


class TestDecompositionJournal:
    """Tests for DecompositionJournal."""

    def test_init_creates_parent_dir(self, tmp_path):
        """Test that journal initialization creates parent directories."""
        journal_path = tmp_path / "subdir" / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))
        assert journal.path == journal_path
        assert journal.path.parent.exists()

    def test_record_creates_file(self, tmp_path):
        """Test recording a single entry."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Task 1"))

        journal.record(dag, outcome="success", notes="Good decomposition")

        assert journal_path.exists()
        with open(journal_path, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["outcome"] == "success"
        assert data["notes"] == "Good decomposition"
        assert data["subtask_count"] == 1

    def test_record_multiple_entries(self, tmp_path):
        """Test recording multiple entries appends correctly."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag1 = TaskDAG()
        dag1.add_node(TaskNode(id="t1", description="Task 1"))
        journal.record(dag1, outcome="success")

        dag2 = TaskDAG()
        dag2.add_node(TaskNode(id="t1", description="Task 1"))
        dag2.add_node(TaskNode(id="t2", description="Task 2"))
        journal.record(dag2, outcome="collision", notes="File conflict")

        with open(journal_path, "r") as f:
            lines = f.readlines()
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        assert entry1["subtask_count"] == 1
        assert entry2["subtask_count"] == 2
        assert entry2["outcome"] == "collision"

    def test_successful_patterns(self, tmp_path):
        """Test filtering successful decompositions."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Task 1"))

        journal.record(dag, outcome="success")
        journal.record(dag, outcome="failed")
        journal.record(dag, outcome="success")

        successful = journal.successful_patterns()
        assert len(successful) == 2
        assert all(e.outcome == "success" for e in successful)

    def test_collision_history(self, tmp_path):
        """Test filtering collision entries."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Task 1"))

        journal.record(dag, outcome="success")
        journal.record(dag, outcome="collision")
        journal.record(dag, outcome="merge_conflict")
        journal.record(dag, outcome="failed")

        collisions = journal.collision_history()
        assert len(collisions) == 2
        assert all(
            e.outcome in ("collision", "merge_conflict")
            for e in collisions
        )

    def test_suggest_split_with_collisions(self, tmp_path):
        """Test suggest_split identifies files in past collisions."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        # Record a collision: file owned by two nodes
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Task 1",
                file_ownership=["src/shared.py"],
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="Task 2",
                file_ownership=["src/shared.py"],
            )
        )
        journal.record(dag, outcome="collision", notes="Shared file")

        # Now suggest split for files that include the problematic file
        suggestions = journal.suggest_split(
            ["src/shared.py", "src/other.py"]
        )
        assert "src/shared.py" in suggestions
        assert "src/other.py" not in suggestions

    def test_suggest_split_no_collisions(self, tmp_path):
        """Test suggest_split with no collision history."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        # No entries recorded
        suggestions = journal.suggest_split(["src/foo.py", "src/bar.py"])
        assert suggestions == []

    def test_suggest_split_empty_input(self, tmp_path):
        """Test suggest_split with empty file list."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag = TaskDAG()
        dag.add_node(
            TaskNode(id="t1", description="Task 1", file_ownership=["a.py"])
        )
        dag.add_node(
            TaskNode(id="t2", description="Task 2", file_ownership=["a.py"])
        )
        journal.record(dag, outcome="collision")

        suggestions = journal.suggest_split([])
        assert suggestions == []

    def test_empty_journal(self, tmp_path):
        """Test querying empty journal returns empty lists."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        assert journal.successful_patterns() == []
        assert journal.collision_history() == []
        assert journal.suggest_split(["a.py"]) == []

    def test_round_trip_with_file_ownership(self, tmp_path):
        """Test recording and retrieving entry with file ownership."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Module A",
                file_ownership=["src/module_a.py"],
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="Module B",
                file_ownership=["src/module_b.py"],
            )
        )

        journal.record(dag, outcome="success", notes="Clean separation")

        entries = journal.successful_patterns()
        assert len(entries) == 1

        entry = entries[0]
        assert entry.outcome == "success"
        assert entry.notes == "Clean separation"
        assert entry.subtask_count == 2
        assert "src/module_a.py" in entry.file_ownership_map
        assert entry.file_ownership_map["src/module_a.py"] == ["t1"]

    def test_collision_detection_multiple_owners(self, tmp_path):
        """Test that collisions are properly detected when file has multiple owners."""
        journal_path = tmp_path / "journal.jsonl"
        journal = DecompositionJournal(str(journal_path))

        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Task 1",
                file_ownership=["src/shared.py", "src/unique1.py"],
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="Task 2",
                file_ownership=["src/shared.py", "src/unique2.py"],
            )
        )

        journal.record(dag, outcome="collision")

        collisions = journal.collision_history()
        assert len(collisions) == 1
        assert collisions[0].file_ownership_map["src/shared.py"] == ["t1", "t2"]
        assert collisions[0].file_ownership_map["src/unique1.py"] == ["t1"]

        # suggest_split should identify the shared file
        suggestions = journal.suggest_split(
            ["src/shared.py", "src/unique1.py"]
        )
        assert "src/shared.py" in suggestions
