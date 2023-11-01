# SPDX-License-Identifier: Apache License 2.0
#
# Copyright 2023 Google LLC
# Written by Simon Glass <sjg@chromium.org>

"""Validates a given devicetree

This enforces various rules defined by the schema. Some of these are fairly
simple (the valid properties and subnodes for each node, the allowable values
for properties) and some are more complex (where phandles are allowed to point).

The schema is defined by Python objects containing variable SchemaElement
subclasses. Each subclass defines how the devicetree property is validated.
For strings this is via a regex. Phandles properties are validated by the
target they are expected to point to.

Schema elements can be optional or required. Optional elements will not cause
a failure if the node does not include them.

The presence or absence of a particular schema element can also be controlled
by a 'conditional_props' option. This lists elements that must (or must not)
be present in the node for this element to be present. This provides some
flexibility where the schema for a node has two options, for example, where
the presence of one element conflicts with the presence of others.

Unit tests can be run like this:

    python validate_config_unittest.py
"""

import os

from dtoc import fdt, fdt_util
from validate.elements import NodeAny, NodeDesc
from validate.elements import PropAny, PropDesc

class FdtValidator():
    """Validator for the master configuration"""
    def __init__(self, schema, raise_on_error):
        """Master configuration validator.

        Properties:
            _errors: List of validation errors detected (each a string)
            _fdt: fdt.Fdt object containing device tree to validate
            _raise_on_error: True if the validator should raise on the first error
                    (useful for debugging)
            model_list: List of model names found in the config
            submodel_list: Dict of submodel names found in the config:
                    key: Model name
                    value: List of submodel names
        """
        self._errors = []
        self._fdt = None
        self._raise_on_error = raise_on_error
        self._schema = schema

        # This iniital value matches the standard schema object. This is
        # overwritten by the real model list by Start().
        self.model_list = ['MODEL']
        self.submodel_list = {}

    def fail(self, location, msg):
        """Record a validation failure

        Args:
            location: fdt.Node object where the error occurred
            msg: Message to record for this failure
        """
        self._errors.append(f'{location}: {msg}')
        if self._raise_on_error:
            raise ValueError(self._errors[-1])

    @staticmethod
    def _is_builtin_property(node, prop_name):
        """Checks if a property is a built-in device-tree construct

        This checks for 'reg', '#address-cells' and '#size-cells' properties which
        are valid when correctly used in a device-tree context.

        Args:
            node: fdt.Node where the property appears
            prop_name: Name of the property

        Returns:
            True if this property is a built-in property and does not have to be
            covered by the schema
        """
        if prop_name == 'reg' and '@' in node.name:
            return True
        if prop_name in ['#address-cells', '#size-cells']:
            for subnode in node.subnodes:
                if '@' in subnode.name:
                    return True
        return False

    @staticmethod
    def element_present(schema, parent_node):
        """Check whether a schema element should be present

        This handles the conditional_props feature. The list of names of sibling
        nodes/properties that are actually present is checked to see if any of them
        conflict with the conditional properties for this node. If there is a
        conflict, then this element is considered to be absent.

        Args:
            schema: Schema element to check
            parent_node: Parent fdt.Node containing this schema element (or None if
                    this is not known)

        Returns:
            True if this element is present, False if absent
        """
        if schema.conditional_props and parent_node:
            for rel_name, value in schema.conditional_props.items():
                name = rel_name
                schema_target = schema.parent
                node_target = parent_node
                while name.startswith('../'):
                    schema_target = schema_target.parent
                    node_target = node_target.parent
                    name = name[3:]
                parent_props = [e.name for e in schema_target.elements]
                sibling_names = set(node_target.props.keys())
                sibling_names |= set(n.name for n in node_target.subnodes)
                if name in parent_props and value != (name in sibling_names):
                    return False
        return True

    def get_element(self, schema, name, node, expected=None):
        """Get an element from the schema by name

        Args:
            schema: Schema element to check
            name: Name of element to find (string)
            node: Node containing the property (or for nodes, the parent node
                containing the subnode) we are looking up. None if none
                available
            expected: The SchemaElement object that is expected. This can be
                NodeDesc if a node is expected, PropDesc if a property is
                expected, or None if either is fine.

        Returns:
            Tuple:
                Schema for the node, or None if none found
                True if the node should have schema, False if it can be ignored
                    (because it is internal to the device-tree format)
        """
        for element in schema.elements:
            if not self.element_present(element, node):
                continue
            if element.name == name:
                return element, True
            if ((expected is None or expected == NodeDesc) and
                        isinstance(element, NodeAny)):
                return element, True
            if ((expected is None or expected == PropDesc) and
                        isinstance(element, PropAny)):
                return element, True
        if expected == PropDesc:
            if name == 'linux,phandle' or self._is_builtin_property(node, name):
                return None, False
        return None, True

    def get_element_by_path(self, path):
        """Find a schema element given its full path

        Args:
            path: Full path to look up (e.g. '/chromeos/models/MODEL/thermal/dptf-dv')

        Returns:
            SchemaElement object for that path

        Raises:
            AttributeError if not found
        """
        parts = path.split('/')[1:]
        schema = self._schema
        for part in parts:
            element, _ = self.get_element(schema, part, None)
            schema = element
        return schema

    def _validate_schema(self, node, schema):
        """Simple validation of properties.

        This only handles simple mistakes like getting the name wrong. It
        cannot handle relationships between different properties.

        Args:
            node: fdt.Node where the property appears
            schema: NodeDesc containing schema for this node
        """
        schema.validate(self, node)
        schema_props = [e.name for e in schema.elements
                                        if isinstance(e, PropDesc) and
                                        self.element_present(e, node)]

        # Validate each property and check that there are no extra properties not
        # mentioned in the schema.
        for prop_name in node.props.keys():
            if prop_name == 'linux,phandle':    # Ignore this (use 'phandle' instead)
                continue
            element, _ = self.get_element(schema, prop_name, node, PropDesc)
            if not element or not isinstance(element, PropDesc):
                if prop_name == 'phandle':
                    self.fail(node.path, 'phandle target not valid for this node')
                elif not self._is_builtin_property(node, prop_name):
                    self.fail(
                        node.path,
                        f"Unexpected property '{prop_name}', valid list is "
                        f"({', '.join(schema_props)})")
                continue
            element.validate(self, node.props[prop_name])

        # Check that there are no required properties which we don't have
        for element in schema.elements:
            if (not isinstance(element, PropDesc) or
                    not self.element_present(element, node)):
                continue
            if element.required and element.name not in node.props.keys():
                self.fail(
                    node.path,
                    f"Required property '{element.name}' missing")

        # Check that any required subnodes are present
        subnode_names = [n.name for n in node.subnodes]
        for element in schema.elements:
            if (not isinstance(element, NodeDesc) or not element.required
                    or not self.element_present(element, node)):
                continue
            if element.name not in subnode_names:
                msg = f"Missing subnode '{element.name}'"
                if subnode_names:
                    msg += f" in {', '.join(subnode_names)}"
                self.fail(node.path, msg)

    def get_schema(self, node, parent_schema):
        """Obtain the schema for a subnode

        This finds the schema for a subnode, by scanning for a matching element.

        Args:
            node: fdt.Node whose schema we are searching for
            parent_schema: Schema for the parent node, which contains that schema

        Returns:
            Schema for the node, or None if none found
        """
        schema, needed = self.get_element(parent_schema, node.name, node.parent,
                                                                         NodeDesc)
        if not schema and needed:
            elements = [e.name for e in parent_schema.get_nodes()
                        if self.element_present(e, node.parent)]
            self.fail(os.path.dirname(node.path),
                      f"Unexpected subnode '{node.name}', valid list is "
                      f"({', '.join(elements)})")
        return schema

    def _validate_tree(self, node, parent_schema):
        """Validate a node and all its subnodes recursively

        Args:
            node: name of fdt.Node to search for
            parent_schema: Schema for the parent node
        """
        if node.name == '/':
            schema = parent_schema
        else:
            schema = self.get_schema(node, parent_schema)
            if schema is None:
                return

        self._validate_schema(node, schema)
        for subnode in node.subnodes:
            self._validate_tree(subnode, schema)

    def prepare(self, _fdt):
        """Prepare to validate"""
        self._fdt = _fdt


    def start(self, fname):
        """Start validating a master configuration file

        Args:
            fname: Filename of devicetree to validate.
                Supports compiled .dtb, source .dts and README.md (which
                has configuration source between ``` markers)

        Returns:
            list of str: List of errors found
        """
        self.model_list = []
        self.submodel_list = {}
        self._errors = []
        dtb = fdt_util.EnsureCompiled(fname)
        self.prepare(fdt.FdtScan(dtb))

        # Validate the entire master configuration
        self._validate_tree(self._fdt.GetRoot(), self._schema)
        return self._errors
