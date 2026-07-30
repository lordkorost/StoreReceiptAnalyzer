# Advanced Local Server Installation

## 1.Introduction

This guide describes the setup of a local/LAN server installation hosting multiple Django web applications, managed via Nginx, systemd, and HTTPS.

The goal is to have a **single entry point**:

```text
https://SERVER_IP
```
This entry point displays a central menu from which all installed services can be reached.
Example:
```text
https://192.168.1.11
        |
        +-- Webapp1
        |
        +-- StoreReceiptAnalyzer
        |
        +-- Webapp2
```

## 2. Architecture

The configuration utilizes the following stack:

- Nginx: HTTPS reverse proxy
- Gunicorn: WSGI server for standard Django applications
- Daphne: ASGI/WebSocket server for real-time Django applications
- Systemd: Automatic service management and boot startup
- UFW: LAN firewall restrictions
- Local SSL Certificates: For HTTPS encryption

Architecture Diagram:
```text
Client LAN
    |
    v
Nginx (HTTPS Reverse Proxy)
    |
    +-------------------------+
    |                         |
    v                         v
Webapp1                StoreReceiptAnalyzer
(Gunicorn :8000)        (Daphne :8001)
```

## 3. System Prerequisites
Before configuring the application, ensure the server has the required system packages installed.
> [!NOTE]
> This guide assumes an Ubuntu/Debian-based system.

```bash
# Update package list
sudo apt update

# Install Python tools, Redis, Nginx, and Firewall
sudo apt install python3-venv python3-pip python3-dev redis-server nginx ufw build-essential

# Enable and start Redis (required for websocket updates)
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

## 4. Application Setup
Perform these steps for each Django application (e.g. StoreReceiptAnalyzer).

### 4.1 Clone and Prepare Environment
> [!NOTE]
> Replace <YOUR_USER> with your actual Linux username 

```bash
# Navigate to your preferred installation directory
cd /home/<YOUR_USER>/

# Clone the repository
git clone https://github.com/lordkorost/StoreReceiptAnalyzer.git
cd StoreReceiptAnalyzer

# Create and activate the virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 4.2 Install Dependencies and Package
This step installs external requirements and registers the application's entry points (like the as-worker command) defined in pyproject.toml.

```bash
# Install standard requirements
pip install -r requirements.txt

# Install the project itself in editable mode (generates 'as-worker' executable)
pip install  .
```


## 5. Configure the Environment

Copy the example configuration file:

```bash
cp .env.advanced.example .env
```

Open the file:

```bash
nano .env
```

The most important variables are:

### Django

Generate a secure Django secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Example configuration:

```env
SECRET_KEY=your-generated-secret-key

DEBUG=False

ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.11

CSRF_TRUSTED_ORIGINS=https://192.168.1.11:81

AS_HOST=localhost
AS_PORT=8001

SERVE_MEDIA=False
# MEDIA_PATH=/path/to/media
```
> [!NOTE]
> AS_PORT is the internal Daphne port. It does not need to match the HTTPS port exposed by Nginx.

### HTTPS configuration

When using HTTPS through Nginx, Django must trust the public URL used to access the application.

For example:

```env
CSRF_TRUSTED_ORIGINS=https://192.168.1.11:81
```
> [!NOTE]
> If the application is exposed on another address or port, update this value accordingly.


### PostgreSQL

Django requires a dedicated database and user. Follow these steps to create them securely.

> [!IMPORTANT]
> Ensure PostgreSQL is installed on your system (`sudo apt install postgresql postgresql-contrib`) before proceeding.

**1. Access the PostgreSQL shell:**
```bash
sudo -u postgres psql
```
**2. Create the database and user:**
Run the following SQL commands inside the psql prompt. Replace 'your-secure-password' with a strong, unique password.
```bash
CREATE DATABASE storereceiptanalyzer_db;
CREATE USER storereceiptanalyzer_user WITH PASSWORD 'your-secure-password';

-- Optimize settings for Django
ALTER ROLE storereceiptanalyzer_user SET client_encoding TO 'utf8';
ALTER ROLE storereceiptanalyzer_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE storereceiptanalyzer_user SET timezone TO 'UTC';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE storereceiptanalyzer_db TO storereceiptanalyzer_user;

-- Exit the prompt
\q
```

