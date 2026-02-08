"""Task decomposition module for Tier 1: splitting work into parallel-safe units.

Provides data models for representing tasks as a DAG of independent work units,
validation that subtasks follow decomposition rules, and a journal for tracking
decomposition patterns and outcomes.
"""

from .dag import TaskNode, TaskDAG, TaskStatus
from .checklist import DecompositionValidator, ChecklistResult, RuleResult
from .journal import DecompositionJournal, JournalEntry
from .decomposer import TaskDecomposer, SubtaskSpec, DecompositionResult

__all__ = [
    "TaskNode",
    "TaskDAG",
    "TaskStatus",
    "DecompositionValidator",
    "ChecklistResult",
    "RuleResult",
    "DecompositionJournal",
    "JournalEntry",
    "TaskDecomposer",
    "SubtaskSpec",
    "DecompositionResult",
]
