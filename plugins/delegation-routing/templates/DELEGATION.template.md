# DELEGATION — think before you hand off

Applies to EVERY agent creation: Paseo `mcp__paseo__create_agent`, the native Agent tool, and Workflow `agent()` calls.

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
| Claude cheap (`sonnet` / `haiku`) | Research/search (`sonnet`); trivial mechanical work and tests (`haiku`). |
| OpenAI frontier (top Codex tier, thinking xhigh) | Hard contrarian analysis, high-stakes reviews, repeatedly inconclusive reviews. |
| OpenAI workhorse (default Codex tier) | Default contrarian reviewer and design challenger. |
| OpenAI cheap (mini Codex tier) | Trivial mechanical work when a Codex agent fits better. |

Native Agent/Workflow `model` values are the stable aliases: `haiku` / `sonnet` / `opus` / `fable`.

## Fan-out budget — how many, how deep

Picking the right *model* bounds the price per agent, not the total. Volume does that, and a quota blowup is almost always volume, not tier. Before fanning out, budget it:

- **Default caps:** ≤ 4 agents per wave, ≤ 8 per task total. Going wider needs an explicit "yes, go wide" from the user.
- **One level of fan-out.** A spawned agent does its own work — it does not spawn its own sub-agents unless you were told to go that deep. Recursive fan-out is how 4 agents silently become 40.
- **Fan out only if inline won't do.** A handful of web lookups or file reads is cheaper done inline than as a delegated fleet. First question: does this need sub-agents at all?
- **Scope to the deliverable, not the topic.** "One email with a pick and a price" is a couple of lookups, not a market study. Match width to what actually ships.
- **High stakes ≠ upgrade the whole fleet.** "This has to be accurate" justifies *one* workhorse/frontier verifier over cheap-tier gathered data — not the entire fleet on the frontier tier. Gather cheap, verify once.
- **Circuit-breaker.** If agents die on quota / rate-limit / API errors, STOP. Do not re-spawn into the same wall — surface the failure and wait for it to clear.
- **Watch context size too.** A fleet of large-context (e.g. 1M) agents multiplies token cost independently of tier. Use the smallest window that fits the task.

## Contrarian pairing

Substantive work authored by a Claude agent gets its review from a Codex agent, and vice versa — cross-family review catches blind spots same-family review misses. Frontier-vs-frontier (Fable vs top Codex tier) only to settle hard disagreements.

## Where the concrete bindings live

Versioned model IDs and the Paseo role→provider map live ONLY in `~/.paseo/orchestration-preferences.json` (read it before any Paseo agent creation — the paseo skills already require this). Keep them fresh with `/delegation-audit` (suggested cadence: every 2 weeks).
