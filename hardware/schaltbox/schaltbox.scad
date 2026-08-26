// Mains distribution box for the Fotobox, with the switch for the photo lamp.
//
// Front wall: the lower two Euro sockets, in a column pushed to the left edge.
// Rear wall (the lid): the third, directly opposite the place it used to have.
// Right wall: the IEC inlet, upright and low -- it brings mains, fuse and main
// switch in one part. Between the middle and the top socket a shelf spans the
// full width; the relay sits on it.
//
// The lid screws on from behind into brass inserts, so the case needs no tabs.
//
// The box size is given, not derived. Every part is checked against it and the
// file says what fits and what does not when it renders.
//
// x runs across the width, y from the front wall back to the lid, z upwards.
// Origin is the inner corner at front/left/bottom.

include <schaltbox_parts.scad>

part = "beides";   // "unterteil" | "deckel" | "beides"
$fn = 48;

// --- derived ----------------------------------------------------------------

inner = [box[0] - 2 * wall, box[1] - 2 * wall, box[2] - 2 * wall];
ssr_body = ssr_flat ? ssr_body_f : ssr_body_v;

// Sockets lie flat: the 44 mm side of the frame runs across the width, the
// 20 mm side stacks up the height.
sock_w  = socket_cut[1];     // 34
sock_h  = socket_cut[0];     // 13.2
sfl_w   = socket_flange[1];  // 44
sfl_h   = socket_flange[0];  // 20

// Column against the left edge; that frees the whole right side.
sock_x  = sfl_w / 2 + 4;
sock_pitch = max(sfl_h + 6, sock_h + 10);
sock_z  = [for (i = [0 : socket_count - 1])
              (inner[2] - (socket_count - 1) * sock_pitch) / 2 + i * sock_pitch];
front_z = [for (i = [0 : front_count - 1]) sock_z[i]];
rear_z  = sock_z[socket_count - 1];

// The inlet stands upright and low, so the shelf above it can run right across.
iec_z   = iec_cut[0] / 2 + 3;

// Shelf between the middle and the top socket, full width. It stops short of
// the lid so wires can pass from the inlet up to the relay.
// As low as it may go, not midway: below it the inlet and the middle socket set
// the limit, and every millimetre saved there is headroom for the relay above.
shelf_z  = max(sock_z[front_count - 1] + sock_h / 2 + 1 + rib_h / 2,
               iec_z + iec_cut[0] / 2 + 0.5 + rib_h / 2);
// All the way to the lid. What used to be an 8 mm slot at the back is now the
// U-shaped notch in the shelf.
shelf_y  = inner[1];
shelf_ok = shelf_z - rib_h / 2 > iec_z + iec_cut[0] / 2;

// What is left above the shelf, right of the socket column.
free_w = inner[0] - (sock_x + sock_w / 2 + snap_margin + 2);
free_z = inner[2] - (shelf_z + rib_h / 2);

// --- fit report -------------------------------------------------------------

pcb_stack = pcb_standoff + pcb[2] + ssr_body[2];

echo(str("Aussen ", box[0], " x ", box[1], " x ", box[2],
         "  ->  innen ", inner[0], " x ", inner[1], " x ", inner[2]));
echo(str("Verbindung ", connection,
         ": Kaltgeraetebuchse ", iec_depth, " mm, Euro ", socket_depth, " mm"));
echo(str("Dosen ragen ", socket_depth, " mm in ", inner[1], " mm Tiefe -> ",
         socket_depth <= inner[1] ? "passt" : "PASST NICHT"));
echo(str("Buchse ragt ", iec_depth, " mm in ", inner[0], " mm Breite -> ",
         iec_depth <= inner[0] ? "passt" : "PASST NICHT"));
echo(str("  Ausschnitt hochkant ", iec_cut[0], " hoch x ", iec_cut[1],
         " tief auf ", inner[2], " x ", inner[1], " -> ",
         iec_cut[0] <= inner[2] && iec_cut[1] + 2 * snap_margin <= inner[1]
             ? "passt" : "PASST NICHT"));
echo(str("Steg auf z=", shelf_z, ", Buchse endet bei ", iec_z + iec_cut[0] / 2,
         " -> ", shelf_ok ? "frei" : "STOSSEN ZUSAMMEN"));
echo(str("Ueber dem Steg, rechts der Saeule: ", free_w, " breit x ", inner[1],
         " tief x ", free_z, " hoch"));
echo(str("  SSR allein ", ssr_body[2], " mm hoch -> ",
         ssr_body[2] <= free_z ? "passt" : "PASST NICHT"));
echo(str("  mit Platine ", pcb_stack, " mm -> ",
         pcb_stack <= free_z ? "passt" : "PASST NICHT"));

// --- helpers ----------------------------------------------------------------

// The wall stays thick and is thinned only around an opening, on the two edges
// the snaps grip. The pocket is wider at the inner face than at its floor: a
// step would be a ceiling the printer has to bridge.
module snap_pocket(w, h, mx, my, depth) {
    hull() {
        linear_extrude(0.01)
            square([w + 2 * (mx + depth), h + 2 * (my + depth)], center = true);
        translate([0, 0, depth])
            linear_extrude(0.01) square([w + 2 * mx, h + 2 * my], center = true);
    }
}

