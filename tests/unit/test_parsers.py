"""Tests for language parsers."""

from __future__ import annotations

from pathlib import Path

import pytest

from onboarding_agent.parsers.python_parser import PythonParser
from onboarding_agent.parsers.typescript_parser import TypeScriptParser


@pytest.mark.unit
class TestPythonParser:
    def setup_method(self) -> None:
        self.parser = PythonParser()

    def test_supported_extensions(self) -> None:
        assert ".py" in self.parser.supported_extensions
        assert ".pyi" in self.parser.supported_extensions

    def test_extract_imports(self) -> None:
        code = """
import os
from pathlib import Path
from .utils import helper
from onboarding_agent.config import Settings
"""
        imports = self.parser.extract_imports(Path("test.py"), code)
        assert len(imports) == 4
        modules = [i.module for i in imports]
        assert "os" in modules
        assert "pathlib" in modules

    def test_extract_functions(self) -> None:
        code = """
def sync_func(x: int, y: str) -> bool:
    return True

async def async_func(data: dict) -> list[str]:
    return []

def untyped_func(a, b):
    pass
"""
        funcs = self.parser.extract_functions(Path("test.py"), code)
        assert len(funcs) == 3
        assert funcs[0].name == "sync_func"
        assert funcs[0].return_type == "bool"
        assert funcs[1].is_async is True
        assert funcs[2].return_type == ""

    def test_extract_env_vars(self) -> None:
        code = """
db_url = os.environ["DATABASE_URL"]
secret = os.environ.get("SECRET_KEY", "default")
debug = os.getenv("DEBUG")
"""
        env_vars = self.parser.extract_env_vars(code)
        assert set(env_vars) == {"DATABASE_URL", "SECRET_KEY", "DEBUG"}

    def test_count_typed_functions(self) -> None:
        code = """
def typed(x: int) -> str: ...
def untyped(x): ...
async def also_typed() -> None: ...
"""
        typed, total = self.parser.count_typed_functions(Path("test.py"), code)
        assert typed == 2
        assert total == 3


@pytest.mark.unit
class TestTypeScriptParser:
    def setup_method(self) -> None:
        self.parser = TypeScriptParser()

    def test_supported_extensions(self) -> None:
        assert ".ts" in self.parser.supported_extensions
        assert ".tsx" in self.parser.supported_extensions
        assert ".js" in self.parser.supported_extensions

    def test_extract_imports(self) -> None:
        code = """
import { Router, Request } from 'express';
import React from 'react';
import * as path from 'path';
import { helper } from './utils';
"""
        imports = self.parser.extract_imports(Path("test.ts"), code)
        assert len(imports) == 4
        # Relative import detection
        relative_imports = [i for i in imports if i.is_relative]
        assert len(relative_imports) == 1

    def test_extract_env_vars(self) -> None:
        code = """
const dbUrl = process.env.DATABASE_URL;
const secret = process.env['SECRET_KEY'];
"""
        env_vars = self.parser.extract_env_vars(code)
        assert set(env_vars) == {"DATABASE_URL", "SECRET_KEY"}
