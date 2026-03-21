"""Abstract base for language-specific parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ParsedImport:
    """Represents a single import statement."""

    __slots__ = ("is_relative", "module", "names", "source_file")

    def __init__(
        self,
        module: str,
        names: list[str],
        *,
        is_relative: bool = False,
        source_file: str = "",
    ) -> None:
        self.module = module
        self.names = names
        self.is_relative = is_relative
        self.source_file = source_file


class ParsedFunction:
    """Represents a function/method signature."""

    __slots__ = ("is_async", "line_number", "name", "params", "return_type")

    def __init__(
        self,
        name: str,
        params: list[str],
        return_type: str = "",
        *,
        is_async: bool = False,
        line_number: int = 0,
    ) -> None:
        self.name = name
        self.params = params
        self.return_type = return_type
        self.is_async = is_async
        self.line_number = line_number


class BaseParser(ABC):
    """Base class for language-specific file parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this parser handles (e.g. {'.py'})."""

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix in self.supported_extensions

    @abstractmethod
    def extract_imports(self, file_path: Path, content: str) -> list[ParsedImport]:
        """Extract all import statements from file content."""

    @abstractmethod
    def extract_functions(self, file_path: Path, content: str) -> list[ParsedFunction]:
        """Extract function/method signatures from file content."""

    @abstractmethod
    def extract_env_vars(self, content: str) -> list[str]:
        """Extract environment variable references from file content."""

    @abstractmethod
    def count_typed_functions(self, file_path: Path, content: str) -> tuple[int, int]:
        """Return (typed_count, total_count) for type safety scoring."""
