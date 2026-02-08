"""Layer abstraction for verification pipeline.

Defines the base Layer interface and LayerResult dataclass.
Enables parallel development by decoupling layers from runner.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class LayerResult:
    """Result from a verification layer execution."""
    passed: bool
    message: str
    error_details: List[str] = None
    
    def __post_init__(self):
        """Initialize error_details as empty list if None."""
        if self.error_details is None:
            self.error_details = []


@dataclass
class VerificationContext:
    """Shared state flowing through verification pipeline.

    Accumulated as layers execute. Layers read from context instead of
    receiving loose kwargs — makes dependencies explicit and enables caching.
    """
    modified_files: Optional[List[str]] = None
    pytest_output: Optional[str] = None
    test_count: Optional[int] = None
    test_duration: Optional[float] = None
    changed_files: Optional[List[str]] = None
    manifest_text: Optional[str] = None
    test_files: Optional[List[str]] = None

    _cache: dict = field(default_factory=dict, repr=False)

    def get_cached(self, key: str, compute_fn: Callable):
        """Get cached value or compute and cache it."""
        if key not in self._cache:
            self._cache[key] = compute_fn()
        return self._cache[key]


class Layer(ABC):
    """Base class for verification layers.
    
    Subclasses implement specific verification logic.
    Each layer is responsible for a single verification concern.
    """
    
    def __init__(self):
        """Initialize layer with enabled flag."""
        self.enabled = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Layer name (e.g., 'FileExists', 'SyntaxCheck')."""
        pass
    
    @property
    @abstractmethod
    def level(self) -> int:
        """Layer level (L1=1, L2=2, etc.) for execution ordering."""
        pass
    
    @abstractmethod
    def run(self, *, context: Optional['VerificationContext'] = None, **kwargs) -> LayerResult:
        """Execute the verification layer.

        Args:
            context: Optional VerificationContext with shared pipeline state
            **kwargs: Layer-specific parameters (backwards compat)

        Returns:
            LayerResult with pass/fail status and message
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if layer is enabled.
        
        Returns:
            True if layer should run, False otherwise
        """
        return self.enabled
    
    def __repr__(self) -> str:
        """String representation of layer."""
        return f"{self.__class__.__name__}(level={self.level})"
