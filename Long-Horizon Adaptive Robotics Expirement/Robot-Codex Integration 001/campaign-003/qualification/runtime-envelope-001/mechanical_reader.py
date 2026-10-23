"""Independently read dev011; keep its derived view beside this reader."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
import build_viewer
import qualify_audit
build_viewer.HERE=ROOT
raise SystemExit(qualify_audit.run(ROOT/'system','20261004T022323188785Z-3f50404f',ROOT/'independent-audit'))
