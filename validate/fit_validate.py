#!/usr/bin/env python3
# SPDX-License-Identifier: Apache License 2.0
#
# Copyright 2023 Google LLC
# Written by Simon Glass <sjg@chromium.org>

"""Flat Image Tree (FIT) validator

This does not use dtschema, at least for now, since:

- it does not have bindings for FIT
- the errors dtschema shows when things go wrong are verbose and confusing
- the dtschema validation is not powerful enough for checking configurations and
  other relations between nodes
"""

import argparse
import os
import sys

if __name__ == "__main__":
    # Allow 'from validate import xxx to work'
    our_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(os.path.join(our_path, '..'))

# pylint: disable=C0413
from u_boot_pylib import tools
from validate import schema
from validate import fdt_validate

def parse_args(argv):
    """Parse arguments to the program

    Args:
        argv (list of str): List of arguments to parse (without argv[0])

    Returns:
        Namespace: Parsed arguments
    """
    epilog = 'Validate Flat Image Tree (FIT) files'
    parser = argparse.ArgumentParser(epilog=epilog)
    parser.add_argument('-r', '--raise-on-error', action='store_true',
                        help='Causes the validator to raise on the first ' +
                             'error it finds. This is useful for debugging.')
    parser.add_argument('files', type=str, nargs='*', help='Files to validate')
    # parser.add_argument('-U', '--show-environment', action='store_true',
          # default=False, help='Show environment changes in summary')

    return parser.parse_args(argv)

def show_errors(fname, errors):
    """Show validation errors

    Args:
        fname: Filename containng the errors
        errors: List of errors, each a string
    """
    print(f'{fname}:', file=sys.stderr)
    for error in errors:
        print(error, file=sys.stderr)
    print(file=sys.stderr)


def run_fit_validate(argv=None):
    """Main program for FIT validator

    This validates each of the provided files and prints the errors for each, if
    any.

    Args:
      argv: Arguments to the problem (excluding argv[0]); if None, uses sys.argv
    """
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    tools.prepare_output_dir(None)
    validator = fdt_validate.FdtValidator(schema.SCHEMA, args.raise_on_error)
    found_errors = False
    try:
        for fname in args.files:
            errors = validator.start(fname)
            if errors:
                found_errors = True
            if errors:
                show_errors(fname, errors)
                found_errors = True
    except ValueError as exc:
        if args.debug:
            raise
        print(f'Failed: {exc}', file=sys.stderr)
        found_errors = True
    tools.finalise_output_dir()
    if found_errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_fit_validate())
