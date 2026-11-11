"""Redraw the data plots of the paper's figures from the benchmark runs stored in this repository.

Every plot is drawn from the solver output files of one stored run (``_benchmark/<model set>/<run>/L1_call_NN/solver``);
no solver is run and no file outside this repository is read.  The Pourbaix maps go through the plotter of the
analysis pipeline shipped here (``SRD46_research_agent``), so a map is the pipeline's own drawing of the run's saved
label map, sized for print.

    python replot_figures.py                 every figure below (10-15 min; a six-component map takes 0.5-2 min)
    python replot_figures.py fig6 s7-2       selected figures
    python replot_figures.py --list          the figure names
    python replot_figures.py --out DIR       output folder (default: output/ next to this script)

Output: one folder per figure.  The pictures in it are TIFF files at 600 dpi print resolution and show what the
figure looks like; its ``csv`` subfolder holds what is plotted, as plain tables (one header row, numbers below, an
empty cell where there is no value) that can be pasted into a plotting program:

    curves   <panel>.csv               x in the first column, one column per curve
             <panel>_species.csv       colour and line style of each curve, and where its name is set
    maps     <panel>_boundaries.csv    pH, E along every boundary line; an empty row separates two lines
             <panel>_regions.csv       one row per label on the map: position, species, fill colour
             <panel>_points.csv        triple points, and points where a boundary meets the edge of the map
             <panel>_water_lines.csv   the two water stability lines
             <panel>_label_map.csv     the raster the map is filled from: E down, pH across, cell = label id
                                       (the ids are listed in <panel>_regions.csv; -2 = no value)

Figures and what is drawn for each:

    fig4   M_Fig4/        Fig. 4a-c      Fe Pourbaix maps in three water-organic solvent mixtures, and the three in a row
    fig5   M_Fig5/        Fig. 5a,b      fraction of each metal, glycine sweep and ethylenediamine pH sweep
    fig6   M_Fig6/        Fig. 6a,b      Cu and Fe Pourbaix maps of the six-component system
    e5     ED_Fig_E5/     ED Fig. E5a-d  Cu-ammonia map from the runs of four models, one plot-area size, one numbering
    e7     ED_Fig_E7/     ED Fig. E7a,b  Cu and Fe maps of the six-component system from the GPT-5.5 run
    s6-1   SI_Fig_S6-1/   SI Fig. S6-1   Cu and Fe maps of the six-component system, prompt without the hint
    s6-2   SI_Fig_S6-2/   SI Fig. S6-2   log-concentration plots, Fe(III) with EDTA and with citrate
    s6-3   SI_Fig_S6-3/   SI Fig. S6-3   Cu and Fe maps of the run made without topology clean-up, uncleaned topology
    s7-1   SI_Fig_S7-1/   SI Fig. S7-1   Ni-glycine map, Opus 4.7 and GPT-5.5
    s7-2   SI_Fig_S7-2/   SI Fig. S7-2   Cu-ammonia map, Opus 4.7 and GPT-5.5
    s7-3   SI_Fig_S7-3/   SI Fig. S7-3   Fe(III)-citrate log-concentration plot, Opus 4.7 and GPT-5.5
    s7-4   SI_Fig_S7-4/   SI Fig. S7-4   Cu, Zn + glycine + ammonia log-concentration plot, Opus 4.7 and GPT-5.5
    s7-5   SI_Fig_S7-5/   SI Fig. S7-5   Cu-ammonia log-concentration plot at fixed Eh, Opus 4.7 and GPT-5.5
    s7-6   SI_Fig_S7-6/   SI Fig. S7-6   Cu-ammonia fraction and log-concentration plots from the runs of four models

What the published figures add around these plots is not drawn here: panel letters, model names, the keys of the
numbered regions and the legend of S7-6 are text in the figure layout (the keys are in ``_regions.csv``, the legend
entries in ``SI_S7-6_legend.csv``).  Fig. 5a,b are drawn in the published figure as editable vector shapes; here
the same curves, labels and positions are drawn with matplotlib.  Schematics, tables, answer excerpts and
screenshots are not data plots and are not covered.

Apart from Fig. 5 the pictures have the pixels of the published ones when drawn with matplotlib 3.11.0 (see
requirements.txt) and the fonts DejaVu Sans (maps, log-concentration plots) and Arial (S7-6, Fig. 5): a map falls
back to a region number where a name does not fit, and the log-concentration plots look for free space for each
name on the rendered canvas, so other text metrics can move or renumber labels.  The TIFF files are written
uncompressed by Pillow, which matplotlib installs.  Every map needs, next to its ``pourbaix_map_*.csv``, the run's
``speciation_full_*.csv`` (only its header is read, for the list of solids).
"""
import argparse
import contextlib
import csv
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True
# The maps are drawn with the pipeline's topology clean-up on (its default); S6-3 asks for the uncleaned topology itself.
os.environ['SRD46_TOPOLOGY_FIX'] = '1'

import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(os.path.abspath(__file__)).parent
BENCHMARK = HERE.parents[1]
CODE = BENCHMARK.parent / 'SRD46_research_agent'
NUMCALC = CODE / 'NIST_SRD46_db_agent' / 'NIST_SRD46_analysis_agent' / 'NIST_SRD46_core_numcalc_pipeline'

PRINT_DPI = 600
CANVAS_W = 8.6          # tight width (in) of the pipeline plotter's canvas; sets the font scale for a print width

SYS6 = 'Cu_+_Fe_+_Citric_acid_+_Glycine_+_Ammonia_+_Chloride_ion'
SYS6_TITLE = 'Cu + Fe + Citric acid + Glycine\n+ Ammonia + Chloride ion (%s)'
FE_REDOX = 'Fe$+2_+_Fe$+0_+_Fe$+3_+_Fe$+6_+_'
CU_REDOX = 'Cu$+1_+_Cu$+0_+_Cu$+2_+_'


@contextlib.contextmanager
def drive_letter_paths():
    """On Windows, ``Path.resolve()`` turns a path on a mapped network drive into its longer UNC form.  The pipeline
    modules put their folders on ``sys.path`` through ``resolve()``, and from a deep folder on such a drive the
    deepest of them then pass the 260-character path limit and cannot be imported.  While the figures are drawn,
    ``resolve()`` keeps the form of the path this script was started with; elsewhere this changes nothing."""
    if os.name != 'nt':
        yield
        return
    with mock.patch.object(Path, 'resolve', lambda self, strict=False: Path(os.path.abspath(self))):
        yield


def solver_dir(model_set, run, call='L1_call_01'):
    return BENCHMARK / model_set / run / call / 'solver'


def save_tiff(fig, path, dpi, t0, **savefig_options):
    """Save the figure as an RGB TIFF tagged with the print resolution.  Pillow writes it uncompressed with its
    own writer; a compressed TIFF needs its libtiff binding, which does not work in every installation."""
    rendered = io.BytesIO()
    Figure.savefig(fig, rendered, format='png', dpi=dpi, **savefig_options)
    rendered.seek(0)
    image = Image.open(rendered).convert('RGB')
    image.save(path, dpi=(PRINT_DPI, PRINT_DPI))
    print(f'  {path.name}: {image.width} x {image.height} px, {time.time() - t0:.0f} s', flush=True)


def cell(value):
    """A table cell: a number with ten significant digits, nothing for a missing value."""
    if value is None:
        return ''
    if isinstance(value, (float, np.floating)):
        return '' if np.isnan(value) else repr(float('%.10g' % value))
    if isinstance(value, np.integer):
        return int(value)
    return value


def write_csv(path, header, rows):
    """One header row, then the rows; an empty row is written as an empty line."""
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(header)
        for row in rows:
            writer.writerow([cell(v) for v in row])


# --------------------------------------------------------------------------------------------------------------------
# Species names
# --------------------------------------------------------------------------------------------------------------------

