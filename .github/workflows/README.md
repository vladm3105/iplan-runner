# CI workflow policy

**This is a PUBLIC repository — CI runs on GitHub-hosted runners. Do NOT switch any
workflow to a self-hosted runner.**

Two independent reasons, either sufficient:

1. **No cost benefit** — public-repo GitHub Actions minutes are free and unlimited;
   the self-hosted runner exists only to stop burning the *private* repos' allotment.
2. **A security hole** — a self-hosted runner on a **public** repo lets a **fork PR
   run arbitrary code on the host**. GitHub explicitly warns against this.

The company's ephemeral self-hosted runner is for **private repos only**.
Source of truth: `aidoc-flow-operations` →
`ops/iplans/IPLAN-0012_ephemeral-sandboxed-ci-runners.md` (the "SETTLED" exclusion note).
