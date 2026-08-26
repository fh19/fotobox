// Mains distribution box for the Fotobox, with the switch for the photo lamp.
//
// A bar of 50 x 60 x 120 mm. The underside carries the IEC inlet -- which
// brings mains, fuse and main switch in one part -- and one Euro socket, in
// line. The left side carries the other two Euro sockets, also in line. The lid
// is the long face opposite the left side, so taking it off opens the whole bar
// sideways and both groups of sockets are reachable.
//
// The box size is given, not derived. Every part is therefore checked against
// it and the file says what fits and what does not when it renders.
//
// x runs along the 120 mm length, y from the left side towards the lid, z from
// the underside upwards. Origin is the inner corner at the underside/left end.

include <schaltbox_parts.scad>

part = "beides";   // "unterteil" | "deckel" | "beides" | "explosion"
$fn = 48;

// --- derived ----------------------------------------------------------------

inner = [box[0] - 2 * wall, box[1] - 2 * wall, box[2] - 2 * wall];
ssr_body = ssr_flat ? ssr_body_f : ssr_body_v;

// Sockets sit in a column on the front: the 44 mm side of the frame runs across
// the width, the 20 mm side stacks up the height.
sock_w  = socket_cut[1];     // 34, across the width
sock_h  = socket_cut[0];     // 13.2, up the height
sfl_w   = socket_flange[1];  // 44
sfl_h   = socket_flange[0];  // 20

// Column pushed to the left edge: that frees a corner on the right for the
// inlet and, under it, the relay.
sock_x  = sfl_w / 2 + 4;
sock_pitch = max(sfl_h + 6, sock_h + 10);
sock_z  = [for (i = [0 : socket_count - 1])
              (inner[2] - (socket_count - 1) * sock_pitch) / 2 + i * sock_pitch];

// The inlet stands upright on the right wall, pushed up so the space below it
// stays in one piece.
iec_z   = inner[2] - iec_cut[0] / 2 - 4;

// The corner right of the column and below the inlet, in one piece. The frame
// sits outside, so what takes up room in here is the body passing through the
// cutout -- plus a little in case it flares behind the panel.
free_w  = inner[0] - (sock_x + sock_w / 2 + snap_margin + 2);
free_z  = iec_z - iec_cut[0] / 2 - 2;

pcb_x0 = (inner[0] - pcb[0]) / 2;
pcb_z0 = socket_depth + 2;          // above whatever the underside parts occupy

// --- fit report -------------------------------------------------------------
// Printed on every render. A box with a given size can only be honest about
// what does not go in.

free_behind = inner[1] - socket_depth;
pcb_stack   = pcb_standoff + pcb[2] + ssr_body[2];

echo(str("Aussen ", box[0], " x ", box[1], " x ", box[2],
         "  ->  innen ", inner[0], " x ", inner[1], " x ", inner[2]));
echo(str("Verbindung ", connection,
         ": Kaltgeraetebuchse ", iec_depth, " mm, Euro ", socket_depth, " mm"));
echo(str("Vorderseite, Dosen ragen in y (", inner[1], " frei): ",
         socket_depth <= inner[1] ? "passt" : "PASST NICHT"));
echo(str("Rechte Seite, Buchse ragt in x (", inner[0], " frei): ",
         iec_depth <= inner[0] ? "passt" : "PASST NICHT"));
// Der Ausschnitt muss auch auf die Flaeche passen, nicht nur die Tiefe in den
// Kasten. Genau das war einmal falsch herum gedreht.
echo(str("  Ausschnitt hochkant ", iec_cut[0], " hoch x ", iec_cut[1],
         " tief auf einer Flaeche ", inner[2], " x ", inner[1], " -> ",
         iec_cut[0] <= inner[2] && iec_cut[1] + 2 * snap_margin <= inner[1]
             ? "passt" : "PASST NICHT"));
echo(str("  Flansch ", iec_flange[0], " x ", iec_flange[1], " auf ",
         box[2], " x ", box[1], " -> ",
         iec_flange[0] <= box[2] && iec_flange[1] <= box[1] ? "passt" : "PASST NICHT"));
echo(str("Saeule: ", socket_count, " Rahmen a ", sfl_h, " mm im Raster ", sock_pitch,
         " -> ", (socket_count - 1) * sock_pitch + sfl_h, " von ", inner[2], " mm Hoehe"));
echo(str("Platine+SSR ", pcb_stack, " mm Aufbau."));
echo(str("  Ecke rechts unter der Buchse: ", free_w, " breit x ", inner[1],
         " tief x ", free_z, " hoch"));
echo(str("    liegend, SSR nach oben: Platine ", pcb[0], " x ", pcb[1], " -> ",
         pcb[0] <= inner[1] && pcb[1] <= free_w && pcb_stack <= free_z
             ? "passt" : "PASST NICHT"));
echo(str("    stehend an der Wand: Aufbau ", pcb_stack, " in ", free_w, " mm -> ",
         pcb_stack <= free_w ? "passt" : "PASST NICHT"));
echo(str("    groesste liegende Platine: ", inner[1], " x ", free_w,
         " mm bei Aufbau bis ", free_z, " mm"));
echo(str("  hinter den Dosen: ", free_behind, " mm"));

// --- helpers ----------------------------------------------------------------

// The wall stays thick and is thinned only around an opening, on the two edges
// the snaps actually grip. mx/my say which. The pocket is wider at the inner
// face than at its floor: a step would be a ceiling the printer has to bridge.
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

// --- openings ---------------------------------------------------------------

