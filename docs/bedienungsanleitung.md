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

### Wenn gerade niemand fotografiert

Nach **5 Minuten** ohne Bedienung zeigt die Box die Bilder des Abends in zufälliger
Reihenfolge, formatfüllend. **Der erste Tipp macht kein Foto** — er holt nur den
Startbildschirm zurück; erst die zweite Berührung löst aus. Sonst würde die Box jeden
fotografieren, der sie bloß aufwecken wollte.

### Galerie am Bildschirm

Unten rechts auf dem Startbildschirm führt **„Galerie"** zu den bisherigen Fotos —
dieselbe Ansicht wie am Handy. Durchblättern mit Wischen oder den Pfeilen, und über den
runden Knopf unten rechts im Bild lässt sich ein Foto **noch einmal drucken**. Nach einer
Minute ohne Bedienung kehrt die Box von selbst zur Fotobox zurück.

---

## 4. Admin-Bereich

**Zugang:** Auf dem Startbildschirm die **obere linke Ecke 5 Sekunden** gedrückt halten →
PIN-Feld → PIN **`2606`** → **Anmelden**.
Alternativ im Browser eines Geräts im selben Netz: `http://<IP-der-Box>/admin`.

Die Kacheln:

| Kachel | Wofür |
|---|---|
| **Status** | Kamera, Drucker, Speicher, CPU-Temperatur, Uptime, letzte Log-Einträge |
| **Drucker** | **„Drucker fortsetzen"** (nach Papier-/Bandwechsel), Warteschlange leeren, Testdruck, Druckzähler zurücksetzen |
| **Kamera** | Haupt-/Vorschaukamera wählen, **Ausrichtung kalibrieren** |
| **Hintergründe & Rahmen** | Rahmen/Hintergründe hochladen, auflisten, löschen (Abschnitt 6) |
| **Einstellungen** | Countdown-Dauer, Timeouts, Druck-Limits, Hintergrundauswahl ein/aus |
| **Event** | Aktives Event, Bildzahl, neues Event anlegen |
| **Galerie** | Alle Veranstaltungen durchsehen, Bilder auswählen, herunterladen, löschen; Bilder neu berechnen (Abschnitt 7) |
| **Netzwerk** | Access-Point ein/aus und automatisch, IP-Adresse, Galerie-URL (Abschnitt 7) |
| **Export** | Aktives Event auf USB-Stick kopieren (Abschnitt 7) |
| **System** | Betriebsart (Fotobox / Druckermodus), Fotobox neu starten, Herunterfahren |

**„Drucker fortsetzen"** ist die Handbremse für das häufigste Problem (Papier oder
Kassette leer). Meist braucht man ihn nicht: nach dem Nachlegen gibt die Box die
Warteschlange nach rund 20 Sekunden von selbst wieder frei.

**Eingeben ohne Tastatur:** Tippt man am Touchscreen ein Text- oder Zahlenfeld an, fährt
unten eine Tastatur aus — mit Umlauten, Umschalttaste, Leertaste, Rückschritt und
**„Fertig"**. Zahlenfelder bekommen nur einen Ziffernblock. Am PC mit echter Tastatur
erscheint sie nicht.

### Werden Einstellungen gespeichert?

Ja. Änderungen im Admin werden dauerhaft gespeichert und **überstehen einen Neustart**:
Einstellungen (Countdown, Timeouts, Limits, Hintergrundauswahl), die **Kamera-/Vorschau-
Auswahl**, die **Ausrichtung**, angelegte **Events** und hochgeladene **Rahmen**.

Zwei Ausnahmen — **bewusst nicht dauerhaft**:

