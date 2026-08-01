// Raspberry Pi 4B enclosure, variant 2: fan sits inside, lid clips on.
//
// Differences to pi4_case.scad:
//   * the 50 x 50 x 10 fan hangs under the lid in a locating pocket instead of
//     sitting on top of it -- the case gets taller inside but stays flat outside
//   * the board is screwed down from above into two domes in the floor
//   * the lid snaps on, four cantilever tabs into a groove in the short walls
//
// Board data and connector positions come from pi4_board.scad.
//
// Export:
//   openscad -D 'part="base"' -o stl/pi4_case_v2_base.stl pi4_case_v2.scad
//   openscad -D 'part="lid"'  -o stl/pi4_case_v2_lid.stl  pi4_case_v2.scad

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
// Clear height above the PCB top. Has to stack the RTC module on the GPIO
// header (~18), a gap, the fan (10) and the pocket it sits in.
inner_h     = 33.0;
comp_h      = 18.0;   // tallest thing on the board, for the clearance check

/* [Board mounting -- 2 x M2.5 x 6, self tapping, from above] */
dome_od     = 7.0;    // the two screwed domes, on one diagonal
post_od     = 6.0;    // the two plain supports, on the other diagonal
pin_od      = 2.4;    // locating pin on the plain supports (PCB hole is 2.7)
pin_h       = 2.5;
screw_pilot = 2.1;
pilot_depth = 5.5;

/* [Snap lid] */
lip_h       = 3.0;    // continuous alignment lip
lip_t       = 1.2;
lip_gap     = 0.2;
tab_n       = 2;      // cantilever tabs per short wall
tab_w       = 14.0;
tab_t       = 1.6;
tab_len     = 6.0;    // free length of the cantilever
tab_pos     = [20, 44];   // along the short wall, from the front edge
bead        = 0.85;   // how far the tab noses into the groove
bead_h      = 2.0;
// The groove ends a touch below the top of the nose, so a seated lid keeps the
// tabs slightly bent and is pulled down onto the wall instead of rattling.
snap_preload = 0.1;
pry_w       = 16.0;   // notch in the rim to get a fingernail under the lid
pry_d       = 1.5;

/* [Fan 50 x 50 x 10, inside] */
// Held by four moulded spring clips, no screws and no local thickening -- the
// lid stays lid_t thick everywhere, and the fan sits straight against it.
fan_size      = 50;
fan_thick     = 10;
fan_bore      = 48;   // air opening in the lid; 1 mm of lid left over the fan
                      // frame at mid side, the corners carry the contact
fan_center    = [36, 27];   // in PCB coordinates, over SoC / RAM
fan_pad       = 2.0;  // rim wall around the fan
fan_fit       = 0;    // pocket clearance on top of the nominal 50 mm, total.
                      // 0 verified on the printed pocket, the fan goes in.
fan_rim_h     = 3.0;  // locating rim the fan drops into
fan_cable_w   = 8.0;  // gap in the rim for the fan lead
fclip_w       = 12.0; // one clip per side, centred
fclip_t       = 1.2;
fclip_lip     = 0.8;  // how far the hook reaches under the fan frame
// Both faces of the hook are ramps. The lid prints on its top face, so the hook
// points upwards: its holding face is the one that overhangs, and at 45 deg it
// still prints without support. The insertion ramp faces upwards while printing
// and is therefore free -- flatter means it clips in more gently.
fclip_bear_a  = 45;   // holding face, from horizontal. Do not go below 45.
fclip_lead_a  = 30;   // insertion ramp, from horizontal
fclip_gap     = 0.6;  // slot each side, so the clip is free of the rim
fan_guard     = true;
fan_guard_rib = 2.6;

/* [Mounting to a plate] */
foot_h     = 5.0;
foot_d     = 10.0;
ear_axis   = "x";
ear_w      = 20.0;
ear_root   = 12.0;
ear_reach  = 10.0;
ear_tip_r  = 7.0;
ear_hole   = 4.5;
ear_offset = 0;

/* [Ventilation] */
vent_w      = 3.2;
vent_gap    = 4.4;
vent_r      = 2.6;

