# Offene Punkte zur IoT-Landschaft

Diese Liste basiert auf der aktuellen Dokumentation und den Live-Findings vom 2026-06-15. Ziel ist eine vollstaendige Betriebsdokumentation der TinyHouse-IoT-Landschaft. Bitte die Punkte nach Moeglichkeit beantworten, ergaenzen oder korrigieren.

## 1. Router und DNAT

1. Welches Router-Modell ist im TinyHouse verbaut, inklusive Hersteller, Modellnummer, Seriennummer, Firmware-Version und Management-URL?
> 
2. Wie erfolgt der administrative Router-Zugriff: Web-UI, SSH, VPN, lokaler Port, nur aus dem privaten Netz oder auch ueber die Uni-Seite?
>
3. Wer besitzt den Router-Admin-Zugang und wo sind die Zugangsdaten sicher abgelegt?
>
4. Wie lautet die vollstaendige WAN-Konfiguration des Routers: IP, Subnetzmaske, Gateway, DNS, VLAN, statisch oder DHCP?
>
5. Wie lautet die vollstaendige LAN-Konfiguration: Router-IP, Subnetz, DHCP-Bereich, statische Leases, DNS, NTP und lokale Domain?
>
6. Gibt es auf dem Router DHCP-Reservierungen fuer Management-PC, Scale, Raspberry Pis, AI Pis, Jetsons, Kameras und Jump Host?
>
7. Bitte die komplette DNAT-/Port-Forwarding-Tabelle liefern: externer Port, Protokoll, Ziel-IP, Ziel-Port, Geraetename, Zweck, Status, Verantwortlicher.
>
8. Sind die dokumentierten Ports `4021` bis `4027`, `4031`, `4032`, `4041`, `4042` und `4050` exakt die aktuelle Router-Konfiguration?
>
9. Welche DNAT-Regeln sind geplant, aber noch nicht aktiv?
>
10. Welche DNAT-Regeln sind historisch/alt und koennen geloescht werden?
>
11. Gibt es Source-IP-Beschraenkungen, Firewall-Regeln oder Rate-Limits fuer DNAT-Zugriffe?
>
12. Welche Router-Firewall-Regeln gelten zwischen WAN, LAN, Management-PC, Kameras und Sensorgeraeten?
>
13. Gibt es Port-Forwardings fuer MQTT, Cockpit, EMQX Dashboard, HTTP/HTTPS, RTSP/MJPEG oder nur fuer SSH?
>
14. Gibt es ein Backup der Router-Konfiguration und wie kann sie wiederhergestellt werden?
>

## 2. Switch, Uni-Netz und physische Verkabelung

1. Welches Switch-Modell ist `SW1-TH`, inklusive Hersteller, Firmware, Management-Zugang und Seriennummer?
>
2. Ist die Switch-Adresse `132.180.196.166` weiterhin korrekt?
>
3. Welche Switch-Ports sind aktuell belegt und welches Kabel/Geraet haengt an welchem Port?
>
4. Stimmen die dokumentierten Public-Ports `1/1/11`, `1/1/13`, `1/1/15`, `1/1/16` und Private-Ports `1/1/1` bis `1/1/10`, `1/1/12`, `1/1/14` noch?
>
5. Gibt es VLANs, Trunks, Access-Ports, Port-Isolation, STP oder besondere Security-Settings?
>
6. Welche oeffentlichen Uni-IP-Adressen sind offiziell fuer TinyHouse reserviert: `132.180.196.164`, `.165`, `.166`, `.167` und ggf. weitere?
>
7. Wer ist fuer Aenderungen an Uni-Netz, Switch-Port, Firewall oder IP-Zuweisungen zustaendig?
>
8. Gibt es eine aktuelle Kabel- und Portbeschriftung im TinyHouse?
>
9. Gibt es PoE, separate Netzteile, USV oder andere Stromversorgungsdetails, die dokumentiert werden muessen?
>

## 3. Vollstaendiges Geraeteinventar

1. Bitte eine vollstaendige Inventarliste aller IoT-/Netzwerkgeraete liefern: Name, Rolle, IP, MAC, Seriennummer, Standort, Stromversorgung, Betriebssystem/Firmware, Besitzer.
>
2. Welche Geraete existieren aktuell im Bereich `192.168.1.0/24` ausser den dokumentierten Adressen?
>
3. Was sind die Geraete hinter den in der Neighbor Table gesehenen Adressen `192.168.1.101`, `.102`, `.103`, `.105`, `.107`, `.108` und `.113`?
>
4. Ist `192.168.1.100` noch die private Adresse des Management-PCs?
>
5. Ist `192.168.1.106` noch die Scale und ist sie aktuell erreichbar?
>
6. Welche Geraete sind `EMQX001` bis `EMQX007` genau und welche davon sollen produktiv sein?
>
7. Gibt es eine Namenskonvention fuer Hostnames, Labels, Inventarnamen und MQTT-Device-IDs?
>
8. Gibt es Geraete, die in alten PDFs oder E-Mails stehen, aber nicht mehr vorhanden sind?
>

