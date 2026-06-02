# Lessons

Engineering gotchas hit while building this repo, with the rule to avoid repeating them.

## Tooling / environment

- **Bash working directory persists between calls.** After `cd apps`, later commands stayed in
  `apps/`. Rule: use absolute paths, or `cd` back to the repo root in the same command.
- **pnpm here exits non-zero on ignored build scripts** (`sharp`, `unrs-resolver`, `msw`) and a
  hook injects an invalid `allowBuilds:` stub into `pnpm-workspace.yaml`. Rule: list every such
  package under `ignoredBuiltDependencies` so installs stay non-interactive; delete the stub.
- **`create-next-app` in a monorepo drops cruft**: a nested `pnpm-workspace.yaml` (fractures the
  workspace) plus `CLAUDE.md`/`AGENTS.md`. Rule: delete the nested workspace file (fold its
  `ignoredBuiltDependencies` into root) and the nested instruction files.
- **`shadcn init` can half-complete**: it wrote `components.json` but not `utils.ts`/themed
  `globals.css` when the dep install step exited non-zero. Rule: re-run with `-f` and pipe `yes`.
- Next's `apps/web/.gitignore` has `.env*` with no exception → blocks `.env.example`. Add
  `!.env.example`.

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
