#!/bin/bash

# Post-create script for GitHub Codespaces
# Optimized for lightweight ML dependencies
# Last updated: 2026-01-25

set -e

echo "Setting up Flask testing environment for Codespaces..."

# Install system dependencies for Playwright
sudo apt-get update && sudo apt-get install -y \
  libnss3 \
  libatk-bridge2.0-0 \
  libdrm2 \
  libxkbcommon0 \
  libgtk-3-0 \
  libgbm1 \
  curl \
  --no-install-recommends

# Clean up apt cache to save space
sudo apt-get clean && sudo rm -rf /var/lib/apt/lists/*

# Set up environment variables
echo "export FLASK_CONFIG=codespaces" >> ~/.bashrc
echo "export SECRET_KEY=codespaces-test-secret-key-[1;32m$(date +%s)" >> ~/.bashrc
echo "export PLAYWRIGHT_BROWSER_HEADLESS=true" >> ~/.bashrc
echo "export TOKENIZERS_PARALLELISM=false" >> ~/.bashrc

# Source the environment variables
source ~/.bashrc

# Wait for PostgreSQL to be ready (using devcontainer feature)
echo "Waiting for PostgreSQL..."
timeout=60
while ! pg_isready -h localhost -p 5432 2>/dev/null; do
  if [ $timeout -le 0 ]; then
    echo "PostgreSQL not ready after 60 seconds, continuing with SQLite fallback..."
    echo "export DATABASE_URL=sqlite:///test_codespaces.db" >> ~/.bashrc
    source ~/.bashrc
    break
  fi
  echo "db:5432 - no response"
sleep 2
  timeout=$((timeout-2))
done

if pg_isready -h localhost -p 5432 2>/dev/null; then
  echo "PostgreSQL is ready"
  echo "export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/flask_app" >> ~/.bashrc
  source ~/.bashrc

  # Create test database
  createdb -h localhost -p 5432 -U postgres flask_app 2>/dev/null || echo "Database may already exist"

  # Enable pgvector extension if available
  export PGPASSWORD=postgres
  psql -h localhost -p 5432 -U postgres -d flask_app -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || echo "pgvector extension not available (optional)"
else
  echo "Using SQLite for testing"
fi

# Create necessary directories
mkdir -p test-results/videos
mkdir -p logs

# Upgrade pip first
echo "Upgrading pip..."
pip install --upgrade pip

# Install PyTorch CPU-only version FIRST (much smaller, faster)
echo "Installing PyTorch (CPU-only for Codespaces)..."
pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

# Install main requirements
if [ -f "requirements.txt" ]; then
  echo "Installing Python dependencies..."
pip install -r requirements.txt --no-cache-dir
fi

# Install Playwright browsers (chromium only to save space)
echo "Installing Playwright browsers..."
playwright install chromium --with-deps

# Run database setup if script exists
if [ -f "scripts/setup/setup_codespaces_db.py" ]; then
  echo "Setting up database..."
  python scripts/setup/setup_codespaces_db.py || echo "Database setup skipped (may need Flask app context)"
fi

# Verify Flask app can be created
echo "Testing Flask app creation..."
python -c "from app import create_app; app = create_app('codespaces'); print('Flask app created successfully')" || echo "Flask app verification skipped"

echo ""
echo "============================================"
echo "Codespaces environment setup complete!"
echo "============================================"
echo ""
echo "To start testing:"
echo "1. Start the Flask server: python run.py"
echo "2. Run tests: pytest tests/enterprise/ -v"
echo ""
