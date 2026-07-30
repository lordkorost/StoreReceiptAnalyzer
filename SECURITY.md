# Security Policy

## Privacy & Local-First Architecture

StoreReceiptAnalyzer is designed with a strict **local-first** approach:
* **No Telemetry:** The application does not collect analytics, track usage, or send telemetry data. (It only periodically checks the GitHub repository to verify if a new version is available).
* **No External Cloud:** Receipt images, text, and parsed financial data are never sent to external cloud services.
* **Local AI:** All processing relies on local AI models via Ollama. 

### Network & Ollama Configuration
While the application defaults to running Ollama locally or within your private **LAN**, it technically supports connecting to a remote Ollama instance via `OLLAMA_HOST` in `.env`.

---

## Reporting a Vulnerability

If you discover a security vulnerability within StoreReceiptAnalyzer, please report it responsibly:

* **Do not** open a public GitHub issue for sensitive security vulnerabilities.
* Instead, please contact the maintainer directly or open a private advisory via GitHub Security Advisories if available.

We appreciate your help in keeping the project secure!
