# Schaltbox — Netzverteilung und Lampenschalter

Ein Riegel von **150 × 60 × 60 mm** zum Einbau ins Fotobox-Gehäuse. Auf der
**Unterseite** die Kaltgerätebuchse — sie bringt Netzanschluss, Feinsicherung und
Hauptschalter in einem Teil — und eine Euro-Buchse, in Linie. Auf der **linken
Seite** die beiden anderen Euro-Buchsen, ebenfalls in Linie. Layout nach der
Handskizze `photo_2026-08-26_21-06-01.jpg`.

Der **Deckel ist die lange Fläche gegenüber der linken Seite**: abgenommen liegt
der ganze Riegel seitlich offen, und beide Buchsengruppen sind erreichbar.

```
Dateien   schaltbox_parts.scad   gemessene Maße und die Vorgaben
          schaltbox.scad         Geometrie, mit Passungsbericht
```

## Das Maß ist die Vorgabe — also wird geprüft, nicht gerechnet

Die Größe ist gesetzt, also müssen sich die Teile fügen. Jeder Render gibt aus,
was passt und was nicht:

```
Aussen 150 x 60 x 60  ->  innen 144 x 54 x 54
Verbindung loeten: Kaltgeraetebuchse 29 mm, Euro 35 mm
Unterseite, Teile ragen in z (54 frei): passt
Linke Seite, Teile ragen in y (54 frei): passt
Platine+SSR 16.6 mm hoch; ueber den Unterseiten-Teilen 19 mm frei -> passt liegend
Freier Abschnitt am Ende: 32 x 54 x 54 mm; Platine ist 70 x 30 -> PASST NICHT stehend
```

Alle Einbauteile werden an **ein Ende** geschoben, damit die übrige Länge in
einem Stück am anderen Ende bleibt — dort ist der einzige Platz, an dem eine
stehende Platine je Platz fände.

### Löten bleibt die bessere Wahl

Geometrisch passen Flachstecker jetzt: 50 mm in 54 mm. Es blieben aber nur
**4 mm** hinter den Buchsen, und darin lässt sich keine Ader biegen. Mit
Lötverbindung sind es 35 mm und **19 mm** Luft dahinter.

### Und die Platine?

| SSR | Aufbau | passt? |
|---|---|---|
| flach `AQ2A2-J-ZP3` | 16,6 mm | **ja**, liegend über den Unterseiten-Teilen (19 mm frei) |
| stehend `AQ2A2-ZP3` | 30,6 mm | nein — braucht **72 mm Gehäusehöhe** (dann 31 mm frei) |

Der freie Abschnitt am Ende misst **32 × 54 × 54 mm**. Für die 70 mm lange
Platine in Reihe (Klemme – SSR – Klemme) reicht das nicht; für ein kompakteres
Layout mit den Klemmen *neben* dem SSR statt dahinter schon.

Bleibt es bei 60 mm Höhe und stehendem SSR, gehört das Relais aus dieser Box
heraus — sie wird dann reine Verteilung, und das SSR sitzt näher am Pi.

## Dünne Wand für die Snaps

Ein Snap-in-Teil will eine dünne Platte, ein Netzgehäuse eine dicke Wand. Die
Wand bleibt 3 mm und wird **nur um jede Öffnung** ausgedünnt:

| Teil | auf | an welchen Kanten |
|---|---|---|
| Kaltgerätebuchse | 1,5 mm | den beiden langen (48 mm) |
| Euro-Buchsen | 2,0 mm | den beiden schmalen (13,2 mm) |

Die Taschen laufen mit 45° aus — eine Stufe wäre eine Decke, die der Drucker
überbrücken müsste. Und sie greifen nur dort, wo die Snaps wirklich sitzen; rings
um die Öffnung ausgedünnt würde unnötig Material schwächen.

Die Buchsen liegen **quer**: die 44-mm-Seite des Rahmens läuft entlang der
120 mm, sodass die schmalen Flächen nur seine 20 mm tragen müssen. Beim
Kaltgeräteeinbau überdeckt der Flansch die Öffnung nur um 1,45 mm je Seite — der
Ausschnitt muss also sitzen. Die zwei 5-mm-Fasen sitzen an einer **Schmalseite** (27,4 mm) und sind die
Verdrehsicherung; `iec_key_flip` dreht sie auf die andere Seite.

## Verdrahtung

```
Kaltgerätebuchse (Netz + Sicherung 1 A + Schalter), Unterseite
   PE ──────────────────────────┬── Euro-Buchsen (PE, falls vorhanden)
                                └── zur Lampe
   N  ──────────────────────────┬── Euro-Buchsen (N)
                                └── zur Lampe
   L  (geschaltet, abgesichert) ┬── Euro-Buchsen (L)
                                └── SSR Pin 1 ──► Pin 2 ──► Lampe (geschaltet)

Steuerleitung vom Pi (eigene Einführung, nur mit Platine)
   GPIO 17 ──► SSR Pin 3 (+)      optional 100 nF über Pin 3/4
   GND     ──► SSR Pin 4 (−)
```

**PE wird nie geschaltet.** Der Schalter der Kaltgerätebuchse trennt alles, das
SSR danach nur noch den Lampenzweig.

**Zur Sicherung:** 1 A sind bei 230 V rund 230 W, und sie sitzt vor allem. Pi,
Drucker und Lampe teilen sich das. Der Selphy zieht beim Drucken kräftig — fällt
die Sicherung, ist nicht sie zu klein, sondern die Summe zu groß.

## Drucken

- **Kein PLA.** Flammhemmend mit UL94 V-0 (PC/ABS FR, ABS-FR oder PETG V0).
- **3 mm Wand** ist die Untergrenze — außer den ausgedünnten Feldern, und die sind
  so dünn, wie die Teile es verlangen.
- **Der Druck hält, isolieren muss etwas anderes.** Eine FDM-Wand ist entlang der
  Schichtgrenzen porös; spannungsführende Teile zusätzlich isolieren.
- Auf der Deckelöffnung liegend drucken. Die Snap-Taschen laufen mit 45° aus und
  brauchen keine Stützen.

## Rendern

```bash
openscad -o unterteil.stl -D 'part="unterteil"' -D 'connection="loeten"' schaltbox.scad

# mit stehendem SSR: 72 statt 60 mm hoch
openscad -D 'part="beides"' -D 'connection="loeten"' -D 'box=[150,60,72]' \
         -D 'with_pcb=true' -D 'pcb_standoff=4' schaltbox.scad
openscad -o deckel.stl    -D 'part="deckel"'    schaltbox.scad

# mit flachem SSR und Platine
openscad -D 'part="beides"' -D 'connection="loeten"' \
         -D 'with_pcb=true' -D 'ssr_flat=true' -D 'pcb_standoff=4' schaltbox.scad
```
