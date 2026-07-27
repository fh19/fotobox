# Druck-Layout

## Die Zahlen

Der Selphy CP1500 druckt mit **300 × 300 dpi**. Die native Rastergröße für Postkartenformat
(100 × 148 mm, 4 × 6") ist **1248 × 1872 Pixel** — exakt 2:3. Das ist im Gutenprint-Treiber
so hinterlegt (`selphy_print.c`, Größe `P`).

Das trifft sich gut: eine Nikon-DSLR liefert ebenfalls 3:2. Ein Ergebnisbild wird also
**nicht beschnitten**, sondern nur skaliert — vorausgesetzt, die Pipeline behält das
Seitenverhältnis bei.

**Aber:** Der Treiber vergrößert für den randlosen Druck um etwa 4 % („overspray"), und
das ist nicht abschaltbar. Umlaufend gehen dadurch rund **2 % je Kante** verloren.

## Konsequenz für das Layout

```
┌─────────────────────────────────────────┐  1248 × 1872 px  (Vollformat, wird gedruckt)
│ ░░░░░░░░░░░ Anschnitt ░░░░░░░░░░░░░░░░░ │
│ ░ ┌───────────────────────────────────┐ │
│ ░ │                                   │ │  Sicherer Bereich:
│ ░ │       Motiv + Rahmentext          │ │  1198 × 1798 px
│ ░ │                                   │ │  Offset 25 px links/rechts,
│ ░ └───────────────────────────────────┘ │         37 px oben/unten
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
└─────────────────────────────────────────┘
```

- **Ausgabedatei:** immer 1248 × 1872 px, JPEG, Qualität 95, sRGB
- **Sicherer Bereich:** alles, was lesbar bleiben muss — Text, Datum, Namen, QR-Code —
  liegt innerhalb von 1198 × 1798 px, zentriert
- **Gesichter:** die Pipeline schneidet nicht automatisch. Wer sich am Bildrand aufstellt,
  verliert 2 % — das ist akzeptabel und der Grund, warum der Kalibrierrahmen im Live-Bild
  den *sicheren* Bereich markiert, nicht den vollen Sensorausschnitt.

Diese Werte gehören als `printing.canvas_width`, `canvas_height`, `safe_margin_x`,
`safe_margin_y` in die Config, nicht in den Code.

## Verarbeitungskette

```
original.jpg (z. B. 4928 × 3264, 3:2)
   │
   ├─ Freistellen (chroma | ai)  oder  unverändert (overlay | none)
   │
   ├─ Hintergrund komponieren   background.jpg auf 1248 × 1872 gefüllt (cover, zentriert)
   │
   ├─ Overlay auflegen          overlay.png, exakt 1248 × 1872, mit Alphakanal
   │
   ├─ Rahmentext rendern        aus printing.caption, lokale Schriftdatei
   │
   ├─ QR-Code (optional)        printing.qr_enabled, unten rechts, 150 × 150 px,
   │                            inkl. 4 Modulen Ruhezone, im sicheren Bereich
   │
   └─ processed/IMG_0143.jpg (1248 × 1872)  →  prints/IMG_0143.jpg (identisch)
```

`processed` und `print` sind bei Postkartenformat dieselbe Datei. Sie werden trotzdem
getrennt geführt, weil ein späteres Zusatzformat (Streifen, Sticker) nur `print` betrifft.

## Hochformat vs. Querformat

Die Box steht fest, die Kamera ist fest montiert. **Ausrichtung wird einmal in der Config
festgelegt** (`printing.orientation: portrait | landscape`) und gilt für den ganzen Abend.
Keine automatische Erkennung, keine gemischten Formate — sonst passt der Rahmen nicht mehr
und die Kalibrierung ist wertlos.

Bei `landscape` sind Leinwand und sicherer Bereich getauscht: 1872 × 1248 bzw. 1798 × 1198.
Das Cassette-Format bleibt Postkarte; der Selphy dreht selbst nichts.

## Schriften

Die Schriftdatei liegt unter `/data/assets/fonts/` und wird per Pfad referenziert. Keine
Systemschrift, kein Fontconfig — auf einem read-only Root-Dateisystem ist das eine
Fehlerquelle ohne Nutzen.

Vorschlag Rahmentext, konfigurierbar:

```yaml
printing:
  caption:
    enabled: true
    text: "Anna & Ben · 15. August 2026"
    position: bottom_center
    font: /data/assets/fonts/Cormorant-Regular.ttf
    size_px: 44
    color: "#ffffff"
    shadow: true
```

Schatten ist kein Zierrat: weißer Text auf einem hellen Hintergrundbild ist sonst
unlesbar, und welches Bild dahinter liegt, weiß man vorher nicht.

## CUPS-Aufruf

```
lp -d Selphy_CP1500 \
   -o media=Postcard \
   -o StpBorderless=True \
   -o fit-to-page \
   prints/IMG_0143.jpg
```

Nicht direkt aufrufen — über `pycups` und den `PrinterBackend`. Der genaue Optionssatz muss
in Meilenstein 6 am echten Gerät verifiziert werden; die Namen der Gutenprint-Optionen
weichen je nach PPD ab.

## Zeitrechnung

Ein Postkartendruck dauert etwa **41 Sekunden** (Dye-Sublimation, vier Durchläufe).
Ein Farbband/Papier-Set reicht für **108 Blatt**.

Daraus folgt:

- Der Druck darf die Session **nicht blockieren**. `PRINTING` endet, sobald der Job an CUPS
  übergeben ist — nicht, wenn das Blatt fertig ist. Sonst steht der nächste Gast 40 s.
- Bei Andrang bildet sich eine Warteschlange. Die ist unproblematisch, solange sie sichtbar
  ist: der Admin-Screen zeigt die Länge, und ab `printing.queue_warn_length` (Standard 5)
  erscheint in `PREVIEW` unter dem Druck-Button dezent: „Dein Bild kommt in Kürze aus dem
  Drucker".
- Ein Limit von einem Druck pro Foto ist der Standard. 108 Blatt sind bei 120 Gästen
  schneller weg, als man denkt.
