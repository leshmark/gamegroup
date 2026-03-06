# README
## Purpose
This project appears as a simple game group management system built using Brython, FastAPI, and PostgreSQL. The actual intention is to provide a reference/sample implementation for a properly formed web application using these technologies, and to demonstrate secure, scalable practices in application development.

## Technologies Used
- **Brython**: A Python 3 implementation for client-side web programming, allowing developers to write Python code that runs in the browser.
- **FastAPI**: A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.
- **PostgreSQL**: A powerful, open-source object-relational database system known for its robustness, extensibility, and standards compliance.

## Features

### Authentication & Authorization
- **Passwordless Email Authentication**: Magic link-based login system
- **Three-tier Authorization**: Viewer, Contributor, and Admin roles with inheritance
- **JWT Token Management**: Secure token-based session management

### Game Library Management
- **Card Grid Display**: Visual game cards with pagination (20 per page)
- **Sorting & Navigation**: Sort by title, owner, player count, or BGG rating
- **Detailed Game View**: Flip cards to see full details, descriptions, and links
- **Multiple Add Methods**:
  - Manual form entry
  - BoardGameGeek URL scraping with auto-population
  - Bulk CSV upload
- **Game Tracking**: Vote for next play and favorite games (per-user)
- **Contributor Control**: Delete games from library

### Admin Features
- **User Management**: Add, view, update authorizations, and delete users
- **Image Updates**: Batch update missing game images from BoardGameGeek
- **System Administration**: Manage all aspects of the application

### Technical Features
- **RESTful API**: JSON-based communication between frontend and backend
- **Responsive Design**: Modern CSS with card-based layout
- **Real-time Updates**: Dynamic content loading without page refreshes
- **Docker Containerization**: Easy deployment and development
- **TLS/HTTPS Support**: Secure communications with certificate generation

## Installation

### Prerequisites

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Make** (for using Makefile commands)
- **Git** (for version control)

#### Optional (for GCP deployment):
- **Google Cloud SDK** (`make gcloud-sdk-install`)
- **Terraform** (handled via Docker in Makefile)
- **Active GCP Account** with billing enabled

### Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd gamegroup
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and configure required variables:
   - Database credentials (`DB_USER`, `DB_PASSWORD`, `DB_NAME`)
   - Email service credentials (`FORWARD_EMAIL_USER`, `FORWARD_EMAIL_PASSWORD`)
   - JWT secret key (`JWT_PRIVATE_KEY`)
   - Domain names and allowed origins

3. **Generate TLS certificates**
   
   For local development (self-signed):
   ```bash
   make cert-dev
   ```
   
   For production (Let's Encrypt):
   ```bash
   make cert-prod DOMAIN=yourdomain.com EMAIL=admin@yourdomain.com
   ```

4. **Build and start services**
   ```bash
   make dev
   ```
   This command will:
   - Build Docker images for frontend and backend
   - Start PostgreSQL database
   - Initialize database tables
   - Start all services
   - Follow logs for monitoring

5. **Access the application**
   - Frontend: `https://localhost:8443`
   - Backend API: `https://localhost:8443/api`
   - API Documentation: `https://localhost:8443/api/docs`

## Startup/Development Instructions

### Common Commands

```bash
# Start development environment (rebuild + start + logs)
make dev

# Build Docker images
make build

# Start services in background
make up

# Stop services
make down

# Restart services
make restart

# View logs
make logs

# Follow logs in real-time
make logs-follow

# View running containers
make ps

# Clean up (remove containers and volumes)
make clean
```

### Code Quality

```bash
# Run ruff linting
make ruff

# Format code with ruff
make ruff-format

# Auto-fix linting issues
make ruff-fix
```

### Database Management

```bash
# Backup database to backup.tar.gz
make db-backup

# Restore database from backup.tar.gz
make db-restore
```

### Development Workflow

1. **Start the development environment**
   ```bash
   make dev
   ```

2. **Make code changes**
   - Frontend code: `frontend/` directory (Brython/Python)
   - Backend code: `backend/` directory (FastAPI/Python)
   - Changes are reflected based on volume mounts

3. **Run code quality checks**
   ```bash
   make ruff-fix
   ```

4. **Rebuild if needed**
   ```bash
   make rebuild
   ```

5. **View logs for debugging**
   ```bash
   make logs-follow
   ```

### Google Cloud Deployment

1. **Setup GCP authentication**
   ```bash
   make gcloud-auth
   ```

2. **Publish Docker images to Artifact Registry**
   ```bash
   make publish-frontend
   make publish-backend
   ```

3. **Deploy infrastructure with Terraform**
   ```bash
   make terraform-init
   make terraform-plan
   make terraform-apply
   ```

### Troubleshooting

- **Port conflicts**: Ensure ports 8082 (HTTP) and 8443 (HTTPS) are available
- **Database connection issues**: Check `.env` file for correct credentials
- **Certificate errors**: Regenerate certificates with `make cert-dev`
- **Permission issues**: Run `sudo chown -R $USER:$USER certs/` after certificate generation

For complete command reference, run:
```bash
make help
```

