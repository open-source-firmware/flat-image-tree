.. SPDX-License-Identifier: GPL-2.0+

.. _chapter-source-file-format:

Flattened Image Tree (FIT) Format
=================================

Introduction
------------

FIT consists of a devicetree blob with nodes and properties following a certain
schema. Therefore this document defines FIT by providing FDT (Flat Device Tree)
bindings. These describe the final form of the FIT at the moment when it is
used. The user perspective may be simpler, as some of the properties (like
timestamps and hashes) are filled in automatically by available tooling, such
as `mkimage`.

To avoid confusion with the :index:`kernel FDT <pair: kernel; FDT>` the following
naming convention is used:

FIT
    Flattened Image Tree

    FIT is formally a flattened devicetree (in the libfdt meaning), which
    conforms to bindings defined in this document.

:index:`.its`
    image tree source

:index:`.fit`
    flattened image tree blob

    This was previously known as :index:`.itb` but has been renamed to `.fit`.

Image-building procedure
~~~~~~~~~~~~~~~~~~~~~~~~

The following picture shows how the FIT is prepared. Input consists of
image source file (.its) and a set of data files. Image is created with the
help of standard :index:`U-Boot mkimage <pair: U-Boot; mkimage>` tool which in
turn uses dtc (device tree compiler) to produce image tree blob (.fit). The
resulting .fit file is the actual binary of a new FIT::

    tqm5200.its
    +
    vmlinux.bin.gz     mkimage + dtc               xfer to target
    eldk-4.2-ramdisk  --------------> tqm5200.fit --------------> boot
    tqm5200.dtb                          /|\
                                          |
                                     'new FIT'

Steps:

#. Create .its file, automatically filled-in properties are omitted

#. Call :index:`mkimage` tool on .its file

#. mkimage calls dtc to create .fit image and assures that
   missing properties are added

#. .fit (new FIT) is uploaded onto the target and used therein


Unique identifiers
~~~~~~~~~~~~~~~~~~

To identify FIT sub-nodes representing images, hashes, configurations (which
are defined in the following sections), the "unit name" of the given sub-node
is used as its identifier as it assures uniqueness without additional
checking required.

.. index:: External data

.. _ExternalData:

External data
~~~~~~~~~~~~~

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

Root-node properties
--------------------

The root node of the FIT should have the following layout::

    / o image-tree
        |- description = "image description"
        |- timestamp = <12399321>
        |- #address-cells = <1>
        |
        o images
        | |
        | o image-1 {...}
        | o image-2 {...}
        | ...
        |
        o configurations
          |- default = "conf-1"
          |
          o conf-1 {...}
          o conf-2 {...}
          ...

Optional property
~~~~~~~~~~~~~~~~~

description
    Textual description of the FIT

Mandatory property
~~~~~~~~~~~~~~~~~~

:index:`timestamp`
    Last image modification time being counted in seconds since
    1970-01-01 00:00:00 - to be automatically calculated by mkimage tool.

Conditionally mandatory property
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:index:`#address-cells`
    Number of 32bit cells required to represent entry and
    load addresses supplied within sub-image nodes. May be omitted when no
    entry or load addresses are used.

Mandatory nodes
~~~~~~~~~~~~~~~

:index:`images`
    This node contains a set of sub-nodes, each of them representing
    single component sub-image (like :index:`kernel`, :index:`ramdisk`, etc.).
    At least one sub-image is required.

:index:`configurations`
    Contains a set of available configuration nodes and
    defines a default configuration.


'/images' node
--------------

This node is a container node for component sub-image nodes. Each sub-node of
the '/images' node should have the following layout::

    o image-1
        |- description = "component sub-image description"
        |- data = /incbin/("path/to/data/file.bin")
        |- type = "sub-image type name"
        |- arch = "ARCH name"
        |- os = "OS name"
        |- compression = "compression name"
        |- load = <00000000>
        |- entry = <00000000>
        |
        o hash-1 {...}
        o hash-2 {...}
        ...

Mandatory properties
~~~~~~~~~~~~~~~~~~~~

