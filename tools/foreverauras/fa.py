"""fa: author ForeverAuras auras as Lua source files.

  fa.py encode  <src.lua> [-o out.txt]          source -> !WA:2! import string
  fa.py decode  <string-or-file> [-o out.lua]   import string -> source
  fa.py pull    --sv <ForeverAuras.lua> [--group <id>] [-o src.lua]
  fa.py install <src.lua> --sv <ForeverAuras.lua> [--dry-run <out.lua>]
  fa.py lint    <src.lua> [--fa-dir <ForeverAuras folder>] [--compile [ssh-host]]
"""
# --compile with no host uses this PC's Docker (the wowf/lua51 image from tools\lua.ps1).

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lint  # noqa: E402
import savedvars  # noqa: E402
import transmission  # noqa: E402


def _out(text, path):
    if path:
        with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
            f.write(text)
        print("wrote %s" % path, file=sys.stderr)
    else:
        sys.stdout.write(text)


def _fill_internal_version(src, iv):
    for aura in [src["d"]] + transmission.children_of(src):
        if aura.get("internalVersion") is None:
            aura["internalVersion"] = iv
            print("note: %r had no internalVersion; set to %d" % (aura.get("id"), iv), file=sys.stderr)


def cmd_encode(a):
    src = transmission.read_src(a.src)
    _fill_internal_version(src, transmission.internal_version(a.fa_dir))
    payload = transmission.build_payload(src, a.version or transmission.addon_version(a.fa_dir))
    _out(transmission.encode_payload(payload) + "\n", a.output)
    return 0


def cmd_decode(a):
    text = a.input
    if os.path.isfile(text):
        with open(text, encoding="utf-8", errors="replace") as f:
            text = f.read()
    payload = transmission.decode_string(text)
    header = ["decoded ForeverAuras export: m=%s v=%s s=%s" % (payload.get("m"), payload.get("v"), payload.get("s"))]
    _out(transmission.write_src(transmission.payload_to_src(payload), header), a.output)
    return 0


def cmd_pull(a):
    sv = savedvars.SvFile(a.sv)
    displays = sv.saved().get("displays") or {}
    if not a.group:
        groups = savedvars.list_groups(displays)
        print("groups in %s:" % os.path.basename(a.sv))
        for gid in groups:
            print("  %s (%d children)" % (gid, len(savedvars.child_ids(displays[gid]))))
        if not groups:
            print("  (none; %d displays)" % len(displays))
        return 0
    group, children, warnings = savedvars.collect(displays, a.group)
    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    src = {"d": group}
    if children:
        src["c"] = children
    _out(transmission.write_src(src, ["pulled %r from SavedVariables" % a.group]), a.output)
    return 0


def cmd_install(a):
    src = transmission.read_src(a.src)
    if not a.dry_run:
        running = savedvars.game_running()
        if running:
            print("refused: Wow.exe is running; the game overwrites SavedVariables on exit. Close it first.",
                  file=sys.stderr)
            return 2
        if running is None:
            print("refused: tasklist is unavailable, cannot tell whether the game is running.", file=sys.stderr)
            return 2
    sv = savedvars.SvFile(a.sv)
    notes = savedvars.merge(sv.saved(), src["d"], transmission.children_of(src),
                            transmission.internal_version(a.fa_dir))
    for n in notes:
        print(n)
    if a.dry_run:
        sv.write(a.dry_run)
        print("dry run: wrote %s (the SavedVariables file is untouched)" % a.dry_run)
    else:
        print("backup: %s" % savedvars.backup(a.sv))
        sv.write(a.sv)
        print("wrote %s" % a.sv)
    return 0


def cmd_lint(a):
    src = transmission.read_src(a.src)
    index = lint.FaIndex(a.fa_dir or transmission.default_fa_dir())
    errors, warnings, notes = lint.lint(src, index)
    if a.compile:
        codes = []
        for aura in [src["d"]] + transmission.children_of(src):
            codes += [("%s: %s" % (aura.get("id"), w), c) for w, c in lint.custom_code(aura)]
        notes = [n for n in notes if "custom code" not in n]
        errors += lint.compile_remote(codes, a.compile)
        if not errors:
            notes.append("%d custom code string(s) compiled with luac5.1 on %s" % (len(codes), a.compile))
    for e in errors:
        print("error: " + e)
    for w in warnings:
        print("warning: " + w)
    for n in notes:
        print("note: " + n)
    print("%d error(s), %d warning(s)" % (len(errors), len(warnings)))
    return 1 if errors else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="fa.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("encode", help="source file -> !WA:2! string")
    e.add_argument("src")
    e.add_argument("-o", "--output")
    e.add_argument("--version", help="s field (default: ForeverAuras.toc ## Version)")
    e.add_argument("--fa-dir")
    e.set_defaults(fn=cmd_encode)

    d = sub.add_parser("decode", help="import string (or a file holding one) -> source file")
    d.add_argument("input")
    d.add_argument("-o", "--output")
    d.set_defaults(fn=cmd_decode)

    pl = sub.add_parser("pull", help="group from SavedVariables -> source file")
    pl.add_argument("--sv", required=True)
    pl.add_argument("--group")
    pl.add_argument("-o", "--output")
    pl.set_defaults(fn=cmd_pull)

    i = sub.add_parser("install", help="merge a source file into SavedVariables (game closed)")
    i.add_argument("src")
    i.add_argument("--sv", required=True)
    i.add_argument("--dry-run", metavar="OUT", help="write the merged file here instead")
    i.add_argument("--fa-dir")
    i.set_defaults(fn=cmd_install)

    li = sub.add_parser("lint", help="check a source file against the installed addon")
    li.add_argument("src")
    li.add_argument("--fa-dir")
    li.add_argument("--compile", metavar="SSH_HOST", nargs="?", const=lint.LOCAL,
                    help="also compile custom code with luac5.1 in the wowf/lua51 container: local Docker by default, "
                         "or the Docker of this ssh host")
    li.set_defaults(fn=cmd_lint)

    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape")
    try:
        return a.fn(a)
    except (ValueError, KeyError, OSError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
