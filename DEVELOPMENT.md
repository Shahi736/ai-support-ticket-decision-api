# Development Notes

This documents how the project was built, step by step, including the real issues hit along the way and how they were resolved. AI coding agent (Claude) usage is noted inline where relevant, per the assignment's evaluation criteria.

## 1. Project Setup

Started with the suggested repo structure: `src/` for backend modules, `knowledge_base/` for policy docs, `data/` for test cases, `tests/` for test/eval scripts, and `streamlit_app.py` at the root.

Set up a virtual environment and installed dependencies from `requirements.txt` (FastAPI, SQLAlchemy, Pydantic, python-jose, bcrypt, streamlit, google-generativeai, python-dotenv, pytest, httpx).

## 2. Database Layer (`src/database.py`)

Defined three SQLAlchemy models matching the required schema:
- `User` — id, email (unique), password_hash, created_at
- `Ticket` — id, user_id (FK), message, created_at
- `Decision` — id, ticket_id (FK), action, reason, confidence, sources (stored as JSON string), created_at

Used SQLite with `check_same_thread=False` since FastAPI can access the DB across threads. `init_db()` creates all tables on app startup.

## 3. Authentication (`src/auth.py`, `src/deps.py`)

Implemented password hashing with `bcrypt` directly (switched from an earlier `passlib` approach after hitting a `bcrypt.__about__` compatibility error between `passlib` and newer `bcrypt` versions — passlib was abandoned in favor of calling `bcrypt` directly).

JWT creation/validation uses `python-jose`, with the secret and algorithm loaded from `.env`. `get_current_user` in `deps.py` is a FastAPI dependency that decodes the bearer token and loads the matching user, raising 401 if the token is missing/invalid/expired or the user no longer exists.

**Debugging note:** hit a persistent issue where `uvicorn --reload` was stuck in an infinite reload loop, caused by the file watcher monitoring the entire project directory including `.venv` — every time a library's own files were touched (e.g. during import), it triggered a reload. Fixed by scoping the watcher: `uvicorn src.api:app --reload --reload-dir src`.

## 4. Core API Endpoints (`src/api.py`, `src/schemas.py`)

Built `/register`, `/login`, `/me` first and tested each manually via Swagger UI (`/docs`) before moving on — confirmed 201/200/401 responses at each step, including deliberately testing wrong-password and duplicate-email cases.

Also hit and fixed several PowerShell-specific quirks while testing manually: `curl` aliasing to `Invoke-WebRequest` (needed `curl.exe` for real curl syntax), and wildcard glob expansion breaking `--reload-exclude ".venv/*"` (worked around by scoping `--reload-dir` instead, as above).

## 5. Knowledge Base (`knowledge_base/*.md`)

Wrote four policy documents (refunds, returns, shipping, damaged goods) with concrete, specific rules and thresholds (e.g. "orders above ₹2,000 require photo evidence," "reports must be made within 7 days") so the LLM would have unambiguous grounding to cite rather than vague policy language it would have to guess around.

## 6. RAG Pipeline (`src/retrieval.py`)

Implemented a lightweight local RAG pipeline, avoiding a hosted vector DB per the assignment's guidance:
- Load all `.md` files from `knowledge_base/`
- Split into ~500-character overlapping chunks
- Embed each chunk with Gemini's embedding model, cache to `kb_embeddings.pkl` (numpy array + pickle)
- At query time, embed the incoming ticket and rank cached chunks by cosine similarity

**Debugging note:** went through three different embedding model names (`text-embedding-004`, `embedding-001`, before landing on `gemini-embedding-001`) after repeated 404s — resolved by calling `genai.list_models()` directly against my API key to see which models actually supported `embedContent`, rather than continuing to guess from documentation that didn't match the SDK version installed.

Verified retrieval manually by running `retrieval.py` standalone and confirming a damage-related query correctly surfaced `damaged_goods.md` chunks as the top matches before wiring it into the decision pipeline.

## 7. AI Decision Pipeline (`src/decision.py`, updated `src/schemas.py`)

Built `make_decision()`: retrieves top-3 policy chunks for a ticket, builds a prompt instructing the LLM to decide strictly from the provided context, calls Gemini, and parses/validates the JSON response against an `AIDecision` Pydantic schema (with `action` constrained to a fixed `Literal` set of valid actions).

