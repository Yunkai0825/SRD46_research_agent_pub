"""Native pipeline import entry for the standalone output resolver."""
import sys
from output_settings import output_paths as _paths
sys.modules[__name__] = _paths
