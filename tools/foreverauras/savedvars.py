"""ForeverAuras SavedVariables: pull a group out, merge a group in."""

import copy
import os
import random
import shutil
import subprocess
import time

import lualit

SAVED = "ForeverAurasSaved"
UID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789()"
GROUP_TYPES = ("group", "dynamicgroup")


class SvFile:
    """A parsed SavedVariables file that writes back in the layout it was read in."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            text = f.read().decode("utf-8", "surrogateescape")
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.indent = "\t" if "\n\t" in text else ""
        self.assignments = lualit.parse_assignments(text)

    def get(self, name):
        for n, v in self.assignments:
            if n == name:
                return v
        return None

    def saved(self):
        s = self.get(SAVED)
        if not isinstance(s, dict):
            raise ValueError("%s: no %s table (log in once with ForeverAuras enabled)" % (self.path, SAVED))
        return s

    def text(self):
        return lualit.dump_sv(self.assignments, self.indent, self.newline)

    def write(self, path):
        """Write to a temp file, prove it parses back to the same tables, then swap it in."""
        text = self.text()
        if lualit.parse_assignments(text) != self.assignments:
            raise ValueError("refused to write %s: the output does not parse back to the same data" % path)
        tmp = path + ".fa-tmp"
        with open(tmp, "wb") as f:
            f.write(text.encode("utf-8", "surrogateescape"))
        os.replace(tmp, path)


def child_ids(aura):
    cc = aura.get("controlledChildren")
    if cc is None:
        return []
    return lualit.split_table(cc)[0]


def list_groups(displays):
    return sorted(k for k, v in displays.items() if isinstance(v, dict) and v.get("controlledChildren") is not None)


def collect(displays, gid):
    """(group, children in TraverseAllChildren order, warnings). Copies, never the SV's own tables."""
    if gid not in displays:
        raise KeyError("no display with id %r in displays" % gid)
    warnings, children, seen = [], [], {gid}

    def walk(group_id):
        listed = child_ids(displays[group_id])
        strays = sorted(k for k, v in displays.items()
                        if isinstance(v, dict) and v.get("parent") == group_id and k not in listed)
        for k in strays:
            warnings.append("%r has parent %r but is not in its controlledChildren; included" % (k, group_id))
        for cid in listed + strays:
            if cid in seen:
                continue
            seen.add(cid)
            child = displays.get(cid)
            if not isinstance(child, dict):
                warnings.append("%r lists child %r, which is not in displays; skipped" % (group_id, cid))
                continue
            children.append(copy.deepcopy(child))
            if child.get("controlledChildren") is not None:
                walk(cid)

    walk(gid)
    return copy.deepcopy(displays[gid]), children, warnings


def generate_uid(rng=random):
    """WeakAuras' GenerateUniqueID: 11 characters of its base64 alphabet."""
    return "".join(rng.choice(UID_ALPHABET) for _ in range(11))


def game_running():
    """True when a Wow.exe process is listed by tasklist. None when tasklist is unavailable."""
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             errors="replace", check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        name = line.split(",")[0].strip('"').lower()
        if name == "wow.exe":
            return True
    return False


POSITION_KEYS = ("xOffset", "yOffset", "anchorPoint", "selfPoint", "anchorFrameType", "anchorFrameFrame", "scale")


def merge(saved, data, children, internal_version, rng=random):
    """Merge a group (or single aura) into saved.displays. Returns notes for the user."""
    displays = saved.setdefault("displays", {})
    data, children = copy.deepcopy(data), copy.deepcopy(children)
    gid = data.get("id")
    if not isinstance(gid, str) or not gid:
        raise ValueError("d has no id")
    notes = []
    nested = any(ch.get("controlledChildren") is not None for ch in children)
    if children and not nested:
        # What the importer does for a v1421 export.
        data["controlledChildren"] = {i: ch["id"] for i, ch in enumerate(children, 1)}
        for ch in children:
            ch["parent"] = gid
    new_ids = {gid} | {ch["id"] for ch in children}
    used_uids = {v.get("uid") for k, v in displays.items() if isinstance(v, dict) and k not in new_ids}
    for aura in [data] + children:
        if aura.get("internalVersion") is None:
            aura["internalVersion"] = internal_version
        uid = aura.get("uid")
        if uid is None or uid in used_uids:
            if uid is not None:
                notes.append("%r: uid %s is used by another display; new uid" % (aura["id"], uid))
            uid = generate_uid(rng)
            while uid in used_uids:
                uid = generate_uid(rng)
            aura["uid"] = uid
        used_uids.add(uid)
    old = displays.get(gid)
    if isinstance(old, dict):
        # Keep where the user dragged the group in game; the source only gives the first position.
        kept = [k for k in POSITION_KEYS if k in old and old.get(k) != data.get(k)]
        for k in POSITION_KEYS:
            if k in old:
                data[k] = old[k]
        if kept:
            notes.append("kept %r's in-game position (%s)" % (gid, ", ".join(kept)))
        for cid in child_ids(old):
            if cid not in new_ids and isinstance(displays.get(cid), dict) and displays[cid].get("parent") == gid:
                del displays[cid]
                notes.append("removed %r: it was in the old %r and is not in the new one" % (cid, gid))
    for aura in [data] + children:
        notes.append(("replaced " if aura["id"] in displays else "added ") + repr(aura["id"]))
        displays[aura["id"]] = aura
    return notes


def backup(path):
    dest = "%s.fa-backup-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, dest)
    return dest
