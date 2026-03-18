.. SPDX-License-Identifier: GPL-2.0+

.. _chapter-security:

Security
========

Introduction
------------

FIT has robust security features. When enabled, each FIT configuration has
one or more signatures. These protect the configuration and the images it
refers to. The bootloader must check the signatures against a public key which
it has stored elsewhere.

If any configuration fails its signature check, then it must be ignored. Images
must each include a suitable hash node, so that images are actually protected
against modification. Once each image is loaded, its hash must be computed and
checked against the hash in the FIT.

For more information on FIT security, see
`U-Boot's documentation <https://docs.u-boot.org/en/latest/usage/fit/signature.html>`_.
The mechanism is also widely covered in conference talks, some of which are
listed at `elinux.org <https://elinux.org/Boot_Loaders#U-Boot>`_.

Architecture
------------

FIT security uses a two-level scheme: image hashing and configuration signing.

Image hashing
~~~~~~~~~~~~~

Each image node contains one or more hash sub-nodes. Each hash sub-node holds
the algorithm name (e.g. ``sha256``) and the resulting digest of the image
data. The hash covers the image content only, so the loader can verify that the
image data has not been modified after the hash was computed.

Hashing alone does not provide authentication, since an attacker who can modify
the image data can also replace the hash. Authentication comes from the
configuration signature, described next.

Configuration signing
~~~~~~~~~~~~~~~~~~~~~

Each configuration node may contain one or more signature sub-nodes. A
configuration signature covers:

- the configuration node itself (including its references to images),
- each image node referenced by the configuration,
- the hash sub-nodes of those images, and
- the root (``/``) node of the FIT.

Because the signature covers the hash sub-nodes, the image data is
transitively protected: any change to the image data invalidates the hash,
and any change to the hash invalidates the configuration signature.

This design means that image data is protected without being directly included
in the configuration signature. The ``data`` property (and related properties
``data-size``, ``data-position`` and ``data-offset``) of image nodes are
explicitly excluded from the signed region, since image-data integrity is already
guaranteed by the image hash.

This two-level design has an important consequence: the same image can appear
in multiple configurations, each with its own signature, without duplicating
the image data or requiring it to be signed multiple times.

Configuration signing compared to image signing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Signing each image independently is vulnerable to a mix-and-match attack, where
an attacker combines legitimately signed images into a configuration that was
never intended. For example, an attacker could pair a signed kernel with a
different signed devicetree to change the system's behaviour, even though both
images carry valid signatures.

Configuration signing prevents this, because the signature binds a specific
set of images together. A loader that verifies the configuration signature
knows that this exact combination of images was approved by the signer.

Verification procedure
~~~~~~~~~~~~~~~~~~~~~~

The bootloader verifies a configuration as follows:

#. Locate the configuration's signature node and verify the signature against
   a trusted public key.
#. The signature covers certain FDT nodes and a region of the string table
   (see :ref:`hash_contents` below). Rebuild the list of nodes that should
   have been signed (the root node, the configuration node, each referenced
   image node and its hash sub-nodes) and verify that the hash of those nodes
   matches the signature.
#. For each image referenced by the configuration, compute the hash of the
   image data and compare it against the ``value`` in the image's hash
   sub-node. This step may be deferred until the image is actually loaded,
   which can be some time after the configuration is selected.

If any step fails, the configuration must be rejected.

.. _hash_contents:

Hash contents
-------------

This section defines exactly which bytes are included when computing the hash
for a signature. A FIT is a flattened devicetree (FDT), so the hash operates
on the FDT binary structure as defined in the Devicetree Specification
[dtspec]_.

The input to the hash is the concatenation of two regions: a set of nodes from
the FDT structure block, followed by a region of the FDT strings block.

Structure block
~~~~~~~~~~~~~~~

The signer and verifier each construct a **node list**: the set of FDT nodes
whose content is included in the hash. For a configuration signature this list
contains:

- the root (``/``) node,
- the configuration node (e.g. ``/configurations/conf-1``),
- each image node referenced by the configuration
  (e.g. ``/images/kernel``, ``/images/fdt-1``),
- the hash sub-nodes of those image nodes
  (e.g. ``/images/kernel/hash-1``, ``/images/fdt-1/hash-1``), and
- any cipher sub-nodes of those image nodes (e.g. ``/images/kernel/cipher-1``).

The signer walks the FDT structure block sequentially and includes or excludes
each token according to the following rules:

``FDT_BEGIN_NODE``
    The token and the node's unit name are included if the node or its parent
    is in the node list.

``FDT_END_NODE``
    Included under the same condition as ``FDT_BEGIN_NODE``.

``FDT_PROP``
    The token, the property length word, the string-table offset word, and the
    property data are all included if the containing node is in the node list
    **and** the property name is not one of the excluded properties: ``data``,
    ``data-size``, ``data-position`` and ``data-offset``. These are excluded
    because image-data integrity is covered by image hashes instead.

``FDT_NOP``
    Included if the containing node is in the node list.

``FDT_END``
    Always included.

Note that the "or its parent" condition in the ``FDT_BEGIN_NODE`` and
``FDT_END_NODE`` rules means that sub-nodes of listed nodes contribute their
structural tokens to the hash, even though they are not themselves in the node
list. For example, the signature sub-nodes of the configuration node have their
``FDT_BEGIN_NODE`` and ``FDT_END_NODE`` tokens included, but their properties
are excluded (since ``FDT_PROP`` requires the node itself to be in the list).

All included bytes are fed into the hash in the order they appear in the
structure block. Padding bytes that are part of the FDT token alignment are
included as they appear.

Strings block
~~~~~~~~~~~~~

The ``hashed-strings`` property in the signature node records the start offset
and size of the region of the FDT strings block that is hashed. The start is
normally 0 (the beginning of the strings block). Only property names that
are referenced by the signed nodes need to appear in this region; the signer
must ensure that the region is large enough to cover them.

After hashing the structure-block regions, the hash algorithm continues with
the strings-block region to produce the final digest.

Image hashing
~~~~~~~~~~~~~

For image hash nodes (``/images/image-name/hash-1``), the hash is computed
over the image's ``data`` property value only (i.e. the raw image content,
not any FDT metadata). The algorithm is given by the hash node's ``algo``
property and the resulting digest is stored in its ``value`` property.

Worked example
~~~~~~~~~~~~~~

This section walks through a concrete FIT to show exactly which bytes are
included in a configuration signature hash.

Source
^^^^^^

Consider the following minimal FIT source::

    / {
        description = "Example FIT";
        #address-cells = <1>;

        images {
            kernel {
                data = /incbin/("vmlinuz");
                type = "kernel";
                arch = "arm64";
                os = "linux";
                compression = "none";
                load = <0x40000000>;
                entry = <0x40000000>;
                hash-1 {
                    algo = "sha256";
                };
            };
            fdt-1 {
                data = /incbin/("board.dtb");
                type = "flat_dt";
                arch = "arm64";
                compression = "none";
                hash-1 {
                    algo = "sha256";
                };
            };
        };
        configurations {
            default = "conf-1";
            conf-1 {
                description = "Boot Linux";
                compatible = "vendor,board";
                kernel = "kernel";
                fdt = "fdt-1";
                signature-1 {
                    algo = "sha256,rsa2048";
                    key-name-hint = "dev";
                    sign-images = "kernel", "fdt";
                };
            };
        };
    };

After signing
^^^^^^^^^^^^^

During signing, the signer adds a ``value`` property to each hash node
containing the image digest, and adds ``value``, ``hashed-nodes``,
``hashed-strings`` and other properties to the signature node. The
resulting FIT looks like this::

    / {
        description = "Example FIT";
        timestamp = <0x67d96bac>;
        #address-cells = <1>;

        images {
            kernel {
                data = <...kernel data...>;
                type = "kernel";
                arch = "arm64";
                os = "linux";
                compression = "none";
                load = <0x40000000>;
                entry = <0x40000000>;
                hash-1 {
                    algo = "sha256";
                    value = <...32-byte SHA-256 digest of kernel data...>;
                };
            };
            fdt-1 {
                data = <...devicetree data...>;
                type = "flat_dt";
                arch = "arm64";
                compression = "none";
                hash-1 {
                    algo = "sha256";
                    value = <...32-byte SHA-256 digest of devicetree data...>;
                };
            };
        };
        configurations {
            default = "conf-1";
            conf-1 {
                description = "Boot Linux";
                compatible = "vendor,board";
                kernel = "kernel";
                fdt = "fdt-1";
                signature-1 {
                    algo = "sha256,rsa2048";
                    key-name-hint = "dev";
                    sign-images = "kernel", "fdt";
                    value = <...256-byte RSA-2048 signature...>;
                    hashed-nodes = "/", "/configurations/conf-1",
                        "/images/kernel", "/images/kernel/hash-1",
                        "/images/fdt-1", "/images/fdt-1/hash-1";
                    hashed-strings = <0x00000000 0x000000d4>;
                    timestamp = <0x67d96bac>;
                    signer-name = "mkimage";
                    signer-version = "2025.04-rc3";
                };
            };
        };
    };

