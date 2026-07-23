---
name: delegation-audit
description: Audit model-routing decisions for agent fan-out — scan recent transcripts for misroutes (wrong model chosen for a handoff, inherited defaults, escalations, frontier models on mechanical work), check for model drift vs the Paseo bindings, and propose human-gated edits to DELEGATION.md and ~/.paseo/orchestration-preferences.json. Use when the user says "delegation audit", "audit my model routing", "check my model choices", "are agents on the right models", "refine the delegation policy", or on a /loop cadence.
argument-hint: "[--days N] [--max-events N]"
---

# Delegation Audit

Refinement loop for the model-routing policy in `~/.claude/DELEGATION.md` and `~/.paseo/orchestration-preferences.json` (installed by `/delegation-setup`). Follow the steps strictly in order. Read-only until the user approves each edit.

## Input

`$ARGUMENTS` passes through to the scanner. Defaults: `--days 30 --max-events 15`.

## Step 1: Run the scanner

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/delegation-audit/scripts/scan.py" $ARGUMENTS
```

The scanner is offline and stateless (zero LLM tokens). It walks both `~/.claude/projects/**/*.jsonl` and the Paseo/ccs transcript root `~/.ccs/shared/context-groups/**/*.jsonl` — Paseo agents live outside `~/.claude/projects`, so scanning only the latter would miss exactly the agents that fan out. `subagents/` transcripts are included (that is where most of the spend lives, and the only place recursive fan-out is visible); only `tool-results/` and `memory/` are skipped. Override roots with `--projects-dir` (repeatable). It reports three things:

- **Too much context** — total token spend broken into cache reads / cache writes / output, an estimated list-price cost, and the costliest individual agents ranked by `turns × avg context`. This is usually where the money is: tier bounds price-per-token, turns × context bounds the total. Also flags recursive fan-out (agents spawned by an agent), which the one-level rule forbids.
- **Wrong model** — a routing histogram, inherited-default creations, escalations (similar task re-launched on a bigger tier or the other family), frontier models on mechanical-looking work, and user-pushback friction near handoffs.
- **Too many agents** — fan-out volume (sessions creating more than the per-task cap) and quota/rate-limit deaths, including re-spawns that fired *after* a death (circuit-breaker violations). A quota blowup is almost always volume, not tier.

Costs are list-price estimates for Claude models only, assuming 5-minute cache TTL — a floor, not a bill. Non-Claude turns are counted but left unpriced. Treat the *split* and the *ranking* as the signal, not the absolute dollar figure.

Machine text (paseo notifications, hook output, system wrappers) is filtered out of the friction pass. It still ignores raw retry counts, runtimes, and test failures — those signal bad task packaging, not a routing or volume problem.

## Step 2: Read the report

If it prints `ALL CLEAN` and the drift check (Step 3b) finds nothing, stop here and tell the user everything is clean.

Prioritize by money, then by policy breach: over-budget costly agents > recursive fan-out > quota-death re-spawns > `strong` friction events > wide fan-out sessions > escalations > inherited defaults > frontier-on-mechanical. Take at most the top 3–5.

Read the `lever` line first. If reads+writes are ≥60% of cost, routing changes will barely move the number — the fix is turn budgets and context hygiene, and you should say so plainly rather than proposing tier edits that look productive but save nothing.

## Step 3: Investigate

**3a — transcripts.** For each selected event, open the named session file, `grep -n` for the agent title to find the line, and Read ~50 lines around it. Diagnose: was the model actually wrong for the task (misroute), or was the prompt/task packaging the problem (not a routing issue — skip it)?

For a costly over-budget agent, find *what* inflated its context instead: grep its transcript for the biggest tool results (whole-file `Read`s, unfiltered build/test/log output, repeated re-reads of the same file). Name the specific habit — "piped full `npm run build` output 11 times" is actionable; "used too much context" is not.

**3b — drift check.** If the Paseo MCP server is available, call `mcp__paseo__list_models` for each enabled provider. Compare against the bindings in `~/.paseo/orchestration-preferences.json` and the tier assumptions in `~/.claude/DELEGATION.md`:
- A bound model ID no longer listed → stale binding, propose the replacement.
- A new top-tier model appeared (e.g. a new GPT frontier, a new Opus) → propose rebinding that tier.

## Step 4: Propose edits (human-gated)

For each confirmed misroute or drift, propose ONE specific edit: file path + before/after diff + one-sentence rationale. Targets are only `~/.claude/DELEGATION.md` (policy/tier and turn-budget rules) and `~/.paseo/orchestration-preferences.json` (concrete bindings). Do NOT apply edits automatically — wait for the user's explicit OK on each, then apply with Edit.

Context-bloat findings often have no file edit worth making — the turn budget is already written down and was simply not followed. In that case report the habit and the dollar figure and stop. Do not invent a policy line to have something to write; `DELEGATION.md` is `@`-included into every session, so each line you add costs tokens forever.

## Step 5: Summarize

Report: total spend and its split, the costliest agents and what inflated them, events diagnosed vs skipped, edits proposed/applied, drift findings, and remind the cadence: `/loop 2w /delegation-audit`.

## Rules

- Read-only by default; every write is individually user-approved.
- Don't over-interpret a single generic "no/wait" — misroutes need a model-targeted signal or a repeat pattern.
- Don't propose churn: no rebinding on one data point.
- Budget: investigate at most 5 events per run.
- Don't invent friction — the honest "all clean" report is the useful one.
