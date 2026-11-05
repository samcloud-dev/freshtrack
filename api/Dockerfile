# Base: official Python 3.12 on Debian "trixie" slim, pinned by digest (checked 2026-10-16).
FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# Send logs out immediately (no buffering), and don't write .pyc cache files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# All following commands run inside /app in the image.
WORKDIR /app

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
