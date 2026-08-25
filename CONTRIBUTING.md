# Contributing to django-identifiers

Thank you for your interest in contributing to `django-identifiers`.

Contributions are welcome, including bug reports, documentation improvements, tests, and focused feature proposals.

`django-identifiers` is intentionally small and focused. Contributions should
preserve its role as a reusable identifier-generation foundation for Django.

## Development Setup

Clone the repository:

```bash
git clone https://github.com/fifoa-labs/django-identifiers.git
cd django-identifiers
```

Install the development environment:

```bash
uv sync
```

This project uses `uv` for dependency and environment management.

## Development Commands

The repository provides a `Makefile` for common development tasks.

Run the test suite:

```bash
make test
```

Run formatting:

```bash
make format
```

Run linting:

```bash
make lint
```

Run static type checking:

```bash
make typecheck
```

Before submitting a change, run the complete validation suite:

```bash
make release-check
```

All checks should pass before a pull request is submitted.

## Project Scope

`django-identifiers` provides reusable identifier-generation primitives for
Django models.

The package should remain:

* Django-focused
* Reusable across projects
* Explicit rather than convention-heavy
* Independent of project-specific models and application structure
* Focused on short, collision-resistant application identifiers

Features related to identifier generation, model lifecycle integration,
immutability, collision handling, and efficient bulk creation may belong in the
package when they are broadly useful to Django applications.

Project-specific identifier patterns, model registrations, business rules, and
domain-specific naming conventions generally do not belong in the core package.

Applications remain responsible for defining the identifier policies appropriate
for their own models.

## Compatibility

Changes should preserve the Python and Django versions supported by the project.

The supported versions are defined by the project's `pyproject.toml` and CI configuration.

Do not introduce dependencies on newer Python or Django features without first updating the project's declared compatibility policy and test matrix.

## Dependencies

Runtime dependencies should be kept minimal.

New dependencies should only be introduced when they provide substantial value that cannot reasonably be implemented using Python, Django, or the package's existing dependencies.

Please discuss significant new runtime dependencies before submitting a pull request that introduces them.

## Code Quality

Contributions should:

* Follow the existing project structure and conventions
* Include type annotations where appropriate
* Pass Ruff formatting and linting
* Pass mypy type checking
* Preserve deterministic behavior
* Avoid unnecessary abstractions
* Keep the public API intentional and small
* Avoid coupling the package to a specific application or domain

Public APIs should be designed conservatively. Once functionality becomes part of the public package API, downstream projects may depend on it.

## Tests

Behavior changes should include tests.

Bug fixes should normally include a regression test demonstrating the problem being fixed.

New features should include tests covering their expected behavior, edge cases, and relevant failure conditions.

The project maintains full statement and branch coverage. New contributions should preserve that standard.

Run coverage validation with:

```bash
make coverage
```

Do not add meaningless tests solely to satisfy a coverage percentage. Tests should verify useful behavior and important branches.

## Documentation

Changes to public behavior should include corresponding documentation updates.

When adding or changing public APIs, update the README or other relevant documentation so users can understand:

* What the feature does
* How to use it
* Any important constraints
* Whether existing behavior has changed

Examples should be small and representative.

## Public API

Treat additions to the public API carefully.

Implementation details should remain internal unless there is a clear reason for downstream applications to depend on them.

If a new class, function, or constant is intended to be public, ensure that it is exported consistently with the package's existing public API.

Tests should verify important public imports where appropriate.

## Pull Requests

Keep pull requests focused.

A pull request should ideally address one bug, feature, refactor, or documentation concern.

Before submitting a pull request:

1. Update your branch from `main`.
2. Run the formatter.
3. Run linting.
4. Run type checking.
5. Run the complete test suite.
6. Confirm coverage remains at the required level.
7. Update documentation when public behavior changes.
8. Review your diff for unrelated changes.

Please provide a clear pull request description explaining:

* What changed
* Why the change is needed
* Any important design decisions
* How the change was tested

Large architectural changes should generally be discussed before substantial implementation work begins.

## Backward Compatibility

Avoid unnecessary breaking changes.

If a contribution requires changing existing public behavior, explain the compatibility impact in the pull request.

Breaking changes should be deliberate, documented, and appropriate for the project's release strategy.

## Security Issues

Please do not report security vulnerabilities through public issues or pull requests.

Follow the instructions in `SECURITY.md` for responsible security reporting.

## Code of Conduct

Participation in this project is governed by the repository's `CODE_OF_CONDUCT.md`.

By participating, you are expected to follow those guidelines.

## License

By contributing to `django-identifiers`, you agree that your contributions will be licensed under the same license as the project.

Thank you for helping improve `django-identifiers`.
