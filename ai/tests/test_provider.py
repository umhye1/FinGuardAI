import json

import httpx
import pytest

from finguard_ai.config import Settings
from finguard_ai.errors import ServiceUnavailable
from finguard_ai.provider import GeminiProvider


def settings():
    return Settings(service_token="s" * 32, gemini_api_key="test-provider-key", generation_model="test-model")


def response(payload, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps(payload)}]}}]}


def test_request_is_masked_and_schema_is_sent():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response({"label": "PHISHING", "decision": "FLAG"}))

    provider = GeminiProvider(
        settings(), httpx.Client(transport=httpx.MockTransport(handler), base_url="https://test/")
    )
    result = provider.classify("010-1234-5678로 연락해서 계좌 이체해주세요")
    assert result.label == "PHISHING"
    body = json.loads(requests[0].content)
    assert "010-1234-5678" not in requests[0].content.decode()
    assert "responseJsonSchema" in body["generationConfig"]
    assert requests[0].headers["x-goog-api-key"] == "test-provider-key"
    provider.close()


@pytest.mark.parametrize(
    "payload",
    [
        response({"label": "NORMAL", "decision": "FLAG"}),
        response({"label": None, "decision": "ABSTAIN"}, "MAX_TOKENS"),
        {"candidates": []},
    ],
)
def test_invalid_generation_is_rejected(payload):
    provider = GeminiProvider(
        settings(),
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
            base_url="https://test/",
        ),
    )
    with pytest.raises(ServiceUnavailable):
        provider.classify("질문")
    provider.close()


@pytest.mark.parametrize("vector", [[1, 2], [0] * 768, [float("inf")] * 768])
def test_invalid_embedding_vectors(vector):
    # Raw content is used to exercise non-finite provider JSON handling.
    provider = GeminiProvider(
        settings(),
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, content=json.dumps({"embeddings": [{"values": vector}]}))
            ),
            base_url="https://test/",
        ),
    )
    with pytest.raises(ServiceUnavailable):
        provider.embed(["문단"], "RETRIEVAL_DOCUMENT")
    provider.close()


def test_embedding_shape_task_and_normalization():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"embeddings": [{"values": [2.0] + [0.0] * 767}]})

    provider = GeminiProvider(
        settings(), httpx.Client(transport=httpx.MockTransport(handler), base_url="https://test/")
    )
    vector = provider.embed(["문단"], "RETRIEVAL_DOCUMENT")[0]
    assert vector[0] == 1.0
    assert requests[0]["requests"][0]["embedContentConfig"]["outputDimensionality"] == 768
    provider.close()


def test_provider_timeout_maps_to_service_unavailable():
    def timeout(request):
        raise httpx.ReadTimeout("private payload must not escape", request=request)

    provider = GeminiProvider(
        settings(), httpx.Client(transport=httpx.MockTransport(timeout), base_url="https://test/")
    )
    with pytest.raises(ServiceUnavailable, match="PROVIDER_UNAVAILABLE"):
        provider.classify("질문")
    provider.close()
