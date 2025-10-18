# Contributing to Mini JSON Summarizer

Thank you for your interest in contributing! This guide will help you get started.

## Branching Strategy

We use a feature branch workflow:

- `main` (or `master`) - Production-ready code, always deployable
- `feature/*` - New features (e.g., `feature/llm-engine`, `feature/template-dsl`)
- `bugfix/*` - Bug fixes (e.g., `bugfix/redaction-leak`)
- `hotfix/*` - Critical production fixes

### Workflow

1. **Create a feature branch from main:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes with clear commits:**
   ```bash
   git add .
   git commit -m "Add: description of what you added"
   ```

3. **Push your branch:**
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. **Create a Pull Request:**
   - Go to GitHub and create a PR from your feature branch to `main`
   - Fill out the PR template with a clear description
   - Wait for CI checks to pass
   - Request review from maintainers

5. **After approval, merge:**
   - Squash and merge for cleaner history
   - Delete the feature branch after merging

## Commit Message Guidelines

Follow conventional commits format:

- `Add: new feature or capability`
- `Fix: bug fix`
- `Update: improvements to existing features`
- `Refactor: code restructuring without behavior changes`
- `Docs: documentation updates`
- `Test: adding or updating tests`
- `Chore: maintenance tasks`

Example:
```
Add: LLM engine with OpenAI adapter

- Implement LLMEngine interface
- Add OpenAI API integration
- Include evidence-only system prompts
- Add constrained JSON generation
```

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/stevenmcsorley/mini-json-summarizer.git
   cd mini-json-summarizer
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -e .[dev]
   ```

4. **Run tests:**
   ```bash
   pytest
   ```

5. **Start development server:**
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

## Code Quality Standards

### Before submitting a PR:

1. **Run linting:**
   ```bash
   ruff check app/ tests/
   ```

2. **Format code:**
   ```bash
   black app/ tests/
   ```

3. **Run tests:**
   ```bash
   pytest --cov=app
   ```

4. **Run integration tests:**
   ```bash
   bash edge_cases_strict.sh
   ```

### Code Style

- Follow PEP 8 conventions
- Use type hints for function signatures
- Write docstrings for public functions
- Keep functions focused and single-purpose
- Maximum line length: 100 characters

## Testing

### Unit Tests

Place unit tests in `tests/` matching the module structure:
```
app/summarizer/engines/deterministic.py
tests/test_deterministic_engine.py
```

### Integration Tests

Shell scripts for end-to-end testing:
- `edge_cases_strict.sh` - Edge case validation
- `load_smoke.sh` - Load testing
- `mega_test.sh` - Comprehensive testing

## Pull Request Process

1. **PR Title:** Use conventional commit format
   - `Add: LLM engine support`
   - `Fix: redaction not applied before LLM`

2. **PR Description:** Include:
   - What: Brief description of changes
   - Why: Problem being solved
   - How: Approach taken
   - Testing: How you tested the changes
   - Screenshots/examples (if applicable)

3. **Link Issues:** Reference related issues with `Fixes #123` or `Relates to #456`

4. **Wait for CI:** All checks must pass before merge

5. **Address Review Comments:** Respond to all feedback

6. **Update Documentation:** Keep README, API docs, and code comments current

## Feature Development Guidelines

### Adding a New Feature

1. Check the PRD.md for alignment with project goals
2. Create a feature branch
3. Implement with tests
4. Update documentation
5. Create PR with detailed description

### LLM Engine Development (Specific)

When implementing LLM features:
- Always use evidence bundles, never raw JSON
- Implement constrained generation with JSON schemas
- Add system prompts that prevent hallucinations
- Include fallback to deterministic mode
- Log token usage and latency metrics

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions
- Check existing issues and PRs first

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
