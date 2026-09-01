from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.middleware import RequestBodyLimitMiddleware, RequestContextMiddleware


def test_body_limit_rejects_content_length_above_limit() -> None:
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=10)

    @app.post("/")
    async def endpoint(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    response = TestClient(app).post("/", content=b"01234567890")

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large."}


def test_body_limit_allows_body_at_limit() -> None:
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=10)

    @app.post("/")
    async def endpoint(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    response = TestClient(app).post("/", content=b"0123456789")

    assert response.status_code == 200
    assert response.json() == {"size": 10}


def test_body_limit_counts_chunked_body_without_content_length() -> None:
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=10)

    @app.post("/")
    async def endpoint(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    response = TestClient(app).post("/", content=iter([b"012345", b"67890"]))

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large."}


def test_request_context_accepts_safe_request_id_and_traceparent() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/")
    async def endpoint(request: Request) -> dict[str, str]:
        return {
            "request_id": request.state.request_id,
            "traceparent": request.state.traceparent,
        }

    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    response = TestClient(app).get(
        "/",
        headers={"x-request-id": "client-request_123", "traceparent": traceparent},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "client-request_123"
    assert response.json() == {
        "request_id": "client-request_123",
        "traceparent": traceparent,
    }


def test_request_context_replaces_unsafe_request_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/")
    async def endpoint(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    response = TestClient(app).get("/", headers={"x-request-id": "unsafe value"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "unsafe value"
    assert response.json()["request_id"] == response.headers["x-request-id"]
