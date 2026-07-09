<div align="center">

# RecruitIQ

**AI-powered recruitment platform — resume screening, interview management, and offer tracking, end to end.**

[![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-Frontend%20%26%20Admin-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey)](#)

</div>

<br/>

<div align="center">
  <img src="./docs/admin_screenshot.png" alt="RecruitIQ admin portal" width="640"/>
  <p><em>Platform admin portal — organization oversight and audit logs</em></p>
</div>

<br/>

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [AI Pipeline](#ai-pipeline)
- [Prerequisites](#prerequisites)
- [Run with Docker (recommended)](#run-with-docker-recommended)
- [Run locally without Docker](#run-locally-without-docker)
- [Admin Portal](#admin-portal)
- [Project Structure](#project-structure)

<br/>

## Overview

RecruitIQ automates the recruitment pipeline from job description to hire: it generates tier-specific screening criteria from a job description, parses and scores incoming resumes against that criteria, manages interview scheduling and panelist evaluations, and handles the full offer lifecycle — including candidate-facing accept/decline links.

| Service    | URL                             | Description                |
| ---------- | -------------------------------- | --------------------------- |
| API        | http://localhost:8000            | FastAPI backend              |
| Frontend   | http://localhost:3000            | HR / recruiter web app       |
| Admin      | http://localhost:3001            | Platform admin portal        |
| LiteLLM    | http://localhost:4000            | Self-hosted LLM gateway      |
| MinIO      | http://localhost:9001            | Object storage console       |
| PostgreSQL | localhost:5432                   | Primary database             |
| Redis      | localhost:6379                   | Job queue / cache            |

<br/>

## Architecture

```mermaid
flowchart LR
    subgraph Client
        FE[Frontend :3000]
        AD[Admin Portal :3001]
    end

    subgraph Core
        API[FastAPI :8000]
        WK[arq Worker]
    end

    subgraph Data
        PG[(PostgreSQL 17)]
        RD[(Redis 7)]
        MN[(MinIO)]
    end

    LLM[LiteLLM Proxy :4000]
    EXT[Groq / OpenAI]
    MAIL[Resend]

    FE --> API
    AD --> API
    API --> PG
    API --> RD
    API --> MN
    API --> WK
    WK --> RD
    WK --> LLM
    API --> LLM
    LLM --> EXT
    API --> MAIL
```

Every service — app, worker, model gateway, and data layer — runs as its own container, orchestrated through a single `docker-compose.yml` with health-check-based startup ordering.

<br/>

## AI Pipeline

Resume screening runs as a decoupled, asynchronous pipeline so long-running AI calls never block the API:

```mermaid
sequenceDiagram
    participant U as Recruiter (Frontend)
    participant A as FastAPI
    participant M as MinIO
    participant R as Redis Queue
    participant W as arq Worker
    participant P as pydantic-ai Agents
    participant L as LiteLLM Proxy

    U->>A: Upload resume
    A->>M: Store file
    A->>R: Enqueue scoring job
    A-->>U: 202 Accepted (immediate)
    W->>R: Pick up job
    W->>P: Run jd_analyzer → criteria_builder
    W->>P: Run resume_parser → resume_scorer → quality_reviewer
    P->>L: Model calls (retry-wrapped)
    L->>W: Structured result
    W->>A: Persist score to Postgres
    A-->>U: Result available / email sent
```

Six specialized `pydantic-ai` agents are invoked directly per task (no crew/coordination layer): `jd_analyzer`, `criteria_builder`, `resume_parser`, `resume_scorer`, `quality_reviewer`, `rejection_writer`. Each agent's context is built at call time from the job description text, resume text, and a `DesignationTier` enum that injects tier-appropriate evaluation guidance.

<br/>

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Optional API keys for full AI/email features:
  - `GROQ_API_KEY` or `OPENAI_API_KEY` — resume screening & criteria generation
  - `RESEND_API_KEY` — transactional email

The stack starts without these keys, but AI screening and email features will not work until they're configured.

<br/>

## Run with Docker (recommended)

### 1. Clone and enter the project

```bash
cd recruitIQ
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `JWT_SECRET` — a random string (e.g. `openssl rand -hex 32`)
- `PLATFORM_ADMIN_EMAIL` / `PLATFORM_ADMIN_PASSWORD` — credentials for the admin portal

Add `GROQ_API_KEY` / `OPENAI_API_KEY` / `RESEND_API_KEY` when you need those features.

### 3. Start all services

```bash
docker compose up --build
```

First startup can take several minutes while images build and dependencies install. Wait until the `api` logs show migrations applied and Uvicorn running — the platform admin user is seeded automatically on every API boot (it's a no-op if the admin already exists).

### 4. Open the apps

| App           | URL                          |
| -------------- | ----------------------------- |
| API docs       | http://localhost:8000/docs   |
| Admin portal   | http://localhost:3001/login  |
| HR frontend    | http://localhost:3000        |
| MinIO console  | http://localhost:9001        |

Sign in to the admin portal with your `PLATFORM_ADMIN_EMAIL` and `PLATFORM_ADMIN_PASSWORD`.

### 5. Stop the stack

```bash
docker compose down
```

To also remove database volumes:

```bash
docker compose down -v
```

<br/>

## Run locally without Docker

This setup runs Postgres, Redis, MinIO, and LiteLLM in Docker (stateless services, easy to containerize) but runs the API and worker directly on your machine for faster iteration. Recommended for local dev on Windows.

**Requirements:** Python 3.12 (LiteLLM/CrewAI dependencies don't yet support 3.14), [uv](https://docs.astral.sh/uv/), Docker Desktop.

### 1. Start infrastructure services

```bash
docker compose up postgres redis minio minio-init litellm -d
```

Confirm LiteLLM is healthy before continuing — it needs `GROQ_API_KEY` (and optionally `OPENAI_API_KEY`) set in the **root** `.env`, since `docker-compose.yml` passes these through to the `litellm` container:

```bash
docker compose ps litellm
curl http://localhost:4000/health/liveliness
```

### 2. Set up the backend virtual environment

```bash
cd backend
uv python install 3.12
uv venv --python 3.12
.venv\Scripts\activate   # Windows
uv pip install -e ".[dev]"
```

> **Note:** `bcrypt` 5.x is incompatible with the installed `passlib` version. If `uv pip install -e ".[dev]"` pulls in `bcrypt>=5`, pin it manually:
> ```bash
> uv pip install "bcrypt==4.0.1"
> ```

### 3. Configure `backend/.env`

Create a `backend/.env` file (separate from the root `.env` used by Docker) with **localhost**-based URLs — services running outside Docker can't resolve Docker service names like `redis` or `litellm`:

```env
DATABASE_URL=postgresql+asyncpg://recruitiq:recruitiq@localhost:5432/recruitiq
REDIS_URL=redis://localhost:6379
LITELLM_BASE_URL=http://localhost:4000
LITELLM_MASTER_KEY=sk-recruitiq-local
GROQ_API_KEY=your_groq_key_here
JWT_SECRET_KEY=your_32_plus_character_secret_here
PLATFORM_ADMIN_EMAIL=your_admin_email_here
PLATFORM_ADMIN_PASSWORD=your_admin_password_here
```

### 4. Run migrations and start the API

```bash
alembic upgrade head
uvicorn app.main:app --reload --reload-dir app --port 8000
```

> **Note:** `--reload-dir app` restricts the file watcher to your source code. Without it, `uvicorn --reload` also watches `.venv`, which can trigger constant reloads from background package activity — especially disruptive if your project sits in a synced folder like OneDrive.

In another terminal, start the background worker (same venv):

```bash
cd backend
.venv\Scripts\activate
arq app.workers.settings.WorkerSettings
```

Seed the platform admin (safe to re-run — it no-ops if the admin already exists):

```bash
cd backend
python scripts/seed_platform_admin.py
```

> **Windows + OneDrive note:** If this project folder lives inside OneDrive (or any cloud-synced directory), you may hit intermittent file-lock errors during `uv pip install`, package corruption, or CRLF line-ending issues. If you run into repeated, hard-to-explain errors during setup, moving the project to a local, non-synced path (e.g. `C:\Projects\recruitIQ`) is the most reliable fix.

### Admin app (local dev)

```bash
cd admin
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open http://localhost:3000 (local dev uses port 3000; Docker maps it to **3001**).

### Frontend (local dev)

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open http://localhost:3000. Register a new organization or sign in with an existing HR account.

**Pages:** Dashboard, Positions (resume upload & AI screening), Interviews, Offers, Settings (team invites).

<br/>

## Admin Portal

The admin app (`/admin`) is the platform administration UI for users with the `platform_admin` role. It connects to these API endpoints:

- `GET /api/v1/admin/organizations` — list all tenant organizations
- `PATCH /api/v1/admin/organizations/{id}/suspend` — suspend an organization
- `GET /api/v1/admin/audit-logs` — view recent audit events

**Admin pages:**
- **Organizations** — view tenants and usage, suspend accounts
- **Audit Logs** — browse the last 200 platform audit events

<br/>

## Project Structure

```
recruitIQ/
├── backend/          # FastAPI app, arq worker, pydantic-ai agents, alembic migrations
├── frontend/          # Next.js HR/recruiter web app
├── admin/             # Next.js platform admin portal
├── docs/              # Screenshots and reference assets (add your own)
├── docker-compose.yml
├── .env.example
└── README.md
```