## 5. Raspberry Pis, AI Pis und Jetsons

4. Sind die AI Pis `192.168.1.131` und `192.168.1.132` tatsaechlich vorhanden, und warum antworten `4031` und `4032` nicht?
>
5. Sind die Jetsons `192.168.1.141` und `192.168.1.142` korrekt dokumentiert, und welche Dienste laufen dort?
>
6. Welche OS-Version, Hardware-Revision, SD-Karte/Storage, Netzteil und Rolle hat jedes Pi-/Jetson-Geraet?
>
7. Warum unterscheiden sich die AlmaLinux-Versionen auf den Pis und soll das vereinheitlicht werden?
>
8. Welche Services sind auf den Pis beabsichtigt: Mosquitto, EMQX, Cockpit, Docker, MySQL, HTTP/HTTPS, XRDP?
>

## 6. MQTT- und Broker-Architektur

1. Was ist die Zielarchitektur: Mosquitto auf jedem Pi, ein zentraler EMQX-Broker, EMQX-Cluster oder Mischbetrieb?
>
3. Warum ist EMQX auf mehreren Pis installiert, aber nur auf `EMQX003` als Listener sichtbar?
4. Soll Mosquitto auf `EMQX001`, `EMQX004`, `EMQX005`, `EMQX006` bleiben oder durch EMQX ersetzt werden?
5. Welche MQTT-Ports sollen intern und extern erreichbar sein: `1883`, `8883`, `8083`, `8084`, `18083`?
6. Gibt es TLS-Zertifikate, Benutzer, ACLs, Client-Zertifikate oder bleibt MQTT anonym?
7. Welche Topic-Konvention ist verbindlich?
8. Welches Payload-Schema ist verbindlich: Felder, Einheiten, Zeitstempel, Sensor-ID, Device-ID, Qualitaetsstatus, Kalibrierung?
9. Welche QoS-Stufen, Retained Messages, Last-Will-Messages und Health Topics sollen genutzt werden?
10. Gibt es MQTT-Bridges zu externen Brokern, Kafka, Datenbanken oder Cloud-Diensten?
12. Wer darf das EMQX Dashboard verwenden und wie wird der Zugriff abgesichert?

## 7. Sensoren, Arduino-/ESP-Firmware und Datenfluss

1. Wie viele Arduino-/Nano-/ESP-Boards sind verbaut oder geplant?
2. Welches Board haengt an welchem Pi und ueber welche Schnittstelle: RX/TX, USB-Serial, GPIO, WLAN?
3. Welche Sensoren sind an welchen Pins angeschlossen: analog, digital, I2C, SPI, UART?
4. Gibt es einen Schaltplan oder Verdrahtungsplan fuer jedes Sensor-Setup?
5. Welche Firmware-Version laeuft auf den Boards und wo liegt der Source Code?
6. Wie sieht das serielle Protokoll vom Arduino zum Pi genau aus?
7. Welche Sampling-Raten, Debounce-Zeiten, Grenzwerte und Einheiten gelten pro Sensor?
8. Wer erzeugt die Zeitstempel: Sensor-Board, Pi oder Broker?
9. Wie werden Sensor-IDs, Geraete-IDs und physische Positionen vergeben?
10. Welche Kalibrierungen sind notwendig und wo werden Offset/Tare/Faktoren dokumentiert?
11. Ist die Pi-Receiver-Software fuer Serial-to-MQTT bereits spezifiziert, und wer stellt sie fertig?

## 8. Scale, Kameras und Spezialgeraete

1. Ist die Netzwerk-Scale unter `192.168.1.106` erreichbar und welches Protokoll/API nutzt sie?
2. Sendet die Scale selbst MQTT-Daten oder wird sie von einem Pi/ESP ausgelesen?
3. Stimmt der im Dashboard konfigurierte externe Broker `broker.emqx.io` mit Topic `tinyhouse/scale/#`?
4. Welche Kalibrierung/Tare-Prozedur gilt fuer die Scale, insbesondere wegen des dokumentierten leeren Werts von ca. `130 g`?

## 9. Ansible, Dashboard und Source of Truth

4. Wie werden neue Geraete aufgenommen: IP-Reservierung, DNS/Hostname, DNAT?


