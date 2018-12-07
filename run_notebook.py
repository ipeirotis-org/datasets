#!/usr/bin/python3

import sys
import os
import subprocess
import tempfile
import nbformat

from os import listdir
from os.path import isfile, join, isdir


def notebook_run(path):
    """Execute a notebook via nbconvert and collect output.
       :returns (parsed nb object, execution errors)
    """

    with tempfile.NamedTemporaryFile(suffix=".ipynb") as fout:
        args = ["jupyter", "nbconvert", "--to", "notebook", "--execute",
          "--ExecutePreprocessor.timeout=7200",
          "--output", fout.name, path]
        subprocess.check_call(args)

        fout.seek(0)
        nb = nbformat.read(fout.name, nbformat.current_nbformat)

    errors = [output for cell in nb.cells if "outputs" in cell
                     for output in cell["outputs"]\
                     if output.output_type == "error"]

    return nb, errors


def main():
    notebook = sys.argv[1]
    nb, errors = notebook_run(notebook)
    assert errors == []


if __name__ == "__main__":
    main()