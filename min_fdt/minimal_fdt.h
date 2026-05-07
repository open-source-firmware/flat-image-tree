/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * minimal_fdt.h - Minimal FDT parser for a constrained post-sign FIT trailer.
 *
 * The on-disk format is the standard Flattened Devicetree blob (DTB)
 * defined by the Devicetree Specification - the same format consumed by
 * libfdt and produced by dtc - so a blob that satisfies this parser
 * also reads correctly with any conformant DT tool.  This parser only
 * implements a small profile of that format: the blob is expected to
 * contain a single root node with properties only - no sub-nodes, no
 * phandles, no aliases.  That keeps the parser small and auditable
 * without giving up interoperability with the wider DT ecosystem.
 */

#ifndef MINIMAL_FDT_H
#define MINIMAL_FDT_H

#include <stdint.h>

/**
 * DOC: Error codes
 *
 * Numbers are chosen to match libfdt's (negated) convention where the
 * semantics overlap - see <libfdt.h>.  Codes with no libfdt equivalent
 * use values past FDT_ERR_MAX (19).  mfdt_parse() returns int so a
 * callback can propagate arbitrary negative values; named codes are
 * still members of enum mfdt_err for debugger display and switch
 * coverage.
 */
enum mfdt_err {
	MFDT_OK			= 0,
	MFDT_ERR_BADOFFSET	= -4,	/* property name offset OOB    */
	MFDT_ERR_TRUNCATED	= -8,	/* blob too small, missing END */
	MFDT_ERR_BADMAGIC	= -9,
	MFDT_ERR_BADVERSION	= -10,	/* version != 17               */
	MFDT_ERR_BADSTRUCT	= -11,	/* tokens, nesting, root name  */
	MFDT_ERR_BADLAYOUT	= -12,	/* bounds, overlap, totalsize  */
	MFDT_ERR_ALIGNMENT	= -19,
	MFDT_ERR_TOOLARGE	= -50,	/* blob exceeds MFDT_MAX_SIZE  */
};

/** MFDT_MAX_SIZE - Hard upper bound on trailer size (64 KB). */
#define MFDT_MAX_SIZE		(64 * 1024)

/**
 * typedef mfdt_prop_callback - Per-property callback fired during parsing
 * @ctx: Caller-supplied context, passed through unchanged
 * @name: NUL-terminated property name from the strings block
 * @value: Pointer to the property value bytes (inside the blob)
 * @len: Length of the value in bytes
 *
 * Fired once per property in the root node.  Return < 0 to stop parsing;
 * that value is propagated directly as the parse return code.  Callbacks
 * that want to avoid collision with parser codes should use values below
 * -100.
 *
 * Return: 0 to continue, negative to stop parsing.
 */
typedef int (*mfdt_prop_callback)(void *ctx, const char *name,
				  const uint8_t *value, uint32_t len);

/**
 * mfdt_parse() - Parse a minimal FDT blob
 * @blob: Pointer to the blob bytes
 * @size: Total size of the blob in bytes
 * @callback: Per-property callback, or %NULL to validate only
 * @callback_ctx: Opaque context passed to @callback
 *
 * Walks the structure block of @blob, calling @callback for each property
 * in the root node.  All offsets and lengths are bounds-checked; the
 * parser uses no heap and no recursion.
 *
 * Return: %MFDT_OK on success, or one of the negative MFDT_ERR_* codes on
 *   failure.  If @callback returns a negative value the parser stops and
 *   propagates that value.
 */
int mfdt_parse(const uint8_t *blob, uint32_t size,
	       mfdt_prop_callback callback, void *callback_ctx);

/**
 * mfdt_strerror() - Translate an error code to a human-readable string
 * @err: Error code returned by mfdt_parse()
 *
 * Return: Pointer to a static, NUL-terminated string describing @err.
 *   Always non-%NULL; unknown codes return a generic message.
 */
const char *mfdt_strerror(int err);

#endif /* MINIMAL_FDT_H */
