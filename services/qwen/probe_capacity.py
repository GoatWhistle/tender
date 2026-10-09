"""Exercise 16 distinct near-limit prompts while all three GPU models run."""

import argparse
import concurrent.futures
import json
import subprocess
import threading
import time
from pathlib import Path

from transformers import AutoTokenizer
from verify_gpu import call, summary, timed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--extractor", default="http://127.0.0.1:8082")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    schema = {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["ok"]}},
        "required": ["status"],
        "additionalProperties": False,
    }
    filler = tokenizer.encode(" Длинный текст каталога: деревянный стол.", add_special_tokens=False)
    bodies, token_counts = [], []
    for index in range(16):
        # Change the first user tokens so prefix caching cannot share long prompts.
        text = f"Случай {index}. " + tokenizer.decode((filler * 2000)[:7400])
        messages = [{"role": "user", "content": text + " Верни status=ok."}]
        count = len(
            tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
            )
        )
        assert 7300 < count < 7900
        token_counts.append(count)
        bodies.append(
            {
                "model": "qwen-extractor",
                "messages": messages,
                "max_tokens": 32,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "capacity", "strict": True, "schema": schema},
                },
            }
        )
    samples, stopped = [], threading.Event()

    def monitor():
        while not stopped.is_set():
            value = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                text=True,
            )
            samples.append({"time": time.time(), "used_mib": int(value.strip())})
            stopped.wait(0.25)

    thread = threading.Thread(target=monitor)
    thread.start()
    started = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=18) as pool:
            futures = [
                pool.submit(timed, args.extractor, "/v1/chat/completions", body) for body in bodies
            ]
            embedding = pool.submit(
                call,
                "http://127.0.0.1:8081",
                "/v1/embeddings",
                {"model": "qwen-embedding", "input": ["Деревянный стол"] * 32},
            )
            decision = pool.submit(
                call,
                "http://127.0.0.1:8080",
                "/v1/nli",
                {
                    "premise": "Высота стола 70 см.",
                    "hypotheses": ["Высота стола 70 см.", "Высота стола 90 см."],
                },
            )
            results = [future.result() for future in futures]
            assert len(embedding.result()["data"]) == 32
            assert [r["label"] for r in decision.result()["results"]] == [
                "supported",
                "contradicted",
            ]
        for _, response in results:
            choice = response["choices"][0]
            assert choice["finish_reason"] == "stop"
            assert json.loads(choice["message"]["content"]) == {"status": "ok"}
        report = {
            "clients": 16,
            "prompt_tokens": token_counts,
            "engine_usage": [r["usage"] for _, r in results],
            "wall_seconds": time.perf_counter() - started,
            "strict_passed": 16,
            "parallel_embedding_and_openjev_passed": True,
            **summary([ms for ms, _ in results]),
        }
    finally:
        stopped.set()
        thread.join()
    report["gpu_samples"] = samples
    report["peak_used_mib"] = max(s["used_mib"] for s in samples)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "gpu_samples"}))


if __name__ == "__main__":
    main()
