// Raspberry Pi 4B enclosure with a 50 x 50 x 10 mm fan mounted on the lid.
//
// All dimensions in mm and parametric -- nothing is baked into the geometry.
// Board data and connector positions come from pi4_board.scad.
//
// Assembly: the PCB rests on four standoffs in the base. Four M2.5 screws enter
// from underneath, pass through base standoff and PCB, and thread into the four
// pillars of the lid. That single screw set clamps board and lid at once.
//
// Export:
//   openscad -D 'part="base"' -o stl/pi4_case_base.stl pi4_case.scad
//   openscad -D 'part="lid"'  -o stl/pi4_case_lid.stl  pi4_case.scad

include <pi4_board.scad>

/* [Render] */
part = "both";        // "base" | "lid" | "both" | "assembly"

$fa = 2;
$fs = 0.4;
eps = 0.01;

/* [Enclosure] */
fit         = 1.6;    // gap between PCB edge and inner wall, per side
wall        = 2.4;
floor_t     = 3.0;
lid_t       = 2.4;
corner_r    = 3.0;
standoff_h  = 3.5;    // clear space under the PCB (microSD, solder joints)
standoff_od = 6.0;
// Clear height above the PCB top surface. 18 would be enough for the bare board
// (tallest part: USB stack, 15.6). 24 leaves room for the RTC module sitting on
// the GPIO header: socket ~11 + module PCB 1.6 + battery holder ~5 = ~18.
inner_h     = 24.0;
lip_h       = 2.5;    // lid lip reaching into the base
lip_t       = 1.2;
lip_gap     = 0.2;

/* [Screws -- 4x M2.5 x 16, self tapping into plastic] */
screw_clear  = 2.9;
screw_head   = 5.4;
screw_head_h = 1.8;
screw_pilot  = 2.1;
pilot_depth  = 12;    // M2.5 x 16 engages ~10 mm, so the screw never bottoms out
pillar_od    = 5.0;   // stays clear of the GPIO header body (starts at x = 6.35)

/* [Fan 50 x 50 x 10] */
fan_size      = 50;
fan_thick     = 10;   // informational, the fan sits on top of the lid
fan_bolt      = 40;   // bolt circle, square pattern
fan_bolt_dia  = 4.4;  // clearance for M4 / self tapping fan screws
fan_bore      = 46;   // air opening in the lid
fan_center    = [36, 27];   // in PCB coordinates, over SoC / RAM
fan_guard     = true;
fan_guard_rib = 2.6;

/* [Fan cable pass-through to GPIO pin 4/6] */
cable_slot    = [10, 6];    // width x depth, deep enough to reach both pin rows
cable_pos     = [13, 53.0]; // in PCB coordinates

/* [Mounting to a plate] */
// The case stands on four feet, so the floor slots exhaust into the gap
// underneath. Two ears reach out to the same plane and take the M4 screws.
foot_h     = 5.0;     // gap between plate and case floor
foot_d     = 10.0;    // feet sit under the four PCB screw bosses
ear_axis   = "x";     // "x" = ears on the short walls, "y" = on the long walls
ear_w      = 20.0;    // ear width where it meets the case
ear_root   = 12.0;    // how far the ear reaches back under the floor
ear_reach  = 10.0;    // screw hole distance from the outer wall
ear_tip_r  = 7.0;
ear_hole   = 4.5;     // M4 clearance
ear_offset = 0;       // shifts both ears along their wall, e.g. clear of the
                      // microSD slot (needs +19 for that)

/* [Ventilation] */
vent_w      = 3.2;
vent_gap    = 4.4;
vent_r      = 2.6;    // clearance kept around standoffs, pillars and feet

/* ---------------------------------------------------------------- derived */
inner_x = pcb_x + 2 * fit;
inner_y = pcb_y + 2 * fit;
outer_x = inner_x + 2 * wall;
outer_y = inner_y + 2 * wall;
base_h  = floor_t + standoff_h + pcb_t + inner_h;

org_x   = wall + fit;         // PCB origin, world coordinates
org_y   = wall + fit;
pcb_bot = floor_t + standoff_h;
pcb_top = pcb_bot + pcb_t;

/* ------------------------------------------------------------- primitives */
module rbox(size, r) {
    linear_extrude(height = size[2])
        offset(r = r, $fn = 32)
            offset(r = -r)
                square([size[0], size[1]]);
}

// child placed at a PCB coordinate, z measured from the PCB top surface
module at_pcb(x, y, z = 0) {
    translate([org_x + x, org_y + y, pcb_top + z]) children();
}

