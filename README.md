# StoreReceiptAnalyzer

A self-hosted, local AI-powered platform designed to transform shopping receipts into structured expense data while keeping your financial information under your control.

[![Privacy First](https://img.shields.io/badge/Privacy-Local%2FSelf--Hosted-success?style=flat-square)](docs/ADVANCED_INSTALL.md)
[![Docker Supported](https://img.shields.io/badge/Docker-Ready-blue?style=flat-square)](docs/DOCKER_INSTALL.md)
[![Ollama](https://img.shields.io/badge/AI-Ollama-orange?style=flat-square)](https://ollama.com)

---

## Key Features

* **📄 Receipt Processing:** Upload and manage receipts via web interface.
* **🔍 Local OCR:** Text extraction powered by vision AI models.
* **🤖 Smart Extraction:** LLM-driven parsing for products, prices, and discounts.
* **🧠 Memory & Categories:** Automatic product name learning and categorization.
* **✏️ Manual Review:** Streamlined workflow to correct any errors.
* **⚡ Live Updates:** Real-time notifications via WebSockets (Django Channels + Redis).
* **🔒 100% Privacy:** Local-first architecture; no data sent to external clouds.
* **🖥️ Hardware Flexibility:** Support for local or remote Ollama servers over your LAN.

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

The project consists of two main components communicating via **Redis** and **WebSockets**:

| Component | Main Role |
| :--- | :--- |
| **Django Web Interface** | Receipt management, authentication, AI configuration, and review interface. |
| **Background Worker** | Execution of asynchronous operations (OCR, parsing, and AI analysis). |

---

## AI Models (Ollama)

Runs entirely on local models via [Ollama](https://ollama.com). You can run them on the same machine or another computer on your network across four key roles:
1. **Vision OCR** (to read the image)
2. **Analysis** (to extract products datas from the normalized ocr)
3. **Categorization** (to assign categories)
4. **Chat** (to interact with the AI to help with regex in store templates)

---

## Installation

Choose the method that best fits your setup:

| Method | Description | Reference Guide |
| :--- | :--- | :--- |
| **Docker** *(Recommended)* | Includes WebUI, Worker, PostgreSQL, and Redis. | [📖 Docker Guide](docs/DOCKER_INSTALL.md) |
| **Manual** | Run directly on your system without Docker. | [📖 Manual Guide](docs/MANUAL_INSTALL.md) |
| **Advanced** | Advanced local server setup with Nginx, SSL, Systemd, and LAN. | [📖 Advanced Guide](docs/ADVANCED_INSTALL.md) |

---

## Notes & Limitations

* **Receipt normalization** templates are currently optimized and tested with Italian supermarket receipts.
* **OCR correction** rules are based on Italian receipt layouts and abbreviations
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

## 🛡️ Privacy

StoreReceiptAnalyzer is built with a **local-first** philosophy: your receipt images and financial data never leave your devices, relying solely on the hardware you own.