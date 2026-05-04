.. SPDX-License-Identifier: GPL-2.0+

.. _chapter-binary-trailer:

Binary Trailer
==============

Introduction
------------

A FIT may carry a *binary trailer* placed immediately after the
FIT's FDT header. The trailer holds data that is intentionally not
covered by FIT signatures, including:

- mutable per-installation metadata that must be updatable without
  re-signing the FIT (e.g. an installation UUID), and
- detached signatures that gate verification of the rest of the FIT
  and therefore cannot live inside the data they sign.

The trailer is a self-contained FDT blob restricted to a profile that
allows it to be parsed before authentication by a small, auditable
parser. This avoids exposing a general-purpose FDT parser to
adversarial input while reusing the FDT format for tooling and
extensibility.

The trailer is **fixed in size and position** at producer time. Its
internal contents are mutable post-signing — installation tooling
can add, remove or modify properties — but the trailer's overall
``totalsize`` does not change. This stability is what allows whole-
FIT signing to cover the FIT as a single contiguous byte range
without having to exclude any FDT header fields. Producers
pre-allocate enough trailer space (e.g. 4 KiB) to accommodate
expected modifications; the unused space is held as
:ref:`padding <trailer-padding>`.

Placing the trailer in the file prefix means a consumer can read and
validate it without seeking past the rest of the FDT or the external
image data. This is useful for streaming, network boot and A/B slot
selection, where a peek at trailer metadata may inform whether to
fetch the rest of the FIT.


Location
--------

The trailer occupies the bytes immediately after the FIT's FDT
header. For FDT version 17 (the version mandated by FIT, see
:ref:`chapter-source-file-format`) the FDT header is ``0x28`` bytes
long, so the trailer starts at file offset ``0x28``. The main FDT's
``off_mem_rsvmap``, ``off_dt_struct`` and ``off_dt_strings`` fields
all advance past the trailer so that libfdt sees a valid FDT.

This specification assumes the FDT v17 header size of ``0x28``
bytes. All references to ``0x28`` in this chapter are
``sizeof(struct fdt_header)`` for v17. If a future FDT specification
defines a larger header, this trailer scheme would need a
corresponding update; ``0x28`` is treated as a fixed constant here
to keep the pre-authentication parser simple.

A consumer locates the trailer as follows:

#. Read four bytes at offset ``0x28``. If the value is not the FDT
   magic (``0xd00dfeed``), no trailer is present.
#. Otherwise, read the trailer's own FDT header and obtain its
   ``totalsize``.
#. Verify that ``0x28 + trailer_totalsize`` is not greater than
   ``totalsize`` (the main FDT's totalsize, which encompasses the
   trailer).

The main FDT therefore looks like this:

.. code-block::

    offset 0     0x28          0x28+T                      totalsize
           |     |             |                           |
           v     v             v                           v
           [hdr] [trailer FDT] [memrsv | struct | strings]

External image data follows the main FDT, and ``boot_cpuid_phys``
in the FDT header records its size:

.. code-block::

    offset 0                 totalsize    totalsize + boot_cpuid_phys
           |                 |            |
           v                 v            v
           [main FDT, including trailer]  [external image data]

Compatibility with existing FITs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This scheme is designed to be safe to apply to any FIT:

- A pre-existing FIT (no trailer) has its memreserve block
  immediately after the FDT header at offset ``0x28``. The
  consumer reads four bytes at ``0x28``, sees the start of the
  memreserve block (which begins with the high 32 bits of an
  address — almost always zero), fails the magic check, and
  concludes correctly that no trailer is present.

- A new-style FIT carries a real trailer at ``0x28``, identified
  by FDT magic. The main FDT's ``off_mem_rsvmap`` points past the
  trailer to where the memreserve block actually begins.

A consumer that does not understand the trailer scheme parses the
FDT in the standard way using ``off_mem_rsvmap``, ``off_dt_struct``
and ``off_dt_strings``, and never inspects the bytes between the
header and the memreserve block. Such a consumer remains compatible
with FITs that carry a trailer.

Producers must update ``off_mem_rsvmap``, ``off_dt_struct`` and
``off_dt_strings`` to skip past the trailer when emitting one.
``totalsize`` must also encompass the trailer.

The trailer is **outside the signed regions of the FIT** (see
`Whole-FIT signing`_ below) and is therefore unsigned. A consumer
shall apply its own validation policy before relying on any value
read from the trailer.

External data size
~~~~~~~~~~~~~~~~~~

The ``boot_cpuid_phys`` field of the main FDT header (offset
``0x1c``, four bytes, big-endian) carries the size of the external
data region in bytes — the number of bytes after the main FDT's
``totalsize`` that contain externally stored image data. FIT does
not otherwise use this field. A FIT with no external data sets it
to zero.

This value is required for whole-FIT signing because it defines the
extent of the authenticated content. Producers that emit a
whole-FIT signature shall set ``boot_cpuid_phys`` accurately.

Because the field is 32 bits, the external data region is limited
to 4 GiB. A FIT with more than 4 GiB of external data cannot use
whole-FIT signing under this scheme. In practice this is not a
constraint, since FITs of that size are rare.


