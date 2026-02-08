"""DecompositionJournal for tracking decomposition attempts and outcomes.

Records decomposition attempts as structured JSONL logs, enabling pattern
detection and learning from past successes and failures.
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .dag import TaskDAG, TaskNode, TaskStatus


@dataclass
class JournalEntry:
    """A single decomposition journal entry.

    Records the outcome of a decomposition attempt, including the task
    description, subtask count, file ownership mapping, and outcome status.
    """
    timestamp: str  # ISO format
    task_description: str
    subtask_count: int
    file_ownership_map: Dict[str, List[str]]  # file -> [node_ids]
    outcome: str  # "success", "collision", "merge_conflict", "failed"
    notes: str = ""

    def to_dict(self) -> Dict:
        """Convert entry to dictionary for JSON serialization."""
        return asdict(self)


class DecompositionJournal:
    """Tracks decomposition attempts and learns from outcomes.

    Maintains a JSONL log of decomposition attempts with their outcomes,
    enabling pattern detection for future decompositions.
    """

    def __init__(self, path: str):
        """Initialize journal with file path.

        Args:
            path: File path for the JSONL log (created/appended to).
        """
        self.path = Path(path)
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        dag: TaskDAG,
        outcome: str,
        notes: str = "",
    ) -> None:
        """Record a decomposition attempt.

        Args:
            dag: The TaskDAG that was created.
            outcome: One of "success", "collision", "merge_conflict", "failed".
            notes: Optional additional notes about the outcome.
        """
        # Build task description from dag
        task_desc = (
            f"{len(dag.nodes)} nodes: "
            + ", ".join(n.description[:30] for n in dag.nodes[:3])
        )
        if len(dag.nodes) > 3:
            task_desc += f", ... ({len(dag.nodes)} total)"

        entry = JournalEntry(
            timestamp=datetime.utcnow().isoformat(),
            task_description=task_desc,
            subtask_count=len(dag.nodes),
            file_ownership_map=dag.file_ownership_map(),
            outcome=outcome,
            notes=notes,
        )

        # Append as JSON line
        with open(self.path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def _load_entries(self) -> List[JournalEntry]:
        """Load all entries from journal file.

        Returns:
            List of JournalEntry objects, or empty list if file doesn't exist.
        """
        if not self.path.exists():
            return []

        entries = []
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    entries.append(JournalEntry(**data))
        return entries

    def successful_patterns(self) -> List[JournalEntry]:
        """Get all successful decomposition attempts.

        Returns:
            List of entries where outcome == "success".
        """
        entries = self._load_entries()
        return [e for e in entries if e.outcome == "success"]

    def collision_history(self) -> List[JournalEntry]:
        """Get decompositions with file collisions or merge conflicts.

        Returns:
            List of entries where outcome is "collision" or "merge_conflict".
        """
        entries = self._load_entries()
        return [
            e for e in entries
            if e.outcome in ("collision", "merge_conflict")
        ]

    def suggest_split(self, file_list: List[str]) -> List[str]:
        """Suggest which files should NOT be in the same task.

        Based on past collisions, identifies files that were previously
        owned by different nodes in the same decomposition attempt,
        suggesting they should be split across tasks.

        Args:
            file_list: List of file patterns to analyze.

        Returns:
            List of file patterns that were involved in past collisions
            with files in file_list.
        """
        collision_entries = self.collision_history()
        files_in_collisions = set()

        # Build set of all files involved in past collisions
        for entry in collision_entries:
            for file_pat, owner_ids in entry.file_ownership_map.items():
                # Collision means file_pat is owned by multiple nodes
                if len(owner_ids) > 1:
                    files_in_collisions.add(file_pat)

        # Check which files in input file_list were in collisions
        problematic_files = []
        for f in file_list:
            if f in files_in_collisions:
                problematic_files.append(f)

        return problematic_files
