"""Measurement normalization, guarded row repairs, and published provenance (VLM/NOTE)."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple
from dataclasses import dataclass
import re
from .sources import CANONICAL_NULL_TOKEN
from .registry import RULES, Rule, _declare, ledger_source


# =============================================================================
# VLM  verkn_ligand_metal value normalisation  (applied per row by raw_canonical)
# =============================================================================
VLM_PLACEHOLDER_TOKEN = "*"
# Non-critical placeholder records: SRD46 marks metal-ligand pairs whose values were judged
# non-critical with '*' in constant / constant_sic / temperature / ionicstrength, constanttyp 1
# ('*'), beta_definition 19 ('*') and footnote 135 ("The non-critical data may be found in the
# reference."). 10,758 rows. Stored value: NULL (was 0.0 in earlier builds).
VLM_PLACEHOLDER_EXPECTED: Dict[str, str] = {"constanttypNr": "1", "beta_definitionNr": "19", "footnoteNr": "135"}
VLM_PLACEHOLDER_NOTE = ("SRD46 non-critical placeholder record (footnote 135: 'The non-critical data may be found "
                        "in the reference.'): no numeric constant, temperature or ionic strength is stored in SRD46 "
                        "for this metal-ligand pair; see the literature references of the pair.")
_declare(Rule("VLM-01", "raw_canonical", "verkn_ligand_metal_canonical",
              "constant == '*' -> placeholder row: constant/temperature/ionicstrength values NULL (cards: parser:placeholder=1)",
              "the '*' is a marker, not a measurement; a float default of 0.0 would fabricate log K = 0"))

# Parenthesised constants: SRD46 writes ``(x)`` for values the compilers flagged as tentative /
# lower reliability. Numeric value = x (sign as written inside the parentheses); the flag is
# kept in ``constant_in_parentheses`` and the verbatim text in ``constant_raw`` (staging) and as
# parser notes in the cards DB (NOTE-01). The long explanation goes to the ledger ``reason``.
VLM_PAREN_RE = re.compile(r"^\(\s*(?P<num>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*\)$")
VLM_PAREN_NOTE = ("constant written in parentheses in SRD46 = tentative / lower-reliability value; "
                  "numeric value taken as written inside the parentheses (manual rule VLM-02)")
_declare(Rule("VLM-02", "raw_canonical", "verkn_ligand_metal_canonical",
              "'(x)' -> numeric x, flagged (cards: parser:constant_in_parentheses=1 + parser:constant_raw=(x))",
              "parentheses are SRD46's tentative-value notation, not a sign; Excel had turned '(x)' into '-x'"))

# Temperature strings with a trailing 'tv' (temperature variation): SRD46 marks enthalpy/entropy
# rows whose dH/dS were derived from the temperature dependence of log K over a range; the
# footnote of the row holds the range (footnote 70: 0-50 degC for the '30tv' rows 123702/123705;
# footnote 85: 20-40 degC for the '35tv' row 144285). SRD46 itself normalised the 1152 '25tv'
# rows to '25' in its 2008 revision; these 3 rows were missed. The numeric part is kept as the
# nominal (reference) temperature. All 3 rows are constanttyp H/S. Ledger ``reason`` = VLM_TV_NOTE.
VLM_TEMPERATURE_SUFFIX: Dict[str, float] = {"30tv": 30.0, "35tv": 35.0}
VLM_TV_NOTE = ("temperature given as {raw!r} in SRD46 (tv = temperature-variation method: dH/dS from the T dependence "
               "of log K over a range); nominal {value:g} degC stored, the range is in the footnote of this row "
               "(manual rule VLM-03)")
_declare(Rule("VLM-03", "raw_canonical", "verkn_ligand_metal_canonical",
              "temperature '30tv'/'35tv' -> 30/35 (nominal), range stays in the footnote (cards: parser:temperature_raw=30tv)",
              "'tv' = temperature-variation marker on dH/dS rows (SRD46 normalised its 1152 '25tv' rows in 2008, "
              "missed these 3); the only non-numeric temperatures besides '*'"))

# Anything else that is neither NULL nor numeric after VLM-01..03 is left NULL and ledgered as
# 'unparsed' under VLM-00, so new notations cannot slip through silently.
_declare(Rule("VLM-00", "raw_canonical", "verkn_ligand_metal_canonical",
              "non-numeric leftover -> value NULL, ledger status 'unparsed'",
              "visibility: every value the pipeline could not interpret is listed"))

VLM_NUMERIC_FIELDS: Tuple[str, ...] = ("constant", "temperature", "ionicstrength")


@dataclass(frozen=True)
class VlmMetalCorrection:
    expected: Mapping[str, str]  # complete, verbatim source row; no fuzzy/pair-wide matching
    metal_id: str
    evidence: str


VLM_SOURCE_FIELDS: Tuple[str, ...] = (
    "verkn_ligand_metalID", "ligandenNr", "metalNr", "beta_definitionNr", "constanttypNr",
    "temperature", "ionicstrength", "constant", "constant_sic", "error", "footnoteNr",
    "solventNr", "electrolyte", "comment", "Importhilfe", "Acc_feld",
)
# Sommer's original paper explicitly studies Ti(IV). SRD46's existing reference link
# 13669 already assigns ligand 9483 / metal 188 to literature_alt 4221 (63Sd), but these
# four measurements were assigned metal 187 = Ti(III). Metal 188 = Ti(IV), not the
# separate titanyl entry 189: the beta expressions already contain the explicit O.
# This fixes the source-row metal foreign key only. In particular, beta 998's
# hydrogen-unbalanced quotient remains unresolved; the article's full constant table
# has not been recovered, so no quotient or numerical constant is inferred here.
_VLM04_EVIDENCE = (
    "L. Sommer, Reaktionen von Titan(IV) mit der 2,3-Dihydroxynaphthalin-6-sulfonsaeure, "
    "Collect. Czech. Chem. Commun. 1963, 28, 3057-3071; https://doi.org/10.1135/cccc19633057. "
    "The primary article title and public first page identify Ti(IV); existing SRD46 pair-reference "
    "13669 links ligand 9483 / metal 188 to literature_alt 4221 (63Sd, Sommer 1963 p.3057). "
    "Correct only these four exact source rows from metal 187 (Ti3+) to 188 (Ti4+); "
    "preserve VLM IDs, beta IDs and all constants. This does not resolve beta 998's quotient."
)
_VLM04_COMMON = {
    "ligandenNr": "9483", "metalNr": "187", "constanttypNr": "3", "temperature": "20",
    "ionicstrength": "0.1", "error": "0", "footnoteNr": CANONICAL_NULL_TOKEN, "solventNr": "1",
    "electrolyte": CANONICAL_NULL_TOKEN, "comment": CANONICAL_NULL_TOKEN,
    "Importhilfe": CANONICAL_NULL_TOKEN, "Acc_feld": "2007-05-08 15:29:11",
}
VLM_METAL_CORRECTIONS: Dict[str, VlmMetalCorrection] = {
    rid: VlmMetalCorrection(
        expected={**_VLM04_COMMON, "verkn_ligand_metalID": rid, "beta_definitionNr": bid,
                  "constant": constant, "constant_sic": constant},
        metal_id="188", evidence=_VLM04_EVIDENCE,
    )
    for rid, bid, constant in (
        ("164462", "917", "-0.68"), ("164463", "919", "4.0"),
        ("164464", "998", "16.6"), ("164465", "893", "1.8"),
    )
}
_declare(Rule("VLM-04", "raw_canonical", "verkn_ligand_metal_canonical",
              "four exact Sommer 1963 Ti(IV) source rows: metal 187 -> 188; raw metal ID retained",
              _VLM04_EVIDENCE))


def corrected_vlm_metal_id(row: Mapping[str, str]) -> str:
    """Effective metal foreign key, refusing any drift in a targeted original row."""
    rid = str(row.get("verkn_ligand_metalID", ""))
    correction = VLM_METAL_CORRECTIONS.get(rid)
    if correction is None:
        return row.get("metalNr") or ""
    differences = [f"{key}: {row.get(key)!r} (expected {correction.expected.get(key)!r})"
                   for key in sorted(set(row) | set(correction.expected))
                   if key not in row or key not in correction.expected or row[key] != correction.expected[key]]
    if differences:
        raise ValueError(f"VLM-04 source guard failed for {rid}: " + "; ".join(differences))
    return correction.metal_id


def validate_vlm_metal_correction_rows(rows: Sequence[Mapping[str, str]]) -> None:
    """A full raw import must contain every guarded correction target exactly once."""
    counts = dict.fromkeys(VLM_METAL_CORRECTIONS, 0)
    for row in rows:
        rid = str(row.get("verkn_ligand_metalID", ""))
        if rid in counts:
            corrected_vlm_metal_id(row)
            counts[rid] += 1
    bad = {rid: count for rid, count in counts.items() if count != 1}
    if bad:
        raise ValueError(f"VLM-04 source guard requires each target exactly once; observed counts: {bad}")


@dataclass(frozen=True)
class VlmSourceReview:
    expected: Mapping[str, str]
    note: str


# The 1968 reference already linked by SRD46 remains authoritative source identity.
# The accessible 1991 paper motivates review, not a replacement equation or citation.
VLM_SOURCE_REVIEW_NOTE = (
    "SOURCE REVIEW (VLM-05): SRD46 beta 937 uses four explicit protons with [MO2(OH)4]; "
    "the later W-citrate paper https://doi.org/10.1039/DT9910001727 lists log beta126 = 34.51 "
    "with six protons relative to WO4 and Hcit. The SRD46 equation is atom-balanced, but "
    "equivalence of these source conventions is unverified. Original SRD46 reference 6286 "
    "(68PKb, Pyatnitskii and Kravtsova 1968) is retained. No equation or constant is changed."
)
_VLM05_COMMON = {
    "ligandenNr": "9058", "metalNr": "204", "beta_definitionNr": "937", "temperature": "25",
    "ionicstrength": "1.0", "error": "0", "footnoteNr": "47", "solventNr": "1",
    "electrolyte": CANONICAL_NULL_TOKEN, "comment": CANONICAL_NULL_TOKEN,
    "Importhilfe": CANONICAL_NULL_TOKEN,
}
VLM_SOURCE_REVIEWS: Dict[str, VlmSourceReview] = {
    rid: VlmSourceReview(
        expected={**_VLM05_COMMON, "verkn_ligand_metalID": rid, "constanttypNr": kind,
                  "constant": constant, "constant_sic": sic, "Acc_feld": stamp},
        note=VLM_SOURCE_REVIEW_NOTE,
    )
    for rid, kind, constant, sic, stamp in (
        ("157723", "3", "34.51", "34.51", "2007-05-08 15:29:04"),
        ("157724", "2", "-133.9", "-32", "2007-05-09 09:27:45"),
        ("157725", "4", "213.4", "51", "2007-05-09 09:27:45"),
    )
}
VLM_SOURCE_REVIEW_EQUATION = "[MO2(OH)4] + [L]^2 + [H]^4 <=> [MO2H2(H-1L)2] + [H2O]^4"
# Acc_feld values are pinned to the original MySQL dump, including seconds.
VLM_SOURCE_REVIEW_REFERENCES = {
    "verkn_ligand_metal_literature": (
        {"verkn_ligand_metal_literatureID": "23289", "ligandenNr": "9058", "metalNr": "204",
         "literatureNr": "0", "literature_altNr": "6286", "not_used": "-1",
         "comment": CANONICAL_NULL_TOKEN, "Acc_feld": "2007-05-14 18:28:23"},
    ),
    "verkn_ligand_metal_literature_sic": tuple(
        {"verkn_ligand_metal_literatureID": link_id, "verkn_ligand_metalNr": rid,
         "literatureNr": "0", "literature_altNr": "6286", "not_used": "-1",
         "comment": CANONICAL_NULL_TOKEN, "Acc_feld": "2007-05-08 13:10:42"}
        for rid, link_id in (("157723", "684114"), ("157724", "684118"), ("157725", "684112"))
    ),
    "literature_alt": (
        {"literature_altID": "6286", "literature_shortcut": "68PKb",
         "literature_alt": "I. V. Pyatnitskii and L. F. Kravtsova, Soviet Progr. Chem. (Ukr. Khim. Zh.), 1968, 34, No. 7, 60 (706)",
         "comment": CANONICAL_NULL_TOKEN, "Acc_feld": "2007-04-30 07:13:34"},
    ),
}
_declare(Rule("VLM-05", "pip2c_cards", "ligandmetal_stability_measured.notes",
              "three exact W-citrate beta 937 rows: source-convention review note; equation and constants retained",
              VLM_SOURCE_REVIEW_NOTE))


def validate_vlm_source_review_rows(rows: Sequence[Mapping[str, str]],
                                    references: Mapping[str, Sequence[Mapping[str, str]]]) -> None:
    """Require exact source rows and their original reference context before publishing a warning.

    Canonical rows carry extra derived columns; only the complete original source
    field projection is compared. All targets must be present once even on a limited run.
    """
    def check(table, actual_rows, expected_rows, id_key):
        expected_by_id = {r[id_key]: r for r in expected_rows}
        counts = dict.fromkeys(expected_by_id, 0)
        for row in actual_rows:
            rid = str(row.get(id_key, ""))
            expected = expected_by_id.get(rid)
            if expected is None:
                continue
            differences = [f"{key}: {row.get(key)!r} (expected {value!r})"
                           for key, value in expected.items() if row.get(key) != value]
            if differences:
                raise ValueError(f"VLM-05 source guard failed for {table}/{rid}: " + "; ".join(differences))
            counts[rid] += 1
        bad = {rid: count for rid, count in counts.items() if count != 1}
        if bad:
            raise ValueError(f"VLM-05 source guard requires each {table} target exactly once; observed counts: {bad}")

    check("verkn_ligand_metal", rows, [r.expected for r in VLM_SOURCE_REVIEWS.values()],
          "verkn_ligand_metalID")
    for table, expected in VLM_SOURCE_REVIEW_REFERENCES.items():
        id_key = "literature_altID" if table == "literature_alt" else "verkn_ligand_metal_literatureID"
        check(table, references.get(table, ()), expected, id_key)


# =============================================================================
# NOTE  parser notes: how derived facts reach the published cards DB
# =============================================================================
# The cards DB schema is FROZEN to what its consumers (SRD46_research_agent search tools, MCP
# server, database browser, pip3) read: no column is added or moved. Everything the VLM rules
# derive per measured row is carried inside the existing free-text column
# ``ligandmetal_stability_measured.notes`` as self-describing strings
#
#     parser:<key>=<value>
#
# ``notes`` keeps its original shape: ``str()`` of a Python list of strings whose first items are
# the SRD46 footnote ids / comments of the row (e.g. ['48']; NULL when there is nothing).
# Parser strings are appended as further list items, one per key, ONLY when a rule fired - a row
# without any ``parser:`` item holds verbatim SRD46 numbers:
#
#     ['5', 'parser:rules=VLM-02', 'parser:constant_raw=(-0.6)', 'parser:constant_in_parentheses=1']
#     ['135', 'parser:rules=VLM-01', 'parser:placeholder=1', 'parser:constant_raw=*',
#      'parser:temperature_raw=*', 'parser:ionicstrength_raw=*']
#
# keys (emitted in this order)
#     rules                      rule ids applied to the row, '+'-joined: VLM-01 | VLM-02 | VLM-02+VLM-03 | VLM-04 | VLM-00
#     placeholder=1              VLM-01 '*' row: constant_value, temperature_c, ionic_strength_mol_l are NULL
#     constant_raw               verbatim SRD46 constant text when a rule changed it, e.g. (-0.6) or *
#     constant_in_parentheses=1  VLM-02 tentative-value notation; constant_value holds the number inside
#     temperature_raw            verbatim temperature text when a rule changed it: 30tv, 35tv, *
#     ionicstrength_raw          verbatim ionic-strength text when a rule changed it: *
#     metal_id_raw / metal_id_corrected  VLM-04 original and corrected SRD46 metal IDs: 187 / 188
#     source_convention_review=1 VLM-05 source convention unresolved; human explanation follows
#
# Values never contain whitespace, quotes, commas or brackets (parser_note() refuses them), so
#     re.findall(r"parser:([a-z_]+)=([^\s'\",\[\]]+)", notes or "")    -> [(key, value), ...]  (parse_parser_notes)
#     WHERE notes LIKE '%parser:placeholder=1%'                            -> the 10,758 placeholder rows
#     WHERE notes IS NULL OR notes NOT LIKE '%parser:placeholder=1%'       -> accepted rows
# (``constant_type = '*'`` selects the same rows: SRD46 files every placeholder under constanttyp '*';
# ``verify`` asserts the two counts are equal on every run.)
#
# Tables without a notes column are covered by derivation rules instead of flags:
#     ligandmetal_card   placeholder card   <=> every measured row of the card carries parser:placeholder=1
#     ligand_card        placeholder ligand <=> figure_definition = '***' AND formula consists of '*' only (LIG-04);
#                        ligand_SMILES may still hold a PubChem-recovered structure, or '*' when unresolved
# The SQL for both lives in PLACEHOLDER_SPLIT_QUERIES / ACCEPTED_ROWS_ON_PLACEHOLDER_LIGANDS_SQL.
PARSER_NOTE_PREFIX = "parser:"
PARSER_NOTE_KEYS: Tuple[str, ...] = ("rules", "placeholder", "constant_raw", "constant_in_parentheses",
                                     "temperature_raw", "ionicstrength_raw", "metal_id_raw", "metal_id_corrected",
                                     "source_convention_review")
PARSER_NOTE_RE = re.compile(r"parser:([a-z_]+)=([^\s'\",\[\]]+)")
_PARSER_NOTE_VALUE_RE = re.compile(r"^[^\s'\",\[\]]+$")
PARSER_NOTE_RULE_JOINER = "+"
PLACEHOLDER_NOTE = "parser:placeholder=1"
_declare(Rule("NOTE-01", "raw_canonical / pip2c_cards", "ligandmetal_stability_measured.notes",
              "derived facts are appended to notes as 'parser:<key>=<value>' strings; no cards column is added",
              "the cards schema is the contract of the downstream agents/tools; notes is the one free-text slot per row"))


def parser_note(key: str, value: object) -> str:
    """One ``parser:<key>=<value>`` string; refuses keys outside NOTE-01 and unsafe values."""
    if key not in PARSER_NOTE_KEYS:
        raise ValueError(f"NOTE-01: unknown parser note key {key!r}")
    text = str(value)
    if not _PARSER_NOTE_VALUE_RE.match(text):
        raise ValueError(f"NOTE-01: value {text!r} for {key} contains whitespace/quotes/commas/brackets")
    return f"{PARSER_NOTE_PREFIX}{key}={text}"


def parse_parser_notes(notes: Optional[str]) -> Dict[str, str]:
    """``{key: value}`` of every parser note inside a cards ``notes`` cell (empty for NULL / no notes)."""
    return dict(PARSER_NOTE_RE.findall(notes or ""))


def vlm_parser_notes(row: Mapping[str, str], applied: Sequence[str], is_placeholder: bool,
                     in_parentheses: bool, metal_id_corrected: Optional[str] = None) -> List[str]:
    """NOTE-01 strings for one verkn_ligand_metal row given the rules applied to it (``[]`` when none).

    ``applied`` items are ``<rule id>`` (constant) or ``<rule id>:<field>`` (temperature / ionicstrength)
    as produced by :func:`derive_vlm_fields`.
    """
    if not applied:
        return []
    rule_ids: List[str] = []
    changed = set()
    for item in applied:
        rule_id, _, field = item.partition(":")
        if rule_id not in rule_ids:
            rule_ids.append(rule_id)
        changed.add(field or "constant")
    if is_placeholder:
        changed.update(VLM_NUMERIC_FIELDS)
    values: Dict[str, object] = {"rules": PARSER_NOTE_RULE_JOINER.join(rule_ids)}
    if is_placeholder:
        values["placeholder"] = 1
    for field in VLM_NUMERIC_FIELDS:
        raw = (row.get(field) or "").strip()
        if field in changed and raw:                       # nothing to record for an empty cell
            values[f"{field}_raw"] = raw
    if in_parentheses:
        values["constant_in_parentheses"] = 1
    if "metalNr" in changed:
        if metal_id_corrected is None:
            raise ValueError("NOTE-01: corrected metal ID missing for VLM-04 provenance")
        values["metal_id_raw"] = row["metalNr"]
        values["metal_id_corrected"] = metal_id_corrected
    return [parser_note(key, values[key]) for key in PARSER_NOTE_KEYS if key in values]


# Placeholder / accepted split of the published cards DB, derived from the frozen schema alone.
# ``{t}`` = optional table alias prefix ("" or "l." / "m.").
LIGAND_PLACEHOLDER_SQL = ("({t}figure_definition = '***' AND {t}formula IS NOT NULL AND {t}formula <> '' "
                          "AND {t}formula NOT GLOB '*[^*]*')")
MEASURED_PLACEHOLDER_SQL = "COALESCE({t}notes LIKE '%" + PLACEHOLDER_NOTE + "%', 0)"
# table -> query returning (placeholder, accepted, total); a card is a placeholder when it has
# measured rows and none of them is accepted
PLACEHOLDER_SPLIT_QUERIES: Dict[str, str] = {
    "ligand_card": (f"SELECT SUM(CASE WHEN {LIGAND_PLACEHOLDER_SQL.format(t='')} THEN 1 ELSE 0 END), "
                    f"SUM(CASE WHEN {LIGAND_PLACEHOLDER_SQL.format(t='')} THEN 0 ELSE 1 END), COUNT(*) FROM ligand_card"),
    "ligandmetal_stability_measured": (f"SELECT SUM(CASE WHEN {MEASURED_PLACEHOLDER_SQL.format(t='')} THEN 1 ELSE 0 END), "
                                       f"SUM(CASE WHEN {MEASURED_PLACEHOLDER_SQL.format(t='')} THEN 0 ELSE 1 END), COUNT(*) "
                                       "FROM ligandmetal_stability_measured"),
    "ligandmetal_card": ("SELECT SUM(CASE WHEN n_rows > 0 AND n_accepted = 0 THEN 1 ELSE 0 END), "
                         "SUM(CASE WHEN n_accepted > 0 THEN 1 ELSE 0 END), COUNT(*) FROM ("
                         "SELECT c.card_id, COUNT(m.stability_id) AS n_rows, "
                         f"SUM(CASE WHEN m.stability_id IS NOT NULL AND NOT {MEASURED_PLACEHOLDER_SQL.format(t='m.')} THEN 1 ELSE 0 END) AS n_accepted "
                         "FROM ligandmetal_card c LEFT JOIN ligandmetal_stability_measured m ON m.card_id = c.card_id "
                         "GROUP BY c.card_id)"),
}
# LIG-04 invariant: a placeholder ligand carries no accepted measured row
ACCEPTED_ROWS_ON_PLACEHOLDER_LIGANDS_SQL = (
    "SELECT COUNT(*) FROM ligandmetal_stability_measured m "
    "JOIN ligandmetal_card c ON c.card_id = m.card_id JOIN ligand_card l ON l.ligand_id = c.ligand_id "
    f"WHERE {LIGAND_PLACEHOLDER_SQL.format(t='l.')} AND NOT {MEASURED_PLACEHOLDER_SQL.format(t='m.')}")
# documented equivalence checked by verify: constanttyp '*' <=> placeholder row
PLACEHOLDER_CONSTANT_TYPE_SQL = "SELECT COUNT(*) FROM ligandmetal_stability_measured WHERE constant_type = '*'"


def _to_float(text: str) -> Optional[float]:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_vlm_number(field: str, raw: Optional[str]) -> Tuple[Optional[float], bool, Optional[str], Optional[str]]:
    """Normalise one numeric verkn_ligand_metal field.

    Returns ``(value, in_parentheses, rule_id, status)`` where ``rule_id`` is the rule that
    produced the value (None for plain numerics / NULL) and ``status`` is the ledger status
    ('applied' or 'unparsed') or None when nothing needs to be ledgered.
    """
    text = (raw or "").strip()
    if text in ("", CANONICAL_NULL_TOKEN):
        return None, False, None, None
    plain = _to_float(text)
    if plain is not None:
        return plain, False, None, None
    m = VLM_PAREN_RE.match(text)
    if m:
        return float(m.group("num")), True, "VLM-02", "applied"
    if field == "temperature" and text in VLM_TEMPERATURE_SUFFIX:
        return VLM_TEMPERATURE_SUFFIX[text], False, "VLM-03", "applied"
    return None, False, "VLM-00", "unparsed"


def derive_vlm_fields(row: Mapping[str, str]) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    """Derived columns + ledger entries for one verbatim verkn_ligand_metal row.

    Derived columns: metalNr_raw, metalNr_value, constant_raw, constant_value, constant_in_parentheses, temperature_value,
    ionicstrength_value, is_placeholder, applied_rules, parser_tokens (the NOTE-01 strings for the
    row, space-separated; pip2c appends them to the card notes). Ledger entries carry field /
    old_value / new_value / reason / source / status; the caller adds table_name and record_id.
    """
    constant_raw = row.get("constant") or ""
    metal_raw = row.get("metalNr") or ""
    metal_value = corrected_vlm_metal_id(row)
    derived: Dict[str, object] = {
        "metalNr_raw": metal_raw, "metalNr_value": metal_value,
        "constant_raw": constant_raw, "constant_value": None, "constant_in_parentheses": 0,
        "temperature_value": None, "ionicstrength_value": None, "is_placeholder": 0, "applied_rules": "",
        "parser_tokens": "",
    }
    entries: List[Dict[str, object]] = []
    applied: List[str] = []
    if metal_value != metal_raw:
        correction = VLM_METAL_CORRECTIONS[str(row["verkn_ligand_metalID"])]
        applied.append("VLM-04:metalNr")
        entries.append({"field": "metalNr", "old_value": metal_raw, "new_value": metal_value,
                        "reason": correction.evidence, "source": ledger_source("VLM-04"), "status": "applied"})

    if constant_raw.strip() == VLM_PLACEHOLDER_TOKEN:
        derived["is_placeholder"] = 1
        applied.append("VLM-01")
        deviations = [f"{k}={row.get(k)!r} (expected {v})" for k, v in VLM_PLACEHOLDER_EXPECTED.items()
                      if (row.get(k) or "").strip() != v]
        entries.append({"field": "constant", "old_value": constant_raw, "new_value": None,
                        "reason": VLM_PLACEHOLDER_NOTE if not deviations
                        else VLM_PLACEHOLDER_NOTE + " DEVIATION from the usual placeholder pattern: " + "; ".join(deviations),
                        "source": ledger_source("VLM-01"),
                        "status": "applied" if not deviations else "applied_with_deviation"})
        derived["applied_rules"] = ",".join(applied)
        derived["parser_tokens"] = " ".join(vlm_parser_notes(row, applied, True, False, metal_value))
        return derived, entries

    for field in VLM_NUMERIC_FIELDS:
        raw = row.get(field) or ""
        value, in_paren, rule_id, status = parse_vlm_number(field, raw)
        derived[f"{field}_value"] = value
        if field == "constant":
            derived["constant_in_parentheses"] = int(in_paren)
        if rule_id is not None:
            applied.append(f"{rule_id}:{field}" if field != "constant" else rule_id)
            rule = RULES[rule_id]
            if status != "applied":
                reason = f"value {raw!r} matches no numeric pattern and no declared rule; stored as NULL"
            elif rule_id == "VLM-02" and field == "constant":
                reason = VLM_PAREN_NOTE
            elif rule_id == "VLM-03":
                reason = VLM_TV_NOTE.format(raw=raw.strip(), value=value)
            else:
                reason = rule.summary
            entries.append({"field": field, "old_value": raw, "new_value": value, "reason": reason,
                            "source": ledger_source(rule_id), "status": status})
    derived["applied_rules"] = ",".join(applied)
    derived["parser_tokens"] = " ".join(vlm_parser_notes(row, applied, False, bool(derived["constant_in_parentheses"]), metal_value))
    return derived, entries

PARSER_NOTES_DOC = """\
NOTE-01  parser notes in srd46_cards.db (schema frozen to the downstream contract; no extra columns)
  ligandmetal_stability_measured.notes = str(list of strings): SRD46 footnote ids / comments first, then, only
  when a manual rule fired, one 'parser:<key>=<value>' string per key (values: no whitespace/quotes/commas/brackets):
    parser:rules=<ID>[+<ID>]        VLM-01 | VLM-02 | VLM-02+VLM-03 | VLM-04 | VLM-00
    parser:placeholder=1            '*' row: constant_value / temperature_c / ionic_strength_mol_l are NULL
    parser:constant_raw=<text>      verbatim SRD46 constant, e.g. (-0.6) or *
    parser:constant_in_parentheses=1  tentative-value notation; constant_value = number inside the parentheses
    parser:temperature_raw=<text>   verbatim temperature when changed: 30tv, 35tv, *
    parser:ionicstrength_raw=<text> verbatim ionic strength when changed: *
    parser:metal_id_raw=<ID>        verbatim SRD46 metal ID before a guarded VLM-04 correction
    parser:metal_id_corrected=<ID>  corrected metal ID used by maps, cards and pair-reference joins
    parser:source_convention_review=1  VLM-05 unresolved source convention; human explanation follows
  examples  ['5', 'parser:rules=VLM-02', 'parser:constant_raw=(-0.6)', 'parser:constant_in_parentheses=1']
            ['135', 'parser:rules=VLM-01', 'parser:placeholder=1', 'parser:constant_raw=*', 'parser:temperature_raw=*',
             'parser:ionicstrength_raw=*']
  parse     re.findall(r"parser:([a-z_]+)=([^\\s'\\",\\[\\]]+)", notes or "")   (manual_rules.parse_parser_notes)
  SQL       placeholder rows: notes LIKE '%parser:placeholder=1%'   (== constant_type = '*', asserted by verify)
            accepted rows:    notes IS NULL OR notes NOT LIKE '%parser:placeholder=1%'
  derived   ligandmetal_card placeholder <=> all its measured rows are placeholders
            ligand_card placeholder (LIG-04) <=> figure_definition = '***' AND formula NOT GLOB '*[^*]*'
