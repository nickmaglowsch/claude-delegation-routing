"""PreToolUse hook for the scout agent: allow only read-only Bash commands.

Exit 2 blocks the call and feeds stderr back to the agent.
Fail closed: a small Bash-quoting lexer rejects every unquoted character the shell could expand, redirect,
glob or treat as a comment, then each command is checked against its own option allowlist. Anything it
cannot classify is blocked, so the failure mode is a false block the agent rephrases, never a write.
ponytail: few commands on purpose; Read/Grep/Glob tools cover the rest without a shell.
"""
import json
import re
import sys

UNQUOTED_OK = re.compile(r"[A-Za-z0-9_./:=,@%+\-]")
DQUOTE_BAD = set("$`\\!")
SEPARATORS = ("&&", "||", "|", ";")
SED_PRINT = re.compile(r"^\s*(\d+|\$)(\s*,\s*(\d+|\$))?\s*p\s*$")


class Blocked(Exception):
    pass


def lex(command):
    """Split into commands of words, with Bash quote removal. Raises Blocked on anything risky."""
    commands, words, word, in_word, i = [], [], [], False, 0
    while i < len(command):
        c = command[i]
        if c in " \t":
            if in_word:
                words.append("".join(word))
                word, in_word = [], False
            i += 1
            continue
        sep = next((s for s in SEPARATORS if command.startswith(s, i)), None)
        if sep:
            if in_word:
                words.append("".join(word))
                word, in_word = [], False
            commands.append(words)
            words = []
            i += len(sep)
            continue
        if c == "'":
            end = command.find("'", i + 1)
            if end < 0:
                raise Blocked("unterminated quote")
            word.append(command[i + 1:end])
            in_word, i = True, end + 1
            continue
        if c == '"':
            end = command.find('"', i + 1)
            if end < 0:
                raise Blocked("unterminated quote")
            body = command[i + 1:end]
            if DQUOTE_BAD.intersection(body):
                raise Blocked("$, backtick, backslash or ! inside double quotes; use single quotes")
            word.append(body)
            in_word, i = True, end + 1
            continue
        if not UNQUOTED_OK.match(c):
            raise Blocked("unquoted %r is not allowed (no redirects, &, $, #, globs, braces, newlines); quote patterns in single quotes" % c)
        word.append(c)
        in_word, i = True, i + 1
    if in_word:
        words.append("".join(word))
    commands.append(words)
    return commands


def short_flags(arg, allowed):
    return re.fullmatch(r"-[%s]+" % re.escape(allowed), arg) is not None


# Exact option tables per git subcommand: (flag chars, chars that take a value, long names; '=' means value form).
GIT_OPTS = {
    "grep": ("nIFEPiwvlLchHozqWp0123456789", "efABCm",
             {"--untracked", "--cached", "--no-index", "--line-number", "--count", "--files-with-matches",
              "--files-without-match", "--name-only", "--only-matching", "--ignore-case", "--word-regexp",
              "--fixed-strings", "--extended-regexp", "--perl-regexp", "--invert-match", "--heading", "--break",
              "--and", "--or", "--not", "--all-match", "--full-name", "--column", "--max-count="}),
    "log": ("p0123456789", "nSGL",
            {"--oneline", "--stat", "--name-only", "--name-status", "--follow", "--all", "--no-merges",
             "--reverse", "--first-parent", "--abbrev-commit", "--patch", "--no-patch", "--no-color",
             "--format=", "--pretty=", "--since=", "--until=", "--author=", "--grep=", "--max-count=",
             "--date=", "--unified=", "--no-textconv"}),
    "show": ("p", "",
             {"--stat", "--name-only", "--name-status", "--no-patch", "--oneline", "--no-color",
              "--format=", "--pretty=", "--unified=", "--no-textconv"}),
    "ls-files": ("coz", "", {"--others", "--cached", "--exclude-standard", "--full-name", "--error-unmatch"}),
    "blame": ("wesl", "L", {"--porcelain", "--line-porcelain", "--show-email", "--no-textconv"}),
    "rev-parse": ("", "", {"--show-toplevel", "--short", "--abbrev-ref", "--git-dir", "--verify"}),
}


