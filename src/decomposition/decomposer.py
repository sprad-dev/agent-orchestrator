"""TaskDecomposer — integration point between decomposition and execution.

Takes a task description and a list of subtask definitions, builds a validated
DAG, and records outcomes to the journal. This is the bridge between Tier 1
(decomposition skill) and Tier 2 (parallel execution).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .dag import TaskDAG, TaskNode, TaskStatus
from .checklist import DecompositionValidator, ChecklistResult
from .journal import DecompositionJournal


DEFAULT_JOURNAL_PATH = ".decomposition/journal.jsonl"


@dataclass
class SubtaskSpec:
    """Specification for a single subtask in a decomposition."""
    id: str
    description: str
    file_ownership: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    test_command: Optional[str] = None


@dataclass
class DecompositionResult:
    """Result of decomposing and validating a task."""
    dag: TaskDAG
    validation: ChecklistResult
    is_parallel_safe: bool
    file_conflicts: Dict[str, List[str]]
    execution_order: List[TaskNode]


class TaskDecomposer:
    """Decomposes tasks into validated DAGs of parallel-safe subtasks.

    Sits upstream of execution models. Given a set of subtask specs,
    builds a DAG, validates it against decomposition rules, and records
    outcomes to a journal for pattern learning.
    """

    def __init__(self, journal_path: Optional[str] = None):
        """Initialize decomposer with optional journal path.

        Args:
            journal_path: Path for JSONL journal. Defaults to .decomposition/journal.jsonl
        """
        self._validator = DecompositionValidator()
        self._journal = DecompositionJournal(journal_path or DEFAULT_JOURNAL_PATH)

    def decompose(self, subtasks: List[SubtaskSpec]) -> DecompositionResult:
        """Build and validate a DAG from subtask specifications.

        Args:
            subtasks: List of subtask specs defining the decomposition.

        Returns:
            DecompositionResult with DAG, validation, and execution order.

        Raises:
            ValueError: If DAG structure is invalid (cycles, dangling deps).
        """
        dag = TaskDAG()
        for spec in subtasks:
            dag.add_node(TaskNode(
                id=spec.id,
                description=spec.description,
                file_ownership=spec.file_ownership,
                inputs=spec.inputs,
                outputs=spec.outputs,
                dependencies=spec.dependencies,
                test_command=spec.test_command,
            ))

        # Validate DAG structure
        dag_validation = dag.validate()
        if not dag_validation.valid:
            raise ValueError(
                f"Invalid DAG structure: {'; '.join(dag_validation.errors)}"
            )

        # Validate decomposition rules
        checklist = self._validator.validate(dag)

        # Get execution order
        execution_order = dag.topological_sort()

        return DecompositionResult(
            dag=dag,
            validation=checklist,
            is_parallel_safe=checklist.passed,
            file_conflicts=dag.file_conflicts(),
            execution_order=execution_order,
        )

    def record_outcome(self, dag: TaskDAG, outcome: str, notes: str = "") -> None:
        """Record decomposition outcome to journal.

        Args:
            dag: The TaskDAG that was executed.
            outcome: One of "success", "collision", "merge_conflict", "failed".
            notes: Optional notes about the outcome.
        """
        self._journal.record(dag, outcome=outcome, notes=notes)

    def suggest_split(self, file_list: List[str]) -> List[str]:
        """Suggest files that should NOT be in the same subtask.

        Based on historical collision data from the journal.

        Args:
            file_list: Files being considered for a decomposition.

        Returns:
            Files that have caused collisions in past decompositions.
        """
        return self._journal.suggest_split(file_list)

    @property
    def validator(self) -> DecompositionValidator:
        """Access the underlying validator for direct rule checks."""
        return self._validator

    @property
    def journal(self) -> DecompositionJournal:
        """Access the underlying journal for queries."""
        return self._journal
