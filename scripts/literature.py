#!/usr/bin/env python3
"""Run the source checkout without installing the Skill globally."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from literature_workflow.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
