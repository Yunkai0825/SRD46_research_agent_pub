"""
Parse the 'Substances Considered' tables from all Pourbaix Atlas .md files.

Extracts every species row, converts mu_0 from cal to kJ/mol (the unit
used by the main Pourbaix calculator and data-card pipeline), and writes
a combined CSV plus a per-element summary to stdout.

Usage:
    python parse_pourbaix_substances.py              # prints summary
    python parse_pourbaix_substances.py --csv out.csv # writes CSV
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CAL_TO_KJ = 4.184 / 1000.0  # 1 cal = 0.004184 kJ

# This standalone parser lives in Auxillary_dbs_storage/_aux_db_parsers/
# pourbaix_atlas/; raw Atlas Markdown is a sibling of _aux_db_parsers.
ATLAS_DIR = Path(__file__).resolve().parents[2] / "Pourbaix_atlas_database"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_mu0(raw: str) -> float | None:
    """Return mu_0 in cal as a float, or None if unparseable.

    Handles:
      - thousands-separator commas:        -118,580
      - thousands-separator spaces:        -108 300   (European style)
      - footnote markers:                  -313200 (2)
      - leading footnote letter prefix:    a. -108 300   (refers to
        an "a." / "b." annotation in the Pourbaix Atlas source text)
      - bracketed footnote refs:           [see ref. 17]   → None
      - plain integers:                    0, -56690
      - explicit placeholders:             ?, see equation 17  → None
    """
    cleaned = raw.strip()
    if not cleaned:
        return None

    # Explicit unparseable placeholders.
    low = cleaned.lower()
    if low in {"?", "-", "--", "n/a", "na"}:
        return None
    if low.startswith(("see ", "cf.", "cf ", "ref.", "ref ")):
        return None

    # Strip trailing footnote markers like " (2)" or "[3]".
    cleaned = re.sub(r"\s*[\(\[]\d+[\)\]]\s*$", "", cleaned)

    # Strip leading single-letter footnote prefix like "a. " / "B. ".
    cleaned = re.sub(r"^[A-Za-z]\.\s*", "", cleaned)

    # Remove thousands-separator commas, then collapse ALL internal
    # whitespace so "-108 300" → "-108300".
    cleaned = cleaned.replace(",", "")
    cleaned = re.sub(r"\s+", "", cleaned)

    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _element_from_filename(fname: str) -> str:
    """Extract the element/topic name from filenames like '12_Iron.md'."""
    stem = Path(fname).stem          # e.g. '12_Iron'
    parts = stem.split("_", 1)
    return parts[1] if len(parts) == 2 else stem


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(
    r"\|\s*Phase\s*\|\s*Species\s*\|\s*Oxidation\s+State\s*\|\s*mu_0\s*\(cal\.\)\s*\|\s*Name\s*\|",
    re.IGNORECASE,
)

# Match a Markdown H3 heading like "### Lanthanum" (used in overview files)
_SUBSECTION_RE = re.compile(r"^###\s+(.+)", re.MULTILINE)


def parse_file(path: Path) -> list[dict]:
    """Parse all 'Substances Considered' rows from a single .md file.

    Returns a list of dicts with keys:
        file, element, sub_element, phase, species, oxidation_state,
        mu0_cal, mu0_kJ, name
    """
    text = path.read_text(encoding="utf-8")
    element = _element_from_filename(path.name)
    rows: list[dict] = []

    # Split into lines for sequential scanning
    lines = text.splitlines()
    n = len(lines)
    i = 0
    in_substances_section = False
    current_sub_element: str | None = None

    while i < n:
        line = lines[i]

        # Detect "## Substances Considered" section start
        if re.match(r"^##\s+Substances\s+Considered", line, re.IGNORECASE):
            in_substances_section = True
            current_sub_element = None
            i += 1
            continue

        # Detect end of substances section (next ##-level heading)
        if in_substances_section and re.match(r"^##\s+", line) and not re.match(
            r"^##\s+Substances\s+Considered", line, re.IGNORECASE
        ):
            in_substances_section = False
            i += 1
            continue

        if not in_substances_section:
            i += 1
            continue

        # Sub-element heading (e.g. "### Lanthanum" in overview files)
        m_sub = _SUBSECTION_RE.match(line)
        if m_sub:
            current_sub_element = m_sub.group(1).strip()
            i += 1
            continue

        # Detect table header row
        if _HEADER_RE.search(line):
            # Skip separator row (next line is  |---|---|...)
            i += 1
            if i < n and re.match(r"\s*\|[-\s|]+\|", lines[i]):
                i += 1

            # Now read data rows until a non-table line
            while i < n:
                row_line = lines[i]
                if not row_line.strip().startswith("|"):
                    break
                cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
                if len(cells) < 5:
                    i += 1
                    continue

                phase = cells[0].strip()
                species = cells[1].strip()
                ox_state = cells[2].strip()
                mu0_raw = cells[3].strip()
                name = cells[4].strip()

                mu0_cal = _parse_mu0(mu0_raw)
                mu0_kJ = round(mu0_cal * CAL_TO_KJ, 4) if mu0_cal is not None else None

                rows.append(
                    {
                        "file": path.name,
                        "element": element,
                        "sub_element": current_sub_element or element,
                        "phase": phase,
                        "species": species,
                        "oxidation_state": ox_state,
                        "mu0_cal": mu0_cal,
                        "mu0_kJ": mu0_kJ,
                        "name": name,
                    }
                )
                i += 1
            continue

        i += 1

    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Substances Considered tables from Pourbaix Atlas .md files."
    )
    parser.add_argument(
        "--csv",
        metavar="FILE",
        help="Write combined CSV to FILE (default: print summary to stdout)",
    )
    parser.add_argument(
        "--dir",
        metavar="DIR",
        default=str(ATLAS_DIR),
        help=f"Directory containing .md files (default: {ATLAS_DIR})",
    )
    args = parser.parse_args()

    md_dir = Path(args.dir)
    if not md_dir.is_dir():
        print(f"Error: directory not found: {md_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = sorted(md_dir.glob("*.md"))
    if not md_files:
        print(f"Error: no .md files found in {md_dir}", file=sys.stderr)
        sys.exit(1)

    all_rows: list[dict] = []
    for f in md_files:
        all_rows.extend(parse_file(f))

    # ---- Write CSV ----
    fieldnames = [
        "file", "element", "sub_element", "phase", "species",
        "oxidation_state", "mu0_cal", "mu0_kJ", "name",
    ]

    if args.csv:
        out_path = Path(args.csv)
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"Wrote {len(all_rows)} rows to {out_path}")
    else:
        # Print summary + first rows
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
        print(buf.getvalue())

    # ---- Summary stats ----
    elements = sorted(set(r["sub_element"] for r in all_rows))
    print(f"\n--- Summary ---")
    print(f"Files parsed   : {len(md_files)}")
    print(f"Total species  : {len(all_rows)}")
    print(f"Unique elements: {len(elements)}")
    print(f"Elements       : {', '.join(elements)}")


if __name__ == "__main__":
    main()
