"""
msda_hub.iot_manager — Main IoT Orchestrator
Manages background threads (maintenance, monitor), signal handling, and CLI.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime

from .config import ConfigManager
from .database import DatabaseManager
from .serial_manager import SerialManager


class IoTManager:
    def __init__(self, config_file='iot_config.ini'):
        self.config = ConfigManager(config_file)
        self.setup_logging()
        self.db = DatabaseManager(self.config)
        self.serial = SerialManager(self.config, self.db)
        self.running = False

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        level = getattr(logging, self.config.get('LOGGING', 'level', 'INFO'), logging.INFO)
        log_file = self.config.get('LOGGING', 'file', 'iot_system.log')
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def signal_handler(self, signum, frame):
        logging.info("Shutdown signal received")
        self.stop()
        sys.exit(0)

    # ── Start / Stop ──────────────────────────────────────────────────

    def start(self) -> bool:
        logging.info("Starting IoT Management System")
        self.db.add_event("SYSTEM", "INFO", "System started")
        self.running = True

        if not self.serial.start():
            logging.error("Failed to start serial communication")
            return False

        import threading
        threading.Thread(target=self.maintenance_loop, daemon=True).start()
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        return True

    def stop(self):
        logging.info("Stopping IoT Management System")
        self.running = False
        self.serial.stop()
        self.db.add_event("SYSTEM", "INFO", "System stopped")
        self.db.close()

    # ── Background Threads ────────────────────────────────────────────

    def maintenance_loop(self):
        last_cleanup = time.time()
        last_backup = time.time()

        while self.running:
            now = time.time()
            if now - last_cleanup > 86400:          # daily cleanup
                logging.info("Running database cleanup")
                self.db.cleanup_old_data()
                last_cleanup = now

            backup_interval = self.config.getint('DATABASE', 'backup_interval_hours', 24) * 3600
            if now - last_backup > backup_interval:  # periodic backup
                logging.info("Running database backup")
                self.db.backup_database()
                last_backup = now

            time.sleep(60)

    def monitor_loop(self):
        while self.running:
            try:
                # Check for stale sensors
                cursor = self.db.conn.cursor()
                cursor.execute('''
                    SELECT sensor_id, last_seen FROM sensors
                    WHERE active = 1 AND last_seen < datetime('now', '-5 minutes')
                ''')
                for sensor_id, last_seen in cursor.fetchall():
                    logging.warning(f"Sensor {sensor_id} hasn't reported since {last_seen}")
                    self.db.add_event("SENSOR", "WARNING", f"Sensor {sensor_id} is stale")

                # Push current sample rate to Arduino
                interval = self.config.getint('MONITORING', 'sensor_read_interval', 2000)
                self.serial.send_command("SET_RATE", str(interval))

            except Exception as e:
                logging.error(f"Monitor error: {e}")

            time.sleep(30)

    # ── Arduino Configuration ─────────────────────────────────────────

    def configure_arduino(self):
        """Send initial configuration to Arduino after connection."""
        interval = self.config.getint('MONITORING', 'sensor_read_interval', 2000)
        self.serial.send_command("SET_RATE", str(interval))

    # ── CLI ───────────────────────────────────────────────────────────

    def run_cli(self):
        print("\n=== IoT Management System CLI ===")
        print("Commands: status, sensors, detect, config, stats, alerts, export, quit")

        while self.running:
            try:
                cmd = input("\n> ").strip().lower()

                if cmd in ("quit", "exit"):
                    break
                elif cmd == "status":
                    self.show_status()
                elif cmd == "sensors":
                    self.show_sensors()
                elif cmd == "detect":
                    self.serial.send_command("INVENTORY")
                    print("Inventory request sent")
                elif cmd == "config":
                    self.show_config()
                elif cmd == "stats":
                    self.show_statistics()
                elif cmd == "alerts":
                    self.show_alerts()
                elif cmd == "export":
                    self.export_data()
                elif cmd.startswith("set "):
                    self.set_config(cmd[4:])
                else:
                    print("Unknown command")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

    def show_status(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensors WHERE active = 1")
        active_sensors = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sensor_data WHERE timestamp > datetime('now', '-1 hour')")
        recent_readings = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0")
        unack_alerts = cursor.fetchone()[0]

        print(f"\nSystem Status:")
        print(f"  Active Sensors:           {active_sensors}")
        print(f"  Recent Readings (1h):     {recent_readings}")
        print(f"  Unacknowledged Alerts:    {unack_alerts}")
        print(f"  Serial Port:              {self.serial.port}")
        print(f"  Last Heartbeat:           {time.time() - self.serial.last_heartbeat:.1f}s ago")

    def show_sensors(self):
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT s.sensor_id, s.sensor_type, s.last_seen,
                   COUNT(d.id) as readings,
                   MAX(d.value1) as last_value
            FROM sensors s
            LEFT JOIN sensor_data d ON s.sensor_id = d.sensor_id
            WHERE s.active = 1
            GROUP BY s.sensor_id
        ''')
        sensors = cursor.fetchall()
        print(f"\nActive Sensors ({len(sensors)}):")
        print(f"{'ID':<15} {'Type':<8} {'Readings':<10} {'Last Value':<12} {'Last Seen'}")
        print("-" * 70)
        for sensor in sensors:
            sensor_id, sensor_type, last_seen, readings, last_value = sensor
            last_value_str = f"{last_value:.2f}" if last_value else "N/A"
            print(f"{sensor_id:<15} {str(sensor_type):<8} {readings:<10} {last_value_str:<12} {last_seen}")

    def show_config(self):
        print("\nCurrent Configuration:")
        for section in self.config.config.sections():
            print(f"\n[{section}]")
            for key, value in self.config.config[section].items():
                print(f"  {key}: {value}")

    def set_config(self, args):
        parts = args.split()
        if len(parts) != 3:
            print("Usage: set <section> <key> <value>")
            return
        section, key, value = parts
        self.config.set(section.upper(), key, value)
        print(f"Set {section}.{key} = {value}")

        if section.upper() == "MONITORING" and key == "sensor_read_interval":
            self.serial.send_command("SET_RATE", value)

    def show_statistics(self):
        cursor = self.db.conn.cursor()
        print("\nSensor Statistics (Last 7 Days):")
        cursor.execute("SELECT DISTINCT sensor_id FROM sensors WHERE active = 1")
        for (sensor_id,) in cursor.fetchall():
            stats = self.db.get_sensor_statistics(sensor_id, 7)
            if stats['count'] and stats['count'] > 0:
                print(f"\n{sensor_id}:")
                print(f"  Readings: {stats['count']}")
                print(f"  Min:      {stats['min']:.2f}")
                print(f"  Max:      {stats['max']:.2f}")
                print(f"  Avg:      {stats['avg']:.2f}")

    def show_alerts(self):
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT id, timestamp, sensor_id, alert_type, value, threshold, message
            FROM alerts
            WHERE acknowledged = 0
            ORDER BY timestamp DESC
            LIMIT 20
        ''')
        alerts = cursor.fetchall()
        print(f"\nUnacknowledged Alerts ({len(alerts)}):")
        for alert in alerts:
            alert_id, timestamp, sensor_id, alert_type, value, threshold, message = alert
            print(f"\n[{alert_id}] {timestamp}")
            print(f"  Sensor:    {sensor_id}")
            print(f"  Type:      {alert_type}")
            print(f"  Value:     {value:.2f} (Threshold: {threshold:.2f})")
            print(f"  {message}")

    def export_data(self):
        filename = f"iot_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT sensor_id, timestamp, value1, value2, value3, unit1, unit2, unit3
            FROM sensor_data
            ORDER BY timestamp DESC
        ''')
        with open(filename, 'w') as f:
            f.write("sensor_id,timestamp,value1,value2,value3,unit1,unit2,unit3\n")
            for row in cursor.fetchall():
                f.write(','.join(str(x) if x is not None else '' for x in row) + '\n')
        print(f"Data exported to {filename}")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='IoT Management System for Raspberry Pi')
    parser.add_argument('--config',   default='iot_config.ini', help='Configuration file path')
    parser.add_argument('--port',     help='Serial port (overrides config)')
    parser.add_argument('--baudrate', type=int, help='Baud rate (overrides config)')
    parser.add_argument('--daemon',   action='store_true', help='Run as daemon (no CLI)')
    parser.add_argument('--reset-db', action='store_true', help='Reset database')
    args = parser.parse_args()

    manager = IoTManager(args.config)

    if args.port:
        manager.config.set('SERIAL', 'port', args.port)
    if args.baudrate:
        manager.config.set('SERIAL', 'baudrate', str(args.baudrate))

    if args.reset_db:
        if os.path.exists(manager.db.db_path):
            os.remove(manager.db.db_path)
            print(f"Database {manager.db.db_path} deleted")
        manager.db.init_database()
        print("Database reinitialized")

    if not manager.start():
        print("Failed to start system")
        sys.exit(1)

    time.sleep(1)
    manager.configure_arduino()

    try:
        if args.daemon:
            print("Running in daemon mode. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        else:
            manager.run_cli()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        manager.stop()
