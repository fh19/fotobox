// Fotobox enclosure -- 400 x 236 x 438 mm carcass from 18 mm glued panel.
//
// Panel numbers follow the hand sketch:
//   1 front, 2 back (door), 3a upper right, 3b lower right, 4 left,
//   5 bottom, 6 top and the two shelves, plus 24 x 48 rails under the shelves.
//
// Construction: front (1) and back (2) are full size panels that cover the
// front and rear edges of both sides. The sides (3a/3b, 4) stand on the bottom
// (5), which carries the whole footprint. Top (6) and both shelves are inset
// boards between the sides. The right side is split into 3a and 3b, the gap
// between them is the slot the lower shelf -- the one the printer stands on --
// runs in. That shelf is long: it sticks out about 200 mm past the right side
// and carries the printer's paper cassette, and it can be pulled out completely
// for transport. The back is a door.
//
// The display is only partly let in: it is screwed onto the outside of the front
// panel, only the bulge on its back (320 x 110) passes through a notch that
// reaches down to the lower edge of the front panel. That notch, not a window,
// is the only opening for the display.
//
// Coordinates: x to the right, y to the back, z up, origin at the front left
// bottom corner. Every panel module is authored lying flat (x = length,
// y = width, z = thickness), so the same geometry serves the assembly and the
// cut list view.
//
// Views:
//   openscad fotobox_case.scad                            assembly
//   openscad -D 'part="exploded"' fotobox_case.scad       panels pulled apart
//   openscad -D 'part="cutlist"'  fotobox_case.scad       all boards laid flat
//   openscad -D 'part="front"' -o front.stl ...           one board
//
// The echo output on the console is the cut list plus the clearance checks.

/* [Render] */
part = "assembly";   // "assembly" | "exploded" | "cutlist" | "front" | "back" | "left" | "right_upper" | "right_lower" | "bottom" | "top" | "shelf" | "rail"
show_contents = true;    // ghost volumes of display, camera, printer, Pi
door_angle    = 0;       // back door, 0 = closed, up to 110
pullout       = 0;       // how far the printer shelf is pulled out to the right
explode_gap   = 130;     // used by part="exploded"

$fa = 2;
$fs = 1.2;
eps = 0.01;

/* [Material] */
t       = 18;   // panel thickness
rail_w  = 48;   // 24 x 48 rail, lying flat: 48 across, 24 high
rail_h  = 24;

/* [Carcass] */
width   = 400;  // outer width, front and back panel
inner_d = 200;  // depth of the side panels -> outer depth = inner_d + 2 * t
side_h  = 420;  // height of the side, front and back panels

/* [Front openings] */
// Notch for the bulge on the back of the display. It is open towards the lower
// edge of the front panel, so the display hangs as low as the panel allows.
bulge_w   = 320;
bulge_h   = 100;
bulge_d   = 25;   // how far the bulge stands off the display, incl. the panel
bulge_r   = 6;    // corner radius of the two upper corners, router bit
webcam_d  = 26;   // preview camera
webcam_z  = 305;  // axis over the floor
lens_d    = 85;   // main camera, clears the lens barrel
lens_z    = 369;  // optical axis over the floor, = shelf + riser + camera_axis
edge_min  = 12;   // smallest strip of wood left next to an opening

/* [Compartments] */
// The lower bay is exactly as high as the bulge, so the printer shelf clears it.
base_bay    = bulge_h;  // 3b, holds Pi, power supply and wiring
printer_bay = 100;      // clear height over the printer shelf
slot_play   = 0;        // extra height of the pull out slot, 1 mm gives the shelf air

/* [Printer shelf and window] */
shelf_over = 198;  // how far the shelf sticks out past the right side
pwin_len   = 150;  // window in 3a, along the box depth, sits centred
pwin_h     = 95;   // over the shelf; the window is open towards the slot

/* [Shelf rails] */
rail_y1 = 68;     // front rail, clear of the display body
rail_y2 = 170;    // back rail

