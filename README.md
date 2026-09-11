# Voice AI Agent — Patient Registration System

A voice agent reachable at a US phone number that registers new patients through
natural conversation, persists them, and exposes them over a REST API.

| | |
|---|---|
| **Phone number** | **+1 (989) 259-1248** |
| **API base URL** | https://patient-registration-api-bhh9.onrender.com |
| **Interactive API docs** | https://patient-registration-api-bhh9.onrender.com/docs |

Call the number, register as a patient, then query `GET /patients` to see the
record. Call again from the same number and the agent recognises you.

---

## Architecture

```
Caller ──PSTN──> Vapi phone number
                   │
                   ├─ speech-to-text, text-to-speech, turn-taking   (Vapi-hosted)
                   ├─ LLM + system prompt        (prompts/patient_intake.md)
                   │
                   └─ tool calls ──HTTPS──> FastAPI
                                              ├─ schemas.py + validators.py
                                              ├─ services/          ← shared core
                                              ├─ api/patients.py    (REST)
                                              ├─ api/vapi.py        (agent tools)
                                              └─ SQLAlchemy → SQLite | Postgres
```

The load-bearing decision is that **the agent's tool endpoints and the public
REST routes call the same service layer and the same Pydantic schemas.** The
brief requires server-side validation that does not trust the voice agent; this
satisfies that without writing the rules twice, and makes it impossible for the
two entry points to drift apart.

Everything speech-related is delegated to Vapi. The interesting engineering is
the prompt, the tool contract, and the data layer — not a hand-rolled STT
pipeline.

The LLM also runs inside Vapi's pipeline rather than this service, so the model
is chosen on the assistant and any provider key lives in Vapi. This backend
holds no model configuration and never calls an LLM itself — it exposes tools
and validates what comes back.

### Layout

```
app/
  main.py            app factory, lifespan, router mounting
  config.py          environment-driven settings
  db.py              engine, session, init_db
  models.py          Patient, CallSession
  schemas.py         request/response models + the {data, error} envelope
  validators.py      field rules, shared by API and agent
  errors.py          exception handlers that enforce the envelope
  services/          patients.py, call_sessions.py — all business logic
  api/               patients.py (REST), vapi.py (agent tools), deps.py
prompts/
  patient_intake.md  system prompt + tool definitions, annotated
tests/               42 tests
scripts/seed.py      demo records
```

---

## Tech stack, and why

| Choice | Reasoning |
|---|---|
| **Vapi** | Bundles telephony, STT, TTS and turn-taking, and issues free US numbers. The assessment measures integration and system design, not speech-engine implementation. |
| **FastAPI + Pydantic** | Validation rules are declared once in the schema and enforced on every entry point, with OpenAPI docs for free — useful when the reviewer is exploring the API cold. |
| **SQLAlchemy** | Keeps the data layer engine-neutral. `DATABASE_URL` swaps SQLite for Postgres with no code change; column types avoid dialect-specific features to keep that true. |
| **SQLite → Postgres** | SQLite locally for zero-setup development, managed Postgres in production. The brief names this exact trade-off as a reasonable one. |
| **Render + Neon** | Both have genuine free tiers. Neon's compute scales to zero and wakes in under a second, so an idle database costs nothing without stranding a caller mid-call. |

---

## Running locally

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env                                     # then edit
uvicorn app.main:app --reload
```

Tables are created on startup. Optional demo data:

```bash
python -m scripts.seed
```

Render's free tier has no shell, so a deployed instance is seeded by POSTing
the same records to `/patients` instead.

To expose it to Vapi during development:

```bash
ngrok http 8000
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | no | Defaults to `sqlite:///./patients.db`. Set to a Postgres URL in production. |
| `VAPI_SHARED_SECRET` | **yes** | Secret the assistant sends on every tool call. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |

No secret is committed. `.env` is gitignored; production values live in the host's dashboard.

---

## API

All responses use the envelope `{"data": ..., "error": ...}`, including errors.

