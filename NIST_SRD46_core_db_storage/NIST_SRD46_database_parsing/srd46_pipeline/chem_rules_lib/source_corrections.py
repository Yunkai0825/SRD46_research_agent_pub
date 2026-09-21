"""Guarded preservation of curated source names when importing the MySQL dump.

The archived CSV is provenance only: this module never reads it. A one-time,
record-by-record comparison of all 984 beta names found 699 identical names,
238 reproducible markup normalizations, and 47 residual curated values. Those
47 historical varchar(110) corrections include 45 extensions and the trailing
spaces on IDs 554 and 710; their exact spelling is retained here. Existing
BETA chemistry corrections still run later, after these source names are parsed.
Metal names and the solvent name receive the same historical HTML-to-notation
translation; all measurement and historical beta text stays faithful to MySQL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class SourceNameCorrection:
    expected_original: str
    replacement: str
    provenance: str


BETA_CURATION_CSV_SHA256 = '29a02a654366e22089165c4dd9072a26ed5f33cff46ca9756ea61fa5b42b63b4'
BETA_CURATION_DUMP_SHA256 = '997ca41785ab4881421030b6b7589cd15e054574a377b1d729874273ee7072c4'
BETA_CURATION_PROVENANCE = (
    "Historical Export/CSV files/beta_definition__2.csv, name_beta_definition; "
    "SHA-256 " + BETA_CURATION_CSV_SHA256
)

# Each ID is pinned to its exact original dump text, before markup normalization.
# Preserve replacements verbatim, including historical spaces and malformed tags;
# later BETA rules remain responsible for chemistry and equation repairs.
BETA_SOURCE_CORRECTIONS: dict[int, SourceNameCorrection] = {
    4: SourceNameCorrection(
        '[M<sub>3</sub>L<sub>6</sub>]<sup>2</sup>[H]<sup>6</sup>/[H<sub>2</sub>L]<sup>3</sup>[(M<sub>2</sub>L<sub>3</su',
        '[M<sub>3</sub>L<sub>6</sub>]<sup>2</sup>[H]<sup>6</sup>/[H<sub>2</sub>L]<sup>3</sup>[(M<sub>2</sub>L<sub>3</sub>(s))]<sub>3</sub>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=4; historical completion of a varchar(110) source value'),
    9: SourceNameCorrection(
        '[(MO<sub>2</sub>)<sub>2</sub>(H-<sub>2</sub>L)(H-<sub>1</sub>L)<sub>2</sub>]/[(MO<sub>2</sub>(OH)<sub>4</sub>)',
        '[(MO<sub>2</sub>)<sub>2</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>2</sub>]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][H]<sup>4</sup>[L]<sup>3</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=9; historical completion of a varchar(110) source value'),
    10: SourceNameCorrection(
        '[(MO<sub>2</sub>)<sub>2</sub>(H-<sub>2</sub>L)<sub>2</sub>]/[{MO<sub>2</sub>(OH)<sub>4</sub>}<sub>2</sub>][H]<',
        '[(MO<sub>2</sub>)<sub>2</sub>(H<sub>-2</sub>L)<sub>2</sub>]/[{MO<sub>2</sub>(OH)<sub>4</sub>}<sub>2</sub>][H]<sup>4</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=10; historical completion of a varchar(110) source value'),
    12: SourceNameCorrection(
        '[(MO<sub>3</sub>)<sub>2</sub>H<sub>3</sub>L<sub>2</sub>]/[MO<sub>4</sub>]<sup>2</sup>[H]<sup>7</sup>[L]<sup>2<',
        '[(MO<sub>3</sub>)<sub>2</sub>H<sub>3</sub>L<sub>2</sub>]/[MO<sub>4</sub>]<sup>2</sup>[H]<sup>7</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=12; historical completion of a varchar(110) source value'),
    13: SourceNameCorrection(
        '[(MO<sub>3</sub>)<sub>2</sub>H<sub>4</sub>L<sub>2</sub>]/[(MO<sub>3</sub>)<sub>2</sub>H<sub>3</sub>L<sub>2</su',
        '[(MO<sub>3</sub>)<sub>2</sub>H<sub>4</sub>L<sub>2</sub>]/[(MO<sub>3</sub>)<sub>2</sub>H<sub>3</sub>L<sub>2</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=13; historical completion of a varchar(110) source value'),
    18: SourceNameCorrection(
        '[(VO<sub>3</sub>)<sub>3</sub>(HL)<sub>2</sub>]/[(VO<sub>3</sub>)<sub>2</sub>(HL)<sub>2</sub>][H<sub>2</sub>VO<',
        '[(VO<sub>3</sub>)<sub>3</sub>(HL)<sub>2</sub>]/[(VO<sub>3</sub>)<sub>2</sub>(HL)<sub>2</sub>][H<sub>2</sub>VO<sub>4</sub>]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=18; historical completion of a varchar(110) source value'),
    47: SourceNameCorrection(
        '[H<sub>2</sub>M<sub>2</sub>O<sub>3</sub>(H-<sub>2</sub>L)(H-<sub>4</sub>L)][H]<sup>2</sup>/[M(OH)<sub>4</sub>]',
        '[H<sub>2</sub>M<sub>2</sub>O<sub>3</sub>(H<sub>-2</sub>L)(H<sub>-4</sub>L)][H]<sup>2</sup>/[M(OH)<sub>4</sub>]<sup>2</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=47; historical completion of a varchar(110) source value'),
    50: SourceNameCorrection(
        '[H<sub>2</sub>V<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>][H]<sup>1<sub>4</sub></sup>/[VO<sub>2</sub><s',
        '[H<sub>2</sub>V<sub>10</sub>O<sub>28</sub>][H]<sup>14</sup>/[VO<sub>2</sub><sup>+</sup>]<sup>10</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=50; historical completion of a varchar(110) source value'),
    51: SourceNameCorrection(
        '[H<sub>2</sub>V<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>]/[HV<sub>1</sub><sub>0</sub>O<sub>2</sub><sub',
        '[H<sub>2</sub>V<sub>10</sub>O<sub>28</sub>]/[HV<sub>10</sub>O<sub>28</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=51; historical completion of a varchar(110) source value'),
    52: SourceNameCorrection(
        '[H<sub>2</sub>W<sub>1</sub><sub>2</sub>O<sub>4</sub><sub>1</sub>]/[HW<sub>1</sub><sub>2</sub>O<sub>4</sub><sub',
        '[H<sub>2</sub>W<sub>12</sub>O<sub>41</sub>]/[HW<sub>12</sub>O<sub>41</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=52; historical completion of a varchar(110) source value'),
    60: SourceNameCorrection(
        '[H<sub>3</sub>Mo<sub>7</sub>O<sub>2</sub><sub>4</sub>]/[H<sub>2</sub>Mo<sub>7</sub>O<sub>2</sub><sub>4</sub>][',
        '[H<sub>3</sub>Mo<sub>7</sub>O<sub>24</sub>]/[H<sub>2</sub>Mo<sub>7</sub>O<sub>24</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=60; historical completion of a varchar(110) source value'),
    61: SourceNameCorrection(
        '[H<sub>3</sub>V<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>]/[H<sub>2</sub>V<sub>1</sub><sub>0</sub>O<sub',
        '[H<sub>3</sub>V<sub>10</sub>O<sub>28</sub>]/[H<sub>2</sub>V<sub>10</sub>O<sub>28</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=61; historical completion of a varchar(110) source value'),
    62: SourceNameCorrection(
        '[H<sub>3</sub>W<sub>1</sub><sub>2</sub>O<sub>4</sub><sub>1</sub>]/[H<sub>2</sub>W<sub>1</sub><sub>2</sub>O<sub',
        '[H<sub>3</sub>W<sub>12</sub>O<sub>41</sub>]/[H<sub>2</sub>W<sub>12</sub>O<sub>41</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=62; historical completion of a varchar(110) source value'),
    361: SourceNameCorrection(
        '[M][V<sub>1</sub><sub>2</sub>O<sub>3</sub><sub>1</sub>]/[MV<sub>1</sub><sub>2</sub>O<sub>3</sub><sub>1</sub>(s',
        '[M][V<sub>12</sub>O<sub>31</sub>]/[MV<sub>12</sub>O<sub>31</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=361; historical completion of a varchar(110) source value'),
    363: SourceNameCorrection(
        '[M]<sup>1<sub>0</sub></sup>[L]<sup>6</sup>/[H]<sup>8</sup>[M<sub>1</sub><sub>0</sub>(OH)<sub>6</sub>OL<sub>6</',
        '[M]<sup>10</sup>[L]<sup>6</sup>/[H]<sup>8</sup>[M<sub>10</sub>(OH)<sub>6</sub>OL<sub>6</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=363; historical completion of a varchar(110) source value'),
    365: SourceNameCorrection(
        '[M<sub>1</sub><sub>1</sub>(OH)<sub>1</sub><sub>2</sub>L<sub>6</sub>][H]<sup>1<sub>2</sub></sup>/[M]<sup>1<sub>',
        '[M<sub>11</sub>(OH)<sub>12</sub>L<sub>6</sub>][H]<sup>12</sup>/[M]<sup>11</sup>[L]<sup>6</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=365; historical completion of a varchar(110) source value'),
    366: SourceNameCorrection(
        '[M<sub>1</sub><sub>3</sub>O<sub>4</sub>(OH)<sub>2</sub><sub>4</sub>(H-<sub>1</sub>L)<sub>4</sub>][H]<sup>3<sub',
        '[M<sub>13</sub>O<sub>4</sub>(OH)<sub>24</sub>(H<sub>-1</sub>L)<sub>4</sub>][H]<sup>36</sup>/[M]<sup>13</sup>[HL]<sup>4</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=366; historical completion of a varchar(110) source value'),
    367: SourceNameCorrection(
        '[M<sub>1</sub><sub>3</sub>O<sub>4</sub>L<sub>2</sub><sub>4</sub>]/[M]<sup>1<sub>3</sub></sup>[L]<sup>3<sub>2</',
        '[M<sub>13</sub>O<sub>4</sub>L<sub>24</sub>]/[M]<sup>13</sup></sup>[L]<sup>32</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=367; historical completion of a varchar(110) source value'),
    410: SourceNameCorrection(
        '[M<sub>2</sub>(OH)<sub>2</sub>(H-<sub>1</sub>L)<sub>2</sub>][OH]<sup>2</sup>/[M(OH)<sub>3</sub>]<sup>2</sup>[L',
        '[M<sub>2</sub>(OH)<sub>2</sub>(H<sub>-1</sub>L)<sub>2</sub>][OH]<sup>2</sup>/[M(OH)<sub>3</sub>]<sup>2</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=410; historical completion of a varchar(110) source value'),
    412: SourceNameCorrection(
        '[M<sub>2</sub>(OH)<sub>2</sub>(H-<sub>1</sub>L)<sub>3</sub>][OH]/[M(OH)<sub>3</sub>]<sup>2</sup>[L]<sup>3</sup',
        '[M<sub>2</sub>(OH)<sub>2</sub>(H<sub>-1</sub>L)<sub>3</sub>][OH]/[M(OH)<sub>3</sub>]<sup>2</sup>[L]<sup>3</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=412; historical completion of a varchar(110) source value'),
    449: SourceNameCorrection(
        '[M]<sup>2</sup>[H<sub>4</sub>L]<sup>3</sup>[OH]<sup>4</sup>/[M<sub>2</sub>Si<sub>3</sub>O<sub>8</sub>(H<sub>2<',
        '[M]<sup>2</sup>[H<sub>4</sub>L]<sup>3</sup>[OH]<sup>4</sup>/[M<sub>2</sub>Si<sub>3</sub>O<sub>8</sub>(H<sub>2</sub>O)(s,sepiolite)]<sup>3.5</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=449; historical completion of a varchar(110) source value'),
    460: SourceNameCorrection(
        '[M]<sup>2</sup>[V<sub>2</sub>O<sub>7</sub>]/[M<sub>2</sub>V<sub>2</sub>O<sub>7</sub>(H<sub>2</sub>O)<sub>2</su',
        '[M]<sup>2</sup>[V<sub>2</sub>O<sub>7</sub>]/[M<sub>2</sub>V<sub>2</sub>O<sub>7</sub>(H<sub>2</sub>O)<sub>2</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=460; historical completion of a varchar(110) source value'),
    461: SourceNameCorrection(
        '[M][V<sub>4</sub>O<sub>1</sub><sub>2</sub>]<sup>0.5</sup>/[M(VO<sub>3</sub>)<sub>2</sub>(H<sub>2</sub>O)<sub>4',
        '[M][V<sub>4</sub>O<sub>12</sub>]<sup>0.5</sup>/[M(VO<sub>3</sub>)<sub>2</sub>(H<sub>2</sub>O)<sub>4</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=461; historical completion of a varchar(110) source value'),
    467: SourceNameCorrection(
        '[M<sub>2</sub>H<sub>2</sub>(H-<sub>1</sub>L)<sub>2</sub>]/[M<sub>2</sub>(H-<sub>1</sub>L)<sub>2</sub>][H]<sup>',
        '[M<sub>2</sub>H<sub>2</sub>(H<sub>-1</sub>L)<sub>2</sub>]/[M<sub>2</sub>(H<sub>-1</sub>L)<sub>2</sub>][H]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=467; historical completion of a varchar(110) source value'),
    554: SourceNameCorrection(
        '[M<sub>2</sub>O<sub>4</sub>(H-<sub>1</sub>L)]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L][H]<sup>3</sup>',
        '[M<sub>2</sub>O<sub>4</sub>(H<sub>-1</sub>L)]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L][H]<sup>3</sup> ',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=554; historical trailing-space preservation'),
    555: SourceNameCorrection(
        '[M<sub>2</sub>O<sub>4</sub>(OH)<sub>2</sub>(H-<sub>1</sub>L)]/[M<sub>2</sub>O<sub>4</sub>(OH)<sub>3</sub>(H-<s',
        '[M<sub>2</sub>O<sub>4</sub>(OH)<sub>2</sub>(H<sub>-1</sub>L)]/[M<sub>2</sub>O<sub>4</sub>(OH)<sub>3</sub>(H<sub>-1</sub>L)][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=555; historical completion of a varchar(110) source value'),
    556: SourceNameCorrection(
        '[M<sub>2</sub>O<sub>4</sub>(OH)<sub>3</sub>(H-<sub>1</sub>L)]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L',
        '[M<sub>2</sub>O<sub>4</sub>(OH)<sub>3</sub>(H<sub>-1</sub>L)]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L][H]<sup>4</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=556; historical completion of a varchar(110) source value'),
    557: SourceNameCorrection(
        '[V<sub>2</sub>O<sub>4</sub>(OH)<sub>4</sub>L<sub>2</sub>]/[H<sub>2</sub>VO<sub>4</sub>]<sup>2</sup>[L]<sup>2</',
        '[V<sub>2</sub>O<sub>4</sub>(OH)<sub>4</sub>L<sub>2</sub>]/[H<sub>2</sub>VO<sub>4</sub>]<sup>2</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=557; historical completion of a varchar(110) source value'),
    559: SourceNameCorrection(
        '[M<sub>2</sub>O<sub>5</sub>(H-<sub>1</sub>L)<sub>2</sub>]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L]<su',
        '[M<sub>2</sub>O<sub>5</sub>(H<sub>-1</sub>L)<sub>2</sub>]/[(MO<sub>2</sub>(OH)<sub>4</sub>)<sub>2</sub>][L]<sup>2</sup>[H]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=559; historical completion of a varchar(110) source value'),
    590: SourceNameCorrection(
        '[M<sub>2</sub>V<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>]/[MV<sub>1</sub><sub>0</sub>O<sub>2</sub><sub',
        '[M<sub>2</sub>V<sub>10</sub>O<sub>28</sub>]/[MV<sub>10</sub>O<sub>28</sub>][M]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=590; historical completion of a varchar(110) source value'),
    618: SourceNameCorrection(
        '[M]<sup>3</sup>[VO<sub>4</sub>]<sup>2</sup>/[M<sub>3</sub>(VO<sub>4</sub>)<sub>2</sub>(H<sub>2</sub>O)<sub>4</',
        '[M]<sup>3</sup>[VO<sub>4</sub>]<sup>2</sup>/[M<sub>3</sub>(VO<sub>4</sub>)<sub>2</sub>(H<sub>2</sub>O)<sub>4</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=618; historical completion of a varchar(110) source value'),
    626: SourceNameCorrection(
        '[M]<sup>3</sup>[V<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>]/[M<sub>3</sub>V<sub>1</sub><sub>0</sub>O<s',
        '[M]<sup>3</sup>[V<sub>10</sub>O<sub>28</sub>]/[M<sub>3</sub>V<sub>10</sub>O<sub>28</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=626; historical completion of a varchar(110) source value'),
    628: SourceNameCorrection(
        '[M<sub>3</sub>H<sub>1</sub><sub>7</sub>L<sub>6</sub>]/[M<sub>3</sub>H<sub>1</sub><sub>5</sub>L<sub>6</sub>][H]',
        '[M<sub>3</sub>H<sub>17</sub>L<sub>6</sub>]/[M<sub>3</sub>H<sub>15</sub>L<sub>6</sub>][H]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=628; historical completion of a varchar(110) source value'),
    629: SourceNameCorrection(
        '[M<sub>3</sub>H<sub>1</sub><sub>8</sub>L<sub>8</sub>][H]<sup>6</sup>/[M]<sup>3</sup>[H<sub>3</sub>L]<sup>8</su',
        '[M<sub>3</sub>H<sub>18</sub>L<sub>8</sub>][H]<sup>6</sup>/[M]<sup>3</sup>[H<sub>3</sub>L]<sup>8</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=629; historical completion of a varchar(110) source value'),
    658: SourceNameCorrection(
        '[M<sub>4</sub>(H-<sub>2</sub>L)(H-<sub>1</sub>L)<sub>2</sub>]/[M<sub>4</sub>(H-<sub>2</sub>L)<sub>2</sub>(H-<s',
        '[M<sub>4</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>2</sub>]/[M<sub>4</sub>(H<sub>-2</sub>L)<sub>2</sub>(H<sub>-1</sub>L)][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=658; historical completion of a varchar(110) source value'),
    680: SourceNameCorrection(
        '[V<sub>4</sub>O<sub>4</sub>(OH)<sub>1</sub><sub>2</sub>L<sub>2</sub>]/[H<sub>2</sub>VO<sub>4</sub>]<sup>4</sup',
        '[V<sub>4</sub>O<sub>4</sub>(OH)<sub>12</sub>L<sub>2</sub>]/[H<sub>2</sub>VO<sub>4</sub>]<sup>4</sup>[H]<sup>4</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=680; historical completion of a varchar(110) source value'),
    681: SourceNameCorrection(
        '[V<sub>4</sub>O<sub>4</sub>(OH)<sub>8</sub>(H-<sub>2</sub>L)<sub>2</sub>]/[H<sub>2</sub>VO<sub>4</sub>]<sup>4<',
        '[V<sub>4</sub>O<sub>4</sub>(OH)<sub>8</sub>(H<sub>-2</sub>L)<sub>2</sub>]/[H<sub>2</sub>VO<sub>4</sub>]<sup>4</sup>[H]<sup>4</sup>[L]<sup>2</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=681; historical completion of a varchar(110) source value'),
    685: SourceNameCorrection(
        '[M<sub>5</sub>(H-<sub>2</sub>L)(H-<sub>1</sub>L)<sub>3</sub>]/[M<sub>5</sub>(H-<sub>2</sub>L)<sub>2</sub>(H-<s',
        '[M<sub>5</sub>(H<sub>-2</sub>L)(H<sub>-1</sub>L)<sub>3</sub>]/[M<sub>5</sub>(H<sub>-2</sub>L)<sub>2</sub>(H<sub>-1</sub>L)<sub>2</sub>[H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=685; historical completion of a varchar(110) source value'),
    687: SourceNameCorrection(
        '[M]<sup>5</sup>[HL]<sup>4</sup>/[H]<sup>2</sup>[M<sub>5</sub>H<sub>2</sub>L<sub>4</sub>(H<sub>2</sub>O)<sub>4<',
        '[M]<sup>5</sup>[HL]<sup>4</sup>/[H]<sup>2</sup>[M<sub>5</sub>H<sub>2</sub>L<sub>4</sub>(H<sub>2</sub>O)<sub>4</sub>(s)]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=687; historical completion of a varchar(110) source value'),
    697: SourceNameCorrection(
        '[M<sub>6</sub>(H-<sub>2</sub>L)<sub>2</sub>(H-<sub>1</sub>L)<sub>3</sub>][H]<sup>7</sup>/[M]<sup>6</sup>[L]<su',
        '[M<sub>6</sub>(H<sub>-2</sub>L)<sub>2</sub>(H<sub>-1</sub>L)<sub>3</sub>][H]<sup>7</sup>/[M]<sup>6</sup>[L]<sup>5</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=697; historical completion of a varchar(110) source value'),
    709: SourceNameCorrection(
        '[M<sub>8</sub>(H-<sub>2</sub>L)<sub>4</sub>(H-<sub>1</sub>L)<sub>2</sub>][H]<sup>1<sub>0</sub></sup>/[M]<sup>8',
        '[M<sub>8</sub>(H<sub>-2</sub>L)<sub>4</sub>(H<sub>-1</sub>L)<sub>2</sub>][H]<sup>10</sup>/[M]<sup>8</sup>[L]<sup>6</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=709; historical completion of a varchar(110) source value'),
    710: SourceNameCorrection(
        '[M<sub>9</sub>L<sub>2<sub>0</sub></sub>]/[M<sub>6</sub>L<sub>1<sub>2</sub></sub>]<sup>1.5</sup>[L]<sup>2</sup>',
        '[M<sub>9</sub>L<sub>2<sub>0</sub></sub>]/[M<sub>6</sub>L<sub>1<sub>2</sub></sub>]<sup>1.5</sup>[L]<sup>2</sup> ',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=710; historical trailing-space preservation'),
    810: SourceNameCorrection(
        '[MHV<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>]/[M][HV<sub>1</sub><sub>0</sub>O<sub>2</sub><sub>8</sub>',
        '[MHV<sub>10</sub>O<sub>28</sub>]/[M][HV<sub>10</sub>O<sub>28</sub>]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=810; historical completion of a varchar(110) source value'),
    937: SourceNameCorrection(
        '[MO<sub>2</sub>H<sub>2</sub>(H-<sub>1</sub>L)<sub>2</sub>]/[MO<sub>2</sub>(OH)<sub>4</sub>][L]<sup>2</sup>[H]<',
        '[MO<sub>2</sub>H<sub>2</sub>(H<sub>-1</sub>L)<sub>2</sub>]/[MO<sub>2</sub>(OH)<sub>4</sub>][L]<sup>2</sup>[H]<sup>4</sup>',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=937; historical completion of a varchar(110) source value'),
    1003: SourceNameCorrection(
        '[Sb<sub>1</sub><sub>2</sub>(OH)<sub>6</sub><sub>4</sub>]/[Sb<sub>1</sub><sub>2</sub>(OH)<sub>6</sub><sub>5</su',
        '[Sb<sub>12</sub>(OH)<sub>64</sub>]/[Sb<sub>12</sub>(OH)<sub>65</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=1003; historical completion of a varchar(110) source value'),
    1004: SourceNameCorrection(
        '[Sb<sub>1</sub><sub>2</sub>(OH)<sub>6</sub><sub>5</sub>]/[Sb<sub>1</sub><sub>2</sub>(OH)<sub>6</sub><sub>6</su',
        '[Sb<sub>12</sub>(OH)<sub>65</sub>]/[Sb<sub>12</sub>(OH)<sub>66</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=1004; historical completion of a varchar(110) source value'),
    1005: SourceNameCorrection(
        '[Sb<sub>1</sub><sub>2</sub>(OH)<sub>6</sub><sub>6</sub>]/[Sb<sub>1</sub><sub>2</sub>(OH)<sub>6</sub><sub>7</su',
        '[Sb<sub>12</sub>(OH)<sub>66</sub>]/[Sb<sub>12</sub>(OH)<sub>67</sub>][H]',
        BETA_CURATION_PROVENANCE + '; beta_definitionID=1005; historical completion of a varchar(110) source value'),
}


def normalize_beta_markup(value: str) -> str:
    """Preserve the three mechanical markup edits in the historical beta export."""
    value = value.replace("</sub><sub>", "").replace("</sup><sup>", "")
    value = re.sub(r"([A-Za-z])-<sub>(\d+)</sub>", r"\1<sub>-\2</sub>", value)
    # The dump sometimes nests the final decimal/digit inside a subscript tag,
    # e.g. <sup>0.2<sub>5</sub></sup>; concatenate the numeric fragments.
    return re.sub(r"<(sub|sup)>([0-9.]+)<sub>([0-9]+)</sub></\1>",
                  r"<\1>\2\3</\1>", value)


def normalize_metal_markup(value: str) -> str:
    """Translate the dump's HTML subscripts and charges to parser notation."""
    value = re.sub(r"<sub>(.*?)</sub>", r"_[\1]", value)
    return re.sub(r"<sup>(.*?)</sup>", r"^[\1]", value)