Constrained FDT profile
-----------------------

The trailer is a valid FDT but restricted to the profile defined
below. A producer that emits a trailer shall conform to this profile;
a consumer shall reject any trailer that does not.

Header
~~~~~~

- ``magic`` shall be ``0xd00dfeed``.
- ``version`` shall be ``17``.
- ``last_comp_version`` shall be ``17`` or less.
- ``totalsize`` shall be at most 65536 bytes.
- ``off_mem_rsvmap`` shall equal ``sizeof(struct fdt_header)`` (``0x28``).
- The structure block and strings block shall not overlap each other,
  the FDT header, or the memory reservation block.
- All offsets and sizes shall fit within ``totalsize``.

Memory reservation block
~~~~~~~~~~~~~~~~~~~~~~~~

The memory reservation block shall contain exactly one entry: the
16-byte all-zero terminator. The trailer shall not carry memory
reservations.

Structure block
~~~~~~~~~~~~~~~

- The trailer contains a single root node.
- The root node carries properties only. Sub-nodes are not permitted.
- The root node's unit name shall be the empty string.
- Allowed tokens are ``FDT_BEGIN_NODE``, ``FDT_END_NODE``, ``FDT_PROP``,
  ``FDT_NOP`` and ``FDT_END``.
- ``FDT_NOP`` tokens are permitted anywhere and shall be skipped by
  the parser.
- Each property name offset shall point inside the strings block and
  shall reference a null-terminated string.

Strings block
~~~~~~~~~~~~~

A standard FDT strings block. No additional constraints beyond those
implied by the property-name rule above.

Phandles, aliases, ``/chosen``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Not used. The trailer carries no nodes other than the root, so
phandle-based references are meaningless in this context.

.. _trailer-padding:

Padding for in-place modification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The trailer's ``totalsize`` is fixed at producer time and shall not
change after signing. Producers should allocate the trailer
generously to leave room for future modifications. Unused space
within the trailer takes one of two forms:

- ``FDT_NOP`` tokens at the end of the structure block. These are
  consumed by the parser as no-ops and may be replaced by
  ``FDT_PROP`` tokens when adding properties.
- Unused bytes after the strings block, before ``totalsize``.
  These accommodate growth of the strings block when new property
  names are added.

A producer that wishes to permit later in-place modification shall
ensure that both forms of padding are available. Tooling that
modifies the trailer (e.g. ``fdtput`` to stamp ``install-uuid``)
shall consume from these padding regions rather than changing
``totalsize``.

A FIT that runs out of trailer space cannot be modified in place.
Such a FIT must be reissued with a larger trailer, which requires
re-signing.


Parser requirements
-------------------

A consumer parsing the trailer before authentication shall use a
parser with the following properties:

- No dynamic memory allocation.
- No recursion.
- All offsets and lengths bounds-checked against ``totalsize``.
- A hard upper bound on input size of 65536 bytes.
- Rejects any input that violates the profile above.

A reference implementation in approximately 200 lines of C is
available; see issue #48 in the upstream repository. Implementations
are encouraged to use this or a similarly minimal parser, rather than
a general-purpose FDT library, to limit the attack surface exposed to
unauthenticated input.

A consumer that does not require trailer contents may ignore the
trailer entirely. The trailer is optional; absence is signalled by
the absence of the FDT magic at offset ``0x28``.


Producer behaviour
------------------

Producers (e.g. mkimage) shall emit trailers conforming to the
profile above. In particular, producers shall not invoke libfdt
operations that may introduce sub-nodes, memory reservations or
other features outside the profile.

When emitting a trailer, the producer shall:

- Place the trailer at file offset ``0x28``, immediately after the
  main FDT header.
- Choose a fixed trailer ``totalsize``, generous enough to
  accommodate expected post-signing modifications.
- Pad the trailer's structure and strings blocks as described in
  :ref:`trailer-padding`.
- Update the main FDT's ``totalsize`` to encompass the trailer.
- Update ``off_mem_rsvmap``, ``off_dt_struct`` and ``off_dt_strings``
  to skip past the trailer.

The trailer's ``totalsize`` shall not change after signing.

Producers shall not invoke ``fdt_open_into()`` or equivalent
operations that re-pack the main FDT, as these will overwrite the
trailer region.

Standard FDT tooling (``fdtget``, ``fdtput``, ``fdtdump``) operating
on a trailer-only FDT remains conforming as long as no sub-nodes
are added and the trailer's ``totalsize`` is preserved. ``fdtput``
operating on the trailer in place will consume padding to absorb
size changes. Installation tooling may use it to stamp values such
as ``install-uuid``.


Defined trailer properties
--------------------------

The following property names are defined by this specification.
Other property names in the trailer's root node are reserved for
future revisions; consumers shall skip unknown properties without
treating them as an error.

The ``vendor-`` prefix is reserved for vendor-defined properties
that will never be standardised by this specification.

