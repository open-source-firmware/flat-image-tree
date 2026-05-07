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

from fit_validate.elements import NodeConfig, NodeDesc, NodeHash, NodeImage
from fit_validate.elements import NodeSignature
from fit_validate.elements import PropAddressCells, PropBool, PropBytes
from fit_validate.elements import PropConfigRef, PropDesc, PropImageRef
from fit_validate.elements import PropImageRefList, PropInt, PropString
from fit_validate.elements import PropStringList, PropTimestamp


# Hash algorithms accepted on a hash-N node (chapter 5, Hash nodes).
HASH_ALGO = r'crc16-ccitt|crc32|md5|sha1|sha256|sha384|sha512'

# Signature algorithms are a composite '<hash>,<signing>' string (chapter 5,
# Image-signature nodes). The spec lists explicit combinations but explains
# that any hash may be paired with any signing algorithm, so allow any
# rsaNNNN or ecdsaNNNN paired with one of the supported hashes.
SIGNATURE_ALGO = r'(sha1|sha256|sha384|sha512),(rsa\d+|ecdsa\d+)'

# Padding modes for signature nodes.
SIGNATURE_PADDING = r'pkcs-1\.5|pss'


def _hash_node():
    """Build a hash-N node schema element"""
    return NodeHash(elements=[
        PropString('algo', True, str_pattern=HASH_ALGO),
        PropBytes('value', True),
    ])


def _image_signature_node():
    """Build a signature-N schema element for use under an image node

    Per the spec, in a fully-signed image these properties are mandatory:
    algo, key-name-hint, value, hashed-nodes, hashed-strings.
    """
    return NodeSignature(elements=[
        PropString('algo', True, str_pattern=SIGNATURE_ALGO),
        PropString('key-name-hint', True),
        PropBytes('value', True),
        PropStringList('hashed-nodes', True),
        PropBytes('hashed-strings', True),
        PropImageRefList('sign-images'),
        PropTimestamp('timestamp'),
        PropString('signer-name'),
        PropString('signer-version'),
        PropString('comment'),
        PropString('padding', str_pattern=SIGNATURE_PADDING),
    ])


def _config_signature_node():
    """Build a signature-N schema element for use under a config node

    Per the spec, in a fully-signed config only algo, key-name-hint and
    value are mandatory; sign-images and hashed-strings are optional.
    """
    return NodeSignature(elements=[
        PropString('algo', True, str_pattern=SIGNATURE_ALGO),
        PropString('key-name-hint', True),
        PropBytes('value', True),
        PropImageRefList('sign-images'),
        PropBytes('hashed-strings'),
        PropTimestamp('timestamp'),
        PropString('signer-name'),
        PropString('signer-version'),
        PropString('comment'),
        PropString('padding', str_pattern=SIGNATURE_PADDING),
    ])


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
        PropInt('data-offset', True, conditional_props={
            'data': False, 'image-data': False}),
        PropInt('data-size', True, conditional_props={
            'data': False, 'image-data': False}),
        PropDesc('data', True, conditional_props={
            'data-offset': False, 'data-size': False, 'image-data': False}),
        PropImageRef('image-data', no_chain=True),
        PropString('os', True),
        PropInt('load'),
        PropStringList('capabilities'),
        PropString('producer'),
        PropInt('uncomp-size'),
        PropInt('entry-start', False),
        PropInt('entry', False),
        PropInt('reloc-start', False),
        _hash_node(),
        _image_signature_node(),
    ])

    node_config = NodeConfig(r'config-\d+' if upl else r'conf-\d+', elements=[
        PropString('description', True),
        PropImageRef('fdt'),
        PropImageRefList('loadables'),
        PropStringList('compatible'),
        PropBool('require-fit'),
        _config_signature_node(),
    ])

    schema = NodeDesc('/', True, [
        PropTimestamp('timestamp', True),
        PropString('description', True),
        PropAddressCells(True),
        NodeDesc('images', True, [
            node_image,
        ]),
        NodeDesc('configurations', True, [
            PropConfigRef('default'),
            node_config,
        ]),
    ])

    # Tweak the base schema as needed for UPL/vanilla variants
    if upl:
        node_image.add_element(PropString('project', True))
        node_config.add_element(PropImageRef('firmware', True))
    else:
        node_config.add_element(PropImageRef('kernel', True))
        node_config.add_element(PropImageRef('ramdisk'))

    return schema
