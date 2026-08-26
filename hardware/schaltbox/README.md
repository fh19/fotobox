# Schaltbox — Netzverteilung und Lampenschalter

Ein Riegel von **50 × 60 × 120 mm** zum Einbau ins Fotobox-Gehäuse. Auf der
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

Bisher ergab sich die Größe aus den Teilen. Jetzt ist sie gesetzt, also müssen
sich die Teile fügen. Jeder Render gibt aus, was passt und was nicht:

```
Aussen 120 x 50 x 60  ->  innen 114 x 44 x 54
Verbindung loeten: Kaltgeraetebuchse 29 mm, Euro 35 mm
Unterseite, Teile ragen in z (54 frei): passt
Linke Seite, Teile ragen in y (44 frei): passt
Platine+SSR 32.6 mm; ueber den Unterseiten-Teilen 19 mm frei -> PASST NICHT
```

### Löten ist bei dieser Größe Pflicht

Die Euro-Buchsen ragen mit Flachsteckern **50 mm** hinein, innen sind in y aber
nur **44 mm**. Die beiden linken Buchsen passen damit nicht. Mit Lötverbindung
sind es 35 mm, und alle vier Einbauteile gehen hinein. `connection = "loeten"`.

### Die Platine mit stehendem SSR passt nicht

Über den Teilen der Unterseite bleiben **19 mm**, die Platine mit dem stehenden
AQ2A2-ZP3 braucht **32,6 mm**. Neben den linken Buchsen sind es sogar nur 9 mm.
Drei Wege:

1. **Flache SSR-Bauform** `AQ2A2-J-ZP3` — 33 × 25 × **11 mm** statt 33 × 10 × 25.
   Mit `ssr_flat = true` und `pcb_standoff = 4` bleiben 2,4 mm Luft, die Platine
   liegt über allem. Das ist die Lösung ohne Kompromiss, falls unter deinen
   Exemplaren eine flache ist.
2. **Gehäuse 14 mm höher**, also `box = [120, 50, 74]`. Dann passt die stehende
   Bauform.
3. **SSR außerhalb dieser Box.** Sie wird zur reinen Verteilung, das Relais sitzt
   näher am Pi. Kostet zwei zusätzliche Netzadern für den Lampenzweig, trennt
   dafür Netz und Steuerung vollständig.

Voreingestellt ist `with_pcb = false` — die Box wie gezeichnet, ohne Platine.

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
openscad -o deckel.stl    -D 'part="deckel"'    schaltbox.scad

# mit flachem SSR und Platine
openscad -D 'part="beides"' -D 'connection="loeten"' \
         -D 'with_pcb=true' -D 'ssr_flat=true' -D 'pcb_standoff=4' schaltbox.scad
```
