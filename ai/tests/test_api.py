import pytest
from fastapi.testclient import TestClient

from finguard_ai.classification import MissingClassifier
from finguard_ai.config import Settings
from finguard_ai.main import Services, create_app
from finguard_ai.schemas import ClassificationResult

TOKEN = "a" * 32


class Classifier:
    def classify(self, text):
        return ClassificationResult(label=None, decision="ABSTAIN", modelVersion="test-v1")


class Provider:
    configured = False


class EmptyRepository:
    def has_embeddings(self, model):
        return False


@pytest.fixture
def app():
    return create_app(
        Settings(service_token=TOKEN, max_concurrent_requests=1),
        Services(Classifier(), EmptyRepository(), Provider(), True),
    )


def test_internal_auth_and_valid_contract(app):
    with TestClient(app) as client:
        assert client.post("/internal/v1/classifications", json={"text": "문자"}).status_code == 401
        r = client.post(
            "/internal/v1/classifications", json={"text": "문자"}, headers={"X-Service-Token": TOKEN}
        )
        assert r.status_code == 200
        assert r.json() == {
            "status": "COMPLETED",
            "label": None,
            "decision": "ABSTAIN",
            "modelVersion": "test-v1",
            "errorCode": None,
        }
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


@pytest.mark.parametrize(
    "payload", [{"text": " "}, {"text": "a" * 10001}, {"text": 123}, {"text": "문자", "role": "ADMIN"}]
)
def test_invalid_input_does_not_echo_raw_text(app, payload):
    with TestClient(app) as client:
        r = client.post("/internal/v1/classifications", json=payload, headers={"X-Service-Token": TOKEN})
        assert r.status_code == 422
        assert r.json() == {"error": "INVALID_REQUEST"}


def test_body_size_limit_and_capacity(app):
    with TestClient(app) as client:
        assert client.post("/internal/v1/classifications", content=b"x" * 65537).status_code == 413
        app.state.capacity.acquire()
        try:
            assert (
                client.post(
                    "/internal/v1/classifications", json={"text": "문자"}, headers={"X-Service-Token": TOKEN}
                ).status_code
                == 429
            )
        finally:
            app.state.capacity.release()


def test_empty_corpus_abstains_without_provider(app):
    with TestClient(app) as client:
        r = client.post(
            "/internal/v1/rag/answers",
            json={"question": "무엇을 해야 하나요?"},
            headers={"X-Service-Token": TOKEN},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "INSUFFICIENT_EVIDENCE"
        assert r.json()["chunkIds"] == []


def test_missing_model_returns_503():
    app = create_app(Settings(service_token=TOKEN), Services(MissingClassifier(), None, Provider(), False))
    with TestClient(app) as client:
        assert (
            client.post(
                "/internal/v1/classifications", json={"text": "문자"}, headers={"X-Service-Token": TOKEN}
            ).status_code
            == 503
        )
