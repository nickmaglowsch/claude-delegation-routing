---
name: delegation-audit
description: Audit model-routing decisions for agent fan-out — scan recent transcripts for misroutes (wrong model chosen for a handoff, inherited defaults, escalations, frontier models on mechanical work), check for model drift vs the Paseo bindings, and propose human-gated edits to DELEGATION.md and ~/.paseo/orchestration-preferences.json. Use when the user says "delegation audit", "audit my model routing", "check my model choices", "are agents on the right models", "refine the delegation policy", or on a /loop cadence.
argument-hint: "[--days N] [--max-events N]"
---

# Delegation Audit

Refinement loop for the model-routing policy in `~/.claude/DELEGATION.md` and `~/.paseo/orchestration-preferences.json`. Follow the steps strictly in order. Read-only until the user approves each edit.

## Input

`$ARGUMENTS` passes through to the scanner. Defaults: `--days 30 --max-events 15`.

## Step 1: Run the scanner

```bash
python3 ~/.claude/skills/delegation-audit/scripts/scan.py $ARGUMENTS
```

The scanner is offline and stateless (zero LLM tokens). It walks `~/.claude/projects/**/*.jsonl` (skipping `subagents/` and `tool-results/`), extracts agent-creation tool calls (`mcp__paseo__create_agent` provider, native `Agent`/`Task` model), and reports: a routing histogram, inherited-default creations, escalations (similar task re-launched on a bigger tier or the other family), frontier models on mechanical-looking work, and user-pushback friction near handoffs. It deliberately ignores raw retry counts, runtimes, test failures, and permission errors — those signal bad task packaging, not wrong model choice.

## Step 2: Read the report

If it prints `ALL CLEAN` and the drift check (Step 3b) finds nothing, stop here and tell the user everything is clean.

Prioritize: `strong` friction events > escalations > inherited defaults > frontier-on-mechanical. Take at most the top 3–5.

## Step 3: Investigate

**3a — transcripts.** For each selected event, open the named session file, `grep -n` for the agent title to find the line, and Read ~50 lines around it. Diagnose: was the model actually wrong for the task (misroute), or was the prompt/task packaging the problem (not a routing issue — skip it)?

**3b — drift check.** Call `mcp__paseo__list_models` for providers `claude` and `codex`. Compare against the bindings in `~/.paseo/orchestration-preferences.json` and the tier assumptions in `~/.claude/DELEGATION.md`:
- A bound model ID no longer listed → stale binding, propose the replacement.
- A new top-tier model appeared (e.g. a new GPT frontier, a new Opus) → propose rebinding that tier.

## Step 4: Propose edits (human-gated)

For each confirmed misroute or drift, propose ONE specific edit: file path + before/after diff + one-sentence rationale. Targets are only `~/.claude/DELEGATION.md` (policy/tier rules) and `~/.paseo/orchestration-preferences.json` (concrete bindings). Do NOT apply edits automatically — wait for the user's explicit OK on each, then apply with Edit.

## Step 5: Summarize

Report: events diagnosed vs skipped, edits proposed/applied, drift findings, and remind the cadence: `/loop 2w /delegation-audit`.

## Rules

- Read-only by default; every write is individually user-approved.
- Don't over-interpret a single generic "no/wait" — misroutes need a model-targeted signal or a repeat pattern.
- Don't propose churn: no rebinding on one data point.
- Budget: investigate at most 5 events per run.
- Don't invent friction — the honest "all clean" report is the useful one.
