// Mains switch box for the photo lamp, built into the Fotobox enclosure.
//
// Holds the SSR on a small board between a 2-pole control terminal and a 3-pole
// lamp terminal, three snap-in Euro sockets, and one snap-in IEC inlet that
// brings in the mains, the fuse and the main switch in a single part.
//
// The floor carries a rib splitting the inside in two: mains on the socket
// side, the 3.3 V control lead on the other, each with its own way in. A 3D
// print is a good holder and a poor insulator -- the rib and the walls hold
// things apart, sleeving and the parts themselves do the insulating.
//
// Origin is the inner floor corner on the inlet side. x runs along the socket
// wall, y from the socket wall towards the control side, z upwards.

include <schaltbox_parts.scad>

part = "beides";   // "unterteil" | "deckel" | "beides" | "explosion"
$fn = 48;

// --- derived sizes ----------------------------------------------------------

// Orientation first: everything below follows from it.
sock_w   = socket_upright ? socket_cut[0] : socket_cut[1];
sock_h   = socket_upright ? socket_cut[1] : socket_cut[0];
flange_w = socket_upright ? socket_flange[0] : socket_flange[1];
flange_h = socket_upright ? socket_flange[1] : socket_flange[0];

// The gap is measured between cutouts, but it is the frames that must not
// touch: they overhang the opening by (flange - cut) / 2 on each side.
socket_pitch = max(sock_w + socket_gap, flange_w + 4);
socket_span  = (socket_count - 1) * socket_pitch + sock_w;

// Behind the socket bodies the mains side needs room for wiring -- and the
// inlet sits in the same zone, lying on its long edge, so the zone has to be at
// least as deep as the inlet cutout is wide.
wire_room  = 15;
mains_zone = max(socket_depth + wire_room, iec_cut[0] + 2 * snap_margin + 8);

rib_y = mains_zone;
rib_t = 2.4;

// The inlet reaches into the box along x; the sockets must start beyond it.
socket_x0 = iec_depth + creep_gap;

inner_x = max(socket_x0 + socket_span + creep_gap, pcb[0] + 2 * creep_gap);
inner_y = rib_y + rib_t + creep_gap + pcb[1] + creep_gap;
// The frames sit on the wall, so the wall has to be taller than they are.
inner_z = max(ssr_body[2] + pcb_standoff + pcb[2] + 6,
              flange_h + 6,
              iec_flange[1] + 6);

outer_x = inner_x + 2 * wall;
outer_y = inner_y + 2 * wall;
outer_z = inner_z + floor_t;

pcb_x0 = (inner_x - pcb[0]) / 2;
pcb_y0 = rib_y + rib_t + creep_gap / 2;

// --- helpers ----------------------------------------------------------------

module pcb_hole_positions() {
    for (dx = [pcb_inset, pcb[0] - pcb_inset])
        for (dy = [pcb_inset, pcb[1] - pcb_inset])
            translate([pcb_x0 + dx, pcb_y0 + dy, 0]) children();
}

module lid_boss_positions() {
    // Pulled into the corners so the bosses cut into the walls instead of
    // standing tangent to them, which would leave a non-manifold seam.
    for (x = [boss_d / 2 - 0.8, inner_x - boss_d / 2 + 0.8])
        for (y = [boss_d / 2 - 0.8, inner_y - boss_d / 2 + 0.8])
            translate([x, y, 0]) children();
}

// A rectangle with two corners cut off at one short side -- the inlet's
// orientation key, so the part cannot go in upside down.
module keyed_rect(w, h, cham) {
    polygon([[-w/2,        -h/2],
             [ w/2,        -h/2],
             [ w/2,         h/2 - cham],
             [ w/2 - cham,  h/2],
             [-w/2 + cham,  h/2],
             [-w/2,         h/2 - cham]]);
}

// The wall stays 3 mm and is thinned only around an opening, so a snap-in part
// finds the panel thickness it expects. The pocket is wider at the inner face
// than at its floor: a step would be a ceiling the printer has to bridge.
// mx/my say on which pair of edges the snaps sit; only there does the wall have
// to give way. Thinning all round would merge the three socket pockets into one
// weak field, because the gap between them is exactly a pocket wide.
module snap_pocket_profile(w, h, mx, my, depth) {
    hull() {
        linear_extrude(0.01)
            square([w + 2 * (mx + depth), h + 2 * (my + depth)], center = true);
        translate([0, 0, depth])
            linear_extrude(0.01) square([w + 2 * mx, h + 2 * my], center = true);
    }
}

// --- openings ---------------------------------------------------------------

module socket_openings() {
    z_mid = inner_z / 2;
    depth = wall - socket_snap_wall;
    for (i = [0 : socket_count - 1]) {
        cx = socket_x0 + i * socket_pitch + sock_w / 2;
        // through hole
        translate([cx, -wall - 1, z_mid])
            rotate([-90, 0, 0])
                linear_extrude(wall + 2)
                    square([sock_w, sock_h], center = true);
        // thinning, opening towards the inside
        translate([cx, 0, z_mid])
            rotate([90, 0, 0])
                snap_pocket_profile(sock_w, sock_h,
                                    socket_upright ? 0 : snap_margin,
                                    socket_upright ? snap_margin : 0, depth);
    }
}

