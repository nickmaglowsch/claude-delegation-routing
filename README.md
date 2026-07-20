# claude-delegation-routing

A Claude Code plugin for deliberate model routing in agent fan-out — stop spawning every subagent on the default/inherited model.

## The problem

When an orchestrator session fans out work (Claude Code's native Agent tool, Workflow `agent()`, or [Paseo](https://paseo.dev)'s `create_agent`), agents are usually created on whatever model is the default. That wastes tokens (frontier models doing mechanical work), loses quality (cheap models on hard problems), and misses the biggest win of multi-provider setups: cross-family contrarian review.

A 14-day audit of one real setup found **83 of 90 agent creations ran on an inherited default**.

## Install

```
/plugin marketplace add nickmaglowsch/claude-delegation-routing
/plugin install delegation-routing@claude-delegation-routing
/delegation-setup
```

## What you get

**`/delegation-setup`** — templates the policy into place, as a template, not frozen state:

- `~/.claude/DELEGATION.md`, @-included from your global `~/.claude/CLAUDE.md`, so the think-before-handoff rule is in context every session: classify each task (trivial / normal / hard / really-hard; authoring vs reviewing), pick the tier, pass the model explicitly — never inherit. Tier ladder in stable names (no versioned IDs), with cross-family pairing: Claude authors → GPT reviews, and vice versa.
- `~/.paseo/orchestration-preferences.json` (only if you use Paseo) — role→provider bindings for `impl`/`ui`/`research`/`planning`/`audit`, **generated from your live `list_models` output**, never from IDs baked into this repo. The only file that holds versioned model IDs.

**`/delegation-audit`** — the refinement loop. A stateless Python scanner (stdlib only, zero LLM tokens) walks your session transcripts and reports misroutes: inherited defaults, escalations (same task re-launched bigger / other family), frontier models on mechanical work, and human pushback near handoffs (machine notifications and hook output are filtered out). It also drift-checks the bindings against `list_models` so new model releases get rebound instead of rotting. All edits are proposed as diffs and human-approved. Suggested cadence:

```
/loop 2w /delegation-audit
```

## Default routing philosophy

- Claude frontier — really-hard only (resisted a first attempt, gnarly architecture)
- Claude workhorse — default implementation
- OpenAI frontier (thinking maxed) — hard contrarian analysis, high-stakes review
- OpenAI workhorse — default contrarian reviewer / design challenger
- Cheap tiers — research, tests, mechanical work

All of it is yours to edit after setup — the plugin ships the template and the audit loop, not your state.

## Requirements

- Claude Code. Paseo is optional — without it you still get the DELEGATION.md policy for native Agent/Workflow fan-out and the audit skill.
- Python 3 (stdlib only) for the scanner.
