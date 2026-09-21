"""
initial_condition_normalizer.py
===============================
Normalise ``sweep_constraints.initial_condition`` entries to canonical
units before any downstream consumer reads them.

Each entry may now be supplied in either of two shapes:

* **Composite** (preferred) -- a ``[value, unit]`` 2-element list
  (also accepts a tuple or ``{"value": ..., "unit": ...}`` dict)::

      "temperature":     [25.0,   "C"],
      "ionic_strength":  [100.0,  "mM"],
      "[Cu]_total":      [1.0,    "mM"],
      "pH":              [7.0,    "pH"],
      "E_V":             [-59.0,  "mV"]

* **Bare scalar** (legacy) -- a plain number or string. Treated as
  *already in canonical units*; the unit slot becomes ``None``::

      "temperature":     298.15,        # already K
      "ionic_strength":  0.1,           # already mol/L
      "ionic_strength":  "auto"         # string pass-through

Canonical units (the only form downstream code ever sees):

==================== =============== ============================
Quantity             Canonical unit  Aliases accepted on input
==================== =============== ============================
``pH``               (dimensionless) ``""``, ``"1"``, ``"-"``,
                                     ``"pH"``, ``"dimensionless"``
``E_V``              V               ``"V"``, ``"mV"``, ``"kV"``
``temperature``      K               ``"K"``, ``"C"`` / ``"°C"``,
                                     ``"F"`` / ``"°F"``
``ionic_strength``   mol/L           ``"mol/L"``, ``"M"``, ``"mM"``,
                                     ``"uM"`` / ``"µM"``, ``"nM"``
``[X]_total``        mol/L           same as ionic_strength
declared freeform    (per declare)   exact match against
variables                            ``freeform_vars_define[<name>]
                                     ["unit"]`` (case-insensitive,
                                     same alias table)
==================== =============== ============================

For a freeform variable whose declared unit is *not* one of the
recognised quantity kinds (e.g. ``"V/pH"``), the supplied unit must
match the declared unit exactly (after case-folding) -- no conversion
is attempted.

The public entry point is :func:`normalize_initial_condition`; it
returns a fresh dict with the same keys but with values rewritten to
canonical-unit floats (or pass-through strings for tokens like
``"auto"``).
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Mapping, Optional, Tuple


class InitialConditionUnitError(ValueError):
    """Raised when an initial_condition entry has an unknown / mismatched unit."""


# ── Quantity-kind registry ─────────────────────────────────────────

_KIND_DIMLESS     = "dimensionless"
_KIND_VOLTAGE     = "voltage"
_KIND_TEMPERATURE = "temperature"
_KIND_CONCENTRATION = "concentration"

# Canonical keys → kind
_FIXED_KEY_KINDS: Dict[str, str] = {
    "pH":              _KIND_DIMLESS,
    "E_V":             _KIND_VOLTAGE,
    "temperature":     _KIND_TEMPERATURE,
    "ionic_strength":  _KIND_CONCENTRATION,
}

# ``[<token>]_total`` → concentration
_BRACKET_TOTAL_RE = re.compile(r"^\[([A-Za-z0-9_+\-$.]+)\]_total$")

# Unit aliases (case-folded). Value = (kind, multiplicative factor to canonical)
# For temperature, the factor is unused -- conversion is handled separately.
_UNIT_TABLE: Dict[str, Tuple[str, float]] = {
    # dimensionless
    "":              (_KIND_DIMLESS,     1.0),
    "1":             (_KIND_DIMLESS,     1.0),
    "-":             (_KIND_DIMLESS,     1.0),
    "ph":            (_KIND_DIMLESS,     1.0),
    "dimensionless": (_KIND_DIMLESS,     1.0),
    "none":          (_KIND_DIMLESS,     1.0),

    # voltage → V
    "v":             (_KIND_VOLTAGE,     1.0),
    "mv":            (_KIND_VOLTAGE,     1e-3),
    "kv":            (_KIND_VOLTAGE,     1e3),

    # temperature → K (factor unused; see _convert_temperature)
    "k":             (_KIND_TEMPERATURE, 1.0),
    "c":             (_KIND_TEMPERATURE, 1.0),
    "°c":            (_KIND_TEMPERATURE, 1.0),
    "degc":          (_KIND_TEMPERATURE, 1.0),
    "f":             (_KIND_TEMPERATURE, 1.0),
    "°f":            (_KIND_TEMPERATURE, 1.0),
    "degf":          (_KIND_TEMPERATURE, 1.0),

    # concentration → mol/L
    "mol/l":         (_KIND_CONCENTRATION, 1.0),
    "m":             (_KIND_CONCENTRATION, 1.0),
    "mmol/l":        (_KIND_CONCENTRATION, 1e-3),
    "mm":            (_KIND_CONCENTRATION, 1e-3),
    "umol/l":        (_KIND_CONCENTRATION, 1e-6),
    "um":            (_KIND_CONCENTRATION, 1e-6),
    "µm":            (_KIND_CONCENTRATION, 1e-6),
    "μm":            (_KIND_CONCENTRATION, 1e-6),
    "nmol/l":        (_KIND_CONCENTRATION, 1e-9),
    "nm":            (_KIND_CONCENTRATION, 1e-9),
}


def _canon_unit(unit: Optional[str]) -> str:
    if unit is None:
        return ""
    return str(unit).strip().lower()


def _unwrap(raw: Any) -> Tuple[Any, Optional[str]]:
    """Return ``(value, unit_or_None)`` for any accepted entry shape.

    Accepted shapes:
      * bare scalar  -> ``(value, None)``
      * 2-element list/tuple ``[value, unit]``
      * dict ``{"value": ..., "unit": ...}`` (also ``"val"`` alias)
    """
    if isinstance(raw, (list, tuple)):
        if len(raw) != 2:
            raise InitialConditionUnitError(
                f"composite initial_condition entry must have exactly "
                f"2 elements [value, unit]; got {raw!r}")
        return raw[0], (None if raw[1] is None else str(raw[1]))
    if isinstance(raw, Mapping):
        if "value" in raw:
            v = raw["value"]
        elif "val" in raw:
            v = raw["val"]
        else:
            raise InitialConditionUnitError(
                f"composite initial_condition dict must have a 'value' "
                f"key; got keys {list(raw)!r}")
        u = raw.get("unit")
        return v, (None if u is None else str(u))
    return raw, None


def _convert_temperature(value: float, unit_canon: str) -> float:
    if unit_canon in ("k", ""):
        return value
    if unit_canon in ("c", "°c", "degc"):
        return value + 273.15
    if unit_canon in ("f", "°f", "degf"):
        return (value - 32.0) * 5.0 / 9.0 + 273.15
    raise InitialConditionUnitError(
        f"unknown temperature unit {unit_canon!r}")


def _convert_to_canonical(value: Any, unit: Optional[str], kind: str,
                          key_for_err: str) -> float:
    """Convert ``value`` (with optional supplied ``unit``) to ``kind``'s
    canonical unit.  ``unit=None`` means the value is already canonical."""
    if isinstance(value, bool):
        raise InitialConditionUnitError(
            f"initial_condition[{key_for_err!r}] value cannot be boolean")
    try:
        fval = float(value)
    except (TypeError, ValueError) as exc:
        raise InitialConditionUnitError(
            f"initial_condition[{key_for_err!r}] value must be numeric; "
            f"got {value!r}") from exc

    if not math.isfinite(fval):
        raise InitialConditionUnitError(
            f"initial_condition[{key_for_err!r}] value must be finite")

    if unit is None:
        return fval

    u = _canon_unit(unit)

    # Temperature has additive offsets, not just a factor.
    if kind == _KIND_TEMPERATURE:
        return _convert_temperature(fval, u)

    if u not in _UNIT_TABLE:
        raise InitialConditionUnitError(
            f"initial_condition[{key_for_err!r}]: unknown unit {unit!r}")
    declared_kind, factor = _UNIT_TABLE[u]
    if declared_kind != kind:
        raise InitialConditionUnitError(
            f"initial_condition[{key_for_err!r}]: unit {unit!r} is "
            f"{declared_kind!r}, expected {kind!r}")
    return fval * factor


def _kind_for_key(key: str,
                  freeform_vars_define: Mapping[str, Any]
                  ) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(kind, declared_unit_or_None)`` for an initial_condition key.

    For a key declared in ``freeform_vars_define`` whose unit string
    matches a known quantity kind alias, the kind is returned (and
    standard conversion will apply). For free-form units that are not
    known (e.g. ``"V/pH"``), the kind is ``None`` and downstream code
    falls back to exact-string match on the supplied unit.
    """
    if key in _FIXED_KEY_KINDS:
        return _FIXED_KEY_KINDS[key], None
    if _BRACKET_TOTAL_RE.match(key):
        return _KIND_CONCENTRATION, None
    if key in freeform_vars_define:
        decl = freeform_vars_define[key] or {}
        decl_unit = decl.get("unit") if isinstance(decl, Mapping) else None
        if decl_unit is None:
            return _KIND_DIMLESS, None
        u = _canon_unit(decl_unit)
        if u in _UNIT_TABLE:
            return _UNIT_TABLE[u][0], decl_unit
        return None, decl_unit
    return None, None