If the LLM's response is malformed or fails validation, the pipeline fails safe to `NEEDS_MORE_INFORMATION` rather than persisting a guessed or invalid decision — this was a specific requirement from the assignment ("the system must not invent an answer when information is insufficient").

**Debugging note:** the decision model name (`gemini-2.5-flash`) also became unavailable partway through development ("no longer available to new users") — switched to `gemini-3.6-flash` after checking `list_models()` again.

Verified manually by running `decision.py` standalone against a sample damage ticket and confirming the output correctly cited the ₹2,000 threshold from `damaged_goods.md`.

## 8. Wiring Up `/tickets` Endpoints

Added `POST /tickets`, `GET /tickets`, `GET /tickets/{id}` to `api.py`. The single-ticket endpoint deliberately returns 404 (not 403) when a ticket exists but belongs to another user — this avoids confirming to an unauthorized caller that the ticket exists at all.

Tested end-to-end manually: created a ticket via curl, confirmed the AI decision was generated and persisted correctly, then registered a second user (Bob) and confirmed his token got a 404 when trying to access the first user's (Alice's) ticket — proving the authorization requirement before writing it as an automated test.

## 9. Streamlit Frontend (`streamlit_app.py`)

Built three pages using `st.session_state` to hold the JWT across reruns:
- **Login/Register** — tabs for each, calling the backend via `requests`
- **New Decision** — submits a ticket, displays action/confidence/reason/sources
- **History** — lists past tickets in expandable sections, each showing its decision

Streamlit communicates with the backend purely over HTTP (never touches the database directly), per the assignment's requirement.

## 10. Automated Tests (`tests/test_auth.py`)

Wrote tests covering registration, login (success and failure), `/me` auth enforcement, and — the specific case required by the assignment — that Alice's token cannot retrieve Bob's ticket.

**Debugging note:** the ticket-related tests initially called the real Gemini API and intermittently failed with `429 RESOURCE_EXHAUSTED` (free tier: 5 requests/minute), especially after a lot of manual testing had already used up the quota. Fixed by mocking `make_decision` in the ticket tests with `unittest.mock.patch`, so authorization logic is tested independently of a live, rate-limited external API — a more correct approach for unit testing anyway.

Also had to add a `pytest.ini` with `pythonpath = .` after hitting `ModuleNotFoundError: No module named 'src'` when running pytest from the project root.

## 11. Evaluation Script (`tests/evaluate.py`, `data/tickets.csv`)

Wrote 20 sample test tickets spanning all four policy areas, including deliberately ambiguous cases meant to test the `NEEDS_MORE_INFORMATION` fallback (e.g. a shipment delayed by an unspecified amount, a refund near the manager-approval threshold with no confirmation stated).

The evaluation script runs each ticket through the real pipeline and reports accuracy in the format specified by the assignment (`N test cases / Correct: X / Accuracy: Y%`).

**Debugging note:** running all 20 cases back-to-back hit the same free-tier rate limit repeatedly, including a run where every single case failed even with retry/backoff logic — indicating the *daily* quota, not just the per-minute one, had been exhausted from cumulative testing earlier in the day. Added a 20-second delay between cases and a retry-with-backoff wrapper; the script also logs a case as `ERROR` and continues rather than crashing the whole run if retries are exhausted.

## AI Coding Agent Usage Summary

Claude (Anthropic) was used throughout as a coding agent for drafting new modules, debugging error messages, and explaining SDK/environment issues. Every piece of code was run and verified by me personally — manual endpoint testing before automation, standalone script runs before wiring into the API, and reading actual tracebacks to diagnose issues (model name mismatches, a `reload` loop, PowerShell quoting, rate limits, a `DDECISION_MODEL` typo caught from a `NameError`) rather than accepting fixes without understanding them.

## What I Would Do Differently With More Time

- Add retry/backoff directly inside `decision.py`/`retrieval.py`, not just the evaluation script, so the live app degrades gracefully under rate limits instead of surfacing a raw 429 to the user.
- Cache query embeddings for repeated/similar ticket messages to reduce API calls.
- Add dedicated tests for ticket creation/listing (currently covered indirectly via the authorization tests).
- Move `@app.on_event("startup")` to FastAPI's newer lifespan event handlers.