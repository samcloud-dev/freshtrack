# Base: official Python 3.12 on Debian "trixie" slim, pinned by digest (checked 2026-10-16).
FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# Send logs out immediately (no buffering), and don't write .pyc cache files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# All following commands run inside /app in the image.
WORKDIR /app

# Temporary: security fixes not yet in the base image. Remove each one when the base image includes it.
#   apt:  CVE-2026-109518, fixed in 3.0.4 (DSA-6607-1)
#   zlib: CVE-2026-76844, CVE-2026-85091, fixed in 1:1.3.dfsg+really1.3.1-1+deb13u1 (DSA-6613-1)
RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade \
      apt=3.0.4 libapt-pkg7.0=3.0.4 \
      zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
 && rm -rf /var/lib/apt/lists/*

# Install runtime packages first. Docker reuses this layer when only the code changes.
# Same locked install as CI: wheels only, every file checked against its hash.
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt

# Copy only the application code.
COPY app.py db.py validation.py schema.sql init_db.py .

# Create a user with no login and no home, and run as it (not root).
# A numeric ID lets Kubernetes verify "runAsNonRoot".
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin freshtrack
USER 10001

# Document the port the app listens on.
EXPOSE 8000

# gunicorn is the production web server; it calls create_app() to build the Flask app.
# --no-control-socket: Kubernetes manages the process, so gunicorn's admin socket is not needed.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--no-control-socket", "app:create_app()"]
