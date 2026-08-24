// Mains switch box for the photo lamp, to be built into the Fotobox enclosure.
//
// Holds: the SSR on a small board between a 2-pole control terminal and a
// 3-pole lamp terminal, a 1 A fuse holder, three Euro sockets feeding the box
// itself, and one gland for the incoming mains.
//
// The floor carries a rib that splits the inside in two: mains on the socket
// side, the 3.3 V control lead on the other, each with its own way in. That rib
// is the only reason this print is worth more than a cardboard box.
//
// Origin is the inner floor corner on the gland side. x runs along the socket
// wall, y from the socket wall towards the control side, z upwards.

include <schaltbox_parts.scad>

part = "beides";   // "unterteil" | "deckel" | "beides" | "explosion"
$fn = 64;

// --- derived sizes ----------------------------------------------------------

socket_span  = socket_count * socket_cut[0] + (socket_count - 1) * socket_gap;
inner_x      = max(socket_span + 2 * creep_gap,
                   fuse_depth + 2 * creep_gap,
                   pcb[0] + 2 * creep_gap);

// Behind the socket bodies runs a strip that belongs to the mains side alone:
// the incoming cable lands here, the fuse holder reaches into it from the right
// wall, and the wires to the sockets run along it. Without that strip the fuse
// holder ends up inside the third socket -- 32 mm reach into a 26 mm deep row.
mains_strip  = 25;
rib_y        = socket_depth + mains_strip;
rib_t        = 2.4;

inner_y      = rib_y + rib_t + creep_gap + pcb[1] + creep_gap;
inner_z      = max(ssr_body[2] + pcb_standoff + pcb[2] + 6,
                   fuse_hole_d + 2 * creep_gap,
                   socket_cut[1] + 4);

outer_x = inner_x + 2 * wall;
outer_y = inner_y + 2 * wall;
outer_z = inner_z + floor_t;

// Everything that pierces a short wall sits in that strip, clear of the sockets.
service_y = socket_depth + mains_strip / 2;

// Board position: centred in x, in the control-side half.
pcb_x0  = (inner_x - pcb[0]) / 2;
pcb_y0  = rib_y + rib_t + creep_gap / 2;

module pcb_hole_positions() {
    for (dx = [pcb_inset, pcb[0] - pcb_inset])
        for (dy = [pcb_inset, pcb[1] - pcb_inset])
            translate([pcb_x0 + dx, pcb_y0 + dy, 0]) children();
}

module lid_boss_positions() {
    // Pulled 0.8 mm into the corner so the bosses cut into the walls instead
    // of standing tangent to them.
    for (x = [boss_d / 2 - 0.8, inner_x - boss_d / 2 + 0.8])
        for (y = [boss_d / 2 - 0.8, inner_y - boss_d / 2 + 0.8])
            translate([x, y, 0]) children();
}

// --- cutouts ----------------------------------------------------------------

module socket_cutouts() {
    x0 = (inner_x - socket_span) / 2;
    z0 = (inner_z - socket_cut[1]) / 2;
    for (i = [0 : socket_count - 1]) {
        cx = x0 + i * (socket_cut[0] + socket_gap) + socket_cut[0] / 2;
        // Start outside the wall: rotate([-90,0,0]) sends +z to +y, so a cut
        // that begins at y = -1 leaves the outer millimetres of the wall
        // standing and the socket never breaks through.
        translate([cx, -wall - 1, z0 + socket_cut[1] / 2])
            rotate([-90, 0, 0])
                if (socket_round)
                    cylinder(d = socket_cut[0], h = wall + 2);
                else
                    linear_extrude(wall + 2)
                        offset(r = 1.5) offset(r = -1.5)
                            square([socket_cut[0], socket_cut[1]], center = true);
    }
}

module gland_hole() {
    // Left short wall, in the mains half.
    translate([-wall - gland_boss_len - 1, service_y, inner_z / 2])
        rotate([0, 90, 0])
            cylinder(d = gland_hole_d, h = wall + gland_boss_len + 3);
}

module gland_boss() {
    translate([0, service_y, inner_z / 2])
        rotate([0, 90, 0])
            difference() {
                translate([0, 0, -gland_boss_len])
                    cylinder(d = gland_boss_d, h = gland_boss_len);
                translate([0, 0, -gland_boss_len - 1])
                    cylinder(d = gland_hole_d, h = gland_boss_len + 2);
            }
}

