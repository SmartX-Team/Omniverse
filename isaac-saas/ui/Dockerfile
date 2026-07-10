# Isaac Sim self-service UI (FastAPI + uvicorn).
# Dependencies are locked by uv.lock - every build installs the exact same tree
# (versions + hashes), on the lab build host today and in AWS CI later.
FROM python:3.12-slim

# uv binary (pinned tag; no Python needed in this stage of the copy)
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /srv

# Locked dependency layer - cached unless pyproject.toml/uv.lock change.
# --frozen: refuse to build if the lockfile is out of date (fail fast, never drift)
COPY pyproject.toml uv.lock /srv/
RUN uv sync --frozen --no-dev --no-install-project --compile-bytecode

# Application package: config / k8s / policy / resources / tracking / instances /
# gpu / web, plus static/ (index.html, style.css, app.js).
COPY app/ /srv/app/

# Run as a non-root user; the app binds 8080 (>1024) and only reads the in-cluster
# ServiceAccount token, so no elevated privileges are needed.
RUN useradd -u 10001 -r -s /usr/sbin/nologin appuser
USER 10001

ENV PORT=8080 PATH="/srv/.venv/bin:$PATH"
EXPOSE 8080
# Run the package (app/__main__.py -> web.main() -> uvicorn)
CMD ["python3", "-m", "app"]