def check_git(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            i += 2
        elif args[i] == "--no-pager":
            i += 1
        else:
            raise Blocked("git global option %s is not allowed" % args[i])
    if i >= len(args) or args[i] not in GIT_OPTS:
        raise Blocked("git %s is not allowed" % (args[i] if i < len(args) else ""))
    sub = args[i]
    flags, valued, longs = GIT_OPTS[sub]
    rest, j = args[i + 1:], 0
    # show and blame always diff/convert; log only with a patch. textconv runs configured helper programs.
    needs_no_textconv = sub in ("show", "blame")
    seen = set()
    while j < len(rest):
        a = rest[j]
        j += 1
        if a == "--":
            break
        if re.search(r"%[-+ ]*G", a):
            raise Blocked("%G format placeholders run the signature verifier")
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            if (name + "=" if eq else name) not in longs:
                raise Blocked("git option %s is not allowed (exact names only)" % a)
            if name == "--unified" and not value.isdigit():
                raise Blocked("--unified needs a number")
            seen.add(name)
            needs_no_textconv |= name in ("--patch", "--unified")
        elif a.startswith("-") and a != "-":
            for k, ch in enumerate(a[1:]):
                if ch == "U":  # only -U<n> with the number attached; bare -U takes no value in git
                    if not a[k + 2:].isdigit():
                        raise Blocked("use -U<n> with the number attached, e.g. -U3")
                    needs_no_textconv = True
                    break
                if ch in valued:
                    if k == len(a) - 2:
                        j += 1  # value is the next arg, never parsed as an option
                    break
                if ch not in flags:
                    raise Blocked("git option -%s is not allowed" % ch)
                needs_no_textconv |= sub == "log" and ch == "p"
    if needs_no_textconv and "--no-textconv" not in seen:
        raise Blocked("add --no-textconv to git %s so no configured helper program runs" % sub)


def check_sed(args):
    scripts, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-n", "-E"):
            pass
        elif a == "-e" and i + 1 < len(args):
            scripts.append(args[i + 1])
            i += 1
        elif a.startswith("-"):
            raise Blocked("sed option %s is not allowed" % a)
        elif not scripts:
            scripts.append(a)
        i += 1
    for script in scripts:
        for part in script.split(";"):
            if part.strip() and not SED_PRINT.match(part):
                raise Blocked("sed script %r must be a line-range print like 40,60p" % part)


def check_flags(name, args, allowed, takes_value="", max_operands=None):
    operands, i = 0, 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and a != "-":
            if takes_value and a[:2] in {"-" + v for v in takes_value}:
                if len(a) == 2:
                    i += 1
            elif not short_flags(a, allowed):
                raise Blocked("%s option %s is not allowed" % (name, a))
        else:
            operands += 1
        i += 1
    if max_operands is not None and operands > max_operands:
        raise Blocked("%s with %d operands could write a file" % (name, operands))


def check(words):
    name, args = words[0], words[1:]
    if name == "git":
        check_git(args)
    elif name == "sed":
        check_sed(args)
    elif name == "wc":
        check_flags(name, args, "lwcm")
    elif name == "sort":
        check_flags(name, args, "unrfVb", takes_value="kt")
    elif name == "uniq":
        check_flags(name, args, "cdui", max_operands=1)
    elif name in ("head", "tail"):
        check_flags(name, args, "0123456789", takes_value="n")
    elif name == "cut":
        check_flags(name, args, "s", takes_value="dfc")
    elif name == "tr":
        check_flags(name, args, "dsc", max_operands=2)
    elif name == "echo":
        pass  # cannot write: the lexer already blocks every redirect
    elif name == "cd":
        if len(args) > 1:
            raise Blocked("cd takes one directory")
    else:
        raise Blocked("%s is not allowed; use the Read, Grep or Glob tool instead" % name)


def problem(command):
    try:
        for words in lex(command):
            if not words:
                raise Blocked("empty command around a separator")
            check(words)
    except Blocked as exc:
        return str(exc)
    return None


def main():
    data = json.load(sys.stdin)
    reason = problem(data.get("tool_input", {}).get("command", ""))
    if reason:
        print("scout is read-only: " + reason, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        ok = ["git grep -nIF -e 'handle_request(' -- lib | wc -l",
              "cd /repo && git grep -h -o 'mount_tag(.[^.]*.)' -- templates | sort -u | wc -l",
              "sed -n '40,60p' app.py", "git grep -E 'foo|bar' -- lib",
              "git -C /repo grep -nIF -e needle", "git grep -o 'x' | cut -d : -f 2 | sort | uniq -c", "git grep -nIF -e '-O' -- lib",
              "git grep -nIF -e '--output' -- lib", "git log --format=%h -3 -- lib", "git grep -n -A3 foo",
              "git log --oneline -5", "sed -n '1,5p;10,12p' a.py", "git grep -nIF -e '>' -- lib",
              "git grep -l 'notes' -- templates | wc -l", "git grep --untracked -nIF -e foo",
              "git show --no-textconv HEAD:lib/db.py | sed -n '1,20p'", "git log -p --no-textconv -3", "git log -U3 --no-textconv -1", "git grep -P -e 'foo(?=bar)' -- lib", "echo ---", "git grep -np -e 'foo' -- lib", "git blame --no-textconv -L 1,5 a.py", "sort -k 2 -t : -n | head -n 30",
              "git ls-files 'templates/*.html' | wc -l", "cut -d : -f 1 | sort -u"]
        bad = ["git grep foo > /tmp/x", "sed -i 's/a/b/' f.py", "rm -rf lib", "git checkout -- .",
               "echo hi | tee out.txt", "python3 -c 'open(1)'", "cat $(ls)", "touch /tmp/scout-test",
               "git grep x & touch /tmp/x", "cat <(touch /tmp/x)", "sort -o /tmp/x /etc/hosts",
               "sort -uo /tmp/x /etc/hosts", "uniq /etc/hosts /tmp/x", "sed -n '1w /tmp/x' /etc/hosts",
               "git diff --output=/tmp/x", "git -c core.pager=sh log", "git log --output=/tmp/x",
               "sed 's/a/b/w /tmp/x' f", "git grep x\ntouch /tmp/x", "FOO=1 touch x", "git grep -Ovim foo",
               "git grep x#; touch /tmp/x", "sort $'-o' /tmp/x /etc/hosts", "sort {-o,} /tmp/x a",
               "sort * ", "git grep \"$HOME\"", "git grep x 2>/dev/null", "sort \\-o x",
               "file -C -m /etc/magic", "rg --hostname-bin=/p --hyperlink-format=default x",
               "git grep x ; ", "sort '-'o /tmp/x a", "git grep -e '--' -O'touch /tmp/x' -- lib",
               "git grep --open-files-in-page=sh x", "sed 's/^/\\\\/w lib/g' /etc/hosts", "sed 's/a/b/' f",
               "git log --output-directory=/tmp", "git show --ext-diff", "git log -U --output=/tmp/x", "git show -U --output=/tmp/x", "git log --format=%G? -3", "git log --format='%+G?' -1", "git log --format='%-G?' -1", "git log --format='% G?' -1", "git log -p -3", "git show HEAD", "git blame a.py", "git log --unified= -p --no-textconv"]
        for c in ok:
            assert problem(c) is None, (c, problem(c))
        for c in bad:
            assert problem(c) is not None, c
        print("selftest ok (%d allowed, %d blocked)" % (len(ok), len(bad)))
    else:
        main()
