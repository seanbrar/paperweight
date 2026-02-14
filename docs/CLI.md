# CLI modes and ergonomics

This document defines the intended behavior of the paperweight CLI.

## Commands

`paperweight` defaults to `paperweight run` for backwards compatibility.

1. `paperweight run`
2. `paperweight init`
3. `paperweight doctor`

## `run` mode

Purpose: fetch, triage, process, and deliver a digest.

Options:

- `--config PATH`: config file path (`config.yaml` default)
- `--force-refresh`: ignore watermark and fetch recent window
- `--delivery stdout|atom|email`: output adapter (`stdout` default)
- `--output PATH`: write stdout/atom output to file
- `--sort-order relevance|alphabetical|publication_time`

Expected outputs:

- `stdout`: deterministic plain text digest
- `atom`: Atom XML feed content
- `email`: sends email if notifier config is present

Failure behavior:

- returns non-zero exit code on config/network/runtime errors
- email mode fails fast if notifier config is missing

## `init` mode

Purpose: bootstrap a minimal usable config quickly.

Options:

- `--config PATH`: destination path (`config.yaml` default)
- `--force`: overwrite existing file

Expected output:

- writes config file and prints written path
- fails if file exists and `--force` is not provided

## `doctor` mode

Purpose: fast local diagnostics without running the full pipeline.

Options:

- `--config PATH`: config file path (`config.yaml` default)

Checks:

- config file existence
- config parse/validation
- triage provider key availability
- delivery mode availability (`stdout`, `atom`, optional `email`)

Expected output:

- line-based status report with `OK`, `WARN`, or `FAIL`
- non-zero exit code only on hard failures (missing/invalid config)

## API key requirements

- API keys are not required for all modes.
- `init` and `doctor` work without provider keys.
- `run` can operate without keys if triage/analyzer paths fall back to non-LLM behavior.
