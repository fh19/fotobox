// Raspberry Pi 4 Model B -- board facts, shared by every case variant here.
//
// Numbers follow the official mechanical drawing. Origin is the board corner on
// the microSD / USB-C side; x runs along the 85 mm edge, y along the 56 mm edge,
// so y = 0 is the HDMI edge and y = 56 the GPIO edge.
//
// Connector centres are measured from that origin. Taking the reference edge
// from the wrong side once already put the RJ45 on the wrong end of the case --
// this file is the only place these numbers live.

pcb_x = 85;
pcb_y = 56;
pcb_t = 1.4;

hole_inset = 3.5;
hole_dx    = 58;
hole_dy    = 49;
hole_pos   = [[hole_inset,           hole_inset],            // 0: front left
              [hole_inset + hole_dx, hole_inset],            // 1: front right
              [hole_inset,           hole_inset + hole_dy],  // 2: rear left
              [hole_inset + hole_dx, hole_inset + hole_dy]]; // 3: rear right

// GPIO header, for clearance checks against pillars and modules
gpio_x0 = 6.35;
gpio_x1 = 57.15;
gpio_y  = 52.5;
gpio_h  = 8.5;

// [edge, centre along that edge, width, height above the PCB, label]
// "front" sits on y = 0, "right" on x = 85. On the Pi 4 ethernet and USB
// swapped places compared to the Pi 3, so counted from the HDMI edge the order
// is USB 2.0, USB 3.0, RJ45.
pi4_ports = [
    ["front", 11.20, 13.0,  5.5, "USB-C power"],
    ["front", 26.00, 12.0,  6.0, "micro HDMI 0"],
    ["front", 39.50, 12.0,  6.0, "micro HDMI 1"],
    ["front", 54.00, 10.0,  8.5, "AV jack"],
    ["right",  9.00, 17.0, 17.5, "USB 2.0 stack"],
    ["right", 27.00, 17.0, 17.5, "USB 3.0 stack"],
    ["right", 45.75, 18.0, 15.5, "RJ45"],
];

// microSD card, on the x = 0 edge and underneath the board
sd_centre = 28;
sd_width  = 16;

// All connector openings, in board coordinates with z = 0 at the PCB top
// surface. `face` is the distance from the board edge to the outer face of the
// case, sd_z0 and sd_h place the microSD opening.
//
// The microSD opening is a funnel, not a slot. The card only sticks out about
// 2 mm past the board edge, so with a 4 mm wall those 2 mm sit at the bottom of
// a tunnel and can only be reached with tweezers. Flaring the opening towards
// the outside puts a fingertip next to the card: at the outer face the mouth is
// sd_w + 2*sd_flare wide, and the 45 degree flanks print without support.
module port_cuts_local(face, sd_z0, sd_h, sd_w = 22, sd_flare = 3.5) {
    depth = face + 2;
    for (p = pi4_ports) {
        if (p[0] == "front")
            translate([p[1] - p[2] / 2, -depth + 1, -1]) cube([p[2], depth, p[3]]);
        else
            translate([pcb_x - 1, p[1] - p[2] / 2, -1]) cube([depth, p[2], p[3]]);
    }
    translate([0, sd_centre, 0]) hull() {
        translate([0, -sd_w / 2, sd_z0])
            cube([1, sd_w, sd_h]);
        translate([-face - 1, -(sd_w + 2 * sd_flare) / 2, sd_z0])
            cube([1, sd_w + 2 * sd_flare, sd_h + sd_flare]);
    }
}
