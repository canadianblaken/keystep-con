/* Make bass (KeyStep Pro 2.5.20): a bass line from another track's pattern, written as steps.
 *
 * Same rules as makeBass in the KeyStep Con page (src/6b-editor.js), so both give the same notes:
 * each step with notes is a chord; its root is the note with a fifth and a third above it (the
 * lowest note wins close calls); Root, Root + 5th, Octaves and Pulse play one line per chord
 * change, Follow plays the root on every step the part plays, with its gate.
 *
 * Built with clang -fropi into the hook block (build_ksp_patch.py): no library calls, constant
 * data in .text, firmware functions called by absolute address.
 *
 * Live sequencer RAM, project p, track t 0-3 (sequencer mode), pattern n (from 080464d0, the
 * project loader, and the note accessors 0802f51c / 0802d908 / 0802d31c):
 *   notes     0xC0000000 + p*0xF000 + t*0x3C00 + n*0x3C0, 192 x {pitch (0xff unused), gate, vel, shift, rand}
 *   step of   0xC015C000 + p*0x3000 + t*0xC00 + n*0xC0, per note slot (0xff unused)
 *   passes    0xC0104000 + ((p*5 + t)*16 + n)*0x20, 4 bits per step, 8 steps per word
 *   header    seq + p*0xFEC + t*0x140 + n*0x14 + 0x930: +0 u16 state (0xAAAA data), +2..+6 default
 *             note, +8 length-1, +0xA root (high nibble), +0xB scale (low nibble), +0xC 64 on bits
 * Track 1 in drum mode (bit 0 of seq + p*0xFEC + 0x1753) keeps its notes elsewhere: refused.
 * The sequencer's note offs come from its own queue of sounding notes, not from the pattern,
 * so rewriting a playing pattern does not leave notes hanging.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define SEQ         (*(u8 *volatile *)0x20001498)
#define CUR_PROJECT (*(volatile u8 *)0x20004dad)
#define CUR_PAT     ((volatile u8 *)0x20004da8)
#define UI          (*(u8 *volatile *)0x20001510)   /* popup owner, as 0802a244 passes to 08020e3c */
#define POPUP_CTX   (*(u32 *volatile *)0x200017f8)
#define POPUP_GATE  (*(volatile u8 *)0x200014d7)
#define POPUP_TABLE ((const u8 *)0x08020e4e)        /* 08020e3c's tbb table, per UI state */

typedef void (*f_dirty)(u8 *seq, u32 on, u32 pat, u32 track, u32 project);   /* 0802ceac */
typedef void (*f_unindex)(u8 *seq, u32 track, u32 zero);                      /* 0802caf0 */
typedef void (*f_index)(u8 *seq, u32 track);                                  /* 0802f340 */
typedef void (*f_scale)(u8 *seq, u32 track);                                  /* 0803094c */
typedef void (*f_ui)(u8 *ui, u32 what);                                       /* 0801f96c */
typedef void (*f_popup)(u32 *ctx, const char *text, u32 ms);                  /* 08025274 */

#define NOTES(p, t, n) ((u8 *)(0xC0000000u + (p) * 0xF000u + (t) * 0x3C00u + (n) * 0x3C0u))
#define STEPOF(p, t, n) ((u8 *)(0xC015C000u + (p) * 0x3000u + (t) * 0xC00u + (n) * 0xC0u))
#define PASSES(p, t, n) ((u32 *)(0xC0104000u + (((p) * 5u + (t)) * 16u + (n)) * 0x20u))
#define HEADER(s, p, t, n) ((s) + (p) * 0xFECu + (t) * 0x140u + (n) * 0x14u + 0x930u)

enum { ST_ROOT, ST_FIFTH, ST_OCT, ST_PULSE, ST_FOLLOW, STYLES };
#define BASS_OCTAVE 2   /* C2-B2, the page's default */
#define SLOTS 192

static const char bass_text_style[STYLES][32] = {
    "Bass: Root\nfrom track ", "Bass: Root + 5th\nfrom track ", "Bass: Octaves\nfrom track ",
    "Bass: Pulse\nfrom track ", "Bass: Follow\nfrom track "};
static const char bass_text_empty[] = "Bass: no notes\nin track ";
static const char bass_text_drum[] = "Bass: not with\ndrum mode on track ";

struct ev { u8 step, root, fifth, vel, gate, shift, rand, passes; };

/* scratch in the pad state block (0xC01EF800-0xC01EFFFF, which no stock code uses; the pad state
   itself ends below 0xC01EFA00): the chord list (64 x 8 bytes, kept off the event loop's stack)
   and the popup text */
#define EVS  ((struct ev *)0xC01EFA00)
#define TEXT ((char *)0xC01EFF80)

