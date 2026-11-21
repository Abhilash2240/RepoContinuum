"""Unit tests for Python AST parser."""

from pathlib import Path
import pytest
from repocontinuum.domain.models import ParseStatus, SymbolKind
from repocontinuum.indexing.ast_parser import PythonAstParser


@pytest.fixture
def parser() -> PythonAstParser:
    return PythonAstParser()


def test_simple_valid_python_module(tmp_path: Path, parser: PythonAstParser) -> None:
    """Test parsing a simple valid module with class and function."""
    content = '''"""Module docstring."""

def add(a: int, b: int = 0) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Calculator class."""
    def multiply(self, x: float, y: float) -> float:
        return x * y
'''
    f = tmp_path / "calc.py"
    f.write_text(content, encoding="utf-8")

    indexed = parser.parse_file(f, tmp_path)
    assert indexed.parse_status == ParseStatus.PARSED
    assert indexed.parse_error is None
    assert len(indexed.symbols) == 4  # Module, add, Calculator, Calculator.multiply

    # Module symbol
    mod_sym = indexed.symbols[0]
    assert mod_sym.kind == SymbolKind.MODULE
    assert mod_sym.docstring == "Module docstring."

    # Function symbol
    add_sym = [s for s in indexed.symbols if s.name == "add"][0]
    assert add_sym.kind == SymbolKind.FUNCTION
    assert add_sym.return_annotation == "int"
    assert len(add_sym.parameters) == 2
    assert add_sym.parameters[0].name == "a"
    assert add_sym.parameters[0].annotation == "int"
    assert add_sym.parameters[1].name == "b"
    assert add_sym.parameters[1].default_value == "0"

    # Class & method symbol
    calc_sym = [s for s in indexed.symbols if s.name == "Calculator"][0]
    assert calc_sym.kind == SymbolKind.CLASS
    assert calc_sym.docstring == "Calculator class."

    mult_sym = [s for s in indexed.symbols if s.name == "multiply"][0]
    assert mult_sym.kind == SymbolKind.METHOD
    assert mult_sym.qualified_name == "Calculator.multiply"
    assert mult_sym.parent_qualified_name == "Calculator"


def test_nested_functions_and_classes(tmp_path: Path, parser: PythonAstParser) -> None:
    """Test extracting nested classes and functions with proper qualified names."""
    content = '''
class Outer:
    class Inner:
        def inner_method(self):
            def deeply_nested():
                pass
            return deeply_nested
'''
    f = tmp_path / "nested.py"
    f.write_text(content, encoding="utf-8")

    indexed = parser.parse_file(f, tmp_path)
    assert indexed.parse_status == ParseStatus.PARSED

    qual_names = {s.qualified_name: s.kind for s in indexed.symbols}
    assert "Outer" in qual_names
    assert qual_names["Outer"] == SymbolKind.CLASS
    assert "Outer.Inner" in qual_names
    assert qual_names["Outer.Inner"] == SymbolKind.CLASS
    assert "Outer.Inner.inner_method" in qual_names
    assert qual_names["Outer.Inner.inner_method"] == SymbolKind.METHOD
    assert "Outer.Inner.inner_method.deeply_nested" in qual_names
    assert qual_names["Outer.Inner.inner_method.deeply_nested"] == SymbolKind.FUNCTION


def test_decorators_and_async_functions(tmp_path: Path, parser: PythonAstParser) -> None:
    """Test decorator extraction and async function/method detection."""
    content = '''
@decorator_one
@decorator_two("arg")
async def fetch_data(url: str):
    pass

class Service:
    @staticmethod
    async def async_method():
        pass
'''
    f = tmp_path / "async_mod.py"
    f.write_text(content, encoding="utf-8")

    indexed = parser.parse_file(f, tmp_path)
    assert indexed.parse_status == ParseStatus.PARSED

    fetch_sym = [s for s in indexed.symbols if s.name == "fetch_data"][0]
    assert fetch_sym.kind == SymbolKind.ASYNC_FUNCTION
    assert len(fetch_sym.decorators) == 2
    assert fetch_sym.decorators[0] == "decorator_one"
    assert fetch_sym.decorators[1] in {'decorator_two("arg")', "decorator_two('arg')"}

    method_sym = [s for s in indexed.symbols if s.name == "async_method"][0]
    assert method_sym.kind == SymbolKind.ASYNC_METHOD
    assert "@staticmethod" in method_sym.decorators or "staticmethod" in method_sym.decorators


def test_imports_extraction(tmp_path: Path, parser: PythonAstParser) -> None:
    """Test extracting direct and from...import statements."""
    content = '''
import os
import sys as system
from pathlib import Path, PurePath as PPath
from ..config import settings

def func():
    import local_module  # Dynamic import inside function
'''
    f = tmp_path / "imports_test.py"
    f.write_text(content, encoding="utf-8")

    indexed = parser.parse_file(f, tmp_path)
    assert indexed.parse_status == ParseStatus.PARSED

    imported_names = {i.imported_name: i for i in indexed.imports}
    assert "os" in imported_names
    assert "sys" in imported_names
    assert imported_names["sys"].alias == "system"
    assert "Path" in imported_names
    assert "PurePath" in imported_names
    assert imported_names["PurePath"].alias == "PPath"
    assert "local_module" in imported_names
    assert imported_names["local_module"].provenance == "dynamic_import"


def test_malformed_syntax_error_handled(tmp_path: Path, parser: PythonAstParser) -> None:
    """Verify that syntax errors are contained and do not raise exceptions."""
    content = "def broken_func(:\n    return 42\n"
    f = tmp_path / "broken.py"
    f.write_text(content, encoding="utf-8")

    indexed = parser.parse_file(f, tmp_path)
    assert indexed.parse_status == ParseStatus.SYNTAX_ERROR
    assert indexed.parse_error is not None
    assert indexed.parse_error.error_type == "SyntaxError"
    assert indexed.parse_error.line == 1
    assert len(indexed.symbols) == 0


def test_unicode_and_emojis(tmp_path: Path, parser: PythonAstParser) -> None:
    """Verify that source files with Unicode and emoji characters parse accurately."""
    content = '''
# 🚀 Unicode header with accented chars: naïve résumé
def greet(name: str = "世界") -> str:
    """挨拶する 😊"""
    return f"こんにちは, {name}"
'''
    f = tmp_path / "unicode_mod.py"
    f.write_text(content, encoding="utf-8")

    indexed = parser.parse_file(f, tmp_path)
    assert indexed.parse_status == ParseStatus.PARSED
    sym = indexed.symbols[0]
    assert sym.name == "greet"
    assert sym.docstring == "挨拶する 😊"
    assert sym.parameters[0].default_value in {'"世界"', "'世界'"}
