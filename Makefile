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

all: latexpdf html

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo "  latexdiff   to make LaTeX files including changebars against previous release"
	@echo "  branchdiff  to make a diff PDF comparing current branch against origin/main"

.PHONY: all help latexdiff branchdiff Makefile

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

branchdiff:
	@echo "Generating diff PDF against origin/main..."
	@./scripts/make-diff-pdf
	@echo
	@echo "branchdiff finished; diff.pdf is in the top-level directory."

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