def normalize_initial_condition(
    ic: Mapping[str, Any],
    freeform_vars_define: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a copy of ``ic`` with every value converted to canonical units.

    * Numeric entries become ``float`` in canonical units.
    * String entries (e.g. ``"auto"``) are passed through unchanged.
    * Entries whose key is unknown to the normaliser (no fixed kind,
      no ``[X]_total`` shape, not a declared freeform var) are accepted
      as bare scalars only -- supplying a composite ``[value, unit]``
      raises :class:`InitialConditionUnitError`.

    Raises :class:`InitialConditionUnitError` on any structural or
    unit-conversion problem so the caller can surface a single,
    user-facing error.
    """
    if not isinstance(ic, Mapping):
        raise InitialConditionUnitError(
            "'initial_condition' must be a JSON object")
    fvars: Mapping[str, Any] = freeform_vars_define or {}

    out: Dict[str, Any] = {}
    for key, raw in ic.items():
        # String pass-through (e.g. ionic_strength: "auto").
        if isinstance(raw, str):
            out[key] = raw
            continue

        value, supplied_unit = _unwrap(raw)

        # String value inside a composite is also a pass-through.
        if isinstance(value, str):
            if supplied_unit is not None:
                raise InitialConditionUnitError(
                    f"initial_condition[{key!r}]: string value {value!r} "
                    f"cannot carry a unit ({supplied_unit!r})")
            out[key] = value
            continue

        kind, declared_unit = _kind_for_key(key, fvars)

        if kind is None:
            # Either an unknown key, OR a freeform var whose declared
            # unit is opaque (e.g. "V/pH"). Composite entries are only
            # accepted if the supplied unit matches the declaration
            # exactly (case-insensitive); bare scalars are accepted as
            # already-in-declared-unit.
            if supplied_unit is None:
                if isinstance(value, bool):
                    raise InitialConditionUnitError(
                        f"initial_condition[{key!r}] value cannot be boolean")
                try:
                    out[key] = float(value)
                except (TypeError, ValueError) as exc:
                    raise InitialConditionUnitError(
                        f"initial_condition[{key!r}] value must be "
                        f"numeric; got {value!r}") from exc
                if not math.isfinite(out[key]):
                    raise InitialConditionUnitError(
                        f"initial_condition[{key!r}] value must be finite")
                continue
            if declared_unit is None:
                raise InitialConditionUnitError(
                    f"initial_condition[{key!r}]: unit {supplied_unit!r} "
                    f"supplied but key is not recognised "
                    f"(not a DOF, [X]_total, or declared freeform var)")
            if _canon_unit(supplied_unit) != _canon_unit(declared_unit):
                raise InitialConditionUnitError(
                    f"initial_condition[{key!r}]: unit {supplied_unit!r} "
                    f"does not match declared unit {declared_unit!r} "
                    f"(no conversion available for this quantity)")
            if isinstance(value, bool):
                raise InitialConditionUnitError(
                    f"initial_condition[{key!r}] value cannot be boolean")
            try:
                out[key] = float(value)
            except (TypeError, ValueError) as exc:
                raise InitialConditionUnitError(
                    f"initial_condition[{key!r}] value must be numeric; "
                    f"got {value!r}") from exc
            if not math.isfinite(out[key]):
                raise InitialConditionUnitError(
                    f"initial_condition[{key!r}] value must be finite")
            continue

        out[key] = _convert_to_canonical(value, supplied_unit, kind, key)

    return out


__all__ = [
    "normalize_initial_condition",
    "InitialConditionUnitError",
]