/* ---------------------------------------------------------------- derived */
inner_x = pcb_x + 2 * fit;
inner_y = pcb_y + 2 * fit;
outer_x = inner_x + 2 * wall;
outer_y = inner_y + 2 * wall;
base_h  = floor_t + standoff_h + pcb_t + inner_h;

org_x   = wall + fit;
org_y   = wall + fit;
pcb_bot = floor_t + standoff_h;
pcb_top = pcb_bot + pcb_t;

tab_bot  = base_h - lip_h - tab_len;   // free end of the cantilever
lip_face = wall + lip_gap;             // outer face of lip and tabs

// The groove in the base is the reference, the nose on the lid is placed
// against it: its top ends snap_preload above the top of the groove, so a
// seated lid keeps the tabs slightly bent. Preload therefore lives entirely in
// the lid -- the base stays as it is even when the fit is retuned.
groove_z = tab_bot + 0.65;             // bottom of the groove
groove_h = bead_h + 0.3;
bead_z   = groove_z + groove_h - bead_h + snap_preload;

// fan, hanging from the lid straight against its inner face
fan_open = fan_size + fan_fit;
fan_top  = base_h;
fan_bot  = fan_top - fan_thick;

/* ------------------------------------------------------------- primitives */
module rbox(size, r) {
    linear_extrude(height = size[2])
        offset(r = r, $fn = 32)
            offset(r = -r)
                square([size[0], size[1]]);
}

module at_pcb(x, y, z = 0) {
    translate([org_x + x, org_y + y, pcb_top + z]) children();
}

module at_holes() {
    for (p = hole_pos) translate([org_x + p[0], org_y + p[1], 0]) children();
}

module port_cuts() {
    at_pcb(0, 0, 0)
        port_cuts_local(wall + fit,
                        -(standoff_h + pcb_t),        // opening starts at floor level
                        standoff_h + pcb_t + 4.1);    // and ends above the PCB edge
}

/* ---------------------------------------------------------------- venting */
module vent_field(w, l, count_x, count_y, thickness) {
    difference() {
        for (i = [0 : count_x - 1], j = [0 : count_y - 1])
            translate([i * (w + vent_gap), j * (l + vent_gap), 0])
                rbox([w, l, thickness], min(w, l) / 2 - 0.01);
        children();
    }
}

module keepouts(h) {
    at_holes() cylinder(h = h, d = max(dome_od, post_od, foot_d) + 2 * vent_r);
}

module floor_vents() {
    w  = vent_w;
    l  = 26;
    nx = floor((pcb_x - 16) / (w + vent_gap));
    ny = 2;
    y0 = org_y + (pcb_y - (ny * l + (ny - 1) * vent_gap)) / 2;
    translate([org_x + 8, y0, -1])
        vent_field(w, l, nx, ny, floor_t + 2)
            translate([-(org_x + 8), -y0, 0]) keepouts(floor_t + 4);
}

module slot_y(w, h, d) {
    hull() for (k = [0, 1])
        translate([0, 0, k * (h - w)]) rotate([-90, 0, 0]) cylinder(h = d, d = w);
}

module slot_x(w, h, d) {
    hull() for (k = [0, 1])
        translate([0, 0, k * (h - w)]) rotate([0, 90, 0]) cylinder(h = d, d = w);
}

// The fan pushes air down onto the board, so the exhaust area matters more
// than in variant 1: floor field, rear wall, left wall and the free strip of
// the front wall right of the AV jack.
module wall_vents() {
    sw    = 3.0;
    depth = wall + fit + 2;
    sh    = inner_h - 13;   // stays clear of the snap groove further up

    n     = 9;
    total = n * sw + (n - 1) * vent_gap;
    for (i = [0 : n - 1])
        at_pcb((pcb_x - total) / 2 + sw / 2 + i * (sw + vent_gap), pcb_y - 1, 3)
            slot_y(sw, sh, depth);

    m  = 3;
    lt = m * sw + (m - 1) * vent_gap;
    for (i = [0 : m - 1])
        at_pcb(-(depth - 1), sd_centre - lt / 2 + sw / 2 + i * (sw + vent_gap), 10)
            slot_x(sw, 8, depth);

