# Architecture

RexCrop is a two-application workspace:

```text
frontend/  Next.js 15 application
backend/   FastAPI application and local worker
```

The frontend uses Next.js route handlers as a backend-for-frontend layer. It keeps JWTs in HTTP-only, same-site cookies and forwards authenticated requests to FastAPI. Browser code never receives the token directly.

The FastAPI application owns authentication, SQLite persistence, uploaded files, job state, and local AI integrations. Its modules are organized by responsibility:

```text
app/
├── api/        # HTTP routes and dependencies
├── ai/         # Local AI adapters, including Whisper
├── core/       # Configuration
├── db/         # SQLAlchemy base and sessions
├── models/     # Database entities
├── schemas/    # Request and response contracts
├── services/   # Shared application services
└── workers/    # In-process queue and job handlers
```

At API startup, the worker starts in the same process. It polls persisted queued jobs and handles them one at a time. This is suitable for local development; production should move job execution to a separate worker process backed by durable shared infrastructure.

## Request flow

1. The user signs in through a Next.js route handler.
2. The handler stores the FastAPI-issued JWT in an HTTP-only cookie.
3. Protected frontend pages validate the JWT with FastAPI.
4. Uploads and job requests are forwarded by authenticated Next.js route handlers.
5. The FastAPI worker updates job progress in SQLite; the dashboard polls status every two seconds.
