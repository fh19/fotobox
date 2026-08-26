# Schaltbox — Netzverteilung und Lampenschalter

Ein Kasten von **80 × 50 × 90 mm** zum Einbau ins Fotobox-Gehäuse. Auf der
**Vorderseite** stehen die drei Euro-Buchsen in einer Säule übereinander, an den
**linken Rand** gerückt. Auf der **rechten Seite** steht hochkant die
Kaltgerätebuchse — sie bringt Netzanschluss, Feinsicherung und Hauptschalter in
einem Teil — nach oben geschoben, damit darunter eine freie Ecke bleibt. Layout nach
`photo_2026-08-26_21-35-32.jpg`.

Der **Deckel ist die Rückseite**, mit vier kleinen Schrauben. Abgenommen liegt
alles auf einmal offen.

Zwischen den Öffnungen laufen zwei **Stege** von der Vorderwand bis zur
Rückwand. Drei Ausschnitte und die dünnen Snap-Felder daneben lassen die
Vorderwand sonst federn; die Stege binden sie nach hinten an. Sie reichen nur
über die Säule plus 4 mm, damit die Kanäle links und rechts frei bleiben.

```
Dateien   schaltbox_parts.scad   gemessene Maße und die Vorgaben
          schaltbox.scad         Geometrie, mit Passungsbericht
```

## Das Maß ist die Vorgabe — also wird geprüft, nicht gerechnet

Die Größe ist gesetzt, also müssen sich die Teile fügen. Jeder Render sagt, was
passt und was nicht:

```
Aussen 80 x 50 x 90  ->  innen 74 x 44 x 84
Verbindung loeten: Kaltgeraetebuchse 29 mm, Euro 35 mm
Vorderseite, Dosen ragen in y (44 frei): passt
Rechte Seite, Buchse ragt in x (74 frei): passt
  Ausschnitt hochkant 48 hoch x 27.4 tief auf einer Flaeche 84 x 44 -> passt
  Flansch 51 x 31 auf 90 x 50 -> passt
Saeule: 3 Rahmen a 20 mm im Raster 26 -> 72 von 84 mm Hoehe
  Ecke rechts unter der Buchse: 25 breit x 44 tief x 30 hoch
```

Geprüft wird auch, ob der Ausschnitt auf die **Fläche** passt und nicht nur die
Tiefe in den Kasten. Genau das war einmal falsch herum gedreht: hochkant gehört
die 48-mm-Seite auf die Höhe, nicht über die 44 mm Tiefe.

### Löten ist bei dieser Tiefe Pflicht

Die Euro-Buchsen ragen mit Flachsteckern 50 mm hinein, innen sind in y aber nur
**44 mm**. Gelötet sind es 35 mm, mit 9 mm Luft dahinter. `connection = "loeten"`.

### Die freie Ecke rechts

Weil die Säule links steht und die Buchse oben, bleibt rechts darunter ein Stück
am Stück: **25 breit × 44 tief × 30 hoch**.

```
    liegend, SSR nach oben: groesste Platine 44 x 25 mm, Aufbau bis 30 mm
    stehend an der Wand:    Aufbau bis 25 mm
```

| SSR | Aufbau | wie |
|---|---|---|
| stehend `AQ2A2-ZP3` | 29,6 mm bei `pcb_standoff = 3` | **liegend** auf dem Boden, SSR nach oben |
| flach `AQ2A2-J-ZP3` | 16,6 mm | liegend oder stehend an der Wand |

**Die Platine muss dafür anders bestückt werden.** In Reihe — Klemme, SSR,
Klemme — ist sie rund 70 mm lang und passt in diese Ecke nicht. Mit den Klemmen
**neben** dem SSR statt dahinter kommt man auf etwa 44 × 25 mm, und das geht.
Das SSR selbst ist nur 33 × 10 mm, der Platz reicht also.

## Dünne Wand für die Snaps

Ein Snap-in-Teil will eine dünne Platte, ein Netzgehäuse eine dicke Wand. Die
Wand bleibt 3 mm und wird **nur um jede Öffnung** ausgedünnt:

| Teil | auf | an welchen Kanten |
|---|---|---|
| Kaltgerätebuchse | 1,5 mm | den beiden langen (48 mm), hier oben und unten |
| Euro-Buchsen | 2,0 mm | den beiden schmalen (13,2 mm) |

Die Taschen laufen mit 45° aus — eine Stufe wäre eine Decke, die der Drucker
überbrücken müsste. Und sie greifen nur dort, wo die Snaps wirklich sitzen; rings
um die Öffnung ausgedünnt würde unnötig Material schwächen.

Die Buchsen liegen **quer**: die 44-mm-Seite des Rahmens läuft über die Breite,
die 20-mm-Seite stapelt sich über die Höhe. Beim
Kaltgeräteeinbau überdeckt der Flansch die Öffnung nur um 1,45 mm je Seite — der
Ausschnitt muss also sitzen. Die zwei 5-mm-Fasen sitzen an einer **Schmalseite** (27,4 mm) und sind die
Verdrehsicherung; `iec_key_flip` dreht sie auf die andere Seite.

## Verdrahtung

```
Kaltgerätebuchse (Netz + Sicherung 1 A + Schalter), rechte Seite
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
openscad -o deckel.stl    -D 'part="deckel"'    schaltbox.scad

# mit flachem SSR und Platine
openscad -D 'part="beides"' -D 'connection="loeten"' \
         -D 'with_pcb=true' -D 'ssr_flat=true' -D 'pcb_standoff=4' schaltbox.scad

# mit stehendem SSR: 106 statt 80 mm breit
openscad -D 'part="beides"' -D 'connection="loeten"' -D 'box=[106,50,90]' \
         -D 'with_pcb=true' -D 'pcb_standoff=4' schaltbox.scad
```
