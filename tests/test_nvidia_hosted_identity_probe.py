from scripts.probe_nvidia_hosted_identity import sanitize_generation_observation


def test_sanitized_observation_keeps_contract_metadata_only() -> None:
    payload = {
        "id": "request-id",
        "model": "moonshotai/kimi-k3",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "sensitive generated content",
                    "reasoning_content": "sensitive reasoning",
                },
            }
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11},
    }

    observation = sanitize_generation_observation(
        model="moonshotai/kimi-k3",
        status_code=200,
        elapsed_ms=12.3456,
        payload=payload,
    )

    assert observation["response_model"] == "moonshotai/kimi-k3"
    assert observation["identity_matches"] is True
    assert observation["response_id_present"] is True
    assert observation["choices_present"] is True
    assert observation["finish_reason"] == "stop"
    assert observation["usage_fields_present"] == {
        "usage_object": True,
        "prompt_tokens": True,
        "completion_tokens": True,
        "total_tokens": True,
    }
    rendered = str(observation)
    assert "sensitive generated content" not in rendered
    assert "sensitive reasoning" not in rendered
    assert "request-id" not in rendered


def test_sanitized_observation_records_protocol_failure_without_body() -> None:
    observation = sanitize_generation_observation(
        model="deepseek-ai/deepseek-v4.1-flash",
        status_code=429,
        elapsed_ms=10,
        payload={"error": {"message": "account-specific failure detail"}},
        failure_type="HTTP_429",
    )

    assert observation["identity_matches"] is False
    assert observation["failure_type"] == "HTTP_429"
    assert "account-specific failure detail" not in str(observation)
