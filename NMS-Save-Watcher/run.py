#!/usr/bin/env python3
"""
Direct run script for NMS Save Watcher.
Use this when running from source or after PyInstaller packaging.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == '__main__':
    main()
