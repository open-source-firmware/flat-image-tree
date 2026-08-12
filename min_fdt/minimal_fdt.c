/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * Minimal FDT parser - see minimal_fdt.h for the profile constraints
 *
 * No heap, no recursion, all bounds checked.  The state machine has
 * four states - see enum parser_state.
 */

#include "minimal_fdt.h"
#include <string.h>

#define FDT_MAGIC		0xd00dfeed
#define FDT_BEGIN_NODE		1
#define FDT_END_NODE		2
#define FDT_PROP		3
#define FDT_NOP			4
#define FDT_END			9

#define FDT_HDR_SIZE		40
#define FDT_MEMRSV_TERM_SIZE	16

static inline uint32_t align4(uint32_t x)
{
	return (x + 3) & ~3;
}

/*
 * Host-endian copy of the FDT header fields
 *
 * off_mem_rsvmap is validated below; boot_cpuid_phys is meaningless in
 * a post-sign trailer and is deliberately not checked
 */
struct fdt_hdr {
	uint32_t magic;
	uint32_t totalsize;
	uint32_t off_struct;
	uint32_t off_strings;
	uint32_t off_mem_rsvmap;
	uint32_t version;
	uint32_t last_comp_version;
	uint32_t boot_cpuid_phys;
	uint32_t size_strings;
	uint32_t size_struct;
};

/*
 * FDT_HDR_SIZE is a wire-format constant (Devicetree Specification, 5.2)
 * and is parsed via explicit be32() reads, not memcpy.  Keep the host
 * struct layout in step so that mismatches are caught at compile time.
 */
_Static_assert(sizeof(struct fdt_hdr) == FDT_HDR_SIZE,
	       "fdt_hdr layout no longer matches the on-disk header size");

/*
 * Conceptual state of the structure-block walk.  Each FDT token either
 * advances the state, leaves it unchanged (FDT_NOP), or is rejected as
 * a structural error if it does not match the current state.
 */
enum parser_state {
	BEFORE_ROOT,	/* no FDT_BEGIN_NODE yet */
	IN_ROOT,	/* inside the single root node */
	AFTER_ROOT,	/* root closed, awaiting FDT_END */
	DONE,		/* FDT_END seen, loop exits */
};

static uint32_t be32(const uint8_t *p)
{
	return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
	       ((uint32_t)p[2] << 8)  |  (uint32_t)p[3];
}

static void parse_hdr(const uint8_t *blob, struct fdt_hdr *hdr)
{
	hdr->magic		= be32(blob +  0);
	hdr->totalsize		= be32(blob +  4);
	hdr->off_struct		= be32(blob +  8);
	hdr->off_strings	= be32(blob + 12);
	hdr->off_mem_rsvmap	= be32(blob + 16);
	hdr->version		= be32(blob + 20);
	hdr->last_comp_version	= be32(blob + 24);
	hdr->boot_cpuid_phys	= be32(blob + 28);
	hdr->size_strings	= be32(blob + 32);
	hdr->size_struct	= be32(blob + 36);
}

/*
 * Validate the 40-byte header and populate hdr.  On success, all of
 * hdr's offset/size fields are known to fit inside the blob and the
 * struct and strings blocks do not overlap.
 */
static int validate_header(const uint8_t *blob, uint32_t size,
			   struct fdt_hdr *hdr)
{
	int i;

	if (size < FDT_HDR_SIZE)
		return MFDT_ERR_TRUNCATED;
	if (size > MFDT_MAX_SIZE)
		return MFDT_ERR_TOOLARGE;

	parse_hdr(blob, hdr);

	if (hdr->magic != FDT_MAGIC)
		return MFDT_ERR_BADMAGIC;
	if (hdr->totalsize != size)
		return MFDT_ERR_BADLAYOUT;
	if (hdr->version != 17)
		return MFDT_ERR_BADVERSION;
	if (hdr->last_comp_version > 17)
		return MFDT_ERR_BADVERSION;

	/*
	 * Memreserve block must immediately follow the header and contain
	 * nothing but the 16-byte all-zero terminator (no reservations
	 * are permitted in our trailer profile)
	 */
	if (hdr->off_mem_rsvmap != FDT_HDR_SIZE)
		return MFDT_ERR_BADLAYOUT;
	if (size < FDT_HDR_SIZE + FDT_MEMRSV_TERM_SIZE)
		return MFDT_ERR_TRUNCATED;
	for (i = 0; i < FDT_MEMRSV_TERM_SIZE; i++)
		if (blob[FDT_HDR_SIZE + i])
			return MFDT_ERR_BADLAYOUT;

