"""Enable `python -m subkit ...`.

README, examples/README.md and 拿来说明.md all document this invocation form.
Without this file the package imports fine but `python -m subkit` dies with
"No module named subkit.__main__" and exits 1 without printing anything --
found by running the documented command verbatim, not by reading the code.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
