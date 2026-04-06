.. SPDX-License-Identifier: GPL-2.0+

.. _chapter-binary-file-format:

Flattened Image Tree (FIT) Binary Format
========================================

.. _fit-magic:

FIT magic
---------

A FIT is stored as an FDT blob.
Since a FIT and a plain devicetree share the same FDT magic number (``0xD00DFEED``),
an additional mechanism is needed to distinguish FIT images from regular devicetrees.

The ``boot_cpuid_phys`` field in the FDT header
(offset ``0x1C``, as defined in the Devicetree Specification [dtspec]_)
is used for this purpose.
This field is not validated by typical FDT parsers
and is not meaningful for FIT images.
FIT generators should set ``boot_cpuid_phys`` to ``0x46495400``,
encoding the null-terminated ASCII string ``"FIT\0"``.

.. note::

  The FIT header is a late addition to the specification.
  Implementations should not reject a FIT because the magic is absent,
  to allow backward compatibility with existing FIT images that do not set it.

  For legacy FIT, a possible heuristic is to check for existence of
  the '/images' and '/configurations' top-level device tree
  nodes in the FIT.

.. _fit-header:

FIT header
----------

When the FIT magic is present in ``boot_cpuid_phys``,
a FIT header shall be placed directly after ``struct fdt_header``
(at byte offset ``0x28`` from the start of the file).
The ``struct fit_header`` has the following format:

.. table:: struct fit_header

   ======  ====  ===================  =============================================
   Offset  Size  Field                Description
   ======  ====  ===================  =============================================
   0x00    4     magic                ``"FIT\0"`` (``0x46495400``)
   0x04    4     hdr_size             Size of this header in bytes (big-endian)
   0x08    8     ext_data_size        Size of external data area (big-endian)
   0x10    4     required_flags       Required feature flags (big-endian)
   0x14    4     optional_flags       Optional feature flags (big-endian)
   ======  ====  ===================  =============================================

The ``magic`` field shall be ``0x46495400``.
It serves as a cross-check that the FIT magic in ``boot_cpuid_phys`` is intentional.
If the magic is not recognized,
implementations shall ignore the FIT header
and treat the image as a legacy FIT.

The ``hdr_size`` field gives the size of this header in bytes, including all fields.
This allows future versions to append new fields to the header.
Implementations should use this field to determine the header extent
rather than assuming a fixed size.
Implementations shall reject a FIT header with ``hdr_size`` less than 24.
Implementations shall accept a FIT header with ``hdr_size`` greater than 24
and shall ignore any trailing bytes beyond the fields they understand.
Implementations shall also verify that
``0x28 + hdr_size`` does not exceed ``fdt_header::totalsize``
to guard against integer overflow or malformed images.
The current version has ``hdr_size = 24`` (``0x18``).

The ``ext_data_size`` field is a 64-bit big-endian integer
giving the number of bytes after ``fdt_header::totalsize``
that are referenced by external data properties
('data-offset' or 'data-position').
Only the lower 48 bits are significant;
the upper 16 bits are reserved and shall be zero.
``ext_data_size`` starts counting just after ``fdt_header::totalsize``
and thus includes any alignment padding between ``totalsize``
and the first image as well as alignment padding between images.
When no external image data is present, this field only identifies padding
and may be zero.
See :ref:`fit-whole-signing` for how this field factors into the authenticated
range.

FIT producers shall ensure that ``ext_data_size`` is at least
``max(data-offset + data-size) + (ALIGN(totalsize, 4) - totalsize)``
across all image nodes that use 'data-offset'.
For image nodes that use 'data-position',
``ext_data_size`` shall be at least
``max(data-position + data-size) - totalsize``.
Both constraints apply simultaneously
so that all external image data falls within the authenticated range
when employing :ref:`fit-whole-signing`.

.. _fit-flags:

The ``required_flags`` field indicates the presence of features
that an implementation must understand in order to correctly process
the FIT image.
Implementations shall reject a FIT whose ``required_flags`` field
contains any bits they do not recognize.
This allows future versions of this specification to introduce
mandatory features in a way that older parsers cannot silently misinterpret.

.. _fit-required-flags-table:

.. table:: FIT header required flags

   ====  ========================  =============================================
   Bit   Name                      Description
   ====  ========================  =============================================
   0-31  *reserved*                Shall be zero.
   ====  ========================  =============================================

The ``optional_flags`` field indicates the presence of features
that are informational or advisory.
Implementations may ignore bits in ``optional_flags``
that they do not recognize.

.. _fit-optional-flags-table:

