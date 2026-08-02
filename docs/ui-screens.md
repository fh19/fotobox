# UI-Screens

Alle Texte sind verbindlich. Nicht umformulieren, nicht „verbessern", keine Varianten
erfinden. Neue Texte gehören zuerst in dieses Dokument.

## Gestaltungsrahmen

- Zielgruppe: Gäste zwischen 8 und 88, angetrunken, im Halbdunkel, ohne Einweisung
- Nur ein Interaktionselement pro Screen ist wirklich wichtig; alles andere tritt zurück
- Touch-Ziele mindestens 120 × 120 px
- Schriftgrößen: Überschrift 64 px, Fließtext 32 px, Buttons 40 px
- Kein Text, der gelesen werden *muss* — jeder Screen ist auch ohne Lesen bedienbar
- Keine Animation länger als 300 ms außer Countdown und Verarbeitungsanzeige
- Dunkles Layout (Hintergrund `#111`), damit der Bildschirm nachts nicht blendet
- Das Live-Bild ist per CSS gespiegelt (`transform: scaleX(-1)`), das Ergebnisfoto nicht

## Globales Verhalten

- Kein Scrollen, kein Zoom, kein Kontextmenü, keine Textselektion, kein Cursor
- Jede Berührung außerhalb eines Buttons wird verschluckt, nicht durchgereicht
- Bei WebSocket-Abbruch: Overlay „Verbindung wird wiederhergestellt …", Live-Bild bleibt
  sichtbar, keine Fehlermeldung — der Reconnect dauert typischerweise unter 2 s

---

## `IDLE`

Live-Bild formatfüllend. Darüber mittig:

> **Bereit für dein Foto?**
> Tippe auf den Bildschirm

Der gesamte Bildschirm ist die Schaltfläche. Der Hinweistext pulsiert dezent
(Deckkraft 0.6 ↔ 1.0, 2 s Zyklus), damit erkennbar ist, dass die Box lebt.

Ist Drucken nicht verfügbar, erscheint unten klein und unaufdringlich:

> Drucken ist gerade nicht möglich — Fotos werden gespeichert

Ist die Kamera nicht verfügbar:

> **Kleine Pause**
> Die Fotobox ist gleich wieder da

Kein Start möglich, der Bildschirm reagiert nicht auf Berührung.

---

## `BACKGROUND_SELECT`

Live-Bild verkleinert oben, darunter eine horizontal scrollbare Kachelreihe der
Hintergründe. Überschrift:

> **Wähle deinen Hintergrund**

Erste Kachel immer:

> Ohne Hintergrund

Jede Kachel zeigt das Vorschaubild und den Namen. Antippen wählt aus und startet sofort
den Countdown — kein zusätzlicher Bestätigungsschritt.

Unten links, klein:

> Abbrechen

Timeout `timeouts.background_select_seconds` (Standard 45 s) → `IDLE`.

---

## `COUNTDOWN`

Live-Bild formatfüllend, alle Bedienelemente verschwunden. Zentral die Ziffer, sehr groß
(40 % der Bildschirmhöhe), bei jedem Wechsel kurz skalierend.

Bei `1` → Text statt Ziffer:

> **Lächeln!**

Zusätzlich zur Zahl ein umlaufender Fortschrittsring, damit auch aus zwei Metern
Entfernung ohne Lesen erkennbar ist, wie viel Zeit bleibt.

Optional (`countdown.sound_enabled`): kurzer Ton pro Sekunde, anderer Ton bei Auslösung.
Standard: aus. Auf einer Hochzeit mit Band ist das ohnehin unhörbar, im Sektempfang
dagegen störend.

Unten rechts klein: `Abbrechen`

---

## `CAPTURE`

Keine eigene Darstellung. Ist `ui.flash_enabled` gesetzt, wird der Bildschirm **weiß**
und bleibt es während der Auslösung — als **Aufhellung/Blitzersatz**. Er leuchtet
`ui.flash_duration_ms` **vor** der Auslösung auf (das Backend wartet diese Zeit ab),
damit das Motiv bei der Belichtung beleuchtet ist. Danach läuft `PROCESSING` an.

---

## `PROCESSING`