def chem(name, bold=True):
    """Database species name -> matplotlib mathtext: digits after an element or bracket become subscripts, the
    trailing charge a superscript.  The name itself is kept, e.g. [Cu(Ammo)4]2+ -> [Cu(Ammo)$_4$]$^{2+}$."""
    wrap = (lambda s: r'\mathbf{%s}' % s) if bold else (lambda s: r'\mathrm{%s}' % s)
    suffix = ''
    if name.endswith('(s)'):
        name, suffix = name[:-3], '(s)'
    # A digit before the sign is a charge digit after "]" (complex), after a bare element symbol (Cu2+) or after
    # another digit (CuO22-); otherwise it belongs to the formula (HCuO2-).
    m = (re.search(r'(?<=\])\d?[+-]$', name) or re.fullmatch(r'[A-Z][a-z]?(\d?[+-])', name)
         or re.search(r'(?<=\d)\d[+-]$', name) or re.search(r'[+-]$', name))
    charge = ''
    if m:
        start = m.start(1) if m.re.groups else m.start()
        name, charge = name[:start], name[start:]
    body = re.sub(r'(?<=[A-Za-z)])(\d+(?:\.\d+)?)', lambda d: '$_{%s}$' % wrap(d.group(1)), name)
    if charge:      # braces keep mathtext from spacing the sign as a binary operator
        body += '$^{%s}$' % wrap('%s{%s}' % (charge[:-1], charge[-1]))
    return body.replace('$$', '') + suffix


# --------------------------------------------------------------------------------------------------------------------
# Pourbaix maps: saved label map -> topology -> the pipeline's plotter
# --------------------------------------------------------------------------------------------------------------------

_PIPELINE = {}
_SCENES = {}
_ELEMENT = re.compile(r'^[A-Z][a-z]?$')


def pipeline():
    """The plotting and topology modules of the analysis pipeline in this repository, imported on first use."""
    if not _PIPELINE:
        sys.path[:0] = [str(NUMCALC), str(NUMCALC / 'solvers_and_topology'), str(CODE)]
        from solvers_and_topology.nd_grid.data_types import GridAxis
        from solvers_and_topology.nd_grid.effective_topology import extract_effective_topology
        from sweep_pipelines._output_and_plotting._output_topology_compactor.compact_nd import compact_topology_nd
        from sweep_pipelines._output_and_plotting.pourbaix_diagrams import plotter
        from sweep_pipelines._output_and_plotting.pourbaix_diagrams.csv_exporter import load_pourbaix_csv
        _PIPELINE.update(GridAxis=GridAxis, extract_effective_topology=extract_effective_topology,
                         compact_topology_nd=compact_topology_nd, plotter=plotter,
                         load_pourbaix_csv=load_pourbaix_csv)
    return SimpleNamespace(**_PIPELINE)


class LabelGrid:
    """The saved label map in the shape the plotter reads a solved grid."""

    def __init__(self, axes, labels, catalog):
        self.axes = axes
        self.labels = labels
        self.label_catalog = catalog
        self.labels_per_element = None
        self.label_catalog_per_element = None

    @property
    def ndim(self):
        return len(self.axes)

    @property
    def shape(self):
        return tuple(axis.n for axis in self.axes)

    def axis_index(self, name):
        return next(i for i, axis in enumerate(self.axes) if axis.name == name)

    @property
    def E_values(self):
        return self.axes[self.axis_index('E_V')].values

    @property
    def pH_values(self):
        return self.axes[self.axis_index('pH')].values


def csv_header(path):
    """The ``# key: value`` lines at the top of a solver CSV."""
    meta = {}
    with path.open('r', encoding='utf-8') as stream:
        for line in stream:
            if not line.startswith('#'):
                break
            if ':' in line:
                key, value = line[1:].split(':', 1)
                meta[key.strip()] = value.strip()
    return meta


def header_range(meta, key):
    return tuple(float(v) for v in meta[key].split(','))


def solids_of_run(folder):
    """Names of the solids the run considered, from the header of its full speciation table."""
    for table in sorted(folder.glob('speciation_full_*.csv')):
        raw = csv_header(table).get('saturation_reference_json')
        if raw:
            return sorted(json.loads(raw).keys())
    return []


def chemical_system(meta, catalog, solids):
    components = []
    for chunk in meta.get('component_totals_M', '').split(';'):
        if '=' in chunk:
            name, value = chunk.split('=', 1)
            components.append((name.strip(), float(value)))
    elements = [(n, v) for n, v in components if _ELEMENT.match(n)]
    ligands = [(n, v) for n, v in components if not _ELEMENT.match(n)]
    names = set(catalog.values())
    return SimpleNamespace(
        system_name=meta.get('system_name', ''),
        element_names=[n for n, _ in elements], element_totals=[v for _, v in elements],
        ligand_names=[n for n, _ in ligands], ligand_totals=[v for _, v in ligands],
        temperature_C=25.0,
        diss_labels=[s for s in solids if s in names],
        spec_id_to_name={name: chem(name) for name in names})


def coarse_grid(meta, E, pH, E_domain, pH_domain):
    """Cell-centred axes of the run's coarse solver grid.  The topology clean-up takes its trust radius from the
    spacing of these axes; without recorded coarse counts the fine axis is used as it is."""
    GridAxis = pipeline().GridAxis
    step = {}
    try:
        n_pH, n_E = int(meta['n_pH_coarse']), int(meta['n_E_coarse'])
    except (KeyError, ValueError):
        n_pH = n_E = 0
    if n_pH > 1:
        step['pH'] = (pH_domain[1] - pH_domain[0]) / (n_pH - 1)
    if n_E > 1:
        step['E_V'] = (E_domain[1] - E_domain[0]) / (n_E - 1)

    def axis(name, fine, domain):
        if step.get(name):
            lo, hi = domain
            values = np.arange(lo + step[name] / 2.0, hi, step[name])
            if values.size < 1:
                values = np.asarray([(lo + hi) / 2.0], dtype=float)
        else:
            values = np.asarray(fine, dtype=float)
        return GridAxis(name, values, domain_range=tuple(domain))

    return SimpleNamespace(axes=[axis('E_V', E, E_domain), axis('pH', pH, pH_domain)])


def build_scene(source_csv, raw_topology=False):
    """Saved label map -> what the plotter needs, rebuilt the way the pipeline builds it when it writes its own
    picture: topology from the label map, clean-up pass, compaction of the boundaries.

    ``raw_topology`` draws the topology and the region labels as they are before the clean-up pass, for the run
    that was made, and read by the agent, without it.
    """
    key = (str(source_csv), raw_topology)
    if key in _SCENES:
        return _SCENES[key]
    pipe = pipeline()
    meta = csv_header(source_csv)
    pH_domain, E_domain = header_range(meta, 'pH_range'), header_range(meta, 'E_range')
    pH, E, labels, catalog = pipe.load_pourbaix_csv(str(source_csv))
    inside = ((pH >= pH_domain[0]) & (pH <= pH_domain[1])).all() and ((E >= E_domain[0]) & (E <= E_domain[1])).all()
    assert inside, f'{source_csv.name}: the label map extends beyond its declared pH or E range'
    axes = [pipe.GridAxis('E_V', E, domain_range=E_domain), pipe.GridAxis('pH', pH, domain_range=pH_domain)]
    cleaned, _axes, cleaned_labels, _facets, raw = pipe.extract_effective_topology(
        coarse_grid(meta, E, pH, E_domain, pH_domain), ([E, pH], labels, catalog))
    compact = pipe.compact_topology_nd(raw if raw_topology else cleaned)
    compact.label_catalog = dict(catalog)
    scene = SimpleNamespace(
        csv=source_csv, element=meta['element'], catalog=catalog,
        grid=LabelGrid(axes, labels, catalog),
        system=chemical_system(meta, catalog, solids_of_run(source_csv.parent)),
        compact=compact,
        region_labels=np.asarray(labels if raw_topology else cleaned_labels))
    _SCENES[key] = scene
    return scene


def plot_on_canvas(scene, out_png, font_scale, title):
    """Run the pipeline plotter (publication mode, no side panel) and keep its figure open instead of saving it.
    Returns the figure and the numbered-region key, which the plotter writes as a footnote and the paper's figures
    set as text; the footnote is taken off the figure."""
    pipe = pipeline()
    held = {}
    with mock.patch.object(Figure, 'savefig', lambda self, *a, **k: held.setdefault('fig', self)), \
            mock.patch.object(plt, 'close', lambda *a, **k: None):
        pipe.plotter.plot_pourbaix(scene.grid, scene.system, str(out_png), csv_path=str(scene.csv),
                                   principal_element=scene.element, topology_map=scene.compact,
                                   show_compact_controls=True, region_label_source=scene.region_labels,
                                   publication=True, side_panel=False, font_scale=font_scale, title=title,
                                   debug=False)
    fig = held['fig']
    key = {}
    for t in list(fig.texts):
        for num, name in re.findall(r'(\d+)\. (.+?)(?=\s{3}\d+\. |$)', t.get_text()):
            key[int(num)] = name.strip()
        t.remove()
    return fig, key