static void bass_popup(const char *head, u32 track)
{
    char *d = TEXT;
    while (*head) *d++ = *head++;
    *d++ = (char)('1' + track);
    *d = 0;
    u8 *ui = UI;
    u32 state = ui[0xC];
    if (state > 0x60) return;
    u8 path = POPUP_TABLE[state];          /* as 08020e3c: 0x31 shows, 0x6c shows when the gate is 0 */
    if (path == 0xa9 || (path == 0x6c && POPUP_GATE)) return;
    ((f_ui)0x0801f96d)(ui, 3);
    ((f_ui)0x0801f96d)(ui, 4);
    ((f_ui)0x0801f96d)(ui, 5);
    ((f_ui)0x0801f96d)(ui, 0x50);
    ((f_popup)0x08025275)(POPUP_CTX, TEXT, 1000);
    ui[0xC] = 0xf;
}

static u32 bass_is_drum(u8 *seq, u32 p, u32 t) { return t == 0 && (seq[p * 0xFEC + 0x1753] & 1); }

/* gate value for a length in 1/16 steps, as the page's Graw (gate table measured on hardware) */
static u32 bass_gate(u32 sixteenths)
{
    if (sixteenths <= 8) return sixteenths ? sixteenths - 1 : 0;
    u32 n = sixteenths >> 4;                /* whole steps from here on */
    if (n <= 3) return 3 + 8 * n;
    if (n <= 8) return 27 + (n - 3) * 4;
    if (n <= 32) return 47 + (n - 8) * 2;
    return n > 64 ? 127 : 95 + (n - 32);
}

/* root pitch class and fifth interval of a chord, as chordRoot in the page */
static void bass_chord_root(const u8 *pitches, u32 count, u32 *root, u32 *fifth)
{
    u32 pcs = 0;
    for (u32 i = 0; i < count; i++) pcs |= 1u << (pitches[i] % 12);
#define HAS(r, i) ((pcs >> (((r) + (i)) % 12)) & 1)
    int best = -1;
    u32 r = 0;
    for (u32 k = 0; k < count; k++) {      /* pitches sorted, no repeats */
        u32 c = pitches[k] % 12;
        int sc = (HAS(c, 7) ? 6 : 0) + (HAS(c, 3) || HAS(c, 4) ? 4 : 0) + (HAS(c, 10) || HAS(c, 11) ? 2 : 0) + (k ? 0 : 3);
        if (sc > best) { best = sc; r = c; }
    }
    *root = r;
    *fifth = HAS(r, 7) ? 7 : HAS(r, 6) && HAS(r, 3) ? 6 : HAS(r, 8) && HAS(r, 4) ? 8 : 7;
#undef HAS
}

/* write one note into the next free slot; returns the new slot count */
static u32 bass_put(u8 *notes, u8 *stepof, u32 slot, u32 step, u32 pitch, u32 sixteenths, const struct ev *e, u32 *on, u32 *passes)
{
    if (slot >= SLOTS || step >= 64) return slot;
    u8 *n = notes + slot * 5;
    n[0] = (u8)(pitch > 127 ? 127 : pitch);
    n[1] = (u8)(sixteenths ? bass_gate(sixteenths) : e->gate);
    n[2] = e->vel;
    n[3] = e->shift;
    n[4] = e->rand;
    stepof[slot] = (u8)step;
    on[step >> 5] |= 1u << (step & 31);
    passes[step >> 3] = (passes[step >> 3] & ~(0xfu << ((step & 7) * 4))) | ((u32)e->passes << ((step & 7) * 4));
    return slot + 1;
}

