"""TypeScript/JavaScript parser using regex (tree-sitter integration added later)."""

from __future__ import annotations

import re
from pathlib import Path

from onboarding_agent.parsers.base import BaseParser, ParsedFunction, ParsedImport

_IMPORT_PATTERNS = [
    # import { x, y } from 'module'
    re.compile(r"""import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]"""),
    # import x from 'module'
    re.compile(r"""import\s+(\w+)\s+from\s+['"]([^'"]+)['"]"""),
    # import * as x from 'module'
    re.compile(r"""import\s+\*\s+as\s+(\w+)\s+from\s+['"]([^'"]+)['"]"""),
    # const x = require('module')
    re.compile(r"""(?:const|let|var)\s+(?:\{([^}]+)\}|(\w+))\s*=\s*require\(['"]([^'"]+)['"]\)"""),
]

_ENV_PATTERNS = [
    re.compile(r"""process\.env\.(\w+)"""),
    re.compile(r"""process\.env\[['"](\w+)['"]\]"""),
]

_FUNCTION_PATTERN = re.compile(
    r"""(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*"""
    r"""\(([^)]*)\)(?:\s*:\s*([^\s{]+))?\s*\{""",
)

_ARROW_PATTERN = re.compile(
    r"""(?:export\s+)?(?:const|let)\s+(\w+)\s*"""
    r"""(?::\s*\([^)]*\)\s*=>\s*\w+\s*)?=\s*(?:async\s+)?"""
    r"""\(([^)]*)\)(?:\s*:\s*([^\s=]+))?\s*=>""",
)


class TypeScriptParser(BaseParser):
    @property
    def supported_extensions(self) -> set[str]:
        return {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

    def extract_imports(self, file_path: Path, content: str) -> list[ParsedImport]:
        imports: list[ParsedImport] = []

        for pattern in _IMPORT_PATTERNS[:3]:
            for match in pattern.finditer(content):
                names_str, module = match.group(1), match.group(2)
                names = [n.strip().split(" as ")[0].strip() for n in names_str.split(",")]
                is_relative = module.startswith(".")
                imports.append(
                    ParsedImport(
                        module=module,
                        names=names,
                        is_relative=is_relative,
                        source_file=str(file_path),
                    )
                )

        # require() pattern
        for match in _IMPORT_PATTERNS[3].finditer(content):
            destructured, default_name, module = match.groups()
            names = [n.strip() for n in destructured.split(",")] if destructured else [default_name]
            imports.append(
                ParsedImport(
                    module=module,
                    names=names,
                    is_relative=module.startswith("."),
                    source_file=str(file_path),
                )
            )
        return imports

    def extract_functions(self, file_path: Path, content: str) -> list[ParsedFunction]:
        functions: list[ParsedFunction] = []

        for match in _FUNCTION_PATTERN.finditer(content):
            name, params_str, return_type = match.groups()
            params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
            is_async = "async" in content[max(0, match.start() - 10) : match.start()]
            line_num = content[: match.start()].count("\n") + 1
            functions.append(
                ParsedFunction(
                    name=name,
                    params=params,
                    return_type=return_type or "",
                    is_async=is_async,
                    line_number=line_num,
                )
            )

        for match in _ARROW_PATTERN.finditer(content):
            name, params_str, return_type = match.groups()
            params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
            line_num = content[: match.start()].count("\n") + 1
            functions.append(
                ParsedFunction(
                    name=name,
                    params=params,
                    return_type=return_type or "",
                    line_number=line_num,
                )
            )
        return functions

    def extract_env_vars(self, content: str) -> list[str]:
        env_vars: list[str] = []
        for pattern in _ENV_PATTERNS:
            env_vars.extend(pattern.findall(content))
        return list(set(env_vars))

    def count_typed_functions(self, file_path: Path, content: str) -> tuple[int, int]:
        functions = self.extract_functions(file_path, content)
        total = len(functions)
        typed = sum(1 for f in functions if f.return_type)
        return typed, total