> **Einen Moment …**
> Dein Foto wird fertig gemacht

Unbestimmter Fortschrittsindikator, kein Prozentwert — geschätzte Prozentwerte, die
stehenbleiben, sind schlimmer als gar keine.

Dauert es länger als `timeouts.processing_warn_seconds` (Standard 8 s), ergänzt sich:

> Gleich ist es soweit

---

## `PREVIEW`

Das fertige Foto formatfüllend. Darunter zwei Schaltflächen:

| Links | Rechts |
|---|---|
| **Drucken** | **Fertig** |

Nach erfolgreichem Drucken wechselt der linke Button für 3 s zu:

> Wird gedruckt …

und ist danach deaktiviert (`printing.max_per_photo` erreicht) oder wieder verfügbar.

Ist Drucken nicht möglich, wird der linke Button nicht ausgegraut, sondern **entfernt** —
ein ausgegrauter Button provoziert wiederholtes Tippen. Stattdessen zentriert:

> **Fertig**

Rechts oben ein Zähler des Timeouts als dünner Ring. Timeout
`timeouts.preview_seconds` (Standard 30 s) → `IDLE`. Jede Berührung des Bildschirms setzt
den Timeout zurück.

---

## `PRINTING`

Kein eigener Vollbild-Screen. Der Zustand ist nur ein kurzer Übergang und wird als
Zustandsänderung des Druck-Buttons in `PREVIEW` dargestellt.

---

## `ERROR`

> **Da ist etwas schiefgelaufen**
> {message aus der Fehlermeldung}
> Versuch es gleich noch einmal

Nach `timeouts.error_seconds` (Standard 6 s) automatisch nach `IDLE`. Keine Schaltfläche —
Gäste sollen hier nichts entscheiden müssen.

Fehlermeldungen (`message`), Auswahl:

| `code` | `message` |
|---|---|
| `camera_timeout` | Die Kamera hat nicht reagiert |
| `camera_disconnected` | Die Kamera ist nicht verbunden |
| `capture_failed` | Das Foto konnte nicht aufgenommen werden |
| `pipeline_failed` | Das Foto konnte nicht bearbeitet werden — es ist aber gespeichert |
| `printer_unavailable` | Der Drucker ist gerade nicht bereit |
| `storage_full` | Der Speicher ist voll |

Keine technischen Details, keine Codes, keine Stacktraces auf dem Gästebildschirm.
Das gehört ins Log und in den Admin-Bereich.

---

## Admin-Bereich

**Zugang:** 5 Sekunden Berührung in der oberen linken Ecke (Bereich 100 × 100 px, unsichtbar)
→ PIN-Feld → Admin. Kein sichtbarer Hinweis, keine Schaltfläche.

Unter dem PIN-Feld steht ein numerisches Tastenfeld, weil das Gerät keine Tastatur hat:
Ziffern 1–9, darunter `✕` (Eingabe leeren), `0` und `←` (letzte Ziffer zurück). Bestätigt
wird mit `Anmelden`. Die Tasten tragen Symbole statt Wörtern. Nach einer fehlgeschlagenen
Anmeldung wird das Feld geleert — ohne Tastatur lässt sich eine halb eingegebene PIN nicht
bequem korrigieren.

Der Admin-Bereich ist bewusst nüchtern und darf hässlich sein. Er wird von genau einer
Person bedient, die weiß, was sie tut.

Kacheln:

1. **Status** — Kamera, Drucker, Speicher, CPU-Temperatur, Uptime, letzte 20 Log-Einträge

   Darstellung als Beschriftung/Wert-Liste, nicht als JSON. Werte, die das Backend
   nicht ermitteln kann, erscheinen als `unbekannt`. Zeilen mit Störung (Kamera oder
   Drucker nicht verfügbar, Drucker angehalten, Speicher knapp oder voll) werden rot
   hervorgehoben. Die Druckerzustände heißen deutsch: `bereit`, `druckt`, `Fehler`,
   `nicht erreichbar`, bei pausierter Warteschlange `angehalten`.

