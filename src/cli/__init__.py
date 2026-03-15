"""
Moduł cli - interfejsy linii poleceń
====================================
"""

from .pathfinder_cli import main as pathfinder_main
from .tsp_cli import main as tsp_main

__all__ = ["pathfinder_main", "tsp_main"]
