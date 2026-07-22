FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PATH=/venv/bin:$PATH

WORKDIR /app

# System build deps for native wheels (adjust if a package needs more)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and use virtualenv
RUN python -m venv /venv

# Install pip and wheel then project requirements (cache layer)
COPY requirements.txt /app/requirements.txt
RUN /venv/bin/pip install --upgrade pip setuptools wheel && \
    /venv/bin/pip install -r /app/requirements.txt

# Copy application
COPY . /app

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

# Production: use Gunicorn with config file
CMD ["gunicorn", "-c", "gunicorn.conf.py", "manage:app"]