Node list
^^^^^^^^^

For the configuration signature ``/configurations/conf-1/signature-1``, the
node list is:

- ``/``
- ``/configurations/conf-1``
- ``/images/kernel``
- ``/images/kernel/hash-1``
- ``/images/fdt-1``
- ``/images/fdt-1/hash-1``

What is hashed
^^^^^^^^^^^^^^

The following shows the signed FIT with **bold** indicating the parts that are
included in the configuration signature hash. Lines in normal weight are not
hashed. Note that node braces (``{`` and ``}``) represent ``FDT_BEGIN_NODE``
and ``FDT_END_NODE`` tokens respectively; these are included whenever the node
or its parent is in the node list.

.. parsed-literal::

   **/ {**
       **description = "Example FIT";**
       **timestamp = <0x67d96bac>;**
       **#address-cells = <1>;**

       **images {**
           **kernel {**
               data = <...kernel data...>;
               **type = "kernel";**
               **arch = "arm64";**
               **os = "linux";**
               **compression = "none";**
               **load = <0x40000000>;**
               **entry = <0x40000000>;**
               **hash-1 {**
                   **algo = "sha256";**
                   **value = <...32-byte SHA-256 digest...>;**
               **};**
           **};**
           **fdt-1 {**
               data = <...devicetree data...>;
               **type = "flat_dt";**
               **arch = "arm64";**
               **compression = "none";**
               **hash-1 {**
                   **algo = "sha256";**
                   **value = <...32-byte SHA-256 digest...>;**
               **};**
           **};**
       **};**
       **configurations {**
           default = "conf-1";
           **conf-1 {**
               **description = "Boot Linux";**
               **compatible = "vendor,board";**
               **kernel = "kernel";**
               **fdt = "fdt-1";**
               **signature-1 {**
                   algo = "sha256,rsa2048";
                   key-name-hint = "dev";
                   sign-images = "kernel", "fdt";
                   value = <...256-byte RSA-2048 signature...>;
                   hashed-nodes = "/", "/configurations/conf-1", ...;
                   hashed-strings = <0x00000000 0x000000d4>;
                   timestamp = <0x67d96bac>;
                   signer-name = "mkimage";
                   signer-version = "2025.04-rc3";
               **};**
           **};**
       **};**
   **};**

   Strings block:
   **description\\0**
   **timestamp\\0**
   **#address-cells\\0**
   **type\\0**
   **arch\\0**
   **os\\0**
   **compression\\0**
   **load\\0**
   **entry\\0**
   **algo\\0**
   **value\\0**
   **compatible\\0**
   **kernel\\0**
   **fdt\\0**
   default\\0
   padding\\0

Key points to note:

- The ``data`` properties of both image nodes are excluded since image-data
  integrity is verified separately through the hash nodes.
- The ``default`` property of the ``configurations`` node is not hashed because
  that node is not in the node list (only its parent ``/`` is). This is safe
  because the bootloader selects a configuration by its own logic, not by
  trusting the default.
- All properties of ``signature-1`` are excluded because that node is not in the
  node list. Its braces are included because its parent ``conf-1`` is. This is
  safe because the signature itself is verified against a trusted public key,
  not by hashing.
- The ``images`` and ``configurations`` nodes have no properties of their own,
  but their braces are included because their parent ``/`` is in the node list.
  This serves as a structural sanity check, ensuring that an attacker cannot
  inject unexpected nodes into the tree without detection.
- The strings-block region contains the property name strings referenced by the
  hashed nodes. Although the string-table offset in each ``FDT_PROP`` token is
  hashed, the string at that offset must also be protected; otherwise an
  attacker could rename a property (e.g. changing ``algo`` to something
  unrecognised) to trick the bootloader into skipping verification. The hashed
  region should therefore always start at offset 0.

The complete byte sequence (structure-block regions plus strings-block region)
is hashed with SHA-256. The resulting digest is then signed with the RSA-2048
private key to produce the signature ``value``.

.. sectionauthor:: Simon Glass <sjg@chromium.org>
