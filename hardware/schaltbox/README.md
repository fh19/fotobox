# Schaltbox — Netzverteilung und Lampenschalter

Ein Kasten von **80 × 50 × 90 mm** zum Einbau ins Fotobox-Gehäuse.

```
Vorderwand   die unteren zwei Euro-Buchsen, Säule am linken Rand
Rückwand     die dritte Buchse, genau gegenüber ihrer Position in der Säule
rechte Wand  die Kaltgerätebuchse, hochkant und unten
             (Netzanschluss + Feinsicherung + Hauptschalter in einem Teil)
```

Die **Rückwand ist der Deckel** und wird von hinten mit vier M3-Schrauben in
**Messing-Schmelzbuchsen** verschraubt; die Dome dafür sitzen in den vier Ecken.
Laschen gibt es nicht — sie stünden nur im Weg.

Zwischen der mittleren und der oberen Dose läuft ein **Steg über die gesamte
Breite**; darauf sitzt das SSR. Ein zweiter Steg zwischen den beiden vorderen
Öffnungen reicht von der linken Wand bis knapp hinter die Säule und bindet die
Vorderwand nach hinten an: drei Ausschnitte und die dünnen Snap-Felder daneben
lassen sie sonst federn.

**Beide Stege reichen bis an die Rückwand.** Die Kabel gehen nicht mehr hinten
herum, sondern durch eine **U-förmige Aussparung** im oberen Steg — zum Deckel
hin offen, sodass sich ein Bündel von hinten einlegen lässt statt eingefädelt zu
werden. Sie sitzt links neben dem SSR.

Für das **Steuerkabel** hat die rechte Wand über dem Steg ein **8-mm-Loch**,
direkt neben der Platine. Der Steg trennt es von der Kaltgerätebuchse darunter —
Netz und 3,3 V teilen sich damit kein Stück Wand.

```
Dateien   schaltbox_parts.scad   gemessene Maße und die Vorgaben
          schaltbox.scad         Geometrie, mit Passungsbericht
```

## Das Maß ist die Vorgabe — also wird geprüft, nicht gerechnet

```
Aussen 80 x 50 x 90  ->  innen 74 x 44 x 84
Verbindung loeten: Kaltgeraetebuchse 29 mm, Euro 35 mm
Dosen ragen 35 mm in 44 mm Tiefe -> passt
Buchse ragt 29 mm in 74 mm Breite -> passt
  Ausschnitt hochkant 48 hoch x 27.4 tief auf 84 x 44 -> passt
Steg auf z=54, Buchse endet bei 51 -> frei
Ueber dem Steg, rechts der Saeule: 25 breit x 44 tief x 27.5 hoch
  SSR allein 25 mm hoch -> passt
  mit Platine 26.6 mm -> passt
```

**Löten ist Pflicht.** Mit Flachsteckern ragen die Dosen 50 mm in 44 mm Tiefe.

**Der Steg liegt so tief wie möglich**, nicht mittig: nach unten begrenzen ihn
die Kaltgerätebuchse (endet bei z = 51) und die mittlere Dose, nach oben zählt
jeder Millimeter für das SSR. So bleiben **27,5 mm**, und die Platine mit dem
stehenden `AQ2A2-ZP3` braucht 26,6.

**Die Platine liegt flach auf dem Steg**, ohne Abstandshalter — dafür ist kein
Platz. Die Schrauben gehen direkt in die 5 mm Kunststoff des Stegs; die Löcher
sind vorgesehen. Und sie muss **quer** bestückt sein: 33 mm SSR passen längs der
Tiefe (44 mm), quer sind nur 25 frei.

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
die 20-mm-Seite stapelt sich über die Höhe. Für die Dose im Deckel gilt dasselbe,
nur ist dort die Wand 3 mm dick statt der Gehäusewand. Beim
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