/* target, source: tracks 0-3; style 0-4. Returns the number of bass notes written, -1 if refused. */
int bass_go(u32 target, u32 source, u32 style)
{
    u8 *seq = SEQ;
    u32 p = CUR_PROJECT, tn = CUR_PAT[target], sn = CUR_PAT[source];
    if (target > 3 || source > 3 || target == source || style >= STYLES) return -1;
    if (bass_is_drum(seq, p, target)) { bass_popup(bass_text_drum, target); return -1; }
    if (bass_is_drum(seq, p, source)) { bass_popup(bass_text_drum, source); return -1; }

    u8 *sh = HEADER(seq, p, source, sn), *snotes = NOTES(p, source, sn), *sstep = STEPOF(p, source, sn);
    u32 *spass = PASSES(p, source, sn);
    u32 len = sh[8] + 1u;
    if (len > 64) len = 64;
    u32 son0 = sh[0xC] | sh[0xD] << 8 | sh[0xE] << 16 | (u32)sh[0xF] << 24;
    u32 son1 = sh[0x10] | sh[0x11] << 8 | sh[0x12] << 16 | (u32)sh[0x13] << 24;

    /* chords, one per step that plays */
    struct ev *evs = EVS;
    u32 count = 0;
    for (u32 i = 0; i < len; i++) {
        if (!(((i < 32 ? son0 : son1) >> (i & 31)) & 1)) continue;
        u32 pass = (spass[i >> 3] >> ((i & 7) * 4)) & 0xf;
        if (!pass) continue;
        u8 ps[16];
        u32 np = 0, first = SLOTS, vel = 0;
        for (u32 s = 0; s < SLOTS && np < 16; s++) {
            if (sstep[s] != i || snotes[s * 5] > 127) continue;
            u8 *n = snotes + s * 5;
            if (first == SLOTS) first = s;
            if (n[2] > vel) vel = n[2];
            u32 x = n[0], j = np;              /* insert sorted, drop repeats */
            u32 dup = 0;
            for (u32 k = 0; k < np; k++) if (ps[k] == x) dup = 1;
            if (dup) continue;
            while (j && ps[j - 1] > x) { ps[j] = ps[j - 1]; j--; }
            ps[j] = (u8)x;
            np++;
        }
        if (!np) continue;
        struct ev *e = &evs[count++];
        u32 root, fifth;
        bass_chord_root(ps, np, &root, &fifth);
        u8 *f = snotes + first * 5;
        e->step = (u8)i; e->root = (u8)root; e->fifth = (u8)fifth; e->vel = (u8)vel;
        e->gate = f[1]; e->shift = f[3]; e->rand = f[4]; e->passes = (u8)pass;
    }
    if (!count) { bass_popup(bass_text_empty, source); return -1; }
    if (style != ST_FOLLOW) {                  /* one line per chord change */
        u32 k = 1;
        for (u32 i = 1; i < count; i++)
            if (evs[i].root != evs[k - 1].root || evs[i].fifth != evs[k - 1].fifth) evs[k++] = evs[i];
        count = k;
    }

    /* clear the target pattern as the device does (0x80299e0: unused slots keep the default note) */
    u8 *th = HEADER(seq, p, target, tn), *tnotes = NOTES(p, target, tn), *tstep = STEPOF(p, target, tn);
    u32 *tpass = PASSES(p, target, tn);
    for (u32 s = 0; s < SLOTS; s++) {
        u8 *n = tnotes + s * 5;
        n[0] = 0xff; n[1] = th[3]; n[2] = th[4]; n[3] = th[5]; n[4] = th[6];
        tstep[s] = 0xff;
    }
    for (u32 w = 0; w < 8; w++) tpass[w] = 0xffffffffu;
    u32 on[2] = {0, 0}, slot = 0, base = 12 * (BASS_OCTAVE + 1);
    for (u32 k = 0; k < count; k++) {
        const struct ev *e = &evs[k];
        u32 span = (k + 1 < count ? evs[k + 1].step : len) - e->step, r = base + e->root;
        switch (style) {
        case ST_FOLLOW: slot = bass_put(tnotes, tstep, slot, e->step, r, 0, e, on, tpass); break;
        case ST_ROOT: slot = bass_put(tnotes, tstep, slot, e->step, r, span * 16, e, on, tpass); break;
        case ST_FIFTH: {
            u32 h = span >= 2 ? span / 2 : span;
            slot = bass_put(tnotes, tstep, slot, e->step, r, h * 16, e, on, tpass);
            if (h < span) slot = bass_put(tnotes, tstep, slot, e->step + h, r + e->fifth, (span - h) * 16, e, on, tpass);
            break;
        }
        default:
            for (u32 j = 0; j < span; j++)
                slot = bass_put(tnotes, tstep, slot, e->step + j, style == ST_OCT && (j & 1) ? r + 12 : r, 8, e, on, tpass);
        }
    }
    th[8] = (u8)(len - 1);
    th[0xA] = (u8)((th[0xA] & 0x0f) | (sh[0xA] & 0xf0));             /* root */
    th[0xB] = (u8)((th[0xB] & 0xf0) | (sh[0xB] & 0x0f));             /* scale */
    for (u32 b = 0; b < 4; b++) { th[0xC + b] = (u8)(on[0] >> (8 * b)); th[0x10 + b] = (u8)(on[1] >> (8 * b)); }
    ((f_dirty)0x0802cead)(seq, 1, tn, target, p);                     /* edited + state 0xAAAA */
    ((f_unindex)0x0802caf1)(seq, target, 0);                          /* rebuild the step index */
    ((f_index)0x0802f341)(seq, target);
    ((f_scale)0x0803094d)(seq, target);                               /* scale map for the new root/scale */
    bass_popup(bass_text_style[style], source);
    return (int)slot;
}