- Der **Access-Point** ist nach einem Neustart wieder **aus** (Sicherheitsnetz, damit die
  Box immer ins normale Netz zurückkehrt). Nach einem Neustart bei Bedarf erneut
  einschalten.
  **Ausnahme:** Findet die Box zwei Minuten lang gar kein Netzwerk — der Normalfall an
  einer fremden Location —, schaltet sie den Access-Point von selbst ein. Das gilt
  nur, wenn seit dem Einschalten **noch nie** ein Netz da war. Bricht eine
  bestehende Verbindung ab, wartet sie stattdessen: das ist meist Roaming zwischen
  mehreren Zugangspunkten, und der Access-Point würde `wlan0` genau dann wegnehmen,
  wenn die Box sich gerade wieder verbinden will. Sie schaltet ihn
  nie von selbst wieder aus: im AP-Betrieb sieht sie das Heimnetz gar nicht mehr, und ein
  Zurückschalten mitten in der Feier würde alle Gäste trennen. Der Schalter dafür steht
  im Admin unter *Netzwerk*.
- Die **Druckzähler** überstehen Neustarts. „Gedruckt (Event)" zählt die fertigen Drucke
  des laufenden Events, „Gedruckt (gesamt)" läuft bis zum nächsten Zurücksetzen weiter.
  Eine Restanzeige des Bandvorrats gibt es nicht — der Drucker meldet den Bandstand nicht.

---

## 5. Während der Feier — wiederkehrende Handgriffe

### Papier oder Farbkassette wechseln
Neues Papier oder neue Kassette einlegen — **mehr ist normalerweise nicht nötig**. Die Box
gibt die Warteschlange nach etwa 20 Sekunden von selbst wieder frei und druckt weiter.
(CUPS lässt eine gestoppte Warteschlange sonst stehen, bis jemand sie von Hand freigibt;
deshalb versucht die Box es in kurzen Abständen selbst.)

Bleibt es doch einmal stehen, hilft **Drucker → „Drucker fortsetzen"** im Admin. Die
Druckzähler hängen nicht am Papiervorrat.

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
3. Die Galerie **öffnet sich von selbst** — das Handy meldet „Anmeldung erforderlich"
   und zeigt die Fotos. Passiert das nicht (manche Handys unterdrücken es), im Browser
   irgendeine Adresse eingeben, egal welche: alles landet in der Galerie. Notfalls
   direkt `http://192.168.4.1/gallery`.
   Dort: alle Fotos ansehen, zwischen **„Mit Hintergrund"** und **„Original"** umschalten,
   **„Alle Fotos herunterladen (ZIP)"**.
4. Danach den Access-Point wieder ausschalten (oder neu starten).

**Nur einzelne Bilder:** **„Auswählen"** oben schaltet um — ein Tipp auf eine Kachel wählt
sie aus (blauer Rahmen mit Haken) statt sie zu öffnen. Darunter steht, wie viele Bilder
gewählt sind und wie groß das Archiv wird: **„Auswahl herunterladen (ZIP)"**.

**Einzelne Bilder ansehen:** Tippen öffnet das Bild groß. Weiter geht es durch Wischen,
mit den Pfeilen links und rechts oder den Pfeiltasten; der runde Knopf unten rechts
**druckt das Bild noch einmal** — und zwar in der Fassung, die gerade zu sehen ist.

### Alle Veranstaltungen verwalten (Admin)

Admin → **Galerie** → **„Hauptgalerie öffnen"**. Oben lässt sich zwischen **allen**
Veranstaltungen umschalten, nicht nur der aktuellen. Der Auswahlmodus bietet hier
zusätzlich **„Auswahl löschen"**.

Löschen und Platz schaffen sind zwei Schritte:

1. **Löschen** nimmt die Bilder sofort aus Galerie, Zählern und Archiven — die Dateien
   bleiben aber auf der Karte.
2. Die Admin-Kachel zeigt, wie viel diese Dateien noch belegen, und bietet
   **„Endgültig entfernen"**. Das gibt den Platz frei und ist **nicht umkehrbar**.

### Bilder neu berechnen

