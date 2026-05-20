.. SPDX-License-Identifier: GPL-2.0+

.. _chapter-usage:

Flattened Image Tree (FIT) Usage
================================

Introduction
------------

This section describes how FIT is typically used. This is not necessarily
proscriptive but may be useful for those implementing this specification.

Boot process
------------

At some point in the boot process, the bootloader select and boot an Operating
System. To do this, it follows these steps:

#. Load a FIT into memory
#. Select a configuration to boot
#. Load the images from the selected configuration
#. Fix up the devicetree
#. Jump to the OS

Each of these is now dealt with in turn.

Load a FIT into memory
~~~~~~~~~~~~~~~~~~~~~~

The bootloader provides a way to select a FIT to load into memory. This is
typically on boot media available to the bootloader, such as eMMC or UFS.

There may be multiple FITs available. The mechanism for locating and selecting
a FIT is not defined by this specification. See for example [VBE]_.

The bootloader may load the entire FIT into memory at once, before processing
it. For simple applications where there are just a few images, this is the
easiest approach.

Where there are many configuration and several images, such that only a subset
of the available images will actually be used on any one boot, it is inefficient
to load the entire FIT, since most of the loaded data will not be used. In this
case, an external-data FIT can be used. See :ref:`Externaldata`.

In this case, the bootloader reads the FDT header (say 64 bytes), checks that
it is valid, then reads enough more bytes to bring in ``totalsize`` bytes
(``totalsize`` is the second 32-bit word in the header). Typically this will be
a few KB of data, consisting just of the FIT metadata. Later, the bootloader can
read more data from the FIT as it needs to load each image.

Another case that sometimes comes up is loading images from a FIT into internal
SRAM, which may be very limited. In that case it may be useful to align images
on a storage-device's block boundary (see ``-B`` flag in :ref:`Externaldata`).
The bootloader can then avoid needing bounce buffers and other complications.

Select a configuration to boot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The FIT typically contains more than one configuration. It is common to use a
separate configuration for each supported model. The configuration contains
a ``compatible`` stringlist which indicates which models the configuration is
compatible with.

The bootloader itself typically has a compatible stringlist, indicating the
model that it is running on. For U-Boot this is in the root node of the
devicetree used by U-Boot, typically exactly the same devicetree as is used by
Linux for that model. For other bootloaders, the stringlist may be hard-coded,
or obtained by some other means.

The bootloader should loop through each configuration to find the best match to
its own compatible string. The best match is the configuration which matches
earliest string in the bootloader's compatible stringlist.

For example, imagine the bootloader has ``compatible = "foo,bar", "bim,bam"``
and the FIT has two configurations::

    config-1 {
        compatible = "foo,bar";
        fdt = "fdt-1";
        ...
    };
    config-2 {
        compatible = "bim,bam", "baz,biz";
        fdt = "fdt-2";
        ...
    };

Here, the bootloader chooses ``config-1`` since it is a better match. The first
string in the bootloader's compatible list, ``"foo,bar"``, matches a compatible
string in the root of ``fdt1``. Although ``"bim,bam"`` in ``fdt2`` matches the
second string, this isn't as good a match as ``fdt1``.

In U-Boot this algorithm is handled by ``fit_conf_find_compat()`` and enabled
by the ``CONFIG_FIT_BEST_MATCH`` option.

Sometime models have multiple PCB revisions or different minor variants, often
referred to as SKUs. For this reason, bootloaders may want to select
configurations in a finer-grained way. In this case, rather than using the
compatible stringlist in its devicetree, if any, it constructs a single string
using the base name along with any available suffixes, each beginning with a
hyphen. The best match algorithm is then run using that string.

The following compatible-string suffixes may be used to this end. They must be
provided in this order (<n> is an integer >= 0):

``-rev<n>``
    Board revision number, typically referring to a revision of the PCB to fix
    a problem or adjust component selection. The intention is that the board is
    the same design, just with some minor fixes or improvements. The first
    revision is typically ``rev0``.

``-sku<n>``
    Board variant, called a SKU (Stock-Keeping Unit) which is a unique code that
    identifies a model variant. This may encode differences in the display,
    WiFi and the like, but where the same PCB design (and revision) is used.
    The base SKU is typically ``sku0``.

Examples::

    compatible = "google,kevin-rev15";
    compatible = "google,kevin-rev15-sku2";

When matching, the bootloader should build the most specific string it can using
any available revision / SKU information, then try to match that. If the most
specific string fails (e.g. ``"google,kevin-rev15-sku2"``), it should fall back
to just ``"google,kevin-rev15"`` and then ``"google,kevin-sku2"``. If nothing
matches, then it should try without any additions, i.e. ``"google,kevin"``.

This multi-stage process uses the same 'best match' approach as above. Each
attempt finds the best match given the compatible string being searched. Where
a stage does not find any match, the next stage begins. As soon as a match is
found, searching stops, using the best match found in the stage.

Other suffixes may be added in future.