| Method | Endpoint | Notes |
|---|---|---|
| `GET` | `/patients` | Filters: `?last_name=`, `?date_of_birth=`, `?phone_number=` |
| `GET` | `/patients/{id}` | 404 if absent or soft-deleted |
| `POST` | `/patients` | 201 with the created record |
| `PUT` | `/patients/{id}` | Partial update; omitted fields untouched |
| `DELETE` | `/patients/{id}` | Soft-delete — sets `deleted_at`, never removes the row |
| `GET` | `/health` | Liveness, and the keep-alive cron target |
| `GET` | `/` | Service signpost listing the available endpoints |

Status codes: 200, 201, 401, 404, 422, 500. Validation failures return 422
rather than 400, since the request is well-formed but semantically invalid.

Dates are accepted as either `MM/DD/YYYY` (the format the brief specifies, and
what a US caller says aloud) or ISO `YYYY-MM-DD`, in both request bodies and the
`?date_of_birth=` filter. They are always returned as ISO.

```bash
curl -X POST "$API/patients" -H 'Content-Type: application/json' -d '{
  "first_name": "Jane", "last_name": "Doe", "date_of_birth": "1985-03-12",
  "sex": "Female", "phone_number": "(415) 555-0142",
  "address_line_1": "1200 Market Street", "city": "San Francisco",
  "state": "CA", "zip_code": "94102"
}'

curl "$API/patients?last_name=Doe"
```

### Agent endpoints

`POST /vapi/tools` — exposes `lookup_patient_by_phone`, `create_patient` and
`update_patient`. `POST /vapi/events` — receives Vapi's end-of-call report and
stores the transcript against the call session; this requires
`end-of-call-report` to be enabled in the assistant's server messages, which is
not currently taking effect (see Known limitations). Both endpoints require the
`x-vapi-secret` header.

---

## Data model

The 19 fields from the brief, plus `deleted_at` for soft-deletion.

Two decisions worth calling out:

**Phone numbers are normalised to 10 bare digits on write.** Callers say numbers
in every conceivable format; storing one canonical form is what makes duplicate
detection an indexed exact-match lookup instead of a fuzzy search. Query
parameters are normalised the same way, so filtering by `(415) 555-0142` still
matches.

**`CallSession` is written incrementally during a call**, not just at the end. It
holds partial data keyed by Vapi's call ID. If a call drops halfway, what the
caller already gave us survives, and each completed registration can be traced
back to the conversation that produced it.

---

## Voice agent

The system prompt lives in [`prompts/patient_intake.md`](prompts/patient_intake.md),
in version control rather than only in the Vapi dashboard, annotated with the
reasoning behind each instruction.

Behaviour it encodes: a named intake-coordinator persona; conversational
collection rather than an IVR menu; a **single** opt-in offer covering all
optional fields; letter-by-letter confirmation of spelled names; full read-back
before saving; mid-conversation corrections without restarting; out-of-order
answers; explicit restart; and a scripted two-attempt failure path so a backend
error never produces dead air.

