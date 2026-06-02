# Phase 1 — Product Skeleton — TODO

Web + API skeletons over mocked contracts + one shared emerald/green shadcn design system.
Plan: `~/.claude/plans/melodic-dreaming-karp.md`. Conventions: granular conventional commits,
NO `Co-Authored-By`, push frequently.

## Tasks
- [x] A. Shared contracts — `packages/shared/src/shared/schemas.py` (+ exports)
- [x] B. Mock data + fixtures — `apps/api/src/api/mock_data.py`
- [x] C. API endpoints + auth + CORS + pyproject deps
- [x] D. Backend tests + CI (pytest job + web build job)
- [x] E. Web scaffold (create-next-app) + shadcn design system (emerald/green theme + brand)
- [x] F. Public search surface (results + timestamp-seek player)
- [x] G. Admin console (login, ingest form, jobs table)
- [x] H. Eval dashboard stub over committed sample JSON
- [x] I. Docs + task log; final verification

## Review

**Outcome:** Phase 1 done. A clickable app with a fake-but-shaped data flow across all three
surfaces, one shared design system, real (mocked) typed contracts, and green CI.

**Backend (`apps/api`, `packages/shared`)**
- Pydantic contracts in `shared/schemas.py` (single source of truth; mirrored in TS).
- Mocked, deterministic `mock_search` (keyword→intent, fuzzy overlap scoring, refusal gate) over
  the 3 real demo videos; in-memory jobs store seeded with a completed + failed job.
- Endpoints: `/api/videos`, `/api/search`, `/api/admin/{login,logout,session,jobs,ingest}`.
- Real-but-minimal admin auth: argon2 verify + signed (`itsdangerous`) session cookie.
- 8 pytest tests (health, videos, answerable + no-answer search, visual intent, admin flow + 401s).

**Frontend (`apps/web`)** — Next.js 16 / React 19 / Tailwind v4 / shadcn.
- One design system, emerald accent on very-light-green, brand in `src/lib/brand.ts`.
- Public search: hero, search bar, example chips, video filter, rich result cards, answer panel,
  no-answer notice, and a YouTube player that seeks by remounting the embed iframe.
- Admin console: gated login → ingest form + live-polling job table.
- Eval dashboard: interactive config toggle over committed `eval-sample.json` (clearly-labeled
  placeholder data; real numbers land in Phase 5).
- Dev DX: client defaults to same-origin; `next.config.ts` proxies `/api/*` to the backend.

**Verification**
- `uv run pytest` → 8 passed. `uvx ruff check/format` clean.
- `pnpm --filter web lint && typecheck && build` clean; `/`, `/admin`, `/eval` prerender static.
- Live: API health + search + CORS confirmed via curl; all three surfaces screenshotted in a real
  browser — answerable search → answer + card + player seek; off-domain → graceful refusal; admin
  login → ingest → job appears; eval config toggle updates RAGAS panel.

**Out of scope (later):** real ingestion (P2), Pinecone/Bedrock retrieval + LangGraph (P3–4),
real eval numbers (P5), Vercel/Lambda deploy (P6).
