"""Unit tests for pytest test discovery and symbol linkage."""

from pathlib import Path
from repocontinuum.domain.models import ConfidenceLevel, TestDiscoveryMethod
from repocontinuum.indexing.ast_parser import PythonAstParser
from repocontinuum.indexing.test_discovery import PytestDiscoverer


def test_pytest_naming_conventions_and_methods(tmp_path: Path) -> None:
    """Verify discovery of test functions, test classes, and test methods."""
    test_content = '''
import pytest
from app.calculator import add, multiply

def test_add_function():
    assert add(1, 2) == 3

class TestCalculatorSuite:
    def test_multiply_method(self):
        assert multiply(2, 3) == 6

    def helper_not_a_test(self):
        pass
'''
    f = tmp_path / "test_calculator.py"
    f.write_text(test_content, encoding="utf-8")

    parser = PythonAstParser()
    indexed_file = parser.parse_file(f, tmp_path)

    discoverer = PytestDiscoverer()
    all_symbols = {
        "add": ["app.calculator.add"],
        "multiply": ["app.calculator.multiply"],
    }

    test_cases = discoverer.discover_tests(indexed_file, all_symbols)
    assert len(test_cases) == 3  # test_add_function, TestCalculatorSuite, test_multiply_method

    tc_by_name = {tc.name: tc for tc in test_cases}
    assert "test_add_function" in tc_by_name
    assert tc_by_name["test_add_function"].discovery_method == TestDiscoveryMethod.PYTEST_FUNCTION

    assert "TestCalculatorSuite" in tc_by_name
    assert tc_by_name["TestCalculatorSuite"].discovery_method == TestDiscoveryMethod.PYTEST_CLASS

    assert "test_multiply_method" in tc_by_name
    assert tc_by_name["test_multiply_method"].discovery_method == TestDiscoveryMethod.PYTEST_METHOD

    # Check linkage heuristics
    mult_test = tc_by_name["test_multiply_method"]
    assert "app.calculator.multiply" in mult_test.linked_symbols
    assert mult_test.link_confidence == ConfidenceLevel.HIGH


def test_non_test_files_ignored_by_discoverer(tmp_path: Path) -> None:
    """Verify that regular application modules do not produce test cases."""
    content = '''
def test_like_function():
    pass
'''
    f = tmp_path / "regular_service.py"
    f.write_text(content, encoding="utf-8")

    parser = PythonAstParser()
    indexed_file = parser.parse_file(f, tmp_path)

    discoverer = PytestDiscoverer()
    test_cases = discoverer.discover_tests(indexed_file, {})
    assert len(test_cases) == 0
