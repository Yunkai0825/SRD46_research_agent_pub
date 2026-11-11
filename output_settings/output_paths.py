"""Local SRD-46 output paths; no account names participate in routing."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
OUTPUT_ROOT = Path(os.environ.get('SRD46_OUTPUT_ROOT', str(ROOT / '_output')))
BENCHMARK_ROOT = ROOT / '_benchmark'
BENCHMARK_BUCKET = 'Benchmark'
GUEST_BUCKET = 'local'
DB_SRD46 = 'SRD46'
DIAGNOSTICS_DIRNAME = 'Diagnostics'
QUERY_OUTPUT_DIRNAME = '_output'
BUILD_DIRNAME = '_build'
POSTEVAL_STATS_BUILD_DIRNAME = 'posteval'
ORCHESTRATOR_MANIFEST_FILENAME = 'orchestrator_manifest.json'
SRD46_REPO_ROOT = ROOT / 'SRD46_research_agent'
SRD46_QUERY_AGENT_ROOT = SRD46_REPO_ROOT / 'NIST_SRD46_db_agent/NIST_SRD46_query_agent'
SRD46_ANALYSIS_AGENT_ROOT = SRD46_REPO_ROOT / 'NIST_SRD46_db_agent/NIST_SRD46_analysis_agent'
SRD46_ANALYSIS_PROMPTS_FILE = SRD46_ANALYSIS_AGENT_ROOT / '_DEBUG_input/TEST_PROMPTS.md'
_account = ContextVar('srd46_live_api_account', default=None)

def current_bucket():
    return 'local'

def active_bucket():
    return current_bucket()

def active_username():
    return current_bucket()

def get_username():
    return current_bucket()

def is_benchmark_bucket(bucket=None):
    return bucket == BENCHMARK_BUCKET

def srd46_analysis_dir(*, bucket=None, stored=True, **kwargs):
    return BENCHMARK_ROOT if is_benchmark_bucket(bucket) else OUTPUT_ROOT if stored else OUTPUT_ROOT / '_Temp'

def iter_srd46_analysis_roots(*, include_benchmark=True, include_temp=False, user_only=False, **kwargs):
    rows = [{'path': OUTPUT_ROOT, 'bucket': 'local', 'stored': True}]
    if include_temp:
        rows.append({'path': OUTPUT_ROOT / '_Temp', 'bucket': 'local', 'stored': False})
    if include_benchmark and not user_only:
        rows.append({'path': BENCHMARK_ROOT, 'bucket': BENCHMARK_BUCKET, 'stored': True})
    return rows

def srd46_query_roots(*, bucket=None, stored=True, **kwargs):
    root = (BENCHMARK_ROOT if is_benchmark_bucket(bucket) else OUTPUT_ROOT) / 'Query'
    if not stored:
        root = root / '_Temp'
    return root / '_output', root / '_output_eval'

def iter_srd46_query_root_pairs(*, include_benchmark=True, include_temp=False, user_only=False, **kwargs):
    rows = [srd46_query_roots()]
    if include_temp:
        rows.append(srd46_query_roots(stored=False))
    if include_benchmark and not user_only:
        rows.append(srd46_query_roots(bucket=BENCHMARK_BUCKET))
    return rows

def diagnostic_dir(database=None, agent=None, name=None, *, bucket=None, **kwargs):
    return srd46_analysis_dir(bucket=bucket) / DIAGNOSTICS_DIRNAME

def ensure_benchmark_seeded():
    return None

def is_benchmark_path(path):
    return Path(path).resolve().is_relative_to(BENCHMARK_ROOT.resolve())

def srd46_query_eval_stats_root(**kwargs):
    return srd46_query_roots(**kwargs)[1] / '_eval_stats'

def srd46_query_tool_stats_root(**kwargs):
    return srd46_query_eval_stats_root(**kwargs) / 'tool_stats'

def srd46_query_posteval_stats_root(**kwargs):
    return srd46_query_eval_stats_root(**kwargs) / 'posteval_stats'

def srd46_query_posteval_build_root(**kwargs):
    return srd46_query_eval_stats_root(**kwargs) / BUILD_DIRNAME / POSTEVAL_STATS_BUILD_DIRNAME

def srd46_query_enrichment_cache_root(**kwargs):
    return srd46_query_roots(**kwargs)[1] / '_cache' / 'enrichment'

def srd46_query_orchestrator_manifest_path(**kwargs):
    return srd46_query_eval_stats_root(**kwargs) / BUILD_DIRNAME / ORCHESTRATOR_MANIFEST_FILENAME

def argo_api_user():
    return _account.get()

@contextmanager
def argo_api_user_scope(user):
    token = _account.set(user)
    try:
        yield
    finally:
        _account.reset(token)
