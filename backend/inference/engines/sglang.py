from __future__ import annotations

import asyncio

import json

import time

from urllib import error, request

from backend.inference.base import (

    InferenceEngine,

    InferenceRequest,

    InferenceResponse,

)

class SGLangEngine(InferenceEngine):

    """

    Native SGLang inference adapter.

    This adapter deliberately uses SGLang's native /generate endpoint,

    not an OpenAI-compatible API.

    """

    name = "sglang"

    def __init__(

        self,

        base_url: str = "http://127.0.0.1:30000",

        timeout: float = 120.0,

    ) -> None:

        self.base_url = base_url.rstrip("/")

        self.timeout = timeout

    async def is_available(self) -> bool:

        return await asyncio.to_thread(self._check_health)

    def _check_health(self) -> bool:

        try:

            req = request.Request(

                f"{self.base_url}/health",

                method="GET",

            )

            with request.urlopen(req, timeout=3):

                return True

        except (error.URLError, TimeoutError, OSError):

            return False

    async def generate(

        self,

        inference_request: InferenceRequest,

    ) -> InferenceResponse:

        return await asyncio.to_thread(

            self._generate_sync,

            inference_request,

        )

    def _generate_sync(

        self,

        inference_request: InferenceRequest,

    ) -> InferenceResponse:

        payload = {

            "text": inference_request.prompt,

            "sampling_params": {

                "temperature": inference_request.temperature,

            },

        }

        if inference_request.max_tokens is not None:

            payload["sampling_params"]["max_new_tokens"] = (

                inference_request.max_tokens

            )

        body = json.dumps(payload).encode("utf-8")

        req = request.Request(

            f"{self.base_url}/generate",

            data=body,

            headers={"Content-Type": "application/json"},

            method="POST",

        )

        started = time.perf_counter()

        try:

            with request.urlopen(

                req,

                timeout=self.timeout,

            ) as response:

                result = json.loads(response.read().decode("utf-8"))

        except error.HTTPError as exc:

            detail = exc.read().decode("utf-8", errors="replace")

            raise RuntimeError(

                f"SGLang returned HTTP {exc.code}: {detail}"

            ) from exc

        except error.URLError as exc:

            raise RuntimeError(

                f"Unable to reach SGLang at {self.base_url}"

            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000

        meta = result.get("meta_info", {})

        return InferenceResponse(

            text=result.get("text", ""),

            model=inference_request.model,

            engine=self.name,

            latency_ms=latency_ms,

            input_tokens=meta.get("prompt_tokens"),

            output_tokens=meta.get("completion_tokens"),

            metadata={

                "sglang_meta": meta,

            },

        )
    