    f  = 3;   // between the AV jack at x = 59 and the corner
    ft = f * sw + (f - 1) * vent_gap;
    for (i = [0 : f - 1])
        at_pcb(71 - ft / 2 + sw / 2 + i * (sw + vent_gap), -(depth - 1), 3)
            slot_y(sw, 14, depth);
}

/* --------------------------------------------------------- feet and ears */
// No screws come through the floor in this variant, so the feet are solid.
module foot_pads() {
    at_holes() translate([0, 0, -foot_h]) cylinder(h = foot_h, d = foot_d);
}

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

/* -------------------------------------------------------- board mounting */
// Two domes take a screw from above, the other diagonal only carries the board
// and locates it with a pin. Two screws are enough to hold it, four points stop
// it from flexing when connectors are pushed in.
module pcb_mounts() {
    for (i = [0, 3])
        translate([org_x + hole_pos[i][0], org_y + hole_pos[i][1], 0])
            cylinder(h = pcb_bot, d = dome_od);
    for (i = [1, 2])
        translate([org_x + hole_pos[i][0], org_y + hole_pos[i][1], 0]) {
            cylinder(h = pcb_bot, d = post_od);
            cylinder(h = pcb_bot + pcb_t + pin_h, d = pin_od);
        }
}

module pcb_mount_cuts() {
    for (i = [0, 3])
        translate([org_x + hole_pos[i][0], org_y + hole_pos[i][1],
                   pcb_bot - pilot_depth])
            cylinder(h = pilot_depth + 1, d = screw_pilot);
}

/* ---------------------------------------------------------------- snap fit */
// One cantilever tab, hanging off the lid at the wall x = 0 and nosing out in
// -x. The nose is chamfered top and bottom, so the lid clicks in and can be
// pulled off again with a firm pull.
module snap_tab() {
    translate([lip_face, -tab_w / 2, tab_bot]) cube([tab_t, tab_w, tab_len]);
    hull() {
        translate([lip_face - eps, -tab_w / 2, bead_z]) cube([eps, tab_w, bead_h]);
        translate([lip_face - bead, -tab_w / 2, bead_z + 0.7])
            cube([eps, tab_w, bead_h - 1.4]);
    }
}

module snap_tabs() {
    for (p = tab_pos) {
        translate([0, p, 0]) snap_tab();
        translate([outer_x, p, 0]) mirror([1, 0, 0]) snap_tab();
    }
}

// Matching groove, running along both short walls.
module snap_groove() {
    gh = groove_h;
    gz = groove_z;
    gd = bead + 0.05;
    for (x0 = [wall - gd, outer_x - wall - 0.1])
        translate([x0, corner_r + 2, gz])
            cube([gd + 0.1, outer_y - 2 * (corner_r + 2), gh]);
}

// Notch in the rim between the tabs, to get a fingernail under the lid.
module pry_notches() {
    for (x0 = [-0.1, outer_x - pry_d])
        translate([x0, outer_y / 2 - pry_w / 2, base_h - 2])
            cube([pry_d + 0.1, pry_w, 3]);
}

/* ------------------------------------------------------------------- base */
module base() {
    difference() {
        union() {
            difference() {
                rbox([outer_x, outer_y, base_h], corner_r);
                translate([wall, wall, floor_t])
                    rbox([inner_x, inner_y, base_h], max(corner_r - wall, 0.1));
            }
            pcb_mounts();
            foot_pads();
            ears();
        }
        pcb_mount_cuts();
        port_cuts();
        floor_vents();
        wall_vents();
        snap_groove();
        pry_notches();
    }
}

/* -------------------------------------------------------------------- lid */
// One spring clip, sitting on the -x side of the fan and hooking inwards under
// its frame. Origin is the fan centre, z = 0 the lid inner face.
module fan_clip() {
    xi   = -fan_open / 2;                   // face the fan rests against
    hook = fclip_lip / tan(fclip_bear_a);   // drop of the holding face
    lead = fclip_lip / tan(fclip_lead_a);   // drop of the insertion ramp
    len  = fan_thick + hook + lead;
    translate([xi - fclip_t, -fclip_w / 2, -len]) cube([fclip_t, fclip_w, len]);
    // The holding face starts exactly at the underside of the fan, so the fan
    // has no play, and slopes away from there -- no square shoulder anywhere.
    // The back of the profile reaches into the clip body; sharing a face
    // exactly would leave the union non-manifold.
    translate([0, fclip_w / 2, 0]) rotate([90, 0, 0])
        linear_extrude(fclip_w)
            polygon([[xi - fclip_t / 2, -fan_thick],
                     [xi,               -fan_thick],
                     [xi + fclip_lip,   -fan_thick - hook],
                     [xi,               -fan_thick - hook - lead],
                     [xi - fclip_t / 2, -fan_thick - hook - lead]]);
}

