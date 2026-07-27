# Bedienungsanleitung — Fotobox

Autarke Fotobox für Hochzeiten und Feiern. Sie läuft **komplett offline**: eine
Vorschaukamera für das Live-Bild, eine Spiegelreflexkamera (DSLR) für das eigentliche
Foto, ein Fotodrucker für den Sofort-Abzug. Bedient wird alles über den **Touchscreen**.

---

## 1. Überblick in einem Satz

Gast tippt auf den Bildschirm → wählt einen Hintergrund/Rahmen → ein Countdown läuft →
das Foto wird aufgenommen, bearbeitet und angezeigt → Gast druckt es oder ist fertig.
Alle Fotos werden gespeichert und lassen sich nach der Feier herunterladen.

---

## 2. Vor der Veranstaltung — Aufbau

### 2.1 Anschließen (Reihenfolge beachten)

1. **Kamera** (DSLR) per USB anschließen und **einschalten**.
2. **Drucker** (Canon Selphy CP1500) per USB anschließen, Papier und Farbkassette
   einlegen, **einschalten**.
3. **Vorschaukamera** anschließen (fest verbaut, meist schon montiert).
4. Erst **jetzt** die Fotobox mit Strom versorgen.

> **Wichtig:** Die DSLR sollte **eingeschaltet sein, bevor** die Box hochfährt. Wird sie
> erst später eingeschaltet, im Admin einmal die Kamera neu auswählen (Abschnitt 4) oder
> die Box neu starten — sonst bleibt sie als „nicht verfügbar" stehen.

### 2.2 Hochfahren

Die Box startet automatisch in den Vollbild-Kiosk. Nach ~30–60 s erscheint der
Startbildschirm mit dem Live-Bild und dem Text **„Bereit für dein Foto?"**. Es ist
keine Anmeldung nötig.

### 2.3 Startcheck (im Admin)

In den Admin-Bereich gehen (Abschnitt 4) und unter **Status** prüfen:

- **Kamera:** verfügbar, richtiges Modell
- **Drucker:** Status „idle", nicht pausiert, Restblätter plausibel
- **Speicher:** genug frei

Dann einmal **Testdruck** auslösen (Drucker-Kachel) — verbraucht **ein Blatt**, zeigt aber
sofort, dass die ganze Druckkette funktioniert.

### 2.4 Ausrichtung festlegen

Die Kamera in der gewünschten Ausrichtung montieren (Hoch- oder Querformat) und im Admin
unter **Kamera** auf **„Ausrichtung kalibrieren (Probefoto)"** tippen. Die Box nimmt ein
Probefoto und stellt das Druckformat automatisch passend ein.

### 2.5 Eigene Rahmen hochladen (optional)

Im Admin unter **Hintergründe & Rahmen** ein PNG hochladen (siehe Abschnitt 6). So bekommt
jedes Foto z. B. einen farbigen Rahmen mit Namen und Datum.

### 2.6 Neues Event anlegen

Im Admin unter **Event** einen Namen eingeben (z. B. „Hochzeit Anna & Ben") und
**„Neues Event anlegen"**. Alle Fotos des Abends werden darunter gesammelt.

---

## 3. So bedienen die Gäste

Der Ablauf ist selbsterklärend — Gäste brauchen keine Einweisung.

| Schritt | Was auf dem Bildschirm passiert |
|---|---|
| **Start** | Live-Bild mit **„Bereit für dein Foto?" / „Tippe auf den Bildschirm"**. Der ganze Bildschirm ist die Taste. |
| **Hintergrund** | **„Wähle deinen Hintergrund"** — eine Reihe Kacheln (erste immer **„Ohne Hintergrund"**). Antippen startet **sofort** den Countdown. |
| **Countdown** | Große Ziffer zählt herunter, bei `1` steht **„Lächeln!"**. |
| **Auslösen** | Kurzer heller „Blitz". |
| **Verarbeitung** | **„Einen Moment … / Dein Foto wird fertig gemacht"**. |
| **Vorschau** | Das fertige Foto, darunter **„Drucken"** und **„Fertig"**. |
| **Fertig** | Nach dem Antippen (oder automatisch nach 30 s) zurück zum Start. |

Hinweise:
- Wird die Hintergrundauswahl in den Einstellungen abgeschaltet, geht es nach dem Tippen
  **direkt** in den Countdown (immer derselbe voreingestellte Rahmen).