Load the images from the selected configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The configuration contains a number of images. One of these is the OS itself.
Another is typically a devicetree blob, which provides information about
available devices, useful for the OS as it boots and runs. Another image may be
a ramdisk (or initrd) which provides an initial root disk for the OS to use,
before it is able to access the real root disk.

The bootloader reads each image from the FIT and 'loads' it to the correct
address. This address may be provided by the image's ``load`` property
(see :ref:`prop_load`), but if not provided, the bootloader can load it to any
suitable address. In some cases it may be possible to avoid loading the image
and just refer to the image data within the FIT itself.

Fix up the devicetree
~~~~~~~~~~~~~~~~~~~~~

Many Operating Systems use devicetree blobs for configuration. As a result, most
bootloaders provide a way to update the devicetree in the FIT before passing it
to the OS. This may be used to pass command-line parameters to Linux, to select
the console device to use, or to pass the ramdisk to the OS. It is also common
to enable or disable certain devicetree nodes based on the hardware
in use.

The fixups required depend on the OS and its expectations. The result is a
devicetree slightly modified from the FIT version.

Jump to the OS
~~~~~~~~~~~~~~

Once everything is ready, the bootloader jumps to the OS. At this point the FIT
is no longer in use. The OS typically does not see the FIT itself and only cares
about the images that were loaded. At this point, the FIT has served its
purpose.

Firmware usage
--------------

As firmware has become more complex, with multiple binaries loaded at each
phase of the boot, it has become common to use FIT to load firmware.

In this case, there is the concept of a boot phase (see :ref:`prop_phase`),
indicating which phase each image is for.

In this case the bootloader itself is likely split into multiple phases. For
U-Boot, a common approach is for SPL (Secondary Program Loader) to load U-Boot
proper, along with :index:`ATF` and any other images required by U-Boot proper.

FIT processing for firmware images is no different from the approach described
above, except that any image with a ``phase`` property is only loaded if the
phase matches the phase being loaded. So, for example, SPL loads U-Boot proper
so will only load images with a phase of "u-boot". If TPL is in use (the phase
before SPL), then TPL will only load images with a phase of "spl". This allows
all images to be provided in a single FIT, with each phase pulling out what is
needed as the boot proceeds.

.. _multi_step:

Multi-step loading
------------------

The most common use of a FIT is where each configuration contains everything
needed to boot. For example, on ARM systems a configuration contains a kernel,
devicetree(s) and a ramdisk if needed. This approach is widely used on embedded
systems.

This approach is not always desirable, however, particularly when the firmware
and the OS are supplied by different parties. In that case, the devicetree may
be provided by the firmware with the other pieces coming from the OS. This
means that FIT may omit the devicetree images.

With devicetree in particular, it is common for the OS to provide its own
version, or perhaps a devicetree overlay to add some new nodes and properties.

Obviously if the OS has to provide a devicetree for every device, the OS files
would become very large. A middle path could be that the hardware vendor
provides a FIT on a boot partition, containing devicetrees for hardware
supported by that vendor. Then the bootloader can load that FIT to get just the
devicetree, followed by the main FIT to load the OS.

To enable this last case, add a :ref:`load_only` property to the configuration.
This signals to the bootloader that it should not require an executable (i.e.
kernel or firmware), nor should it try to boot with this configuration. Booting
then becomes a two-step process: load one FIT to obtain the devicetree, then
another to obtain the OS. Only the second FIT is booted.

Specifically, the 'load-only' property adjusts the meaning of loading a FIT, so
that implementors should follow the following behaviour:

===================  ==================  ====================
'load-only' present  Executable present  Behaviour
===================  ==================  ====================
no                   no                  Raise an error
yes                  no                  Only load the images
no                   yes                 Execute binary
yes                  yes                 Execute binary
===================  ==================  ====================

.. _verity-usage:

dm-verity for filesystem images
-------------------------------

A FIT may contain ``filesystem``-type sub-images that carry a ``dm-verity``
child node (see :ref:`dm-verity-nodes`). Such images bundle both the
filesystem payload and the dm-verity Merkle-tree hash data inside the same
sub-image. A Linux block driver exposes each loadable sub-image as
``/dev/fit0``, ``/dev/fit1``, etc.

When a ``dm-verity`` node is present, the bootloader should translate its
properties into kernel command-line parameters so that the kernel can activate
a dm-verity integrity target at boot, before mounting the root filesystem.
Two parameters are needed:

``dm-mod.waitfor``
    Tells ``dm-init`` to wait for the block device to appear before creating
    mapped devices. The bootloader should list the ``/dev/fitN`` device that
    corresponds to the sub-image::

        dm-mod.waitfor=/dev/fit0

