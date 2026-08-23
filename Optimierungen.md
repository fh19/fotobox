# Optimierungen nach dem ersten produktiven Einsatz
Nach dem ersten Einsatz auf einer Hochzeit mit intensiver Nutzung über 15h sind die folgenden Dinge aufgefallen.


## Erfahrungen 

### Während der Nutzung, Bedienung 
- Box hat sehr gut und stabil funktioniert
- Gäste kamen sehr gut mit der einfachen Bedienung klar
- in der Konfiguration kann man ohne Tastatur nur sehr wenig ändern
- Bilder lassen sich nachträglich nicht mehr ausdrucken

### Meldungen
- Papierende und Tonerende war nur sichtbar, weil keine Ausdrucke mehr kamen. Durch die gute Zugänglichkeit von hinten, konnte am Drucker schnell festgestellt werden, wo das Problem liegt.
- Limit der Ausdrucke (war unbewusst auf 108 parametriert) wurde irgendwann erreicht und die Box hat das Drucken einfach nicht mehr angeboten - ohne Meldung; die "Fehlersuche" war leider zeitintensiv
- die 4s, bis das Foto gemacht wird, war manchmal zu kurz - gerade bei größeren Gruppen

### Hardware
- die Nikon hat sehr gut und zuverlässig funktioniert
 - mit Permanentspannungsversorgung 
 - im Autofokusmodus (fast keine Probleme oder schlecht fokussierte Bilder)
 - Blende 8
- Beleuchtung mit Softbox (50W LED) etwa 70cm oberhalb der Linse gibt ein sehr gutes Licht
- Zugänglichkeit über hintere Tür erleichtert Zugang zum Drucker zB für Tonertausch
- Temperatur der Box war ok (durch zusätzlich 4 Lüftungsgitter)

### Anschauen der Bilder über AP
- Bildübersicht ist gut
- einzelne Bilder ansehen geht auch gut
- umständlich ist der Anschauen mehrerer Bilder nacheinander, weil jedes Bild separat geöffnet und geschlossen werden muss

### Sonstiges
- Bilder haben KEINEN sinnvollen Zeitstempel!
 - Raspi-RTC hat scheinbar nicht funktioniert??
 - oder verlieren die Dateien beim zippen die Zeitinfo?
- Nikon-Originalbilder haben die komplette und korrekte Bildinformation (EXIF), diese geht jedoch beim Zusammenbau der Bilder mit Rahmen verloren
- Bilder mit Hintergrund/Rahmen haben eine sehr geringe Auflösung


## Verbesserungen

### Meldungen
- klare und größere Meldung bei Papier- und Tonerende 
- Meldung, wenn Drucklimit erreicht ist

### Bedieung
- virtuelle Tastatur für Touchbedienung bei Parametern im Konfig-Modus automatisch einblenden

### Anschauen der Bilder
- Automatisches Einschalten des AP, wenn keine Verbindung zum Heimnetzwerk
- beim Anschauen einzelner Bilder Navigationspfeile einblenden oder das swipen ermöglichen
- Anschauen sollte auch am Bildschirm möglich sein 
 - ähnlich wie per Netzwerk
 - Button unten rechts "Gallerie"
- Nachträgliches Ausdrucken bei Ansicht der Bilder sollte möglich sein => Button bei Einzelansicht der Bilder
- Auswahl mehrere Bilder in der Gallerie und dann Download der Auswahl als ZIP
- Anschauen und Löschen aller Veranstaltungsbilder aus dem Konfig-Menü heraus 
 - Button für Hauptgallerie
 - von dort aus in die Veranstaltungen navigieren
 - Bilder auswählen können
 - Download und Löschen anbieten

### Allgemein
- EXIF-Information der Originalbilder beim Zusammenbau mit Rahmen übernehmen
- Die Bilder mit Rahmen sollten in einer besseren Auflösung exportiert werden
 - entweder beim Erzeugen bereits mit höherer Auflösung speichern? 
 - Zum Ausdrucken vorher runterskalieren? Könnte eventuell den Druck verlängern
 - oder beim Runterladen neu erzeugen? => sehr zeitintensiv?
