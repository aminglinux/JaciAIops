# Repository Guidelines

## Project Structure & Module Organization

This repository is organized by capability. `aiops-platform/` is the main application: `backend/` contains the FastAPI service, agent orchestration, and skill packages; `frontend/` contains the React + TypeScript UI built with Vite; `docker/`, `k8s/`, `ansible/`, and `scripts/` hold deployment and ops assets. `time_sequence_prediction/` contains standalone Python experiments and detectors such as `security_audit/` and `cpu_anomaly_detection/`. `knowledge_graph/` and `docs/` contain graph tooling and supporting documentation.

## Build, Test, and Development Commands

- `cd aiops-platform/backend && pip install -r requirements.txt` — install backend dependencies.
- `cd aiops-platform/backend && python app/main.py` — start the API locally on port `8000`.
- `cd aiops-platform/frontend && npm install` — install frontend dependencies.
- `cd aiops-platform/frontend && npm run dev` — start the Vite dev server on port `3000`.
- `cd aiops-platform/frontend && npm run build` — type-check and build the frontend.
- `cd aiops-platform/frontend && npm run lint` — run ESLint for the UI.
- `cd aiops-platform/backend && pytest` or `python test_skill_loading.py` — run Python tests; some legacy checks are executable scripts.

## Coding Style & Naming Conventions

Use 4-space indentation in Python and follow existing type-hint usage in `app/`. Prefer `snake_case` for Python modules, functions, and skill directories. Frontend code uses TypeScript, 2-space indentation, and `PascalCase` for React components in `src/components/` and `src/pages/`. Keep API and service modules grouped by feature. Run `npm run lint` before submitting frontend changes.

## Testing Guidelines

Python tests use `pytest` where available and follow `test_*.py` naming, for example `time_sequence_prediction/security_audit/tests/test_security_audit.py`. Keep tests close to the feature they validate. For backend changes, add or update focused tests in the affected package when practical; for frontend changes, at minimum validate `npm run build` and `npm run lint`.

## Commit & Pull Request Guidelines

Recent history follows short conventional prefixes such as `feat:` and `docs:`; keep that format and write imperative summaries, for example `feat: add Redis diagnosis skill`. Keep commits scoped to one change. Pull requests should include a clear summary, impacted paths, setup or migration notes, linked issues, and screenshots for UI changes.

## Security & Configuration Tips

Do not commit populated `.env` files or secrets. Start from `aiops-platform/backend/.env.example`. API keys, Neo4j credentials, and cloud access keys must stay in local environment configuration only.
