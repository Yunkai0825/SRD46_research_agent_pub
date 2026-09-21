"""Pourbaix Atlas browse routes."""

from flask import Blueprint, render_template, request
import re

_PARENT_PACKAGE = (__package__ or "").rpartition(".")[0]

if _PARENT_PACKAGE:
    from .. import db as dbmod
else:
    import db as dbmod

pourbaix_bp = Blueprint("pourbaix", __name__, url_prefix="/pourbaix")


@pourbaix_bp.route("/")
def pourbaix_index():
    data = dbmod.get_pourbaix_data()

    # Group by element
    elements = {}
    for row in data:
        el = row.get("Element", row.get("element", ""))
        if el not in elements:
            elements[el] = 0
        elements[el] += 1

    # Sort alphabetically
    elements = dict(sorted(elements.items()))
    return render_template("pourbaix.html", elements=elements)


@pourbaix_bp.route("/<element>")
def pourbaix_detail(element):
    data = dbmod.get_pourbaix_data()

    # Filter rows for this element
    species = [
        r for r in data
        if r.get("Element", r.get("element", "")) == element
    ]

    # Load domain knowledge .md file
    md_text = dbmod.get_pourbaix_md(element)

    return render_template(
        "pourbaix_detail.html",
        element=element, species=species, md_text=md_text,
    )
