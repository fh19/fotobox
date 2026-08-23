# Weitere Ideen

## Fotobox-Nutzung
- wenn die Box für zB 5min nicht benutzt wurde, sollen die bisherigen Bilder in zufälliger Reihenfolge auf dem Schirm angezeigt werden. 
- sobald man den Schirm antippt, kommt der Screen und erst jetzt kann man Fotos per Tippen auslösen
- die Fotolampe automatisch per Shelly schalten
 - wenn Bildschirmschoner (Show mit den bisherigen Bildern) läuft oder im Galleriemodus => Lampe aus
 - nur im Fotomodus => Lampe an


## Neuer Use-Case: Nutzen der Box als Fotodrucker
Der Fotodrucker CP1500 verhält sich am WLAN etwas instabil, daher soll die Box auch als Druckserver im Netz zu dienen - sie hat immerhin alles notwendige an Bord

### Allgemeine Anforderungen
- Box soll den Modus (Fotobox oder Druckservice) automatisch beim Booten erkennen
 - Box läuft als Fotobox, wenn Bildschirm und Webcam verfügbar sind
 - Box läuft im Druckservice-Modus, wenn Bildschirm und Webcam beim Booten nicht erkannt werden
- Hintergrund: der permanente Stromverbrauch soll möglichst gering sein, daher kein Bildschirm und Webcam
- erfordert, dass die USB-Verbindung zum Bildschirm und zur Webcam gekappt werden; ausserdem muss der Drucker an den Shelly angeschlossen werden

### Anforderungen Druckservice-Modus
- ohne Monitor und ohne Eingabegerät
- Kernfunktion: Druckservice für alle Rechner im Netz bereitstellen
- Rechner sollen per Netzwerk ihre Ausdrucke an die Box schicken können und zwar im direkten Modus (als JPEG oder anderes Bildformat)
- die Box konvertiert das Format -falls nötig- und sendet es an den Drucker
- die Ausdrucke sollen immer die maximale Größe nutzen - oder ist das nicht sinnvoll?
- die Box liefert passende Fehlermeldungen, falls zB der Drucker aus ist, kein Papier oder Tinte hat
- die Box liefert eine Erfolgsmeldung
- die Box soll im Netzwerk automatisch als Drucker erkannt werden und Airprint ermöglichen
- die Box erkennt im laufenden Betrieb automatisch, wenn der Drucker eingeschaltet wird
- die Box puffert Drucke und arbeitet sie nacheinander ab
- wenn der Drucker ausfällt, werden die Drucke trotzdem gepuffert und gedruckt sobald der Drucker wieder geht
- die Druckerwarteschlange sollte zurückgemeldet werden (falls möglich) und kann dann vom Client ggf. gelöscht werden
- beim Neustart wird die Druckerwarteschlange immer gelöscht
- den Fotodrucker per Shelly -der sonst auch für die Lampe verwendet wird- automatisch ausschalten, zB 2h nach dem letzten Druck

### Offen/Fragen
- gibt es eine andere/bessere/robustere Möglichkeit zwischen den beiden Modi hin- und herzuschalten?
- kann man den Drucker ferngesteuert einschalten bzw. hat er einen Automodus, in dem er beim Stromeinschalten automatisch angeht?
- gibt es Ideen, die Einschalttaste am Drucker zB per Steppermotor oder Druckmagent zu bedienen?