2. **Drucker** — großer Button `Drucker fortsetzen` (nach Papier-/Bandwechsel),
   `Warteschlange leeren`, `Testdruck`, `Druckzähler zurücksetzen`

   Kann nicht gedruckt werden, steht der Grund orange über dem Status — sonst
   bleibt nur Raten. Wortlaut: `Kein Papier`, `Farbband verbraucht`, `Papierstau`,
   `Klappe offen`, `Drucker nicht erreichbar`, `Warteschlange angehalten`.

   Nach einem Papierwechsel gibt die Box die angehaltene Queue von selbst wieder
   frei (`printer.auto_resume_seconds`, Standard 20 s) — CUPS tut das nicht. Der
   Button bleibt für den ungeduldigen Fall.

2b. **Kamera** — Auswahl von `Hauptkamera`, `Vorschau-Backend` und `Vorschaugerät`,
   darüber das Live-Bild der Vorschaukamera zur Ausrichtungskontrolle. Buttons:
   `Kamera übernehmen`, `Neu suchen`, `Kamera zurücksetzen`, `Probefoto`,
   `Ausrichtung kalibrieren`.

   `Neu suchen` findet eine Kamera, die erst nach dem Start angeschlossen oder
   eingeschaltet wurde — ohne Neustart der Box. `Kamera zurücksetzen` fragt vorher
   nach (`Kamera zurücksetzen? Sie wird kurz vom USB getrennt.`) und ist die Antwort
   auf eine Kamera, die am USB hängt, sich aber nicht mehr ansprechen lässt.
   `Probefoto` zeigt das aufgenommene Bild mit Modell und Auflösung — daran erkennt
   man sofort, ob wirklich die DSLR ausgelöst hat oder die Ersatzkamera.

   Löst die Vorschaukamera als Ersatz aus, steht ganz oben in der Kachel in Orange:
   `Ersatzkamera aktiv — Fotos kommen von der Vorschaukamera`.
3. **Event** — aktives Event, Bildzahl, `Neues Event anlegen`
4. **Hintergründe & Rahmen** — Liste der hochgeladenen Einträge (Name, Modus) mit
   `Löschen`; Upload per `Name`, `Modus` (Rahmen/Overlay/Greenscreen/KI) und Datei.
   `frame` rahmt das Foto im transparenten Fenster des PNG, `overlay` legt das PNG
   über das Foto
5. **Einstellungen** — Countdown-Dauer, `Auslöser-Vorlauf (ms)`, Timeouts, Druck-Limits,
   Hintergrundauswahl ein/aus

   Der Vorlauf löst so viel früher aus, als der Countdown bei „0" ankommt, und gleicht
   damit Blitzdauer und Kameralatenz aus. Die letzte Sekunde des Countdowns bleibt
   immer stehen — ein zu großer Wert darf den Gästen nicht das Zählen wegnehmen.

   `Aufhellblitz (weißer Bildschirm)` und `Blitzdauer (ms)` steuern das Weißleuchten
   während der Auslösung (`ui.flash_enabled`, `ui.flash_duration_ms`). Im hellen
   Sektempfang stört es nur, im abendlichen Saal ist es das einzige Licht. Die
   Änderung greift, sobald der Kiosk-Screen wieder geladen wird.
6. **Kalibrierung** — Live-Bild mit verschiebbarem Rahmen für den DSLR-Ausschnitt
7. **Netzwerk** — Access-Point ein/aus, aktuelle IP-Adresse, Galerie-URL groß dargestellt
8. **Export** — `Auf USB-Stick kopieren` mit Fortschrittsanzeige
9. **System** — `Fotobox neu starten`, `Herunterfahren`

Der Button `Drucker fortsetzen` ist der wichtigste im ganzen Admin-Bereich und gehört
ganz oben, groß. Er ist die Antwort auf das häufigste Problem des Abends.

---

## Galerie (nach der Veranstaltung)

Eigene Route `/gallery`, normale Webseite, kein Kiosk. Responsiv, wird meist vom Handy
oder Laptop aufgerufen.

- Kachelraster der Bilder, Klick öffnet die große Ansicht
- Umschalter `Mit Hintergrund` / `Original`
- Oben: `Alle Fotos herunterladen (ZIP)` mit Angabe der Dateigröße
- Kein Löschen, kein Bearbeiten — die Galerie ist read-only
