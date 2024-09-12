# paperweight environment variables guide

paperweight offers a flexible system for managing configuration and sensitive information, balancing ease of use with security. This guide will walk you through the various methods and best practices.

## 1. Configuration File (config.yaml)

The primary configuration is stored in `config.yaml`. This file can contain all your settings, including non-sensitive information and placeholders for sensitive data.

```yaml
arxiv:
  max_results: 100
notifier:
  email:
    password: ${EMAIL_PASSWORD}
```

> 🔒 **Security Note**: Never commit `config.yaml` to version control if it contains real credentials.

## 2. Environment Variables

Environment variables can be used in two ways:

a) Direct reference in config.yaml:
   Use `${VARIABLE_NAME}` syntax in your config file to reference environment variables:

   ```yaml
   notifier:
     email:
       password: ${EMAIL_PASSWORD}
   ```

b) Overriding config values:
   Set environment variables with the prefix `PAPERWEIGHT_` to override any config value:

   ```bash
   export PAPERWEIGHT_ARXIV_MAX_RESULTS=200
   ```

> ⚠️ **Important**: Environment variables take precedence over values in `config.yaml`.

## 3. .env File

For local development and managing API keys, you can use a `.env` file:

1. Create a file named `.env` in the root directory of the paperweight project.
2. Add your API keys and other sensitive information:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   EMAIL_PASSWORD=your_email_password_here
   ```

> 🔒 **Security Note**: Never commit your `.env` file to version control.

## 4. API Keys

API keys require special handling:

- If using the 'summary' analyzer type, you must provide an API key for the specified LLM provider.
- You can set the API key in `config.yaml`, in the `.env` file, or as an environment variable.

The order of precedence is: environment variable > `.env` file > `config.yaml`.

> 🔄 **Best Practice**: Regularly rotate your API keys and passwords.

## 5. Type Conversion

Configuration values are automatically converted to the appropriate type:

- Boolean values: 'true', '1', 'yes' (case-insensitive) are converted to `True`, others to `False`.
- Integer and float values are converted accordingly.

## 6. Example Usage

Here's how all these elements come together:

1. In your `config.yaml`:
   ```yaml
   arxiv:
     max_results: 100
   notifier:
     email:
       password: ${EMAIL_PASSWORD}
   analyzer:
     type: summary
     llm_provider: openai
   ```

2. In your `.env` file:
   ```
   OPENAI_API_KEY=your_actual_api_key_here
   EMAIL_PASSWORD=your_actual_email_password
   ```

3. To override a config value:
   ```bash
   export PAPERWEIGHT_ARXIV_MAX_RESULTS=200
   ```

4. Run paperweight:
   ```bash
   paperweight
   ```

This system will combine all these sources to create the final configuration, prioritizing in this order: environment variables > `.env` file > `config.yaml`.

## Security Summary

- Use environment variables for the most sensitive information, especially in production environments.
- Never commit `config.yaml` or `.env` files containing real credentials to version control.
- Regularly rotate your API keys and passwords.
- For personal use on a private machine, storing non-sensitive config in `config.yaml` and sensitive data in `.env` might be acceptable.
- For shared or production environments, using environment variables is strongly recommended.

Remember, the method you choose depends on your specific needs and security requirements. Always prioritize the security of sensitive information.