/* [Contents, for the clearance check only] */
display   = [360, 40, 210];   // display outline in front of the panel, W x D x H
printer   = [133, 181, 68];   // Canon Selphy CP1500, D x W x H -- front faces right
cassette  = [95, 130, 35];    // paper cassette, sticks out through the window
camera    = [131, 80, 96];    // DSLR body, W x D x H
camera_riser = 60;            // plate, ball head or block, keeps the axis at lens_z
camera_axis  = 55;            // optical axis over the camera base
lens_len  = 90;
pi        = [127, 64, 49];    // printed Pi case, see ../pi4-fan-case

/* [Derived] */
depth     = inner_d + 2 * t;              // 236
inner_w   = width - 2 * t;                // 364
total_h   = side_h + t;                   // 438
slot_h    = t + slot_play;                // pull out slot in the right side
shelf_p_z = t + base_bay;                 // underside of the printer shelf, 128
shelf_c_z = shelf_p_z + slot_h + printer_bay;   // underside of the camera shelf, 266
shelf_p_l = inner_w + t + shelf_over;     // long printer shelf, 580
right_lo  = base_bay;                     // 3b, 110
right_up  = total_h - shelf_p_z - slot_h; // 3a, 292
top_z     = total_h - t;                  // 420
cam_bay   = top_z - (shelf_c_z + t);      // clear height over the camera shelf

// A feature at height Z sits at this local y on front, back and side panels,
// all of which start at z = t.
function fz(z) = z - t;

/* [Colours] */
c_fb    = [0.85, 0.72, 0.50];
c_side  = [0.78, 0.64, 0.44];
c_shelf = [0.90, 0.80, 0.60];
c_rail  = [0.62, 0.48, 0.32];

// ---------------------------------------------------------------- panels ---
// All authored lying flat: x = length, y = width, z = thickness.

module rrect(w, h, r) {
  hull() for (x = [r, w - r], y = [r, h - r]) translate([x, y]) circle(r);
}

// Rectangle with two rounded upper corners, open at the bottom edge.
module notch(w, h, r) {
  hull() {
    for (x = [r, w - r]) translate([x, h - r]) circle(r);
    translate([0, -1]) square([w, 1]);
  }
}

// 1 -- front: notch for the display bulge at the lower edge, two camera holes
module p_front() {
  difference() {
    cube([width, side_h, t]);
    translate([(width - bulge_w) / 2, 0, -eps])
      linear_extrude(t + 2 * eps) notch(bulge_w, bulge_h, bulge_r);
    translate([width / 2, fz(webcam_z), -eps]) cylinder(d = webcam_d, h = t + 2 * eps);
    translate([width / 2, fz(lens_z),   -eps]) cylinder(d = lens_d,   h = t + 2 * eps);
  }
}

// 2 -- back, same blank, hinged as a door
module p_back() {
  cube([width, side_h, t]);
}

// 4 -- left side
module p_left() {
  cube([inner_d, side_h, t]);
}

// 3a -- upper right side, notched for the printer window. The notch is open
// towards the slot underneath, so cassette and print pass through in one piece.
module p_right_upper() {
  difference() {
    cube([inner_d, right_up, t]);
    translate([(inner_d - pwin_len) / 2, -eps, -eps])
      cube([pwin_len, pwin_h + eps, t + 2 * eps]);
  }
}

// 3b -- lower right side
module p_right_lower() {
  cube([inner_d, right_lo, t]);
}

// 5 -- bottom, full footprint
module p_bottom() {
  cube([width, depth, t]);
}

// 6 -- top and camera shelf, identical inset boards
module p_shelf() {
  cube([inner_w, inner_d, t]);
}

// Printer shelf: runs through the slot in the right side and sticks out, the
// overhang carries the paper cassette.
module p_shelf_printer() {
  cube([shelf_p_l, inner_d, t]);
}

// 24 x 48 rail under a shelf, spans the full inner width
module p_rail() {
  cube([inner_w, rail_w, rail_h]);
}

// -------------------------------------------------------------- assembly ---

// Rotates a flat panel so that local x runs along global y and local y up.
module stand_up() {
  rotate([0, 0, 90]) rotate([90, 0, 0]) children();
}

module case_assembly(ex = 0, door = 0, pull = 0) {
  color(c_side) translate([0, 0, -ex]) p_bottom();                        // 5

  color(c_fb) translate([0, t - ex, t]) rotate([90, 0, 0]) p_front();     // 1

