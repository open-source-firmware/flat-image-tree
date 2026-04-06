.. SPDX-License-Identifier: GPL-2.0+

.. _chapter-binary-file-format:

Flattened Image Tree (FIT) Binary Format
========================================

A FIT is stored as an FDT blob.
Since a FIT and a plain devicetree share the same FDT magic number (``0xD00DFEED``),
an additional mechanism is needed to distinguish FIT images from regular devicetrees.

A possible heuristic to detect a FIT is to check for existence of
the ``/images`` and ``/configurations`` top-level device tree nodes.

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

The :index:`mkimage` tool can convert a FIT to use external data using the `-E`
argument, optionally using `-p` to specific a fixed position.

It is often desirable to align each image to a block size or cache-line size
(e.g. 512 bytes), so that there is no need to copy it to an
:index:`aligned address` when reading the image data. The mkimage tool provides
a `-B` argument to support this.


.. sectionauthor:: Ahmad Fatoum <a.fatoum@pengutronix.de>
.. sectionauthor:: External data, 25/1/16 Simon Glass <sjg@chromium.org>