Die bearbeiteten Fassungen sind nur so gut wie die Pipeline, die sie erzeugt hat. Wird
etwas verbessert — höhere Auflösung, EXIF-Daten, Zeitstempel —, gilt das zunächst nur für
neue Fotos. Admin → **Galerie** → Veranstaltung wählen → **„Bilder neu berechnen"** erzeugt
sie aus den unangetasteten Originalen noch einmal. Läuft im Hintergrund mit Fortschritts-
anzeige; bei 250 Bildern etwa 20 Minuten. Die Originale werden dabei nie verändert.

### Die Box als Netzwerkdrucker

Im Heimnetz meldet sich die Box als **„Fotodrucker Fotobox"**. iPhone, iPad und Android
finden sie von selbst (AirPrint bzw. Mopria) — nichts einzurichten. Am PC den Drucker
**treiberlos** einbinden, sonst kommen Ausdrücke mit Rand und in geringerer Auflösung
heraus (siehe `docs/installation.md`). Gäste im Fotobox-WLAN können **nicht** drucken;
das ist Absicht.

### Fotos auf USB-Stick sichern
USB-Stick (FAT32/exFAT) einstecken → Admin → **Export** → **„Auf USB-Stick kopieren"**.
Der Fortschritt wird angezeigt; kopiert wird das **komplette aktive Event**.

### Betriebsart wechseln

Die Box kann statt als Fotobox auch im **Druckermodus** laufen und dann nur noch
als Netzwerkdrucker im Heimnetz dienen. Chromium und das Live-Bild starten gar
nicht erst; auf dem Bildschirm steht dann nur noch eine feste Seite:

> **Druckermodus** — Diese Box arbeitet gerade als Netzwerkdrucker.
> Zurück zur Fotobox: Kamera anstecken oder `http://fotobox.local/admin`
Sinnvoll, wenn Bildschirm und Webcam ohnehin abgesteckt sind und nur der Drucker
im Netz bereitstehen soll.

Admin → **System** → **Betriebsart** umstellen. Die Box startet dazu neu; die
Auswahl liegt auf der Datenpartition und übersteht den schreibgeschützten Root.

Das ist bewusst eine **Auswahl und keine automatische Erkennung**. Beim Booten
steht nicht verlässlich fest, welche USB-Geräte schon angemeldet sind — eine
Webcam, die drei Sekunden später kommt, würde sonst darüber entscheiden, ob auf
der Hochzeit eine Fotobox hochfährt. Der Fehler wäre lautlos und vollständig.

#### Zurück in den Fotobox-Modus

Im Druckermodus läuft **keine Fotobox-Oberfläche** — auf der Box selbst kommt man
nicht mehr in den Admin. Der Rückweg führt über das Netz;
das Backend läuft ja weiter:

1. **Von einem anderen Gerät im Netz:** `http://fotobox.local/admin` (oder die
   IP-Adresse der Box). Dort *System → Betriebsart → Fotobox*. Diese Adresse steht
   auch in der Rückfrage, wenn du auf Druckermodus umschaltest — sie ist der Grund,
   warum sie dort steht.
2. **Ohne Netzwerk:** Die Box macht nach zwei Minuten von selbst ihren
   Access-Point auf. Handy mit dem WLAN „Fotobox" verbinden, dann
   `http://192.168.4.1/admin`.
3. **Wenn gar nichts geht:** SD-Karte in einen anderen Rechner, auf der
   Datenpartition die Datei `mode` öffnen und `fotobox` hineinschreiben. Die Karte
   zurück in die Box, fertig.

**Am bequemsten aber:** einfach die Kamera anstecken. Erkennt die Box im
Druckermodus eine Kamera, wird sie von selbst wieder zur Fotobox — ohne Neustart,
der Kiosk startet innerhalb weniger Sekunden (gemessen: unter fünf).

