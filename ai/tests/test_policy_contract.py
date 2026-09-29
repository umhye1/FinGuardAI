"""Prevent independently passing Python/Java tests from hiding a policy-version mismatch."""

import json
import re
from pathlib import Path

from finguard_ai.evidence import CLARIFICATION, POLICY_VERSION


def test_python_java_and_documented_contract_agree():
    root = Path(__file__).parents[2]
    java = (root / "backend/src/main/java/com/finguard/ai/service/RagClient.java").read_text()
    version = re.search(r'EVIDENCE_POLICY_VERSION = "([^"]+)"', java).group(1)
    assert version == POLICY_VERSION
    assert CLARIFICATION in java
    writer = (root / "backend/src/main/java/com/finguard/chat/service/ChatAnswerWriter.java").read_text()
    assert "RagClient.EVIDENCE_POLICY_VERSION.equals(result.policyVersion())" in writer
    contract = json.loads((root / "contracts/internal-ai.openapi.json").read_text())
    assert f"policyVersion={POLICY_VERSION}" in json.dumps(contract)
