## Configuration

**Important:** Keep your `config.yaml` file secure, especially if it contains sensitive information like email passwords. Consider using environment variables for sensitive data instead of storing them directly in the configuration file.

The project uses a YAML configuration file to customize its behavior. Follow these steps to set up your configuration:

1. Locate the `config-base.yaml` file in the project directory.
2. Make a copy of this file and rename it to `config.yaml`.
3. Open `config.yaml` in a text editor and modify the values according to your preferences.

Here's a breakdown of the configuration options:

### ArXiv Settings

   ```yaml
   arxiv:
     categories:
       - category1
       - category2
       - category3
     max_results: 100
   ```

Replace `category1`, `category2`, etc., with the arXiv categories you're interested in. For example:
- `cs.AI` (Artificial Intelligence)
- `cs.CL` (Computation and Language)
- `cs.LG` (Machine Learning)

You can find a full list of arXiv categories [here](https://arxiv.org/category_taxonomy).

The `max_results` option specifies the maximum number of papers to fetch for each category. Adjust this value based on your needs and to manage API request limits.

### Processor Settings

   ```yaml
   processor:
     keywords:
       - keyword1
       - keyword2
       - keyword3
       - keyword4
       - keyword5
     exclusion_keywords:
       - exclude1
       - exclude2
       - exclude3
     important_words:
       - important1
       - important2
       - important3
     title_keyword_weight: 3
     abstract_keyword_weight: 2
     content_keyword_weight: 1
     exclusion_keyword_penalty: 5
     important_words_weight: 0.5
     min_score: 10
   ```

- `keywords`: List of terms you're interested in. Papers containing these will be scored higher.
- `exclusion_keywords`: Papers containing these terms will be penalized.
- `important_words`: Special words that, if present, will boost a paper's score.
- `*_weight` and `*_penalty`: Adjust these to fine-tune the scoring algorithm.
- `min_score`: Papers must score at least this value to be included in notifications.

### Analyzer Settings

   ```yaml
   analyzer:
     type: abstract  # abstract | summary
     llm_provider: openai  # gemini | openai
   ```

- `type`: Choose between `abstract` (use the paper's abstract) or `summary` (generate a summary).
- `llm_provider`: Select the LLM provider for summarization (`openai` or `gemini`).

**Note**: For LLM use, please create a .env and provide your own API keys for OpenAI or Gemini.

### Notifier Settings

   ```yaml
   notifier:
     email:
       to: "your_email@example.com"
       from: "sender_email@example.com"
       password: "YOUR_PASSWORD_HERE"
       smtp_server: "smtp.example.com"
       smtp_port: 587  # 465 | 587
   ```

Replace these values with your email settings:
- `to`: Your email address where you want to receive notifications.
- `from`: The email address sending the notifications (often the same as `to`).
- `password`: The password for the sender email account.
- `smtp_server` and `smtp_port`: These depend on your email provider. Common examples:
  - Gmail: `smtp.gmail.com`, port 587
  - Yahoo: `smtp.mail.yahoo.com`, port 587
  - Outlook: `smtp-mail.outlook.com`, port 587

**Note**: For security, consider using environment variables or a secure method to store your email password instead of putting it directly in the config file.

### Logging Settings

   ```yaml
   logging:
     level: INFO  # DEBUG | INFO | WARNING | ERROR
     file: app.log  # app.log | /path/to/logfile.log
   ```

- `level`: Set the logging level (DEBUG, INFO, WARNING, or ERROR).
- `file`: Specify the log file name or path.