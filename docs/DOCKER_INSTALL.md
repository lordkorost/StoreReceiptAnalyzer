# Docker Installation

This installation method runs StoreReceiptAnalyzer using Docker Compose.

The Docker setup includes:

- Django WebUI
- Background Worker
- PostgreSQL database
- Redis service

Ollama is **not included in Docker** and must run separately on the host machine or another reachable machine in the network.

---

# 1. Clone the repository

Clone the project:

```bash
git clone https://github.com/lordkorost/StoreReceiptAnalyzer.git

cd StoreReceiptAnalyzer
```
Copy the Docker environment file:
```bash
cp .env.docker.example .env.docker
```

Edit .env.docker and configure your settings.

After completing the configuration, copy it as the active environment file:

```bash
cp .env.docker .env
```

# 2. Configure Docker environment variables

Some variables must keep specific values because they refer to Docker Compose services.

Docker internal services

The following variables must not be changed:

```env
AS_HOST=web
DB_HOST=db
REDIS_URL=redis://redis:6379/0
```

These values refer to Docker Compose service names:

| Variable | Value | Description |
|----------|-------|-------------|
| `AS_HOST` | `web` | Django WebUI container name |
| `DB_HOST` | `db` | PostgreSQL container name |
| `REDIS_URL` | `redis://redis:6379/0` | Redis container address |

Do not replace them with:

```env
AS_HOST=localhost
DB_HOST=localhost
REDIS_URL=redis://localhost:6379/0
```

Inside Docker, localhost refers to the current container, not another service.

# 3. Ollama configuration

Ollama runs outside Docker.

The Docker containers must connect to the Ollama server through the network.

Configure the Ollama address:
```env
OLLAMA_HOST=http://192.168.1.50:11434
```
Replace the IP address with the address of your Ollama machine.

Do not use:
```env
OLLAMA_HOST=http://localhost:11434
```
because Ollama is not running inside the Docker container.

The Ollama server must listen on network interfaces accessible by Docker.

Example:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```
or configure your system service with:

```bash
OLLAMA_HOST=0.0.0.0
```
StoreReceiptAnalyzer includes an automatic Ollama connection checker in the WebUI.

# 4. Django configuration
Allowed hosts

For Docker installations, keep the Docker WebUI hostname:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,web
```

The value web is required because it is the internal Docker Compose hostname used by Django.

WebUI port

By default, StoreReceiptAnalyzer exposes the WebUI on port 8000.

The port can be changed using:

```env
AS_PORT=8000
```
Example:

```env
AS_PORT=8080
```
This changes the exposed WebUI port.

Media serving

When running without a reverse proxy, keep:
```env
SERVE_MEDIA=True
```

This allows Django to serve uploaded files directly.

If StoreReceiptAnalyzer is placed behind Nginx or another reverse proxy, media handling can be configured differently.

# 5. Start Docker containers

Build and start all services:

```bash
docker compose --env-file .env.docker up --build
```

The first startup will:

create Docker containers
create the PostgreSQL database volume
start Redis
apply Django migrations
collect static files
start the WebUI
start the background worker

# 6. Run in background

To start containers in detached mode:

```bash
docker compose --env-file .env.docker up --build -d
```

Check running containers:

```bash
docker compose ps
```
View logs:
```bash
docker compose logs -f
```

# 7. Access the application

Open your browser:

```bash
http://localhost:8000
```

If you changed AS_PORT:

```bash
http://localhost:<your-port>
```

Example:

```bash
http://localhost:8080
```

# 8. Updating Docker installation

To update an existing installation:

```bash
git pull
```

Then rebuild the containers:

```bash
docker compose --env-file .env.docker up --build
```

If database migrations are included, they will be applied automatically during startup.

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
chmod 600 .env.docker
```
Make sure that the user running Docker Compose can still read the file.