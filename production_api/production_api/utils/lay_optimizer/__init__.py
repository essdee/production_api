"""
Lay Planning Optimizer for Essdee MRP
======================================

Package for optimizing cutting lay plans across multiple strategies.

Usage (Python API):
    from lay_optimizer import optimize_lay_plan, optimize_all_strategies

    result = optimize_lay_plan(order, max_plies, max_pieces, strategy="ilp")
    results, failed = optimize_all_strategies(order, max_plies, max_pieces)

Author: VETRI (Essdee Production Intelligence)
Version: 3.0.0
Date: 2026-03-30
"""

from .core import (
    optimize_lay_plan,
    optimize_all_strategies,
)
from .display import print_plan, print_comparison

__version__ = "3.0.0"
__all__ = [
    "optimize_lay_plan",
    "optimize_all_strategies",
    "print_plan",
    "print_comparison",
]
