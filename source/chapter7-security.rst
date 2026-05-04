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
must each include a suitable hash node so that they are protected against
modification. Once each image is loaded, its hash must be computed and checked
against the hash in the FIT. The exception is ``filesystem``-type images that
carry a ``dm-verity`` node: their integrity is delegated to the kernel's
dm-verity target rather than verified by the bootloader.

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
- the hash sub-nodes of those images,
- the ``dm-verity`` sub-nodes of those images (where present), and
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
   image node, its hash sub-nodes, and any ``dm-verity`` sub-node) and verify
   that the hash of those nodes
   matches the signature.
#. For each image referenced by the configuration, compute the hash of the
   image data and compare it against the ``value`` in the image's hash
   sub-node. This step may be deferred until the image is actually loaded,
   which can be some time after the configuration is selected.

   For ``filesystem``-type images that carry a ``dm-verity`` child node and
   are being used to launch Linux, the bootloader *may* omit loading the
   image into RAM and skip this hash check entirely. Instead, the bootloader
   shall derive kernel command-line parameters from the ``dm-verity`` node as
   described in :ref:`verity-usage`, delegating integrity verification to the
   kernel's dm-verity target at mount time.

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
  (e.g. ``/images/kernel/hash-1``, ``/images/fdt-1/hash-1``),
- any cipher sub-nodes of those image nodes (e.g. ``/images/kernel/cipher-1``), and
- the ``dm-verity`` sub-node of any ``filesystem``-type image node that carries one
  (e.g. ``/images/rootfs-1/dm-verity``).

An image node is "referenced by the configuration" if it is named by
any string property of the configuration node, except for the following
properties which are excluded:

- ``description`` - textual description of the configuration,
- ``compatible`` - board compatible string(s) used for configuration
  matching, and
- ``default`` - reserved name; not used on a configuration node itself.

All other string properties are treated as image references and their
named image nodes are added to the node list. For each such property,
if no image node with the named unit name exists under ``/images``, the
property is skipped (a missing reference is not an error during node-list
construction).

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


Whole-FIT signing
-----------------

Per-configuration signing covers the integrity of one configuration and
the images it references. A FIT may additionally carry a *whole-FIT
signature* over the entire FIT image, including the FDT and any
external image data. Whole-FIT signing is intended to complement
per-configuration signing, not to replace it.

A whole-FIT signature is stored in the binary trailer (see
:ref:`chapter-binary-trailer`) as a ``signature-N`` property. The
trailer is a constrained FDT blob placed inside the main FDT but
excluded from the signed range, so its contents (including the
signatures themselves) can be modified post-signing.

Why whole-FIT signing
~~~~~~~~~~~~~~~~~~~~~

Per-configuration signing requires the bootloader to parse the FIT's
FDT before authentication: it must locate the configuration node, the
referenced image nodes, and the signature node, then construct the
node list and hash the relevant FDT structure bytes. The pre-auth
parser is therefore a full FDT parser (e.g. libfdt), which is large
and has historically been a source of bugs when fed adversarial
input.

Whole-FIT signing allows a bootloader to authenticate the FIT before
parsing any FDT structure. The verifier reads a small number of
fixed-offset fields, hashes a contiguous byte range, and checks the
signature. Only after the signature verifies does the bootloader
parse the FDT — and at that point it is operating on trusted bytes.

Bootloaders that need a smaller pre-authentication attack surface
should use whole-FIT signing. Bootloaders that already trust the FDT
parser they use may continue to use per-configuration signing alone.
A FIT may carry both, so a single image can serve both kinds of
bootloader.

What is signed
~~~~~~~~~~~~~~

A whole-FIT signature covers two byte ranges, in this order:

#. ``[0, 0x28)`` — the main FDT header (40 bytes). The trailer's fixed
   ``totalsize`` keeps every header field stable, so the entire header
   is signed without exclusions. This authenticates the FDT's
   internal layout (``totalsize``, ``off_dt_struct``, ``off_dt_strings``,
   ``off_mem_rsvmap``) as well as the external data extent
   (``boot_cpuid_phys``).
#. ``[0x28 + trailer_totalsize, totalsize + boot_cpuid_phys)`` —
   the main FDT's memreserve, structure and strings blocks, followed
   by all external image data.

The trailer itself, ``[0x28, 0x28 + trailer_totalsize)``, is excluded
so that its mutable contents (UUIDs, signatures, counters) can be
modified post-signing without invalidating the signature.

See :ref:`chapter-binary-trailer` for the byte-level details and
verification procedure.

Relationship to per-configuration signing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whole-FIT signing protects the FIT as a whole; per-configuration
signing protects each configuration individually. They are
complementary:

- A whole-FIT signature alone authenticates the FIT bytes but does
  not bind specific images to specific configurations. If the
  bootloader supports configuration selection by external means
  (e.g. board compatibility), per-configuration signing is still
  needed to prevent mix-and-match attacks within an authenticated
  FIT.
- Per-configuration signing alone provides the mix-and-match
  protection but requires a full FDT parser to be exposed to
  unauthenticated input.
