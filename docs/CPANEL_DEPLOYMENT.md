# LoadSuite cPanel Deployment Guide

This guide walks you through deploying LoadSuite to a cPanel shared hosting environment with PostgreSQL.

## Prerequisites

- cPanel access at orbitsuite.cloud
- SSH access (recommended) or cPanel Terminal
- Python 3.11+ support on host

---

## Step 1: Create PostgreSQL Database in cPanel

1. **Log into cPanel** at `https://orbitsuite.cloud/cpanel` (or your host's cPanel URL)

2. **Navigate to Databases → PostgreSQL Databases**

3. **Create a new database:**
   - Database name: `loadsuite` (will be prefixed with your cPanel username, e.g., `username_loadsuite`)
   - Click "Create Database"

4. **Create a database user:**
   - Username: `loadsuite_user` (will become `username_loadsuite_user`)
   - Password: Generate a strong password and **save it securely**
   - Click "Create User"

5. **Add user to database:**
   - Select the user and database you just created
   - Grant **ALL PRIVILEGES**
   - Click "Add"

6. **Note your connection details:**
   ```
   Host: localhost (or the PostgreSQL server hostname shown in cPanel)
   Port: 5432 (default PostgreSQL port)
   Database: username_loadsuite
   Username: username_loadsuite_user
   Password: (your generated password)
   ```

---

## Step 2: Run the Database Schema

### Option A: Using phpPgAdmin (if available in cPanel)

1. Open phpPgAdmin from cPanel
2. Select your database
3. Click "SQL" tab
4. Copy/paste contents of `scripts/schema.sql`
5. Click "Execute"

### Option B: Using SSH/Terminal

```bash
# Connect to your server via SSH or cPanel Terminal
cd ~/LoadSuite

# Connect to PostgreSQL and run schema
psql -h localhost -U username_loadsuite_user -d username_loadsuite -f scripts/schema.sql
# Enter your password when prompted
```

### Option C: Using Python (after setup)

```bash
cd ~/LoadSuite
source venv/bin/activate

# Use psql through the connection URL
psql "$DATABASE_URL" -f scripts/schema.sql
```

---

## Step 3: Upload Application Files

### Option A: Git Clone (Recommended)

```bash
# SSH into your server
ssh username@orbitsuite.cloud

# Navigate to web directory
cd ~/public_html
# Or create a subdirectory for the app
mkdir -p ~/apps && cd ~/apps

# Clone the repository
git clone https://github.com/SyntacticLuster/LoadSuite.git
cd LoadSuite
```

### Option B: File Upload via cPanel File Manager

1. Zip the LoadSuite directory on your local machine
2. Upload via cPanel File Manager
3. Extract to `~/apps/LoadSuite` or desired location

---

## Step 4: Set Up Python Environment

```bash
cd ~/apps/LoadSuite  # Or wherever you placed the app

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install poetry
poetry install --no-dev
```

---

## Step 5: Configure Environment Variables

```bash
cd ~/apps/LoadSuite

# Copy the example environment file
cp .env.example .env

# Edit with your actual values
nano .env  # or use vim/cPanel File Manager
```

**Update these values in `.env`:**

```bash
# Database - use your actual cPanel PostgreSQL credentials
DATABASE_URL=postgresql://username_loadsuite_user:YOUR_PASSWORD@localhost:5432/username_loadsuite

# Production settings
ENVIRONMENT=production
USE_DATABASE=true
SECRET_KEY=generate-a-long-random-string-here

# CORS - your domain
CORS_ORIGINS=https://orbitsuite.cloud,https://www.orbitsuite.cloud

# Disable synthetic loads once you have real data
GENERATE_SYNTHETIC_LOADS=true
SYNTHETIC_LOAD_COUNT=100
```

**Generate a secure SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Step 6: Set Up Python Application in cPanel

### Option A: Setup Python App (cPanel feature)

1. Go to **cPanel → Setup Python App**
2. Click **Create Application**
3. Configure:
   - Python version: `3.11` (or highest available)
   - Application root: `apps/LoadSuite`
   - Application URL: `/FreightLens` (recommended for `apps.orbitsuite.cloud/FreightLens`)
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`
4. Click **Create**

### Recommended domain layout (apps subdomain)

If you want the app to live at `https://apps.orbitsuite.cloud/FreightLens`:

1. Create the subdomain `apps.orbitsuite.cloud` in cPanel.
2. Create the Python app with **Application URL** set to `/FreightLens`.

The UI and API in this repo are compatible with being hosted under a subpath like `/FreightLens` (no Apache proxy rewrite required).

#### Note: Passenger is WSGI, FastAPI is ASGI

cPanel's "Setup Python App" runs your app through Phusion Passenger in **WSGI** mode.
FastAPI is an **ASGI** app, so the included `passenger_wsgi.py` uses an ASGI→WSGI adapter.

Make sure the adapter dependency is installed in your cPanel app environment:

```bash
pip install a2wsgi
```

Create `passenger_wsgi.py` in your LoadSuite directory:

```python
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import the FastAPI app
from app.main import app

# Passenger expects 'application'
application = app
```

### Option B: Run with Gunicorn (if you have process control)

Create `gunicorn.conf.py`:

```python
bind = "127.0.0.1:8035"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
accesslog = "-"
errorlog = "-"
```

Start command:
```bash
cd ~/apps/LoadSuite
source venv/bin/activate
gunicorn app.main:app -c gunicorn.conf.py
```

---

## Step 7: Configure Domain/SSL

### Verify HTTPS is working

1. Visit `https://orbitsuite.cloud`
2. Check for valid SSL certificate (green padlock)

### If HTTPS isn't set up:

1. Go to **cPanel → SSL/TLS Status** or **Let's Encrypt SSL**
2. Issue a certificate for `orbitsuite.cloud`
3. Enable **Force HTTPS Redirect** in cPanel

### Set up Proxy (if using cPanel's Apache)

Create/edit `.htaccess` in `public_html`:

```apache
RewriteEngine On

# Force HTTPS
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

# Proxy to Python app (if running on port 8035)
RewriteCond %{REQUEST_URI} ^/api/
RewriteRule ^(.*)$ http://127.0.0.1:8035/$1 [P,L]

# Serve static files directly
RewriteCond %{REQUEST_FILENAME} -f
RewriteRule ^ - [L]

# Proxy everything else to the app
RewriteRule ^(.*)$ http://127.0.0.1:8035/$1 [P,L]
```

---

## Step 8: Test the Deployment

```bash
# Test health endpoint
curl https://orbitsuite.cloud/api/health

# Expected response:
{
  "status": "healthy",
  "environment": "production",
  "use_database": true,
  "database": {"status": "healthy", "connected": true, ...}
}

# Test loads endpoint
curl https://orbitsuite.cloud/api/meta
```

---

## Step 9: Seed Initial Data (Optional)

If you want to populate the database with synthetic loads:

```bash
cd ~/apps/LoadSuite
source venv/bin/activate

python -c "
import asyncio
from app.database import init_db_pool, close_db_pool
from app.data import generate_synthetic_loads
from app.services.postgres import PostgresLoadRepository

async def seed():
    await init_db_pool()
    repo = PostgresLoadRepository()
    dataset = generate_synthetic_loads(200)
    count = await repo.save_many(dataset.loads)
    print(f'Seeded {count} loads')
    await close_db_pool()

asyncio.run(seed())
"
```

---

## Troubleshooting

### Database Connection Errors

```bash
# Test PostgreSQL connection
psql -h localhost -U username_loadsuite_user -d username_loadsuite -c "SELECT 1;"
```

### Check Application Logs

```bash
# If using cPanel Python App
cat ~/apps/LoadSuite/passenger.log

# If using Gunicorn/systemd
journalctl -u loadsuite -f
```

### Permission Issues

```bash
# Ensure proper ownership
chown -R $USER:$USER ~/apps/LoadSuite
chmod -R 755 ~/apps/LoadSuite
```

### Environment Not Loading

```bash
# Verify .env exists and is readable
cat ~/apps/LoadSuite/.env

# Test environment loading
cd ~/apps/LoadSuite && source venv/bin/activate
python -c "from app.config import settings; print(settings.database_url)"
```

---

## Next Steps

1. **Set up monitoring** - Configure uptime checks for `/api/health`
2. **Enable logging** - Configure log aggregation
3. **Backups** - Set up PostgreSQL backups in cPanel
4. **SSL auto-renewal** - Ensure Let's Encrypt auto-renews

---

## Quick Reference

| Item | Value |
|------|-------|
| App URL | `https://orbitsuite.cloud` |
| Health Check | `https://orbitsuite.cloud/api/health` |
| API Base | `https://orbitsuite.cloud/api/` |
| App Location | `~/apps/LoadSuite` |
| Virtual Env | `~/apps/LoadSuite/venv` |
| Logs | `~/apps/LoadSuite/*.log` |
