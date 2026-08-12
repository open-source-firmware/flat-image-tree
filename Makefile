# SPDX-License-Identifier: Apache-2.0
#
# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SOURCEDIR     = source
BUILDDIR      = build
LATEXDIFF     = latexdiff

# Minimal FDT parser (issue #48). Built into a static library so that
# consumers can link a single .a file. Override CC/AR/CFLAGS_MIN_FDT
# from the command line for cross-compilation or stricter warnings.
CC                 ?= cc
AR                 ?= ar
CFLAGS_MIN_FDT     ?= -Wall -Wextra -Wpedantic -O2 -fPIC
MIN_FDT_DIR         = min_fdt
MIN_FDT_OBJS        = $(MIN_FDT_DIR)/minimal_fdt.o
MIN_FDT_LIB         = $(MIN_FDT_DIR)/libminfdt.a

all: latexpdf html

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo "  latexdiff   to make LaTeX files including changebars against previous release"

.PHONY: all help latexdiff Makefile minfdt minfdt-clean clean

minfdt: $(MIN_FDT_LIB)

$(MIN_FDT_LIB): $(MIN_FDT_OBJS)
	$(AR) rcs $@ $^

$(MIN_FDT_DIR)/%.o: $(MIN_FDT_DIR)/%.c $(MIN_FDT_DIR)/minimal_fdt.h
	$(CC) $(CFLAGS_MIN_FDT) -c -o $@ $<

minfdt-clean:
	rm -f $(MIN_FDT_OBJS) $(MIN_FDT_LIB)

# Override the Sphinx catch-all so that 'make clean' wipes both the
# Sphinx build tree and the minfdt artifacts.
clean: minfdt-clean
	@$(SPHINXBUILD) -M clean "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

latexdiff: latex
	@echo "Generating LaTeX changebars..."
	$(LATEXDIFF) --type=UNDERLINE --config VERBATIMENV=sphinxVerbatim \
		$(BUILDDIR)/latex-previous/flat-image-tree-specification.tex \
		$(BUILDDIR)/latex/flat-image-tree-specification.tex \
		> $(BUILDDIR)/latex/flat-image-tree-specification-changebars.tex
	@echo "Running LaTeX files through pdflatex..."
	$(MAKE) -C $(BUILDDIR)/latex all-pdf
	@echo
	@echo "latexdiff finished; the PDF files are in $(BUILDDIR)/latex."

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
