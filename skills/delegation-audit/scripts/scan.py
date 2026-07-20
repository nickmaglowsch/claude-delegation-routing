#!/usr/bin/env python3
"""Delegation audit scanner.

Stateless: walks Claude Code session transcripts, extracts agent-creation
tool calls (paseo create_agent + native Agent/Task tool) and downstream
friction signals that suggest the WRONG MODEL was chosen. Emits a plain-text
report; an LLM triages it afterwards. Zero LLM tokens spent here.

Deliberately NOT counted (noisy — usually bad task packaging, not wrong
model): raw retry counts, long runtimes, test failures, permission errors.
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter

CREATE_TOOLS = {"mcp__paseo__create_agent"}
NATIVE_AGENT_TOOLS = {"Agent", "Task"}
SKIP_DIRS = {"subagents", "tool-results", "memory"}

# Heuristic tier rank — version-tolerant substrings, checked in order.
TIER_RULES = [
    ("fable", 3), ("mythos", 3),
    ("gpt-5.5", 3), ("gpt-5.6", 3), ("gpt-6", 3),
    ("mini", 0), ("haiku", 0),
    ("opus", 2), ("gpt-", 2),
    ("sonnet", 1),
]
TIER_NAMES = {0: "cheap", 1: "light", 2: "workhorse", 3: "frontier"}

MECHANICAL_RE = re.compile(
    r"\b(rename|typo|reformat|format.only|lint|boilerplate|scaffold|"
    r"fix imports|copy.paste|move (the )?file|bump (the )?version)\b",
    re.IGNORECASE,
)

# Strong = correction explicitly attacking depth/overkill/speed/cost or
# demanding a model switch. Medium = generic pushback near a handoff.
STRONG_PATTERNS = [
    (re.compile(r"\b(too (shallow|superficial|weak)|not (deep|thorough|smart) enough)\b", re.I), "depth"),
    (re.compile(r"\b(overkill|too expensive|wast\w* tokens|burn\w* tokens|too costly|cheaper model)\b", re.I), "cost"),
    (re.compile(r"\buse (a )?(bigger|smarter|better|stronger|smaller) model\b", re.I), "model-switch"),
    (re.compile(r"\b(switch|change) (it |this |the agent )?to (fable|opus|sonnet|haiku|gpt|codex|claude)\b", re.I), "model-switch"),
    (re.compile(r"\bshould have used (fable|opus|sonnet|haiku|gpt|codex|claude)\b", re.I), "model-switch"),
]
MEDIUM_PATTERNS = [
    (re.compile(r"^(no|wait|stop|hold on)\b", re.I), "pushback"),
    (re.compile(r"^actually\b", re.I), "pushback"),
    (re.compile(r"\b(redo|re-do|start over|try again|do it again)\b", re.I), "redo"),
    (re.compile(r"\bthat'?s (wrong|not (right|it|what))\b", re.I), "wrong"),
]

STOPWORDS = frozenset(
    "the a an and or of to in for on with this that is are be it as at by from".split()
)


def tier_of(model):
    m = (model or "").lower()
    for sub, rank in TIER_RULES:
        if sub in m:
            return rank
    return None


def family_of(provider_or_model):
    s = (provider_or_model or "").lower()
    if "claude" in s or s in {"haiku", "sonnet", "opus", "fable"}:
        return "claude"
    if "gpt" in s or "codex" in s:
        return "openai"
    return "unknown"


def word_set(text):
    return {w for w in re.findall(r"[a-z0-9][a-z0-9_-]+", (text or "").lower()) if w not in STOPWORDS}


def similar(a, b, threshold=0.4):
    wa, wb = word_set(a), word_set(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= threshold


def user_text(entry):
    """Real user text only — skip tool results, bash I/O, hook output."""
    if entry.get("type") != "user":
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        content = "\n".join(p for p in parts if p)
    if not isinstance(content, str) or not content.strip():
        return None
    if re.match(r"\s*<(bash-input|bash-stdout|local-command-stdout|task-notification)", content):
        return None
    # Machine notifications, not the human: paseo agent-finished blocks arrive
    # wrapped in "[Request interrupted by user]", so strip the marker and skip
    # anything that isn't leftover human text.
    if "<paseo-system>" in content or content.lstrip().startswith("[SYSTEM NOTIFICATION"):
        return None
    if re.match(r"\s*\S+( \S+)? hook (feedback|success|error|denied)", content):
        return None
    content = re.sub(r"\[Request interrupted by user[^\]]*\]", "", content)
    content = re.sub(r"<system-reminder>.*?</system-reminder>", "", content, flags=re.S).strip()
    return content or None


def creations_in(entry):
    """Yield (tool, model_or_provider, title, prompt_snippet, explicit) for agent-creation tool_use blocks."""
    if entry.get("type") != "assistant":
        return
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name", "")
        inp = block.get("input") or {}
        if name in CREATE_TOOLS:
            yield name, inp.get("provider", ""), inp.get("title", ""), str(inp.get("initialPrompt", ""))[:200], True
        elif name in NATIVE_AGENT_TOOLS:
            model = inp.get("model")
            yield name, model or "(inherited)", inp.get("description", ""), str(inp.get("prompt", ""))[:200], bool(model)


def scan_file(path):
    """Return (creations, user_turns); creations get friction attached in-place."""
    creations, user_turns = [], []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for idx, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                ts = entry.get("timestamp", "")
                for tool, model, title, prompt, explicit in creations_in(entry):
                    creations.append({
                        "idx": idx, "ts": ts, "tool": tool, "model": model,
                        "title": title, "prompt": prompt, "explicit": explicit,
                        "file": path, "cwd": entry.get("cwd", ""), "friction": [],
                    })
                text = user_text(entry)
                if text:
                    user_turns.append((idx, text))
    except OSError:
        pass
    return creations, user_turns


def attach_friction(creations, user_turns):
    for c in creations:
        following = [t for i, t in user_turns if i > c["idx"]][:5]
        for text in following:
            head = text[:400]
            for pat, label in STRONG_PATTERNS:
                if pat.search(head):
                    c["friction"].append(("strong", label, head.splitlines()[0][:120]))
                    break
            else:
                for pat, label in MEDIUM_PATTERNS:
                    if pat.search(head):
                        c["friction"].append(("medium", label, head.splitlines()[0][:120]))
                        break


def find_escalations(creations):
    """Same-session re-launch of a similar task on a bigger tier or the other family."""
    out = []
    for i, a in enumerate(creations):
        for b in creations[i + 1:]:
            if b["file"] != a["file"]:
                continue
            if not similar(a["title"] + " " + a["prompt"], b["title"] + " " + b["prompt"]):
                continue
            ta, tb = tier_of(a["model"]), tier_of(b["model"])
            fam_switch = family_of(a["model"]) != family_of(b["model"]) != "unknown"
            if (ta is not None and tb is not None and tb > ta) or fam_switch:
                out.append((a, b, "tier-up" if (ta is not None and tb is not None and tb > ta) else "family-switch"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--max-events", type=int, default=15)
    args = ap.parse_args()

    cutoff = time.time() - args.days * 86400
    all_creations, files_scanned = [], 0

    for root, dirs, files in os.walk(args.projects_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(root, fn)
            try:
                if os.path.getmtime(path) < cutoff:
                    continue
            except OSError:
                continue
            files_scanned += 1
            creations, user_turns = scan_file(path)
            attach_friction(creations, user_turns)
            all_creations.extend(creations)

    all_creations.sort(key=lambda c: c["ts"])
    escalations = find_escalations(all_creations)
    inherited = [c for c in all_creations if not c["explicit"]]
    frontier_mechanical = [
        c for c in all_creations
        if tier_of(c["model"]) == 3 and MECHANICAL_RE.search(c["title"] + " " + c["prompt"])
    ]
    frictioned = [c for c in all_creations if c["friction"]]

    print(f"DELEGATION AUDIT — last {args.days} days")
    print(f"files scanned: {files_scanned} | agent creations: {len(all_creations)} "
          f"(paseo: {sum(1 for c in all_creations if c['tool'] in CREATE_TOOLS)}, "
          f"native: {sum(1 for c in all_creations if c['tool'] in NATIVE_AGENT_TOOLS)})")

    print("\n== Routing histogram (model -> count) ==")
    for model, n in Counter(c["model"] for c in all_creations).most_common():
        tier = tier_of(model)
        print(f"  {model:<32} {n:>4}  [{TIER_NAMES.get(tier, 'unknown-tier')}]")

    print(f"\n== Inherited/default model (native tool, no explicit model): {len(inherited)} ==")
    for c in inherited[-args.max_events:]:
        print(f"  {c['ts'][:10]} {c['tool']}: {c['title'][:80]}  ({c['cwd']})")

    print(f"\n== Escalations (similar task re-launched bigger/other-family): {len(escalations)} ==")
    for a, b, kind in escalations[-args.max_events:]:
        print(f"  [{kind}] {a['ts'][:10]} {a['model']} -> {b['model']}: {a['title'][:70]}")

    print(f"\n== Frontier model on mechanical-looking work: {len(frontier_mechanical)} ==")
    for c in frontier_mechanical[-args.max_events:]:
        print(f"  {c['ts'][:10]} {c['model']}: {c['title'][:80]}")

    print(f"\n== Friction events (user pushback within 5 turns of a handoff): {len(frictioned)} ==")
    for c in list(reversed(frictioned))[:args.max_events]:
        strongest = sorted(c["friction"], key=lambda f: f[0] != "strong")[0]
        print(f"  [{strongest[0]}:{strongest[1]}] {c['ts'][:10]} {c['model']} — {c['title'][:60]}")
        print(f"      quote: {strongest[2]}")
        print(f"      session: {os.path.basename(c['file'])}  cwd: {c['cwd']}")

    if not (inherited or escalations or frontier_mechanical or frictioned):
        print("\nALL CLEAN — no misroute signals in the window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
