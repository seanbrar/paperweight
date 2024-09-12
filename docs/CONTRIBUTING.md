# paperweight contributing guide

Thank you for your interest in contributing to paperweight, a Python tool for collecting and recommending arXiv papers. We welcome contributions from the community to help improve and expand this project.

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```
   git clone https://github.com/your-username/paperweight.git
   cd paperweight
   ```
3. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```
4. Install development dependencies:
   ```
   pip install -r requirements-dev.txt
   ```

## Development Setup

1. Ensure you have Python 3.7 or higher installed.
2. Set up your development environment as described in the "Getting Started" section.
3. Copy `config-base.yaml` to `config.yaml` and edit it with your preferences.
4. Create a `.env` file in the project root and add your API keys if using the summarization functionality:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
5. Configure valid SMTP settings in `config.yaml` for email notifications.

## Making Changes

1. Create a new branch for your feature or bugfix:
   ```
   git checkout -b feature-or-bugfix-name
   ```
2. Make your changes in your feature branch.
3. Add or update tests as necessary.
4. Ensure all tests pass by running:
   ```
   pytest
   ```
5. Use `ruff` for linting:
   ```
   ruff check .
   ```
6. Run type checking with mypy:
   ```
   mypy .
   ```
7. Update the documentation if you've added or changed functionality.

## Submitting Changes

1. Ensure all tests pass by running:
   ```
   pytest
   ```
   It's crucial that all tests pass before you submit your pull request. Pull requests with failing tests will not be merged.

2. Run the linter and type checker:
   ```
   ruff check .
   mypy .
   ```
   Address any issues raised by these tools.

3. Push your changes to your fork on GitHub:
   ```
   git push origin feature-or-bugfix-name
   ```

4. Submit a pull request to the main paperweight repository.

5. In your pull request description:
   - Describe your changes in detail
   - Mention any related issues
   - Confirm that all tests are passing
   - Note any new dependencies added

6. Be prepared to address feedback and make additional changes if requested during the review process.

## Coding Standards

- Follow PEP 8 style guidelines for Python code.
- Use meaningful variable and function names.
- Add comments to explain complex logic or algorithms.
- Ensure your code passes `ruff` linting and `mypy` type checking.
- Write and update tests for new functionality using pytest.

## Reporting Issues

If you find a bug or have a suggestion for improvement:

1. Check if the issue already exists in the GitHub issue tracker.
2. If not, create a new issue, providing as much relevant information as possible.

## Project Structure

- `paperweight/`: Main package directory
- `tests/`: Directory containing pytest tests
- `docs/`: Project documentation
- `config-base.yaml`: Base configuration file
- `requirements.txt`: Project dependencies
- `requirements-dev.txt`: Development dependencies

## Questions?

If you have any questions about contributing, feel free to open an issue for discussion.

Thank you for contributing to paperweight!