description
    Textual description of the component sub-image

:index:`type`
    Name of component sub-image type. Supported types are:

    ====================  ==================
    Sub-image type        Meaning
    ====================  ==================
    invalid               Invalid Image
    aisimage              Davinci AIS image
    atmelimage            ATMEL ROM-Boot Image
    copro                 Coprocessor Image
    fdt_legacy            legacy Image with Flat Device Tree
    filesystem            Filesystem Image
    firmware              Firmware
    firmware_ivt          Firmware with HABv4 IVT
    flat_dt               Flat Device Tree
    fpga                  FPGA Device Image (bitstream file, vendor specific)
    gpimage               TI Keystone SPL Image
    imx8image             NXP i.MX8 Boot Image
    imx8mimage            NXP i.MX8M Boot Image
    imximage              Freescale i.MX Boot Image
    kernel                Kernel Image
    kernel_noload         Kernel Image (no loading done)
    kwbimage              Kirkwood Boot Image
    lpc32xximage          LPC32XX Boot Image
    mtk_image             MediaTek BootROM loadable Image
    multi                 Multi-File Image
    mxsimage              Freescale MXS Boot Image
    omapimage             TI OMAP SPL With GP CH
    pblimage              Freescale PBL Boot Image
    pmmc                  TI Power Management Micro-Controller Firmware
    ramdisk               RAMDisk Image
    rkimage               Rockchip Boot Image
    rksd                  Rockchip SD Boot Image
    rkspi                 Rockchip SPI Boot Image
    script                Script
    socfpgaimage          Altera SoCFPGA CV/AV preloader
    socfpgaimage_v1       Altera SoCFPGA A10 preloader
    spkgimage             Renesas SPKG Image
    standalone            Standalone Program
    stm32image            STMicroelectronics STM32 Image
    sunxi_egon            Allwinner eGON Boot Image
    sunxi_toc0            Allwinner TOC0 Boot Image
    tee                   Trusted Execution Environment Image
    tfa-bl31              Trusted Firmware-A BL31 Image
    ublimage              Davinci UBL image
    vybridimage           Vybrid Boot Image
    x86_setup             x86 setup.bin
    zynqimage             Xilinx Zynq Boot Image
    zynqmpbif             Xilinx ZynqMP Boot Image (bif)
    zynqmpimage           Xilinx ZynqMP Boot Image
    ====================  ==================

compression
    :index:`Compression` used by included data. If no compression is used, the
    compression property should be set to "none". If the data is compressed but
    it should not be uncompressed by the loader
    (e.g. :index:`compressed ramdisk <pair: ramdisk; compressed`), this
    should also be set to "none".

    Supported compression types are:

    ====================  ==================
    Compression type      Meaning
    ====================  ==================
    none                  uncompressed
    bzip2                 bzip2 compressed
    gzip                  gzip compressed
    lz4                   lz4 compressed
    lzma                  lzma compressed
    lzo                   lzo compressed
    zstd                  zstd compressed
    ====================  ==================

Conditionally mandatory properties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

data
    Path to the external file which contains this node's binary data. Within
    the FIT this is the contents of the file. This is mandatory unless
    :index:`external data` is used.

data-size
    Size of the data in bytes. This is mandatory if :index:`external data` is
    used.

data-offset
    Offset of the data in a separate image store. The image store is placed
    immediately after the last byte of the device tree binary, aligned to a
    4-byte boundary. This is mandatory if :index:`external data` is used, with an offset.

data-position
    Machine address at which the data is to be found. This is a fixed address
    not relative to the loading of the FIT. This is mandatory if
    :index:`external data` is used with a fixed address.

