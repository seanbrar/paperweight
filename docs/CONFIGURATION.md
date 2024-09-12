# paperweight configuration guide

## Introduction

This document explains how to configure paperweight. The system uses a YAML configuration file to customize its behavior, allowing you to tailor the paper selection, processing, analysis, and notification to your specific needs.

## Table of Contents
- [paperweight Configuration Guide](#paperweight-configuration-guide)
  - [Introduction](#introduction)
  - [Configuration Setup](#configuration-setup)
  - [Security Note](#security-note)
  - [Configuration Options](#configuration-options)
    - [ArXiv Settings](#arxiv-settings)
    - [Processor Settings](#processor-settings)
    - [Analyzer Settings](#analyzer-settings)
    - [Notifier Settings](#notifier-settings)
    - [Logging Settings](#logging-settings)
  - [Additional Notes](#additional-notes)
  - [Troubleshooting](#troubleshooting)

## Configuration Setup

1. Locate the `config-base.yaml` file in the project directory.
2. Make a copy of this file and rename it to `config.yaml`.
3. Open `config.yaml` in a text editor and modify the values according to your preferences.

## Security Note

> ⚠️ **Important:** Keep your `config.yaml` file secure, especially if it contains sensitive information like email passwords or API keys. We strongly recommend using environment variables for sensitive data instead of storing them directly in the configuration file.

For more information on securely managing passwords, API keys, and other sensitive information, please refer to the [environment variables guide](ENVIRONMENT_VARIABLES.md).

## Configuration Options

### ArXiv Settings

```yaml
arxiv:
  categories:
    - cs.AI
    - cs.CL
    - cs.LG
  max_results: 100
```

- `categories`: List the arXiv categories you're interested in. Replace with your desired categories. Examples:
  - `cs.AI` (Artificial Intelligence)
  - `cs.CL` (Computation and Language)
  - `cs.LG` (Machine Learning)
- Find a full list of arXiv categories [here](https://arxiv.org/category_taxonomy).
- `max_results`: Specifies an additional limit on the number of papers to fetch per category.
  - If set to a positive number (e.g., 100), it limits the papers fetched per category to that number.
  - If set to 0, no additional limit is applied beyond the daily published papers.
  - Example: If there are 15 papers in category A, 10 in B, and 5 in C, with `max_results: 10`:
    - Category A: 10 papers fetched
    - Category B: 10 papers fetched
    - Category C: 5 papers fetched

**Note**: Setting a lower `max_results` value can help reduce processing time, especially for popular categories with many daily submissions.

### Processor Settings

The processor settings control how papers are evaluated and scored. These settings allow you to customize the system to focus on topics that are most relevant to your interests.

```yaml
processor:
  keywords:
    - machine learning
    - natural language processing
    - deep learning
  exclusion_keywords:
    - quantum computing
    - blockchain
  important_words:
    - transformer
    - attention mechanism
  title_keyword_weight: 3
  abstract_keyword_weight: 2
  content_keyword_weight: 1
  exclusion_keyword_penalty: 5
  important_words_weight: 0.5
  min_score: 10
```

#### Understanding the Settings

1. `keywords`: 
   - List of terms you're interested in. 
   - The system searches for these words in the title, abstract, and main content of each paper.
   - Papers containing these words receive higher scores.

2. `exclusion_keywords`: 
   - Terms you want to avoid.
   - If a paper contains these words, its score is reduced.

3. `important_words`: 
   - Special terms that are particularly significant in your field of interest.
   - Finding these words in a paper gives it an extra score boost.

4. `title_keyword_weight`: 3
   - Determines how much a keyword in the title contributes to the overall score.

5. `abstract_keyword_weight`: 2
   - Sets the importance of keywords found in the paper's abstract.

6. `content_keyword_weight`: 1
   - Defines how much keywords in the main content contribute to the score.

7. `exclusion_keyword_penalty`: 5
   - Determines how much the score is reduced when an exclusion keyword is found.

8. `important_words_weight`: 0.5
   - Sets how much the important words contribute to the overall score.

9. `min_score`: 10
   - The minimum score a paper must achieve to be included in your notifications.

#### How It Works

1. For each paper, the system searches for your keywords in the title, abstract, and content.
2. It calculates a score based on how many keywords are found and where they appear, using the respective weights.
3. If exclusion keywords are found, it reduces the score.
4. It then looks for important words and adds a small boost to the score if they're present.
5. If the final score is at least equal to the `min_score`, the paper is included in your notifications.

By adjusting these settings, you can fine-tune the system to better match your specific interests and filter out less relevant papers.

**Note**: The system requires at least one item in each category (keywords, exclusion_keywords, important_words) to function properly.

### Analyzer Settings (BETA)

```yaml
analyzer:
  type: abstract  # abstract | summary
  llm_provider: openai  # gemini | openai
```

- `type`: Choose between:
  - `abstract`: Uses the paper's original abstract in the final email.
  - `summary` (BETA): Generates a summary using the specified LLM provider. Note: This feature is currently in beta and may have limitations.
- `llm_provider`: Select the LLM provider for summarization (only applicable when `type` is set to `summary`):
  - `openai`: Uses OpenAI's API for summarization.
  - `gemini`: Uses Google's Gemini API for summarization.

**Note**: Using the `summary` option requires an API key for the chosen provider. Set this as an environment variable for security.

> **Note**: The `summary` option is currently in BETA. If you experience any issues, please revert to the `abstract` type and report the problem on our GitHub issues page.

### Notifier Settings

```yaml
notifier:
  email:
    to: "your_email@example.com"
    from: "sender_email@example.com"
    password: "YOUR_PASSWORD_HERE"
    smtp_server: "smtp.example.com"
    smtp_port: 587  # 465 | 587
    sort_order: alphabetical  # alphabetical | publication_time | relevance
```

Replace these values with your email settings:
- `to`: Your email address where you want to receive notifications.
- `from`: The email address sending the notifications (often the same as `to`).
- `password`: The password for the sender email account.
- `smtp_server` and `smtp_port`: These depend on your email provider. Common examples:
  - Gmail: `smtp.gmail.com`, port 587
  - Yahoo: `smtp.mail.yahoo.com`, port 587
  - Outlook: `smtp-mail.outlook.com`, port 587
- `sort_order`: Determines how papers are sorted in the notification email.

### Logging Settings

```yaml
logging:
  level: INFO  # DEBUG | INFO | WARNING | ERROR
  file: paperweight.log
```

- `level`: Set the logging level:
  - `DEBUG`: Detailed information, typically useful for debugging.
  - `INFO`: General information about program execution.
  - `WARNING`: Indicates potential issues that don't prevent the program from working.
  - `ERROR`: Serious issues that cause the program to fail in performing some functions.
- `file`: Specifies the log file name. This uses a relative path from the project's root directory.

For detailed debugging, set the level to DEBUG. For normal operation, INFO is recommended.

## Additional Notes

- The system processes multiple arXiv categories sequentially.
- Paper ranking in the final output is based on the specified `sort_order`:
  - `alphabetical`: Papers are sorted alphabetically by title.
  - `publication_time`: Papers are sorted by their publication date, most recent first.
  - `relevance`: Papers are sorted by their relevance scores, highest first (default if not specified).
- When using LLM providers for summarization, ensure you have the necessary API keys set up as environment variables.

## Troubleshooting

If you encounter issues with your configuration:
1. Double-check all required fields are filled out correctly.
2. Ensure your email settings are correct, especially if using 2-factor authentication.
3. Verify your API keys are correctly set as environment variables when using LLM summarization.
4. Check the log file for any error messages.

For more general troubleshooting and frequently asked questions, please refer to the [FAQ](FAQ.md).