- **Drucken** ist auf **einen Abzug pro Foto** begrenzt. Nach dem Druck wechselt der Button
  kurz zu **„Wird gedruckt …"**.
- Ist Drucken gerade nicht möglich, verschwindet der Druck-Knopf einfach — die Fotos werden
  trotzdem gespeichert und lassen sich später drucken/laden.
- Bei einem Problem erscheint kurz **„Da ist etwas schiefgelaufen"**; die Box kehrt von
  selbst zum Start zurück. **Ein Fehler beendet nie den Betrieb.**

---

## 4. Admin-Bereich

**Zugang:** Auf dem Startbildschirm die **obere linke Ecke 5 Sekunden** gedrückt halten →
PIN-Feld → PIN **`2606`** → **Anmelden**.
Alternativ im Browser eines Geräts im selben Netz: `http://<IP-der-Box>:8000/admin`.

Die Kacheln:

| Kachel | Wofür |
|---|---|
| **Status** | Kamera, Drucker, Speicher, CPU-Temperatur, Uptime, letzte Log-Einträge |
| **Drucker** | **„Drucker fortsetzen"** (nach Papier-/Bandwechsel), Warteschlange leeren, Testdruck, Druckzähler zurücksetzen |
| **Kamera** | Haupt-/Vorschaukamera wählen, **Ausrichtung kalibrieren** |
| **Hintergründe & Rahmen** | Rahmen/Hintergründe hochladen, auflisten, löschen (Abschnitt 6) |
| **Einstellungen** | Countdown-Dauer, Timeouts, Druck-Limits, Hintergrundauswahl ein/aus |
| **Event** | Aktives Event, Bildzahl, neues Event anlegen |
| **Netzwerk** | Access-Point ein/aus, IP-Adresse, Galerie-URL (Abschnitt 7) |
| **Export** | Aktives Event auf USB-Stick kopieren (Abschnitt 7) |
| **System** | Fotobox neu starten, Herunterfahren |

Der wichtigste Knopf des Abends ist **„Drucker fortsetzen"** — er behebt das häufigste
Problem (Papier/Kassette leer).

### Werden Einstellungen gespeichert?

Ja. Änderungen im Admin werden dauerhaft gespeichert und **überstehen einen Neustart**:
Einstellungen (Countdown, Timeouts, Limits, Hintergrundauswahl), die **Kamera-/Vorschau-
Auswahl**, die **Ausrichtung**, angelegte **Events** und hochgeladene **Rahmen**.

Zwei Ausnahmen — **bewusst nicht dauerhaft**:

- Der **Access-Point** ist nach einem Neustart wieder **aus** (Sicherheitsnetz, damit die
  Box immer ins normale Netz zurückkehrt). Nach einem Neustart bei Bedarf erneut
  einschalten.
- Die **Druckzähler** überstehen Neustarts. „Gedruckt (Event)" zählt die fertigen Drucke
  des laufenden Events, „Gedruckt (gesamt)" läuft bis zum nächsten Zurücksetzen weiter.
  Eine Restanzeige des Bandvorrats gibt es nicht — der Drucker meldet den Bandstand nicht.

---

## 5. Während der Feier — wiederkehrende Handgriffe

### Papier oder Farbkassette wechseln
Wenn der Drucker stoppt (leer): neues Papier / neue Kassette einlegen, dann im Admin
**Drucker → „Drucker fortsetzen"**. Mehr ist nicht nötig — die Druckzähler hängen nicht
am Papiervorrat.

### Kamera-Akku wechseln
DSLR ausschalten, Akku tauschen, wieder einschalten. Falls die Box die Kamera danach als
„nicht verfügbar" zeigt: Admin → **Kamera** → Kamera erneut übernehmen.

### Fehlermeldung auf dem Gästebildschirm
Nichts tun müssen — die Box fängt sich selbst und geht zurück zum Start. Häuft sich ein
Fehler, im Admin unter **Status** die letzten Log-Einträge ansehen.

---

## 6. Rahmen & Hintergründe

Vier Modi (Admin → **Hintergründe & Rahmen**, Feld **Modus**):

- **Rahmen** (`frame`) — das Foto wird in den **transparenten Fensterbereich** deines PNG
  eingepasst, der Rahmen liegt drumherum. Für farbige Rahmen mit Namen/Datum.
- **Overlay** — das PNG wird **über** das Foto gelegt (deckt die Ränder leicht ab).
- **Greenscreen** / **KI-Freisteller** — Person freistellen und vor ein Hintergrundbild
  setzen.

