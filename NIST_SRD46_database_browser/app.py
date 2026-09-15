#!/usr/bin/env python3
"""Read-only SRD-46 database and published-result browser."""

import csv
import sys
from pathlib import Path

from flask import Flask, render_template

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).absolute().parent.parent))
    __package__ = "NIST_SRD46_database_browser"

from . import db as dbmod
from .request_dbs import close_dbs, get_cards
from .routes.metals import metals_bp
from .routes.ligands import ligands_bp
from .routes.stability import stability_bp
from .routes.pka import pka_bp
from .routes.equilibrium import eq_bp
from .routes.literature import lit_bp
from .routes.similarity import sim_bp
from .routes.results import results_bp

app = Flask(__name__)
app.teardown_appcontext(close_dbs)
for blueprint in (metals_bp, ligands_bp, stability_bp, pka_bp, eq_bp,
                  lit_bp, sim_bp, results_bp):
    app.register_blueprint(blueprint)


def _pourbaix_species_count():
    path = Path(__file__).resolve().parent.parent / "Pourbaix_atlas_database" / "_pourbaix_substances_all.csv"
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as reader:
        return sum(1 for row in csv.DictReader(reader))


@app.route("/")
def index():
    db = get_cards()
    stats = {
        "metals": db.execute("SELECT COUNT(*) FROM metal_card").fetchone()[0],
        "ligands": db.execute("SELECT COUNT(*) FROM ligand_card").fetchone()[0],
        "measurements": db.execute(
            "SELECT COUNT(*) FROM ligandmetal_stability_measured"
        ).fetchone()[0],
        "pka": db.execute("SELECT COUNT(*) FROM ligand_pka_measured").fetchone()[0],
    }

    stats["citations"] = db.execute(
        "SELECT COUNT(*) FROM ref_literature_alt"
    ).fetchone()[0]

    stats["pourbaix"] = _pourbaix_species_count()

    # Top-10 metals by measurement count
    top_metals = dbmod.rows_to_dicts(
        db.execute(
            """SELECT m.metal_id, m.metal_name_SRD, m.symbol_pure, m.charge,
                      COUNT(*) AS cnt
               FROM ligandmetal_card c
               JOIN metal_card m ON c.metal_id = m.metal_id
               GROUP BY c.metal_id
               ORDER BY cnt DESC LIMIT 10"""
        )
    )

    # Top-10 ligand classes
    top_classes = dbmod.rows_to_dicts(
        db.execute(
            """SELECT ligand_class_name, COUNT(*) AS cnt
               FROM ligand_card
               WHERE ligand_class_name IS NOT NULL
               GROUP BY ligand_class_name
               ORDER BY cnt DESC LIMIT 10"""
        )
    )

    # Periodic table data: count of ligandmetal_card entries per metal symbol
    pt_data = dbmod.rows_to_dicts(
        db.execute(
            """SELECT m.symbol_pure AS symbol, COUNT(*) AS count
               FROM ligandmetal_card c
               JOIN metal_card m ON c.metal_id = m.metal_id
               GROUP BY m.symbol_pure"""
        )
    )

    return render_template(
        "index.html",
        stats=stats,
        top_metals=top_metals,
        top_classes=top_classes,
        pt_data=pt_data,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5046, debug=False, use_reloader=False)
