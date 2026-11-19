"""Test package marker.

Without this file `python -m unittest discover -s tests -t .` aborts with
"Start directory is not importable", so the suite could not be run from the
repository root -- the exact form README documents.
"""