module iec_opening() {
    cy = mains_zone / 2;
    z_mid = inner_z / 2;
    depth = wall - iec_snap_wall;
    // through hole, keyed corners towards the top
    translate([-wall - 1, cy, z_mid])
        rotate([0, 90, 0])
            linear_extrude(wall + 2) rotate([0, 0, 90]) keyed_rect(iec_cut[1], iec_cut[0], iec_chamfer);
    // thinning
    translate([0, cy, z_mid])
        rotate([0, -90, 0])
            snap_pocket_profile(iec_cut[0], iec_cut[1], 0, snap_margin, depth);
}

module control_opening() {
    translate([inner_x / 2, inner_y + 1, inner_z / 2])
        rotate([90, 0, 0]) cylinder(d = ctrl_hole_d, h = wall + 2);
}

// --- parts ------------------------------------------------------------------

module unterteil() {
    difference() {
        union() {
            translate([-wall, -wall, -floor_t]) cube([outer_x, outer_y, outer_z]);
            mounting_ears();
        }
        translate([0, 0, 0]) cube([inner_x, inner_y, inner_z + 1]);
        socket_openings();
        iec_opening();
        control_opening();
        lid_boss_positions()
            translate([0, 0, inner_z - 12]) cylinder(d = screw_pilot, h = 14);
    }
    separation_rib();
    pcb_standoffs();
    lid_bosses();
}

module separation_rib() {
    // Reaches 0.5 mm into both side walls: faces that merely touch leave a
    // non-manifold seam, and slicers take that badly.
    translate([-0.5, rib_y, -0.5]) cube([inner_x + 1, rib_t, inner_z - 1.5]);
}

module pcb_standoffs() {
    pcb_hole_positions()
        translate([0, 0, -0.5])
            difference() {
                cylinder(d = boss_d, h = pcb_standoff + 0.5);
                translate([0, 0, 2]) cylinder(d = screw_pilot, h = pcb_standoff);
            }
}

module lid_bosses() {
    lid_boss_positions()
        translate([0, 0, -0.5])
            difference() {
                cylinder(d = boss_d, h = inner_z + 0.5);
                translate([0, 0, inner_z - 11.5]) cylinder(d = screw_pilot, h = 13);
            }
}

module mounting_ears() {
    for (x = [outer_x * 0.25, outer_x * 0.75])
        translate([x - wall, outer_y - wall - 1, -floor_t])
            difference() {
                translate([-ear_len / 2, 0, 0]) cube([ear_len, ear_len + 1, floor_t]);
                translate([0, ear_len * 0.6, -1]) cylinder(d = ear_hole_d, h = floor_t + 2);
            }
}

module deckel() {
    difference() {
        union() {
            translate([-wall, -wall, 0]) cube([outer_x, outer_y, lid_t]);
            translate([clearance, clearance, -3])
                cube([inner_x - 2 * clearance, inner_y - 2 * clearance, 3]);
        }
        lid_boss_positions() translate([0, 0, -4]) cylinder(d = screw_d + 0.4, h = lid_t + 6);
        lid_boss_positions() translate([0, 0, lid_t - 1.8]) cylinder(d = screw_d * 2, h = 2);
        translate([-1, rib_y - clearance, -3.1])
            cube([inner_x + 2, rib_t + 2 * clearance, 3.2]);
    }
}

// --- assembly view ----------------------------------------------------------

module pcb_dummy() {
    color("darkgreen") translate([pcb_x0, pcb_y0, pcb_standoff]) cube(pcb);
    color("dimgray")
        translate([pcb_x0 + term_2p_w + 4, pcb_y0 + (pcb[1] - ssr_body[1]) / 2,
                   pcb_standoff + pcb[2]]) cube(ssr_body);
    color("cornflowerblue")
        translate([pcb_x0 + 2, pcb_y0 + (pcb[1] - term_depth) / 2, pcb_standoff + pcb[2]])
            cube([term_2p_w, term_depth, term_height]);
    color("indianred")
        translate([pcb_x0 + pcb[0] - term_3p_w - 2, pcb_y0 + (pcb[1] - term_depth) / 2,
                   pcb_standoff + pcb[2]]) cube([term_3p_w, term_depth, term_height]);
}

module fitting_dummies() {
    // Bodies of the bought parts, to check nothing shares a space.
    color("gray")
        translate([0, (mains_zone - iec_cut[0]) / 2, (inner_z - iec_cut[1]) / 2])
            cube([iec_depth, iec_cut[0], iec_cut[1]]);
    for (i = [0 : socket_count - 1])
        color("silver")
            translate([socket_x0 + i * socket_pitch, 0, (inner_z - sock_h) / 2])
                cube([sock_w, socket_depth, sock_h]);
}

if (part == "unterteil") unterteil();
else if (part == "deckel") deckel();
else if (part == "explosion") {
    unterteil(); pcb_dummy(); fitting_dummies();
    translate([0, 0, inner_z + 30]) deckel();
} else {
    unterteil(); pcb_dummy(); fitting_dummies();
    translate([outer_x + 15, 0, 0]) deckel();
}

echo(str("Verbindung: ", connection,
         " -- Aussenmass ", outer_x, " x ", outer_y, " x ", outer_z + lid_t, " mm"));
