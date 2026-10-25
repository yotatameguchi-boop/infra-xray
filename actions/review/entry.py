"""Run the pinned action's package, never import from the caller's checkout."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from infra_xray.ci import main
raise SystemExit(main())
