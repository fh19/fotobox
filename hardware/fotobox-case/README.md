# Fotobox-Gehäuse

Parametrisches Modell des Holzgehäuses nach der Handskizze — Korpus aus 18 mm
Leimholz, Außenmaß **400 × 236 × 438 mm** (B × T × H), Druckerboden ragt rechts
198 mm heraus.

Alles steckt in `fotobox_case.scad`, jede Zahl ist ein Parameter. Die Stückliste
und die Freiraum-Prüfungen gibt das Modell beim Rendern auf der Konsole aus.

## Aufbau

- **Vorderseite (1)** und **Rückseite (2)** sind volle Platten 400 × 420 und decken
  die Stirnkanten der Seiten ab. Die Rückseite ist die Tür.
- **Seiten (4 links, 3a + 3b rechts)** stehen auf dem **Boden (5)**, der die volle
  Grundfläche trägt.
- **Deckel und Kamera-Fachboden (6)** sind Einlegeböden 364 × 200 zwischen den Seiten.
- Die rechte Seite ist geteilt: zwischen **3a** (oben, 302) und **3b** (unten, 100)
  bleibt ein 18 mm hoher Schlitz, in dem der **Druckerboden** läuft.
- **Druckerboden (Boden 2, 200 × 580)**: liegt im Schlitz und steht rechts 198 mm
  über. Der Überstand trägt die Papierkassette. Zum Transport lässt er sich ganz
  herausziehen.
- In **3a** sitzt über dem Schlitz das **Druckerfenster** (150 × 95), nach unten zum
  Schlitz hin offen — dadurch gehen Kassette und Abzug durch.
- Das **Display ist nur teilversenkt**: es wird von außen auf die Frontplatte
  geschraubt, nur die Ausbuchtung auf seiner Rückseite (320 × 100) greift durch eine
  Aussparung, die bis an die Unterkante der Frontplatte reicht. Eine Scheibe für den
  Bildschirm gibt es nicht — die Front ist über der Aussparung geschlossen.
- Vier **Leisten 24 × 48 × 364** als Auflagen unter den beiden Fachböden, quer
  eingebaut (Auszugsrichtung des Druckerbodens), bei y = 68 und y = 170 — also
  hinter der Display-Ausbuchtung, die die vorderen 25 mm belegt.

Koordinaten: x nach rechts, y nach hinten, z nach oben, Nullpunkt vorne links unten.

## Stückliste

| Nr. | Maß (mm) | Stück | Teil |
|---|---|---|---|
| 1 + 2 | 400 × 420 | 2 | vorn, hinten (Tür) |
| 4 | 200 × 420 | 1 | links |
| 3a | 200 × 302 | 1 | rechts oben, mit Druckerfenster |
| 3b | 200 × 100 | 1 | rechts unten |
| 5 | 236 × 400 | 1 | Boden |
| 6 | 200 × 364 | 2 | Deckel, Fachboden Kamera |
| Boden 2 | 200 × 580 | 1 | Fachboden Drucker, 198 mm Überstand |
| L | 24 × 48 × 364 | 4 | Auflageleisten |

Das deckt sich mit der Skizze, Teil für Teil. Die Höhe des unteren Fachs kommt aus
der Display-Aussparung (`base_bay = bulge_h`): 100 hoch, also 3b = 100 und 3a = 302.

## Höhen

| von | bis | Fach |
|---|---|---|
| 0 | 18 | Boden (5) |
| 18 | 118 | unteres Fach: Display-Ausbuchtung vorn, dahinter Pi, Netzteil, Kabel (100) |
| 118 | 136 | Druckerboden, im Schlitz laufend |
| 136 | 236 | Druckerfach (100 lichte Höhe) |
| 236 | 254 | Fachboden Kamera |
| 254 | 420 | Kamerafach (166 lichte Höhe) |
| 420 | 438 | Deckel (6) |

## Öffnungen in der Front

| Öffnung | Maß | Lage |
|---|---|---|
| Display-Ausbuchtung | 320 × 100, oben R6 | bündig mit der Unterkante der Frontplatte |
| Vorschaukamera | ⌀ 26 | Achse 305 |
| Hauptkamera | ⌀ 85 | Achse 369 |

Die Achse der Hauptkamera ergibt sich aus Fachboden (254) + Podest (60) +
Objektivachse über Kameraboden (55). Wird die Kamera anders aufgestellt, ist
`lens_z` nachzuführen — das Modell prüft die Abstände und bricht mit einer
Meldung ab, wenn sich zwei Öffnungen ins Gehege kommen.

## Ansichten

```bash
openscad hardware/fotobox-case/fotobox_case.scad
```

| Parameter | Ansicht |
|---|---|
| `-D 'part="assembly"'` | Zusammenbau (Standard), mit Geisterkörpern für Display, Kamera, Drucker, Pi |
| `-D 'part="exploded"'` | Platten auseinandergezogen |
| `-D 'part="cutlist"'` | alle Bretter flach nebeneinander, beschriftet |
| `-D 'part="front"'` … | ein einzelnes Brett (`back`, `left`, `right_upper`, `right_lower`, `bottom`, `shelf`, `shelf_printer`, `rail`) |
| `-D 'door_angle=100'` | Tür offen |
| `-D 'pullout=180'` | Druckerboden weiter herausgezogen |
| `-D 'show_contents=false'` | ohne Geisterkörper |

In der Zuschnittansicht von oben blendet die Orthogonalprojektion der Vorschau die
Ausschnitte weg (Tiefenpuffer). Mit Perspektive (`--projection=p`, in der GUI die
Standardeinstellung) sind sie zu sehen.

Der Zusammenbau ist bewusst kein geschlossener Körper (die Platten liegen Fläche
an Fläche) — die 2-Manifold-Warnung beim STL-Export ist normal. Für den Export
einzelner Bretter `part=` benutzen.

## Angenommene Maße — bitte am Bauteil prüfen

| Parameter | Wert | Bedeutung |
|---|---|---|
| `display` | 360 × 40 × 210 | Umriss des Displays vor der Front; Oberkante bei 228, das Loch der Vorschaukamera beginnt bei 292 |
| `bulge_d` | 25 | Tiefe der Ausbuchtung, davon 18 in der Platte, 7 im Innenraum |
| `printer` | 133 × 181 × 68 | Selphy CP1500, Front zeigt nach rechts |
| `cassette` | 95 × 130 × 35 | Papierkassette im herausstehenden Zustand |
| `camera` | 131 × 80 × 96 + 60 Podest | Gehäuse auf dem Kamerafachboden |

Das Modell meldet beim Rendern, wenn eines dieser Maße nicht mehr passt.

## Offene Punkte

1. **Displaybreite** ist geschätzt (360). Höhe 210 und Ausbuchtung 320 × 100 sind gesetzt.
2. **Befestigung des Displays** (Schrauben von innen durch die Front, VESA-Platte o. ä.)
   ist nicht modelliert.
3. **Nicht modelliert:** Kabeldurchführung und Kaltgerätebuchse, Lüftungsöffnungen
   (Drucker und Pi geben Wärme ab, das Kamerafach steht darüber), Türbänder und
   Verschluss, Griffe, Verbindungsmittel (Dübel/Lamello/Domino), Anschlag gegen
   Herausrutschen des Druckerbodens.
4. **Schlitzspiel.** Der Schlitz ist exakt 18 mm hoch. `slot_play = 1` gibt 1 mm Luft;
   3a wird dann 301 statt 302.
