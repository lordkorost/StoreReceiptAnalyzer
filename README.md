# StoreReceiptAnalyzer

StoreReceiptAnalyzer is a self-hosted, local AI-powered platform that transforms shopping receipts into structured expense data while keeping your financial information private and fully under your control.

It combines OCR, deterministic normalization, and local LLMs to extract structured shopping data from receipt images.

---

## Key Features

* **Receipt Processing**  Upload and manage shopping receipts through a simple web interface.

* **Local OCR**  Extract text using local vision AI models.

* **Smart Data Extraction**  Automatically identify products, quantities, prices, discounts, and totals using LLMs.

* **Product Memory & Categorization**  Learn product names over time and automatically categorize future purchases.

* **Manual Review**  Review and correct extracted information before saving it.

* **Real-Time Progress**  Track long-running tasks with live updates powered by Django Channels and Redis.

* **Privacy by Design**  Receipt images and financial data remain under your control with local AI processing.

* **Flexible AI Deployment**  Connect to a local or remote Ollama server running on your private network.

---

## How It Works
```
The system combines deterministic rules with AI models to ensure maximum reliability:
[ Receipt Image ]
│
▼
[ Vision OCR & Normalization ]
│
▼
[ LLM Structured Extraction ]
│
▼
[ User Review & AI Categorization ]
│
▼
[ User Review & Final Expense Data ]
```

---

##  Architecture

The project is composed of two main components:

| Component | Main Role |
| :--- | :--- |
| **Django Web Interface** | Receipt management, authentication, AI configuration, and review interface. |
| **Background Worker** | Execution of asynchronous operations (OCR, parsing, and AI analysis). |

---

## AI Models (Ollama)

StoreReceiptAnalyzer uses local AI models through [Ollama](https://ollama.com). You can run them on the same machine or another computer on your network across four key roles:
1. **Vision OCR** (to read the image)
2. **Analysis** (to extract products data from the normalized OCR)
3. **Categorization** (to assign categories)
4. **Chat** (to interact with the AI to help with regex in store templates)

---

## Installation

Choose the method that best fits your setup:

| Method | Description | Guide |
| :--- | :--- | :--- |
| **Docker** *(Recommended)* | Includes WebUI, Worker, PostgreSQL, and Redis. | [ Docker Guide](docs/DOCKER_INSTALL.md) |
| **Manual** | Run directly on your system without Docker. | [ Manual Guide](docs/MANUAL_INSTALL.md) |
| **Advanced** | Advanced local server setup with Nginx, HTTPS, Systemd, and LAN access. | [ Advanced Guide](docs/ADVANCED_INSTALL.md) |

---

## Notes & Limitations

* **Receipt normalization** templates are currently optimized and tested for Italian supermarket receipts.
* **OCR normalization** rules are based on Italian receipt layouts and abbreviations
* **Default prompts** and **product categories** are in Italian
* **The application architecture** is designed to support additional countries and receipt formats in the future through configurable store templates.
* **Languages:** The user interface supports both English and Italian.


---

## Project Status

StoreReceiptAnalyzer is actively developed.

Planned improvements:

- More generic receipt formats
- Additional languages
- Improved recovery workflows
- More automated template generation
- Additional AI processing improvements

---

## Privacy

StoreReceiptAnalyzer is built with a **local-first** philosophy: your receipt images and financial data remain under your control and are processed using hardware you own.