def set_text_sizes(ax, pt, title_factor):
    ax.tick_params(labelsize=pt)
    ax.xaxis.label.set_size(pt * 1.05)
    ax.yaxis.label.set_size(pt * 1.05)
    ax.title.set_size(pt * title_factor)
    for t in ax.texts:
        if '/H$_2$O' in t.get_text():          # labels of the two water stability lines
            t.set_fontsize(pt * 0.95)


def write_map_tables(folder, name, scene, key, ax):
    """The drawn map as tables in ``csv/``: boundary lines, labels, marked points, water lines, label raster."""
    tables = folder / 'csv'
    catalog = scene.catalog
    labels = np.asarray(scene.grid.labels)
    present = sorted(set(labels.ravel().tolist()) - {-2})
    palette = pipeline().plotter._PALETTE
    colour = {catalog[label]: palette[i % len(palette)] for i, label in enumerate(present)}
    label_id = {species: label for label, species in catalog.items()}
    solids = set(scene.system.diss_labels) | set(scene.system.element_names)
    plain = {chem(species): species for species in catalog.values()}     # names as printed -> database names

    rows, labelled = [], set()
    for t in ax.texts:
        if t.get_zorder() != 12:
            continue
        shown = t.get_text()
        printed = key[int(shown)] if shown.isdigit() else shown
        species = plain.get(printed, printed)
        pH, E = t.get_position()
        rows.append([pH, E, shown if shown.isdigit() else species, species, label_id.get(species),
                     colour.get(species), 'yes' if species in solids else 'no'])
        labelled.add(species)
    rows += [[None, None, None, catalog[label], label, colour[catalog[label]],
              'yes' if catalog[label] in solids else 'no'] for label in present if catalog[label] not in labelled]
    write_csv(tables / f'{name}_regions.csv',
              ['pH', 'E (V vs SHE)', 'label on the map', 'species', 'label id', 'fill colour', 'solid phase'], rows)

    rows = []
    for number, boundary in enumerate(scene.compact.features.get(1, []), start=1):
        sides = [catalog.get(label, '') for label in boundary.labels] + ['', '']
        if rows:
            rows.append([])
        rows += [[pH, E, number, sides[0], sides[1]] for E, pH in boundary.geometry_compact]
    write_csv(tables / f'{name}_boundaries.csv', ['pH', 'E (V vs SHE)', 'boundary', 'species 1', 'species 2'], rows)

    rows = []
    for marks in ax.collections:
        if marks.get_zorder() == 10:
            kind = 'triple point' if marks.get_label() == 'Triple point' else 'boundary at the map edge'
            rows += [[pH, E, kind] for pH, E in np.asarray(marks.get_offsets()).tolist()]
    write_csv(tables / f'{name}_points.csv', ['pH', 'E (V vs SHE)', 'point'], rows)

    water = sorted((line.get_data() for line in ax.lines if line.get_color() == 'b'), key=lambda xy: -xy[1][0])
    if len(water) == 2 and np.array_equal(water[0][0], water[1][0]):
        write_csv(tables / f'{name}_water_lines.csv', ['pH', 'E O2/H2O (V vs SHE)', 'E H2/H2O (V vs SHE)'],
                  zip(water[0][0], water[0][1], water[1][1]))

    with open(tables / f'{name}_label_map.csv', 'w', encoding='utf-8', newline='') as f:
        f.write(','.join(['E (V vs SHE) \\ pH'] + [cell(float(v)) for v in scene.grid.pH_values]) + '\n')
        for E, row in zip(scene.grid.E_values, labels):
            f.write(cell(float(E)) + ',' + ','.join(map(str, row.tolist())) + '\n')


def draw_map(source_csv, folder, name, *, width_in, region_pt=5.5, text_pt=7.0, title=None, raw_topology=False):
    """One map at a given print width.  The figure is drawn at the plotter's own canvas size, so markers, lines and
    hatching keep their proportions, and saved at the dpi that gives ``width_in`` at 600 dpi print resolution.
    Region names print at ``region_pt``, every other text at ``text_pt``."""
    t0 = time.time()
    picture = folder / f'{name}.tiff'
    scene = build_scene(source_csv, raw_topology)
    fig, key = plot_on_canvas(scene, picture, region_pt / (width_in / CANVAS_W) / 12.0, title)
    ax = fig.axes[0]
    pad = 0.04
    fig.canvas.draw()
    scale = width_in / (fig.get_tightbbox(fig.canvas.get_renderer()).width + 2 * pad)
    set_text_sizes(ax, text_pt / scale, 1.05)
    fig.canvas.draw()
    scale = width_in / (fig.get_tightbbox(fig.canvas.get_renderer()).width + 2 * pad)
    save_tiff(fig, picture, PRINT_DPI * scale, t0, bbox_inches='tight', pad_inches=pad)
    write_map_tables(folder, name, scene, key, ax)
    plt.close(fig)


SIX_COMPONENT = dict(width_in=3.25, region_pt=5.5)
MAPS = {
    'fig4': [
        ('Fig4_a_Fe_DMF', solver_dir('Opus4.7', 'FF_1_20261103', 'L1_call_01') / 'pourbaix_map_Fe_+_DMF_Fe.csv',
         dict(width_in=2.2, region_pt=5.0, text_pt=6.5, title='Fe + DMF (Fe)')),
        ('Fig4_b_Fe_acetonitrile',
         solver_dir('Opus4.7', 'FF_1_20261103', 'L1_call_02') / 'pourbaix_map_Fe_+_Acetonitrile_Fe.csv',
         dict(width_in=2.2, region_pt=5.0, text_pt=6.5, title='Fe + acetonitrile (Fe)')),
        ('Fig4_c_Fe_ethylene_glycol',
         solver_dir('Opus4.7', 'FF_1_20261103', 'L1_call_03') / 'pourbaix_map_Fe_+_Ethylene_glycol_Fe.csv',
         dict(width_in=2.2, region_pt=5.0, text_pt=6.5, title='Fe + ethylene glycol (Fe)')),
    ],
    'fig6': [
        ('Fig6_a_Cu', solver_dir('Opus4.7', 'L1_11_20261030') / f'pourbaix_map_{SYS6}_Cu.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Cu')),
        ('Fig6_b_Fe', solver_dir('Opus4.7', 'L1_11_20261030') / f'pourbaix_map_{SYS6}_Fe.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Fe')),
    ],
    'e7': [
        ('ED_E7_a_Cu', solver_dir('GPT-5.5', 'L1_11_20261105') / f'pourbaix_map_{SYS6}_Cu.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Cu')),
        ('ED_E7_b_Fe', solver_dir('GPT-5.5', 'L1_11_20261105') / f'pourbaix_map_{SYS6}_Fe.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Fe')),
    ],
    's6-1': [
        ('SI_S6-1_a_Cu', solver_dir('Opus4.7', 'L1_10_20261030') / f'pourbaix_map_{SYS6}_Cu.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Cu')),
        ('SI_S6-1_b_Fe', solver_dir('Opus4.7', 'L1_10_20261030') / f'pourbaix_map_{SYS6}_Fe.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Fe')),
    ],
    's6-3': [
        ('SI_S6-3_a_Cu', solver_dir('Opus4.7_no_topo_cleanup', 'L1_11_20260830') / f'pourbaix_map_{SYS6}_Cu.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Cu', raw_topology=True)),
        ('SI_S6-3_b_Fe', solver_dir('Opus4.7_no_topo_cleanup', 'L1_11_20260830') / f'pourbaix_map_{SYS6}_Fe.csv',
         dict(SIX_COMPONENT, title=SYS6_TITLE % 'Fe', raw_topology=True)),
    ],
    's7-1': [
        ('SI_S7-1_Opus4.7', solver_dir('Opus4.7', 'L1_1_20261030') / 'pourbaix_map_Ni_+_Glycine_Ni.csv',
         dict(SIX_COMPONENT, title='Ni + Glycine (Ni)')),
        ('SI_S7-1_GPT-5.5', solver_dir('GPT-5.5', 'L1_1_20261103') / 'pourbaix_map_Ni_+_Glycine_Ni.csv',
         dict(SIX_COMPONENT, title='Ni + Glycine (Ni)')),
    ],
    's7-2': [
        ('SI_S7-2_Opus4.7', solver_dir('Opus4.7', 'L1_3_20261030') / 'pourbaix_map_Cu_+_Ammonia_Cu.csv',
         dict(SIX_COMPONENT, title='Cu + Ammonia (Cu)')),
        ('SI_S7-2_GPT-5.5', solver_dir('GPT-5.5', 'L1_3_20261103') / 'pourbaix_map_Cu_+_Ammonia_Cu.csv',
         dict(SIX_COMPONENT, title='Cu + Ammonia (Cu)')),
    ],
}


