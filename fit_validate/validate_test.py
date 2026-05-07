#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2023 Google LLC
# Written by Simon Glass <sjg@chromium.org>

"""Unit tests for the config validator"""

import os
import subprocess
import sys
import tempfile
import unittest

# pylint: disable=E0401
import libfdt

if __name__ == "__main__":
    # Allow 'from validate import xxx to work'
    our_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(os.path.join(our_path, '..'))

    sys.path.append(os.path.join(our_path, '/home/sglass/u/tools'))

# pylint: disable=C0413,E0401
from u_boot_pylib import tools
from fit_validate import schema
from fit_validate import fdt_validate

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
            load = <0x10000000>;
            entry = <0x10000000>;
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

# A header with hash and signature subnodes, signed with sha256+rsa2048.
SIGNED = '''/dts-v1/;

/ {
    timestamp = <123456>;
    description = "Signed image";
    #address-cells = <1>;
    images {
        image-1 {
            description = "Image description";
            arch = "arm64";
            type = "kernel";
            data = "abc";
            os = "linux";
            project = "linux";
            load = <0x10000000>;
            entry = <0x10000000>;
            hash-1 {
                algo = "sha256";
                value = [00 11 22 33];
            };
            signature-1 {
                algo = "sha256,rsa2048";
                key-name-hint = "dev";
                value = [aa bb cc dd];
                hashed-nodes = "/", "/images/image-1";
                hashed-strings = <0 0x100>;
            };
        };
    };

    configurations {
        config-1 {
            description = "Configuration description";
            firmware = "image-1";
            signature-1 {
                algo = "sha256,rsa2048";
                key-name-hint = "dev";
                value = [aa bb cc dd];
            };
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
        self.val = fdt_validate.FdtValidator(schema.get_schema(True), False)
        self.returncode = 0

    def run_test(self, dts_source, use_command_line=False, extra_options=None):
        """Run the validator with a single source file

        Args:
            dts_source (str): Device-tree source to process
            use_command_line (bool): True to run through the command-line
                interface. Otherwise the imported validator class is used
                directly. When using the command-line interface, the return
                code  is available in self.returncode, since only one test
                needs it.
            extra_options (list of str): Extra command-line arguments to pass
        """
        with tempfile.NamedTemporaryFile(suffix='.dts', delete=False) as dts:
            dts.write(dts_source.encode('utf-8'))
            dts.close()
            self.returncode = 0
            if use_command_line:
                call_args = [sys.executable, '-m', 'fit_validate.validate',
                             dts.name]
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

    def test_command_line(self):
        """Test that the command-line interface works correctly"""
        self.assertEqual([], self.run_test(HEADER, True, ['-u']))

    def test_extra(self):
        """Test complaining about extra nodes and properties"""
        result = self.run_test(HEADER + EXTRA)
        self.assertEqual(
            ["/images: Unexpected property 'extra-prop', valid list is ()",
             "/: Unexpected subnode 'wibble', valid list is (images, configurations)"],
             result)

    def test_signed_ok(self):
        """A FIT with valid hash and signature subnodes should validate"""
        self.assertEqual([], self.run_test(SIGNED))

    def test_hash_missing_algo(self):
        """A hash node missing algo should be reported"""
        bad = SIGNED.replace('                algo = "sha256";\n', '', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1/hash-1: Required property 'algo' missing",
            ], result)

    def test_hash_unknown_algo(self):
        """An unsupported hash algorithm should be reported"""
        bad = SIGNED.replace('algo = "sha256";', 'algo = "blake3";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1/hash-1: 'algo' value 'blake3' does not match "
            "pattern '^crc16-ccitt|crc32|md5|sha1|sha256|sha384|sha512$'",
            ], result)

    def test_signature_unknown_algo(self):
        """An unsupported signature algorithm should be reported"""
        bad = SIGNED.replace('"sha256,rsa2048"', '"sha256,dilithium3"', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1/signature-1: 'algo' value 'sha256,dilithium3' "
            "does not match pattern "
            "'^(sha1|sha256|sha384|sha512),(rsa\\d+|ecdsa\\d+)$'",
            ], result)

    def test_image_signature_missing_required(self):
        """An image signature missing hashed-nodes should be reported"""
        bad = SIGNED.replace(
            'hashed-nodes = "/", "/images/image-1";\n            ', '', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1/signature-1: Required property 'hashed-nodes' "
            "missing",
            ], result)

    def test_phase_value_invalid(self):
        """The phase property must be 'spl' or 'u-boot'"""
        bad = HEADER.replace(
            'type = "kernel";',
            'type = "kernel";\n            phase = "tpl";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1: 'phase' value 'tpl' is not one of the allowed "
            "values (spl, u-boot)",
            ], result)

    def test_phase_value_ok(self):
        """A correctly-spelled phase value should validate"""
        ok = HEADER.replace(
            'type = "kernel";',
            'type = "kernel";\n            phase = "spl";', 1)
        self.assertEqual([], self.run_test(ok))

    def test_data_position_satisfies_data_requirement(self):
        """An image with data-position should not require data-offset"""
        ok = HEADER.replace(
            'data = "abc";',
            'data-position = <0x80000000>;\n            data-size = <0x100>;',
            1)
        self.assertEqual([], self.run_test(ok))

    def test_fpga_requires_compatible(self):
        """type=fpga requires the compatible property"""
        bad = HEADER.replace('type = "kernel";', 'type = "fpga";', 1)
        bad = bad.replace('os = "linux";\n            ', '', 1)
        bad = bad.replace('load = <0x10000000>;\n            ', '', 1)
        bad = bad.replace('entry = <0x10000000>;\n            ', '', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1: Required property 'compatible' missing",
            ], result)

    def test_config_load_only(self):
        """A config with load-only and no firmware should validate"""
        ok = HEADER.replace(
            'firmware = "image-1";',
            'load-only;', 1)
        # firmware is required for UPL configs, so the missing-firmware
        # complaint still fires; only check that load-only itself is
        # accepted as a known property.
        result = self.run_test(ok)
        for line in result:
            self.assertNotIn('load-only', line)

    def test_config_cmdline(self):
        """A config with cmdline should validate"""
        ok = HEADER.replace(
            'firmware = "image-1";',
            'firmware = "image-1";\n            cmdline = "console=ttyS0";', 1)
        self.assertEqual([], self.run_test(ok))

    def test_config_fpga_ref(self):
        """A config's fpga property must reference an existing image"""
        bad = HEADER.replace(
            'firmware = "image-1";',
            'firmware = "image-1";\n            fpga = "missing-fpga";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/configurations/config-1: 'fpga' references missing node "
            "'/images/missing-fpga'",
            ], result)

    def test_kernel_requires_os(self):
        """type=kernel images must have an os property"""
        bad = HEADER.replace('os = "linux";\n            ', '', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1: Required property 'os' missing",
            ], result)

    def test_non_kernel_does_not_require_os(self):
        """A non-kernel image without os should validate"""
        ok = HEADER.replace('type = "kernel";', 'type = "ramdisk";', 1)
        ok = ok.replace('os = "linux";\n            ', '', 1)
        ok = ok.replace('load = <0x10000000>;\n            ', '', 1)
        ok = ok.replace('entry = <0x10000000>;\n            ', '', 1)
        self.assertEqual([], self.run_test(ok))

    def test_invalid_arch(self):
        """An arch outside the allowed set should be reported"""
        bad = HEADER.replace('arch = "arm64";', 'arch = "z80";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1: 'arch' value 'z80' is not one of the allowed "
            "values (invalid, alpha, arc, arm64, arm,",
            ], result)

    def test_invalid_compression(self):
        """A compression outside the allowed set should be reported"""
        bad = HEADER.replace(
            'type = "kernel";',
            'type = "kernel";\n            compression = "snappy";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/images/image-1: 'compression' value 'snappy' is not one of "
            "the allowed values (none, bzip2, gzip, lz4, lzma, lzo, zstd)",
            ], result)

    def test_root_description_optional(self):
        """The spec says root description is optional"""
        ok = HEADER.replace(
            'description = "This is my description";\n    ', '', 1)
        self.assertEqual([], self.run_test(ok))

    def test_default_references_missing_config(self):
        """`default` must name an existing configuration"""
        bad = HEADER.replace(
            'configurations {',
            'configurations {\n        default = "missing-conf";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/configurations: 'default' references missing node "
            "'/configurations/missing-conf'",
            ], result)

    def test_firmware_references_missing_image(self):
        """A config's `firmware` must name an existing image"""
        bad = HEADER.replace('firmware = "image-1"',
                             'firmware = "ghost-image"', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/configurations/config-1: 'firmware' references missing node "
            "'/images/ghost-image'",
            ], result)

    def test_loadables_references_missing_image(self):
        """A config's `loadables` items must each name an existing image"""
        bad = HEADER.replace(
            'firmware = "image-1";',
            'firmware = "image-1";\n            '
            'loadables = "image-1", "missing-1", "missing-2";', 1)
        result = self.run_test(bad)
        self._check_all_in([
            "/configurations/config-1: 'loadables' references missing image "
            "'missing-1'",
            "/configurations/config-1: 'loadables' references missing image "
            "'missing-2'",
            ], result)

    def test_image_data_no_chain(self):
        """image-data target must not itself have image-data"""
        chained = HEADER.replace(
            'image-1 {',
            '''image-2 {
            description = "Chain target";
            arch = "arm64";
            type = "ramdisk";
            project = "linux";
            image-data = "image-1";
        };

        image-1 {''', 1).replace(
            'data = "abc";',
            'image-data = "image-2";', 1)
        result = self.run_test(chained)
        self._check_all_in([
            "/images/image-2: 'image-data' target 'image-1' itself has a "
            "'image-data' property; chains are not permitted",
            "/images/image-1: 'image-data' target 'image-2' itself has a "
            "'image-data' property; chains are not permitted",
            ], result)

    def test_whitespace_in_prop_name(self):
        """Test that trailing/leading whitespace in property names is reported

        Some FIT producers emit property names with stray whitespace (for
        example by splitting a DTS-like ``name  = "value"`` line on ``=``
        without strip()-ing the LHS). A binary FIT carries those names
        verbatim, so the validator should flag the malformed name rather than
        report a generic 'Unexpected property' error.
        """
        fdt = libfdt.Fdt.create_empty_tree(1024)
        fdt.setprop_u32(0, '#address-cells', 1)
        fdt.setprop_u32(0, 'timestamp', 123456)
        fdt.setprop_str(0, 'description', 'desc')
        fdt.setprop_u32(0, 'description ', 0)  # trailing space, matches schema
        fdt.setprop_str(0, 'oddprop ', 'x')    # trailing space, no schema match
        with tempfile.NamedTemporaryFile(suffix='.fit', delete=False) as fit:
            fit.write(bytes(fdt.as_bytearray()))
            fit.close()
            tools.prepare_output_dir(None)
            errors = self.val.start(fit.name)
            tools.finalise_output_dir()
            os.unlink(fit.name)
        self.assertIn(
            "/: Property name 'description ' has surrounding whitespace; "
            "check the tool that produced this FIT (did you mean "
            "'description'?)",
            errors)
        self.assertIn(
            "/: Property name 'oddprop ' has surrounding whitespace; "
            "check the tool that produced this FIT",
            errors)


if __name__ == '__main__':
    unittest.main(module=__name__)
