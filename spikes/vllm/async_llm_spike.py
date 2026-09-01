import argparse
import asyncio
import json
import platform
import time
import uuid
from pathlib import Path


async def run(args: argparse.Namespace) -> dict[str, object]:
    # GPU-only imports stay inside the isolated spike entry point.
    import vllm
    from vllm import SamplingParams
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.v1.engine.async_llm import AsyncLLM

    engine = AsyncLLM.from_engine_args(AsyncEngineArgs(
        model=args.model,
        tensor_parallel_size=args.tensor_parallel_size,
        trust_remote_code=args.trust_remote_code,
    ))
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    async def generate(measured: bool) -> dict[str, object]:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        first_output = None
        final = None
        async for output in engine.generate(args.prompt, sampling, request_id):
            if first_output is None:
                first_output = time.perf_counter()
            final = output
        finished = time.perf_counter()
        if final is None or first_output is None:
            raise RuntimeError("AsyncLLM returned no output.")
        output_tokens = len(final.outputs[0].token_ids)
        return {
            "measured": measured,
            "ttft_ms": (first_output - started) * 1000,
            "latency_ms": (finished - started) * 1000,
            "output_tokens": output_tokens,
            "tokens_per_second": output_tokens / (finished - started),
            "finish_reason": final.outputs[0].finish_reason,
        }

    samples = [await generate(False) for _ in range(args.warmup)]
    samples.extend([await generate(True) for _ in range(args.samples)])
    engine.shutdown()
    return {
        "schema_version": 1,
        "vllm_version": vllm.__version__,
        "model": args.model,
        "tensor_parallel_size": args.tensor_parallel_size,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "prompt_characters": len(args.prompt),
        "max_tokens": args.max_tokens,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--prompt", default="Explain Ryuk in one paragraph.")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
