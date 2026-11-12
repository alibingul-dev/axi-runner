# axi-runner

Public runner for the workflows of the private data repo `alibingul-dev/axi-epias-data`.
Public repos get free GitHub Actions minutes; the data never lives here.

- Every workflow checks out the private repo with `PRIVATE_REPO_TOKEN` and pushes results back to it.
- `watcher` replaces the old push triggers: it polls the private repo every 60 s and dispatches the
  workflows whose former push paths (`watcher/routes.json`) match new non-bot commits.
- Logs are public: scripts print counts only, never file contents or codes. Keep it that way.
