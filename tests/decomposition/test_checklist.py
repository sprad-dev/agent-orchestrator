"""Tests for DecompositionValidator checklist rules."""

import pytest

from src.decomposition.dag import TaskNode, TaskDAG
from src.decomposition.checklist import (
    DecompositionValidator,
    ChecklistResult,
    RuleResult,
)


class TestRuleResult:
    """Tests for RuleResult dataclass."""

    def test_create_passed(self):
        result = RuleResult(passed=True)
        assert result.passed is True
        assert result.violations == []

    def test_create_failed(self):
        result = RuleResult(
            passed=False,
            violations=["violation 1", "violation 2"],
        )
        assert result.passed is False
        assert len(result.violations) == 2


class TestChecklistResult:
    """Tests for ChecklistResult dataclass."""

    def test_create_passed(self):
        result = ChecklistResult(
            passed=True,
            rule_results={
                "rule1": RuleResult(passed=True),
                "rule2": RuleResult(passed=True),
            },
        )
        assert result.passed is True
        assert result.summary == "All decomposition rules passed"

    def test_create_failed(self):
        result = ChecklistResult(
            passed=False,
            rule_results={
                "rule1": RuleResult(passed=True),
                "rule2": RuleResult(passed=False, violations=["some violation"]),
            },
        )
        assert result.passed is False
        assert "rule2" in result.summary

    def test_summary_multiple_failures(self):
        result = ChecklistResult(
            passed=False,
            rule_results={
                "file_ownership": RuleResult(passed=False),
                "testability": RuleResult(passed=False),
            },
        )
        assert "file_ownership" in result.summary
        assert "testability" in result.summary


