.. SPDX-License-Identifier: Apache-2.0

.. _chapter-introduction:

Introduction
============

Purpose and Scope
-----------------

The number of elements playing a role in the kernel booting process has
increased over time and now typically includes the devicetree,
:index:`kernel image <pair: kernel; image>` and
possibly a ramdisk image. Generally, all must be placed in the system memory and
booted together.

For firmware images a similar process has taken place, with various binaries
loaded at different addresses, such as ARM's :index:`ATF`, :index:`OpenSBI`,
:index:`FPGA` and :index:`U-Boot` itself.

FIT provides a flexible and extensible format to deal with this complexity. It
provides support for multiple components. It also supports multiple
configurations, so that the same FIT can be used to boot multiple boards, with
some components in common (e.g. kernel) and some specific to that board (e.g.
devicetree).

This specification, the |spec-fullname| (|spec|),
provides a suitable format which can be used to describe any set of files
along with grouping and selection mechanisms.

* :numref:`Chapter %s <chapter-introduction>` introduces the purpose and
  background of |spec|.
* :numref:`Chapter %s <chapter-source-file-format>` introduces the FIT concept
  and describes its logical structure and standard properties.
  certain classes of devices and specific device types.
* :numref:`Chapter %s <chapter-usage>` describes how FIT is used in bootloaders
  to handle booting Operating Systems as well as firmware.

**Conventions Used in this Document**

The word *shall* is used to indicate mandatory requirements strictly to
be followed in order to conform to the standard and from which no
deviation is permitted (*shall* equals *is required to*).

The word *should* is used to indicate that among several possibilities
one is recommended as particularly suitable, without mentioning or
excluding others; or that a certain course of action is preferred but
not necessarily required; or that (in the negative form) a certain
course of action is deprecated but not prohibited (*should* equals *is
recommended that*).

The word *may* is used to indicate a course of action permissible within
the limits of the standard (*may* equals *is permitted*).

Examples of devicetree constructs are frequently shown in *Devicetree
Syntax* form. See [dtspec]_ for a description of this.

Relationship to |dtspec|
------------------------

|spec| is based on the :index:`Devicetree Specification`, in that it uses the
same structure and shares some concepts.

32-bit and 64-bit Support
-------------------------

The |spec| supports CPUs with both :index:`32-bit` and :index:`64-bit`
addressing capabilities. Where applicable, sections of the |spec| describe any
requirements or considerations for 32-bit and 64-bit addressing.


Definition of Terms
-------------------

.. glossary::

   DTB
       Devicetree blob. Compact binary representation of the devicetree.

   DTC
       Devicetree compiler. An open source tool used to create DTB files
       from DTS files.

   DTS
       Devicetree syntax. A textual representation of a devicetree
       consumed by the DTC. See Appendix A Devicetree Source Format
       (version 1).
