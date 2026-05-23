# <TITLE> Implementation Plan

> Development plans follow the SDD workflow inherited from
> `aidoc-flow-framework`: **plan → review (≥2 passes) → implement → verify →
> land**. A plan needs at least two review passes recorded in `## Review log`
> before it may be implemented; harden until a pass finds nothing.

**Goal:** <one-sentence outcome>

**Architecture:** <how this fits the framework/ contract + platforms/ runtimes>

**Tech Stack:** <languages, tools, test runners>

---

| Field      | Value |
|------------|-------|
| Task       | <TASK-ID> |
| Depends on | <files / prior plans> |
| Status     | <PLANNED \| IN REVIEW \| APPROVED \| IN PROGRESS \| DONE \| ABANDONED> - <ISO-8601> |
| Feeds      | <downstream work this unblocks> |

## Objective

<What this plan delivers and why. The problem it solves.>

## Scope

**In:**

1. <included item>

**Out:**

1. <explicitly excluded item>

## Approach

<Narrative of the design. Key decisions and their rationale. Cross-reference
`plans/DECISIONS.md` entries.>

## File Structure

| Path | Responsibility |
|------|----------------|
| `<path>` | <what it does> |

## Step Sequence

### Task N: <name>

**Files:**

- Create / Modify: `<path>`

- [ ] **Step 1: <action>**

  <details, code, commands>

- [ ] **Step N: Commit**

  ```bash
  git add <paths>
  git commit -m "<conventional prefix>: <message>"
  ```

## Verification

> Nothing is "done" until these pass.

```bash
<commands that prove the plan landed correctly>
```

Expected:

1. <observable outcome>

## Risks

| # | Risk | Mitigation |
|---|------|------------|
| R1 | <risk> | <mitigation> |

## Review log

> At least **two** passes before implementation. Each pass: re-read the whole
> plan, list findings, fold fixes back into the sections above. Stop when a pass
> finds nothing.

### Pass 1 - <ISO-8601>

- <finding → how the plan was changed>

### Pass 2 - <ISO-8601>

- <finding, or "no new findings">
