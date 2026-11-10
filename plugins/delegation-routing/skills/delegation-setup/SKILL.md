---
name: delegation-setup
description: One-time setup for deliberate model routing — template a think-before-handoff DELEGATION.md into ~/.claude (with the global CLAUDE.md @-include) and, if Paseo is available, generate ~/.paseo/orchestration-preferences.json from the LIVE model list instead of hardcoded IDs. Use when the user says "set up delegation routing", "install the delegation policy", "delegation setup", or right after installing the delegation-routing plugin.
---

# Delegation Setup

Templates the routing policy into place. Nothing here ships frozen model IDs — bindings are generated from what your providers expose right now. Ask before overwriting anything that already exists.

## Step 1: Install the policy file

Copy `${CLAUDE_PLUGIN_ROOT}/templates/DELEGATION.template.md` to `~/.claude/DELEGATION.md`. If the destination already exists and differs, show a diff and ask before replacing.

Then ensure `~/.claude/CLAUDE.md` contains a line `@DELEGATION.md` (append it if missing; create the file if absent). This puts the think-before-handoff rule in context every session.

## Step 2: Generate Paseo bindings (skip cleanly if no Paseo)

Check whether the Paseo MCP server is available (ToolSearch for `mcp__paseo__list_models`). If not, say so — the DELEGATION.md policy still governs native Agent/Workflow fan-out — and go to Step 4.


If available:

1. Call `mcp__paseo__list_providers`, then `mcp__paseo__list_models` for each enabled provider.
2. Map tiers per family from the live list (do NOT invent IDs):
   - frontier = the top/most-capable model, workhorse = the default/everyday strong model, cheap = the smallest.
3. Ask the user (AskUserQuestion) only what genuinely varies: which family is the implementation workhorse, and which is the contrarian reviewer. Default suggestion: Claude implements, OpenAI-family reviews/challenges.
4. Fill every `<placeholder>` in `${CLAUDE_PLUGIN_ROOT}/templates/orchestration-preferences.template.json` with the chosen live IDs, drop the `_comment` key, and write `~/.paseo/orchestration-preferences.json`. If the file already exists, show a diff and ask before replacing.
5. Validate: `python3 -m json.tool ~/.paseo/orchestration-preferences.json`.

## Step 3: Smoke-test (optional, ask first)

Offer to create one throwaway Paseo agent with a bound provider string to prove the format is accepted, then archive it immediately.

## Step 4: Install the `scout` lookup agent (optional, ask first)

`scout` is a read-only code-search subagent. It answers "where is X", "who calls X", "list every X" and "how many X" with file:line evidence. It runs on the cheap tier (`haiku`) with a search protocol and a fail-closed read-only Bash hook. The README has the benchmark behind it.

It installs at **user level**, not as a plugin agent. Claude Code ignores `hooks` frontmatter on plugin subagents, so a plugin copy would load without its read-only guard and give no warning.

1. Check that `python3` is on PATH, since the hook needs it. If it is missing, say so and skip this step.
2. Before copying anything, check both destinations: `~/.claude/hooks/scout_readonly.py` and `~/.claude/agents/scout.md`. For each one that exists and differs from the template, show a diff and ask. If the user declines either file, stop and change nothing.
3. Back up every existing destination you will replace to `<file>.bak-<YYYYMMDD-HHMMSS>`, using `cp -n` so an existing backup is never overwritten. If that path is taken, add a counter.
4. Copy the hook first: `${CLAUDE_PLUGIN_ROOT}/templates/hooks/scout_readonly.py` to `~/.claude/hooks/scout_readonly.py`. Run `python3 -I ~/.claude/hooks/scout_readonly.py --selftest`. It must print `selftest ok`. If it does not, restore the hook from the backup you made, or delete it if there was no earlier copy. Report the failure and stop without touching the agent file.
5. Only after a passing self-test, copy `${CLAUDE_PLUGIN_ROOT}/templates/agents/scout.md` to `~/.claude/agents/scout.md`. The agent never exists without a passing hook.
6. Tell the user where the backups are.

The DELEGATION.md template already routes lookups and counts to `scout`. If the user declines this step, say that the routing line will name an agent that is not installed, so they can delete that line.

## Step 5: Wrap up

Tell the user: open a NEW session (the @-include loads at startup), and schedule the refinement loop — `/loop 2w /delegation-audit`. Bindings drift as models ship; the audit's drift check proposes rebindings.

## Rules

- Never overwrite an existing file without showing a diff and getting an explicit OK.
- Never write a model ID that didn't come from `list_models` output.
- If a provider family is missing (e.g. no Codex), bind all roles within the available family and note that cross-family review is unavailable.
- Never install `scout` as a plugin agent, and never install it without its hook. A missing guard is silent.
