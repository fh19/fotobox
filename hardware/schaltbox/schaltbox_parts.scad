// Mains switch box for the photo lamp -- part facts, in one place.
//
// Only the SSR is taken from a datasheet; everything else has to be measured on
// the parts actually bought, because "Euro socket" and "fuse holder" name a
// shape, not a size. Every value marked MESSEN is a placeholder that will not
// fit your parts by luck. Measure once, change here, and the whole box follows.

// --- Panasonic/Matsushita AQ2A2-ZP3 -----------------------------------------
// Verified against ds_61601_0001_en_aq1, "AC output, 2A and 3A types (Vertical)".
// Pins in one row: 1,2 = load (LAST), 3,4 = input (STEUERUNG).
ssr_body    = [33, 10, 25];   // length, width, height above the board
ssr_pin_d   = 0.8;
ssr_pitches = [7.62, 12.7, 5.08];  // 1->2, 2->3, 3->4; 25.4 in total
ssr_pin_len = 5.3;            // below the body

// --- Screw terminals, 5.08 mm pitch -----------------------------------------
// MESSEN: body depth and height vary by make; the width follows the pitch.
term_pitch  = 5.08;
term_depth  = 10.0;           // MESSEN: front to back on the board
term_height = 10.5;           // MESSEN: above the board
term_2p_w   = 2 * term_pitch + 2.2;   // ~12.4
term_3p_w   = 3 * term_pitch + 2.2;   // ~17.4

// --- The little board -------------------------------------------------------
// A strip of perfboard is enough: 2-pole terminal | SSR | 3-pole terminal, in a
// row, because that is the order the SSR's own pins impose.
pcb          = [70, 30, 1.6];
pcb_hole_d   = 3.2;
pcb_inset    = 4;             // hole centres from the edges
pcb_standoff = 6;             // board sits this high above the floor

// --- Fuse holder, 5 x 20 mm, panel mount ------------------------------------
// MESSEN: the common ones want a 12.2 mm hole and 30 mm of room behind it.
fuse_hole_d  = 12.2;          // MESSEN
fuse_depth   = 32;            // MESSEN: behind the panel, including the cap
fuse_flat    = 0;             // MESSEN: >0 if the hole has an anti-turn flat

// --- Euro sockets -----------------------------------------------------------
// MESSEN: this is the number most likely to be wrong. Two shapes are common:
// a rectangular snap-in and a round flush socket. Set socket_round accordingly.
socket_round  = false;        // true = round cutout of socket_cut[0] diameter
socket_cut    = [30, 30];     // MESSEN: cutout, not the visible frame
socket_depth  = 26;           // MESSEN: how far it reaches into the box
socket_gap    = 10;           // free space between two cutouts
socket_count  = 3;

// --- Cable entries ----------------------------------------------------------
// Mains in through a gland (that is the strain relief). The control lead gets
// its own hole on the other side, so 3.3 V never shares a run with 230 V.
gland_hole_d   = 16.5;        // M16, for H05VV-F 3G1.0 (~8 mm)
gland_boss_d   = 24;
gland_boss_len = 6;           // thicker wall so the thread has something to hold
ctrl_hole_d    = 7.0;         // grommet for the two-wire control lead

// --- Print and assembly -----------------------------------------------------
// 3 mm is the floor, not a target: an FDM wall is porous along the layer lines
// and is not the insulation a moulded one of the same thickness would be.
wall        = 3.0;
floor_t     = 3.0;
lid_t       = 3.0;
clearance   = 0.3;            // printing play, per side
screw_d     = 3.0;            // lid screws, self-tapping into the bosses
screw_pilot = 2.5;
boss_d      = 8.0;
ear_hole_d  = 4.2;            // mounting into the Fotobox enclosure
ear_len     = 12;

// Mains parts must keep their distance from anything a finger can reach. The
// print is a holder, not the insulation -- sleeve the live parts as well.
creep_gap   = 8.0;
