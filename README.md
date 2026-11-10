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
- `~/.claude/DELEGATION.local.md`: your own overrides, such as which model is your top tier or your gateway advisor. It is @-included after `DELEGATION.md` and wins where they conflict. Setup creates it once and never overwrites it, so `DELEGATION.md` can stay identical to the template and plugin updates apply cleanly.
- `~/.paseo/orchestration-preferences.json` (only if you use Paseo) — role→provider bindings for `impl`/`ui`/`research`/`planning`/`audit`, **generated from your live `list_models` output**, never from IDs baked into this repo. The only file that holds versioned model IDs.

- `~/.claude/agents/scout.md` and `~/.claude/hooks/scout_readonly.py` (optional) — a cheap, read-only code-search subagent for "where is X / who calls X / how many X". See [scout](#scout-a-cheap-lookup-agent-that-counts-right) below.

**`/delegation-audit`** — the refinement loop. A stateless Python scanner (stdlib only, zero LLM tokens) walks your session transcripts — including `subagents/`, where most of the spend lives — and reports:

- **Where the tokens went.** Total spend split into cache reads / cache writes / output, an estimated list-price cost, and the costliest individual agents ranked by `turns × avg context`. Tier bounds the price per token; `turns × context` bounds the total, and context is re-read on every turn — so cost is roughly quadratic in turn count. On a measured 23-agent wave the split was 56% reads / 29% writes / 15% output, and 37 over-budget agents were 86% of the bill while routing itself was clean. Also flags recursive fan-out (agents spawning agents), which the one-level rule forbids and which is invisible to any scanner that skips `subagents/`.
- **Misroutes.** Inherited defaults, escalations (same task re-launched bigger / other family), frontier models on mechanical work, and human pushback near handoffs (machine notifications and hook output are filtered out).
- **Drift.** Bindings checked against `list_models` so new model releases get rebound instead of rotting.

Costs are list-price estimates for Claude models at 5-minute cache TTL — a floor, not a bill; the split and the ranking are the signal. All edits are proposed as diffs and human-approved. Suggested cadence:

```
/loop 2w /delegation-audit
```

## The two levers

**Tier** bounds the price per agent. **Turns × context** bounds the total, and it is usually the bigger number — an 80-turn budget with a handoff file beats any amount of tier tuning on a fleet whose agents each run 200 turns. `DELEGATION.md` carries both rules; the audit tells you which one you are actually violating.

## scout: a cheap lookup agent that counts right

Code lookups make up most delegated exploration, and the built-in Explore agent tends to get the items right and the count wrong. We benchmarked it on a large Python/Mako/JS monorepo: 5 questions with verified answers (list every caller, count every mount, trace a config value, a near-miss name trap), each run in a fresh agent.

| Setup | Accuracy | Tokens / run | Time / run |
|---|---|---|---|
| Explore on Haiku | 97% (3 runs) | ~84k | ~97s |
| Explore on Sonnet | 83% (3 runs) | ~51k | ~39s |
| A Codex cheap-tier model | 90% (3 runs) | ~82k | ~117s |
| **scout (Haiku + protocol)** | **100% (2 runs)** | **~61k** | **~82s** |

Every miss was a counting mistake: a correct list summed to the wrong total, or a match inside a comment counted as live code. scout's protocol fixes that:
- Search with `git grep -nIF` before reading.
- Read only the lines around a hit.
- Get every count from a command, never by eye.
- Drop comments and definitions before counting usages.
- Give production and test numbers separately.
- Rerun with `--untracked` before saying something does not exist.

Read-only is enforced, not requested. In the benchmark, a Haiku agent told to stay read-only still wrote a scratch file. scout's Bash goes through a PreToolUse hook that fails closed:
- A small lexer that follows Bash quoting rules rejects any unquoted character the shell could expand, redirect or glob.
- Each allowed command (`git grep/log/show/ls-files/blame/rev-parse`, line-range `sed`, `wc`, `sort`, `uniq`, `head`, `tail`, `cut`, `tr`) has an exact option table.
- `git show`, `git blame` and `git log -p` must carry `--no-textconv`.

The hook went through six rounds of cross-family review, and its self-test covers every bypass found (`python3 -I ~/.claude/hooks/scout_readonly.py --selftest`). It does not defend against your own repo-local git config.

scout installs at user level because Claude Code ignores `hooks` frontmatter on plugin agents.

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
