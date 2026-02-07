# paperweight

[![PyPI](https://img.shields.io/pypi/v/academic-paperweight)](https://pypi.org/project/academic-paperweight/)
[![GitHub License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

Automated retrieval, filtering, and LLM-powered summarization of arXiv papers based on your research interests.

## Background

Staying current with research in rapidly evolving fields like machine learning, physics, or computational biology can be overwhelming. paperweight was developed to solve this challenge by automating the process of monitoring, filtering, and summarizing new publications. Unlike generic paper recommendation systems, paperweight puts researchers in control with fine-grained filtering and personalized relevance scoring, delivering only the most pertinent research directly to your inbox.

## Features

- **ArXiv Integration**: Fetches recent papers from arXiv using their API, ensuring up-to-date access to the latest research.
- **Customizable Filtering**: Filters papers based on user-defined preferences, including keywords, categories, and exclusion criteria.
- **Intelligent Summarization** (BETA): Generates concise summaries or extracts abstracts, providing quick insights into paper content.
- **Flexible Notification System**: Notifies users via email, with potential for expansion to other notification methods.
- **Configurable Settings**: Allows users to fine-tune the application's behavior through a YAML configuration file.

## System Architecture

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    SCRAPER    │───▶│   PROCESSOR   │───▶│   ANALYZER    │───▶│   NOTIFIER    │
└───────────────┘     └───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │                     │
        ▼                     ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ arXiv API &   │     │ Scoring &     │     │ Abstract      │     │ Email &       │
│ PDF Processing│     │ Filtering     │     │ Extraction    │     │ Templating    │
└───────────────┘     └───────────────┘     └───────────────┘     └───────────────┘
```

## AI Technology Implementation

paperweight leverages several AI technologies to enhance research discovery:

1. **LLM-Based Summarization**: Integrates with OpenAI and Gemini models to generate concise, contextual summaries that capture key contributions, methodologies, and findings.

2. **Semantic Relevance Scoring**: Goes beyond simple keyword matching by implementing a weighted scoring algorithm that considers term frequency, positional importance, and contextual relevance.

3. **Adaptive Content Extraction**: Intelligently parses PDF structure to identify and extract the most meaningful content sections from diverse paper formats.

4. **Context Management**: Optimizes token usage through selective content extraction and compression techniques to work within LLM context limits.

## Table of Contents
- [Background](#background)
- [Features](#features)
- [System Architecture](#system-architecture)
- [AI Technology Implementation](#ai-technology-implementation)
- [Getting Started](#getting-started)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [FAQ and Troubleshooting](#faq-and-troubleshooting)
- [Technical Details](#technical-details)
- [Roadmap](#roadmap)
- [Glossary](#glossary)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

### From PyPI

```bash
pip install academic-paperweight
```

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/seanbrar/paperweight.git
   cd paperweight
   ```

2. Install the package:
   ```bash
   # Using uv (recommended)
   uv sync --all-extras
   source .venv/bin/activate
   
   # Or using pip
   pip install .
   ```

## Quick Start

1. Copy `config-base.yaml` to `config.yaml` and edit it with your preferences.
2. Create a `.env` file in the project root and add your API keys (if using the summarization functionality):
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   Note: While .env files are supported for local development, using system environment variables is recommended for enhanced security in production environments.
3. **Important:** Configure valid SMTP settings in `config.yaml` for email notifications.
4. Run the application:
   ```
   paperweight
   ```

Note: paperweight uses a `last_processed_date.txt` file to track when it last processed papers, ensuring efficient updates on subsequent runs.

## Usage

After installation, you can run paperweight from anywhere using:

```
paperweight
```

Recommended usage: Run paperweight daily for optimal paper tracking. Automatic scheduling is not currently built-in.

Note: Runtime may vary based on the number of categories, papers, and whether summarization is enabled. Check the log file for progress updates during execution.

### Command-line Arguments

- `--force-refresh`: Forces paperweight to fetch and process papers regardless of the last processed date.

## Configuration

For detailed information on configuration options, please see the [configuration guide](docs/CONFIGURATION.md).

For details on environment variables and handling sensitive information, refer to the [environment variables guide](docs/ENVIRONMENT_VARIABLES.md).

## FAQ and Troubleshooting

For quick solutions to common issues:

- **Email Notifications Not Sending**: Ensure your email configuration is correct and that you've allowed less secure app access if using Gmail.
- **Paper Content Not Downloading**: Check your internet connection and verify that the arXiv API is accessible from your network.

For a comprehensive list of frequently asked questions, including setup instructions, usage details, and troubleshooting steps, please refer to the [FAQ](docs/FAQ.md).

If you can't find an answer to your question or solution to your problem in the FAQ, please [open an issue](https://github.com/seanbrar/paperweight/issues) on GitHub.

## Technical Details

### Processing Pipeline

paperweight processes papers through four main stages:

1. **Scraping** (`scraper.py`): Fetches recent papers from arXiv's API based on user-defined categories and processes the PDF/LaTeX content.

2. **Processing** (`processor.py`): Calculates relevance scores based on keyword matching, with weights for title, abstract, and content matches, plus handling of exclusion keywords.

3. **Analysis** (`analyzer.py`): Either extracts the abstract or generates a summary using an LLM (OpenAI or Gemini), with configurable options.

4. **Notification** (`notifier.py`): Formats the filtered papers and sends them via email, with options for sorting by relevance, date, or title.

### Resilience Features

- **Retry Logic**: Uses the `tenacity` library to implement exponential backoff for API calls
- **Error Handling**: Comprehensive error catching and logging throughout the codebase
- **State Persistence**: Maintains processing state between runs using the `last_processed_date.txt` file

### Performance Considerations

- **Token Counting**: Uses `tiktoken` to accurately count tokens for LLM context management
- **Configurable Limits**: Allows setting maximum papers per category to control processing time
- **Incremental Processing**: Only fetches papers published since the last run

## Roadmap

Key upcoming features:
- Implement machine learning-based paper recommendations
- Add support for additional academic paper sources
- Expand notification methods
- Enhance batch processing capabilities

For a full list of proposed features and planned enhancements, see the detailed [roadmap](docs/ROADMAP.md).

## Glossary

- **arXiv**: An open-access repository of electronic preprints for scientific papers.
- **API**: Application Programming Interface; a way for different software to communicate.
- **YAML**: A human-readable data serialization format used for configuration files.
- **SMTP**: Simple Mail Transfer Protocol; used for sending emails.
- **LLM**: Large Language Model; an AI model used for text generation and analysis.
- **Embedding**: A numerical representation of text that captures semantic meaning.
- **Token**: A unit of text processed by language models, roughly corresponding to 4 characters.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! If you're interested in contributing to paperweight, please refer to the [contributing guide](docs/CONTRIBUTING.md) for detailed information on:

- Setting up the development environment
- Running tests
- Our coding standards
- The pull request process

We appreciate all forms of contribution, from code to documentation to bug reports. Thank you for helping to improve paperweight!

## Acknowledgments

- arXiv for providing the API
- [simplerllm](https://github.com/hassancs91/SimplerLLM) for the LLM interface