"""


__all__ = [
    'VLM_PLACEHOLDER_TOKEN',
    'VLM_PLACEHOLDER_EXPECTED',
    'VLM_PLACEHOLDER_NOTE',
    'VLM_PAREN_RE',
    'VLM_PAREN_NOTE',
    'VLM_TEMPERATURE_SUFFIX',
    'VLM_TV_NOTE',
    'VLM_NUMERIC_FIELDS',
    'VlmMetalCorrection',
    'VLM_SOURCE_FIELDS',
    'VlmSourceReview',
    'VLM_SOURCE_REVIEWS',
    'VLM_SOURCE_REVIEW_NOTE',
    'VLM_SOURCE_REVIEW_EQUATION',
    'VLM_SOURCE_REVIEW_REFERENCES',
    'validate_vlm_source_review_rows',
    'VLM_METAL_CORRECTIONS',
    'corrected_vlm_metal_id',
    'validate_vlm_metal_correction_rows',
    'PARSER_NOTE_PREFIX',
    'PARSER_NOTE_KEYS',
    'PARSER_NOTE_RE',
    'PARSER_NOTE_RULE_JOINER',
    'PLACEHOLDER_NOTE',
    'parser_note',
    'parse_parser_notes',
    'vlm_parser_notes',
    'LIGAND_PLACEHOLDER_SQL',
    'MEASURED_PLACEHOLDER_SQL',
    'PLACEHOLDER_SPLIT_QUERIES',
    'ACCEPTED_ROWS_ON_PLACEHOLDER_LIGANDS_SQL',
    'PLACEHOLDER_CONSTANT_TYPE_SQL',
    'parse_vlm_number',
    'derive_vlm_fields',
    'PARSER_NOTES_DOC',
]