module fan_pocket() {
    s = fan_open + 2 * fan_pad;
    difference() {
        at_pcb(fan_center[0] - s / 2, fan_center[1] - s / 2, inner_h - fan_rim_h)
            rbox([s, s, fan_rim_h], 4);
        at_pcb(fan_center[0] - fan_open / 2, fan_center[1] - fan_open / 2,
               inner_h - fan_rim_h - 1)
            rbox([fan_open, fan_open, fan_rim_h + 2], 3);
        // way out for the fan lead, at the corner nearest the GPIO header
        at_pcb(fan_center[0] - s / 2 - 1, fan_center[1] + s / 2 - fan_cable_w,
               inner_h - fan_rim_h - 1)
            cube([fan_pad + 2, fan_cable_w, fan_rim_h + 2]);
        // free the clips from the rim, otherwise they are braced at the root
        // and only bend over their upper part
        at_pcb(fan_center[0], fan_center[1], inner_h - fan_rim_h - 1)
            for (a = [0, 90, 180, 270]) rotate([0, 0, a])
                translate([-s, -(fclip_w + 2 * fclip_gap) / 2, 0])
                    cube([s, fclip_w + 2 * fclip_gap, fan_rim_h + 2]);
    }
    at_pcb(fan_center[0], fan_center[1], inner_h)
        for (a = [0, 90, 180, 270]) rotate([0, 0, a]) fan_clip();
}

module fan_cuts() {
    at_pcb(fan_center[0], fan_center[1], inner_h)
        translate([0, 0, -1]) cylinder(h = lid_t + 2, d = fan_bore);
}

module fan_guard() {
    if (fan_guard)
        at_pcb(fan_center[0], fan_center[1], inner_h)
            intersection() {
                // slightly wider than the bore, so the ribs bite into the plate
                // instead of sharing a surface with it -- that is not manifold
                cylinder(h = lid_t, d = fan_bore + 0.4);
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
                translate([0, 0, base_h]) rbox([outer_x, outer_y, lid_t], corner_r);
                translate([0, 0, base_h - lip_h])
                    difference() {
                        translate([lip_face, lip_face, 0])
                            rbox([inner_x - 2 * lip_gap, inner_y - 2 * lip_gap, lip_h],
                                 max(corner_r - wall, 0.1));
                        translate([lip_face + lip_t, lip_face + lip_t, -eps])
                            rbox([inner_x - 2 * (lip_gap + lip_t),
                                  inner_y - 2 * (lip_gap + lip_t), lip_h + 1], 0.6);
                    }
                snap_tabs();
                fan_pocket();
            }
            fan_cuts();
        }
        fan_guard();
    }
}

module lid_cut() {
    difference() {
        lid();
        port_cuts();
    }
}

/* ----------------------------------------------------------------- dummies */
module fan_dummy() {
    color("#404040", 0.6)
        at_pcb(fan_center[0], fan_center[1], 0)
            translate([0, 0, fan_bot - pcb_top])
                difference() {
                    translate([-fan_size / 2, -fan_size / 2, 0])
                        rbox([fan_size, fan_size, fan_thick], 4);
                    translate([0, 0, -eps]) cylinder(h = fan_thick + 1, d = fan_size - 3);
                }
}

module pcb_dummy() {
    color("#1a6b33")
        translate([org_x, org_y, pcb_bot]) cube([pcb_x, pcb_y, pcb_t]);
    color("#8b1a1a")                                  // RTC module, for the eye
        at_pcb(gpio_x0, 30, 11.0) cube([27, 26, 1.6]);
}

/* ------------------------------------------------------------------ build */
echo(str("clearance fan to tallest part: ", fan_bot - pcb_top - comp_h, " mm"));

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
