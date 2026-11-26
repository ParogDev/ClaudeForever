"""skillup.py against the SkillupHelper addon's Planner.lua: the same constants, the same rule functions.

The offline tables and the in-game plan must agree, so a change to one side fails here until the other follows.
Constants are read from Planner.lua and compared by value. The rule functions skillup.py ports (P.chance,
P.flatChance, P.craftSpread, costPt, smooth) are pinned by a hash of their Lua text: when one changes, port the
change to skillup.py (chance, flat_chance, craft_spread, cost_pt, smooth), then update the hash below.

Optional: it needs a checkout of the SkillupHelper addon (https://github.com/ParogDev/SkillupHelper). Point
SKILLUP_HELPER_DIR at it; without it every test here is skipped.

    SKILLUP_HELPER_DIR=path/to/SkillupHelper python -I -m pytest tools/tsm/tests/test_planner_parity.py -q
"""
import hashlib
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skillup as S  # noqa: E402

_ADDON_DIR = os.environ.get("SKILLUP_HELPER_DIR")
PLANNER = Path(_ADDON_DIR) / "Planner.lua" if _ADDON_DIR else None

# Lua function -> (skillup.py port, hash of the Lua text with whitespace collapsed)
PORTED = {
    "function P.chance(": ("chance", "aaaf5ead5a55"),
    "function P.flatChance(": ("flat_chance", "c4fa08c776cd"),
    "function P.craftSpread(": ("craft_spread", "8fcf2540280b"),
    "local function costPt(": ("cost_pt", "d78255a13408"),
    "local function smooth(": ("smooth", "2a4c44686c76"),
}


@pytest.fixture(scope="module")
def lua() -> str:
    if PLANNER is None:
        pytest.skip("SKILLUP_HELPER_DIR not set: no SkillupHelper checkout to compare against")
    if not PLANNER.is_file():
        pytest.fail(f"Planner.lua not found at {PLANNER}: SKILLUP_HELPER_DIR does not point at a SkillupHelper checkout")
    return PLANNER.read_text(encoding="utf-8")


def constant(lua: str, name: str) -> float:
    m = re.search(rf"^P\.{name} = (-?[\d.]+)", lua, re.MULTILINE)
    assert m, f"Planner.lua has no `P.{name} = <number>` line: renamed or removed? Recheck skillup.py's port"
    return float(m.group(1))


def function_text(lua: str, head: str) -> str:
    start = lua.find(head)
    assert start >= 0, f"Planner.lua has no `{head}...`: renamed? Recheck skillup.py's port"
    end = re.compile(r"^end\b", re.MULTILINE).search(lua, start)
    return lua[start:end.end()]


def fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:12]


@pytest.mark.parametrize("lua_name, py_value", [
    ("LUCK", S.LUCK),
    ("ISLAND", S.ISLAND),
    ("INTERLEAVE_SAVING", S.INTERLEAVE_SAVING),
    ("BIAS", S.BIAS),
    ("EFFORT", S.DEFAULT_EFFORT),
    ("CRAFT_SAVING", S.CRAFT_SAVING),
    ("SELL_SHARE", S.DEFAULT_SELL_SHARE),
    ("TRIP_Z", S.Z_OF[S.LUCK]),
])
def test_constants_match(lua, lua_name, py_value):
    assert constant(lua, lua_name) == pytest.approx(py_value), f"P.{lua_name} in Planner.lua differs from skillup.py"


def test_z_table_matches(lua):
    m = re.search(r"^local Z_OF = \{([^}]*)\}", lua, re.MULTILINE)
    assert m, "Planner.lua has no `local Z_OF = { ... }`"
    table = {int(k): float(v) for k, v in re.findall(r"\[(\d+)\]\s*=\s*([\d.]+)", m.group(1))}
    assert table == pytest.approx(S.Z_OF) and set(table) == set(S.Z_OF)


@pytest.mark.parametrize("head", sorted(PORTED))
def test_ported_functions_are_unchanged(lua, head):
    port, pinned = PORTED[head]
    got = fingerprint(function_text(lua, head))
    assert got == pinned, (f"Planner.lua's `{head}...)` changed (hash {got}, pinned {pinned}): port the change to "
                           f"skillup.{port}, then pin the new hash in {Path(__file__).name}")
    assert callable(getattr(S, port))
