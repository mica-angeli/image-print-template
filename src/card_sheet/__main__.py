"""Enable ``python -m card_sheet``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
