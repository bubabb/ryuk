import pytest

from backend.inference.engines.mock import MockEngine
from backend.inference.registry import EngineRegistry


def test_register_normalizes_engine_name() -> None:
    registry = EngineRegistry()

    registry.register(MockEngine())

    assert "MOCK" in registry
    assert registry.get(" Mock ").name == "mock"
    assert registry.names() == ("mock",)


def test_unregister_unknown_engine_is_safe() -> None:
    registry = EngineRegistry()

    registry.unregister("missing")

    assert len(registry) == 0


def test_get_unknown_engine_reports_registered_names() -> None:
    registry = EngineRegistry()
    registry.register(MockEngine())

    with pytest.raises(KeyError, match="Registered engines: mock"):
        registry.get("missing")
