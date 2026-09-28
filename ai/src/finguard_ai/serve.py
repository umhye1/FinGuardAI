"""Explicit dotenv launcher; never evaluates shell code or prints secrets."""

import argparse

import uvicorn

from finguard_ai.config import load_settings
from finguard_ai.main import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="ai/.env")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-unconfigured",
        action="store_true",
        help="Start for local diagnostics without a provider key; AI calls still fail explicitly",
    )
    args = parser.parse_args()
    config = load_settings(args.env_file)
    if config.classifier_mode != "local":
        key = config.openai_api_key if config.provider == "openai" else config.gemini_api_key
        if (not key or not key.get_secret_value().strip()) and not args.allow_unconfigured:
            parser.error("Selected AI provider key is empty. Set it in the local env file.")
    uvicorn.run(create_app(config), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
