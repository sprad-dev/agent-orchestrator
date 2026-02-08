"""Example usage of templates module.

Run with: python -m src.templates.examples
"""

from src.templates import (
    ANTI_PATTERN_SUFFIX,
    COMPLETION_MANIFEST_TEMPLATE,
    format_completion_manifest,
)


def example_task_prompt():
    """Example: Building a task prompt with quality gates."""
    task = """
Task: Implement user authentication service

Requirements:
- Create UserService class with login/register methods
- Integrate with existing API routes
- Add unit and integration tests
- Handle error cases (invalid credentials, duplicate email)
"""

    # Quality gates are automatically appended via build_static_context,
    # but you can also do it manually:
    full_prompt = f"{task}\n{ANTI_PATTERN_SUFFIX}"

    print("=" * 70)
    print("EXAMPLE: Task Prompt with Quality Gates")
    print("=" * 70)
    print(full_prompt)
    print()


def example_completion_manifest_filled():
    """Example: Agent fills out completion manifest after completing task."""
    manifest = format_completion_manifest(
        files_created=[
            ("src/services/user_service.py", "User authentication service with login/register"),
            ("tests/test_user_service.py", "Unit tests for UserService"),
            ("tests/test_auth_integration.py", "Integration tests for auth endpoints"),
        ],
        files_modified=[
            ("src/api/routes.py", "Added /login and /register endpoints"),
            ("src/di/container.py", "Registered UserService in DI container"),
            ("requirements.txt", "Added bcrypt for password hashing"),
        ],
        integration_points={
            'entrypoint': "UserService.login() called from routes.py:67 in POST /login endpoint",
            'registration': "UserService registered in container.py:23",
            'configuration': "DB connection string in config.py already configured",
        },
        tests_added={
            'unit': 8,  # login success, register success, validation, etc.
            'integration': 4,  # API endpoint tests
            'edge_case': 6,  # duplicate email, invalid password, SQL injection, etc.
        },
        delete_test={
            'deleted_files': ["src/services/user_service.py"],
            'what_breaks': (
                "test_auth_integration.py::test_login_success would fail with ImportError, "
                "POST /login endpoint would return 500 (service not found)"
            ),
        },
        known_gaps=[
            "Rate limiting on login attempts deferred to follow-up task",
            "OAuth integration planned for next sprint",
        ],
    )

    print("=" * 70)
    print("EXAMPLE: Filled Completion Manifest")
    print("=" * 70)
    print(manifest)
    print()


def example_bad_manifest():
    """Example: Agent tries to cheat by submitting empty manifest."""
    from src.templates.completion_manifest import parse_completion_manifest

    # Agent just copy-pastes template
    bad_manifest = COMPLETION_MANIFEST_TEMPLATE

    parsed = parse_completion_manifest(bad_manifest)

    print("=" * 70)
    print("EXAMPLE: Detecting Unfilled Manifest")
    print("=" * 70)
    print(f"Agent submitted template-only manifest")
    print(f"Parsed result: {parsed}")
    print(f"Verdict: {'REJECTED - manifest not filled out' if parsed is None else 'ACCEPTED'}")
    print()


def example_multi_language_adaptation():
    """Example: How to adapt for C# projects."""
    print("=" * 70)
    print("EXAMPLE: Multi-Language Adaptation")
    print("=" * 70)
    print("For C# projects, the same templates apply with different examples:")
    print()
    print("Quality Gate 1: NO test-the-mock")
    print("  Python:  assert result.status == 'saved'")
    print("  C#:      Assert.Equal(\"Saved\", result.Status)")
    print()
    print("Quality Gate 4: NO shallow assertions")
    print("  Python:  assert result.id == 123 and result.name == 'Alice'")
    print("  C#:      Assert.Equal(123, result.Id); Assert.Equal(\"Alice\", result.Name)")
    print()
    print("The completion manifest structure is identical across languages.")
    print()


def main():
    """Run all examples."""
    example_task_prompt()
    print("\n" + "=" * 70 + "\n")

    example_completion_manifest_filled()
    print("\n" + "=" * 70 + "\n")

    example_bad_manifest()
    print("\n" + "=" * 70 + "\n")

    example_multi_language_adaptation()


if __name__ == "__main__":
    main()
