# Lessons

Engineering gotchas hit while building this repo, with the rule to avoid repeating them.

## Tooling / environment

- **Bash working directory persists between calls.** After `cd apps`, later commands stayed in
  `apps/`. Rule: use absolute paths, or `cd` back to the repo root in the same command.
- **pnpm 11/Vercel exits non-zero on ignored build scripts** (`sharp`, `unrs-resolver`, `msw`).
  Rule: keep reviewed packages under `onlyBuiltDependencies` locally, and set Vercel's install
  command to `pnpm install --frozen-lockfile --ignore-scripts` for this static Next app.
- **`create-next-app` in a monorepo drops cruft**: a nested `pnpm-workspace.yaml` (fractures the
  workspace) plus `CLAUDE.md`/`AGENTS.md`. Rule: delete the nested workspace file (fold its
  `ignoredBuiltDependencies` into root) and the nested instruction files.
- **`shadcn init` can half-complete**: it wrote `components.json` but not `utils.ts`/themed
  `globals.css` when the dep install step exited non-zero. Rule: re-run with `-f` and pipe `yes`.
- Next's `apps/web/.gitignore` has `.env*` with no exception → blocks `.env.example`. Add
  `!.env.example`.
- **Production admin cookies break when the browser calls API Gateway directly.** Rule: keep
  production browser calls same-origin via Next/Vercel rewrites (`API_PROXY_TARGET`), not
  `NEXT_PUBLIC_API_BASE_URL`, so the admin session cookie is first-party.
- **Query cache can preserve stale proof ordering after retrieval changes.** Rule: after changing
  ranking logic, smoke a cache-busted query and clear only the targeted stale `query_cache` item for
  any user-reported exact prompt before declaring the live UX fixed.
- **CI runs `ruff format --check`, not just `ruff check`.** Rule: after editing Python files, run
  both commands locally before pushing, especially after CDK/deploy config changes.

## Audit / production hardening

- **Magic constants in retrieval scoring drift silently.** Rule: put scoring constants in
  `GraphConfig` and add a test that pins the conversion they control.
- **Bare `except` branches are operational blindness.** Rule: when falling back for UX resilience,
  log a structured error and emit/count a metric so outages are visible.
- **One retrieval threshold cannot govern two similarity metrics.** Rule: dotproduct transcript
  scores and cosine visual scores need separate thresholds, even if the defaults start equal.
- **`ffmpeg -vf fps=1/N` samples frames from inside each time window, not exactly from `t=0`.**
  Rule: timestamp extracted frames at the window midpoint unless using a seek strategy that proves
  otherwise.
- **Cookie `samesite` should match the actual browser topology.** Rule: if prod browser calls go
  through same-origin Vercel rewrites, use `lax`; only use `none` for real cross-site browser calls.
- **SQS delivery is at-least-once.** Rule: every worker handler starts with an idempotency
  short-circuit before doing downloads, embeds, writes, or other expensive side effects.
- **A model fitting in a Lambda image is not the same as being request-safe.** Rule: keep CPU
  cross-encoders opt-in until cold-start and p95 search latency are proven live, or serve them from
  a warmed, async, or separate compute path.

- **yt-dlp breaks silently when the Docker image goes stale.** YouTube changes its extraction API
  frequently; a pinned `>=2025.1` won't protect against future breakage. Rule: pin yt-dlp to a
  *recent* nightly in the Dockerfile (e.g. `pip install yt-dlp==2026.5.30`), add deno as a JS
  runtime (`curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh`), and re-deploy
  whenever ingestion starts failing with exit status 1.

## Framework

- **shadcn `sonner.tsx` imports `next-themes`.** If you aren't using a theme provider, simplify it
  to a fixed `theme="light"` rather than adding the dependency/provider.
- **React 19 lint rule `react-hooks/set-state-in-effect`** errors on calling a state-setting
  function synchronously in an effect body. Rule: kick initial fetches via `setTimeout(fn, 0)` /
  `setInterval` callbacks (subscription pattern), not a direct call.

## Verification with the preview MCP

- **The preview browser is sandboxed** and cannot reach a separately-launched host API on
  `localhost:8000`. Rule: default the web client to same-origin and add a Next `rewrites()` proxy
  to the backend, so the browser hits the Next server (on the host), which proxies to the API.
- **`preview_fill` does not reliably sync a React controlled input before an immediate
  `preview_click`** — the click can land on a still-disabled submit button. Rule: verify form flows
  via a direct `fetch` in `preview_eval`, or trigger via elements that pass explicit args (chips).

## Eval / metrics

- **The committed eval artifact and the golden set drift independently.** The Jun 6 golden rebuild
  (145 → 135 queries) was never re-evaluated, so `eval-results.json` showed Jun 3 numbers and made a
  later code change look like a regression across configs whose code hadn't changed. Rule: before
  any A/B against the committed artifact, compare `meta.generated_at` / `meta.golden_set_size` with
  `git log -- eval/golden/`; if they disagree, regenerate the baseline first. Cheap scoped baseline:
  monkeypatch `run_eval.CONFIGS` to one config and call `run_eval.run_eval(...)` (~5 min, no
  artifact overwrite). Impossible metric moves in untouched configs ⇒ suspect the test set, not the
  code.
