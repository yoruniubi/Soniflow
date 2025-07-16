import sys
import os

__all__ = ['config_manager']

if hasattr(sys, 'frozen') and sys.frozen:

    try:
        from config_manager import config_manager
    except ImportError:
        # Fallback to relative import if not found as top-level
        from .config_manager import config_manager
else:
    # For development environment, use relative import
    from .config_manager import config_manager
