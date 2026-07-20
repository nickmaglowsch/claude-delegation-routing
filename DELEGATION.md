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

## Contrarian pairing

Substantive work authored by a Claude agent gets its review from a Codex agent, and vice versa — cross-family review catches blind spots same-family review misses. Frontier-vs-frontier (Fable vs top Codex tier) only to settle hard disagreements.

## Where the concrete bindings live

Versioned model IDs and the Paseo role→provider map live ONLY in `~/.paseo/orchestration-preferences.json` (read it before any Paseo agent creation — the paseo skills already require this). Keep them fresh with `/delegation-audit` (suggested cadence: every 2 weeks).
