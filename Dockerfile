FROM python:3.12-slim

ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.source="https://github.com/Anioko/archie-ea" \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.created=$BUILD_DATE

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
    # WeasyPrint native deps — without these, PDF export fails at runtime with
    # "cannot load library 'gobject-2.0-0'". (installed live 2026-07-14)
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi-dev \
    libglib2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Create and use virtualenv
RUN python -m venv /venv

# Install pip and wheel then project requirements (cache layer)
COPY requirements.txt /app/requirements.txt
# torch FIRST, from PyTorch's CPU-only index.
#
# sentence-transformers requires torch, and the default PyPI wheel for Linux
# bundles the entire CUDA runtime. Measured in the running production image:
# 2.7GB of site-packages/nvidia plus 1.2GB of torch, inside a 16.4GB image, on a
# droplet with no /dev/nvidia device at all. None of it can ever execute.
#
# It is not free weight either. A deploy failed outright with "no space left on
# device" while extracting libcublasLt.so.13, and every build since has had to
# write those gigabytes again on a 2-vCPU box.
#
# Installing torch from the cpu index BEFORE the requirements resolve means
# sentence-transformers finds its dependency already satisfied and never pulls the
# CUDA variant. faiss-cpu, directly above it in requirements.txt, was already
# pinned this way; torch simply never was.
RUN /venv/bin/pip install --upgrade pip setuptools wheel && \
    /venv/bin/pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu torch && \
    /venv/bin/pip install -r /app/requirements.txt

# Copy application
COPY . /app

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

# Production: use Gunicorn with config file
CMD ["gunicorn", "-c", "gunicorn.conf.py", "manage:app"]
