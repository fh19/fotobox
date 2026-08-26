# Schaltbox — Netzverteilung und Lampenschalter

Ein Einbaugehäuse für das Fotobox-Gehäuse. Darin: das Halbleiterrelais für die
Fotolampe auf einer kleinen Platine, drei Euro-Buchsen für die Versorgung der Box
und eine Kaltgerätebuchse, die Netzanschluss, Feinsicherung und Hauptschalter in
einem Teil mitbringt.

```
Dateien   schaltbox_parts.scad   gemessene Maße, nur hier ändern
          schaltbox.scad         Geometrie
```

## Vier Größen — du hast die Wahl

Zwei Entscheidungen bestimmen das Format, beide oben in `schaltbox_parts.scad`:

| | `flachstecker` | `loeten` |
|---|---|---|
| **`socket_upright = true`** | 123 × 119 × 56 mm | **112 × 119 × 56 mm** |
| **`socket_upright = false`** | 192 × 119 × 45 mm | 181 × 119 × 45 mm |

**Stehende Buchsen** ergeben ein schmales, hohes Gehäuse; **liegende** ein breites,
flaches. Bei liegenden Buchsen stecken die Stifte nebeneinander und das Kabel geht
seitlich ab — das solltest du vor dem Drucken einmal durchdenken.

**Löten statt Flachstecker** spart 11 mm (Kaltgerätebuchse: 29 statt 40) und
15 mm (Euro-Buchse: 35 statt 50). Der Preis: eine Lötstelle an einer Flachsteckfahne
ist spröder als eine Crimpverbindung, und diese Box wird transportiert. Deshalb ist
`flachstecker` die Voreinstellung.

## Aufteilung

```
   ┌──────────────────────────────────────────────┐
   │  [Buchse] [Buchse] [Buchse]                  │  Vorderwand
   │                                              │
 ▤ │   Verdrahtungsstreifen: Netz                 │   ▤ = Kaltgerätebuchse
   │                                              │       mit Sicherung + Schalter
   │ ════════════ Trennsteg ═══════════════════   │
   │   [2-pol] ── SSR ── [3-pol]   auf Platine    │  Steuerseite
   └───────────────────○──────────────────────────┘
                  Steuerleitung
```

Ein **Trennsteg** teilt das Innere: vorn Netz, hinten die Steuerung. Die
Steuerleitung vom Pi hat ihre eigene Einführung, damit sich 3,3 V keinen Weg mit
230 V teilen. Das Netz braucht keine mehr — es kommt durch die Kaltgerätebuchse.

Die Tiefe der Netzseite ergibt sich aus zwei Dingen: die Buchsenkörper ragen 50 mm
(bzw. 35 mm) hinein, und die Kaltgerätebuchse liegt mit ihren 48,1 mm quer davor.
Der Streifen dahinter nimmt die Verdrahtung auf.

## Dünne Wand für die Snaps

Ein Snap-in-Teil will eine dünne Platte, ein Netzgehäuse eine dicke Wand. Die Wand
bleibt deshalb 3 mm und wird **nur um jede Öffnung herum** ausgedünnt:

- Kaltgerätebuchse: auf **1,5 mm**, an den beiden langen Kanten
- Euro-Buchsen: auf **2,0 mm**, an den beiden schmalen Kanten

Die Taschen laufen mit 45° aus. Eine Stufe wäre eine Decke, die der Drucker
überbrücken müsste. Und sie greifen nur dort, wo die Snaps sitzen — würde man
ringsum ausdünnen, flössen die drei Steckdosentaschen zu einem einzigen schwachen
Feld zusammen, weil ihr Abstand genau einer Taschenbreite entspricht.

**Die Flansche bestimmen die Gehäusehöhe.** Der Steckdosenrahmen ist 44 mm hoch und
muss auf der Wand aufliegen, nicht über ihre Kante ragen — daraus folgt die
Innenhöhe, nicht aus dem SSR.

Beim Kaltgeräteeinbau überdeckt der Flansch die Öffnung nur um **1,45 mm je Seite**.
Der Ausschnitt muss also genau sitzen und die Wand ringsum eben sein. Die beiden
angefasten Ecken (5 mm) an einer Schmalseite sind die Verdrehsicherung und stecken
in der Geometrie.

## Was noch gemessen werden muss

| Teil | Maß | Stand |
|---|---|---|
| SSR AQ2A2-ZP3 | 33 × 10 × 25 mm, Pins 7,62/12,7/5,08 | Datenblatt |
| Kaltgerätebuchse | Ausschnitt 48,1 × 27,6, Flansch 51 × 31, 40 mm tief | gemessen |
| Euro-Buchse | Ausschnitt 13,2 × 34, Flansch 20 × 44, 50 mm tief | gemessen |
| Schraubklemmen | Tiefe, Höhe | **messen** |
| Platine | Größe, Lochbild | nach Bedarf |

## Verdrahtung

```
Kaltgerätebuchse (Netz + Sicherung 1 A + Schalter)
   PE ──────────────────────────┬── Euro-Buchsen (PE, falls vorhanden)
                                └── 3-pol Klemme, Pin PE  → Lampe
   N  ──────────────────────────┬── Euro-Buchsen (N)
                                └── 3-pol Klemme, Pin N   → Lampe
   L  (geschaltet, abgesichert) ┬── Euro-Buchsen (L)
                                └── SSR Pin 1  ┐
                     SSR Pin 2 ───► 3-pol Klemme, Pin L → Lampe (geschaltet)

Steuerleitung vom Pi (eigene Einführung)
   GPIO 17 ──► 2-pol Klemme ──► SSR Pin 3 (+)      optional 100 nF
   GND     ──► 2-pol Klemme ──► SSR Pin 4 (−)      über Pin 3/4
```

**PE wird nie geschaltet.** Der Schalter der Kaltgerätebuchse trennt L (bei
zweipoligen Ausführungen L und N) für alles; das SSR schaltet danach nur noch den
Lampenzweig. Die Steckdosen bleiben versorgt, solange der Hauptschalter an ist.

**Zur Sicherung:** 1 A sind bei 230 V rund 230 W, und sie sitzt in der
Kaltgerätebuchse — also vor allem. Pi, Drucker und Lampe teilen sich diese 230 W.
Der Selphy zieht beim Drucken kräftig; falls die Sicherung fällt, ist nicht sie zu
klein gewählt, sondern die Summe zu groß.

## Drucken

- **Kein PLA.** Erweicht bei etwa 60 °C und brennt bereitwillig. Flammhemmendes
  Filament mit UL94 V-0 (PC/ABS FR, ABS-FR oder PETG V0).
- **Wandstärke 3 mm** ist die Untergrenze, nicht das Ziel — außer den ausgedünnten
  Feldern um die Snaps, und die sind so dünn, wie die Teile es verlangen.
- **Der Druck hält, isolieren muss etwas anderes.** Eine FDM-Wand ist entlang der
  Schichtgrenzen porös. Spannungsführende Teile zusätzlich mit Schrumpfschlauch
  oder Klemmenabdeckung versehen.
- Liegend drucken, Öffnung nach oben. Die Snap-Taschen laufen mit 45° aus und
  brauchen keine Stützen.
- Schrauben: M3 selbstschneidend in die Dome.

## Rendern

```bash
openscad -o unterteil.stl -D 'part="unterteil"' schaltbox.scad
openscad -o deckel.stl    -D 'part="deckel"'    schaltbox.scad
openscad -D 'part="beides"' schaltbox.scad          # mit Einbauten
openscad -D 'part="unterteil"' -D 'socket_upright=false' -D 'connection="loeten"' schaltbox.scad
```
