# Financial Workflow Automation Platform

An enterprise workflow management system that automates financial approval
processes. Users submit requests, which are routed through predefined,
amount-based multi-level approval chains. The platform includes secure
authentication, role-based access control, a complete audit trail, and
in-app/email notifications.

## Tech Stack

- **API**: FastAPI (Python 3.12)
- **Database**: PostgreSQL + SQLAlchemy 2.0 + Alembic migrations
- **Auth**: JWT (access + refresh tokens), bcrypt password hashing
- **Containerization**: Docker / docker-compose
- **CI/CD**: GitHub Actions (lint → test → build & push image → deploy)

## Features

- **Multi-level approval workflows** — approval chain length scales with
  request amount (Manager → Manager+Finance → Manager+Finance+Admin), all
  configurable via environment variables.
- **Role-based authentication & authorization** — `employee`, `manager`,
  `finance`, `admin` roles enforced on every protected endpoint.
- **Notifications** — in-app notification records for every approver/requester
  event, with optional SMTP email delivery.
- **Complete audit trail** — every state change (creation, approval,
  rejection, cancellation, user changes, logins) is written to an
  immutable `audit_logs` table, queryable per-request or system-wide.
- **Automated CI/CD** — GitHub Actions pipeline lints, runs the full test
  suite against a real Postgres service container, then builds and pushes
  a Docker image on merges to `main`.

## Project Structure

```
app/
  main.py              FastAPI app + router wiring
  config.py            Environment-driven settings
  database.py          SQLAlchemy engine/session
  models.py            ORM models (User, FinancialRequest, ApprovalStep, AuditLog, Notification)
  schemas.py           Pydantic request/response schemas
  dependencies.py      Auth + RBAC dependencies
  routers/
    auth.py            Register / login / refresh
    users.py           Profile + admin user management
    requests.py        Submit / list / view / cancel requests
    approvals.py        Approve / reject the active step
    audit.py            Audit trail viewing
    notifications.py    In-app notifications
  services/
    workflow.py          Core approval-chain engine
    audit.py             Audit log writer
    notifications.py     Notification creation + email sending
alembic/               DB migrations
tests/                  Pytest suite (auth + full workflow paths)
.github/workflows/      CI/CD pipeline
Dockerfile / docker-compose.yml
```

## Approval Rules (default, configurable in `.env`)

| Amount (USD)         | Required Approval Chain          |
|-----------------------|-----------------------------------|
| < 1,000               | Manager                           |
| 1,000 – 9,999.99      | Manager → Finance                 |
| ≥ 10,000              | Manager → Finance → Admin         |

The requester's *direct manager* (set via `manager_id`) is used for the
manager step when available; otherwise any active user with the required
role can act on Finance/Admin steps.

## Getting Started (Docker, recommended)

```bash
cp .env.example .env
# edit .env, especially SECRET_KEY

docker compose up --build
```

The API will be available at `http://localhost:8000`, with interactive docs
at `http://localhost:8000/docs`.

## Getting Started (local, without Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start a local Postgres instance and set DATABASE_URL accordingly
cp .env.example .env

uvicorn app.main:app --reload
```

## Database Migrations

Tables are auto-created on startup in `development` mode for convenience.
For real environments, use Alembic:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Running Tests

```bash
pytest -v
```

Tests run against `DATABASE_URL` (point this at a disposable test database
locally, or rely on the Postgres service container that CI spins up).

## Example Workflow

1. `POST /auth/register` — create a user (employee/manager/finance/admin).
2. `POST /auth/login` — obtain access + refresh tokens.
3. `POST /requests` — submit a financial request; the approval chain is
   generated automatically based on amount.
4. `GET /requests/pending-my-approval` — approvers see what's waiting on them.
5. `POST /requests/{id}/decision` — approve or reject the current step.
6. `GET /audit/request/{id}` — view the full audit trail for a request.
7. `GET /notifications` — view in-app notifications.

## API Documentation

Once running, full interactive OpenAPI docs are available at `/docs`
(Swagger UI) and `/redoc`.