**Ein Rahmen-PNG richtig anlegen:**
- Größe **1248 × 1872 px** (Hochformat) bzw. **1872 × 1248 px** (Querformat), **mit
  Transparenz** (RGBA-PNG).
- In der Mitte ein **transparentes Fenster** (dort erscheint das Foto), am besten im
  **3:2-Format** — dann füllt das Foto es randfüllend ohne Beschnitt.
- Text/Verzierung außen herum. Lesbares (Namen, Datum) mindestens **25 px** vom Rand
  entfernt, weil der randlose Druck ganz außen ~2 % abschneidet.

**Für jedes Bild denselben Rahmen:** Admin → **Einstellungen** → „Hintergrundauswahl
anzeigen" **aus**, und den Rahmen als Standard setzen.

---

## 7. Nach der Veranstaltung

### Fotos für Gäste bereitstellen (Galerie über WLAN)
1. Admin → **Netzwerk** → **„Access-Point einschalten"**.
   ⚠️ Dabei bricht eine bestehende WLAN-Verbindung der Box ab — am **Touchscreen** bedienen.
2. Gäste verbinden ihr Handy mit dem WLAN **„Fotobox"**.
3. Die im Admin angezeigte **Galerie-URL** öffnen (`http://192.168.4.1:8000/gallery`).
   Dort: alle Fotos ansehen, zwischen **„Mit Hintergrund"** und **„Original"** umschalten,
   **„Alle Fotos herunterladen (ZIP)"**.
4. Danach den Access-Point wieder ausschalten (oder neu starten).

### Fotos auf USB-Stick sichern
USB-Stick (FAT32/exFAT) einstecken → Admin → **Export** → **„Auf USB-Stick kopieren"**.
Der Fortschritt wird angezeigt; kopiert wird das **komplette aktive Event**.

### Ausschalten
**Immer** über Admin → **System → „Herunterfahren"** — erst danach den Strom trennen.
**Nie einfach den Stecker ziehen** (schützt die SD-Karte). Zum Weiterarbeiten ohne
Stromtrennung: **„Fotobox neu starten"**.

---

## 8. Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| „Kleine Pause — die Fotobox ist gleich wieder da" | Kamera nicht verfügbar. DSLR einschalten/prüfen; Admin → Kamera erneut übernehmen. |
| Countdown läuft, aber es kommt „Die Kamera hat nicht reagiert" | Die DSLR hat nicht ausgelöst (meist Autofokus findet keine Schärfe). **Objektiv auf `MF` (manueller Fokus) stellen** und die Schärfe einmal fest einstellen — dann löst sie immer aus. Die Box heilt sich nach wenigen Sekunden von selbst zurück zum Start. |
| Druck-Knopf fehlt in der Vorschau | Drucker nicht bereit (leer/pausiert). Papier/Kassette prüfen, „Drucker fortsetzen". Fotos sind gespeichert. |
| Drucker stoppt mitten im Abend | Papier oder Farbband leer → nachlegen → „Drucker fortsetzen". |
| Ausdruck hat einen weißen Rand | Randlos-Einstellung; im Normalbetrieb bereits korrekt. Falls nicht, Support/Technik. |
| Bildschirm bleibt schwarz | Monitor/Strom prüfen. Reagiert nichts, Box neu starten (Strom nur als letzte Option trennen). |
| „Der Speicher ist voll" | Alte Events per USB sichern und Platz schaffen. |
| Gäste finden das WLAN nicht | Access-Point im Admin eingeschaltet? WLAN heißt „Fotobox". |

---

## 9. Aktuelle Einstellungen (Stand der Box)

| Einstellung | Wert |
|---|---|
| Ausrichtung | Hochformat |
| Countdown | 4 s (in den Einstellungen änderbar, üblich 5 s) |
| Vorschau-Timeout | 30 s |
| Fehler-Timeout | 6 s |
| Hintergrundauswahl | ein |
| Standard-Hintergrund | Ohne Hintergrund |
| Drucke pro Foto | 1 |
| Kontingent pro Event | 108 (eine Farbkassette) |
| WLAN-Name (Access-Point) | Fotobox |
| Galerie-Adresse (im AP) | http://192.168.4.1:8000/gallery |
| Admin-PIN | 2606 |

Diese Werte lassen sich im Admin (Einstellungen / Netzwerk) jederzeit ändern.