// Rectangle with two corners cut off at one SHORT side -- the inlet's key.
// w is the long dimension, so the chamfers belong on the edge of length h.
module keyed_rect(w, h, cham) {
    polygon([[-w/2,        -h/2],
             [ w/2 - cham, -h/2],
             [ w/2,        -h/2 + cham],
             [ w/2,         h/2 - cham],
             [ w/2 - cham,  h/2],
             [-w/2,         h/2]]);
}

// The four places the lid is screwed. Same x and z in both parts, which is the
// whole point of listing them once -- they used to be written in the shell's
// frame and cut nothing at all in the lid.
// Right into the corners: set in, the domes stand about in the middle of a wall
// and look like an afterthought. At boss_d/2 - 1 they bite into the corner and
// read as part of it.
lip_w = 4;    // Breite des Randes am Deckel
lip_d = 3;    // wie tief er in das Gehaeuse greift

lid_screw_c  = boss_d / 2 - 1;
lid_screw_xz = [[lid_screw_c, lid_screw_c],
                [lid_screw_c, inner[2] - lid_screw_c],
                [inner[0] - lid_screw_c, lid_screw_c],
                [inner[0] - lid_screw_c, inner[2] - lid_screw_c]];

// --- openings ---------------------------------------------------------------

// Snaps on the narrow (13.2 mm) edges, which run across the width, so the wall
// gives way sideways. The shell and the lid need mirrored versions: in the
// shell the inside is at y > 0, in the lid at y < 0. Reusing one module for
// both left the lid's cutout stopping halfway through the plate.
module socket_in_front_wall() {
    rotate([90, 0, 0]) {
        // rotate([90,0,0]) sends +z to -y, so the extrusion runs outwards from
        // here. Starting at -wall-1 left the outer 2 mm of the wall standing.
        translate([0, 0, -1]) linear_extrude(wall + 2)
            square([sock_w, sock_h], center = true);
        snap_pocket(sock_w, sock_h, snap_margin, 0, wall - socket_snap_wall);
    }
}

module socket_in_lid() {
    rotate([-90, 0, 0]) {
        // From behind the rim right through the plate.
        translate([0, 0, -lip_d - 1]) linear_extrude(lid_t + lip_d + 2)
            square([sock_w, sock_h], center = true);
        snap_pocket(sock_w, sock_h, snap_margin, 0, lid_t - socket_snap_wall);
    }
}

module front_openings() {
    for (cz = front_z) translate([sock_x, 0, cz]) socket_in_front_wall();
}

module iec_opening() {
    depth = wall - iec_snap_wall;
    // rotate([0,90,0]) maps the profile's x to -z and its y to +y: the 48 mm
    // side lands on the height, which is the only way it fits a face 44 deep.
    translate([inner[0] - 1, inner[1] / 2, iec_z])
        rotate([0, 90, 0]) linear_extrude(wall + 2)
            keyed_rect(iec_cut[0], iec_cut[1], iec_chamfer);
    translate([inner[0], inner[1] / 2, iec_z])
        rotate([0, 90, 0]) snap_pocket(iec_cut[0], iec_cut[1], 0, snap_margin, depth);
}

// Right wall, above the shelf and next to the board. The shelf keeps it apart
// from the inlet below, so mains and 3.3 V never share a stretch of wall.
module control_opening() {
    translate([inner[0] - 1, inner[1] / 2, shelf_z + rib_h / 2 + ctrl_hole_d / 2 + 4])
        rotate([0, 90, 0]) cylinder(d = ctrl_hole_d, h = wall + 2);
}

// --- inside -----------------------------------------------------------------

module shelf() {
    // Full width, as asked, but 8 mm short of the lid: without that slot no
    // wire gets from the inlet at the bottom up to the relay on top.
    difference() {
        translate([-0.5, 0, shelf_z - rib_h / 2])
            cube([inner[0] + 1, shelf_y, rib_h]);
        cable_notch();
    }
}

// Open towards the lid, so a bundle can be laid in from behind rather than
// threaded through. Placed left of where the relay sits.
module cable_notch() {
    cx = sock_x + sfl_w / 2 - 4;
    hull()
        for (cy = [inner[1] - notch_d + notch_w / 2, inner[1] + 1])
            translate([cx, cy, shelf_z - rib_h / 2 - 1])
                cylinder(d = notch_w, h = rib_h + 2);
}

module lower_rib() {
    // Between the two front openings: three cutouts and the thinned strips
    // beside them leave that wall springy, so it is tied to the back.
    if (front_count > 1) {
        cz = (front_z[0] + front_z[1]) / 2;
        // From the left wall across to just past the column, and back to the lid.
        translate([-0.5, 0, cz - rib_h / 2])
            cube([sock_x + sock_w / 2 + rib_overhang, shelf_y, rib_h]);
    }
}