def draw_maps(figure, folder):
    for name, source_csv, style in MAPS[figure]:
        draw_map(source_csv, folder, name, **style)


def draw_fig4(folder):
    """The three maps, then the row of the figure: a 6.6 in strip with the maps left, centred and right."""
    draw_maps('fig4', folder)
    width, top, height = 3960, 40, 1206
    tiles = [Image.open(folder / f'{name}.tiff').convert('RGB') for name, _, _ in MAPS['fig4']]
    row = Image.new('RGB', (width, max(t.height for t in tiles) + top), 'white')
    for tile, x in zip(tiles, (0, (width - tiles[1].width) // 2, width - tiles[2].width)):
        row.paste(tile, (x, top))
    row.crop((0, 0, width, height)).save(folder / 'Fig4_abc_row.tiff', dpi=(PRINT_DPI, PRINT_DPI))
    print(f'  Fig4_abc_row.tiff: {width} x {height} px', flush=True)


E5_RUNS = [('a', 'Opus4.7', 'L1_3_20261030'), ('b', 'Opus5.5', 'L1_3_20261106'),
           ('c', 'GPT-5.5', 'L1_3_20261103'), ('d', 'GPT-6 Sol', 'L1_3_20261110')]


def draw_e5(folder):
    """The same map from four runs, comparable side by side: one print scale and one crop box around the axes, so
    the four plot areas have the same size, and one numbering of the regions.  The first map numbers its regions;
    a later map takes, for each of its numbered regions, the first map's number of the region with that name.
    Each map keeps the pH and potential range its run computed."""
    tile_w, region_pt, text_pt = 3.2, 5.5, 7.0
    margin = dict(left=0.58, right=0.06, bottom=0.34, top=0.2)      # print inches around the axes
    ylabel_x = 0.47                                                 # print inches from the left spine to the E label
    scale = tile_w / CANVAS_W
    first = {}
    for letter, model_set, run in E5_RUNS:
        t0 = time.time()
        name = f'ED_E5_{letter}_{model_set.replace(" ", "_")}'
        scene = build_scene(solver_dir(model_set, run) / 'pourbaix_map_Cu_+_Ammonia_Cu.csv')
        fig, key = plot_on_canvas(scene, folder / f'{name}.tiff', region_pt / scale / 12.0, '')
        ax = fig.axes[0]
        if first:
            free = {name: [k for k in sorted(first) if first[k] == name] for name in set(first.values())}
            renumber = {}
            for num in sorted(key):
                options = free.get(key[num], [])
                assert options, f'{run}: region {key[num]!r} is not a numbered region of the first map'
                new = num if num in options else options[0]
                options.remove(new)
                renumber[num] = new
            for t in ax.texts:
                if t.get_zorder() == 12 and t.get_text().isdigit() and int(t.get_text()) in renumber:
                    t.set_text(str(renumber[int(t.get_text())]))
            key = {renumber[k]: v for k, v in key.items()}
        else:
            first.update(key)
        set_text_sizes(ax, text_pt / scale, 1.15)
        ax.title.set_fontweight('bold')
        ax.yaxis.set_label_coords(
            -ylabel_x / tile_w * (tile_w / (ax.get_position().width * fig.get_size_inches()[0] * scale)), 0.5)
        fig.canvas.draw()
        p = ax.get_position()
        fw, fh = fig.get_size_inches()
        m = {k: v / scale for k, v in margin.items()}
        box = Bbox.from_extents(p.x0 * fw - m['left'], p.y0 * fh - m['bottom'],
                                p.x1 * fw + m['right'], p.y1 * fh + m['top'])
        save_tiff(fig, folder / f'{name}.tiff', PRINT_DPI * scale, t0, bbox_inches=box)
        write_map_tables(folder, name, scene, key, ax)
        plt.close(fig)


# --------------------------------------------------------------------------------------------------------------------
# Log-concentration plots with the species named on the curves
# --------------------------------------------------------------------------------------------------------------------

LIGAND_COLOURS = ['#e377c2', '#ff7f0e', '#bcbd22', '#8c564b', '#c49c94', '#ffbb78', '#f7b6d2', '#dbdb8d', '#c7c7c7']
ION_COLOURS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#17becf', '#e377c2', '#bcbd22']
SOLID_COLOURS = ['#006400', '#8b0000', '#00008b', '#4b0082', '#2f4f4f', '#8b4513', '#191970']
LOG_FLOOR = -12.0
STRIP_AXES_IN = (1651 / PRINT_DPI, 1463 / PRINT_DPI)       # plot area of a 3.25 in map, so the two kinds line up


def is_solid(name):
    return (name.endswith('(s)') or '(s,' in name or '(alpha)' in name
            or name in ('Cu', 'Fe', 'Zn', 'Ni', 'Co', 'Ag', 'Pb', 'Cd'))


def line_styles(names, solids, ligand_tags):
    """The pipeline's own log-concentration styles: ligand-bearing species dashed in the ligand colours, other
    dissolved species solid in the ion colours, solids thick in the solid colours."""
    out, n_lig, n_ion, n_sol = {}, 0, 0, 0
    for n in names:
        if n in solids:
            out[n] = (SOLID_COLOURS[n_sol % len(SOLID_COLOURS)], '-', 3.5)
            n_sol += 1
        elif any(t in n for t in ligand_tags):
            out[n] = (LIGAND_COLOURS[n_lig % len(LIGAND_COLOURS)], '--', 1.8)
            n_lig += 1
        else:
            out[n] = (ION_COLOURS[n_ion % len(ION_COLOURS)], '-', 1.5)
            n_ion += 1
    return out


def dominant_species(verdict, ligand_tags):
    """(species, pH from, pH to) rows of the 'Dominant species by pH region' blocks of the metals in the solver's
    report; the block of the ligand itself is left out."""
    out = []
    for part in verdict.read_text(encoding='utf-8').split('Dominant species by pH region:')[1:]:
        block = part.split('\n\n', 1)[0]
        rows = [(m[3], float(m[1]), float(m[2]))
                for m in re.finditer(r'pH\s+([\d.]+)–\s*([\d.]+)\s+→\s+(\S+)', block)]
        if any(t in r[0] and '(' not in r[0] for r in rows for t in ligand_tags):
            continue
        out.extend(rows)
    return out


def name_colour(colour):
    r, g, b = mcolors.to_rgb(colour)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (r * 0.68, g * 0.68, b * 0.68) if luminance > 0.55 else (r, g, b)


def draw_strip(source, stem, folder, name, *, title, ligand_tags, text_pt=7.0, name_pt=6.0, canvas_axes_w=5.1):
    """Log-concentration against pH from ``<stem>_log_conc.csv``, with no legend: the species that the solver's
    report (``<stem>_verdict.md``) lists as dominant over some pH window, and the forms of the ligand where each
    is the main one, are named on the plot.  Each name goes to the clear spot nearest its curve, found on the
    rendered canvas; a name with no clear spot is left out."""
    t0 = time.time()
    with open(source / f'{stem}_log_conc.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    names, data = rows[0][1:], np.array(rows[1:], float)
    solids = tuple(n for n in names if is_solid(n))
    pH = data[:, 0]
    scale = STRIP_AXES_IN[0] / canvas_axes_w               # print size / canvas size
    aw, ah = canvas_axes_w, STRIP_AXES_IN[1] / scale

    def pt(printed):
        return printed / scale

    left, bottom, top, right = 1.05, 0.75, 0.75, 0.15
    fig = plt.figure(figsize=(left + aw + right, bottom + ah + top))
    W, H = fig.get_size_inches()
    ax = fig.add_axes((left / W, bottom / H, aw / W, ah / H))

    style = line_styles(names, set(solids), ligand_tags)
    series = {}
    for j, n in enumerate(names, start=1):
        if n == 'H2O':
            continue
        v = data[:, j].copy()
        if n in solids:
            v[v <= -49] = np.nan                           # the solver writes -50 where the solid is absent
        else:
            v[v >= 0] = np.nan
        if np.all(np.isnan(v)) or np.nanmax(v) < LOG_FLOOR:
            continue
        colour, ls, lw = style[n]
        ax.plot(pH, v, color=colour, ls=ls, lw=lw)
        if n in solids:                                    # vertical edge where the solid appears or disappears
            for i in range(len(v)):
                if np.isnan(v[i]):
                    continue
                if (i > 0 and np.isnan(v[i - 1])) or (i < len(v) - 1 and np.isnan(v[i + 1])):
                    ax.plot([pH[i], pH[i]], [LOG_FLOOR, v[i]], color=colour, ls='-', lw=lw, solid_capstyle='butt')
        series[n] = v

    ax.set_xlim(pH.min(), pH.max())
    ax.set_ylim(LOG_FLOOR, 0)
    ax.set_xlabel('pH', fontsize=pt(text_pt * 1.05))
    ax.set_ylabel('log₁₀ [species]  (mol/L)', fontsize=pt(text_pt * 1.05))
    ax.set_title(title, fontsize=pt(text_pt * 1.05))
    ax.tick_params(labelsize=pt(text_pt))
    ax.grid(True, alpha=0.25)

    wanted = dominant_species(source / f'{stem}_verdict.md', ligand_tags)
    ligand_forms = [n for n in series if any(t in n for t in ligand_tags) and '(' not in n]
    n_metal = len(wanted)
    for n in ligand_forms:
        if len(ligand_forms) < 2:
            break
        others = np.nanmax([series[m] for m in ligand_forms if m != n], axis=0)
        on = pH[np.nan_to_num(series[n], nan=-99) >= np.nan_to_num(others, nan=-99)]
        if on.size == 0:
            continue
        wanted.append((n, on.min(), on.max()))
    dpi = fig.dpi
    fig.canvas.draw()
    ink = np.asarray(fig.canvas.buffer_rgba())[..., :3].min(2) < 215      # lines and frame, not the grid
    ink = ink[::-1]                                                       # row 0 = display y 0
    axbox = ax.get_window_extent()
    to_display = ax.transData.transform
    clearance = pt(0.8) * dpi / 72                                        # px around a name
    px_per_unit = (to_display((0, 1)) - to_display((0, 0)))[1]
    order = sorted(wanted[:n_metal], key=lambda w: w[1] - w[2]) + wanted[n_metal:]    # metal species, widest first
    named_at = {}
    for n, x0, x1 in order:
        if n not in series:
            continue
        t = ax.text(0, 0, chem(n, bold=False), fontsize=pt(name_pt), color=name_colour(style[n][0]),
                    ha='center', va='center', zorder=5)
        bb = t.get_window_extent()
        w, h = bb.width / 2 + clearance, bb.height / 2 + clearance
        best = None
        mid = (x0 + x1) / 2
        # candidates: within 1.5 pH of the window and 2.6 log units of the curve; the nearest clear one wins
        for x in np.arange(x0 - 1.5, x1 + 1.5001, 0.05):
            y_curve = np.interp(x, pH, np.nan_to_num(series[n], nan=LOG_FLOOR))
            for dy in np.arange(-2.6, 2.6001, 0.05):
                cx, cy = to_display((x, y_curve))
                cy += dy * px_per_unit
                box = (int(cx - w), int(cy - h), int(cx + w), int(cy + h))
                if box[0] < axbox.x0 or box[2] > axbox.x1 or box[1] < axbox.y0 or box[3] > axbox.y1:
                    continue
                if ink[box[1]:box[3], box[0]:box[2]].any():
                    continue
                score = abs(x - mid) / max(x1 - x0, 0.5) + (0 if x0 <= x <= x1 else 1.5) + 0.6 * abs(dy)
                if best is None or score < best[0]:
                    best = (score, cx, cy, box, x, y_curve, dy)
        if best is None:
            t.remove()
            print(f'  {name}: no clear spot for {n}, left out')
            continue
        _, cx, cy, box, x, y_curve, dy = best
        t.set_position(ax.transData.inverted().transform((cx, cy)))
        named_at[n] = [round(float(v), 3) for v in t.get_position()]
        if abs(dy) > 0.8:                                                 # a name set off its curve gets a leader
            edge = ax.transData.inverted().transform((cx, cy - np.sign(dy) * (bb.height / 2 + clearance)))[1]
            ax.plot([x, x], [edge, y_curve], color=name_colour(style[n][0]), lw=pt(0.5), zorder=4)
        gap = int(2 * clearance)                                          # keep names apart from each other
        ink[max(box[1] - gap, 0):box[3] + gap, max(box[0] - gap, 0):box[2] + gap] = True

    fig.canvas.draw()
    save_tiff(fig, folder / f'{name}.tiff', PRINT_DPI * scale, t0, bbox_inches='tight', pad_inches=0.04)
    plt.close(fig)

    write_csv(folder / 'csv' / f'{name}.csv', ['pH'] + list(series), zip(pH, *series.values()))
    kind = {'--': 'dissolved, holds the ligand', '-': 'dissolved'}
    write_csv(folder / 'csv' / f'{name}_species.csv',
              ['species', 'kind', 'colour', 'line', 'width (pt, in print)', 'name at pH', 'name at log10 c'],
              [[n, 'solid phase' if n in solids else kind[style[n][1]], style[n][0],
                'dashed' if style[n][1] == '--' else 'solid', round(style[n][2] * scale, 3),
                *named_at.get(n, (None, None))] for n in series])


STRIP_L19 = dict(stem='Cu_+_Ammonia', ligand_tags=('Ammo',),
                 title='Log-concentration: Cu (0.001 M) + Ammonia (0.1 M)\n@ Eh = 0.265 V')
STRIP_L14_EDTA = dict(stem=FE_REDOX + 'EDTA', ligand_tags=('EDTA',),
                      title='Log-concentration: Fe(III) (0.001 M) + EDTA (0.005 M)')
STRIP_L14_CITRATE = dict(stem=FE_REDOX + 'Citric_acid', ligand_tags=('Citr',),
                         title='Log-concentration: Fe(III) (0.001 M) + citrate (0.005 M)')
STRIP_L17 = dict(stem=CU_REDOX + 'Zn$+2_+_Zn$+0_+_Glycine_+_Ammonia', ligand_tags=('Glyc', 'Ammo'),
                 title='Log-concentration: Cu(II), Zn(II) (0.001 M)\n+ glycine (0.01 M) + ammonia (0.1 M)')
STRIPS = {
    's6-2': [('SI_S6-2_a_EDTA', solver_dir('Opus4.7', 'L1_4_20261030', 'L1_call_01'), STRIP_L14_EDTA),
             ('SI_S6-2_b_citrate', solver_dir('Opus4.7', 'L1_4_20261030', 'L1_call_02'), STRIP_L14_CITRATE)],
    's7-3': [('SI_S7-3_Opus4.7', solver_dir('Opus4.7', 'L1_4_20261030', 'L1_call_02'), STRIP_L14_CITRATE),
             ('SI_S7-3_GPT-5.5', solver_dir('GPT-5.5', 'L1_4_20261104', 'L1_call_02'), STRIP_L14_CITRATE)],
    's7-4': [('SI_S7-4_Opus4.7', solver_dir('Opus4.7', 'L1_7_20261030'), STRIP_L17),
             ('SI_S7-4_GPT-5.5', solver_dir('GPT-5.5', 'L1_7_20261103'), STRIP_L17)],
    's7-5': [('SI_S7-5_Opus4.7', solver_dir('Opus4.7', 'L1_9_20261030'), STRIP_L19),
             ('SI_S7-5_GPT-5.5', solver_dir('GPT-5.5', 'L1_9_20261104'), STRIP_L19)],
}


def draw_strips(figure, folder):
    for name, source, job in STRIPS[figure]:
        draw_strip(source, job['stem'], folder, name, title=job['title'], ligand_tags=job['ligand_tags'])


# --------------------------------------------------------------------------------------------------------------------
# SI Fig. S7-6: Cu-ammonia speciation at fixed Eh from four runs, eight parts on identical axes
# --------------------------------------------------------------------------------------------------------------------

# The stored GPT-6 Sol run of this prompt; its three CSV files are identical to those of the run of three days
# earlier that the figure was first drawn from.
L19_RUNS = [('Opus4.7', 'L1_9_20261030'), ('Opus5.5', 'L1_9_20261105'),
            ('GPT-5.5', 'L1_9_20261104'), ('GPT-6 Sol', 'L1_9_20261110')]
# one colour per species in every part: (colour, legend label with _{subscript} and ^{superscript})
L19_SPECIES = {
    'HAmmonia+': ('#e377c2', 'NH_{4}^{+}'), 'Ammonia': ('#ff7f0e', 'NH_{3}'),
    'Cu+': ('#d4a017', 'Cu^{+}'), '[Cu(Ammo)2]+': ('#9a8c00', 'Cu(NH_{3})_{2}^{+}'), 'Cu2+': ('#2ca02c', 'Cu^{2+}'),
    '[Cu(OH)]+': ('#d62728', 'CuOH^{+}'), '[Cu2(OH)2]2+': ('#9467bd', 'Cu_{2}(OH)_{2}^{2+}'),
    '[Cu(OH)2]': ('#8c564b', 'Cu(OH)_{2}(aq)'), 'HCuO2-': ('#17becf', 'HCuO_{2}^{−}'),
    '[Cu3(OH)4]2+': ('#c5b0d5', 'Cu_{3}(OH)_{4}^{2+}'), 'CuO22-': ('#bcbd22', 'CuO_{2}^{2−}'),
    '[Cu(Ammo)4]2+': ('#6b2e2e', 'Cu(NH_{3})_{4}^{2+}'), '[Cu(Ammo)3]2+': ('#b07a7a', 'Cu(NH_{3})_{3}^{2+}'),
    '[Cu(Ammo)2]2+': ('#e3a15a', 'Cu(NH_{3})_{2}^{2+}'), '[Cu(Ammo)]2+': ('#f2c0c0', 'Cu(NH_{3})^{2+}'),
    '[(Cu2O)0.5](s)': ('#006400', 'Cu_{2}O(s)'), '[Cu(OH)2](s)': ('#8b0000', 'Cu(OH)_{2}(s)'),
}
L19_NOT_DRAWN = ('H2O', 'Cu')       # constant, and absent at every pH; the runs' own plots leave them out too
L19_DASHES = {'-': 'solid', '--': 'dash', (0, (4, 1.5)): 'long dash'}


def l19_style(species):
    if species.endswith('(s)'):
        return dict(lw=1.6, ls='-')
    if 'Ammo)' in species:
        return dict(lw=0.8, ls='--')
    if species in ('HAmmonia+', 'Ammonia'):
        return dict(lw=0.8, ls=(0, (4, 1.5)))
    return dict(lw=0.8, ls='-')


def read_columns(path):
    with open(path, encoding='utf8') as f:
        rows = list(csv.DictReader(f))
    return [float(r['pH']) for r in rows], {c: [float(r[c]) for r in rows] for c in rows[0] if c != 'pH'}


def draw_s7_6(folder):
    """Top row: fraction of total Cu (``frac_metal``), the species each run kept in its own Cu plot (the columns
    of its ``envelope_Cu`` table).  Bottom row: log concentration (``log_conc``), every species of the run.  Each
    part has the same canvas and plot area; tick labels only on the outer parts."""
    axes_w, axes_h = 6.552 / 4.42, 2.96 / 2.12
    left, right, top, bottom = 0.30, 0.08, 0.05, 0.27
    W, H = left + axes_w + right, bottom + axes_h + top
    used = []
    with plt.rc_context({'font.family': 'Arial', 'font.size': 6.5, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6,
                         'ytick.major.width': 0.6, 'mathtext.default': 'regular'}):
        for j, (model_set, run) in enumerate(L19_RUNS):
            prefix = str(solver_dir(model_set, run) / 'Cu_+_Ammonia_')
            with open(prefix + 'envelope_Cu.csv', encoding='utf8') as f:
                kept = f.readline().strip().split(',')[1:]
            pH_frac, fraction = read_columns(prefix + 'frac_metal.csv')
            pH_conc, log_conc = read_columns(prefix + 'log_conc.csv')
            for i, row in enumerate(('a_fraction', 'b_logconc')):
                t0 = time.time()
                fig = plt.figure(figsize=(W, H))
                ax = fig.add_axes([left / W, bottom / H, axes_w / W, axes_h / H])
                if i == 0:
                    x, curves = pH_frac, {sp: fraction[sp] for sp in kept}
                    ax.set_ylim(-0.01, 1.03)
                else:
                    x, curves = pH_conc, {sp: v for sp, v in log_conc.items() if sp not in L19_NOT_DRAWN}
                    ax.set_ylim(-12, 0)
                    ax.set_xlabel('pH', labelpad=1)
                for sp, values in curves.items():
                    ax.plot(x, values, color=L19_SPECIES[sp][0], **l19_style(sp))
                    used.append(sp)
                ax.set_xlim(0, 14)
                ax.set_xticks(range(0, 15, 2))
                ax.tick_params(length=2, pad=1.5, labelbottom=(i == 1), labelleft=(j == 0))
                ax.grid(alpha=0.25, lw=0.4)
                name = f'SI_S7-6_{row}_{model_set.replace(" ", "_")}'
                save_tiff(fig, folder / f'{name}.tiff', PRINT_DPI, t0)
                plt.close(fig)
                write_csv(folder / 'csv' / f'{name}.csv', ['pH'] + list(curves), zip(x, *curves.values()))
    # y axis titles of the two rows in the figure: 'Fraction of total Cu' and 'log10 [species] (mol/L)'
    write_csv(folder / 'csv' / 'SI_S7-6_legend.csv', ['species', 'legend label', 'colour', 'width (pt)', 'line'],
              [[s, L19_SPECIES[s][1], L19_SPECIES[s][0], l19_style(s)['lw'], L19_DASHES[l19_style(s)['ls']]]
               for s in L19_SPECIES if s in used])


# --------------------------------------------------------------------------------------------------------------------
# Fig. 5a,b: four metals competing for one ligand
# --------------------------------------------------------------------------------------------------------------------

F5_METALS = ['Co', 'Ni', 'Cu', 'Zn']
F5_COLOUR = {'Co': '#7F3C8D', 'Ni': '#11A579', 'Cu': '#E68310', 'Zn': '#3969AC'}
F5_TOTAL = 1e-3                                             # mol/L of each metal
F5_MAIN_GLY = {'Co': '[Co(Glyc)]+', 'Ni': '[Ni(Glyc)2]', 'Cu': '[Cu(Glyc)2]', 'Zn': '[Zn(Glyc)]+'}
F5_MAIN_EN = {'Co': '[Co(Ethy)]2+', 'Ni': '[Ni(Ethy)2]2+', 'Cu': '[Cu(Ethy)2]2+', 'Zn': '[Zn(Ethy)]2+'}
F5_AXES_W, F5_AXES_H, F5_AXES_TOP = 2.30, 2.30, 0.40      # inches; panel positions as in the published figure
F5_AXES_LEFT = {'a': 0.52, 'b': 3.90}
F5_PAGE = (7.0, 3.1)
F5_TICK_PT, F5_LABEL_PT = 7.5, 7.0
F5_LW_FREE, F5_LW_MAIN, F5_LW_SOLID = 1.5, 1.2, 3.5
F5_DASH = (0, (3, 1))


def f5_label(species):
    s = species.replace('Ethy', 'en').replace('Glyc', 'Gly').replace(' (alpha)', '')
    s = re.sub(r'\((\w+)\)(\d)', lambda m: '(%s)$_%s$' % (m.group(1), m.group(2)), s)
    s = re.sub(r'(\]|\b[A-Z][a-z]?)(\d)([+-])', lambda m: '%s$^{%s%s}$' % (m.group(1), m.group(2), m.group(3)), s)
    s = re.sub(r'(\]|\b[A-Z][a-z]?)([+-])(?=$|\s)', lambda m: '%s$^{%s}$' % (m.group(1), m.group(2)), s)
    return s


def f5_metal_count(species, metal):
    """Atoms of ``metal`` in the species (free ion 1, [Co2(OH)]3+ 2, (Cu2O)0.5 1)."""
    if species.startswith(metal) and '[' not in species:
        return 1
    m = re.search(r'\(?%s(\d*)(?:O\)0\.5)?' % metal, species)
    if not m:
        return 0
    if 'O)0.5' in species:
        return 1
    return int(m.group(1)) if m.group(1) else 1


def f5_solid_band(v):
    """Amount of a solid where it is present plus the solver grid point on each side, so the band runs down to
    zero at the next grid point instead of ending in mid-air."""
    on = v > 0
    keep = on.copy()
    keep[1:] |= on[:-1]
    keep[:-1] |= on[1:]
    return np.where(keep, v, np.nan)


class F5Panel:
    """One panel laid out in page inches (y down), every element placed explicitly."""

    def __init__(self, page, letter, xlim):
        self.page, self.xlim = page, xlim
        self.L, self.T = F5_AXES_LEFT[letter], F5_AXES_TOP

    def X(self, x):
        return self.L + (x - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * F5_AXES_W

    def Y(self, y):
        return self.T + (1 - y) * F5_AXES_H

    def line(self, points, colour, width, dash='-', alpha=None):
        xs, ys = zip(*points)
        self.page.plot(xs, ys, color=colour, lw=width, ls=dash, alpha=alpha, solid_capstyle='butt',
                       dash_capstyle='butt', solid_joinstyle='round', dash_joinstyle='round')

    def curve(self, x, y, colour, width, dash='-', alpha=None):
        """Solver grid points joined by straight segments; stretches without a value split the curve."""
        x, y = np.asarray(x, float), np.asarray(y, float)
        assert np.nanmax(y) < 1.0005 and np.nanmin(y) > -1e-6
        present = np.where(~np.isnan(y))[0]
        for part in np.split(present, np.where(np.diff(present) > 1)[0] + 1):
            if len(part) >= 2:
                self.line([(self.X(a), self.Y(min(b, 1.0))) for a, b in zip(x[part], y[part])], colour, width,
                          dash, alpha)

    def text(self, x, y, label, size, colour='#000000', ha='l', va='c', upright=True):
        if not upright:                                     # reads bottom to top, centred on (x, y)
            self.page.text(x, y, label, fontsize=size, color=colour, ha='center', va='center', rotation=90)
            return
        half = size * 1.3 / 72 / 2
        self.page.text(x, {'t': y + half, 'c': y, 'b': y - half}[va], label, fontsize=size, color=colour,
                       ha={'l': 'left', 'c': 'center', 'r': 'right'}[ha], va='center')

    def grid(self, xticks, yticks):
        for x in xticks:
            self.line([(self.X(x), self.T), (self.X(x), self.T + F5_AXES_H)], '#EBEBEB', 0.5)
        for y in yticks:
            self.line([(self.L, self.Y(y)), (self.L + F5_AXES_W, self.Y(y))], '#EBEBEB', 0.5)

    def axes(self, xticks, yticks, xlabel, ylabel):
        b = self.T + F5_AXES_H
        self.line([(self.L, self.T), (self.L, b)], '#000000', 0.8)
        self.line([(self.L, b), (self.L + F5_AXES_W, b)], '#000000', 0.8)
        tick = 3.0 / 72
        for x in xticks:
            self.line([(self.X(x), b), (self.X(x), b + tick)], '#000000', 0.6)
            self.text(self.X(x), b + tick + 0.015, '%g' % x, F5_TICK_PT, ha='c', va='t')
        for y in yticks:
            self.line([(self.L - tick, self.Y(y)), (self.L, self.Y(y))], '#000000', 0.6)
            self.text(self.L - tick - 0.025, self.Y(y), '%.1f' % y, F5_TICK_PT, ha='r', va='c')
        self.text(self.L + F5_AXES_W / 2, b + 0.19, xlabel, F5_TICK_PT, ha='c', va='t')
        self.text(self.L - 0.33, self.T + F5_AXES_H / 2, ylabel, F5_TICK_PT, upright=False)


def draw_fig5(folder):
    """(a) glycine sweep at pH 7 from the per-point solver table (log concentrations and solid amounts, turned
    into the fraction of each metal); (b) pH sweep with ethylenediamine from the run's fraction table.  For each
    metal: free ion (solid line), its main complex (dashed) and any solid holding more than 2 % of it (band)."""
    t0 = time.time()
    run = BENCHMARK / 'Opus4.7' / 'L3_5_20261030'
    with plt.rc_context({'font.family': 'Arial', 'mathtext.default': 'regular'}):
        fig = plt.figure(figsize=F5_PAGE)
        page = fig.add_axes((0, 0, 1, 1))
        page.set_xlim(0, F5_PAGE[0])
        page.set_ylim(F5_PAGE[1], 0)
        page.axis('off')
        yticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        drawn = {'a': {}, 'b': {}}          # the curves of each panel as drawn, and how each is drawn
        lines = []

        def record(panel, species, metal, curve, values, line, width):
            drawn[panel][species] = values
            lines.append([panel, species, metal, curve, F5_COLOUR[metal], line, width])

        with open(run / 'L1_call_01' / 'solver' / 'Co_+_Cu_+_Ni_+_Zn_+_Glycine_cells.csv', newline='') as f:
            rows = list(csv.reader(f))
        header, data = rows[0], np.array(rows[1:], float)
        glycine_mM = data[:, 0] * 1e3
        column = {h: j for j, h in enumerate(header)}
        fraction = {}
        for metal in F5_METALS:
            for h in header:
                if h.startswith('logc['):
                    species, amount = h[5:-1], 10 ** data[:, column[h]]
                elif h.startswith('n_s['):
                    species, amount = h[4:-1], data[:, column[h]]
                else:
                    continue
                n = f5_metal_count(species, metal) if metal in species else 0
                if n:
                    fraction[(metal, species)] = n * amount / F5_TOTAL
        a = F5Panel(page, 'a', (1, 21))
        xticks = [5, 10, 15, 20]
        a.grid(xticks, yticks)
        end_labels = []
        for metal in F5_METALS:
            free, main = fraction[(metal, metal + '2+')], fraction[(metal, F5_MAIN_GLY[metal])]
            a.curve(glycine_mM, free, F5_COLOUR[metal], F5_LW_FREE)
            a.curve(glycine_mM, main, F5_COLOUR[metal], F5_LW_MAIN, dash=F5_DASH)
            record('a', metal + '2+', metal, 'free ion', free, 'solid', F5_LW_FREE)
            record('a', F5_MAIN_GLY[metal], metal, 'main complex', main, 'dashed', F5_LW_MAIN)
            end_labels.append([free[-1], f5_label(metal + '2+'), F5_COLOUR[metal]])
            end_labels.append([main[-1], f5_label(F5_MAIN_GLY[metal]), F5_COLOUR[metal]])
        end_labels.sort(key=lambda r: r[0])
        for k in range(1, len(end_labels)):                 # labels at the right edge, pushed apart where they meet
            if end_labels[k][0] - end_labels[k - 1][0] < 0.056:
                end_labels[k][0] = end_labels[k - 1][0] + 0.056
        band_label_at = {'CuO(s)': (2.5, 0.28), 'Zn(OH)2 (alpha)': (4.3, 0.05)}     # data units, beside each band
        for (metal, species), v in fraction.items():
            if '(s)' in species or species in ('Co(OH)2', 'Ni(OH)2', 'Zn(OH)2 (alpha)', 'CuO(s)') or species == metal:
                if np.nanmax(v) > 0.02:
                    a.curve(glycine_mM, f5_solid_band(v), F5_COLOUR[metal], F5_LW_SOLID, alpha=0.55)
                    record('a', species, metal, 'solid phase', f5_solid_band(v), 'band, 55 % opaque', F5_LW_SOLID)
                    x, y = band_label_at[species]
                    a.text(a.X(x), a.Y(y), f5_label(species), F5_LABEL_PT, F5_COLOUR[metal])
        a.axes(xticks, yticks, 'total glycine (mM), pH 7, 1 mM each metal', 'fraction of metal')
        for y, label, colour in end_labels:
            a.text(a.L + F5_AXES_W + 0.04, a.Y(y), label, F5_LABEL_PT, colour)

        with open(run / 'L1_call_02' / 'solver' / 'Co_+_Cu_+_Ni_+_Zn_+_Ethylenediamine_frac_metal.csv',
                  newline='') as f:
            rows = list(csv.reader(f))
        header, data = rows[0], np.array(rows[1:], float)
        pH = data[:, 0]
        column = {h: j for j, h in enumerate(header)}
        b = F5Panel(page, 'b', (2, 12))
        xticks = [2, 4, 6, 8, 10, 12]
        b.grid(xticks, yticks)
        # label position, leader tip (data units), horizontal and vertical anchor
        complex_label_at = {'Cu': ((8.3, 0.975), None, 'l', 't'), 'Ni': ((8.1, 0.90), None, 'l', 't'),
                            'Co': ((8.3, 0.72), None, 'l', 'c'), 'Zn': ((3.25, 0.30), (7.05, 0.50), 'c', 'c')}
        for metal in F5_METALS:
            b.curve(pH, data[:, column[metal + '2+']], F5_COLOUR[metal], F5_LW_FREE)
            b.curve(pH, data[:, column[F5_MAIN_EN[metal]]], F5_COLOUR[metal], F5_LW_MAIN, dash=F5_DASH)
            record('b', metal + '2+', metal, 'free ion', data[:, column[metal + '2+']], 'solid', F5_LW_FREE)
            record('b', F5_MAIN_EN[metal], metal, 'main complex', data[:, column[F5_MAIN_EN[metal]]], 'dashed',
                   F5_LW_MAIN)
        for species, metal in (('ZnO(s)', 'Zn'), ('[Co(OH)2](s)', 'Co')):
            b.curve(pH, f5_solid_band(data[:, column[species]]), F5_COLOUR[metal], F5_LW_SOLID, alpha=0.55)
            record('b', species, metal, 'solid phase', f5_solid_band(data[:, column[species]]),
                   'band, 55 % opaque', F5_LW_SOLID)
        b.axes(xticks, yticks, 'pH, 10 mM ethylenediamine, 1 mM each metal', 'fraction of metal')
        for metal in F5_METALS:
            (x, y), tip, ha, va = complex_label_at[metal]
            if tip:
                b.line([(b.X(x + 1.15), b.Y(y + 0.02)), (b.X(tip[0]), b.Y(tip[1]))], F5_COLOUR[metal], 0.5)
            b.text(b.X(x), b.Y(y), f5_label(F5_MAIN_EN[metal]), F5_LABEL_PT, F5_COLOUR[metal], ha=ha, va=va)
        for species, metal, x in (('ZnO(s)', 'Zn', 9.45), ('[Co(OH)2](s)', 'Co', 10.75)):
            b.text(b.X(x), b.Y(0.5), f5_label(species), F5_LABEL_PT, F5_COLOUR[metal], upright=False)
        key_x, key_y = b.L + F5_AXES_W + 0.05, F5_AXES_TOP + 0.10      # line key, right of the axes
        for metal in F5_METALS:
            b.line([(key_x, key_y), (key_x + 0.16, key_y)], F5_COLOUR[metal], F5_LW_FREE)
            b.text(key_x + 0.20, key_y, f5_label(metal + '2+'), F5_LABEL_PT)
            key_y += 0.16
        key_y += 0.10
        b.line([(key_x, key_y), (key_x + 0.16, key_y)], '#000000', F5_LW_FREE)
        b.text(key_x + 0.20, key_y, 'free', F5_LABEL_PT)
        b.text(key_x + 0.20, key_y + 0.125, 'M$^{2+}$', F5_LABEL_PT)
        key_y += 0.33
        b.line([(key_x, key_y), (key_x + 0.16, key_y)], '#000000', F5_LW_MAIN, dash=F5_DASH)
        b.text(key_x + 0.20, key_y, 'dominant', F5_LABEL_PT)
        b.text(key_x + 0.20, key_y + 0.125, 'complex', F5_LABEL_PT)

        save_tiff(fig, folder / 'Fig5_ab.tiff', PRINT_DPI, t0)
        plt.close(fig)
    write_csv(folder / 'csv' / 'Fig5_a_glycine_sweep.csv', ['total glycine (mM)'] + list(drawn['a']),
              zip(glycine_mM, *drawn['a'].values()))
    write_csv(folder / 'csv' / 'Fig5_b_ethylenediamine_pH_sweep.csv', ['pH'] + list(drawn['b']),
              zip(pH, *drawn['b'].values()))
    write_csv(folder / 'csv' / 'Fig5_lines.csv',
              ['panel', 'species', 'metal', 'curve', 'colour', 'line', 'width (pt)'], lines)


# --------------------------------------------------------------------------------------------------------------------

# name on the command line: (figure, output folder, drawing function)
FIGURES = {
    'fig4': ('Fig. 4a-c', 'M_Fig4', draw_fig4),
    'fig5': ('Fig. 5a,b', 'M_Fig5', draw_fig5),
    'fig6': ('Fig. 6a,b', 'M_Fig6', lambda folder: draw_maps('fig6', folder)),
    'e5': ('Extended Data Fig. E5a-d', 'ED_Fig_E5', draw_e5),
    'e7': ('Extended Data Fig. E7a,b', 'ED_Fig_E7', lambda folder: draw_maps('e7', folder)),
    's6-1': ('SI Fig. S6-1a,b', 'SI_Fig_S6-1', lambda folder: draw_maps('s6-1', folder)),
    's6-2': ('SI Fig. S6-2a,b', 'SI_Fig_S6-2', lambda folder: draw_strips('s6-2', folder)),
    's6-3': ('SI Fig. S6-3a,b', 'SI_Fig_S6-3', lambda folder: draw_maps('s6-3', folder)),
    's7-1': ('SI Fig. S7-1', 'SI_Fig_S7-1', lambda folder: draw_maps('s7-1', folder)),
    's7-2': ('SI Fig. S7-2', 'SI_Fig_S7-2', lambda folder: draw_maps('s7-2', folder)),
    's7-3': ('SI Fig. S7-3', 'SI_Fig_S7-3', lambda folder: draw_strips('s7-3', folder)),
    's7-4': ('SI Fig. S7-4', 'SI_Fig_S7-4', lambda folder: draw_strips('s7-4', folder)),
    's7-5': ('SI Fig. S7-5', 'SI_Fig_S7-5', lambda folder: draw_strips('s7-5', folder)),
    's7-6': ('SI Fig. S7-6', 'SI_Fig_S7-6', draw_s7_6),
}


def main():
    parser = argparse.ArgumentParser(description='Redraw the data plots of the paper figures from the stored runs.')
    parser.add_argument('figures', nargs='*', metavar='figure', help='figure names (default: all); see --list')
    parser.add_argument('--out', type=Path, default=HERE / 'output',
                        help='output folder; each figure gets its own folder inside')
    parser.add_argument('--list', action='store_true', help='print the figure names and stop')
    args = parser.parse_args()
    if args.list:
        for name, (title, folder, _) in FIGURES.items():
            print(f'{name:6s}{folder + "/":14s}{title}')
        return
    chosen = [f.lower() for f in args.figures] or list(FIGURES)
    unknown = [f for f in chosen if f not in FIGURES]
    if unknown:
        parser.error('unknown figure %s; choose from %s' % (', '.join(unknown), ' '.join(FIGURES)))
    with drive_letter_paths():
        for name in chosen:
            title, folder, draw = FIGURES[name]
            print(title, flush=True)
            (args.out / folder / 'csv').mkdir(parents=True, exist_ok=True)
            draw(args.out / folder)


if __name__ == '__main__':
    main()
