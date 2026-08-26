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

// Sockets lie down: the 44 mm side of the frame runs along the length, so the
// 50 and 60 mm faces only have to carry its 20 mm side.
sock_l  = socket_cut[1];     // 34, along x
sock_s  = socket_cut[0];     // 13.2, across
sfl_l   = socket_flange[1];  // 44
sfl_s   = socket_flange[0];  // 20

// Everything is pushed towards x = 0 rather than spread out, so whatever length
// is left over stays in one piece at the far end -- that is the only place a
// board with an upright SSR could ever stand.
end_margin = 5;
part_gap   = 8;
iec_x    = end_margin + iec_flange[0] / 2;
under_x  = end_margin + iec_flange[0] + part_gap + sfl_l / 2;
left_x   = [end_margin + sfl_l / 2, end_margin + sfl_l + part_gap + sfl_l / 2];

// Free of every built-in part, over the full cross section.
free_x0  = max(under_x + sfl_l / 2, left_x[1] + sfl_l / 2) + 4;
free_len = inner[0] - free_x0;

pcb_x0 = (inner[0] - pcb[0]) / 2;
pcb_z0 = socket_depth + 2;          // above whatever the underside parts occupy

// --- fit report -------------------------------------------------------------
// Printed on every render. A box with a given size can only be honest about
// what does not go in.

free_over_under = inner[2] - socket_depth;
free_beside_left = inner[1] - socket_depth;
pcb_stack = pcb_standoff + pcb[2] + ssr_body[2];

echo(str("Aussen ", box[0], " x ", box[1], " x ", box[2],
         "  ->  innen ", inner[0], " x ", inner[1], " x ", inner[2]));
echo(str("Verbindung ", connection,
         ": Kaltgeraetebuchse ", iec_depth, " mm, Euro ", socket_depth, " mm"));
echo(str("Unterseite, Teile ragen in z (", inner[2], " frei): ",
         iec_depth <= inner[2] && socket_depth <= inner[2] ? "passt" : "PASST NICHT"));
echo(str("Linke Seite, Teile ragen in y (", inner[1], " frei): ",
         socket_depth <= inner[1] ? "passt" : "PASST NICHT"));
echo(str("Platine+SSR ", pcb_stack, " mm hoch; ueber den Unterseiten-Teilen ",
         free_over_under, " mm frei -> ",
         pcb_stack <= free_over_under ? "passt liegend" : "PASST NICHT liegend"));
echo(str("Freier Abschnitt am Ende: ", free_len, " x ", inner[1], " x ", inner[2],
         " mm; Platine ist ", pcb[0], " x ", pcb[1],
         " -> ", pcb[0] <= free_len ? "passt stehend" : "PASST NICHT stehend"));

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

module underside_openings() {
    depth_iec = wall - iec_snap_wall;
    depth_eu  = wall - socket_snap_wall;

    // IEC: 48.1 along x, snaps on those long edges -> the wall gives way in y.
    translate([iec_x, inner[1] / 2, -wall - 1])
        linear_extrude(wall + 2)
            rotate([0, 0, iec_key_flip ? 180 : 0])
                keyed_rect(iec_cut[0], iec_cut[1], iec_chamfer);
    translate([iec_x, inner[1] / 2, 0])
        rotate([180, 0, 0]) snap_pocket(iec_cut[0], iec_cut[1], 0, snap_margin, depth_iec);

    // Euro lying down: 34 along x, snaps on the 13.2 edges -> gives way in x.
    translate([under_x, inner[1] / 2, -wall - 1])
        linear_extrude(wall + 2) square([sock_l, sock_s], center = true);
    translate([under_x, inner[1] / 2, 0])
        rotate([180, 0, 0]) snap_pocket(sock_l, sock_s, snap_margin, 0, depth_eu);
}

module left_openings() {
    depth_eu = wall - socket_snap_wall;
    for (cx = left_x) {
        translate([cx, -wall - 1, inner[2] / 2])
            rotate([-90, 0, 0]) linear_extrude(wall + 2)
                square([sock_l, sock_s], center = true);
        translate([cx, 0, inner[2] / 2])
            rotate([90, 0, 0]) snap_pocket(sock_l, sock_s, snap_margin, 0, depth_eu);
    }
}

module control_opening() {
    // Only needed while the board lives in here.
    if (with_pcb)
        translate([inner[0] + 1, inner[1] / 2, inner[2] * 0.8])
            rotate([0, -90, 0]) cylinder(d = ctrl_hole_d, h = wall + 2);
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
        underside_openings();
        left_openings();
        control_opening();
        lid_screw_holes();
    }
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
        translate([iec_x - iec_cut[0] / 2, (inner[1] - iec_cut[1]) / 2, 0])
            cube([iec_cut[0], iec_cut[1], iec_depth]);
    color("silver")
        translate([under_x - sock_l / 2, (inner[1] - sock_s) / 2, 0])
            cube([sock_l, sock_s, socket_depth]);
    for (cx = left_x)
        color("silver")
            translate([cx - sock_l / 2, 0, (inner[2] - sock_s) / 2])
                cube([sock_l, socket_depth, sock_s]);
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
