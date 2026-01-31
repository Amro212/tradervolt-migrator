#!/usr/bin/env python3
"""
TraderVolt Migrator - GUI Launcher

Launches the Windows desktop interface for the migration tool.
"""

import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.gui.app import main

if __name__ == '__main__':
    main()
