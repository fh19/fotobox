# Raspberry-Pi-4-Gehäuse mit 50-mm-Lüfter

Zweiteiliges Druckgehäuse für den Pi 4B der Fotobox, mit Aufnahme für einen
Lüfter 50 × 50 × 10 mm auf dem Deckel. Quelle ist `pi4_case.scad` — alle Maße
sind Parameter, nichts ist in der Geometrie festgeschrieben.

## Eckdaten

| | |
|---|---|
| Außenmaß | 127 × 64 × 39,3 mm über die Laschen (mit Lüfter 49,3 mm hoch) |
| Gehäusekörper | 93 × 64 mm |
| Montage | 2 × M4, Lochabstand 113 mm, 5 mm Luftspalt unter dem Boden |
| Lüfter | 50 × 50 × 10 mm, Lochbild 40 × 40 mm, Bohrungen Ø 4,4 mm |
| Luftöffnung | Ø 46 mm mit gedrucktem Fingerschutz (6 Speichen + Ring) |
| Platinenabstand | 3,5 mm unter der Platine, 24 mm über der Platine |
| Verschraubung Gehäuse | 4 × M2,5 × 16 mm, selbstschneidend, von unten |
| Lüfterschrauben | 4 × M4 × 25 mm oder die dem Lüfter beiliegenden Blechschrauben |

Der Lüfter sitzt bei den Platinenkoordinaten (36, 27), also mittig über SoC und
RAM, und bläst nach unten auf die Platine. Die Abluft geht über das Schlitzfeld
im Boden, die Rückwand und die linke Seitenwand.

## Aufbau

Die Platine liegt auf vier Abstandshaltern im Unterteil. Vier M2,5-Schrauben
kommen von unten durch Boden, Abstandshalter und Platine und schneiden sich ihr
Gewinde in die vier Säulen des Deckels. Ein Schraubensatz klemmt also Platine
und Deckel gleichzeitig. Die Schraubenköpfe sitzen versenkt im Boden, das
Gehäuse steht damit plan auf.

Ausschnitte: USB-C, 2 × Micro-HDMI, Klinke (Vorderseite), RJ45 und beide
USB-Blöcke (rechts), microSD (links). Die Rückseite hat keine Anschlüsse und
trägt deshalb das Lüftungsfeld.

## Montage auf einer Platte

Das Gehäuse steht auf vier 5 mm hohen Füßen. Die Schlitze im Boden blasen damit
in einen durchgehenden Spalt und die Abluft kann seitlich weg — auf eine Platte
gesetzt wäre das Schlitzfeld sonst wirkungslos.

Die Füße sitzen genau unter den vier Platinenbolzen, die Last geht also
geradewegs von der Platte in die Abstandshalter. Der Kopfsenkung für die
M2,5-Schrauben ist durch den Fuß nach unten durchgezogen, die Schrauben bleiben
deshalb wie gehabt M2,5 × 16 — man braucht nur einen Schraubendreher, der 7 mm
tief in eine Ø 5,4-Bohrung passt.

An den beiden kurzen Seiten sitzt je eine Anschraublasche, bündig mit der
Standfläche, für M4. Sie greift 12 mm unter den Gehäuseboden — dort hält sie,
nicht an der Außenwand.

Zwei Dinge zum Wissen:

* Die linke Lasche liegt vor dem microSD-Schlitz, 4,5 mm darunter. Die Karte
  kommt weiterhin heraus, ist aber fummeliger zu greifen. Wer das nicht will,
  schiebt beide Laschen mit `-D ear_offset=19` aus dem Weg.
* Zum Öffnen des Gehäuses muss es von der Platte, weil die Platinenschrauben von
  unten kommen.

Mit `-D 'ear_axis="y"'` wandern die Laschen auf die langen Seiten. Dann liegen
ihre Wurzeln allerdings unter dem Schlitzfeld und decken dort etwas ab.

Für die Lüfterstromversorgung ist im Deckel ein Kabelschlitz (10 × 4 mm) direkt
über GPIO-Pin 4 (5 V) und Pin 6 (GND).

