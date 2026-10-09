FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services/openjev USE_TF=0 HF_HUB_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false OPENJEV_MODEL_DIR=/models/openjev
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY services/openjev/requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir uv==0.11.28 \
    && uv pip install --system --no-cache -r requirements.lock.txt

RUN useradd --uid 10001 --create-home service \
    && mkdir -p /models/openjev && chown -R service:service /models
COPY services/openjev/openjev_service /app/services/openjev/openjev_service
USER service
EXPOSE 8000
CMD ["python", "-m", "openjev_service"]
