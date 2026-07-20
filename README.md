# claude-delegation-routing

Deliberate model routing for Claude Code agent fan-out — stop spawning every subagent on the default/inherited model.

## The problem

When an orchestrator session fans out work (Claude Code's native Agent tool, Workflow `agent()`, or [Paseo](https://github.com/rlebre/paseo)'s `create_agent`), agents are usually created on whatever model is the default. That wastes tokens (frontier models doing mechanical work), loses quality (cheap models on hard problems), and misses the biggest win of multi-provider setups: cross-family contrarian review.

A 14-day audit of one real setup found **83 of 90 agent creations ran on an inherited default**.

## The three pieces

1. **`DELEGATION.md`** → `~/.claude/DELEGATION.md`, @-included from your global `~/.claude/CLAUDE.md`, so it's in context every session. The rule: before ANY handoff, classify the task (trivial / normal / hard / really-hard; authoring vs reviewing) and pass the model explicitly — never inherit. Tier ladder in stable names only:
   - Claude frontier — really-hard only (resisted a first attempt, gnarly architecture)
   - Claude workhorse — default implementation
   - OpenAI frontier (thinking maxed) — hard contrarian analysis, high-stakes review
   - OpenAI workhorse — default contrarian reviewer / design challenger
   - Cheap tiers — research, tests, mechanical work
   - **Cross-family pairing**: Claude authors → GPT reviews, and vice versa.
2. **`orchestration-preferences.json`** → `~/.paseo/orchestration-preferences.json`. Only needed if you use Paseo — every Paseo skill reads this file for role→provider bindings (`impl`, `ui`, `research`, `planning`, `audit`). This is the ONLY place versioned model IDs live; DELEGATION.md deliberately never names them.
3. **`skills/delegation-audit/`** → `~/.claude/skills/delegation-audit/`. The refinement loop: a stateless Python scanner walks your session transcripts and reports misroutes — inherited defaults, escalations (same task re-launched bigger / other family), frontier models on mechanical work, and human pushback near handoffs (machine notifications and hook output are filtered out). It also drift-checks the bindings against `list_models` so new model releases get rebound instead of rotting. All edits are proposed as diffs and human-approved. Suggested cadence: `/loop 2w /delegation-audit`.

## Install

```bash
./install.sh
```

Idempotent; never overwrites an existing `orchestration-preferences.json`. Then open a new Claude Code session.

## Refine over time

The policy is meant to drift-correct, not stay frozen:

```
/delegation-audit
```

Model IDs in the JSON are current as of July 2026 (Claude Fable 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5; GPT-5.5 / 5.4 / 5.4-mini). When a new tier ships, the audit's drift check will flag the stale binding.

## Requirements

- Claude Code. Paseo is optional — without it you still get the DELEGATION.md policy for native Agent/Workflow fan-out and the audit skill.
- Python 3 (stdlib only) for the scanner.
