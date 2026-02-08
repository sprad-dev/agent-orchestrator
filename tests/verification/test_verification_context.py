"""Tests for VerificationContext dataclass."""

import pytest
from src.verification.layer import VerificationContext


class TestVerificationContext:
    """Tests for VerificationContext shared pipeline state."""

    def test_default_fields_are_none(self):
        ctx = VerificationContext()
        assert ctx.modified_files is None
        assert ctx.pytest_output is None
        assert ctx.test_count is None
        assert ctx.test_duration is None
        assert ctx.changed_files is None
        assert ctx.manifest_text is None
        assert ctx.test_files is None

    def test_fields_set_at_construction(self):
        ctx = VerificationContext(
            modified_files=["a.py"],
            pytest_output="1 passed",
            test_count=5,
            test_duration=1.2,
        )
        assert ctx.modified_files == ["a.py"]
        assert ctx.pytest_output == "1 passed"
        assert ctx.test_count == 5
        assert ctx.test_duration == 1.2

    def test_get_cached_computes_once(self):
        call_count = 0

        def expensive():
            nonlocal call_count
            call_count += 1
            return 42

        ctx = VerificationContext()
        result1 = ctx.get_cached("answer", expensive)
        result2 = ctx.get_cached("answer", expensive)

        assert result1 == 42
        assert result2 == 42
        assert call_count == 1

    def test_get_cached_different_keys(self):
        ctx = VerificationContext()
        ctx.get_cached("a", lambda: 1)
        ctx.get_cached("b", lambda: 2)

        assert ctx.get_cached("a", lambda: 99) == 1
        assert ctx.get_cached("b", lambda: 99) == 2

    def test_cache_independent_per_instance(self):
        ctx1 = VerificationContext()
        ctx2 = VerificationContext()

        ctx1.get_cached("key", lambda: "from_ctx1")
        ctx2.get_cached("key", lambda: "from_ctx2")

        assert ctx1.get_cached("key", lambda: "x") == "from_ctx1"
        assert ctx2.get_cached("key", lambda: "x") == "from_ctx2"

    def test_fields_mutable_after_construction(self):
        ctx = VerificationContext()
        ctx.pytest_output = "collected 10 items"
        ctx.test_count = 10
        assert ctx.pytest_output == "collected 10 items"
        assert ctx.test_count == 10


class TestLayerContextIntegration:
    """Test that layers accept context parameter."""

    def test_file_exists_layer_reads_from_context(self, tmp_path):
        from src.verification.file_exists import FileExistsLayer

        test_file = tmp_path / "exists.py"
        test_file.write_text("pass")

        ctx = VerificationContext(modified_files=[str(test_file)])
        layer = FileExistsLayer()
        result = layer.run(context=ctx)

        assert result.passed is True

    def test_file_exists_layer_kwargs_override_context(self, tmp_path):
        from src.verification.file_exists import FileExistsLayer

        test_file = tmp_path / "exists.py"
        test_file.write_text("pass")

        # Context has a nonexistent file, but kwargs override
        ctx = VerificationContext(modified_files=["/nonexistent.py"])
        layer = FileExistsLayer()
        result = layer.run(context=ctx, files=[str(test_file)])

        assert result.passed is True

    def test_syntax_check_layer_reads_from_context(self, tmp_path):
        from src.verification.syntax_check import SyntaxCheckLayer

        test_file = tmp_path / "valid.py"
        test_file.write_text("x = 1\n")

        ctx = VerificationContext(modified_files=[str(test_file)])
        layer = SyntaxCheckLayer()
        result = layer.run(context=ctx)

        assert result.passed is True

    def test_pytest_validator_reads_from_context(self):
        from src.verification.pytest_validator import PytestValidatorLayer

        ctx = VerificationContext(pytest_output="collected 5 items\n5 passed")
        layer = PytestValidatorLayer()
        result = layer.run(context=ctx)

        assert result.passed is True

    def test_test_count_reads_from_context(self, tmp_path):
        from src.verification.test_count import CountBaselineLayer

        baseline = tmp_path / ".test_baseline"
        ctx = VerificationContext(test_count=10)
        layer = CountBaselineLayer(str(baseline))
        result = layer.run(context=ctx)

        assert result.passed is True
        assert "10" in result.message

    def test_coordinator_passes_context(self):
        from src.verification.coordinator import LayerCoordinator
        from src.verification.pytest_validator import PytestValidatorLayer

        coord = LayerCoordinator()
        coord.register_layer(PytestValidatorLayer())

        ctx = VerificationContext(pytest_output="collected 3 items\n3 passed")
        passed, results = coord.run_layers(3, context=ctx)

        assert passed is True
        assert len(results) == 1
