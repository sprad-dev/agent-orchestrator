"""Task DAG data model for decomposition.

Represents work as a directed acyclic graph of TaskNodes, each owning
specific files with declared inputs/outputs. Validates structural
integrity: no cycles, no orphans, no duplicate IDs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class TaskStatus(Enum):
    """Lifecycle status of a task node."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A single unit of decomposed work.

    Each node owns specific files, declares its inputs/outputs,
    and can depend on other nodes.
    """
    id: str
    description: str
    file_ownership: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    test_command: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING

    def is_ready(self, completed_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_ids for dep in self.dependencies)


@dataclass
class DAGValidationResult:
    """Result of validating a TaskDAG."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class TaskDAG:
    """Directed acyclic graph of TaskNodes.

    Builds and validates the dependency graph. Provides topological
    ordering and ready-task queries.
    """

    def __init__(self):
        self._nodes: Dict[str, TaskNode] = {}

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the DAG.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.id in self._nodes:
            raise ValueError(f"Duplicate node ID: {node.id}")
        self._nodes[node.id] = node

    def get_node(self, node_id: str) -> TaskNode:
        """Get a node by ID.

        Raises:
            KeyError: If node not found.
        """
        return self._nodes[node_id]

    @property
    def nodes(self) -> List[TaskNode]:
        """All nodes in insertion order."""
        return list(self._nodes.values())

    @property
    def node_ids(self) -> Set[str]:
        """Set of all node IDs."""
        return set(self._nodes.keys())

    def validate(self) -> DAGValidationResult:
        """Validate DAG structure.

        Checks:
        - No cycles in dependency graph
        - No dangling dependencies (referencing non-existent nodes)
        - At least one root node (no dependencies)
        """
        errors = []
        warnings = []

        # Check for dangling dependencies
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep not in self._nodes:
                    errors.append(
                        f"Node '{node.id}' depends on '{dep}' which doesn't exist"
                    )

        # Check for cycles using DFS
        cycle = self._detect_cycle()
        if cycle:
            errors.append(f"Cycle detected: {' -> '.join(cycle)}")

        # Check for at least one root
        roots = [n for n in self._nodes.values() if not n.dependencies]
        if self._nodes and not roots:
            errors.append("No root nodes found (every node has dependencies)")

        # Warn about isolated nodes (no deps and nothing depends on them)
        depended_on = set()
        for node in self._nodes.values():
            depended_on.update(node.dependencies)
        for node in self._nodes.values():
            if not node.dependencies and node.id not in depended_on and len(self._nodes) > 1:
                warnings.append(f"Node '{node.id}' is isolated (no connections)")

        return DAGValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def topological_sort(self) -> List[TaskNode]:
        """Return nodes in topological order (dependencies first).

        Raises:
            ValueError: If DAG contains cycles.
        """
        result = self._validate_and_sort()
        return result

    def ready_tasks(self) -> List[TaskNode]:
        """Return tasks whose dependencies are all completed."""
        completed = {
            nid for nid, n in self._nodes.items()
            if n.status == TaskStatus.COMPLETED
        }
        return [
            n for n in self._nodes.values()
            if n.status == TaskStatus.PENDING and n.is_ready(completed)
        ]

    def file_ownership_map(self) -> Dict[str, List[str]]:
        """Map files to the nodes that own them.

        Returns dict of {file_pattern: [node_ids]}. Files owned by
        multiple nodes indicate potential conflicts.
        """
        ownership: Dict[str, List[str]] = {}
        for node in self._nodes.values():
            for file_pat in node.file_ownership:
                ownership.setdefault(file_pat, []).append(node.id)
        return ownership

    def file_conflicts(self) -> Dict[str, List[str]]:
        """Return files owned by more than one node."""
        ownership = self.file_ownership_map()
        return {f: nodes for f, nodes in ownership.items() if len(nodes) > 1}

    def _detect_cycle(self) -> Optional[List[str]]:
        """Detect cycle using DFS. Returns cycle path or None."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self._nodes}
        parent = {}

        def dfs(nid: str) -> Optional[List[str]]:
            color[nid] = GRAY
            for dep in self._nodes[nid].dependencies:
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    # Found cycle - reconstruct path
                    cycle = [dep, nid]
                    curr = nid
                    while curr in parent and parent[curr] != dep:
                        curr = parent[curr]
                        cycle.append(curr)
                    cycle.append(dep)
                    return list(reversed(cycle))
                if color[dep] == WHITE:
                    parent[dep] = nid
                    result = dfs(dep)
                    if result:
                        return result
            color[nid] = BLACK
            return None

        for nid in self._nodes:
            if color[nid] == WHITE:
                result = dfs(nid)
                if result:
                    return result
        return None

    def _validate_and_sort(self) -> List[TaskNode]:
        """Kahn's algorithm for topological sort."""
        if not self._nodes:
            return []

        # Build in-degree map
        in_degree = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    # dep -> node (node depends on dep), but for topo sort
                    # we need reverse: dep has edge to node
                    pass

        # Build adjacency (dep -> dependents)
        adj: Dict[str, List[str]] = {nid: [] for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in adj:
                    adj[dep].append(node.id)
                    in_degree[node.id] = in_degree.get(node.id, 0) + 1

        # Recount in_degree properly
        in_degree = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in self._nodes:
                    in_degree[node.id] += 1

        # Start with zero in-degree nodes
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            # Sort for deterministic output
            queue.sort()
            nid = queue.pop(0)
            result.append(self._nodes[nid])

            for dependent in adj[nid]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._nodes):
            raise ValueError("DAG contains cycles, cannot topologically sort")

        return result
