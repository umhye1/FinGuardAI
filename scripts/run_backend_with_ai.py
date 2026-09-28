"""Run from repo root with ai/.venv/bin/python; credentials remain in process env."""
import os
import subprocess
from pathlib import Path
from dotenv import dotenv_values
root = Path(__file__).resolve().parents[1]
values = dotenv_values(root / 'ai/.env')
token = values.get('AI_SERVICE_TOKEN', '')
if len(token) < 32:
    raise SystemExit('Set AI_SERVICE_TOKEN (32+ characters) in ai/.env first.')
env = os.environ.copy()
env.update(AI_ENABLED='true', AI_SERVICE_TOKEN=token, AI_SERVER_URL='http://127.0.0.1:8000',
           AI_TIMEOUT_MS='25000', AI_RAG_TIMEOUT_MS='60000')
raise SystemExit(subprocess.call([str(root / 'backend/gradlew'), '-p', str(root / 'backend'), 'bootRun'],env=env))
