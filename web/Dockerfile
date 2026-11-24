# Base: same official Python 3.12 slim image as the api, pinned by digest. Update both together.
FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# Send logs out immediately, and don't write .pyc cache files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Temporary: security fixes not yet in the base image. Same as api/Dockerfile; remove from both together.
#   apt:  CVE-2026-109518, fixed in 3.0.4 (DSA-6607-1)
#   zlib: CVE-2026-76844, CVE-2026-85091, fixed in 1:1.3.dfsg+really1.3.1-1+deb13u1 (DSA-6613-1)
RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade \
      apt=3.0.4 libapt-pkg7.0=3.0.4 \
      zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
 && rm -rf /var/lib/apt/lists/*

# Packages first: Docker reuses this layer when only the code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt

# Only the application: code, page templates and styles (tests and dev tools stay out).
COPY app.py api_client.py dates.py icons.py ./
COPY templates/ templates/
COPY static/ static/

# Its own non-root user (the api uses 10001), no home and no login. A numeric ID lets Kubernetes verify runAsNonRoot.
RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin freshtrack-web
USER 10002

EXPOSE 8000

# gunicorn calls create_app(). SECRET_KEY and API_URL must be set at run time, or web refuses to start.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--no-control-socket", "app:create_app()"]
