"""health_check_helper — pre-flight validation for tool + compactor catalogs."""

from .heath_check_tools_compactors_catalogs import (
    run_health_check,
    CatalogHealthCheckError,
)

__all__ = ["run_health_check", "CatalogHealthCheckError"]
