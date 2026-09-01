from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT

    app_name: str = "Ryuk AI"

    app_version: str = "0.1.0"

    max_prompt_chars: int = Field(default=100_000, ge=1)

    max_request_body_bytes: int = Field(default=1_048_576, ge=1)

    max_generation_tokens: int = Field(default=32_768, ge=1)

    runtime_probe_timeout_seconds: float = Field(default=3.0, gt=0)

    runtime_state_ttl_seconds: float = Field(default=15.0, gt=0)

    runtime_refresh_interval_seconds: float = Field(default=5.0, gt=0)

    control_plane_config_path: Path | None = None

    execution_record_path: Path | None = None

    # Existing model/provider settings

    kimi_api_url: str = ""

    kimi_api_key: str = ""

    nvidia_api_key: str = ""

    kimi_secret_ref: str = ""

    nvidia_secret_ref: str = ""

    # Native inference engines

    sglang_enabled: bool = True

    sglang_base_url: str = "http://127.0.0.1:30000"

    sglang_deployment_id: str = "sglang-local"

    sglang_endpoint_id: str = "sglang-local-http"

    sglang_model_artifact_id: str = ""

    sglang_model_revision: str = ""

    sglang_served_model_name: str = ""

    sglang_engine_version: str = ""

    sglang_serving_runtime: str = "standalone"

    sglang_connect_timeout_seconds: float = Field(default=5.0, gt=0)

    sglang_read_timeout_seconds: float = Field(default=120.0, gt=0)

    sglang_write_timeout_seconds: float = Field(default=10.0, gt=0)

    sglang_pool_timeout_seconds: float = Field(default=5.0, gt=0)

    sglang_identity_timeout_seconds: float = Field(default=3.0, gt=0)

    sglang_max_response_bytes: int = Field(default=16_777_216, ge=1)

    sglang_max_context_tokens: int | None = Field(default=None, ge=1)

    sglang_accelerators: str = ""

    sglang_topology: str = ""

    sglang_data_locations: str = ""

    sglang_production_eligible: bool = False

    sglang_cost_class: Literal["unknown", "low", "medium", "high"] = "unknown"

    sglang_latency_class: Literal["unknown", "low", "medium", "high"] = "unknown"

    sglang_text_suitability: int = Field(default=5, ge=-10, le=10)

    vllm_enabled: bool = False

    vllm_base_url: str = "http://127.0.0.1:8000"

    vllm_deployment_id: str = "vllm-worker"

    vllm_endpoint_id: str = "vllm-worker-http"

    vllm_model_artifact_id: str = ""

    vllm_model_revision: str = ""

    vllm_engine_version: str = "0.26.0"

    vllm_max_context_tokens: int | None = Field(default=None, ge=1)

    vllm_accelerators: str = ""

    vllm_topology: str = ""

    vllm_data_locations: str = ""

    vllm_production_eligible: bool = False

    vllm_cost_class: Literal["unknown", "low", "medium", "high"] = "unknown"

    vllm_latency_class: Literal["unknown", "low", "medium", "high"] = "unknown"

    vllm_text_suitability: int = Field(default=5, ge=-10, le=10)

    vllm_chat_suitability: int = Field(default=5, ge=-10, le=10)

    tensorrt_llm_enabled: bool = False

    tensorrt_llm_base_url: str = "http://127.0.0.1:8001"

    dynamo_enabled: bool = False

    dynamo_base_url: str = "http://127.0.0.1:8002"

    dynamo_deployment_id: str = "dynamo-deployment"
    dynamo_endpoint_id: str = "dynamo-frontend-http"
    dynamo_model_artifact_id: str = ""
    dynamo_model_revision: str = ""
    dynamo_runtime_version: str = "1.4.1"
    dynamo_topology: Literal["aggregated", "disaggregated"] = "aggregated"
    dynamo_max_context_tokens: int | None = Field(default=None, ge=1)
    dynamo_accelerators: str = ""
    dynamo_data_locations: str = ""
    dynamo_production_eligible: bool = False
    dynamo_cost_class: Literal["unknown", "low", "medium", "high"] = "unknown"
    dynamo_latency_class: Literal["unknown", "low", "medium", "high"] = "unknown"

    nim_enabled: bool = False

    nim_base_url: str = "http://127.0.0.1:8003"

    nim_api_key: str = ""
    nim_secret_ref: str = ""
    nim_deployment_id: str = "nim-deployment"
    nim_endpoint_id: str = "nim-http"
    nim_model_artifact_id: str = ""
    nim_model_revision: str = ""
    nim_release: str = "2.0.11"
    nim_profile_id: str = ""
    nim_backend: str = "vllm"
    nim_max_context_tokens: int | None = Field(default=None, ge=1)
    nim_accelerators: str = ""
    nim_topology: str = ""
    nim_data_locations: str = ""
    nim_production_eligible: bool = False
    nim_cost_class: Literal["unknown", "low", "medium", "high"] = "unknown"
    nim_latency_class: Literal["unknown", "low", "medium", "high"] = "unknown"

    mock_enabled: bool = True

    mock_deployment_id: str = "mock-development"

    # Supabase

    supabase_url: str = ""

    supabase_anon_key: str = ""

    supabase_service_role_key: str = ""

    # Database

    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_mock_environment(self) -> "Settings":
        if self.mock_enabled and self.app_env is AppEnvironment.PRODUCTION:
            raise ValueError("MOCK_ENABLED must be false in production.")
        if self.app_env is AppEnvironment.PRODUCTION and (
            self.control_plane_config_path is None
            or self.execution_record_path is None
        ):
            raise ValueError(
                "Production requires CONTROL_PLANE_CONFIG_PATH and "
                "EXECUTION_RECORD_PATH."
            )
        if self.app_env is AppEnvironment.PRODUCTION and any(
            value.strip()
            for value in (self.kimi_api_key, self.nvidia_api_key, self.nim_api_key)
        ):
            raise ValueError(
                "Production provider credentials must use secret references."
            )
        if (
            self.app_env is AppEnvironment.PRODUCTION
            and self.nim_enabled
            and not self.nim_secret_ref.strip()
        ):
            raise ValueError("Production NIM requires NIM_SECRET_REF.")
        if self.vllm_enabled and not self.vllm_model_artifact_id.strip():
            raise ValueError("VLLM_MODEL_ARTIFACT_ID is required when VLLM is enabled.")
        if self.dynamo_enabled and not self.dynamo_model_artifact_id.strip():
            raise ValueError(
                "DYNAMO_MODEL_ARTIFACT_ID is required when Dynamo is enabled."
            )
        if self.dynamo_production_eligible:
            raise ValueError(
                "Dynamo production eligibility is held by ADR-006 until its "
                "measured adoption gate passes."
            )
        if self.nim_enabled and (
            not self.nim_model_artifact_id.strip() or not self.nim_profile_id.strip()
        ):
            raise ValueError(
                "NIM_MODEL_ARTIFACT_ID and NIM_PROFILE_ID are required "
                "when NIM is enabled."
            )
        if self.tensorrt_llm_enabled:
            raise ValueError(
                "TensorRT-LLM is held by the G3 decision gate; no adapter is approved."
            )
        return self


settings = Settings()
