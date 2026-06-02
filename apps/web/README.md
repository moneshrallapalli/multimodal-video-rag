# web

Next.js (App Router, TypeScript, Tailwind v4) frontend for the Multimodal Video RAG
platform. Three surfaces share **one** shadcn/ui design system (emerald accent on a
very-light-green canvas):

- `/` — public, read-only search over the demo library, with timestamp-seek playback
- `/admin` — gated ingestion console (login, submit URL, job status)
- `/eval` — interactive evaluation dashboard (over committed JSON; real data in Phase 5)

Brand lives in one swappable file: `src/lib/brand.ts`. The theme tokens live in
`src/app/globals.css`. Typed API contracts mirror `packages/shared` in `src/lib/types.ts`.

## Develop

```bash
pnpm install                       # from the repo root (pnpm workspace)
pnpm --filter web dev              # http://localhost:3000
```

The app talks to the FastAPI backend at `NEXT_PUBLIC_API_BASE_URL`
(default `http://localhost:8000`; see `.env.example`). Start the API with
`uv run uvicorn api.main:app --reload` from the repo root.

## Checks

```bash
pnpm --filter web lint
pnpm --filter web typecheck
pnpm --filter web build
```