os
    :index:`OS` name, mandatory for types "kernel". Valid OS names are:

    ====================  ==================
    OS name               Meaning
    ====================  ==================
    invalid               Invalid OS
    4_4bsd                4_4BSD
    arm-trusted-firmware  ARM Trusted Firmware
    dell                  Dell
    efi                   EFI Firmware
    esix                  Esix
    freebsd               FreeBSD
    integrity             INTEGRITY
    irix                  Irix
    linux                 Linux
    ncr                   NCR
    netbsd                NetBSD
    openbsd               OpenBSD
    openrtos              OpenRTOS
    opensbi               RISC-V OpenSBI
    ose                   Enea OSE
    plan9                 Plan 9
    psos                  pSOS
    qnx                   QNX
    rtems                 RTEMS
    sco                   SCO
    solaris               Solaris
    svr4                  SVR4
    tee                   Trusted Execution Environment
    u-boot                U-Boot
    vxworks               VxWorks
    ====================  ==================

arch
    :index:`Architecture` name, mandatory for types: "standalone", "kernel",
    "firmware", "ramdisk" and "fdt". Valid architecture names are:

    ====================  ==================
    Architecture type     Meaning
    ====================  ==================
    invalid               Invalid ARCH
    alpha                 Alpha
    arc                   ARC
    arm64                 AArch64
    arm                   ARM
    avr32                 AVR32
    blackfin              Blackfin
    ia64                  IA64
    m68k                  M68K
    microblaze            MicroBlaze
    mips64                MIPS 64 Bit
    mips                  MIPS
    nds32                 NDS32
    nios2                 NIOS II
    or1k                  OpenRISC 1000
    powerpc               PowerPC
    ppc                   PowerPC
    riscv                 RISC-V
    s390                  IBM S390
    sandbox               Sandbox
    sh                    SuperH
    sparc64               SPARC 64 Bit
    sparc                 SPARC
    x86_64                AMD x86_64
    x86                   Intel x86
    xtensa                Xtensa
    ====================  ==================

entry
    Entry point address, address size is determined by
    '#address-cells' property of the root node.
    Mandatory for types: "firmware", and "kernel".

.. _prop_load:

load
    Load address, address size is determined by '#address-cells'
    property of the root node.
    Mandatory for types: "firmware", and "kernel".

:index:`compatible`
    Compatible method for loading image.
    Mandatory for types: "fpga", and images that do not specify a load address.
    Supported compatible methods:

    ==========================  =========================================
    Compatible string           Meaning
    ==========================  =========================================
    u-boot,fpga-legacy          Generic fpga loading routine.
    u-boot,zynqmp-fpga-ddrauth  Signed non-encrypted FPGA bitstream for
                                Xilinx Zynq UltraScale+ (ZymqMP) device.
    u-boot,zynqmp-fpga-enc      Encrypted FPGA bitstream for Xilinx Zynq
                                UltraScale+ (ZynqMP) device.
    ==========================  =========================================

    .. note::
       For fdt images, the node should not have a compatible for the model.
       The compatible here is not derived from the fdt, nor is it used to identify
       the fdt. Such usage belongs in the configuration node.

.. _prop_phase:

:index:`phase`
    :index:`U-Boot phase <pair: U-Boot; phase>` for which the image is intended.

    "spl"
        image is an SPL image

    "u-boot"
        image is a U-Boot image

Optional nodes
~~~~~~~~~~~~~~

hash-1
    Each hash sub-node represents a separate hash or checksum
    calculated for node's data according to specified algorithm.

signature-1
    Each signature sub-node represents a separate signature
    calculated for node's data according to specified algorithm.

.. index:: Hash nodes

Hash nodes
----------

::

    o hash-1
        |- algo = "hash or checksum algorithm name"
        |- value = [hash or checksum value]

Mandatory properties
~~~~~~~~~~~~~~~~~~~~

algo
    :index:`Algorithm` name. Supported algorithms and their value sizes are:

    ==================== ============ =========================================
    Sub-image type       Size (bytes) Meaning
    ==================== ============ =========================================
    crc16-ccitt          2            Cyclic Redundancy Check 16-bit
                                      (Consultative Committee for International
                                      Telegraphy and Telephony)
    crc32                4            Cyclic Redundancy Check 32-bit
    md5                  16           Message Digest 5 (MD5)
    sha1                 20           Secure Hash Algorithm 1 (SHA1)
    sha256               32           Secure Hash Algorithm 2 (SHA256)
    sha384               48           Secure Hash Algorithm 2 (SHA384)
    sha512               64           Secure Hash Algorithm 2 (SHA512)
    ==================== ============ =========================================

