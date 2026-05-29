"""Legacy pipeline — all modules moved from src/ for architecture separation.

All imports from legacy/ are deprecated. Use the new Research OS path instead:
    from src.core.research_os import run_research_task
"""
import warnings
warnings.warn("legacy modules are deprecated — use src.core.research_os", DeprecationWarning, stacklevel=2)