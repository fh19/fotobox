// Mains switch box for the photo lamp -- part facts, in one place.
//
// Only the SSR is taken from a datasheet; everything else has to be measured on
// the parts actually bought, because "Euro socket" and "fuse holder" name a
// shape, not a size. Every value marked MESSEN is a placeholder that will not
// fit your parts by luck. Measure once, change here, and the whole box follows.

// --- Panasonic/Matsushita AQ2A2-ZP3 -----------------------------------------
// Verified against ds_61601_0001_en_aq1, "AC output, 2A and 3A types (Vertical)".
// Pins in one row: 1,2 = load (LAST), 3,4 = input (STEUERUNG).
ssr_body_v  = [33, 10, 25];   // vertical type, length x width x height
ssr_body_f  = [33, 25, 11];   // AQ2A2-J, the flat one
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

// --- IEC inlet with fuse holder and switch, snap-in -------------------------
// Measured on the part. This one piece replaces what used to be three: the
// mains entry, the fuse holder and a switch. The two chamfered corners sit at
// one SHORT side -- they are the orientation key, and putting them on the long
// side would make an opening the part does not go into.
iec_cut        = [48, 27.4];  // Gesamtabmessung, Fasen eingerechnet
iec_flange     = [51, 31];    // the visible frame; only 1.45 mm wider per side,
                              // so the cutout has to be accurate and the wall flat
iec_chamfer    = 5;
iec_key_flip   = false;       // which short side carries the chamfers
// Soldering instead of push-on connectors buys depth: 29 instead of 40 for the
// inlet, 35 instead of 50 for the sockets. It also gives up something -- a
// soldered joint on a flat tab is more brittle than a crimp, and this box gets
// carried to venues. "flachstecker" is therefore the default.
connection     = "flachstecker";   // "flachstecker" | "loeten"
iec_depth      = (connection == "loeten") ? 29 : 40;
iec_snap_wall  = 1.5;         // the snaps grip a wall no thicker than this
iec_snap_edge  = "long";      // which pair of cutout edges the snaps sit on

// --- Euro sockets, snap-in --------------------------------------------------
socket_cut       = [13.2, 34];   // snaps on the narrow sides
socket_flange    = [20, 44];     // sets the box height: the frame has to sit on
                                 // the wall, not hang over its edge
// Turned flat the sockets make a wide, low box instead of a narrow, tall one.
// The plug then goes in with its pins side by side and its cable leaves
// sideways -- worth thinking about before printing.
socket_upright   = true;
socket_depth     = (connection == "loeten") ? 35 : 50;
socket_snap_wall = 2.0;
socket_gap       = 10;        // free space between two cutouts
socket_count     = 3;

// A snap-in part wants a thin panel, a mains enclosure wants a thick wall. So
// the wall stays 3 mm and is thinned only around each opening, with 45-degree
// sides: a step there would be a ceiling the printer has to bridge.
snap_margin      = 4;         // how far the thinned area reaches past the cutout

// --- Control lead ------------------------------------------------------------
// Its own hole on the other side of the rib, so 3.3 V never shares a run with
// 230 V. The mains no longer needs one: it arrives through the inlet.
ctrl_hole_d      = 7.0;

// --- The box itself ---------------------------------------------------------
// Given, not derived: the box size is the requirement, so the parts are checked
// against it instead of setting it. Layout follows the second sketch: the three
// Euro sockets sit in a column on the front (the x-z face at y = 0), the inlet
// stands upright on the right (the y-z face at x = inner). The lid is the back,
// so taking it off opens everything at once.
box = [80, 50, 90];

// The vertical SSR needs 6 + 1.6 + 25 = 32.6 mm above its floor. There is not
// that much room left over the built-in parts, so the board is optional -- see
// the fit report the file echoes when it renders.
with_pcb = false;

// The flat variant AQ2A2-J-ZP3 is 33 x 25 x 11 instead of 33 x 10 x 25.
ssr_flat = false;

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