	if (hdr->off_struct & 3)
		return MFDT_ERR_ALIGNMENT;
	if (hdr->off_struct < FDT_HDR_SIZE + FDT_MEMRSV_TERM_SIZE ||
	    hdr->off_struct > size ||
	    hdr->size_struct > size - hdr->off_struct)
		return MFDT_ERR_BADLAYOUT;
	if (hdr->off_strings < FDT_HDR_SIZE + FDT_MEMRSV_TERM_SIZE ||
	    hdr->off_strings > size ||
	    hdr->size_strings > size - hdr->off_strings)
		return MFDT_ERR_BADLAYOUT;
	/* Reject overlapping struct/strings blocks */
	if (hdr->off_struct < hdr->off_strings + hdr->size_strings &&
	    hdr->off_strings < hdr->off_struct + hdr->size_struct)
		return MFDT_ERR_BADLAYOUT;

	return MFDT_OK;
}

int mfdt_parse(const uint8_t *blob, uint32_t size,
	       mfdt_prop_callback callback, void *callback_ctx)
{
	enum parser_state state = BEFORE_ROOT;
	struct fdt_hdr hdr;
	const uint8_t *sb;
	uint32_t pos = 0;
	const char *st;
	int ret;

	ret = validate_header(blob, size, &hdr);
	if (ret != MFDT_OK)
		return ret;

	sb = blob + hdr.off_struct;
	st = (const char *)blob + hdr.off_strings;

	while (pos + 4 <= hdr.size_struct && state != DONE) {
		uint32_t tok = be32(sb + pos);

		pos += 4;

		switch (tok) {
		case FDT_BEGIN_NODE:
			if (state != BEFORE_ROOT)
				return MFDT_ERR_BADSTRUCT;
			if (pos >= hdr.size_struct)
				return MFDT_ERR_TRUNCATED;
			if (sb[pos])
				return MFDT_ERR_BADSTRUCT;
			pos = align4(pos + 1);
			state = IN_ROOT;
			break;
		case FDT_END_NODE:
			if (state != IN_ROOT)
				return MFDT_ERR_BADSTRUCT;
			state = AFTER_ROOT;
			break;
		case FDT_PROP: {
			uint32_t plen, poff;

			if (state != IN_ROOT)
				return MFDT_ERR_BADSTRUCT;
			if (pos + 8 > hdr.size_struct)
				return MFDT_ERR_TRUNCATED;

			plen = be32(sb + pos);
			poff = be32(sb + pos + 4);
			pos += 8;

			if (plen > hdr.size_struct - pos)
				return MFDT_ERR_TRUNCATED;
			if (poff >= hdr.size_strings)
				return MFDT_ERR_BADOFFSET;
			if (!memchr(st + poff, 0, hdr.size_strings - poff))
				return MFDT_ERR_BADOFFSET;

			if (callback) {
				int ret = callback(callback_ctx, st + poff,
						   sb + pos, plen);
				if (ret < 0)
					return ret;
			}

			pos = align4(pos + plen);
			break;
		}
		case FDT_NOP:
			break;
		case FDT_END:
			if (state == IN_ROOT)
				return MFDT_ERR_BADSTRUCT;
			state = DONE;
			break;
		default:
			return MFDT_ERR_BADSTRUCT;
		}
	}

	if (state != DONE)
		return MFDT_ERR_TRUNCATED;
	/* FDT_END must be the last token - no trailing data allowed */
	if (pos != hdr.size_struct)
		return MFDT_ERR_BADSTRUCT;
	return MFDT_OK;
}

const char *mfdt_strerror(int err)
{
	switch (err) {
	case MFDT_OK:
		return "ok";
	case MFDT_ERR_BADOFFSET:
		return "bad offset";
	case MFDT_ERR_TRUNCATED:
		return "truncated";
	case MFDT_ERR_BADMAGIC:
		return "bad magic";
	case MFDT_ERR_BADVERSION:
		return "bad version";
	case MFDT_ERR_BADSTRUCT:
		return "bad structure";
	case MFDT_ERR_BADLAYOUT:
		return "bad layout";
	case MFDT_ERR_ALIGNMENT:
		return "alignment error";
	case MFDT_ERR_TOOLARGE:
		return "blob too large";
	default:
		return "unknown error";
	}
}
