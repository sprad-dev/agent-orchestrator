"""Tests for TaskDAG data model."""

import pytest

from src.decomposition.dag import TaskNode, TaskDAG, TaskStatus, DAGValidationResult


class TestTaskNode:
    """Tests for TaskNode dataclass."""

    def test_create_minimal_node(self):
        node = TaskNode(id="t1", description="Do something")
        assert node.id == "t1"
        assert node.status == TaskStatus.PENDING
        assert node.file_ownership == []
        assert node.dependencies == []

    def test_create_full_node(self):
        node = TaskNode(
            id="t1",
            description="Refactor module",
            file_ownership=["src/foo.py"],
            inputs=["config.yaml"],
            outputs=["src/foo.py"],
            dependencies=["t0"],
            test_command="pytest tests/test_foo.py",
        )
        assert node.file_ownership == ["src/foo.py"]
        assert node.test_command == "pytest tests/test_foo.py"

    def test_is_ready_no_deps(self):
        node = TaskNode(id="t1", description="Root task")
        assert node.is_ready(set()) is True

    def test_is_ready_deps_satisfied(self):
        node = TaskNode(id="t2", description="Child", dependencies=["t1"])
        assert node.is_ready({"t1"}) is True

    def test_is_ready_deps_not_satisfied(self):
        node = TaskNode(id="t2", description="Child", dependencies=["t1"])
        assert node.is_ready(set()) is False

    def test_is_ready_partial_deps(self):
        node = TaskNode(id="t3", description="Multi-dep", dependencies=["t1", "t2"])
        assert node.is_ready({"t1"}) is False
        assert node.is_ready({"t1", "t2"}) is True


class TestTaskDAG:
    """Tests for TaskDAG graph operations."""

    def _make_dag(self, *nodes):
        dag = TaskDAG()
        for n in nodes:
            dag.add_node(n)
        return dag

    def test_add_and_get_node(self):
        dag = TaskDAG()
        node = TaskNode(id="t1", description="Test")
        dag.add_node(node)
        assert dag.get_node("t1") is node

    def test_duplicate_node_raises(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="First"))
        with pytest.raises(ValueError, match="Duplicate node ID"):
            dag.add_node(TaskNode(id="t1", description="Second"))

    def test_get_missing_node_raises(self):
        dag = TaskDAG()
        with pytest.raises(KeyError):
            dag.get_node("missing")

    def test_node_ids(self):
        dag = self._make_dag(
            TaskNode(id="a", description="A"),
            TaskNode(id="b", description="B"),
        )
        assert dag.node_ids == {"a", "b"}

    def test_nodes_list(self):
        dag = self._make_dag(
            TaskNode(id="a", description="A"),
            TaskNode(id="b", description="B"),
        )
        assert len(dag.nodes) == 2


class TestDAGValidation:
    """Tests for DAG structural validation."""

    def test_valid_linear_dag(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Root"))
        dag.add_node(TaskNode(id="t2", description="Child", dependencies=["t1"]))
        result = dag.validate()
        assert result.valid is True
        assert result.errors == []

    def test_valid_diamond_dag(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="root", description="Root"))
        dag.add_node(TaskNode(id="left", description="Left", dependencies=["root"]))
        dag.add_node(TaskNode(id="right", description="Right", dependencies=["root"]))
        dag.add_node(TaskNode(id="join", description="Join", dependencies=["left", "right"]))
        result = dag.validate()
        assert result.valid is True

    def test_dangling_dependency(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Orphan dep", dependencies=["ghost"]))
        result = dag.validate()
        assert result.valid is False
        assert any("ghost" in e for e in result.errors)

    def test_cycle_detected(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="A", dependencies=["b"]))
        dag.add_node(TaskNode(id="b", description="B", dependencies=["a"]))
        result = dag.validate()
        assert result.valid is False
        assert any("Cycle" in e for e in result.errors)

    def test_self_cycle(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="A", dependencies=["a"]))
        result = dag.validate()
        assert result.valid is False
        assert any("Cycle" in e for e in result.errors)

    def test_no_root_nodes(self):
        """All nodes have deps but form a cycle - caught by cycle detection."""
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="A", dependencies=["b"]))
        dag.add_node(TaskNode(id="b", description="B", dependencies=["c"]))
        dag.add_node(TaskNode(id="c", description="C", dependencies=["a"]))
        result = dag.validate()
        assert result.valid is False

    def test_isolated_node_warning(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="connected", description="Connected"))
        dag.add_node(TaskNode(id="child", description="Child", dependencies=["connected"]))
        dag.add_node(TaskNode(id="island", description="Isolated"))
        result = dag.validate()
        assert result.valid is True
        assert any("island" in w for w in result.warnings)

    def test_empty_dag_valid(self):
        dag = TaskDAG()
        result = dag.validate()
        assert result.valid is True

    def test_single_node_valid(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="solo", description="Solo"))
        result = dag.validate()
        assert result.valid is True
        assert result.warnings == []


