from finguard_ai.serve import load_settings


def test_explicit_env_does_not_borrow_parent_api_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-parent-key")
    monkeypatch.setenv("AI_OPENAI_API_KEY", "also-unrelated")
    env = tmp_path / ".env"
    env.write_text(
        "AI_SERVICE_TOKEN="
        + "a" * 32
        + "\nAI_PROVIDER=openai\nAI_CLASSIFIER_MODE=openai\nAI_OPENAI_API_KEY=\n"
    )
    assert load_settings(env).openai_api_key is None
    env.write_text(env.read_text().replace("AI_OPENAI_API_KEY=\n", "AI_OPENAI_API_KEY=explicit-test-key\n"))
    assert load_settings(env).openai_api_key.get_secret_value() == "explicit-test-key"
