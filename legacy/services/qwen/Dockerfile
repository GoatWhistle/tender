FROM vllm/vllm-openai:v0.22.1@sha256:55c9bcee9fc66644b139fddae8a7a03e4c0c8a25ab5c64b0ce614554a8abf5d5
USER root
WORKDIR /app/qwen
COPY services/qwen/ /app/qwen/
RUN python -m pip install --no-cache-dir -r requirements.lock.txt
RUN chmod +x /app/qwen/launch.sh
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
    QWEN_MODEL_DIR=/models/qwen PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
ENTRYPOINT ["/app/qwen/launch.sh"]
