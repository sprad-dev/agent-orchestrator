"""Decomposition validation checklist for TaskDAG.

Validates that a TaskDAG follows decomposition rules for parallel-safe task
splitting:
- Single file ownership: no two tasks touch the same file
- Clear inputs/outputs: every task declares at least one input or output
- Testable in isolation: each task has a non-empty test_command
- No shared mutable state: outputs don't overlap with inputs (outside deps)
"""

from dataclasses import dataclass, field
from typing import Dict, List

from .dag import TaskDAG, TaskNode


@dataclass
class RuleResult:
    """Result of validating a single decomposition rule."""
    passed: bool
    violations: List[str] = field(default_factory=list)


@dataclass
class ChecklistResult:
    """Result of validating a TaskDAG against all decomposition rules."""
    passed: bool
    rule_results: Dict[str, RuleResult] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Human-readable summary of validation results."""
        if self.passed:
            return "All decomposition rules passed"
        failed = [r for r, res in self.rule_results.items() if not res.passed]
        return f"Failed rules: {', '.join(failed)}"


class DecompositionValidator:
    """Validates TaskDAG decomposition for parallel-safe task splitting."""

    def validate(self, dag: TaskDAG) -> ChecklistResult:
        """Run all decomposition rules on the DAG.

        Args:
            dag: TaskDAG to validate

        Returns:
            ChecklistResult with pass/fail status and per-rule details
        """
        rule_results = {}

        # Run all checks
        rule_results["file_ownership"] = self.check_file_ownership(dag)
        rule_results["io_declarations"] = self.check_io_declarations(dag)
        rule_results["testability"] = self.check_testability(dag)
        rule_results["shared_state"] = self.check_shared_state(dag)

        # Overall pass if all rules passed
        passed = all(r.passed for r in rule_results.values())

        return ChecklistResult(passed=passed, rule_results=rule_results)

    def check_file_ownership(self, dag: TaskDAG) -> RuleResult:
        """Validate single file ownership: no two tasks touch the same file.

        Args:
            dag: TaskDAG to validate

        Returns:
            RuleResult with violations if any file is owned by multiple tasks
        """
        conflicts = dag.file_conflicts()
        violations = []

        for file_pat, node_ids in conflicts.items():
            violations.append(
                f"File '{file_pat}' owned by multiple tasks: {', '.join(node_ids)}"
            )

        return RuleResult(passed=len(violations) == 0, violations=violations)

    def check_io_declarations(self, dag: TaskDAG) -> RuleResult:
        """Validate clear inputs/outputs: every task has at least one I/O.

        Args:
            dag: TaskDAG to validate

        Returns:
            RuleResult with violations if any task lacks both inputs and outputs
        """
        violations = []

        for node in dag.nodes:
            has_input = len(node.inputs) > 0
            has_output = len(node.outputs) > 0

            if not (has_input or has_output):
                violations.append(
                    f"Task '{node.id}' has neither inputs nor outputs declared"
                )

        return RuleResult(passed=len(violations) == 0, violations=violations)

    def check_testability(self, dag: TaskDAG) -> RuleResult:
        """Validate testable in isolation: each task has a test_command.

        Args:
            dag: TaskDAG to validate

        Returns:
            RuleResult with violations if any task lacks a test command
        """
        violations = []

        for node in dag.nodes:
            if not node.test_command or not node.test_command.strip():
                violations.append(
                    f"Task '{node.id}' has no test_command defined"
                )

        return RuleResult(passed=len(violations) == 0, violations=violations)

    def check_shared_state(self, dag: TaskDAG) -> RuleResult:
        """Validate no shared mutable state.

        Detects when one task's outputs overlap with another task's inputs,
        excluding expected sharing in dependency relationships.

        Args:
            dag: TaskDAG to validate

        Returns:
            RuleResult with violations if outputs overlap with non-dependent inputs
        """
        violations = []
        nodes_by_id = {node.id: node for node in dag.nodes}

        for node_a in dag.nodes:
            # Check node_a's outputs against other nodes' inputs
            for node_b in dag.nodes:
                if node_a.id == node_b.id:
                    continue

                # If node_b depends on node_a, sharing is expected
                if node_a.id in node_b.dependencies:
                    continue

                # Check for overlapping outputs/inputs
                a_outputs_set = set(node_a.outputs)
                b_inputs_set = set(node_b.inputs)
                overlap = a_outputs_set & b_inputs_set

                if overlap:
                    violations.append(
                        f"Task '{node_a.id}' outputs {overlap} which are inputs "
                        f"to unrelated task '{node_b.id}' (no dependency exists)"
                    )

        return RuleResult(passed=len(violations) == 0, violations=violations)