// The inlet stands upright on the right wall. Snaps on its long (48 mm) edges,
// so the wall gives way above and below the opening.
module iec_opening() {
    depth = wall - iec_snap_wall;
    // rotate([0,90,0]) maps the profile's x to -z and its y to +y. So the 48 mm
    // side lands on the height and the 27.4 mm side across the depth -- upright,
    // which is the only way round it fits a face that is 44 mm deep.
    translate([inner[0] - 1, inner[1] / 2, iec_z])
        rotate([0, 90, 0]) linear_extrude(wall + 2)
            keyed_rect(iec_cut[0], iec_cut[1], iec_chamfer);
    // Snaps on the long (48 mm) edges, which now run up the height, so the wall
    // gives way to either side of them -- across the depth.
    translate([inner[0], inner[1] / 2, iec_z])
        rotate([0, 90, 0]) snap_pocket(iec_cut[0], iec_cut[1], 0, snap_margin, depth);
}

// Three sockets in a column on the front. Snaps on their narrow (13.2 mm)
// edges, which now run across the width -- so the wall gives way sideways.
module front_openings() {
    depth = wall - socket_snap_wall;
    for (cz = sock_z) {
        translate([sock_x, -wall - 1, cz])
            rotate([-90, 0, 0]) linear_extrude(wall + 2)
                square([sock_w, sock_h], center = true);
        translate([sock_x, 0, cz])
            rotate([90, 0, 0]) snap_pocket(sock_w, sock_h, snap_margin, 0, depth);
    }
}

// Between the openings, from the front wall back to the lid. Only as wide as
// the column plus a little, so the side channels stay open.
module front_ribs() {
    for (i = [0 : socket_count - 2]) {
        cz = (sock_z[i] + sock_z[i + 1]) / 2;
        translate([sock_x - sock_w / 2 - rib_overhang, 0, cz - rib_h / 2])
            cube([sock_w + 2 * rib_overhang, inner[1] - 3, rib_h]);
    }
}

module control_opening() {
    // Only needed while the board lives in here.
    if (with_pcb)
        translate([-wall - 1, inner[1] / 2, inner[2] * 0.85])
            rotate([0, 90, 0]) cylinder(d = ctrl_hole_d, h = wall + 2);
}

// --- parts ------------------------------------------------------------------

module unterteil() {
    difference() {
        union() {
            translate([-wall, -wall, -wall]) cube([box[0], box[1], box[2]]);
            mounting_ears();
        }
        // open towards +y, that face is the lid
        translate([0, 0, 0]) cube([inner[0], inner[1] + wall + 1, inner[2]]);
        iec_opening();
        front_openings();
        control_opening();
        lid_screw_holes();
    }
    front_ribs();
    if (with_pcb) pcb_standoffs();
}

module lid_screw_positions() {
    for (x = [8, inner[0] - 8])
        for (z = [8, inner[2] - 8])
            translate([x, inner[1], z]) children();
}

module lid_screw_holes() {
    lid_screw_positions()
        rotate([-90, 0, 0]) translate([0, 0, -14]) cylinder(d = screw_pilot, h = 15);
}

module pcb_standoffs() {
    for (dx = [pcb_inset, pcb[0] - pcb_inset])
        for (dy = [pcb_inset, pcb[1] - pcb_inset])
            translate([pcb_x0 + dx, dy + 4, pcb_z0 - pcb_standoff])
                difference() {
                    cylinder(d = boss_d, h = pcb_standoff);
                    translate([0, 0, 2]) cylinder(d = screw_pilot, h = pcb_standoff);
                }
}

module mounting_ears() {
    // On the top face, so the bar can be screwed up into the Fotobox.
    for (x = [box[0] * 0.25, box[0] * 0.75])
        translate([x - wall, inner[1] - 1, inner[2]])
            difference() {
                translate([-ear_len / 2, 0, 0]) cube([ear_len, ear_len + 1, wall]);
                translate([0, ear_len * 0.6, -1]) cylinder(d = ear_hole_d, h = wall + 2);
            }
}

module deckel() {
    difference() {
        union() {
            translate([-wall, 0, -wall]) cube([box[0], lid_t, box[2]]);
            translate([clearance, -3, clearance])
                cube([inner[0] - 2 * clearance, 3, inner[2] - 2 * clearance]);
        }
        lid_screw_positions()
            rotate([-90, 0, 0]) translate([0, 0, -4]) cylinder(d = screw_d + 0.4, h = lid_t + 6);
        lid_screw_positions()
            rotate([-90, 0, 0]) translate([0, 0, lid_t - 1.8]) cylinder(d = screw_d * 2, h = 2);
    }
}

// --- what goes inside -------------------------------------------------------

module fitting_dummies() {
    color("gray")
        translate([inner[0] - iec_depth, (inner[1] - iec_cut[1]) / 2, iec_z - iec_cut[0] / 2])
            cube([iec_depth, iec_cut[1], iec_cut[0]]);
    for (cz = sock_z)
        color("silver")
            translate([sock_x - sock_w / 2, 0, cz - sock_h / 2])
                cube([sock_w, socket_depth, sock_h]);
}

module pcb_dummy() {
    if (with_pcb) {
        color("darkgreen") translate([pcb_x0, 4, pcb_z0]) cube(pcb);
        color("dimgray")
            translate([pcb_x0 + term_2p_w + 4, 4 + (pcb[1] - ssr_body[1]) / 2,
                       pcb_z0 + pcb[2]]) cube(ssr_body);
    }
}

if (part == "unterteil") unterteil();
else if (part == "deckel") deckel();
else if (part == "explosion") {
    unterteil(); fitting_dummies(); pcb_dummy();
    translate([0, 40, 0]) deckel();
} else {
    unterteil(); fitting_dummies(); pcb_dummy();
    translate([0, box[1] + 20, 0]) deckel();
}
