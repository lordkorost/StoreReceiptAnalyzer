# Security Policy

## Privacy & Local-First Architecture

StoreReceiptAnalyzer is designed with a strict **local-first** approach.

- **No telemetry:** The application does not collect analytics, usage statistics, or telemetry data. It only performs an optional GitHub version check to notify users when a new release is available.
- **No external cloud processing:** Receipt images, extracted text, and financial data are never sent to external cloud AI services by StoreReceiptAnalyzer.
- **Local AI:** AI processing is performed using Ollama, allowing all models to run on your own hardware.

## Network & Ollama Configuration

By default, StoreReceiptAnalyzer is intended to connect to a local Ollama instance or one running within your private network.

The application also supports connecting to a remote Ollama server through the `OLLAMA_HOST` setting in the `.env` file.

The security of a remote Ollama server, including network exposure, authentication, firewall configuration, and access control, is the responsibility of the system administrator.

---

## Reporting a Vulnerability

If you discover a security vulnerability in StoreReceiptAnalyzer, please report it responsibly.

- **Do not** open a public GitHub issue for sensitive security vulnerabilities.
- Instead, contact the maintainer directly or use GitHub Security Advisories if they are enabled for this repository.

Thank you for helping keep StoreReceiptAnalyzer secure.