module fuse_hole() {
    // Right short wall, reachable without opening the box.
    translate([inner_x - 1, service_y, inner_z / 2])
        rotate([0, 90, 0]) cylinder(d = fuse_hole_d, h = wall + 2);
}

module control_hole() {
    // Rear wall, on the control side of the rib. Its own way in on purpose.
    translate([inner_x / 2, inner_y + 1, inner_z / 2])
        rotate([90, 0, 0]) cylinder(d = ctrl_hole_d, h = wall + 2);
}

// --- parts ------------------------------------------------------------------

module unterteil() {
    difference() {
        union() {
            // shell
            translate([-wall, -wall, -floor_t])
                cube([outer_x, outer_y, outer_z]);
            translate([-wall, -wall, -floor_t]) gland_boss_shift();
            mounting_ears();
        }
        // hollow
        translate([0, 0, 0]) cube([inner_x, inner_y, inner_z + 1]);
        socket_cutouts();
        gland_hole();
        fuse_hole();
        control_hole();
        // lid screws
        lid_boss_positions()
            translate([0, 0, inner_z - 12]) cylinder(d = screw_pilot, h = 14);
    }
    // things that live inside
    separation_rib();
    pcb_standoffs();
    lid_bosses();
}

module gland_boss_shift() {
    translate([wall, wall, floor_t]) gland_boss();
}

module separation_rib() {
    // Full height minus a little, so the lid does not have to fight it. It
    // reaches 0.5 mm into both side walls: faces that merely touch leave a
    // non-manifold seam, and slicers take that badly.
    translate([-0.5, rib_y - rib_t / 2, -0.5])
        cube([inner_x + 1, rib_t, inner_z - 1.5]);
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
    // Two ears on the rear wall: this box screws into the Fotobox enclosure.
    for (x = [outer_x * 0.25, outer_x * 0.75])
        translate([x - wall, outer_y - wall - 1, -floor_t])
            difference() {
                translate([-ear_len / 2, 0, 0])
                    cube([ear_len, ear_len + 1, floor_t]);
                translate([0, ear_len * 0.6, -1])
                    cylinder(d = ear_hole_d, h = floor_t + 2);
            }
}

module deckel() {
    difference() {
        union() {
            translate([-wall, -wall, 0]) cube([outer_x, outer_y, lid_t]);
            // lip that drops into the shell, so there is no straight gap
            translate([clearance, clearance, -3])
                cube([inner_x - 2 * clearance, inner_y - 2 * clearance, 3]);
        }
        lid_boss_positions()
            translate([0, 0, -4]) cylinder(d = screw_d + 0.4, h = lid_t + 6);
        lid_boss_positions()
            translate([0, 0, lid_t - 1.8]) cylinder(d = screw_d * 2, h = 2);
        // the rib needs somewhere to go
        translate([-1, rib_y - clearance, -3.1])
            cube([inner_x + 2, rib_t + 2 * clearance, 3.2]);
    }
}

// --- assembly view ----------------------------------------------------------

module ssr_dummy() {
    color("dimgray") translate([pcb_x0 + term_2p_w + 4, pcb_y0 + (pcb[1] - ssr_body[1]) / 2,
                                pcb_standoff + pcb[2]])
        cube(ssr_body);
}

module pcb_dummy() {
    color("darkgreen")
        translate([pcb_x0, pcb_y0, pcb_standoff]) cube(pcb);
    ssr_dummy();
    color("cornflowerblue")  // 2-pole, control
        translate([pcb_x0 + 2, pcb_y0 + (pcb[1] - term_depth) / 2, pcb_standoff + pcb[2]])
            cube([term_2p_w, term_depth, term_height]);
    color("indianred")       // 3-pole, lamp
        translate([pcb_x0 + pcb[0] - term_3p_w - 2, pcb_y0 + (pcb[1] - term_depth) / 2,
                   pcb_standoff + pcb[2]])
            cube([term_3p_w, term_depth, term_height]);
}

if (part == "unterteil") unterteil();
else if (part == "deckel") deckel();
else if (part == "explosion") {
    unterteil();
    pcb_dummy();
    translate([0, 0, inner_z + 25]) deckel();
} else {
    unterteil();
    pcb_dummy();
    translate([outer_x + 15, 0, 0]) deckel();
}

echo(str("Aussenmass: ", outer_x, " x ", outer_y, " x ", outer_z + lid_t, " mm"));
