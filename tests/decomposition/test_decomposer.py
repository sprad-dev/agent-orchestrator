"""Tests for TaskDecomposer integration layer."""

import pytest

from src.decomposition.decomposer import (
    TaskDecomposer,
    SubtaskSpec,
    DecompositionResult,
)
from src.decomposition.dag import TaskStatus


class TestSubtaskSpec:
    """Tests for SubtaskSpec dataclass."""

    def test_minimal_spec(self):
        spec = SubtaskSpec(id="t1", description="Do thing")
        assert spec.id == "t1"
        assert spec.file_ownership == []
        assert spec.test_command is None

    def test_full_spec(self):
        spec = SubtaskSpec(
            id="t1",
            description="Refactor",
            file_ownership=["src/a.py"],
            inputs=["config.yaml"],
            outputs=["src/a.py"],
            dependencies=["t0"],
            test_command="pytest tests/test_a.py",
        )
        assert spec.dependencies == ["t0"]


class TestTaskDecomposer:
    """Tests for the TaskDecomposer integration class."""

    def test_decompose_valid_parallel(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        result = decomposer.decompose([
            SubtaskSpec(
                id="api",
                description="API layer",
                file_ownership=["src/api.py"],
                inputs=["spec.yaml"],
                outputs=["src/api.py"],
                test_command="pytest tests/test_api.py",
            ),
            SubtaskSpec(
                id="db",
                description="DB layer",
                file_ownership=["src/db.py"],
                inputs=["schema.sql"],
                outputs=["src/db.py"],
                test_command="pytest tests/test_db.py",
            ),
        ])
        assert isinstance(result, DecompositionResult)
        assert result.is_parallel_safe is True
        assert result.file_conflicts == {}
        assert len(result.execution_order) == 2

    def test_decompose_with_dependency(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        result = decomposer.decompose([
            SubtaskSpec(
                id="base",
                description="Base module",
                file_ownership=["src/base.py"],
                inputs=["spec.yaml"],
                outputs=["src/base.py"],
                test_command="pytest tests/test_base.py",
            ),
            SubtaskSpec(
                id="ext",
                description="Extension",
                file_ownership=["src/ext.py"],
                inputs=["src/base.py"],
                outputs=["src/ext.py"],
                dependencies=["base"],
                test_command="pytest tests/test_ext.py",
            ),
        ])
        assert result.is_parallel_safe is True
        order_ids = [n.id for n in result.execution_order]
        assert order_ids.index("base") < order_ids.index("ext")

    def test_decompose_file_conflict(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        result = decomposer.decompose([
            SubtaskSpec(
                id="t1",
                description="Task 1",
                file_ownership=["src/shared.py"],
                inputs=["x"],
                outputs=["src/shared.py"],
                test_command="pytest",
            ),
            SubtaskSpec(
                id="t2",
                description="Task 2",
                file_ownership=["src/shared.py"],
                inputs=["y"],
                outputs=["src/shared.py"],
                test_command="pytest",
            ),
        ])
        assert result.is_parallel_safe is False
        assert "src/shared.py" in result.file_conflicts

    def test_decompose_cycle_raises(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        with pytest.raises(ValueError, match="Invalid DAG"):
            decomposer.decompose([
                SubtaskSpec(id="a", description="A", dependencies=["b"]),
                SubtaskSpec(id="b", description="B", dependencies=["a"]),
            ])

    def test_decompose_dangling_dep_raises(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        with pytest.raises(ValueError, match="Invalid DAG"):
            decomposer.decompose([
                SubtaskSpec(id="t1", description="T1", dependencies=["ghost"]),
            ])

    def test_record_outcome(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        result = decomposer.decompose([
            SubtaskSpec(
                id="t1",
                description="Solo task",
                inputs=["x"],
                outputs=["y"],
                test_command="pytest",
            ),
        ])
        decomposer.record_outcome(result.dag, "success", "Clean run")

        entries = decomposer.journal.successful_patterns()
        assert len(entries) == 1
        assert entries[0].outcome == "success"

    def test_suggest_split_from_history(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))

        # Record a collision
        result = decomposer.decompose([
            SubtaskSpec(
                id="t1",
                description="T1",
                file_ownership=["src/conflict.py"],
                inputs=["x"],
                outputs=["y"],
                test_command="pytest",
            ),
            SubtaskSpec(
                id="t2",
                description="T2",
                file_ownership=["src/conflict.py"],
                inputs=["x"],
                outputs=["z"],
                test_command="pytest",
            ),
        ])
        decomposer.record_outcome(result.dag, "collision", "File conflict")

        # Now query suggestions
        suggestions = decomposer.suggest_split(["src/conflict.py", "src/safe.py"])
        assert "src/conflict.py" in suggestions

    def test_validator_and_journal_accessible(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        assert decomposer.validator is not None
        assert decomposer.journal is not None

    def test_empty_decomposition(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        result = decomposer.decompose([])
        assert result.is_parallel_safe is True
        assert result.execution_order == []

    def test_diamond_dag(self, tmp_path):
        decomposer = TaskDecomposer(journal_path=str(tmp_path / "j.jsonl"))
        result = decomposer.decompose([
            SubtaskSpec(
                id="root",
                description="Root",
                file_ownership=["src/root.py"],
                outputs=["src/root.py"],
                test_command="pytest tests/test_root.py",
            ),
            SubtaskSpec(
                id="left",
                description="Left branch",
                file_ownership=["src/left.py"],
                inputs=["src/root.py"],
                outputs=["src/left.py"],
                dependencies=["root"],
                test_command="pytest tests/test_left.py",
            ),
            SubtaskSpec(
                id="right",
                description="Right branch",
                file_ownership=["src/right.py"],
                inputs=["src/root.py"],
                outputs=["src/right.py"],
                dependencies=["root"],
                test_command="pytest tests/test_right.py",
            ),
            SubtaskSpec(
                id="join",
                description="Join",
                file_ownership=["src/join.py"],
                inputs=["src/left.py", "src/right.py"],
                outputs=["src/join.py"],
                dependencies=["left", "right"],
                test_command="pytest tests/test_join.py",
            ),
        ])
        assert result.is_parallel_safe is True
        order_ids = [n.id for n in result.execution_order]
        assert order_ids[0] == "root"
        assert order_ids[-1] == "join"
