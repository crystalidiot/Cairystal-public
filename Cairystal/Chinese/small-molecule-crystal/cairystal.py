"""One portable entry point. Existing scripts/toolbox.py remains compatible."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'scripts'))
from toolbox import main
if __name__ == '__main__':
    raise SystemExit(main())
