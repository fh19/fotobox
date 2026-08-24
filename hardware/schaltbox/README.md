# Schaltbox — Netzverteilung und Lampenschalter

Ein Einbaugehäuse für das Fotobox-Gehäuse. Darin: das Halbleiterrelais für die
Fotolampe auf einer kleinen Platine, ein 1-A-Feinsicherungshalter, drei
Euro-Steckdosen für die Versorgung der Box und eine Kabeleinführung.

```
Außenmaß  132 × 105 × 45 mm   (ergibt sich aus den Teilen, siehe unten)
Dateien   schaltbox_parts.scad   gemessene Maße, nur hier ändern
          schaltbox.scad         Geometrie
```

## Aufteilung

Das Gehäuse ist innen durch einen **Trennsteg** in zwei Bereiche geteilt, und das
ist der eigentliche Grund, warum sich der Druck lohnt:

```
   ┌──────────────────────────────────────────────┐
   │  [Steckdose] [Steckdose] [Steckdose]         │  Vorderwand
   │                                              │
   │   Verdrahtungsstreifen: Netz                 │
 ○ │   Kabeleinführung ←            → Sicherung   │ ○   kurze Wände
   │                                              │
   │ ════════════ Trennsteg ═══════════════════   │
   │                                              │
   │   [2-pol] ── SSR ── [3-pol]   auf Platine    │  Steuerseite
   │                                              │
   └───────────────────○──────────────────────────┘  Steuerleitung
```

Die Netzseite hat ihre eigene Einführung, die Steuerleitung vom Pi ihre eigene.
Die 3,3 V teilen sich damit keinen Weg mit 230 V.

Der Verdrahtungsstreifen hinter den Steckdosen ist nicht Zierde: Der
Sicherungshalter ragt **32 mm** in das Gehäuse, die Steckdosenkörper **26 mm** —
ohne diesen Streifen säße die Sicherung in der dritten Steckdose.

## Was gemessen werden muss

Nur ein Bauteil steht fest, weil es ein Datenblatt hat:

| Teil | Maß | Quelle |
|---|---|---|
| SSR AQ2A2-ZP3 | 33 × 10 × 25 mm, 4 Pins Ø0,8, Raster 7,62/12,7/5,08 | Datenblatt |
| Schraubklemmen | Tiefe, Höhe | **messen** |
| Sicherungshalter | Lochdurchmesser, Einbautiefe | **messen** |
| Euro-Steckdosen | Ausschnitt, Einbautiefe | **messen** |

Alles mit `MESSEN` markierte in `schaltbox_parts.scad` ist ein Platzhalter, der
nicht zufällig passen wird. Besonders die Steckdosen: „Euro-Steckdose" nennt eine
Form, keine Größe. Für runde Ausschnitte `socket_round = true` setzen.

Nach dem Ändern rechnet sich das Gehäuse selbst neu — Innenmaße, Trennsteg und
Platinenfüße folgen den Teilen.

## Verdrahtung

```
Netz ein (Kabelverschraubung)
   PE ──────────────────────────┬── Steckdosen (PE)
                                └── 3-pol Klemme, Pin PE  → Lampe
   N  ──────────────────────────┬── Steckdosen (N)
                                └── 3-pol Klemme, Pin N   → Lampe
   L  ──── Sicherung 1 A ───────┬── Steckdosen (L)
                                └── SSR Pin 1  ┐
                     SSR Pin 2 ───► 3-pol Klemme, Pin L → Lampe (geschaltet)

Steuerleitung vom Pi (eigene Einführung)
   GPIO 17 ──► 2-pol Klemme ──► SSR Pin 3 (+)      optional 100 nF
   GND     ──► 2-pol Klemme ──► SSR Pin 4 (−)      über Pin 3/4
```

**PE wird nie geschaltet** und läuft durchgehend. Geschaltet wird ausschließlich
L, und zwar nur der Zweig zur Lampe — die Steckdosen bleiben immer versorgt.

**Zur Sicherung:** 1 A sind bei 230 V rund 230 W. Schützt sie **nur den
Lampenzweig** (50 W ≈ 0,22 A), ist sie großzügig und richtig. Sitzt sie dagegen
vor allem, teilen sich Pi, Drucker und Lampe diese 230 W — der Selphy zieht beim
Drucken kräftig, das kann eng werden. Die Zeichnung oben legt sie deshalb in den
gemeinsamen L-Pfad; wer sie nur für die Lampe will, setzt sie zwischen Verteilung
und SSR Pin 1.

## Drucken

- **Kein PLA.** Es erweicht bei etwa 60 °C und brennt bereitwillig. Flammhemmendes
  Filament mit UL94 V-0 nehmen (PC/ABS FR, ABS-FR oder PETG V0).
- **Wandstärke 3 mm** ist die Vorgabe in `schaltbox_parts.scad` und die Untergrenze,
  nicht ein Ziel. Eine FDM-Wand ist entlang der Schichtgrenzen porös und ist
  elektrisch nicht das, was eine gespritzte gleicher Dicke wäre.
- **Der Druck hält, isolieren muss etwas anderes.** Spannungsführende Teile
  zusätzlich mit Schrumpfschlauch oder Klemmenabdeckung versehen.
- Liegend drucken, Öffnung nach oben. Stützen braucht nur der Kragen der
  Kabelverschraubung.
- Schrauben: M3 selbstschneidend in die Dome, Lochdurchmesser über `screw_pilot`.

## Rendern

```bash
openscad -o unterteil.stl -D 'part="unterteil"' schaltbox.scad
openscad -o deckel.stl    -D 'part="deckel"'    schaltbox.scad
openscad -D 'part="explosion"' schaltbox.scad        # Ansicht mit Einbauten
```

`part` kennt `unterteil`, `deckel`, `beides` und `explosion`.
