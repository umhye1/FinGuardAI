import json

import httpx
import pytest

from finguard_ai.config import Settings
from finguard_ai.errors import ServiceUnavailable
from finguard_ai.provider import OpenAIProvider, create_provider
from finguard_ai.schemas import GeneratedAnswer


def provider(handler):
    return create_provider(
        Settings(service_token="x" * 32, provider="openai", openai_api_key="secret"),
        httpx.Client(base_url="https://test/", transport=httpx.MockTransport(handler)),
    )


def test_responses_schema_auth_and_validation():
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/responses"
        assert request.headers["Authorization"] == "Bearer secret"
        assert payload["store"] is False
        schema = payload["text"]["format"]["schema"]
        assert set(schema["required"]) == {"status", "answer", "chunkIds"}
        assert schema["additionalProperties"] is False
        assert "default" not in schema["properties"]["answer"]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"status": "ANSWERED", "answer": "test", "chunkIds": [1]}),
                            }
                        ],
                    }
                ],
            },
        )

    p = provider(handler)
    assert isinstance(p, OpenAIProvider)
    assert p.settings.embedding_model == "text-embedding-3-small"
    assert p.generate("system", {}, GeneratedAnswer).chunkIds == [1]
    p.close()


@pytest.mark.parametrize(
    "data",
    [
        {"status": "incomplete"},
        {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
    ],
)
def test_refusal_and_truncation_fail_closed(data):
    p = provider(lambda r: httpx.Response(200, json=data))
    with pytest.raises(ServiceUnavailable, match="INVALID_GENERATION"):
        p.generate("system", {}, GeneratedAnswer)
    p.close()


def test_embedding_order_dimensions_normalization_and_bad_indices():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["dimensions"] == 768
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 2] + [0] * 766},
                    {"index": 0, "embedding": [2] + [0] * 767},
                ]
            },
        )

    p = provider(handler)
    assert p.embed(["one", "two"], "RETRIEVAL_DOCUMENT")[0] == [1] + [0] * 767
    with pytest.raises(ServiceUnavailable, match="INVALID_EMBEDDING"):
        p.embed(["one"], "RETRIEVAL_QUERY")
    p.close()


def test_http_error_is_sanitized():
    p = provider(lambda r: httpx.Response(401, json={"secret": "credential"}))
    with pytest.raises(ServiceUnavailable, match="^PROVIDER_UNAVAILABLE$"):
        p.embed(["one"], "RETRIEVAL_QUERY")
    p.close()