Damit das den Wechsel *in* den Druckermodus nicht sofort rückgängig macht,
wird der Auslöser erst scharf, **nachdem einmal keine Kamera da war**. Umschalten
mit noch angesteckter Kamera bleibt also bestehen; ausgelöst wird auf das
Anstecken, nicht auf das bloße Vorhandensein. Abschaltbar über
`mode.return_on_camera`.

Die Richtung gilt nur so: Aus einer Fotobox wird nie von selbst ein Druckermodus.
Eine erkannte Kamera ist ein eindeutiges Signal — eine fehlende nicht, denn beim
Booten steht nicht fest, ob ein Gerät weg ist oder sich nur noch nicht angemeldet
hat.

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
| Druck-Knopf fehlt in der Vorschau | Drucker nicht bereit (leer/pausiert). Papier/Kassette prüfen, „Drucker fortsetzen". Drucklimit erreicht. Drucklimit im admin-Bereich erhöhen. Fotos sind gespeichert. |
| Drucker stoppt mitten im Abend | Papier oder Farbband leer → nachlegen. Die Box läuft nach ~20 s von selbst weiter; falls nicht, „Drucker fortsetzen". |
| Ausdruck hat einen weißen Rand | Randlos-Einstellung; im Normalbetrieb bereits korrekt. Falls nicht, Support/Technik. |
| Bildschirm bleibt schwarz | Monitor/Strom prüfen. Reagiert nichts, Box neu starten (Strom nur als letzte Option trennen). |
| „Der Speicher ist voll" | Alte Events per USB sichern und Platz schaffen. |
| Gäste finden das WLAN nicht | Access-Point im Admin eingeschaltet? WLAN heißt „Fotobox". |
| Live-Bild bleibt schwarz, Webcam „hängt" | Meist die USB-Strecke, nicht die Software. Im Log steht `uvcvideo ... -71` (Protokollfehler beim Abfragen der Regler) gefolgt von `USB disconnect` — die Kamera stirbt dann schon eine Sekunde nach dem Anmelden, bevor ein Bild fließt. Zum Eingrenzen die Webcam **direkt an den Pi** stecken, also ohne den externen Hub. Laufen Touchscreen und Drucker am selben Hub störungsfrei, liegt es eher an Kamera oder Kabel. (Der interne VIA-Hub des Pi 4 ist immer im Spiel — der Root-Hub hat nur einen Port. Das ist normal.) |
| Galerie lädt quälend langsam | Funkstrecke prüfen: `nmcli -f IN-USE,SSID,CHAN,SIGNAL dev wifi list`. Hängt die Box im 5-GHz-Band derselben SSID, kann der Durchsatz zusammenbrechen — siehe `docs/installation.md`, Abschnitt 9. |
| Bildschirm bleibt dunkel, obwohl die Box läuft | Steht dort „Druckermodus", ist das kein Fehler — Kamera anstecken oder im Admin umstellen (Abschnitt 7). |
| Bilder mit Rahmen sind kleiner als die Originale | `pipeline.processed_scale: auto` setzen und die Veranstaltung neu berechnen lassen (Admin → Galerie). |

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
| Kontingent pro Event | 500 (im Admin reduzierbar; eine Kassette reicht für 108 Blatt) |
| WLAN-Name (Access-Point) | Fotobox |
| Galerie-Adresse (im AP) | http://192.168.4.1/gallery |
| Admin-PIN | 2606 |
| Bildschirmschoner | ein, nach 5 min |
| Auflösung der Download-Fassung | `auto` (Rahmen wächst auf Originalgröße) |
| Access-Point automatisch | ein, nach 2 min ohne Netzwerk |
| Name im Netzwerk (Drucker) | Fotodrucker Fotobox |
| Betriebsart | Fotobox (umschaltbar auf Druckermodus) |
| Zurück aus dem Druckermodus | Kamera anstecken — oder im Admin |
| Vorschau im Leerlauf | rechnet nach 5 s Ruhe nicht mehr mit |

Diese Werte lassen sich im Admin (Einstellungen / Netzwerk) jederzeit ändern.