``dm-mod.create``
    Defines a device-mapper table using the ``--concise`` format accepted by
    ``dmsetup``. The general form for a verity target is::

        <name>,<uuid>,<minor>,ro,
          0 <num_sectors> verity <version>
          <dev> <hash_dev>
          <data_block_size> <hash_block_size>
          <num_data_blocks> <hash_start_block>
          <algorithm> <digest> <salt>
          [<#opt_params> <opt_params>]

    Because both the filesystem data and the hash tree reside inside the same
    ``/dev/fitN`` device, ``<dev>`` and ``<hash_dev>`` are identical and shall
    be set by the bootloader. The ``<version>`` is always ``1``.

Field mapping
~~~~~~~~~~~~~

The following table shows how each dm-verity construction parameter
is derived from the ``dm-verity`` node properties.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - dm-verity parameter
     - Source
   * - ``<name>``
     - The unit name of the ``/images`` sub-node that contains the
       ``dm-verity`` child node.
   * - ``<uuid>``
     - May be left empty (``""``).
   * - ``<minor>``
     - May be left empty (``""``).
   * - ``<num_sectors>``
     - ``num-data-blocks * (data-block-size / 512)``
   * - ``<version>``
     - Always ``1``.
   * - ``<dev>``, ``<hash_dev>``
     - Both set to the ``/dev/fitN`` block device that the uImage.FIT block
       driver creates for this sub-image.
   * - ``<data_block_size>``
     - ``data-block-size`` from the ``dm-verity`` node.
   * - ``<hash_block_size>``
     - ``hash-block-size`` from the ``dm-verity`` node.
   * - ``<num_data_blocks>``
     - ``num-data-blocks`` from the ``dm-verity`` node.
   * - ``<hash_start_block>``
     - ``hash-start-block`` from the ``dm-verity`` node.
   * - ``<algorithm>``
     - ``algo`` from the ``dm-verity`` node.
   * - ``<digest>``
     - ``digest`` from the ``dm-verity`` node, hex-encoded.
   * - ``<salt>``
     - ``salt`` from the ``dm-verity`` node, hex-encoded.
   * - ``<opt_params>``
     - Constructed from the boolean option properties present in the
       ``dm-verity`` node (e.g. ``restart-on-corruption``,
       ``panic-on-error``). The bootloader collects every option property that
       is present, converts the property name from hyphenated to underscored
       form (e.g. ``restart-on-corruption`` becomes ``restart_on_corruption``),
       counts them, and appends ``<count> <option> [<option> ...]`` to the
       target line.

Example
~~~~~~~

Given a ``filesystem`` sub-image node named ``rootfs-1``,
exposed as ``/dev/fit0``, whose ``dm-verity`` node contains::

    dm-verity {
        data-block-size = <4096>;
        hash-block-size = <4096>;
        num-data-blocks = <204800>;
        hash-start-block = <204800>;
        algo = "sha256";
        digest = [ac 87 db 56 30 3c 9c 1d a4 33 d7 20 9b 5a 6e f3
                  e4 77 9d f1 41 20 0c bd 7c 15 7d cb 8d d8 9c 42];
        salt = [5e bf e8 7f 7d f3 23 5b 80 a1 17 eb c4 07 8e 44
                f5 50 45 48 7a d4 a9 65 81 d1 ad b5 64 61 5b 51];
        panic-on-corruption;
        panic-on-error;
    };

The bootloader constructs::

    dm-mod.waitfor=/dev/fit0

    dm-mod.create="rootfs-1,,, ro,
      0 1638400 verity 1
      /dev/fit0 /dev/fit0
      4096 4096 204800 204800 sha256
      ac87db56303c9c1da433d7209b5a6ef3e4779df141200cbd7c157dcb8dd89c42
      5ebfe87f7df3235b80a117ebc4078e44f55045487ad4a96581d1adb564615b51
      2 panic_on_corruption panic_on_error"

.. note::

   The newlines inside the ``dm-mod.create`` value above are
   for readability only. The actual kernel command-line
   parameter must be a single line.

Here ``num_sectors`` = 204800 × (4096 / 512) = 1638400. ``<name>`` is the image
unit name ``rootfs-1``; ``<uuid>`` and ``<minor>`` are left empty; ``ro``
indicates a read-only target. ``<dev>`` and ``<hash_dev>`` are both
``/dev/fit0`` because the filesystem data and the Merkle tree reside in the same
sub-image. The two boolean properties ``panic-on-corruption`` and
``panic-on-error`` become the optional-parameter suffix ``2 panic_on_corruption
panic_on_error`` (count followed by underscore-separated names). The remaining
fields map directly from the ``dm-verity`` node properties.

.. note::

   When preparing the sub-image with ``veritysetup format``, pass
   ``--no-superblock`` so that the hash tree starts directly after
   the data blocks. By default ``veritysetup`` writes a one-block
   on-disk superblock between data and hash tree, which would shift
   ``hash-start-block`` to ``num-data-blocks + 1``. The kernel
   dm-verity target never reads this superblock — all parameters
   are supplied via ``dm-mod.create`` — so it is unnecessary when
   the metadata is already stored in the FIT ``dm-verity`` node.

.. sectionauthor:: Simon Glass <sjg@chromium.org>
