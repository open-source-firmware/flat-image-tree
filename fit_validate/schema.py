# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2023 Google LLC
# Written by Simon Glass <sjg@chromium.org>

"""This is the schema. It is a hierarchical set of nodes and properties, just
like the device tree. If an object subclasses NodeDesc then it is a node,
possibly with properties and subnodes.

In this way it is possible to describe the schema in a fairly natural,
hierarchical way.
"""

from fit_validate.elements import NodeDesc, NodeConfig, NodeImage
from fit_validate.elements import PropAddressCells, PropBool, PropDesc, PropInt
from fit_validate.elements import PropString, PropStringList, PropTimestamp


def get_schema(upl=False):
    """Get the schema to use

    Args:
        upl (bool): True to get the schema for Universal Payload; False to get
            the schema for FIT
    """
    node_image = NodeImage(r'image-\d+' if upl else r'[a-z-]+-\d+', elements=[
        PropString('description', True),
        PropTimestamp('timestamp'),
        PropString('arch', True),
        PropString('type', True),
        PropString('compression'),
        PropInt('data-offset', True, conditional_props={'data': False}),
        PropInt('data-size', True, conditional_props={'data': False}),
        PropDesc('data', True,
                 conditional_props={'data-offset': False,
                                    'data-size': False}),
        PropString('os', True),
        PropInt('load'),
        PropStringList('capabilities'),
        PropString('producer'),
        PropInt('uncomp-size'),
        PropInt('entry-start', False),
        PropInt('entry', False),
        PropInt('reloc-start', False),
    ])

    node_config = NodeConfig(r'config-\d+' if upl else r'conf-\d+', elements=[
        PropString('description', True),
        PropString('fdt'),  # Add
        PropStringList('loadables'),
        PropStringList('compatible'),
        PropBool('require-fit'),
    ])

    schema = NodeDesc('/', True, [
        PropTimestamp('timestamp', True),
        PropString('description', True),
        PropAddressCells(True),
        NodeDesc('images', True, [
            node_image,
        ]),
        NodeDesc('configurations', True, [
            PropString('default'),
            node_config,
        ]),
    ])

    # Tweak the base schema as needed for UPL/vanilla variants
    if upl:
        node_image.add_element(PropString('project', True))
        node_config.add_element(PropString('firmware', True))
    else:
        node_config.add_element(PropString('kernel', True))
        node_config.add_element(PropString('ramdisk'))

    return schema