  color(c_fb)                                                             // 2
    translate([0, depth + ex, 0]) rotate([0, 0, door]) translate([0, -depth, 0])
      translate([0, depth, t]) rotate([90, 0, 0]) p_back();

  color(c_side) translate([-ex, t, t]) stand_up() p_left();               // 4

  color(c_side) translate([width - t + ex, t, t])                         // 3b
    stand_up() p_right_lower();

  color(c_side) translate([width - t + ex, t, shelf_p_z + slot_h])        // 3a
    stand_up() p_right_upper();

  color(c_shelf) translate([t, t, top_z + ex]) p_shelf();                 // 6 top
  color(c_shelf) translate([t, t, shelf_c_z]) p_shelf();                  // 6 camera shelf
  color(c_shelf) translate([t + pull + ex, t, shelf_p_z])                 // printer shelf
    p_shelf_printer();

  color(c_rail) for (z = [shelf_p_z - rail_h, shelf_c_z - rail_h])
    for (y = [rail_y1, rail_y2])
      translate([t, y, z]) p_rail();
}

// ------------------------------------------------------ contents, ghosts ---

module contents() {
  // display on the outside of the front panel, its bulge through the notch
  %translate([(width - display[0]) / 2, -display[1], t])
    cube([display[0], display[1], display[2]]);
  %translate([(width - bulge_w) / 2, 0, t]) cube([bulge_w, bulge_d, bulge_h]);

  // printer on the lower shelf, front towards the right side, cassette out
  // through the window and onto the overhang
  %translate([width - t - printer[0], (depth - printer[1]) / 2, shelf_p_z + t]) {
    cube(printer);
    translate([printer[0] - 10, (printer[1] - cassette[1]) / 2, 0])
      cube([cassette[0], cassette[1], cassette[2]]);
  }

  // camera on its riser, optical axis through the front hole
  %translate([(width - camera[0]) / 2, t + 92, shelf_c_z + t]) {
    translate([20, 0, 0]) cube([camera[0] - 40, camera[1], camera_riser]);
    translate([0, 0, camera_riser]) cube(camera);
    translate([camera[0] / 2, 0, camera_riser + camera_axis])
      rotate([90, 0, 0]) cylinder(d = lens_d - 8, h = lens_len);
  }

  // Pi case in the lower bay
  %translate([t + 30, t + 40, t]) cube(pi);
}

// ------------------------------------------------------------- cut list ---

module label(s) {
  color([0.2, 0.2, 0.2]) translate([0, -22, 0]) linear_extrude(1) text(s, size = 16);
}

module cutlist() {
  gap = 40;
  // row 1: front, back
  translate([0, 0, 0])                  { p_front(); label("1 vorn 400x420"); }
  translate([width + gap, 0, 0])        { p_back();  label("2 hinten (Tuer) 400x420"); }
  // row 2: sides
  y2 = side_h + 3 * gap;
  translate([0, y2, 0])                 { p_left();          label(str("4 links ", inner_d, "x", side_h)); }
  translate([inner_d + gap, y2, 0])     { p_right_upper();   label(str("3a re oben ", inner_d, "x", right_up)); }
  translate([2 * (inner_d + gap), y2, 0]) { p_right_lower(); label(str("3b re unten ", inner_d, "x", right_lo)); }
  // row 3: bottom, top, shelves, rails
  y3 = y2 + side_h + 3 * gap;
  translate([0, y3, 0])                 { p_bottom(); label(str("5 Boden ", depth, "x", width)); }
  translate([width + gap, y3, 0])       { p_shelf();  label(str("6 Deckel ", inner_d, "x", inner_w)); }
  y4 = y3 + max(depth, inner_d) + 3 * gap;
  translate([0, y4, 0])                 { p_shelf(); label(str("6 Fachboden Kamera ", inner_d, "x", inner_w)); }
  translate([inner_w + gap, y4, 0])     { p_shelf_printer(); label(str("Boden 2 Drucker ", inner_d, "x", shelf_p_l)); }
  y5 = y4 + inner_d + 3 * gap;
  for (i = [0 : 3])
    translate([0, y5 + i * (rail_w + gap / 2), 0]) p_rail();
  translate([0, y5, 0]) label(str("4x Leiste ", rail_h, "x", rail_w, "x", inner_w));
}

// ----------------------------------------------------------------- views ---