def normalize_source_rows(
    key: str,
    columns: Sequence[str],
    rows: Iterable[Mapping[str, str]],
    *,
    require_all_corrections: bool = True,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Return source rows and JSON-ready SRC-02 audit entries.

    Full beta imports must contain every curated ID and each exact source value.
    The explicit subset option is for callers processing synthetic fixtures or a
    previously validated subset; production table readers use the strict default.
    Caller-owned rows are never modified. Non-name cells keep their original dump
    values, including timestamps, null markers, and scientific-data precision.
    """
    name_columns = {
        "beta_definition": ("beta_definitionID", "name_beta_definition"),
        "metal": ("metalID", "name_metal"),
        "solvent": ("solventID", "name_solvent"),
    }
    if key not in name_columns:
        return list(rows), []
    id_column, value_column = name_columns[key]
    missing_columns = {id_column, value_column} - set(columns)
    if missing_columns:
        raise ValueError(f"SRC-02 {key}: missing source columns {sorted(missing_columns)}")

    normalized_rows: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        try:
            record_id, original = str(row[id_column]), row[value_column]
        except KeyError as exc:
            raise ValueError(f"SRC-02 {key}: missing source field {exc.args[0]}") from exc
        if record_id in seen_ids:
            raise ValueError(f"SRC-02 {key}: duplicate source ID {record_id}")
        seen_ids.add(record_id)
        if not isinstance(original, str):
            raise ValueError(f"SRC-02 {key} ID {record_id}: source name must be text")
        correction = (BETA_SOURCE_CORRECTIONS.get(int(record_id))
                      if key == "beta_definition" and record_id.isdecimal() else None)
        if correction is not None:
            if original != correction.expected_original:
                raise ValueError(
                    f"SRC-02 beta_definition ID {record_id}: curated source value changed; "
                    f"expected {correction.expected_original!r}, found {original!r}"
                )
            replacement = correction.replacement
            kind = "pinned_source_curation"
            provenance = correction.provenance
        elif key == "beta_definition":
            replacement = normalize_beta_markup(original)
            kind = "markup_normalised"
            provenance = "Historical beta export: adjacent sub/sup tags, negative subscripts, nested numeric tags"
        else:
            replacement = normalize_metal_markup(original)
            kind = "html_to_notation"
            provenance = f"Historical {key} export: HTML sub/sup converted to _[..]/^[..] notation"
        updated = dict(row)
        if replacement != original:
            updated[value_column] = replacement
            entries.append({
                "table": key, "record_id": record_id, "column": value_column,
                "rule_id": "SRC-02", "kind": kind, "original": original,
                "replacement": replacement, "provenance": provenance,
            })
        normalized_rows.append(updated)
    if key == "beta_definition" and require_all_corrections:
        missing_ids = sorted(set(BETA_SOURCE_CORRECTIONS) - {int(i) for i in seen_ids if i.isdecimal()})
        if missing_ids:
            raise ValueError(f"SRC-02 beta_definition: missing curated source IDs {missing_ids}")
    return normalized_rows, entries


__all__ = [
    "SourceNameCorrection", "BETA_SOURCE_CORRECTIONS", "BETA_CURATION_PROVENANCE",
    "BETA_CURATION_CSV_SHA256", "BETA_CURATION_DUMP_SHA256",
    "normalize_beta_markup", "normalize_metal_markup", "normalize_source_rows",
]
