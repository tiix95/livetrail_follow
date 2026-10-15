# ──────────────────────────────────────────────────────────────────────────────
# livetrail-follow — Containerfile
# Outbound-only asyncio poller: no listening port, no EXPOSE.
# Runtime config and state live outside the image:
#   - mount a config file to /etc/livetrail-follow/config.yml (read-only)
#   - mount a writable directory to /data (holds state.json)
# ──────────────────────────────────────────────────────────────────────────────
FROM debian:trixie-slim

LABEL maintainer="tiix"
LABEL version="0.3.1"

RUN rm /etc/localtime && ln -s /usr/share/zoneinfo/Europe/Paris /etc/localtime

# Install dependencies — all from Debian repos, never pip
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        python3-aiohttp \
        python3-yaml \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged user
RUN groupadd -r app && useradd -r -g app -d /app -s /usr/sbin/nologin app

# Copy application source only
COPY src/ /app/src/

# Set ownership and permissions
RUN chown -R app:app /app && chmod -R 750 /app

ENV PYTHONPATH=/app/src

USER app
WORKDIR /app

ENTRYPOINT ["python3", "-m", "livetrail_follow"]
