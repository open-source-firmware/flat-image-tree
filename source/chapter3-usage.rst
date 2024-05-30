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

Security
--------

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

.. sectionauthor:: Simon Glass <sjg@chromium.org>
