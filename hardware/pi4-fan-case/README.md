# Raspberry-Pi-4-Gehäuse mit 50-mm-Lüfter

Zweiteiliges Druckgehäuse für den Pi 4B der Fotobox, für einen Lüfter
50 × 50 × 10 mm. Alle Maße sind Parameter, nichts ist in der Geometrie
festgeschrieben.

## Zwei Varianten

| | Variante 1 | Variante 2 |
|---|---|---|
| Datei | `pi4_case.scad` | `pi4_case_v2.scad` |
| Lüfter | oben aufgeschraubt | innen, unter dem Deckel |
| Platine | 4 Schrauben von unten | 2 Schrauben von oben, 2 Zentrierstifte |
| Deckel | mit denselben 4 Schrauben | geklipst, 4 Rasthaken |
| Gesamthöhe | 49,3 mm | 48,3 mm |
| Lüfterbefestigung | 4 Schrauben durch den Deckel | 4 angeformte Federlaschen |
| Kleinteile | 4 × M2,5 × 16, 4 × M4 (Lüfter), 2 × M4 (Platte) | 2 × M2,5 × 6, 2 × M4 (Platte) |

Beide teilen sich `pi4_board.scad` — dort und nur dort stehen Platinenmaße und
Anschlusspositionen.

Die Abschnitte bis „Drucken" beschreiben Variante 1; Variante 2 hat einen
eigenen Abschnitt weiter unten.

## Eckdaten Variante 1

| | |
|---|---|
| Außenmaß | 127 × 64 × 39,3 mm über die Laschen (mit Lüfter 49,3 mm hoch) |
| Gehäusekörper | 93 × 64 mm |
| Montage | 2 × M4, Lochabstand 113 mm, 5 mm Luftspalt unter dem Boden |
| Lüfter | 50 × 50 × 10 mm, Lochbild 40 × 40 mm, Bohrungen Ø 4,4 mm |
| Luftöffnung | Ø 46 mm (Variante 2: Ø 48) mit gedrucktem Fingerschutz |
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

Ausschnitte: USB-C, 2 × Micro-HDMI, Klinke (Vorderseite), beide USB-Blöcke und
RJ45 (rechts), microSD (links). Die Rückseite hat keine Anschlüsse und trägt
deshalb das Lüftungsfeld.

Auf der rechten Seite ist die Reihenfolge von der Vorderkante (Klinke) aus:
USB 2.0, USB 3.0, RJ45. Der Netzwerkanschluss liegt also am GPIO-Ende — beim
Pi 4 haben Ethernet und USB gegenüber dem Pi 3 die Plätze getauscht.

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

* Die linke Lasche liegt vor der microSD-Öffnung, 3 mm unter deren Unterkante.
  Beim Herausziehen der Karte dient sie eher als Fingerauflage. Ganz aus dem Weg
  bekommt man sie nur mit `-D ear_offset=23 -D ear_w=16` — dann sitzt sie
  allerdings dicht an der Ecke.
* Zum Öffnen des Gehäuses muss es von der Platte, weil die Platinenschrauben von
  unten kommen.

Mit `-D 'ear_axis="y"'` wandern die Laschen auf die langen Seiten. Dann liegen
ihre Wurzeln allerdings unter dem Schlitzfeld und decken dort etwas ab.

Für die Lüfterstromversorgung ist im Deckel ein Kabelschlitz (10 × 6 mm) direkt
über GPIO-Pin 4 (5 V) und Pin 6 (GND). Er ist tief genug, um beide Pinreihen zu
erreichen.

## microSD-Öffnung

Gilt für beide Varianten, die Geometrie steht in `pi4_board.scad`.

Die Karte ragt nur etwa 2 mm über die Platinenkante hinaus, bis zur Außenfläche
sind es aber 4 mm (1,6 mm Spiel + 2,4 mm Wand). Ein enger Schlitz legt diese
2 mm also auf den Grund eines Tunnels — dann geht es nur noch mit der Pinzette.

Die Öffnung ist deshalb ein Trichter: innen 22 × 9 mm, nach außen auf
29 × 12,5 mm aufgeweitet. Entscheidend ist die Breite — neben der 11 mm breiten
Karte bleiben links und rechts je 9 mm, sodass man sie an den Schmalseiten
zwischen Daumen und Zeigefinger fassen kann statt von oben und unten. Die
Flanken stehen unter 45°, drucken also ohne Stützmaterial.

Stellschrauben in `port_cuts_local()`: `sd_w` (lichte Breite innen, 22) und
`sd_flare` (Aufweitung pro Seite, 3,5). Beim Vergrößern von `sd_flare` prüfen,
dass die Trichteroberkante nicht in die Lüftungsschlitze der linken Wand läuft —
aktuell bleiben dort 0,9 mm.

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

## Variante 2 — Lüfter innen, Klipsdeckel

`pi4_case_v2.scad`, außen 127 × 64 × 48,3 mm, Körper 93 × 64. Trotz des innen
liegenden Lüfters 1 mm flacher als Variante 1, weil die 10 mm Lüfterhöhe in die
Bauhöhe hineinwandern statt obendrauf zu kommen. Laschen, Füße und alle
Anschlussausschnitte sind identisch zu Variante 1.

**Lüfter.** Wird von unten in eine Tasche an der Deckelunterseite gedrückt und
von vier angeformten Federlaschen gehalten — keine Schrauben, kein Zusatzteil.
Ein 3 mm hoher Rand führt ihn seitlich, die Laschen greifen 0,8 mm unter den
Rahmen. Der Deckel ist dadurch überall gleich dick (2,4 mm), der Lüfter liegt
plan an der Innenseite und damit direkt an der Ansaugöffnung. Für das Kabel ist
der Rand an der Ecke zum GPIO-Stecker auf 8 mm ausgespart. Die Tasche ist exakt
50,0 mm — am gedruckten Teil geprüft, der Lüfter geht hinein (`fan_fit`).

