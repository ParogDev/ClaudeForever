"""Static checks of an aura source file against the installed ForeverAuras code."""

import os
import re

import lualit
import transmission

GROUP_TYPES = ("group", "dynamicgroup")
NO_EVENT_TYPES = ("custom", "aura2", "secretAura")


class FaIndex:
    """What the installed addon registers: region types, trigger types, event prototypes."""

    def __init__(self, fa_dir):
        self.fa_dir = fa_dir
        self.region_types = set()
        self.trigger_types = set(NO_EVENT_TYPES)
        self.events = {}  # prototype name -> trigger type (None: type not resolved)
        self.internal_version = transmission.internal_version(fa_dir)
        texts = {}
        for root, dirs, files in os.walk(fa_dir):
            dirs[:] = [d for d in dirs if d != "Libs"]
            for name in files:
                if name.endswith(".lua"):
                    path = os.path.join(root, name)
                    with open(path, encoding="utf-8", errors="replace") as f:
                        texts[path] = f.read()
        proto = os.path.join(fa_dir, "Prototypes.lua")
        if proto not in texts:
            raise FileNotFoundError("Prototypes.lua not found under %s (pass --fa-dir)" % fa_dir)
        everything = "\n".join(texts.values())
        self.region_types.update(re.findall(r'RegisterRegionType\("(\w+)"', everything))
        for group in re.findall(r"RegisterTriggerSystem\(\{([^}]*)\}", everything):
            self.trigger_types.update(re.findall(r'"(\w+)"', group))
        self._prototypes(texts[proto], everything)
        self.trigger_types.update(t for t in self.events.values() if t)

    def _prototypes(self, proto, everything):
        lines = proto.splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("Private.event_prototypes = {"))
        key, aliases = None, {}
        for line in lines[start + 1:]:
            if re.match(r"^\}", line):
                break
            m = re.match(r'^  \["(.+?)"\]\s*=\s*(.*)$', line)
            if m:
                key, rhs = m.group(1), m.group(2)
                self.events[key] = None
                a = re.match(r"Private\.(\w+)", rhs)
                if a:
                    aliases[key] = a.group(1)
                continue
            t = re.match(r'^    type = "(\w+)"', line)
            if t and key and self.events[key] is None and key not in aliases:
                self.events[key] = t.group(1)
        assign = r'^[ \t]*(?:Private\.)?event_prototypes\["([^"\n]+)"\][ \t]*=[ \t]*\{(.{0,400})'
        for m in re.finditer(assign, everything, re.S | re.M):
            t = re.search(r'\btype = "(\w+)"', m.group(2))
            self.events[m.group(1)] = t.group(1) if t else None
        copies = {}
        for m in re.finditer(r"for \w+, \w+ in pairs\(Private\.(\w+)\) do(.{0,400}?)\bend\b", everything, re.S):
            for target in re.findall(r"Private\.(\w+)\[\w+\] = ", m.group(2)):
                copies[target] = m.group(1)
        for key, name in aliases.items():
            seen = set()
            while name in copies and name not in seen:
                seen.add(name)
                name = copies[name]
            t = re.search(r"Private\.%s = \{\s*\n\s*type = \"(\w+)\"" % re.escape(name), everything)
            self.events[key] = t.group(1) if t else None


def _array(t):
    if isinstance(t, (dict, list)):
        return lualit.split_table(t)[0]
    return []


def _custom_code_count(value, key=""):
    if isinstance(value, str):
        return 1 if key.startswith("custom") and "function" in value else 0
    if isinstance(value, dict):
        return sum(_custom_code_count(v, k if isinstance(k, str) else key) for k, v in value.items())
    if isinstance(value, list):
        return sum(_custom_code_count(v, key) for v in value)
    return 0


def custom_code(value, path="", key=""):
    """(path, code) for every custom code string, the same strings _custom_code_count counts."""
    if isinstance(value, str):
        return [(path, value)] if key.startswith("custom") and "function" in value else []
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            found += custom_code(v, "%s.%s" % (path, k) if path else str(k), k if isinstance(k, str) else key)
    elif isinstance(value, list):
        for i, v in enumerate(value, 1):
            found += custom_code(v, "%s[%d]" % (path, i), key)
    return found


LOCAL = "local"


def compile_remote(codes, remote=LOCAL, image="wowf/lua51"):
    """Compile each code string as ForeverAuras does ("return " .. code) with luac5.1 in the
    wowf/lua51 container (tools\\lua.ps1 builds it): on this PC's Docker when `remote` is "local"
    (or empty), else on that ssh host's. Returns a list of error strings naming the aura path."""
    import subprocess
    lines, owner = [], []
    for n, (where, code) in enumerate(codes):
        chunk = "do local _ = %s end\n" % code  # do..end: no 200-locals limit however many strings
        start = len(lines) + 1
        lines += chunk.splitlines()
        owner.append((start, len(lines), where))
    src = "\n".join(lines) + "\n"
    # luac5.1 ignores "-" after -p, and the image's entrypoint wraps shell commands: read /dev/stdin.
    if not remote or remote == LOCAL:
        where_ = "local Docker"
        cmd = ["docker", "run", "-i", "--rm", "--entrypoint", "luac5.1", image, "-p", "/dev/stdin"]
    else:
        where_ = remote
        cmd = ["ssh", remote, "docker run -i --rm --entrypoint luac5.1 %s -p /dev/stdin" % image]
    try:
        proc = subprocess.run(cmd, input=src.encode("utf-8"), capture_output=True, timeout=120)
    except FileNotFoundError as e:
        raise OSError("cannot compile on %s: %s not found (is Docker installed?)" % (where_, cmd[0])) from e
    if proc.returncode == 0:
        return []
    err = proc.stderr.decode("utf-8", "replace").strip()
    m = re.search(r"stdin:(\d+):\s*(.*)", err)
    if not m:
        raise OSError("luac on %s failed without a line number (Docker not running, or the wowf/lua51 image "
                      "missing: run tools\\lua.ps1 build): %s" % (where_, err))
    line = int(m.group(1))
    opened = re.search(r"at line (\d+)\)", m.group(2))
    if opened:  # an unclosed block runs to <eof>; the owner is where the block opened
        line = int(opened.group(1))
    for start, end, where in owner:
        if start <= line <= end:
            return ["%s: line %d of its code: %s" % (where, line - start + 1, m.group(2))]
    return [err]