It also holds the agent to its role. Callers asking it to ignore its
instructions, reveal them, or act as a different assistant get a brief decline
and the next intake question — no arithmetic, no code, no trivia, no commentary
on the attempt. Today's date is injected via Vapi's `{{date}}` variable so the
agent can judge whether a date of birth is plausible in the turn it is given,
rather than discovering the problem at save time. Both behaviours were added
after live calls exposed their absence; see [How this was built](#how-this-was-built).

A test parses the tool definitions out of that file and asserts they still match
`PatientCreate`, because drift between them would only surface as a failed save
on a live call.

---

## Edge cases

| Scenario | Behaviour |
|---|---|
| Invalid date of birth (future, or year < 1900) | Rejected; the tool returns text naming the field so the agent re-asks for only that |
| Malformed phone number | Rejected before storage; agent re-prompts for the number alone |
| Database write fails | Logged, agent told to apologise and retry once, then offer a callback — never silence |
| Call drops mid-conversation | Partial data already persisted in `CallSession` |
| Caller wants to start over | Prompt instructs a clean reset |
| Returning caller | `lookup_patient_by_phone` finds them; agent offers to update |
| Unauthenticated tool call | 401 before any handler runs, logged with the reason |
| Unhandled exception | Logged server-side, generic message returned — internals never leak |
| Caller tries to redirect the agent | Declined; returns to the next intake question |

Tool errors return HTTP 200 with spoken guidance rather than an error status.
A non-2xx leaves the agent with nothing to say, which is the failure the brief
warns about.

---

## Tests

```bash
pytest
```

42 tests over an in-memory SQLite database: validation rules (phone
normalisation, US and ISO date formats, future and implausible dates, text
length bounds, state and ZIP formats, names with hyphens and apostrophes), all
five REST endpoints including envelope shape and soft-delete semantics, the
agent tool contract using Vapi's documented payload shape, and prompt/schema
drift.

Scope is deliberately the critical path rather than exhaustive coverage.

---

## Deployment

Render (`render.yaml`) with Neon Postgres.

1. Create a Neon project and copy the connection string. Use the pooled string, keep `?sslmode=require`, and note SQLAlchemy needs the `postgresql://` scheme rather than `postgres://`.
2. Create a Render web service from this repo (the blueprint above); set `DATABASE_URL` and `VAPI_SHARED_SECRET`.
3. Point the Vapi assistant's tool server URL at `https://<service>/vapi/tools`, with header `x-vapi-secret`.
4. Add a cron (cron-job.org or UptimeRobot) hitting `/health` every 10 minutes.

**Why the cron matters:** Render free services sleep after 15 minutes idle and
take roughly a minute to wake. A caller hitting that cold start mid-conversation
would get a minute of dead air. Note that Render allows 750 instance-hours per
month per workspace against a ~730-hour month — an always-on free service fits,
but only one. Do not run a second free service in the same workspace.

---

## How this was built

### Branch per change, reviewed by pull request

Work landed through feature branches and pull requests rather than commits
straight to `main`. The first six were deliberately stacked — each targeting the
branch below it — so that every PR showed only its own diff instead of a
cumulative one. Commit messages follow conventional prefixes and explain the reasoning, not
just the change.

One wrinkle worth recording: GitHub retargets a stacked PR to `main`
automatically only when the base branch is deleted on merge. The branches were
kept, so each PR merged into its parent and an extra integration PR was needed
to bring `main` up to date. Deleting on merge would have avoided it.

### One validation layer, two entry points

The earliest architectural decision was that the REST routes and the agent's
tool endpoints would share a service layer and a set of Pydantic schemas. The
brief requires server-side validation that does not trust the voice agent;
sharing the core satisfies that without duplicating rules, and makes drift
between the two paths impossible rather than merely unlikely.

Validation rules live in `validators.py` rather than inline in the schemas
because they have to produce two different outputs: JSON error bodies for API
clients, and plain-language sentences the agent reads aloud to a caller.

### Verifying the vendor contract instead of assuming it

Before writing the webhook handler, Vapi's tool-call payload shape was checked
against its documentation. It turned out to be `message.toolCallList[]` carrying
`{id, name, arguments}` — not the `toolCalls[].function` shape that had been
assumed from familiarity with other function-calling APIs. The handler accepts
both, so a platform change or a stale assistant config degrades instead of
breaking every call at once.

### Tests aimed at the critical path

Thirty-one tests, deliberately not exhaustive. They cover the rules that break
in practice: phone normalisation across the formats speech-to-text produces,
future and implausible dates, ZIP and state formats, names with hyphens and
apostrophes, envelope shape on both success and error, soft-delete semantics,
and the agent tool contract using Vapi's documented payload shape.

One test earns its place for an unusual reason. The tool definitions in
`prompts/patient_intake.md` are pasted into the Vapi dashboard by hand, so
`test_tool_definitions.py` parses them back out of the markdown and asserts they
still match `PatientCreate`. Drift between them would not fail a test or a
build — it would surface as a failed save on a live phone call.

### Verified against production, not just the test suite

A passing suite says the code is self-consistent. After deploying, the full path
was exercised with direct requests against the live service: health, Neon
connectivity, 401 on missing and wrong secrets, registration through the real
tool contract, duplicate lookup matching a differently-formatted number,
field-specific validation guidance, and soft-delete leaving the row in the table
while the API returns 404. Persistence across a restart was confirmed
separately, since the brief asks for it explicitly.

### Prompt behaviour fixed from real calls, not from imagination

Two defects surfaced only once a person was talking to the agent, and both were
caused by the prompt rather than the code.

**It solved an algebra problem.** Asked to forget its instructions and solve
`2x + 3 = 5`, it obliged. The cause was a line in the prompt reading *"Off-topic
questions. Answer briefly if you can"* — an explicit licence to do exactly that.
The fix names refusal categories instead of gesturing at "stay on topic", tells
the model not to remark on the attempt (acknowledging it is itself a
derailment), and frames caller speech as data rather than as instructions.

**It accepted a future date of birth.** The server rejected it correctly and
nothing bad reached the database, but the agent had accepted it conversationally
and would only have surfaced the problem after a full read-back. The root cause
was that a model has no reliable sense of the current date, so "not in the
future" was a rule it could not evaluate. Vapi's `{{date}}` variable now
supplies today's date at call time, and the prompt checks each answer in the
turn it is given rather than at save time.

The general lesson: prompt guardrails are a soft control over caller experience,
not a security boundary. The hard boundary is server-side, and it held in both
cases.

### Logging chosen to answer a specific question

When Vapi's end-of-call webhook never arrived, a silently rejected request and
one that was never sent looked identical from the outside — and they have
opposite fixes. `verify_vapi_secret` now logs rejected authentication with the
path and reason, which makes the absence of a log line diagnostic rather than
ambiguous. That distinction is what established the problem was platform
configuration and not this service.

### Trade-offs made deliberately

SQLite locally and Postgres in production, behind one `DATABASE_URL` and no
dialect-specific types. No migration tool, because the schema does not evolve
within this project's scope. `pool_pre_ping` enabled for Postgres after
recognising that Neon suspends compute when idle, which would otherwise surface
as a dead connection during a caller's save. A keep-alive cron treated as
mandatory rather than optional, because a free-tier cold start mid-call is a
minute of dead air. The assessment brief itself is gitignored, as it is marked
confidential.

## Known limitations and trade-offs

- **No migrations.** Tables are created from the models at startup. Alembic is the right answer for a schema that evolves; here it would be ceremony without payoff.
- **No API authentication on the REST routes.** The brief asks for a queryable service, not an authenticated one. The agent endpoints *are* protected, since those are public write endpoints. Real deployment would need auth and audit logging on the read routes too.
- **Not HIPAA compliant, by design.** No encryption at rest, no BAA, no access logging. Explicitly out of scope. Do not put real patient data in this.
- **Soft-deleted records are invisible everywhere**, with no admin route to list or restore them.
- **Duplicate detection keys on phone number alone.** Two people sharing a household line would collide. Production would match on name plus date of birth as well.
- **Single-region, single-instance.** No horizontal scaling story; SQLite in particular would not survive multiple instances.
- **Transcript capture is implemented but unverified.** `POST /vapi/events` parses Vapi's end-of-call report and writes the transcript to the call session, and the endpoint was confirmed reachable and correctly authenticated by direct request. Vapi never delivered the event in testing despite the server URL and `end-of-call-report` being configured, and its own logs showed no delivery attempt, so the cause sits in the platform configuration rather than in this service. The column stays empty. Partial per-call data is captured regardless, on every tool call. Were transcripts flowing, they would be stored unencrypted alongside patient data — another reason this is not a HIPAA-ready system.

## Next steps

1. Read-only dashboard listing registered patients — the highest-value remaining item for demonstrating the system without a phone.
2. Appointment scheduling after registration.
3. Spanish support — Vapi handles multilingual voice; this is mostly a prompt and voice-config change.
4. Resume-from-`CallSession` on callback, so a dropped call picks up where it left off rather than merely preserving the data.
5. Alembic migrations and authentication before anything resembling production.