module at_holes() {
    for (p = hole_pos) translate([org_x + p[0], org_y + p[1], 0]) children();
}

/* ------------------------------------------------------------ port cutouts */
// Cut once out of the base walls and once out of the lid, so the lid lip is
// automatically clipped away wherever a connector needs the full height.
module port_cuts() {
    at_pcb(0, 0, 0)
        port_cuts_local(wall + fit,
                        -(standoff_h + pcb_t),        // opening starts at floor level
                        standoff_h + pcb_t + 4.1);    // and ends above the PCB edge
}

/* ---------------------------------------------------------------- venting */
// Slot field, with the standoff and pillar footprints kept clear.
module vent_field(w, l, count_x, count_y, thickness) {
    difference() {
        for (i = [0 : count_x - 1], j = [0 : count_y - 1])
            translate([i * (w + vent_gap), j * (l + vent_gap), 0])
                rbox([w, l, thickness], min(w, l) / 2 - 0.01);
        children();
    }
}

module floor_vents() {
    w = vent_w;
    l = 26;
    nx = floor((pcb_x - 16) / (w + vent_gap));
    ny = 2;
    translate([org_x + 8, org_y + (pcb_y - (ny * l + (ny - 1) * vent_gap)) / 2, -1])
        vent_field(w, l, nx, ny, floor_t + 2)
            translate([-(org_x + 8), -(org_y + (pcb_y - (ny * l + (ny - 1) * vent_gap)) / 2), 0])
                keepouts(floor_t + 4);
}

module keepouts(h) {
    at_holes() cylinder(h = h, d = max(standoff_od, pillar_od) + 2 * vent_r);
}

// Rounded slot standing upright, extruded along +y (for the front/rear walls).
module slot_y(w, h, d) {
    hull() for (k = [0, 1])
        translate([0, 0, k * (h - w)]) rotate([-90, 0, 0]) cylinder(h = d, d = w);
}

// Same, extruded along +x (for the left/right walls).
module slot_x(w, h, d) {
    hull() for (k = [0, 1])
        translate([0, 0, k * (h - w)]) rotate([0, 90, 0]) cylinder(h = d, d = w);
}

module wall_vents() {
    sw    = 3.0;
    depth = wall + fit + 2;

    // rear wall (PCB local y = 56) -- the only long edge without connectors
    n     = 9;
    sh    = inner_h - 6;
    total = n * sw + (n - 1) * vent_gap;
    for (i = [0 : n - 1])
        at_pcb((pcb_x - total) / 2 + sw / 2 + i * (sw + vent_gap), pcb_y - 1, 3)
            slot_y(sw, sh, depth);

    // left wall, above the microSD opening
    m  = 3;
    lt = m * sw + (m - 1) * vent_gap;
    for (i = [0 : m - 1])
        at_pcb(-(depth - 1), 28 - lt / 2 + sw / 2 + i * (sw + vent_gap), 10)
            slot_x(sw, 8, depth);
}

/* --------------------------------------------------------- feet and ears */
// Feet sit right under the four PCB screw bosses, so the load goes straight
// from the plate into the standoffs. The screw head pocket is drilled down
// through them, which keeps the M2.5 x 16 screws from before.
module foot_pads() {
    at_holes() translate([0, 0, -foot_h]) cylinder(h = foot_h, d = foot_d);
}

// One ear, reaching out in -x from the wall at x = 0. The root runs back
// under the floor, that is what actually carries the load.
module ear() {
    difference() {
        hull() {
            translate([0, -ear_w / 2, -foot_h]) cube([ear_root, ear_w, foot_h]);
            translate([-ear_reach, 0, -foot_h]) cylinder(h = foot_h, r = ear_tip_r);
        }
        translate([-ear_reach, 0, -foot_h - 1]) cylinder(h = foot_h + 2, d = ear_hole);
    }
}

module ears() {
    if (ear_axis == "x") {
        translate([0, outer_y / 2 + ear_offset, 0]) ear();
        translate([outer_x, outer_y / 2 + ear_offset, 0]) mirror([1, 0, 0]) ear();
    } else {
        translate([outer_x / 2 + ear_offset, 0, 0]) rotate([0, 0, 90]) ear();
        translate([outer_x / 2 + ear_offset, outer_y, 0]) rotate([0, 0, -90]) ear();
    }
}

