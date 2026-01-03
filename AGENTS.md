# Agent Guidelines

When you make changes in this repository, you MUST keep all user-facing
documentation up to date, including `README.md` and any files in `docs/`.

## Required updates
- If you change CLI commands, flags, defaults, or workflows, update the
  corresponding sections in `README.md` and `docs/`.
- If you add, remove, or rename scripts, update `scripts/README.md`.
- If you change VM behavior, base images, or host/VM requirements, update
  `README.md` and the relevant `systems/*/README.md`.
- If you add new entrypoints or executables, document how to build and use them.

## Quick checklist (run through before finalizing)
- [ ] README instructions match actual command names and flags.
- [ ] VM flows are up to date for QEMU and Firecracker (if impacted).
- [ ] Log locations and defaults are documented if changed.
- [ ] New files/dirs that users must create are documented.
- [ ] Deprecated steps are removed or clearly marked.

## Git discipline (non‑breaking changes)
After **every prompt** that results in non‑breaking changes, you MUST commit to
git.

- **On `main`**: prefer a single, clean commit per prompt (unless the user
  explicitly requests otherwise).
- **On feature/PR branches**: use incremental commits with clear messages
  (e.g., `feat: …`, `docs: …`, `fix: …`). Squashing can happen at merge time.

If you are unsure which docs apply, scan `README.md` and `docs/` and add a
short note to the most relevant files.

## Remote execution
- For ssh/scp tasks in this repo (VM bring-up, provisioning, diagnostics) and
  any bash tasks that do not require sudo, the agent should run the commands
  directly instead of asking the user to run them.