class TestFileOwnershipRule:
    """Tests for single file ownership rule."""

    def test_no_conflicts(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", file_ownership=["src/a.py"]))
        dag.add_node(TaskNode(id="t2", description="B", file_ownership=["src/b.py"]))

        result = validator.check_file_ownership(dag)
        assert result.passed is True
        assert result.violations == []

    def test_conflict_single_file(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", file_ownership=["src/shared.py"]))
        dag.add_node(TaskNode(id="t2", description="B", file_ownership=["src/shared.py"]))

        result = validator.check_file_ownership(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "src/shared.py" in result.violations[0]
        assert "t1" in result.violations[0]
        assert "t2" in result.violations[0]

    def test_conflict_multiple_files(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="A",
                file_ownership=["src/shared1.py", "src/shared2.py"],
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="B",
                file_ownership=["src/shared1.py", "src/shared2.py"],
            )
        )

        result = validator.check_file_ownership(dag)
        assert result.passed is False
        assert len(result.violations) == 2

    def test_empty_dag(self):
        validator = DecompositionValidator()
        dag = TaskDAG()

        result = validator.check_file_ownership(dag)
        assert result.passed is True
        assert result.violations == []

    def test_single_node(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Solo", file_ownership=["src/a.py"]))

        result = validator.check_file_ownership(dag)
        assert result.passed is True
        assert result.violations == []

    def test_three_way_conflict(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", file_ownership=["src/shared.py"]))
        dag.add_node(TaskNode(id="t2", description="B", file_ownership=["src/shared.py"]))
        dag.add_node(TaskNode(id="t3", description="C", file_ownership=["src/shared.py"]))

        result = validator.check_file_ownership(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "t1" in result.violations[0]
        assert "t2" in result.violations[0]
        assert "t3" in result.violations[0]


class TestIODeclarationsRule:
    """Tests for clear inputs/outputs rule."""

    def test_has_input(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", inputs=["config.yaml"]))

        result = validator.check_io_declarations(dag)
        assert result.passed is True
        assert result.violations == []

    def test_has_output(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", outputs=["src/foo.py"]))

        result = validator.check_io_declarations(dag)
        assert result.passed is True
        assert result.violations == []

    def test_has_both_input_output(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="A",
                inputs=["old.py"],
                outputs=["new.py"],
            )
        )

        result = validator.check_io_declarations(dag)
        assert result.passed is True
        assert result.violations == []

    def test_no_input_or_output(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", inputs=[], outputs=[]))

        result = validator.check_io_declarations(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "t1" in result.violations[0]

    def test_multiple_nodes_some_missing(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", inputs=["config.yaml"]))
        dag.add_node(TaskNode(id="t2", description="B", inputs=[], outputs=[]))
        dag.add_node(TaskNode(id="t3", description="C", outputs=["result.txt"]))

        result = validator.check_io_declarations(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "t2" in result.violations[0]

    def test_empty_dag(self):
        validator = DecompositionValidator()
        dag = TaskDAG()

        result = validator.check_io_declarations(dag)
        assert result.passed is True
        assert result.violations == []

    def test_single_node_valid(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="Solo", inputs=["data.json"]))

        result = validator.check_io_declarations(dag)
        assert result.passed is True
        assert result.violations == []


class TestTestabilityRule:
    """Tests for testability in isolation rule."""

    def test_has_test_command(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="A",
                test_command="pytest tests/test_a.py",
            )
        )

        result = validator.check_testability(dag)
        assert result.passed is True
        assert result.violations == []

    def test_missing_test_command(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", test_command=None))

        result = validator.check_testability(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "t1" in result.violations[0]

    def test_empty_test_command(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", test_command=""))

        result = validator.check_testability(dag)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_whitespace_only_test_command(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", test_command="   "))

        result = validator.check_testability(dag)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_multiple_nodes_some_missing(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(id="t1", description="A", test_command="pytest tests/test_a.py")
        )
        dag.add_node(TaskNode(id="t2", description="B", test_command=None))
        dag.add_node(
            TaskNode(id="t3", description="C", test_command="pytest tests/test_c.py")
        )

        result = validator.check_testability(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "t2" in result.violations[0]

    def test_empty_dag(self):
        validator = DecompositionValidator()
        dag = TaskDAG()

        result = validator.check_testability(dag)
        assert result.passed is True
        assert result.violations == []

    def test_single_node_valid(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Solo",
                test_command="pytest tests/test_solo.py",
            )
        )

        result = validator.check_testability(dag)
        assert result.passed is True
        assert result.violations == []


class TestSharedStateRule:
    """Tests for no shared mutable state rule."""

    def test_no_shared_state(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", outputs=["a.txt"]))
        dag.add_node(TaskNode(id="t2", description="B", inputs=["b.txt"]))

        result = validator.check_shared_state(dag)
        assert result.passed is True
        assert result.violations == []

    def test_shared_state_violation(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", outputs=["shared.txt"]))
        dag.add_node(TaskNode(id="t2", description="B", inputs=["shared.txt"]))

        result = validator.check_shared_state(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "t1" in result.violations[0]
        assert "t2" in result.violations[0]

    def test_dependency_allows_sharing(self):
        """If t2 depends on t1, sharing is expected and allowed."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="t1", description="A", outputs=["shared.txt"]))
        dag.add_node(
            TaskNode(id="t2", description="B", inputs=["shared.txt"], dependencies=["t1"])
        )

        result = validator.check_shared_state(dag)
        assert result.passed is True
        assert result.violations == []

    def test_multiple_outputs_one_conflict(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(id="t1", description="A", outputs=["a.txt", "conflict.txt"])
        )
        dag.add_node(
            TaskNode(id="t2", description="B", inputs=["conflict.txt", "b.txt"])
        )

        result = validator.check_shared_state(dag)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "conflict.txt" in result.violations[0]

    def test_multiple_conflicts(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(id="t1", description="A", outputs=["a.txt", "shared1.txt"])
        )
        dag.add_node(
            TaskNode(id="t2", description="B", inputs=["shared1.txt", "shared2.txt"])
        )
        dag.add_node(TaskNode(id="t3", description="C", outputs=["shared2.txt"]))

        result = validator.check_shared_state(dag)
        assert result.passed is False
        # t1->t2 conflict and t3->t2 conflict
        assert len(result.violations) == 2

    def test_diamond_dependency_allowed(self):
        """Diamond: root -> left/right -> join. Shared inputs from root are OK."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(TaskNode(id="root", description="Root", outputs=["config.txt"]))
        dag.add_node(
            TaskNode(
                id="left",
                description="Left",
                inputs=["config.txt"],
                dependencies=["root"],
            )
        )
        dag.add_node(
            TaskNode(
                id="right",
                description="Right",
                inputs=["config.txt"],
                dependencies=["root"],
            )
        )
        dag.add_node(
            TaskNode(
                id="join",
                description="Join",
                inputs=["left_out.txt", "right_out.txt"],
                dependencies=["left", "right"],
            )
        )

        result = validator.check_shared_state(dag)
        assert result.passed is True
        assert result.violations == []

    def test_empty_dag(self):
        validator = DecompositionValidator()
        dag = TaskDAG()

        result = validator.check_shared_state(dag)
        assert result.passed is True
        assert result.violations == []

    def test_single_node(self):
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(id="t1", description="Solo", inputs=["i.txt"], outputs=["o.txt"])
        )

        result = validator.check_shared_state(dag)
        assert result.passed is True
        assert result.violations == []

    def test_self_output_input_allowed(self):
        """A task's own input/output overlap is allowed."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Transform",
                inputs=["data.txt"],
                outputs=["data.txt"],
            )
        )

        result = validator.check_shared_state(dag)
        assert result.passed is True
        assert result.violations == []


class TestDecompositionValidator:
    """Integration tests for full validation."""

    def test_all_rules_pass(self):
        """All decomposition rules pass."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Refactor",
                file_ownership=["src/a.py"],
                inputs=["config.yaml"],
                outputs=["src/a.py"],
                test_command="pytest tests/test_a.py",
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="Test",
                file_ownership=["tests/test_b.py"],
                inputs=["src/a.py"],
                outputs=["coverage.xml"],
                dependencies=["t1"],
                test_command="pytest tests/test_b.py",
            )
        )

        result = validator.validate(dag)
        assert result.passed is True
        assert all(r.passed for r in result.rule_results.values())

    def test_all_rules_fail(self):
        """All rules detect violations."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        # Missing test_command, shared file ownership, no I/O
        dag.add_node(
            TaskNode(
                id="t1",
                description="Bad",
                file_ownership=["src/shared.py"],
                inputs=[],
                outputs=[],
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="Also bad",
                file_ownership=["src/shared.py"],
                inputs=[],
                outputs=[],
            )
        )

        result = validator.validate(dag)
        assert result.passed is False
        assert result.rule_results["file_ownership"].passed is False
        assert result.rule_results["io_declarations"].passed is False
        assert result.rule_results["testability"].passed is False

    def test_some_rules_pass_some_fail(self):
        """Mixed: some rules pass, some fail."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="A",
                file_ownership=["src/a.py"],
                inputs=["config.yaml"],
                outputs=["src/a.py"],
                test_command="pytest tests/test_a.py",
            )
        )
        dag.add_node(
            TaskNode(
                id="t2",
                description="B (bad)",
                file_ownership=["src/a.py"],  # Conflict with t1
                inputs=["config.yaml"],
                outputs=["result.txt"],
                test_command="pytest tests/test_b.py",
            )
        )

        result = validator.validate(dag)
        assert result.passed is False
        assert result.rule_results["file_ownership"].passed is False
        assert result.rule_results["io_declarations"].passed is True
        assert result.rule_results["testability"].passed is True

    def test_empty_dag_validation(self):
        """Empty DAG passes all rules."""
        validator = DecompositionValidator()
        dag = TaskDAG()

        result = validator.validate(dag)
        assert result.passed is True
        assert all(r.passed for r in result.rule_results.values())

    def test_single_node_validation(self):
        """Single valid node passes all rules."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Solo",
                file_ownership=["src/solo.py"],
                inputs=["input.txt"],
                outputs=["output.txt"],
                test_command="pytest tests/test_solo.py",
            )
        )

        result = validator.validate(dag)
        assert result.passed is True
        assert all(r.passed for r in result.rule_results.values())

    def test_single_node_invalid(self):
        """Single invalid node fails appropriately."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Bad",
                file_ownership=["src/bad.py"],
                inputs=[],
                outputs=[],
                test_command=None,
            )
        )

        result = validator.validate(dag)
        assert result.passed is False
        assert result.rule_results["io_declarations"].passed is False
        assert result.rule_results["testability"].passed is False

    def test_complex_dag_valid(self):
        """Complex DAG with multiple valid nodes."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        # Root task
        dag.add_node(
            TaskNode(
                id="analyze",
                description="Analyze",
                file_ownership=["src/analyze.py"],
                inputs=["data.csv"],
                outputs=["analysis.json"],
                test_command="pytest tests/test_analyze.py",
            )
        )
        # Two parallel tasks
        dag.add_node(
            TaskNode(
                id="process_a",
                description="Process A",
                file_ownership=["src/process_a.py"],
                inputs=["analysis.json"],
                outputs=["result_a.json"],
                dependencies=["analyze"],
                test_command="pytest tests/test_process_a.py",
            )
        )
        dag.add_node(
            TaskNode(
                id="process_b",
                description="Process B",
                file_ownership=["src/process_b.py"],
                inputs=["analysis.json"],
                outputs=["result_b.json"],
                dependencies=["analyze"],
                test_command="pytest tests/test_process_b.py",
            )
        )
        # Join task
        dag.add_node(
            TaskNode(
                id="combine",
                description="Combine",
                file_ownership=["src/combine.py"],
                inputs=["result_a.json", "result_b.json"],
                outputs=["final.json"],
                dependencies=["process_a", "process_b"],
                test_command="pytest tests/test_combine.py",
            )
        )

        result = validator.validate(dag)
        assert result.passed is True
        assert all(r.passed for r in result.rule_results.values())

    def test_rule_results_structure(self):
        """Validate ChecklistResult structure."""
        validator = DecompositionValidator()
        dag = TaskDAG()
        dag.add_node(
            TaskNode(
                id="t1",
                description="Test",
                file_ownership=["src/t1.py"],
                inputs=["in.txt"],
                outputs=["out.txt"],
                test_command="pytest tests/t1.py",
            )
        )

        result = validator.validate(dag)
        assert isinstance(result, ChecklistResult)
        assert isinstance(result.rule_results, dict)
        assert set(result.rule_results.keys()) == {
            "file_ownership",
            "io_declarations",
            "testability",
            "shared_state",
        }
        for rule_name, rule_result in result.rule_results.items():
            assert isinstance(rule_result, RuleResult)
            assert isinstance(rule_result.passed, bool)
            assert isinstance(rule_result.violations, list)