if (part == "assembly") {
  case_assembly(0, door_angle, pullout);
  if (show_contents) contents();
} else if (part == "exploded") {
  case_assembly(explode_gap, 25, explode_gap);
} else if (part == "cutlist") {
  cutlist();
} else if (part == "front")       p_front();
else if (part == "back")          p_back();
else if (part == "left")          p_left();
else if (part == "right_upper")   p_right_upper();
else if (part == "right_lower")   p_right_lower();
else if (part == "bottom")        p_bottom();
else if (part == "top" || part == "shelf") p_shelf();
else if (part == "shelf_printer") p_shelf_printer();
else if (part == "rail")          p_rail();
else assert(false, str("unknown part: ", part));

// ------------------------------------------------------------- cut list ---

echo(str("Aussenmass  ", width, " x ", depth, " x ", total_h));
echo(str("1+2  ", width, " x ", side_h, "   2x  vorn + hinten"));
echo(str("4    ", inner_d, " x ", side_h, "   1x  links"));
echo(str("3a   ", inner_d, " x ", right_up, "   1x  rechts oben"));
echo(str("3b   ", inner_d, " x ", right_lo, "   1x  rechts unten"));
echo(str("5    ", depth, " x ", width, "   1x  Boden"));
echo(str("6    ", inner_d, " x ", inner_w, "   2x  Deckel + Fachboden Kamera"));
echo(str("B2   ", inner_d, " x ", shelf_p_l, "   1x  Fachboden Drucker, ragt ",
         shelf_p_l - inner_w - t, " mm heraus"));
echo(str("L    ", rail_h, " x ", rail_w, " x ", inner_w, "   4x  Leisten"));

// ------------------------------------------------------- geometry checks ---

assert((width - bulge_w) / 2 >= edge_min,
       "not enough wood left beside the display notch");
assert(t + bulge_h <= shelf_p_z,
       "display bulge runs into the printer shelf -- raise base_bay");
assert(webcam_z - webcam_d / 2 >= shelf_c_z + t + 5,
       "preview camera hole sits behind the camera shelf");
assert(lens_z - lens_d / 2 >= webcam_z + webcam_d / 2 + 8,
       "the two camera holes collide");
assert(lens_z + lens_d / 2 <= total_h - edge_min,
       "main camera hole too close to the top edge");
assert(pwin_h <= right_up - edge_min && pwin_len <= inner_d - 2 * edge_min,
       "printer window leaves 3a too weak");

// Soft checks -- these only warn, the numbers come from the data sheets and
// are worth re-measuring on the actual parts.
if (inner_d < printer[1] + 8)
  echo(str("WARNUNG: Druckerfach nur ", inner_d,
           " mm tief, der Selphy braucht quer ", printer[1], " mm plus Luft."));
if (t + display[2] > webcam_z - webcam_d / 2)
  echo(str("WARNUNG: Display reicht bis ", t + display[2],
           " mm und verdeckt das Loch der Vorschaukamera bei ",
           webcam_z - webcam_d / 2));
if (pwin_len < cassette[1] + 16)
  echo(str("WARNUNG: Druckerfenster ", pwin_len, " mm, Kassette ist ", cassette[1]));
if (shelf_p_l - inner_w - t < cassette[0] + 20)
  echo(str("WARNUNG: Ueberstand ", shelf_p_l - inner_w - t,
           " mm traegt die Kassette (", cassette[0], " mm) nicht sicher"));
if (cam_bay < camera_riser + camera[2] + 5)
  echo(str("WARNUNG: Kamerafach ", cam_bay, " mm hoch, Kamera plus Podest brauchen ",
           camera_riser + camera[2]));
// The cassette sits in front of the printer, not on top of it -- only the
// printer body has to fit under the camera shelf.
if (printer_bay < printer[2] + 12)
  echo(str("WARNUNG: Druckerfach nur ", printer_bay, " mm hoch, Drucker ist ",
           printer[2]));
if (base_bay < pi[2] + 10)
  echo(str("WARNUNG: unteres Fach nur ", base_bay, " mm hoch"));
if (pwin_h < printer[2] + 5)
  echo(str("WARNUNG: Druckeroeffnung ", pwin_h, " mm hoch, Drucker ist ", printer[2]));
