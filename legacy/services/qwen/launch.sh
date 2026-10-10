#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-4}
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1
model_root=${QWEN_MODEL_DIR:-/models/qwen}
case "${1:-}" in
  embedding)
    python download.py --root "$model_root" --verify-only
    exec vllm serve "$model_root/embedding" \
      --served-model-name qwen-embedding --runner pooling --dtype bfloat16 \
      --host "${QWEN_HOST:-0.0.0.0}" --port "${QWEN_PORT:-8000}" \
      --max-model-len 4096 --max-num-seqs 32 --max-num-batched-tokens 8192 \
      --gpu-memory-utilization "${EMBEDDING_GPU_MEMORY_UTILIZATION:-0.08}"
    ;;
  extractor)
    python download.py --root "$model_root" --verify-only
    exec vllm serve "$model_root/extractor" \
      --served-model-name qwen-extractor --dtype bfloat16 --language-model-only \
      --host "${QWEN_HOST:-0.0.0.0}" --port "${QWEN_PORT:-8000}" \
      --max-model-len 8192 --max-num-seqs 16 --max-num-batched-tokens 4096 \
      --gpu-memory-utilization "${EXTRACTOR_GPU_MEMORY_UTILIZATION:-0.35}" \
      --enable-prefix-caching --enable-chunked-prefill \
      --structured-outputs-config '{"backend":"xgrammar"}' \
      --default-chat-template-kwargs '{"enable_thinking":false}'
    ;;
  strict)
    exec python -m uvicorn strict_api:app --host "${QWEN_HOST:-0.0.0.0}" \
      --port "${QWEN_PORT:-8000}" --workers 1 --limit-concurrency 32
    ;;
  *) echo "Usage: launch.sh embedding|extractor|strict" >&2; exit 2 ;;
esac
