# DELEGATION — think before you hand off

Applies to EVERY agent creation: Paseo `mcp__paseo__create_agent`, the native Agent tool, and Workflow `agent()` calls.

Personal overrides live in `~/.claude/DELEGATION.local.md`: which model counts as your top tier, which gateway model is your advisor, and so on. Where that file conflicts with this one, it wins. Keep this file identical to the plugin template, so updates apply cleanly.

## The rule

Before spawning any agent, classify the task and pick the model deliberately. Never inherit or default the model — always pass `provider` (Paseo) or `model` (native Agent/Workflow) explicitly. State the choice and a one-line reason before spawning (e.g. "normal impl → Claude workhorse").

Classify on two axes:

1. **Difficulty**: trivial / normal / hard / really-hard (resisted a first attempt, or clearly gnarly architecture).
2. **Role**: is this authoring work, or reviewing/challenging another agent's work?

## Tier ladder (stable names — no versioned IDs here)

| Tier | Use for |
|---|---|
| Claude frontier (`fable`) | Really-hard only: second attempts, gnarly architecture. Never routine work. |
| Claude workhorse (`opus`) | Default for implementation, UI, and authoring work. |
| Claude cheap (`sonnet` / `haiku`) | Research and "how does X work" questions (`sonnet`); read-only code lookups and counts (the `scout` agent on `haiku`, see below); trivial mechanical work and tests (`haiku`). |
| OpenAI frontier (top Codex tier, thinking xhigh) | High-stakes review (see the tripwires below), hard contrarian analysis, and reviews that came back inconclusive. |
| OpenAI workhorse (everyday Codex tier) | **Default code reviewer** and design challenger for Claude-authored work. Also authoring work that suits a Codex agent better than a Claude one. |
| OpenAI cheap (cheapest Codex tier) | Trivial mechanical work when a Codex agent fits better, and review of inert text: README prose, comments, changelogs. |
| Third-family advisor (optional: a non-Claude, non-GPT model via a gateway) | Second opinions, design challenges, "is this the right call". Never defect-hunting in real code. |

**Review tier follows the stakes of the artifact, not the fact that it is a review.**
- Running code gets the workhorse reviewer.
- Money, security, data integrity and migrations get the frontier tier.
- Inert text gets the cheap tier, or no review at all.

"A missed bug costs more than the tokens" is a claim about code that executes. It does not price a markdown diff.

**Stakes tripwires — not a vibe check.** Treat a diff as high-stakes if it touches any of these:
- auth or permissions
- payments or money math
- migrations, schema changes or backfills
- concurrency or locking
- secrets or crypto
- data deletion or retention
- a public API contract

**Uncertain counts as high-stakes.** The criterion only drifts one way under time pressure, so the default has to absorb that. State the stakes class in the one-line reason you give when spawning the reviewer, so `/delegation-audit` can grep for it afterwards.

**Cheap-tier review is for inert text only:** README prose, comments, changelogs. A skill file, hook, prompt template or routing config is **behavior**. It changes what agents do, so it reviews as code at the workhorse tier. "It's just markdown" describes the file extension, not the blast radius.

**Codex tier names are not version numbers.** One OpenAI release ships several tiers under different suffixes, and the newest ID is not automatically the strongest. Resolve a tier from the model *description* in `list_models`, never from the ID string. An explicit override recorded in `DELEGATION.local.md` or the prefs beats the description.

Native Agent/Workflow `model` values are the stable aliases: `haiku` / `sonnet` / `opus` / `fable`.
- The native Agent tool takes a separate `effort` value. Pass it when a tier is defined by effort, e.g. a top tier of "workhorse at xhigh".
- Paseo sets effort with the thinking option.
- A Workflow `agent()` call that cannot set effort runs at the model's default effort. Route effort-defined tiers through Agent or Paseo instead.

**Code lookups go to `scout`.** Send read-only lookups and counts ("where is X", "who calls X", "list every X", "how many X") to the native `scout` agent, which `/delegation-setup` installs. Call it as `subagent_type: "scout"`, `model: "haiku"`. Passing any other `model` overrides scout's Haiku. Use scout instead of Explore for these.
- When the target file is already known, do the lookup yourself without an agent.
- If scout reports that its read-only hook blocked a command, answer with the allowed tools or report the limit. Never edit the hook as part of a lookup, and never route around it.

## Fan-out budget — how many, how deep

Picking the right *model* bounds the price per agent, not the total. Volume does that, and a quota blowup is almost always volume, not tier. Before fanning out, budget it:

- **Default caps:** ≤ 4 agents per wave, ≤ 8 per task total. Going wider needs an explicit "yes, go wide" from the user.
- **One level of fan-out.** A spawned agent does its own work — it does not spawn its own sub-agents unless you were told to go that deep. Recursive fan-out is how 4 agents silently become 40.
- **Fan out only if inline won't do.** Valid reasons: (a) the work would bloat the main context, (b) truly parallel tasks that each need a fresh context, (c) independent verification. Anything else stays inline — a single loop measured ~2× faster than a multi-agent harness. A handful of web lookups or file reads is cheaper done inline than as a delegated fleet.
- **Split by context, not by role.** Hand off a slice that needs little from the rest of the task and returns a compact result: an independent research path, a component with a clean interface, a black-box check. Never a planner→implementer→fixer relay; every handoff loses detail.
- **Scope to the deliverable, not the topic.** "One email with a pick and a price" is a couple of lookups, not a market study. Match width to what actually ships.
- **High stakes ≠ upgrade the whole fleet.** "This has to be accurate" justifies *one* top-tier verifier over cheap-tier gathered data, not the entire fleet on the top tier. The top tier is the frontier tier, or whatever `DELEGATION.local.md` names as the top tier. Gather cheap, verify once.
- **Circuit-breaker.** If agents die on quota, rate-limit or API errors, STOP re-spawning on that provider. A retry just widens the crater. Surface the failure and wait for it to clear.
  - **One carve-out, only if the prefs define a `fallback` map:** a different billing pool is a different wall. A subscription-metered provider that runs dry may fail over ONCE to the same tier on a gateway provider.
  - One hop, never a loop. If the fallback dies too, stop and surface it.
  - Failover converts a quota wall into a bill: gateways charge API rates plus a per-token fee. Say in the spawn reason that you failed over, because the audit scan is the only place that cost shows up.
