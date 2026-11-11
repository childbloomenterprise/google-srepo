# ClaimBack

ClaimBack is a phone-first prototype that reviews Indian health-insurance deductions against a
curated IRDAI rulebook, prepares first-person appeal drafts, and tracks the escalation path. Its
analysis, document extraction, voice transcription, and letter generation use the Google Gemini
API. It is an application prototype, not legal advice or legal representation.

## Run locally

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export GEMINI_API_KEY="your-key"
uvicorn app.main:app --reload --port 8080
```

During development only, the app can read `/home/ubuntu/.gemini_key` when `GEMINI_API_KEY` is not
set. Do not place keys in source control. `CB_MODEL_ANALYSIS` and `CB_MODEL_FAST` configure the
analysis/letters and extraction/voice models respectively. Defaults are `gemini-4-argon` and
`gemini-3.8-flash`; analysis retries with the fast model if the analysis model errors.

SQLite is the default store at `data/claimback.db`. Set `CB_DB_PATH` to use a different file. Set
`CB_STORE=firestore` to select the optional Firestore-backed adapter (requires Google Cloud
credentials and `google-cloud-firestore`).

## Tests and demo documents

```bash
python scripts/make_demo_docs.py
pytest
ruff check app
```

The demo documents are synthetic and visibly labelled. The `/api/demo/partial-cut` and
`/api/demo/ped-rejection` endpoints call Gemini on those documents; they do not return canned
verdicts. `/dashboard` summarizes stored prototype cases and labels the future BigQuery export.

## Deploy to Cloud Run

Build and deploy from this directory. Create the `GEMINI_API_KEY` secret in Secret Manager first:

```bash
gcloud run deploy claimback --source . --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest
```

The container listens on Cloud Run's `$PORT` (default 8080). Cloud Run deployments should attach
persistent/managed storage or select an appropriate hosted store; the default local SQLite file is
intended for a prototype container.

## API outline

- `POST /api/cases` — multipart `files[]`, optional `notes` and `lang` (`en`/`hi`)
- `POST /api/demo/{partial-cut|ped-rejection}` — real Gemini document analysis for a demo
- `GET /api/cases/{id}` / `POST /api/cases/{id}/letters`
- `POST /api/voice` — raw webm/ogg/wav audio body
- `PATCH /api/cases/{id}/status` — tracker event
- `GET /api/dashboard` and `GET /healthz`

ClaimBack prepares drafts for a policyholder to send in their own name. It does not appear before
courts and does not provide legal advice.
