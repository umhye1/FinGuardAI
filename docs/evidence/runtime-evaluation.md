# Runtime integration and evaluation (#25)

## Local migration

`DatabaseMigrationTool` is an explicit operator CLI, not application startup auto-baselining.
Stop application writers, take a private `pg_dump -Fc` backup, restore it into a separate database,
and compare data before using `--baseline-v1`. `FG_BACKUP_RESTORE_VERIFIED=true` acknowledges
operator verification; it does not perform or prove a backup by itself.

From `backend`, with `FG_MIGRATION_URL`, `FG_MIGRATION_USER`, `FG_MIGRATION_PASSWORD` set:

```sh
FG_BACKUP_RESTORE_VERIFIED=true ./gradlew migrateDatabase --args=--baseline-v1
```

The tool compares V1 columns and primary/unique/foreign keys, rejects duplicate chunk indices,
repairs known legacy sequence defaults and two FK cascade actions, then explicitly baselines V1
and applies V2–V7. Unexpected layouts are rejected. Sequence counters only advance and are not
transactionally rolled back. This is a tool for the verified legacy schema, not arbitrary DB conversion.
After a failed migration, inspect Flyway state and restore the verified backup to a separate DB
before deciding how to recover; do not enable automatic baseline or delete existing data.

On 2026-09-11 the local `finguard` database was backed up and restored to
`finguard_restore_issue25`. Counts and ordered row fingerprints matched for all eight legacy tables.
Both restored and original databases migrated to V7; the original column data matched after migration.
The private dump is in ignored `ai/.artifacts/backups/issue25/finguard-before.dump`.
The backend subsequently started with Hibernate validation and returned health `UP`.

The five reviewed source summaries were imported as document IDs 9–13 in this local DB.
A second import returned the same IDs. These are reviewed summaries of official pages,
not complete originals. Existing private documents were not sent to a model.

## OpenAI configuration

Copy `ai/.env.example` to ignored `ai/.env`, set the key and DB connection locally.
`AI_PROVIDER=openai` selects OpenAI Responses structured JSON and 768-dimensional
`text-embedding-3-small` embeddings; the example generation model is `gpt-4.1-mini`.
`AI_CLASSIFIER_MODE=local` keeps the local classifier; `openai` selects API classification.
`AI_PROVIDER=gemini` remains supported with explicit Gemini models.
`OPENAI_API_KEY` is also accepted; environment variables override dotenv values.
Use the command below to exclude an unrelated inherited API key when explicitly testing a file.
Service/indexing CLI processes require exported settings; only the evaluation CLI accepts `--env-file`.
Model changes require reindexing: existing vectors are filtered by embedding model.

## Bounded live evaluation

From repository root:

```sh
env -u OPENAI_API_KEY -u AI_OPENAI_API_KEY ai/.venv/bin/python -m finguard_ai.live_evaluation \
  --env-file ai/.env --manifest ai/data/official/manifest.json \
  --max-cases 8 --output ai/.artifacts/live-evaluation.json
```

Without `--execute`, this only validates configuration and corpus with zero provider calls.
Add `--execute` to call paid APIs. The DB must have pgvector installed in public and allow temporary
schema creation. Evaluation creates a unique schema, applies migrations there, imports the five
public summaries, indexes four guidance records, and drops its schema even after failures.
It does not index or evaluate pre-existing user documents. Request attempts are bounded by
`5 + 2 * max_cases`; there are no automatic retries. Existing output files are never overwritten.

Reports retain answers, citation snapshots, required-document coverage, vector baseline/hybrid
candidate IDs, latency, failures and provider attempt count. Candidate diagnostics are not a
ranking-quality score. Answer semantics remain `PENDING` until reviewed by a person; successful
API calls or matching citations alone do not establish accuracy. The offline evaluation from #23
remains a separate TF-IDF experiment, not a historical live-provider before/after measurement.

API contracts: [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create).

## Validation result

- Backend: 25 tests passed, including legacy migration/data preservation/rejection cases.
- AI: 62 tests passed, including real pgvector integration, isolated-schema cleanup,
  OpenAI request/response contracts, refusal/truncation rejection, and bounded-call behavior.
- Local backend startup and health check passed after V7 migration.
- Live OpenAI evaluation was attempted using the explicit local dotenv key, excluding inherited keys.
  The first embedding request failed with HTTP 401. No generated answers or live accuracy results
  were obtained, and local public-corpus embeddings remain unpopulated by this evaluation.
  The sanitized report is `live-attempt-issue25.json`. Re-run with a valid local API key.
