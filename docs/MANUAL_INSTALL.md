# Manual Installation

This guide explains how to install and run **StoreReceiptAnalyzer** directly on your system without Docker.

This installation method is recommended for users who want full control over the environment, services, and hardware resources.

---

# Requirements

Before installing StoreReceiptAnalyzer, make sure the following components are available:

* Python 3.12+
* PostgreSQL
* Redis
* Ollama

Recommended operating systems:

* Ubuntu 22.04+
* Debian-based distributions

---

# 1. Clone the repository

Clone the repository:

```bash
git clone https://github.com/lordkorost/StoreReceiptAnalyzer.git

cd StoreReceiptAnalyzer
```

Copy the example environment file:

```bash
cp .env.example .env
```

Edit the `.env` file:

```bash
nano .env
```

---

# 2. Configure environment variables

## Django configuration

Generate a secure Django secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Add the generated value:

```env
SECRET_KEY="your-generated-secret-key"
```

By default, StoreReceiptAnalyzer runs the Django WebUI on port `8000`.

The port can be changed using the `AS_PORT` environment variable:

```env
AS_PORT=8000
```
---

# Database configuration

StoreReceiptAnalyzer requires PostgreSQL.

Example configuration:

```env
DB_NAME=storereceiptanalyzer_db
DB_USER=storereceiptanalyzer_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432
```

Create the database and user:

```sql
CREATE USER storereceiptanalyzer_user WITH PASSWORD 'your_database_password';

CREATE DATABASE storereceiptanalyzer_db
OWNER storereceiptanalyzer_user;
```

The PostgreSQL user does not require administrator privileges.

---

# Redis configuration

Redis is used for background tasks and real-time communication.

Example:

```env
REDIS_URL=redis://localhost:6379/0
```

---

# Ollama configuration

StoreReceiptAnalyzer uses Ollama for local AI processing.

Default configuration:

```env
OLLAMA_HOST=http://localhost:11434
```

If Ollama is running on another machine:

```env
OLLAMA_HOST=http://192.168.1.50:11434
```

The Ollama server must be reachable from the machine running StoreReceiptAnalyzer.

---

# 3. Run the installer

Run:

```bash
./install.sh
```

The installer will:

* create the Python virtual environment
* install Python dependencies
* validate environment configuration
* check PostgreSQL connection
* check Redis connection
* check Ollama connection
* run Django migrations
* collect static files

At the end, a successful installation should show:

```
INSTALLATION COMPLETED
```

---

# 4. Start StoreReceiptAnalyzer

StoreReceiptAnalyzer can be started in different modes.

## Start WebUI and Worker

Recommended mode:

```bash
./run.sh
```

This starts:

* Django Web Interface
* Background Worker

---

## Start only WebUI

```bash
./run.sh -webui
```

Starts only the Django application.

---

## Start only Worker

```bash
./run.sh -worker
```

Starts only the background processing service.

---

# 5. Access the application

After startup, open:

```
http://localhost:8000
```

The first startup may redirect to the initial setup page.

---

# Background processing

Receipt analysis is performed asynchronously.

The workflow is:

```
Upload receipt
      |
      v
Django creates task
      |
      v
Worker processes receipt
      |
      v
OCR + AI analysis
      |
      v
Results saved
      |
      v
Live updates through WebSocket
```

The worker continues processing tasks independently from the web interface.

---

# Updating an existing installation

To update StoreReceiptAnalyzer:

```bash
git pull
```

If dependencies or database models changed, run:

```bash
./install.sh
```

Then restart the services.

---

# Italian receipt support

The current OCR normalization system is optimized for Italian receipts.

Current limitations:

* store templates are mainly designed for Italian supermarkets
* normalization rules target Italian receipt formats
* default categories are based on Italian shopping habits
* prompts and examples are currently optimized for Italian language data

The architecture is designed to support other countries and receipt formats in the future by adding new store templates and normalization rules.

---

# Troubleshooting

If the installation fails, check the service logs and verify that the required external services are running.

## Check Ollama connection

Example:

```bash
curl http://localhost:11434/api/tags
```

Ollama must be reachable from the machine running StoreReceiptAnalyzer.

---

## Check Redis

Verify that Redis is running:

```bash
redis-cli ping
```

Expected result:

```text
PONG
```

---

## Check Django configuration

Activate the virtual environment:

```bash
source venv/bin/activate
```

Run:

```bash
python manage.py check
```

---



## Environment file security

Environment files contain sensitive information such as:

- Django secret key
- database credentials
- service addresses
- AI configuration

For security reasons, `.env` files should not be readable by unrelated users on the system.

You can restrict permissions with:

```bash
chmod 600 .env
```

However, make sure that the user running StoreReceiptAnalyzer services (Django WebUI and Worker) still has permission to read the file.

If Django or the Worker run under a different system user (for example through systemd), adjust ownership or permissions accordingly.

---

For advanced deployments using Nginx, HTTPS certificates, systemd services, reverse proxy configuration, and LAN access, see:

`ANDVANCED_INSTALL.md`
