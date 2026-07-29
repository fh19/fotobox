# Hardware-Uhr (RTC) einbinden

Die Fotobox läuft offline, also ohne NTP. Ohne batteriegepufferte Echtzeituhr wäre
die Systemzeit nach jedem Stromausfall falsch — und damit die Zeitstempel in der
Datenbank und die Verzeichnisnamen. Die RTC hält die Uhrzeit auch stromlos.

## Das Modul

- Aufdruck/Verkaufstitel oft **„DS1302"**, tatsächlich verbaut ist ein **DS1307**.
- **DS1307 = I²C** (nicht der 3-Draht-DS1302!), sitzt auf Adresse **`0x68`**.
- Prüfen: `sudo i2cdetect -y 1` → `68` erscheint (nach dem Einbau `UU`, weil der
  Treiber den Bus belegt).
- Braucht eine **Knopfzelle** (CR2032 bzw. ladbare LIR2032) für den Pufferbetrieb.

## Verdrahtung (I²C)

| Modul | Pi-Header (physisch) | Funktion |
|-------|----------------------|----------|
| VCC   | Pin 1 (3V3)          | Versorgung |
| GND   | Pin 6                | Masse |
| SDA   | Pin 3                | GPIO2 / I²C-SDA |
| SCL   | Pin 5                | GPIO3 / I²C-SCL |

Hinweis: Der DS1307 ist spezifiziert für ~5 V; viele Module laufen am Pi aber
auch an 3V3 zuverlässig genug (so ist es hier angeschlossen und erkannt). Bei
5 V lägen die I²C-Pull-ups auf 5 V an den 3,3-V-GPIOs des Pi an — dann besser
3V3 verwenden oder ein DS3231-Modul (temperaturkompensiert, 3,3-V-tauglich).

## Einbau

`config.txt` und `cmdline.txt` liegen auf der vfat-Boot-Partition, die **nicht**
vom overlayroot (read-only root) überlagert wird. Die Änderung bleibt also ohne
Overlay-Aus/Ein-Zyklus erhalten. `fake-hwclock` ist auf dem Image nicht
installiert, muss also nicht entfernt werden.

```bash
sudo bash deploy/rtc/setup-rtc.sh
```

Das trägt `dtoverlay=i2c-rtc,ds1307` in `/boot/firmware/config.txt` ein und lädt
den Treiber sofort → `/dev/rtc0`.

## Uhr einmalig stellen

Ab Werk ist der Oszillator angehalten (CH-Bit gesetzt). Einmal setzen startet ihn:

```bash
sudo bash deploy/rtc/setup-rtc.sh --set-time "2026-07-29 20:17:00"
```

Alternativ, wenn der Pi gerade Netz mit Zeitserver hatte und die Systemuhr stimmt,
genügt das Zurückschreiben durch systemd/NTP von selbst (11-Minuten-Modus).

## Kontrolle

```bash
timedatectl        # "RTC time:" muss stimmen
sudo dmesg | grep rtc
# -> rtc-ds1307 1-0068: registered as rtc0
# -> rtc-ds1307 1-0068: setting system clock to ... UTC   (Boot liest die RTC)
```

## Verhalten

- **Offline:** Der Kernel stellt die Systemuhr beim Boot aus der RTC. Einzige Quelle.
- **Mit Netz:** `systemd-timesyncd` korrigiert die Systemuhr per NTP, der Kernel
  schreibt sie alle ~11 min automatisch in die RTC zurück. Kein Eingriff nötig.
- **Stromlos:** Die RTC läuft aus der Knopfzelle weiter. Einmal echt kaltstarten
  (Pi ziehen, kurz warten, wieder an) und `timedatectl` prüfen bestätigt die
  Pufferbatterie.
