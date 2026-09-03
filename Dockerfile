# Label Check (prototype) -- single container, no network access needed at build* or run time.
# (*) pip needs the package index at build time; models and frontend assets are in the repo.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 \
    PORT=8000

# libgomp is needed by onnxruntime; nothing else beyond the slim image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system app && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --require-virtualenv=false -r requirements.txt

COPY --chown=app:app app ./app
COPY --chown=app:app README.md LICENSE THIRD_PARTY_NOTICES.md ./
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA} \
    TTB_OCR_WORKERS=2 \
    TTB_TRUST_PROXY=true

USER app
EXPOSE 8000

# Startup: models load in the background; /api/v1/health reports ready=true when warm.
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=4 \
  CMD python -c "import json,sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health' % __import__('os').environ.get('PORT','8000'), timeout=4); sys.exit(0 if json.load(r).get('ready') else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 15 --no-server-header"]
