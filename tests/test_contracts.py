"""Architectural contract tests for paperweight.

These tests verify cross-cutting invariants that span modules. They catch
architectural drift before it causes runtime problems.
"""

import importlib
import pkgutil

import pytest


class TestModuleImports:
    """Verify all modules can be imported without errors."""

    def test_no_circular_imports(self):
        """All paperweight modules should be importable.

        This catches circular import issues that would prevent the
        package from loading.
        """
        import paperweight

        package_path = paperweight.__path__
        module_names = [
            name for _, name, _ in pkgutil.iter_modules(package_path)
        ]

        for module_name in module_names:
            full_name = f"paperweight.{module_name}"
            try:
                importlib.import_module(full_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {full_name}: {e}")


class TestExceptionHierarchy:
    """Verify custom exceptions follow proper inheritance."""

    def test_database_connection_error_inherits_from_runtime_error(self):
        """DatabaseConnectionError should be a RuntimeError.

        This allows callers to catch it specifically or as part of
        the broader RuntimeError family.
        """
        from paperweight.db import DatabaseConnectionError

        assert issubclass(DatabaseConnectionError, RuntimeError)

        # Verify it can be raised and caught
        with pytest.raises(RuntimeError):
            raise DatabaseConnectionError("test message")
