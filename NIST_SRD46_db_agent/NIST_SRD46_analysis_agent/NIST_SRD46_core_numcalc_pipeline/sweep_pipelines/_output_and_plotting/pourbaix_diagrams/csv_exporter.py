"""
csv_exporter.py
===============
Pure I/O for the final Pourbaix diagram label map: write to / read
from a CSV matrix.

All map-building, fine-grid hole-patching and label-derivation logic
lives in
:mod:`solvers_and_topology.nd_grid.grid_dynamic_refiner.labeler`
(composition + vote fill) and
:mod:`solvers_and_topology.nd_grid.grid_dynamic_refiner.solver_hole_patcher`
(seeded solver retries).  This module is intentionally restricted to
serialization concerns.

CSV layout
----------
# pourbaix_map_v1
# system_name: <name>
# element: <elem>
# catalog: 0=Fe(s)|1=Fe2+|2=FeOH+|...
,pH0,pH1,pH2,...          <- first row: pH values
E0,label,label,label,...  <- subsequent rows: E value then labels
E1,label,label,label,...
...
"""

from __future__ import annotations

import csv
import io
import pathlib
import sys
import numpy as np
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from solver_settings import DEBUG  # noqa: E402
_SP = str(pathlib.Path(__file__).resolve().parents[2])
if _SP not in sys.path:
    sys.path.insert(0, _SP)
from sweep_pipelines._path_utils import long_path  # noqa: E402


# ------------------------------------------------------------------
#  Export to CSV
# ------------------------------------------------------------------

def export_pourbaix_csv(
    pH_fine: np.ndarray,
    E_fine: np.ndarray,
    labels_fine: np.ndarray,
    catalog: Dict[int, str],
    output_path: str,
    *,
    metadata: Optional[Dict] = None,
    spec_id_to_name: Optional[Dict[str, str]] = None,
    debug: bool = DEBUG,
) -> str:
    """
    Write the label map as a CSV matrix.

    Parameters
    ----------
    spec_id_to_name : optional mapping from internal species id to
                      human-readable name (used in the catalog header).

    Returns the output path.
    """
    path = pathlib.Path(output_path)

    # Build catalog string: 0=Fe(s)|1=Fe2+|...
    cat_parts = []
    for lbl_int in sorted(catalog.keys()):
        raw = catalog[lbl_int]
        display = raw
        if spec_id_to_name:
            display = spec_id_to_name.get(raw, raw)
        cat_parts.append(f"{lbl_int}={display}")
    cat_str = "|".join(cat_parts)

    with open(long_path(path), "w", newline="") as f:
        f.write("# pourbaix_map_v1\n")
        if metadata:
            for k, v in metadata.items():
                f.write(f"# {k}: {v}\n")
        f.write(f"# catalog: {cat_str}\n")

        writer = csv.writer(f)

        # Header row: empty cell + pH values
        header = ["E\\pH"] + [f"{pH:.6f}" for pH in pH_fine]
        writer.writerow(header)

        # Data rows: E value + labels
        n_fine_E = len(E_fine)
        for i_E in range(n_fine_E):
            row = [f"{E_fine[i_E]:.6f}"] + [
                str(int(labels_fine[i_E, j])) for j in range(len(pH_fine))
            ]
            writer.writerow(row)

    if debug:
        print(f"[csv_export] Saved {len(E_fine)}x{len(pH_fine)} label map "
              f"to {path}")

    return str(path)


# ------------------------------------------------------------------
#  Load from CSV
# ------------------------------------------------------------------

def load_pourbaix_csv(
    csv_path: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
    """
    Load a Pourbaix map CSV and return (pH_fine, E_fine, labels_fine, catalog).

    catalog maps int → display name (already human-readable).
    """
    path = pathlib.Path(csv_path)

    catalog: Dict[int, str] = {}
    header_line = None
    data_lines: List[str] = []

    with open(long_path(path), "r") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("# catalog:"):
                cat_str = stripped.split(":", 1)[1].strip()
                for part in cat_str.split("|"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        catalog[int(k.strip())] = v.strip()
            elif stripped.startswith("#"):
                continue
            elif header_line is None:
                header_line = stripped
            else:
                data_lines.append(stripped)

    # Parse header → pH values
    reader = csv.reader(io.StringIO(header_line))
    header_cells = next(reader)
    pH_fine = np.array([float(x) for x in header_cells[1:]])

    # Parse data → E values and labels
    n_E = len(data_lines)
    n_pH = len(pH_fine)
    E_fine = np.empty(n_E)
    labels_fine = np.empty((n_E, n_pH), dtype=np.int32)

    for i, line in enumerate(data_lines):
        reader = csv.reader(io.StringIO(line))
        cells = next(reader)
        E_fine[i] = float(cells[0])
        labels_fine[i, :] = [int(x) for x in cells[1:]]

    return pH_fine, E_fine, labels_fine, catalog
