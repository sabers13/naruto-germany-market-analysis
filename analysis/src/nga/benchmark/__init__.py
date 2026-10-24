"""Re-export the §13 benchmark comparison API."""
from nga.benchmark.compare import (
    SOURCE_SPECS,
    compare,
    franchise_correlation,
)

__all__ = ["SOURCE_SPECS", "compare", "franchise_correlation"]