- A FIT carrying both provides the strongest guarantees: the FDT is
  authenticated before it is parsed (whole-FIT) and individual
  configurations are bound to their image sets (per-configuration).

The ``compatible`` property used for configuration matching is
included in the configuration node and therefore covered by
per-configuration signing, but not by whole-FIT signing in any
distinguishing way (whole-FIT signing covers all FDT bytes
indiscriminately). This means a bootloader relying solely on
whole-FIT signing could still be tricked by attacker-modified
``compatible`` strings into selecting a different configuration than
intended. Combining the two schemes closes this gap.

Multiple signatures
~~~~~~~~~~~~~~~~~~~

The trailer can carry multiple ``signature-N`` properties for key
rotation, multi-party signing or algorithm migration. All
signatures cover the same byte ranges; they differ only in
algorithm and key. Bootloader policy determines whether a single
valid signature is sufficient or whether all must verify.

Threat model
~~~~~~~~~~~~

This subsection summarises what whole-FIT signing protects against
and what it does not, and how it compares to per-configuration
signing.

What whole-FIT signing protects against
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Tampering with FDT content.** Any modification to the main
  FDT's structure, strings or memreserve blocks changes bytes in
  the signed range, invalidating the signature.
- **Tampering with external image data.** The signed range extends
  to ``totalsize + boot_cpuid_phys``, covering all external image
  data.
- **FDT-pointer redirection.** ``totalsize``, ``off_dt_struct``,
  ``off_dt_strings`` and ``off_mem_rsvmap`` are all in the signed
  FDT header. An attacker cannot redirect an FDT consumer to parse
  attacker-controlled bytes by manipulating these fields.
- **Truncation and extension.** ``totalsize`` and
  ``boot_cpuid_phys`` are signed, so an attacker cannot shrink the
  apparent extent of the FIT to excise content from the hash, nor
  extend it to smuggle data into a verified region.
- **Bit rot in regions not covered by per-configuration signing.**
  Per-configuration signing is selective and does not hash, for
  example, configuration nodes other than the one being signed,
  unreferenced image nodes, or the FDT's strings block tail.
  Whole-FIT signing covers all of these as raw bytes.
- **Adversarial input to a full FDT parser.** A bootloader can
  verify the whole-FIT signature using only a small fixed-offset
  reader, before invoking libfdt or any equivalent. This shrinks
  the pre-authentication attack surface to the verifier itself
  plus the constrained-FDT trailer parser.

What whole-FIT signing does *not* protect against
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Mix-and-match attacks within an authenticated FIT.** Whole-FIT
  signing certifies the FDT bytes as a whole, but it does not bind
  specific images to specific configurations. A bootloader that
  verifies only the whole-FIT signature and then chooses a
  configuration based on, for example, ``compatible`` matching can
  still be tricked into selecting an attacker-favoured
  configuration if the FIT genuinely contains multiple
  configurations and the attacker controls the matching input.
  Per-configuration signing is required to prevent this.
- **Modification of the trailer.** The trailer (UUIDs, signatures,
  counters) is intentionally excluded from the signed range. An
  attacker with write access to the boot medium can modify trailer
  contents freely. Trailer values used for security-relevant
  decisions (e.g. install UUIDs influencing update targeting) shall
  be cross-checked against an authenticated source.
- **Downgrade attacks against the signing scheme itself.** If the
  bootloader policy is "verify a whole-FIT signature if one is
  present, otherwise allow the FIT to boot", an attacker can strip
  the trailer's signatures (or the trailer entirely) to bypass
  whole-FIT verification. The defence is at policy level: a
  bootloader requiring whole-FIT signing must not fall back to
  unsigned operation. ``boot_cpuid_phys`` and the FDT magic are
  both signed, so a downgrade attack must work at the policy
  layer, not the format layer.
- **Rollback and replay.** Neither whole-FIT signing nor
  per-configuration signing prevents an attacker from booting a
  previously valid (but now superseded) FIT. Anti-rollback
  requires an authenticated version counter, typically held in
  hardware (e.g. fuses) and checked by the bootloader against a
  signed version field in the FIT.
- **Compromise of the signing key.** Whole-FIT signing inherits
  the security of the signature algorithm and key management. Key
  rotation is supported via multiple ``signature-N`` properties,
  but an attacker who obtains a valid private key can produce
  authentic-looking FITs.

Comparison with per-configuration signing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

================================  =============  ===========
Threat                            Per-config     Whole-FIT
================================  =============  ===========
FDT content tampering             Selective      Yes
External image data tampering     Via hash node  Yes
Mix-and-match within FIT          Yes            No
FDT-pointer redirection           Indirect       Yes
File truncation / extension       No             Yes
Pre-auth parser attack surface    libfdt         Trivial
================================  =============  ===========

The two schemes are complementary. A FIT carrying both gets the
mix-and-match resistance of per-configuration signing and the
small pre-authentication attack surface of whole-FIT signing.

.. sectionauthor:: Simon Glass <sjg@chromium.org>
