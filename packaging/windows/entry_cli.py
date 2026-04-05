import sys
import multiprocessing as mp
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == '__main__':
    mp.freeze_support()
    from qslmaster_cli.main import main
    main()