def lint(src, index):
    """Returns (errors, warnings, notes) as lists of strings."""
    errors, warnings, notes = [], [], []
    data = src.get("d")
    children = transmission.children_of(src)
    auras = [data] + children
    ids, uids = {}, {}
    for n, aura in enumerate(auras):
        where = "d" if n == 0 else "c[%d]" % n
        aid = aura.get("id")
        if not isinstance(aid, str) or not aid:
            errors.append("%s: no id" % where)
            continue
        if aid in ids:
            errors.append("%s: id %r is also used by %s" % (where, aid, ids[aid]))
        ids[aid] = where
        uid = aura.get("uid")
        if uid is not None:
            if not isinstance(uid, str):
                errors.append("%r: uid must be a string" % aid)
            elif uid in uids:
                errors.append("%r: uid %s is also used by %r" % (aid, uid, uids[uid]))
            else:
                uids[uid] = aid
        iv = aura.get("internalVersion")
        if iv != index.internal_version:
            errors.append("%r: internalVersion is %r, the installed addon is at %d"
                          % (aid, iv, index.internal_version))
        _lint_aura(aid, aura, index, errors)

    if not uids:
        notes.append("no uid set: every import adds new copies instead of updating the old ones")
    groups = {a.get("id"): a for a in auras if a.get("controlledChildren") is not None}
    if children and data.get("regionType") not in GROUP_TYPES:
        errors.append("%r has children but regionType %r is not a group" % (data.get("id"), data.get("regionType")))
    nested = any(ch.get("controlledChildren") is not None for ch in children)
    for ch in children:
        parent = ch.get("parent")
        cid = ch.get("id")
        if parent is None:
            if nested:
                errors.append("%r: no parent (needed when the group has subgroups)" % cid)
            continue
        if parent not in groups:
            errors.append("%r: parent %r is not a group in this file" % (cid, parent))
        elif cid not in _array(groups[parent].get("controlledChildren")):
            errors.append("%r: not listed in %r's controlledChildren" % (cid, parent))
        if not nested and parent != data.get("id"):
            errors.append("%r: parent %r is not the group id %r" % (cid, parent, data.get("id")))
    for gid, g in groups.items():
        for cid in _array(g.get("controlledChildren")):
            if cid not in ids:
                errors.append("%r lists child %r, which is not in c" % (gid, cid))
    if data.get("controlledChildren") is not None and not nested:
        listed = set(_array(data.get("controlledChildren")))
        for ch in children:
            if ch.get("id") not in listed:
                errors.append("%r is in c but not in %r's controlledChildren" % (ch.get("id"), data.get("id")))
    count = sum(_custom_code_count(a) for a in auras)
    if count:
        notes.append("%d custom code string(s): not checked (no Lua 5.1 compiler here)" % count)
    return errors, warnings, notes


def _lint_aura(aid, aura, index, errors):
    region = aura.get("regionType")
    if region not in index.region_types:
        errors.append("%r: regionType %r is not registered (known: %s)"
                      % (aid, region, ", ".join(sorted(index.region_types))))
    if region in GROUP_TYPES:
        return
    triggers = aura.get("triggers")
    entries = _array(triggers)
    if not entries:
        errors.append("%r: no triggers[1]" % aid)
        return
    for i, entry in enumerate(entries, 1):
        trig = entry.get("trigger") if isinstance(entry, dict) else None
        if not isinstance(trig, dict):
            errors.append("%r: triggers[%d] has no trigger table" % (aid, i))
            continue
        ttype, event = trig.get("type"), trig.get("event")
        if ttype is None:
            errors.append("%r: triggers[%d].trigger.type is not set" % (aid, i))
            continue
        if ttype not in index.trigger_types:
            errors.append("%r: triggers[%d] type %r is not a registered trigger type" % (aid, i, ttype))
            continue
        if ttype in NO_EVENT_TYPES:
            continue
        if event is None:
            errors.append("%r: triggers[%d] type %r needs an event" % (aid, i, ttype))
        elif event not in index.events:
            errors.append("%r: triggers[%d] event %r is not an event prototype" % (aid, i, event))
        elif index.events[event] not in (None, ttype):
            errors.append("%r: triggers[%d] event %r belongs to type %r, not %r"
                          % (aid, i, event, index.events[event], ttype))
    for n, cond in enumerate(_array(aura.get("conditions")), 1):
        _lint_check(aid, n, cond.get("check") if isinstance(cond, dict) else None, len(entries), errors)


def _lint_check(aid, n, check, ntriggers, errors):
    if not isinstance(check, dict):
        return
    t = check.get("trigger")
    if t is not None and t not in (-1, -2) and not (isinstance(t, int) and 1 <= t <= ntriggers):
        errors.append("%r: conditions[%d] uses trigger %r, the aura has %d" % (aid, n, t, ntriggers))
    for sub in _array(check.get("checks")):
        _lint_check(aid, n, sub, ntriggers, errors)