value
    Actual checksum or hash value.

Image-signature nodes
---------------------

::

    o signature-1
        |- algo = "algorithm name"
        |- key-name-hint = "key name"
        |- value = [hash or checksum value]


Mandatory properties
~~~~~~~~~~~~~~~~~~~~

_`FIT Algorithm`:

algo
    :index:`Algorithm` name. Supported algorithms and their value sizes are
    shown below. Note that the hash is specified separately from the signing
    algorithm, so it is possible to mix and match any SHA algorithm with any
    signing algorithm. The size of the signature relates to the signing
    algorithm, not the hash, since it is the hash that is signed.

    ==================== ============ =========================================
    Sub-image type       Size (bytes) Meaning
    ==================== ============ =========================================
    sha1,rsa2048         256          SHA1 hash signed with 2048-bit
                                      Rivest–Shamir–Adleman algorithm
    sha1,rsa3072         384          SHA1 hash signed with 2048-bit RSA
    sha1,rsa4096         512          SHA1 hash signed with 2048-bit RSA
    sha1,ecdsa256        32           SHA1 hash signed with 256-bit  Elliptic
                                      Curve Digital Signature Algorithm
    sha256,...
    sha384,...
    sha512,...
    ==================== ============ =========================================

key-name-hint
    Name of key to use for signing. The keys will normally be in
    a single directory (parameter -k to mkimage). For a given key <name>, its
    private key is stored in <name>.key and the certificate is stored in
    <name>.crt.

sign-images
    A list of images to sign, each being a property of the conf
    node that contains them. The default is "kernel,fdt" which means that these
    two images will be looked up in the config and signed if present. This is
    used by mkimage to determine which images to sign.

The following properties are added as part of signing, and are mandatory:

value
    Actual signature value. This is added by mkimage.

hashed-nodes
    A list of nodes which were :index:`hashed <pair: nodes; hashed>` by the
    signer. Each is a string - the full path to node. A typical value might be::

	hashed-nodes = "/", "/configurations/conf-1", "/images/kernel",
	    "/images/kernel/hash-1", "/images/fdt-1",
	    "/images/fdt-1/hash-1";

hashed-strings
    The start and size of the :index:`string <pair: strings; hashed>` region of
    the FIT that was hashed. The start is normally 0, indicating the first byte
    of the string table. The size indicates the number of bytes hashed as part
    of signing.

The following properties are added as part of signing, and are optional:

timestamp
    Time when image was signed (standard Unix time_t format)

signer-name
    Name of the signer (e.g. "mkimage")

signer-version
    Version string of the signer (e.g. "2013.01")

comment
    Additional information about the signer or image

padding
    The padding algorithm, it may be pkcs-1.5 or pss,
    if no value is provided we assume pkcs-1.5


'/configurations' node
----------------------

The 'configurations' node creates convenient, labeled
:index:`boot configurations <pair: boot; configurations>`,
which combine together :index:`kernel images <pair: kernel; image>` with their
:index:`ramdisks` and fdt blobs.

The 'configurations' node has the following structure::

    o configurations
        |- default = "default configuration sub-node unit name"
        |
        o config-1 {...}
        o config-2 {...}
        ...


Optional property
~~~~~~~~~~~~~~~~~

default
    Selects one of the configuration sub-nodes as a default configuration.

Mandatory nodes
~~~~~~~~~~~~~~~

configuration-sub-node-unit-name
    At least one configuration sub-node is required.

Optional nodes
~~~~~~~~~~~~~~

signature-1
    Each signature sub-node represents a separate signature
    calculated for the configuration according to specified algorithm.


Configuration nodes
-------------------