.. table:: FIT header optional flags

   ====  ========================  =============================================
   Bit   Name                      Description
   ====  ========================  =============================================
   0-31  *reserved*                Shall be zero.
   ====  ========================  =============================================

.. _fit-metadata:

FIT metadata
------------

Any FIT that carries the FIT magic and FIT header
shall have a metadata trailer.
The metadata trailer is a trailing region
that follows the, possibly authenticated, content of the FIT file.
It begins at file offset
``fdt_header::totalsize + fit_header::ext_data_size``
and is entirely **outside the authenticated range**.
This allows metadata entries to be added, modified, or removed at any time,
including after whole FIT signing,
without invalidating a whole-FIT signature.

The region starts with a 4-byte magic ``0x4649544D`` (ASCII ``"FITM"``)
followed by a 4-byte big-endian length field
giving the total number of bytes of metadata entries that follow the header.
An empty metadata region has a length of zero,
making its total on-disk size 8 bytes (magic + zero length).

The complete size of a FIT file is
``fdt_header::totalsize + fit_header::ext_data_size + 8 + fit_metadata::length``.

.. note::

   The metadata trailer is not covered by any whole-FIT hash
   (see :ref:`fit-whole-signing`).
   Items within the metadata trailer that require integrity
   must carry their own authentication mechanism,
   such as an embedded signature that a verifier can check
   independently of the whole-FIT hash.

.. index:: External data

.. _ExternalData:

External data
-------------

FIT is normally built initially with image data in the 'data' property of each
image node. It is also possible for this data to reside outside the FIT itself.
This allows the 'FDT' part of the FIT to be quite small, so that it can be
loaded and scanned without loading a large amount of data. Then when an image is
needed it can be loaded from an external source.

External FITs use 'data-offset' or 'data-position' instead of 'data'.

When ``data-offset`` is used, the offset is relative to the end of the FDT blob,
rounded up to a 4-byte boundary:
``(fdt_header::totalsize + 3) & ~3``.
The external data area starts at this aligned boundary,
and all ``data-offset`` values are relative to it.

The :index:`mkimage` tool can convert a FIT to use external data using the `-E`
argument, optionally using `-p` to specific a fixed position.

It is often desirable to align each image to a block size or cache-line size
(e.g. 512 bytes), so that there is no need to copy it to an
:index:`aligned address` when reading the image data. The mkimage tool provides
a `-B` argument to support this.

.. _fit-layout:

FIT file layout
---------------

The following diagram shows the layout with the current header version
(``hdr_size = 24``, placing the FDT data at offset ``0x40``).
Future header versions may extend ``hdr_size``,
which shifts the start of the FDT data accordingly.

::

    0x00             0x28                  0x40 currently
    |                |                     |
    v                v                     v
    |<---- 0x28 ---->|<- 0x28 + hdr_size ->|
    |<-------------------- totalsize ---------------->|<--- ext_data_size -->|<-- 8  -->|
    +----------------+---------------------+----------+-----+----------------+----------+
    |  fdt_header    |      fit_header     | FDT data |(pad)| external image | metadata |
    |                | .magic@0            | (memrsv, |     |      data      |          |
    | .boot_cpuid@1c | .hdr_size@4         | struct,  |     |                |          |
    | = 0x46495400   | .ext_data_size@8    | strings) |     |                |          |
    |                | ... etc.            |          |     |                |          |
    +----------------+---------------------+----------+-----+----------------+----------+
    |<--------- Authenticated Range in a Whole-FIT signing scheme ---------->|<unsigned>|

The FDT's ``off_dt_struct``, ``off_dt_strings``, and ``off_mem_rsvmap`` fields
must be set to account for the FIT header.
FIT generators should place the memory reservation map,
structure block, and strings block after the FIT header.

FIT-aware tools **shall not** use ``fdt_open_into()`` or equivalent
block-reordering operations on a FIT image.
Such operations rewrite internal offsets
so that the memory reservation map begins
immediately after ``struct fdt_header`` at offset ``0x28``,
clobbering the FIT header.
This destroys the FIT header, corrupting ``ext_data_size``
and therefore the whole-FIT signed range.

When the FIT magic is absent (legacy FIT images), there is no FIT header.
The FDT's ``totalsize`` defines the extent of the FDT blob,
and any external image data follows directly at offset ``totalsize``
as described in :ref:`ExternalData`.
Without ``ext_data_size``, implementations must parse the image nodes
and compute the maximum of ``data-offset + data-size`` across all images
to determine the full extent of external data.

.. sectionauthor:: Ahmad Fatoum <a.fatoum@pengutronix.de>
.. sectionauthor:: External data, 25/1/16 Simon Glass <sjg@chromium.org>
