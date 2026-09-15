"""Request-scoped database connection helpers for the SRD-46 browser."""

from flask import g

if __package__:
    from . import db as dbmod
else:
    import db as dbmod


def get_cards():
    if "cards_db" not in g:
        g.cards_db = dbmod._ro_connect(dbmod.CARDS_DB)
    return g.cards_db


def get_eq():
    if "eq_db" not in g:
        g.eq_db = dbmod._ro_connect(dbmod.EQUILIBRIUM_DB)
    return g.eq_db


def get_lit():
    if "lit_db" not in g:
        g.lit_db = dbmod._ro_connect(dbmod.LITERATURE_DB)
    return g.lit_db


def get_fp():
    if "fp_db" not in g:
        g.fp_db = dbmod._ro_connect(dbmod.FINGERPRINT_DB)
    return g.fp_db


def close_dbs(exc=None):
    del exc
    for key in ("cards_db", "eq_db", "lit_db", "fp_db"):
        conn = g.pop(key, None)
        if conn is not None:
            conn.close()