Each configuration has the following structure::

    o config-1
        |- description = "configuration description";
        |- kernel = "kernel sub-node unit name";
        |- cmdline = "command line for next boot stage";
        |- fdt = "fdt sub-node unit-name" [, "fdt overlay sub-node unit-name", ...];
        |- ramdisk = "ramdisk sub-node unit-name";
        |- loadables = "loadables sub-node unit-name" [, ...];
        |- script = "script sub-node unit-name";
        |- compatible = "vendor,board-style device tree compatible string";
        o signature-1 {...}

Mandatory properties
~~~~~~~~~~~~~~~~~~~~

description
    Textual configuration description.

Conditionally mandatory property
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

kernel or firmware
    Unit name of the corresponding :index:`kernel` or :index:`firmware`
    (u-boot, op-tee, etc) image. If both "kernel" and "firmware" are specified,
    control is passed to the firmware image. For `load_only`_ images, these two
    properties are optional.


Optional properties
~~~~~~~~~~~~~~~~~~~

cmdline
    Command line passed to the next boot stage, e.g. the operating system
    kernel. The value is an UTF-8 encoded string.

fdt
    Unit name of the corresponding fdt blob (component image node of a
    "fdt type"). Additional fdt overlay nodes can be supplied which signify
    that the resulting device tree blob is generated by the first base fdt
    blob with all subsequent overlays applied.

fpga
    Unit name of the corresponding fpga bitstream blob
    (component image node of a "fpga type").

loadables
    Unit name containing a list of additional binaries to be
    loaded at their given locations. "loadables" is a comma-separated list
    of strings. :index:`U-Boot` will load each binary at its given load address
    (see :ref:`prop_load`) and may optionally invoke additional post-processing
    steps on this binary based on its component image node type.

ramdisk
    Unit name of the corresponding ramdisk to be loaded at the given location.

script
    The image to use when loading a :index:`U-Boot` script (for use with the
    source command).

compatible
    The root compatible string of the bootloader device tree that
    this configuration shall automatically match. If this property is not
    provided, the compatible string will be
    extracted from the fdt blob instead. This is only possible if the fdt is
    not compressed, so images with compressed fdts that want to use compatible
    string matching must always provide this property.

    Note that U-Boot requires the :index:`CONFIG_FIT_BEST_MATCH` option to be
    enabled for this matching to work.

.. _load_only:

load-only
    Indicates that this configuration does not necessarily contain an executable
    image, i.e. kernel or firmware. The configuration's images may be loaded
    into memory for use by the executable image, which comes from another
    configuration or FIT. See see :ref:`multi_step`.

The FDT blob is required to properly boot FDT-based kernel, so the minimal
configuration for 2.6 FDT kernel is (kernel, fdt) pair.

Older, 2.4 kernel and 2.6 non-FDT kernel do not use FDT blob, in such cases
'struct bd_info' must be passed instead of FDT blob, thus fdt property *must
not* be specified in a configuration node.


Configuration-signature nodes
-----------------------------

::

    o signature-1
        |- algo = "algorithm name"
        |- key-name-hint = "key name"
        |- sign-images = "path1", "path2";
        |- value = [hash or checksum value]
        |- hashed-strings = <0 len>


Mandatory properties
~~~~~~~~~~~~~~~~~~~~

algo
    See `FIT Algorithm`_.

key-name-hint
    Name of key to use for signing. The keys will normally be in
    a single directory (parameter -k to mkimage). For a given key <name>, its
    private key is stored in <name>.key and the certificate is stored in
    <name>.crt.

The following properties are added as part of signing, and are mandatory:

value
    Actual signature value. This is added by mkimage.

The following properties are added as part of signing, and are optional:

timestamp
    Time when image was signed (standard Unix time_t format)

signer-name
    Name of the signer (e.g. "mkimage")

signer-version
    Version string of the signer (e.g. "2013.01")

comment
    Additional information about the signer or image

padding
    The padding algorithm, it may be pkcs-1.5 or pss,
    if no value is provided we assume pkcs-1.5


.. sectionauthor:: Marian Balakowicz <m8@semihalf.com>
.. sectionauthor:: External data additions, 25/1/16 Simon Glass <sjg@chromium.org>
