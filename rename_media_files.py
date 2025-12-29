#!/usr/bin/env python3
"""
Wrapper script for media renamer.
"""

import subprocess
import sys

# Run module from src directory
result = subprocess.run([sys.executable, "src/rename_media_files.py"] + sys.argv[1:])

sys.exit(result.returncode)
