# paperweight FAQ

## Table of Contents

1. [General Questions](#general-questions)
2. [Configuration and Setup](#configuration-and-setup)
3. [Usage and Features](#usage-and-features)
4. [Troubleshooting](#troubleshooting)
5. [Maintenance and Updates](#maintenance-and-updates)

## General Questions

### What is paperweight?

paperweight is a personal project that automatically retrieves, filters, and summarizes recent academic papers from arXiv based on user-specified categories and preferences. It then sends notifications to the user via email.

### How often does paperweight check for new papers?

The program checks for new papers every time it is run. It compares the current date against the date stored in `last_processed_date.txt` in the root directory. If this file doesn't exist, it assumes it's the first run and pulls papers from the last seven days.

### What is the `last_processed_date.txt` file?

The `last_processed_date.txt` file is automatically created and updated by paperweight to keep track of when it last successfully processed papers. This file:

- Is created in the root directory of the project after the first successful run.
- Contains a single date in the format YYYY-MM-DD.
- Is used to determine which papers to fetch on subsequent runs, avoiding duplicate processing.
- Can be safely deleted if you want to reset the last processed date (paperweight will then fetch papers from the last 7 days on the next run).

### How does paperweight determine which papers to fetch?

paperweight uses the following logic to determine which papers to fetch:

1. If it's the first run (no `last_processed_date.txt` file exists), it fetches papers from the last 7 days.
2. On subsequent runs, it fetches papers published since the date in `last_processed_date.txt`.
3. The number of papers fetched per category is limited by the `max_results` setting in your configuration.

### Can I use paperweight with sources other than arXiv?

Currently, paperweight only supports arXiv as a source for academic papers. Support for additional sources may be added in future updates.

## Configuration and Setup

### How do I set up paperweight?

To set up paperweight:

1. Clone the repository and navigate to the project directory.
2. Copy `config-base.yaml` to `config.yaml` and edit it with your preferences.
3. Create a `.env` file in the project root and add your API keys if using summarization functionality.
4. Install the package using `pip install .`
5. Run the application using the `paperweight` command.

For more detailed instructions, please refer to the [README.md](../README.md) file.
For detailed configuration instructions, please see the [configuration guide](CONFIGURATION.md).

### How can I use a different LLM provider for summarization?

Currently, paperweight supports two LLM providers for summarization: OpenAI's GPT and Google's Gemini. This feature is currently in BETA and may have some limitations. You can specify the provider in the `config.yaml` file under the `analyzer` section:

```yaml
analyzer:
  type: summary
  llm_provider: openai  # or gemini
```

Make sure you have the appropriate API key set. You can set this in your `config.yaml`, as an environment variable, or in your `.env` file. For more details on securely managing API keys, please refer to the [environment variables guide](ENVIRONMENT_VARIABLES.md).

If you experience any issues with the summarization feature, you can switch to the `abstract` type in your configuration. We encourage users to report any problems or suggestions related to the BETA features by opening an issue on our GitHub repository.

## Usage and Features

### How can I customize which papers are retrieved and processed?

You can customize paper retrieval and processing by editing the `config.yaml` file. Key settings include:

1. arXiv categories
2. Keywords and exclusion keywords
3. Scoring weights
4. Minimum score threshold

For a detailed explanation of all configuration options, please see the [configuration guide](CONFIGURATION.md).

### How do I interpret the relevance scores and rankings?

Relevance scores are calculated based on the presence of keywords, important words, and exclusion keywords in the paper's title, abstract, and content. Papers are then ranked based on these scores. A higher score indicates that the paper is more likely to be relevant to your interests as defined in the configuration.

### Is it possible to exclude certain topics or keywords from the results?

Yes, you can use exclusion keywords to make certain papers less likely to be recommended. In your `config.yaml`, add exclusion keywords under the `processor` section:

```yaml
processor:
  exclusion_keywords:
    - keyword1
    - keyword2
```

Note that this doesn't completely exclude papers with these keywords, but significantly reduces their relevance score. The effectiveness of exclusion keywords depends on their weight relative to other scoring factors.

### How can I use the `--force-refresh` argument?

The `--force-refresh` argument allows you to ignore the `last_processed_date.txt` file and fetch papers from the last 7 days. This can be useful if you want to reprocess recent papers or if you've made significant changes to your configuration. Use it like this:

```
paperweight --force-refresh
```

### Can I customize the email format or content?

Currently, the email format and content are not customizable. This feature may be added in future updates.

## Troubleshooting

### How can I troubleshoot issues with paper downloads or processing?

To troubleshoot paper download or processing issues:

1. Set the logging level to DEBUG in your `config.yaml`:

```yaml
logging:
  level: DEBUG
  file: paperweight.log
```

2. Run paperweight again and check the log file for detailed information about each step of the process.
3. Look for any error messages or warnings in the log that might indicate the source of the problem.

### What should I do if I encounter Python dependency issues?

If you encounter Python dependency issues:

1. Ensure you're using Python 3.10 or higher.
2. Try creating a new virtual environment and installing paperweight fresh.
3. Update your pip and setuptools: `pip install --upgrade pip setuptools`
4. If you're still having issues, check the project's `setup.py` file for the list of required packages and versions, and try installing them manually.

### What should I do if I'm not receiving email notifications?

If you're not receiving email notifications:

1. Check your spam folder and verify your email configuration in `config.yaml`.
2. Ensure your SMTP settings are correct, especially if using Gmail or other providers with specific security requirements.
3. Check the log file (default: `paperweight.log`) for any error messages.

If you continue to have problems, please open an issue on the project's GitHub page.

### What do I do if I encounter API rate limits or errors?

If you encounter API rate limits:

1. Try reducing the `max_results` value in your config file.
2. Run paperweight less frequently.
3. Check your API usage on the provider's website.
4. Consider using the 'abstract' analyzer type instead of 'summary' to limit external API use.

### What should I do if the program seems to hang?

Check the log file to ensure it's still processing. Large paper sets or enabled summarization can increase runtime. The program will update the log file as it progresses through different stages of paper retrieval and processing.

### Why am I getting unexpected paper selections?

Review your keyword and scoring settings in the configuration file. The relevance of papers is determined by these settings. Adjust keywords, exclusion keywords, and scoring weights as needed to refine results. You may need to experiment with different configurations to achieve the desired paper selection.

## Maintenance and Updates

### How do I update paperweight to the latest version?

As paperweight doesn't have an established distribution pipeline yet, to update:

1. Pull the most recent version from the GitHub repository.
2. Reinstall the package using `pip install .` in the project directory.

### How can I contribute to the paperweight project?

Contributions to paperweight are welcome! You can contribute by:

1. Submitting issues for bugs or feature requests on the GitHub repository.
2. Creating pull requests with bug fixes or new features.
3. Improving documentation or writing tests.

Please refer to the project's GitHub page for more information on contributing.

### Is there a way to export or save the processed paper data?

Currently, paperweight does not have a built-in feature to export or save processed paper data. This could be a valuable feature to add in the future.

### How does paperweight handle papers in languages other than English?

While paperweight should theoretically work with papers in languages other than English, this functionality has not been extensively tested. The effectiveness may vary depending on the language and the LLM provider used for summarization.

### Can I use paperweight in an offline environment?

No, paperweight requires an internet connection to fetch papers from arXiv and to use the LLM APIs for summarization (if enabled). It cannot be used in a fully offline environment.