install-uuid
    A 16-byte RFC 4122 UUID identifying a particular installation
    of this FIT on persistent storage.

    Installation tooling stamps a fresh UUID at install time. An
    all-zero value (16 bytes of ``0x00``) is the build-time
    placeholder; consumers shall treat it as if the property is
    absent.

    The value is not integrity-protected. Systems that use it for
    update-critical decisions (e.g. selecting an update target
    partition) shall cross-check it against an authenticated source.

signature-N
    An opaque byte sequence carrying a detached signature over the
    FIT's content, excluding the trailer itself. The exact byte
    ranges are defined in `Whole-FIT signing`_.

    Multiple signatures are supported via the suffix ``N``, which
    is a positive integer starting at ``1``. A FIT carrying a single
    signature uses ``signature-1``; further signatures use
    ``signature-2``, ``signature-3`` and so on. Numbers shall be
    contiguous starting from ``1``; consumers stop enumerating at
    the first missing number.

    Multiple signatures support key rotation, multi-party signing
    and algorithm migration. All signatures cover the same byte
    ranges; they differ only in algorithm and key.

    Bootloader policy determines whether one valid signature is
    sufficient (try each in turn until one succeeds) or whether all
    must verify. This is a policy decision, not a format decision.

    The signature algorithm and key for ``signature-N`` are
    determined either by consumer policy (e.g. compiled-in or
    fuse-derived) or by the companion ``signature-N-algo`` and
    ``signature-N-key-hint`` properties below.

signature-N-algo
    A null-terminated string identifying the signature algorithm
    used for ``signature-N``, e.g. ``"sha256,rsa2048"``. The syntax
    matches the per-configuration ``algo`` property defined in
    :ref:`chapter-source-file-format`.

signature-N-key-hint
    A null-terminated string identifying the public key used to
    verify ``signature-N``. The consumer maps this hint to a
    trusted public key in its key store.


Whole-FIT signing
-----------------

A whole-FIT signature stored in a ``signature-N`` property covers
everything in the FIT except the trailer's contents. The trailer's
``totalsize`` is fixed at producer time (:ref:`trailer-padding`),
so the position and extent of every other byte in the FIT are
stable. This includes the FDT header fields, which are fully signed
without exclusions.

The same signed byte range is used by every ``signature-N``
property; multiple signatures over the same content support key
rotation, multi-party signing and algorithm migration.

Signed byte ranges
~~~~~~~~~~~~~~~~~~

The signature covers two byte ranges, in this order:

#. ``[0, 0x28)`` — the FDT header (40 bytes).
#. ``[0x28 + trailer_totalsize, totalsize + boot_cpuid_phys)`` —
   the main FDT's memreserve, structure and strings blocks,
   followed by all external image data.

The hash is computed over the concatenation of these two ranges in
order. The bytes between them, ``[0x28, 0x28 + trailer_totalsize)``,
are the trailer; they are excluded from the hash so that the
trailer's contents can be modified post-signing.

Properties of the signed ranges
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- The full FDT header is signed (range 1), so an attacker cannot
  tamper with ``totalsize``, ``off_dt_struct``, ``off_dt_strings``,
  ``off_mem_rsvmap``, ``boot_cpuid_phys`` or any other header
  field. The FIT layout is fully authenticated.
- The trailer's ``totalsize`` is in the trailer's FDT header, which
  is *inside* the excluded trailer region — but it cannot be
  tampered with for an attack: changing it would shift the start
  of range 2, causing the verifier to hash different bytes than
  the signer, and the signature would fail.
- Range 2 is bounded above by ``totalsize + boot_cpuid_phys``,
  both of which are signed. An attacker cannot shrink the range to
  excise external data from the hash.

Verification procedure
~~~~~~~~~~~~~~~~~~~~~~

A verifier:

#. Reads ``trailer_totalsize`` from the trailer's FDT header
   (offset ``0x2c``).
#. Reads the main FDT's ``totalsize`` (offset ``0x4``) and
   ``boot_cpuid_phys`` (offset ``0x1c``).
#. Hashes ``[0, 0x28)`` followed by
   ``[0x28 + trailer_totalsize, totalsize + boot_cpuid_phys)``.
#. For each ``signature-N`` property in the trailer (starting at
   ``signature-1`` and stopping at the first missing number),
   verifies the hash against the signature using the algorithm and
   key indicated by ``signature-N-algo`` and ``signature-N-key-hint``
   (or by consumer policy).
#. Applies its policy: typically, accept if at least one signature
   verifies; some deployments may require all to verify.


Comparison with TLV trailer
---------------------------

An earlier proposal used a custom tag-length-value (TLV) encoding
for the trailer. The constrained-FDT trailer described here was
chosen for the following reasons:

- One format is used throughout the FIT (FDT only) rather than two
  (FDT plus TLV). There is no second tag registry to maintain and
  no second encoding to specify, implement and test.
- The pre-authentication parser is small and auditable in either
  case, but the constrained-FDT parser also doubles as the format
  consumed by standard tools, removing the need for a second
  tooling stack.
- FDT property values are limited only by the FDT format itself
  (not by a 16-bit length field), which avoids future constraints
  on signature or certificate-chain sizes.
- New trailer entries are added by defining new property names,
  using FDT's existing schema conventions, rather than by
  allocating new TLV tags.