/* ------------------------------------------------------------------- base */
module base() {
    difference() {
        union() {
            // shell
            difference() {
                rbox([outer_x, outer_y, base_h], corner_r);
                translate([wall, wall, floor_t])
                    rbox([inner_x, inner_y, base_h], max(corner_r - wall, 0.1));
            }
            // PCB standoffs
            at_holes() cylinder(h = pcb_bot, d = standoff_od);
            foot_pads();
            ears();
        }
        // screw through holes; the head pocket carries on down through the foot
        // so the screw can still be fitted from below
        at_holes() {
            translate([0, 0, -foot_h - eps]) cylinder(h = pcb_bot + foot_h + 1, d = screw_clear);
            translate([0, 0, -foot_h - eps])
                cylinder(h = foot_h + screw_head_h + eps, d = screw_head);
        }
        port_cuts();
        floor_vents();
        wall_vents();
    }
}

/* -------------------------------------------------------------------- lid */
module fan_mount() {
    at_pcb(fan_center[0], fan_center[1], inner_h) {
        // air opening
        translate([0, 0, -1]) cylinder(h = lid_t + 2, d = fan_bore);
        // fan screws
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * fan_bolt / 2, sy * fan_bolt / 2, -1])
                cylinder(h = lid_t + 2, d = fan_bolt_dia);
    }
}

module fan_guard() {
    if (fan_guard)
        at_pcb(fan_center[0], fan_center[1], inner_h)
            intersection() {
                cylinder(h = lid_t, d = fan_bore);
                union() {
                    cylinder(h = lid_t, d = fan_guard_rib * 3);
                    for (a = [0 : 60 : 179])
                        rotate([0, 0, a])
                            translate([-fan_bore / 2, -fan_guard_rib / 2, 0])
                                cube([fan_bore, fan_guard_rib, lid_t]);
                    difference() {
                        cylinder(h = lid_t, d = fan_bore * 0.68);
                        cylinder(h = lid_t, d = fan_bore * 0.68 - 2 * fan_guard_rib);
                    }
                }
            }
}

module lid() {
    union() {
    difference() {
        union() {
            translate([0, 0, base_h])
                rbox([outer_x, outer_y, lid_t], corner_r);
            // lip reaching down into the base
            translate([0, 0, base_h - lip_h])
                difference() {
                    translate([wall + lip_gap, wall + lip_gap, 0])
                        rbox([inner_x - 2 * lip_gap, inner_y - 2 * lip_gap, lip_h],
                             max(corner_r - wall, 0.1));
                    translate([wall + lip_gap + lip_t, wall + lip_gap + lip_t, -eps])
                        rbox([inner_x - 2 * (lip_gap + lip_t),
                              inner_y - 2 * (lip_gap + lip_t), lip_h + 1], 0.6);
                }
            // pillars down onto the PCB mounting holes
            translate([0, 0, pcb_top])
                at_holes() cylinder(h = inner_h, d = pillar_od);
        }
        translate([0, 0, pcb_top])
            at_holes() translate([0, 0, -eps])
                cylinder(h = pilot_depth, d = screw_pilot);
        fan_mount();
        // fan cable down to the GPIO header
        at_pcb(cable_pos[0] - cable_slot[0] / 2, cable_pos[1] - cable_slot[1] / 2, inner_h - 1)
            rbox([cable_slot[0], cable_slot[1], lid_t + 2], cable_slot[1] / 2 - 0.01);
    }
    fan_guard();   // added after the bore, otherwise the bore would cut it away
    }
}

module lid_cut() {
    difference() {
        lid();
        port_cuts();
    }
}

/* ------------------------------------------------------------- fan dummy */
module fan_dummy() {
    color("#404040", 0.6)
        at_pcb(fan_center[0], fan_center[1], inner_h + lid_t)
            difference() {
                translate([-fan_size / 2, -fan_size / 2, 0])
                    rbox([fan_size, fan_size, fan_thick], 4);
                translate([0, 0, -eps]) cylinder(h = fan_thick + 1, d = fan_size - 3);
            }
}

module pcb_dummy() {
    color("#1a6b33")
        translate([org_x, org_y, pcb_bot]) cube([pcb_x, pcb_y, pcb_t]);
}

/* ------------------------------------------------------------------ build */
// Internal z = 0 is the case floor, the feet reach below it. Lifting everything
// by foot_h puts the mounting plane at z = 0, where the slicer wants it.
translate([0, 0, foot_h]) {
    if (part == "base") base();
    else if (part == "lid") lid_cut();
    else if (part == "assembly") {
        base();
        color("#c8c8c8") lid_cut();
        pcb_dummy();
        fan_dummy();
    } else if (part == "both") {
        base();
        translate([0, outer_y + 10, 0]) lid_cut();
    }
}
// any other value renders nothing -- handy when including this file from a
// check script that builds its own scene