Beide Flanken des Hakens sind Schrägen, keine rechtwinkelige Nase: der Deckel
wird auf der Oberseite liegend gedruckt, die Haltefläche zeigt dabei nach unten
und wäre sonst ein 90°-Überhang. Sie steht auf 45° (`fclip_bear_a`) — flacher
braucht Stützmaterial. Die Einführschräge zeigt beim Drucken nach oben und ist
deshalb frei wählbar, sie steht auf 30° (`fclip_lead_a`), damit der Lüfter sanft
einrastet. Die Haltefläche beginnt genau auf Höhe der Lüfterunterseite, der
Lüfter hat also kein Spiel.

Zum Herausnehmen zwei gegenüberliegende Laschen nach außen drücken und den
Lüfter kippen. Die Laschen federn über die vollen 12,2 mm frei — der Rand ist an
diesen vier Stellen aufgetrennt, sonst wären sie am Fuß eingespannt. 12 × 1,2 mm
Querschnitt, zusammen rund 18 N Auszugskraft bei etwa 1 % Randfaserdehnung: hält
den 30-g-Lüfter um Größenordnungen und bleibt weit im elastischen Bereich.

Ansaugöffnung Ø 48 mm mit Fingerschutz, Blasrichtung nach unten auf die Platine.
Über der Platine sind 33 mm frei; der Lüfter beginnt 23 mm über ihr und lässt
damit 5 mm über dem RTC-Modul. Wer es flacher will und die RTC-Höhe nachgemessen
hat, kann `inner_h` um bis zu 3,6 mm reduzieren.

**Platine.** Vier Dome, paarweise auf den Diagonalen. Die beiden bei (3,5 | 3,5)
und (61,5 | 52,5) nehmen je eine M2,5 × 6 von oben auf, die beiden anderen
tragen Ø 2,4-Zentrierstifte, die in die Befestigungslöcher fassen. Zwei
Schrauben halten die Platine, die vier Auflagepunkte verhindern, dass sie beim
Einstecken eines USB-Steckers federt.

**Deckel.** Vier Rasthaken, je zwei an den kurzen Seiten, rasten in eine Nut in
der Innenwand. Bewusst nicht an den langen Seiten: dort sitzen Anschlüsse,
Lüftungsfeld und die Lüftertasche. Die Nut liegt bei z ≈ 33 mm, also weit über
allen Ausschnitten — das ist der Grund, warum das erst beim hohen Gehäuse geht.

* Nase 0,85 mm tief, oben und unten angeschrägt: klickt beim Aufsetzen ein und
  lässt sich mit festem Zug wieder abziehen
* Die Nase steht 0,1 mm über die Nutoberkante hinaus (`snap_preload`). Der
  aufgesetzte Deckel hält die Haken damit leicht gespannt und wird auf die
  Wandoberkante gezogen, statt zu klappern
* Vertikal liegt der Deckel auf der Wandoberkante auf, nicht auf den Haken
* In der Mitte jeder kurzen Seite ist eine 16 mm breite Kerbe in der Oberkante,
  um mit dem Fingernagel unter den Deckelrand zu kommen

Bezugsmaß ist die Nut im Unterteil; die Nase wird dagegen gesetzt. Das ist
Absicht: **`snap_preload` und `tab_t` ändern nur den Deckel**, das Unterteil
bleibt gleich. Man kann den Sitz also nachstellen, ohne es neu zu drucken.
`bead` verändert dagegen auch die Nuttiefe und damit beide Teile.

**Nachstellen**, falls es zu stramm oder zu lose sitzt: `-D snap_preload=0.2`
(fester) bzw. `-D snap_preload=0` (Spiel wie ohne Vorspannung), `-D tab_t=1.3`
macht die Haken weicher. Erst einen Deckel probieren, bevor beide Teile
gedruckt werden.

Weil kein Lüfter über den Deckel hinausragt und keine Schraube durch den Boden
geht, sind hier auch die Füße massiv.

## Drucken

Kein Supportmaterial nötig.

* **Unterteil** — wie exportiert, Boden auf dem Druckbett.
* **Deckel** — im Slicer um 180° um X drehen, sodass die Deckeloberseite auf dem
  Bett liegt und Säulen bzw. Rasthaken nach oben zeigen.

Empfohlen: PETG (Abwärme), 0,2 mm Schichthöhe, 4 Perimeter, 25 % Infill. Säulen
und Dome brauchen die 4 Perimeter, sonst reißen sie beim Einschneiden der
M2,5-Schrauben auf. Bei Variante 2 die Rasthaken und die Lüfterlaschen **nicht**
mit mehr Perimetern oder Infill drucken — sie müssen federn.

`stl/pi4_case_all.3mf` ist das fertig aufgestellte Projekt mit allen vier Teilen
(Unterteil und Deckel beider Varianten). Nach jeder Änderung an den `.scad`
neu slicen, sonst druckt man den alten Stand.

## STL neu erzeugen

```bash
openscad -D 'part="base"' -o stl/pi4_case_base.stl pi4_case.scad
```

```bash
openscad -D 'part="lid"' -o stl/pi4_case_lid.stl pi4_case.scad
```

```bash
openscad -D 'part="base"' -o stl/pi4_case_v2_base.stl pi4_case_v2.scad
```

```bash
openscad -D 'part="lid"' -o stl/pi4_case_v2_lid.stl pi4_case_v2.scad
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