**3. Configure the .env file:**

Open your .env file and update the database connection settings to match what you just created:

```env
DB_NAME=storereceiptanalyzer_db
DB_USER=storereceiptanalyzer_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432
```

### Ollama

If Ollama is running on another machine:

```env
OLLAMA_HOST=http://192.168.1.50:11434
```

The Ollama server must be reachable from this machine.

> [!NOTE]
> If Ollama runs on another machine, it must listen on a network interface instead of localhost.

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Redis

```env
REDIS_URL=redis://localhost:6379/0
```

### Media

When using Nginx to serve uploaded files:

```env
SERVE_MEDIA=False
```


## 6. Run database migrations

```bash
# Apply migrations to the database
python manage.py migrate

# Collect static files for Nginx to serve
python manage.py collectstatic 
```




## 7. Port Management

Each application uses a dedicated HTTPS port.
| HTTPS Port | Service | Description |
|------------|---------|-------------|
| 443 | Home | Landing page |
| 81 | StoreReceiptAnalyzer | Django ASGI |
| 82 | Webapp1 | Django WSGI |
| 83 | Reserved | Future application |


## 8. Nginx Configuration
Nginx configurations are split into available and enabled sites:

```text
/etc/nginx/
├── sites-available/
│   ├── storereceiptanalyzer
│   ├── webapp1
│   └── home
└── sites-enabled/
    └── (symlinks to active configurations)
```

Each application has its own configuration file in sites-available/ and is activated via a symlink in sites-enabled/.

## Reverse Proxy Setup

One Nginx configuration file should be created for each hosted application.

StoreReceiptAnalyzer
- Nginx listens on https://SERVER_IP:81 and forwards traffic to Daphne.

```nginx
# Inside /etc/nginx/sites-available/storereceiptanalyzer example
server {
    listen 81 ssl;

    ssl_certificate /etc/nginx/ssl/storereceiptanalyzer.crt;
    ssl_certificate_key /etc/nginx/ssl/storereceiptanalyzer.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location /static/ {
        alias /home/user/StoreReceiptAnalyzer/src/analizzascontrini/webui/static/;
    }

    location /media/ {
        alias /home/user/StoreReceiptAnalyzer/src/analizzascontrini/webui/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 20M;

    access_log /var/log/nginx/storereceiptanalyzer_access.log;
    error_log /var/log/nginx/storereceiptanalyzer_error.log;
}
```

Daphne handles: Django ASGI, WebSockets, and real-time notifications.

Webapp1
Nginx listens on https://SERVER_IP:82 and forwards traffic to Gunicorn.

```nginx
server {
    listen 82 ssl;

    server_name _;

    ssl_certificate /etc/nginx/ssl/myspese.crt;
    ssl_certificate_key /etc/nginx/ssl/myspese.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root /home/user/django;

    location /static/ {
        alias /home/user/django/staticfiles/;
    }

    location /media/ {
        alias /mnt/myremotemnt/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 20M;

    access_log /var/log/nginx/myspese_access.log;
    error_log /var/log/nginx/myspese_error.log;
}
```


## Systemd Services
Services are configured to start automatically at boot.
Check status:

```bash
sudo systemctl status storereceiptanalyzer-web
sudo systemctl status as-worker
sudo systemctl status webapp1-gunicorn
```

### Enable a service:
```bash
sudo systemctl enable <service-name>
```
### Start a service:
```bash
sudo systemctl start <service-name>
```

### Restart a service:
```bash
sudo systemctl restart <service-name>
```

## StoreReceiptAnalyzer Worker
The background worker runs as a separate systemd service: as-worker.service.
It reads its configuration from the .env file.
Example .env entry:

```env
OLLAMA_HOST=http://SERVER_IP:11434
```

Note: After modifying the .env file, you must restart the worker:
```bash 
sudo systemctl restart as-worker
```
## UFW Firewall
The server uses a restrictive firewall policy: Default: deny incoming.
Only necessary LAN ports are allowed. Example configuration for a 192.168.1.x network:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 443
sudo ufw allow from 192.168.1.0/24 to any port 81
sudo ufw allow from 192.168.1.0/24 to any port 82
sudo ufw enable
```

Adjust the subnet if your LAN uses a different address range.

## Landing Page
The landing page is served directly by Nginx as static HTML.

    File path: /var/www/home/index.html
    URL: https://SERVER_IP

This page contains direct links to Webapp1, StoreReceiptAnalyzer, and any future services.

### SSL Certificates
Certificates are stored locally in:

```text
/etc/nginx/ssl/
```

Example files:

- storereceiptanalyzer.crt
- storereceiptanalyzer.key

Warning: Since these are local LAN certificates (self-signed or local CA), browsers will require manual acceptance of the security exception on the first visit.
Self-signed certificates are sufficient for LAN deployments.

# Systemd service

## as-worker.service

```ini
# /etc/systemd/system/as-worker.service
[Unit]
Description=StoreReceiptAnalyzer Worker
After=network.target

[Service]
User=myuser
Group=myuser

WorkingDirectory=/home/user/StoreReceiptAnalyzer

Environment="PATH=/home/user/StoreReceiptAnalyzer/venv/bin:/usr/bin"

ExecStart=/home/user/StoreReceiptAnalyzer/venv/bin/as-worker

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## storereceiptanalyzer-web.service

```ini
# /etc/systemd/system/storereceiptanalyzer-web.service
[Unit]
Description=StoreReceiptAnalyzer Web
After=network.target

[Service]
User=myuser
Group=myuser

WorkingDirectory=/home/myuser/StoreReceiptAnalyzer/src/analizzascontrini/webui

Environment="PATH=/home/myuser/StoreReceiptAnalyzer/venv/bin:/usr/bin"

ExecStart=/home/myuser/StoreReceiptAnalyzer/venv/bin/daphne \
    -b 127.0.0.1 \
    -p 8001 \
    core.asgi:application

Restart=always

[Install]
WantedBy=multi-user.target
```

# Troubleshooting

## Nginx Issues

### Test configuration syntax:

```bash
sudo nginx -t
```

### Reload Nginx (applies changes without downtime):


```bash
sudo systemctl reload nginx
```

### Check logs

```bash
sudo journalctl -u storereceiptanalyzer-web -f
sudo journalctl -u as-worker -f
```

### Check open ports:

```bash
sudo ss -tlnp | grep nginx
```

## Application Testing

Verify the endpoints are responding (using -k to ignore self-signed cert warnings):

```bash
# Test StoreReceiptAnalyzer
curl -k -I https://SERVER_IP:81

# Test webapp1
curl -k -I https://SERVER_IP:82
```

## WebSocket Not Working
If real-time features fail, verify the following checklist:

- Daphne service is active (systemctl status ...).
- The internal port (8001) is correct and not blocked.
- Nginx configuration includes the Upgrade and Connection headers for WebSockets.
- UFW is not blocking internal loopback traffic (it shouldn't by default).

## Adding a New Application
To add a new service to this ecosystem, follow these steps:

- Create a new systemd service file.
- Start the backend application on a dedicated local port (e.g., 8002).
- Create a new Nginx configuration file in sites-available/.
- Assign a new external HTTPS port (e.g., 83).
- Open the new port in UFW for the LAN subnet.
- Add a new button/link to the /var/www/home/index.html menu.


Example for "webapp2":

    HTTPS Port: 83
    Backend Target: 127.0.0.1:8002

## Final Result
This architecture provides:

- isolated applications
- automatic startup
- HTTPS access
- easy scalability
- centralized entry point
- LAN-only deployment

