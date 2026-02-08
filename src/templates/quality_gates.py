"""Anti-pattern prompt suffix for agent quality gates.

This suffix is appended to every task prompt to enforce quality standards
and prevent common agent failure modes:
- Shallow/useless tests
- Missing integration
- Hard-to-spot incompleteness

Based on Tier 0 backpressure mechanisms from docs/tier0-backpressure-deep-dive.md
"""

ANTI_PATTERN_SUFFIX = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALITY GATES — Do not mark this task complete until ALL are satisfied:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NO test-the-mock: Every assertion must verify observable behavior,
   not mock interactions. If you mock a dependency, assert on the
   output/side-effect, not on whether the mock was called.

   ❌ BAD:  mock_service.save.assert_called_once()
   ✓ GOOD: assert result.status == "saved"

2. NO orphan code: Every new public type/method must be called from
   existing code. Show the integration point.

   ❌ BAD:  Created new UserService but nothing imports/calls it
   ✓ GOOD: UserService is imported in api/routes.py:42 and called from create_user endpoint

3. NO happy-path-only: For every success test, write at least one
   failure/edge test. Common misses: null input, empty collection,
   duplicate entry, network failure, timeout.

   ❌ BAD:  test_create_user_success() only
   ✓ GOOD: test_create_user_success() + test_create_user_duplicate_email()

4. NO shallow assertions: "Assert.NotNull" / "assert obj is not None"
   alone is never sufficient. Assert on specific values, counts, or
   state changes.

   ❌ BAD:  assert result is not None
   ✓ GOOD: assert result.id == 123 and result.name == "Alice"

5. WIRING PROOF: List every existing file you modified and why. If
   you only created new files, explain how they're reachable from
   the application entrypoint (main, startup, controller, handler).

   Example: "Modified src/api/routes.py to register new endpoint,
            modified src/di/container.py to register UserService"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before submitting: Produce a completion manifest (see template).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# Language-specific adaptations
LANGUAGE_ADAPTATIONS = {
    'python': {
        'test_example_bad': 'mock_service.save.assert_called_once()',
        'test_example_good': 'assert result.status == "saved"',
        'assertion_bad': 'assert obj is not None',
        'assertion_good': 'assert result.id == 123 and result.name == "Alice"',
    },
    'csharp': {
        'test_example_bad': 'mockService.Verify(x => x.Save(It.IsAny<User>()), Times.Once)',
        'test_example_good': 'Assert.Equal("saved", result.Status)',
        'assertion_bad': 'Assert.NotNull(result)',
        'assertion_good': 'Assert.Equal(123, result.Id); Assert.Equal("Alice", result.Name)',
    },
    'typescript': {
        'test_example_bad': 'expect(mockService.save).toHaveBeenCalledOnce()',
        'test_example_good': 'expect(result.status).toBe("saved")',
        'assertion_bad': 'expect(result).not.toBeNull()',
        'assertion_good': 'expect(result).toEqual({ id: 123, name: "Alice" })',
    },
}


def get_quality_gates(language='python'):
    """Get quality gates suffix adapted for specific language.

    Args:
        language: Target language ('python', 'csharp', 'typescript')

    Returns:
        Quality gates string with language-specific examples
    """
    if language not in LANGUAGE_ADAPTATIONS:
        return ANTI_PATTERN_SUFFIX

    adaptations = LANGUAGE_ADAPTATIONS[language]

    # For now, return the default template
    # In the future, we could do string replacement for examples
    return ANTI_PATTERN_SUFFIX