module lid_bosses() {
    // Brass inserts go in from the lid face; the dome gives them material.
    // Flush with the lid face, not past it, and short enough that the lower
    // right dome stays clear of the inlet body behind the wall.
    boss_len = insert_len + 1.5;
    for (p = lid_screw_xz)
        translate([p[0], inner[1] - boss_len, p[1]])
            rotate([-90, 0, 0])
                difference() {
                    cylinder(d = boss_d, h = boss_len);
                    translate([0, 0, boss_len - insert_len - 0.5])
                        cylinder(d = insert_d, h = insert_len + 1);
                }
}

// The board is screwed straight into the shelf, so what it needs there is
// holes, not posts.
module pcb_holes() {
    if (with_pcb)
        for (dx = [pcb_inset, pcb[0] - pcb_inset])
            for (dy = [pcb_inset, pcb[1] - pcb_inset])
                translate([inner[0] - free_w + dx, dy + 4, shelf_z - rib_h])
                    cylinder(d = screw_pilot, h = rib_h * 2);
}

// --- parts ------------------------------------------------------------------

module unterteil() {
    difference() {
        translate([-wall, -wall, -wall]) cube([box[0], box[1], box[2]]);
        translate([0, 0, 0]) cube([inner[0], inner[1] + wall + 1, inner[2]]);
        front_openings();
        iec_opening();
        control_opening();
    }
    difference() {
        shelf();
        pcb_holes();
    }
    lower_rib();
    lid_bosses();
}

module deckel() {
    difference() {
        union() {
            translate([-wall, 0, -wall]) cube([box[0], lid_t, box[2]]);
            // A rim, not a plate. As a full slab it sat behind the socket
            // opening and closed it again, and made the panel 6 mm thick where
            // the snaps want 2.
            difference() {
                translate([clearance, -lip_d, clearance])
                    cube([inner[0] - 2 * clearance, lip_d, inner[2] - 2 * clearance]);
                translate([lip_w, -lip_d - 1, lip_w])
                    cube([inner[0] - 2 * lip_w, lip_d + 2, inner[2] - 2 * lip_w]);
            }
        }
        // the third socket, directly opposite the place it had in front
        translate([sock_x, 0, rear_z]) socket_in_lid();
        // screws from behind, countersunk so nothing stands proud
        for (p = lid_screw_xz) {
            translate([p[0], -4, p[1]]) rotate([-90, 0, 0])
                cylinder(d = screw_d + 0.4, h = lid_t + 6);
            translate([p[0], lid_t - 1.6, p[1]]) rotate([-90, 0, 0])
                cylinder(d1 = screw_d + 0.4, d2 = screw_d * 2, h = 1.7);
        }
        // clear the shelf and the rib
        // Aussparungen fuer die Stege, die bis an die Rueckwand reichen.
        for (cz = [shelf_z, (front_z[0] + front_z[1]) / 2])
            translate([-1, -lip_d - 0.1, cz - rib_h / 2 - clearance])
                cube([inner[0] + 2, lip_d + 0.2, rib_h + 2 * clearance]);
    }
}

// --- what goes inside -------------------------------------------------------

module fitting_dummies() {
    fl = 2;   // wie weit die Rahmen vor der Wand stehen

    // Kaltgeraetebuchse: Koerper innen, Rahmen aussen auf der rechten Wand.
    color("gray")
        translate([inner[0] - iec_depth, (inner[1] - iec_cut[1]) / 2, iec_z - iec_cut[0] / 2])
            cube([iec_depth, iec_cut[1], iec_cut[0]]);
    color("darkgray")
        translate([inner[0] + wall, (inner[1] - iec_flange[1]) / 2, iec_z - iec_flange[0] / 2])
            cube([fl, iec_flange[1], iec_flange[0]]);

    // Die beiden Dosen in der Vorderwand.
    for (cz = front_z) {
        color("silver")
            translate([sock_x - sock_w / 2, 0, cz - sock_h / 2])
                cube([sock_w, socket_depth, sock_h]);
        color("gainsboro")
            translate([sock_x - sfl_w / 2, -wall - fl, cz - sfl_h / 2])
                cube([sfl_w, fl, sfl_h]);
    }

    // Die dritte in der Rueckwand, genau gegenueber -- ihr Rahmen sitzt auf der
    // Aussenseite des Deckels und wandert in der Explosionsansicht mit.
    color("silver")
        translate([sock_x - sock_w / 2, inner[1] - socket_depth, rear_z - sock_h / 2])
            cube([sock_w, socket_depth, sock_h]);

    // SSR auf dem Steg, 33 mm laengs der Tiefe: quer sind nur 25 frei.
    color("dimgray")
        translate([inner[0] - free_w + 6, 6, shelf_z + rib_h / 2 + pcb_standoff + pcb[2]])
            rotate([0, 0, 90]) cube(ssr_body);
}

module lid_dummy_flange() {
    color("gainsboro")
        translate([sock_x - sfl_w / 2, lid_t, rear_z - sfl_h / 2])
            cube([sfl_w, 2, sfl_h]);
}

if (part == "unterteil") unterteil();
else if (part == "deckel") deckel();
else {
    unterteil(); fitting_dummies();
    translate([0, box[1] + 25, 0]) { deckel(); lid_dummy_flange(); }
}
