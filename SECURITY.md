# Security Policy

## Reporting a Vulnerability

If you discover a security issue in this repository (e.g., exposed credentials, SQL injection, insecure API endpoint):

1. **Do NOT open a public GitHub issue.**
2. Email `shard-c6` directly via GitHub private contact.
3. Include: description, reproduction steps, potential impact.

We will respond within **48 hours**.

## Security Practices

- All credentials and API keys are stored in `.env` files — never committed to the repo
- The `.env.example` file contains only placeholder values
- Database connections use parameterised queries (via SQLAlchemy Core, see `src/db.py`) — no raw SQL with user input
- API endpoints are read-only (GET only) — no write access exposed publicly
- No PII is intentionally collected or stored — scrapers extract only public price, route, and timestamp data
