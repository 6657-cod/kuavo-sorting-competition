"""Permit source-tree unit tests without installing the ROS package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
