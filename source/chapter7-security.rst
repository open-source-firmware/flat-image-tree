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

.. sectionauthor:: Simon Glass <sjg@chromium.org>
