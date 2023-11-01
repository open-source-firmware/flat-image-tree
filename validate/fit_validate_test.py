#!/usr/bin/env python3
# SPDX-License-Identifier: Apache License 2.0
#
# Copyright 2023 Google LLC
# Written by Simon Glass <sjg@chromium.org>

"""Unit tests for the config validator"""

import os
import subprocess
import sys
import tempfile
import unittest

if __name__ == "__main__":
    # Allow 'from validate import xxx to work'
    our_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(os.path.join(our_path, '..'))

# pylint: disable=C0413
from u_boot_pylib import tools
from validate import schema
from validate import fdt_validate

HEADER = '''/dts-v1/;

/ {
    timestamp = <123456>;
    description = "This is my description";
    #address-cells = <1>;
    images {
        image-1 {
            description = "Image description";
            arch = "arm64";
            type = "kernel";
            data = "abc";
            os = "linux";
            project = "linux";
        };
    };

    configurations {
        config-1 {
            description = "Configuration description";
            firmware = "image-1";
        };
    };
};
'''

EXTRA = '''
/ {
    wibble {
        something;
    };

    images {
        extra-prop;
    };
};
'''

class UnitTests(unittest.TestCase):
    """Unit tests for FdtValidator

    Properties:
        val: Validator to use
        returncode: Holds the return code for the case where the validator is
            called through its command-line interface
    """
    def setUp(self):
        self.val = fdt_validate.FdtValidator(schema.SCHEMA, False)
        self.returncode = 0

    def run_test(self, dts_source, use_command_line=False, extra_options=None):
        """Run the validator with a single source file

        Args:
            dts_source: String containing the device-tree source to process
            use_command_line: True to run through the command-line interface.
                Otherwise the imported validator class is used directly. When using
                the command-line interface, the return code is available in
                self.returncode, since only one test needs it.
            extra_options: Extra command-line arguments to pass
        """
        with tempfile.NamedTemporaryFile(suffix='.dts', delete=False) as dts:
            dts.write(dts_source.encode('utf-8'))
            dts.close()
            self.returncode = 0
            if use_command_line:
                call_args = ['python', '-m', 'validate.fit_validate', dts.name]
                if extra_options:
                    call_args += extra_options
                try:
                    output = subprocess.check_output(call_args,
                                                    stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as exc:
                    output = exc.output
                    self.returncode = exc.returncode
                errors = output.strip().splitlines()
            else:
                tools.prepare_output_dir(None)
                errors = self.val.start(dts.name)
                tools.finalise_output_dir()
            if errors:
                return errors
            os.unlink(dts.name)
        return []

    def _check_all_in(self, err_msg_list, result_lines):
        """Check that the given messages appear in the validation result

        All messages must appear, and all lines must be matches.

        Args:
            result_lines: List of validation results to check, each a string
            err_msg_list: List of error messages to check for
        """
        err_msg_set = set(err_msg_list)
        for line in result_lines:
            found = False
            for err_msg in err_msg_set:
                if err_msg in line:
                    err_msg_set.remove(err_msg)
                    found = True
                    break
            if not found:
                self.fail(f'Found unexpected result: {line}')
        if err_msg_set:
            self.fail("Expected '%s'\n but not found in result: %s" %
                                (err_msg_set.pop(), '\n'.join(result_lines)))

    def test_base(self):
        """Test a skeleton file"""
        self.assertEqual([], self.run_test(HEADER))

    def test_missing(self):
        """Test complaining about missing properties"""
        lines = [line for line in HEADER.splitlines()
                 if 'project' not in line and 'firmware' not in line]
        missing_dt = '\n'.join(lines)
        result = self.run_test(missing_dt)
        self._check_all_in([
                "/images/image-1: Required property 'project' missing",
                "/configurations/config-1: Required property 'firmware' missing",
                ], result)

    def test_comannd_line(self):
        """Test that the command-line interface works correctly"""
        self.assertEqual([], self.run_test(HEADER, True))

    def test_extra(self):
        """Test complaining about extra nodes and properties"""
        result = self.run_test(HEADER + EXTRA)
        self.assertEqual(
            ["/images: Unexpected property 'extra-prop', valid list is ()",
             "/: Unexpected subnode 'wibble', valid list is (images, configurations)"],
             result)


if __name__ == '__main__':
    unittest.main(module=__name__)