- **Use the smallest context window that fits.** A fleet of 1M-window agents multiplies cost independently of tier.

## Turn budget — the lever that actually bounds spend

Tier sets the price per token; **turns × context** sets the total. Context only grows, and every turn re-reads all of it, so cost is roughly quadratic in turn count: one 240-turn agent costs ~4× four 60-turn agents doing the same work. Measured on a real 23-agent wave, cache reads were 56% of spend, writes 29%, output+thinking 15% — the money is in re-reading context, not in thinking. Capping agent *count* does not cap spend; capping turns does.

- **~80 turns per agent.** Past that, have it write findings to a handoff file and spawn a successor that reads the file instead of inheriting the history.
- **Keep tool output out of context.** `head`/`tail`/`grep -c`/`--quiet` on build, test, and log output; read the line ranges you need, not whole files. Every dumped blob is re-read on every later turn of that agent.
- **Brief tight, scope narrow.** An agent forced to rediscover the codebase pays for that discovery on every subsequent turn.
- **Orchestrator hygiene.** The orchestrator pays its own full context every turn too. One session per wave, resuming from a committed scaffold plus a notes file, beats one session spanning every wave.
- **Spend is concentrated, so audit the tail.** In that wave the top 6 of 23 agents were half the cost. Fix the few fat agents, not the fleet average.

## Reuse before respawn

A finished agent is still alive and still holds its context. The next slice of the same work, a correction, or a review's fix-ups go back to *that* agent — a fresh one pays the context-rebuild cost again and throws away everything the first one learned.

- **Follow-up on the same thread → `mcp__paseo__send_agent_prompt`** (native equivalent: `SendMessage` to the existing agent). Review came back? Send it to the author. Don't spawn author #2.
- **Spawn new only when** the tier must change, the task is genuinely unrelated, the agent's context is poisoned and it can't back out, or it has hit the turn budget or the reuse ceiling.
- **Kill/archive only when done for good.** Killing an agent you're about to re-create at the same tier is pure loss.
- A respawn counts against the fan-out cap; a follow-up doesn't. A follow-up isn't free, though: it re-reads the whole thread, which is exactly what the turn budget prices.
- **Ceiling on reuse.** Reuse beats respawn only while the thread is small. Before a follow-up, check `get_agent_status` → `lastUsage.contextWindowUsedTokens`. Past ~200k, re-reading the history costs more than a fresh agent's rebuild, so hand off to a successor with a short handoff note. If you can't see that number, split after ~5 follow-up rounds on one agent anyway.
- Workflow `agent()` calls are one-shot by design — this rule is about interactive fan-out.

## Contrarian pairing

Substantive work authored by a Claude agent gets its review from a Codex agent, and vice versa. Cross-family review catches blind spots that same-family review misses. Reviewers run at the OpenAI workhorse by default, and high-stakes diffs go to the frontier tier. Escalate the *authoring* side to the Claude frontier only to settle hard disagreements.

**Family follows the *model*, not the CLI.** On a gateway such as Cursor, `cursor/claude-*` counts as Claude and `cursor/gpt-*` as OpenAI. Either satisfies cross-family pairing against the opposite family, but neither adds a *third* voice. An auto-selecting model (e.g. `cursor/auto-smart`) is indeterminate and satisfies nothing. A third voice needs an explicitly non-Claude, non-GPT model (Grok, Gemini, Kimi, GLM, Composer). It is worth the extra agent only as a tiebreaker when Claude and Codex genuinely disagree.

**Cursor gateway traps**, worth knowing before you bind one:
- Reasoning effort is a separate thinking option, and gateway models may default to a lower effort than you intend. Check the model's supported options and always pass the effort explicitly.
- `ask` mode rejects the thinking option. Create advisors in `agent` (or `plan`) mode and enforce read-only in the prompt.
- The `fast` toggle defaults ON, which raises the usage rate on every agent. Pin `features: {"fast": "false"}` and override per agent.
- Every Cursor variant is a 1M-context model, which multiplies cost independently of tier.

The native Agent tool cannot select Codex/OpenAI models — it runs Claude models only. So it can be the cross-family reviewer for Codex-authored work, but never for Claude-authored work: route those through Paseo `create_agent`.

That asymmetry is why one `audit` binding can't satisfy the rule on its own. It names the **Codex-side** reviewer, for Claude-authored work. For Codex-authored work, the reviewer is a Claude one: the native Agent tool, or the `impl` binding via Paseo. Picking `audit` regardless of who wrote the work gives same-family review and quietly voids the pairing.

## Where the concrete bindings live

Versioned model IDs and the Paseo role→provider map live ONLY in `~/.paseo/orchestration-preferences.json` (read it before any Paseo agent creation — the paseo skills already require this). Keep them fresh with `/delegation-audit` (suggested cadence: every 2 weeks).