class TestTopologicalSort:
    """Tests for topological ordering."""

    def test_linear_chain(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="First"))
        dag.add_node(TaskNode(id="t2", description="Second", dependencies=["t1"]))
        dag.add_node(TaskNode(id="t3", description="Third", dependencies=["t2"]))
        order = dag.topological_sort()
        ids = [n.id for n in order]
        assert ids.index("t1") < ids.index("t2") < ids.index("t3")

    def test_diamond_ordering(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="root", description="Root"))
        dag.add_node(TaskNode(id="left", description="Left", dependencies=["root"]))
        dag.add_node(TaskNode(id="right", description="Right", dependencies=["root"]))
        dag.add_node(TaskNode(id="join", description="Join", dependencies=["left", "right"]))
        order = dag.topological_sort()
        ids = [n.id for n in order]
        assert ids[0] == "root"
        assert ids[-1] == "join"

    def test_cycle_raises(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="a", description="A", dependencies=["b"]))
        dag.add_node(TaskNode(id="b", description="B", dependencies=["a"]))
        with pytest.raises(ValueError, match="cycles"):
            dag.topological_sort()

    def test_empty_dag(self):
        dag = TaskDAG()
        assert dag.topological_sort() == []


class TestReadyTasks:
    """Tests for ready task queries."""

    def test_root_tasks_ready(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Root"))
        dag.add_node(TaskNode(id="t2", description="Child", dependencies=["t1"]))
        ready = dag.ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_child_ready_after_parent_complete(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Root", status=TaskStatus.COMPLETED))
        dag.add_node(TaskNode(id="t2", description="Child", dependencies=["t1"]))
        ready = dag.ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t2"

    def test_in_progress_not_ready(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="WIP", status=TaskStatus.IN_PROGRESS))
        ready = dag.ready_tasks()
        assert len(ready) == 0

    def test_parallel_tasks_both_ready(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="root", description="Root", status=TaskStatus.COMPLETED))
        dag.add_node(TaskNode(id="a", description="A", dependencies=["root"]))
        dag.add_node(TaskNode(id="b", description="B", dependencies=["root"]))
        ready = dag.ready_tasks()
        assert len(ready) == 2


class TestFileOwnership:
    """Tests for file ownership tracking."""

    def test_no_conflicts(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", file_ownership=["src/a.py"]))
        dag.add_node(TaskNode(id="t2", description="B", file_ownership=["src/b.py"]))
        assert dag.file_conflicts() == {}

    def test_conflict_detected(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", file_ownership=["src/shared.py"]))
        dag.add_node(TaskNode(id="t2", description="B", file_ownership=["src/shared.py"]))
        conflicts = dag.file_conflicts()
        assert "src/shared.py" in conflicts
        assert set(conflicts["src/shared.py"]) == {"t1", "t2"}

    def test_ownership_map(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", file_ownership=["src/a.py", "src/shared.py"]))
        dag.add_node(TaskNode(id="t2", description="B", file_ownership=["src/b.py", "src/shared.py"]))
        ownership = dag.file_ownership_map()
        assert ownership["src/a.py"] == ["t1"]
        assert set(ownership["src/shared.py"]) == {"t1", "t2"}
