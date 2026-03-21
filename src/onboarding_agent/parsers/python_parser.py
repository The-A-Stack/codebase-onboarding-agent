"""Python-specific parser using AST and regex."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from onboarding_agent.parsers.base import BaseParser, ParsedFunction, ParsedImport

_ENV_VAR_PATTERNS = [
    re.compile(r"""os\.environ\[['"](\w+)['"]\]"""),
    re.compile(r"""os\.environ\.get\(['"](\w+)['"]"""),
    re.compile(r"""os\.getenv\(['"](\w+)['"]"""),
]


class PythonParser(BaseParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".py", ".pyi"}

    def extract_imports(self, file_path: Path, content: str) -> list[ParsedImport]:
        imports: list[ParsedImport] = []
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        ParsedImport(
                            module=alias.name,
                            names=[alias.asname or alias.name],
                            source_file=str(file_path),
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(
                    ParsedImport(
                        module=module,
                        names=names,
                        is_relative=node.level > 0,
                        source_file=str(file_path),
                    )
                )
        return imports

    def extract_functions(self, file_path: Path, content: str) -> list[ParsedFunction]:
        functions: list[ParsedFunction] = []
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return functions

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [
                    arg.arg for arg in node.args.args if arg.arg != "self" and arg.arg != "cls"
                ]
                return_type = ""
                if node.returns:
                    return_type = ast.unparse(node.returns)

                functions.append(
                    ParsedFunction(
                        name=node.name,
                        params=params,
                        return_type=return_type,
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                        line_number=node.lineno,
                    )
                )
        return functions

    def extract_env_vars(self, content: str) -> list[str]:
        env_vars: list[str] = []
        for pattern in _ENV_VAR_PATTERNS:
            env_vars.extend(pattern.findall(content))
        return list(set(env_vars))

    def count_typed_functions(self, file_path: Path, content: str) -> tuple[int, int]:
        functions = self.extract_functions(file_path, content)
        total = len(functions)
        typed = sum(1 for f in functions if f.return_type)
        return typed, total
