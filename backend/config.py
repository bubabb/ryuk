from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    app_env: str = "development"

    app_name: str = "Ryuk AI"

    app_version: str = "0.1.0"

    # Existing model/provider settings

    kimi_api_url: str = ""

    kimi_api_key: str = ""

    nvidia_api_key: str = ""

    # Native inference engines

    sglang_enabled: bool = True

    sglang_base_url: str = "http://127.0.0.1:30000"

    vllm_enabled: bool = False

    vllm_base_url: str = "http://127.0.0.1:8000"

    tensorrt_llm_enabled: bool = False

    tensorrt_llm_base_url: str = "http://127.0.0.1:8001"

    dynamo_enabled: bool = False

    dynamo_base_url: str = "http://127.0.0.1:8002"

    nim_enabled: bool = False

    nim_base_url: str = "http://127.0.0.1:8003"

    mock_enabled: bool = True

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

settings = Settings()