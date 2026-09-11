from pathlib import Path

import httpx
import pytest
from test_rag import Provider, Repository

from finguard_ai.config import Settings
from finguard_ai.errors import ServiceUnavailable
from finguard_ai.live_evaluation import BudgetProvider, preflight, run_cases
from finguard_ai.schemas import GeneratedAnswer

MANIFEST = Path(__file__).parents[1] / "data/official/manifest.json"


def test_preflight_has_no_network_and_does_not_expose_secrets():
    settings = Settings(service_token="x" * 32, database_url="postgresql://user:SECRET@localhost/db")
    result = preflight(settings, MANIFEST, 2)
    assert result["status"] == "NOT_RUN"
    assert result["providerCalls"] == 0
    assert result["missingSettings"] == ["AI_GEMINI_API_KEY", "AI_GENERATION_MODEL"]
    assert "SECRET" not in str(result)


def test_budget_stops_before_extra_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    p = BudgetProvider(
        Settings(service_token="x" * 32, gemini_api_key="test"),
        1,
        httpx.Client(transport=httpx.MockTransport(handler), base_url="https://test/"),
    )
    p._post("test", {})
    with pytest.raises(ServiceUnavailable, match="CALL_LIMIT"):
        p._post("test", {})
    assert len(calls) == 1
    p.close()


def test_live_report_marks_semantic_review_pending_instead_of_claiming_accuracy():
    repo = Repository()
    provider = Provider(GeneratedAnswer(status="ANSWERED", answer="test answer", chunkIds=[1]))
    results = run_cases(repo, provider, Settings(service_token="x" * 32, generation_model="test"), 1)
    assert results[0]["status"] == "ANSWERED"
    assert results[0]["requiredCitationCoverage"] == 1
    assert results[0]["semanticReviewStatus"] == "PENDING"
    assert results[0]["citations"]["1"]["metadata"]["source_url"].startswith("https://www.fsc.go.kr/")


def test_failure_report_does_not_leak_exception_text():
    class FailingProvider:
        def embed(self, *args):
            raise ServiceUnavailable("SECRET credentials and raw request")

    result = run_cases(Repository(), FailingProvider(), Settings(service_token="x" * 32), 1)[0]
    assert result["status"] == "FAILED"
    assert "SECRET" not in str(result)
    assert "answer" not in result


@pytest.mark.integration
def test_evaluation_schema_is_cleaned_on_failure():
    import os

    import psycopg

    from finguard_ai.live_evaluation import evaluation_repository

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    assert url.endswith("/finguard_ai_test")
    settings = Settings(service_token="x" * 32, database_url=url)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        before = conn.execute("SELECT nspname FROM pg_namespace ORDER BY nspname").fetchall()
    with pytest.raises(RuntimeError, match="simulated"):
        with evaluation_repository(
            settings, Path(__file__).parents[2] / "backend/src/main/resources/db/migration"
        ) as repo:
            with repo.pool.connection() as conn:
                assert conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"] == 0
            raise RuntimeError("simulated")
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT nspname FROM pg_namespace ORDER BY nspname").fetchall() == before
