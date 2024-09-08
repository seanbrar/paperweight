# paperweight

This project automatically retrieves, filters, and summarizes recent academic papers from arXiv based on user-specified categories, then sends notifications to the user.

## Features

- **ArXiv Integration**: Fetches recent papers from arXiv using their API, ensuring up-to-date access to the latest research.
- **Customizable Filtering**: Filters papers based on user-defined preferences, including keywords, categories, and exclusion criteria.
- **Intelligent Summarization**: Generates concise summaries or extracts abstracts, providing quick insights into paper content.
- **Flexible Notification System**: Notifies users via email, with potential for expansion to other notification methods.
- **Configurable Settings**: Allows users to fine-tune the application's behavior through a YAML configuration file.

## Table of Contents
- [Features](#features)
- [Getting Started](#getting-started)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

## Getting Started

### Prerequisites

- Python 3.7+
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
3. Run the application:
   ```
   paperweight
   ```

## Usage

After installation, you can run paperweight from anywhere using:

```
paperweight
```

Alternatively, you can run it as a module:

```
python -m paperweight
```

## Configuration

For information on configuration options, please see the [CONFIGURATION](CONFIGURATION.md) file.

## Development

To set up the project for development:

1. Clone the repository:
   ```
   git clone https://github.com/seanbrar/paperweight.git
   cd paperweight
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install development dependencies:
   ```
   pip install -r requirements-dev.txt
   ```

4. Run tests:
   ```
   pytest
   ```

5. Use `ruff` for linting:
   ```
   ruff check .
   ```

## Troubleshooting

- **Email Notifications Not Sending**: Ensure your email configuration is correct and that you've allowed less secure app access if using Gmail.
- **Paper Content Not Downloading**: Check your internet connection and verify that the arXiv API is accessible from your network.

For other problems, please open an issue on GitHub.

## Roadmap

- Implement machine learning-based paper recommendations
- Add support for additional academic paper sources
- Additional notification methods
- Additional configuration options

For a full list of proposed features and known issues, see the [open issues](https://github.com/seanbrar/paperweight/issues) page.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- arXiv for providing the API
- [simplerllm](https://github.com/hassancs91/SimplerLLM) for the LLM interface