## RTC-Modul auf dem GPIO-Stecker

`inner_h` ist auf 24 mm gesetzt, damit das DS1307-Modul auf dem GPIO-Stecker
Platz hat. Gerechnete Stapelhöhe über der Platinenoberseite:

| | |
|---|---|
| Buchsenleiste des Moduls | ~11 mm |
| Modulplatine | 1,6 mm |
| CR2032-Halter | ~5 mm |
| **Summe** | **~18 mm** — bleiben ~6 mm Luft |

Vor dem Druck nachmessen: Abstand von der Pi-Platinenoberfläche bis zum höchsten
Punkt des RTC-Moduls. Liegt der über 22 mm, `inner_h` entsprechend erhöhen
(Schraubenlänge bleibt gleich, die Deckelsäulen wachsen mit).

Zwei Dinge dabei im Auge behalten:

* Die Deckelsäule bei (3,5 | 52,5) steht direkt neben Pin 1. Bis zur
  Steckerkante bei x = 6,35 mm bleiben 0,35 mm. Stößt die Modulplatine an, hilft
  `-D pillar_od=4.5`.
* Sitzt das Modul über den Pins 1–6, sind die 5-V-Pins vom Kabelschlitz aus
  nicht mehr erreichbar. Dann entweder den Schlitz über einen freien Bereich
  legen (`-D 'cable_pos=[30,53.5]'`) und den Lüfter woanders anklemmen, oder ihn
  gleich über einen USB-A-Stecker versorgen.

## Drucken

Kein Supportmaterial nötig.

* **Unterteil** — wie exportiert, Boden auf dem Druckbett.
* **Deckel** — im Slicer um 180° um X drehen, sodass die Deckeloberseite auf dem
  Bett liegt und die Säulen nach oben zeigen.

Empfohlen: PETG (Abwärme), 0,2 mm Schichthöhe, 4 Perimeter, 25 % Infill. Die
Säulen brauchen die 4 Perimeter, sonst reißen sie beim Einschneiden der
M2,5-Schrauben auf.

## STL neu erzeugen

```bash
openscad -D 'part="base"' -o stl/pi4_case_base.stl pi4_case.scad
```

```bash
openscad -D 'part="lid"' -o stl/pi4_case_lid.stl pi4_case.scad
```

`part` kennt außerdem `"both"` (beide Teile nebeneinander, Vorschau) und
`"assembly"` (zusammengebaut mit Platinen- und Lüfterattrappe).

## Anpassen

Die üblichen Stellschrauben stehen oben in der `.scad`:

* `fan_center` — Position des Lüfters in Platinenkoordinaten (0,0 = Ecke bei
  USB-C/microSD). Nach dem Verschieben prüfen, dass die Lüfterbohrungen nicht
  in die Deckelsäulen bei (3,5 | 3,5), (61,5 | 3,5), (3,5 | 52,5) und
  (61,5 | 52,5) laufen — nötiger Abstand ist `pillar_od/2 + fan_bolt_dia/2`.
* `fan_size`, `fan_bolt`, `fan_bolt_dia`, `fan_bore` — für andere Lüftergrößen
  (60 mm: `fan_size=60`, `fan_bolt=50`).
* `inner_h` — lichte Höhe über der Platine. Ohne Aufsteckmodul reichen 18 mm
  (USB-Block: 15,6 mm), mit RTC sind es 24 mm. Siehe Abschnitt oben.
* `fan_guard` — auf `false` setzen, wenn der Lüfter ein eigenes Gitter hat.
* `foot_h` — Höhe des Luftspalts unter dem Gehäuse. Mehr kühlt besser, macht die
  Füße aber schlanker; über 8 mm besser `foot_d` mit erhöhen.
* `ear_axis`, `ear_offset`, `ear_reach`, `ear_hole` — Lage und Lochmaß der
  Anschraublaschen.

`pillar_od` ist bewusst auf 5,0 mm begrenzt: die Säule bei (3,5 | 52,5) liegt
direkt neben dem GPIO-Stecker, dessen Gehäuse bei x = 6,35 mm beginnt.
