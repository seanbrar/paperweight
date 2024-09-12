# paperweight

This project automatically retrieves, filters, and summarizes recent academic papers from arXiv based on user-specified categories, then sends notifications to the user.

## Features

- **ArXiv Integration**: Fetches recent papers from arXiv using their API, ensuring up-to-date access to the latest research.
- **Customizable Filtering**: Filters papers based on user-defined preferences, including keywords, categories, and exclusion criteria.
- **Intelligent Summarization** (BETA): Generates concise summaries or extracts abstracts, providing quick insights into paper content. Note: This feature is currently in beta and may have some limitations.
- **Flexible Notification System**: Notifies users via email, with potential for expansion to other notification methods.
- **Configurable Settings**: Allows users to fine-tune the application's behavior through a YAML configuration file.

## Table of Contents
- [Getting Started](#getting-started)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [FAQ and Troubleshooting](#faq-and-troubleshooting)
- [Roadmap](#roadmap)
- [Glossary](#glossary)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Required Python packages:
  - pypdf
  - python-dotenv
  - PyYAML
  - requests
  - simplerllm

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/seanbrar/paperweight.git
   cd paperweight
   ```

2. Install the package:
   ```
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

## Roadmap

Key upcoming features:
- Implement machine learning-based paper recommendations
- Add support for additional academic paper sources
- Expand notification methods

For a full list of proposed features and known issues, see the [open issues](https://github.com/seanbrar/paperweight/issues) page or the detailed [roadmap](docs/ROADMAP.md).

## Glossary

- **arXiv**: An open-access repository of electronic preprints for scientific papers.
- **API**: Application Programming Interface; a way for different software to communicate.
- **YAML**: A human-readable data serialization format used for configuration files.
- **SMTP**: Simple Mail Transfer Protocol; used for sending emails.
- **LLM**: Large Language Model; an AI model used for text generation and analysis.

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