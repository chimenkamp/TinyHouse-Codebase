"""
msda_hub.database — Database Management
SQLite operations: sensor registry, readings, alerts, events, backups.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .config import ConfigManager


class DatabaseManager:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.db_path = config.get('DATABASE', 'path', 'iot_sensors.db')
        self.conn = None
        self.init_database()

    def init_database(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT UNIQUE NOT NULL,
                sensor_type TEXT,
                pin INTEGER,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                metadata TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                value1 REAL,
                value2 REAL,
                value3 REAL,
                unit1 TEXT,
                unit2 TEXT,
                unit3 TEXT,
                raw_data TEXT,
                FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT,
                severity TEXT,
                message TEXT,
                data TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sensor_id TEXT,
                alert_type TEXT,
                value REAL,
                threshold REAL,
                message TEXT,
                acknowledged BOOLEAN DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT,
                date DATE,
                min_value REAL,
                max_value REAL,
                avg_value REAL,
                count INTEGER,
                UNIQUE(sensor_id, date)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_data_timestamp ON sensor_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_id ON sensor_data(sensor_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)')
        self.conn.commit()

    def add_sensor(self, sensor_id: str, sensor_type: str, pin: int, metadata: dict = None):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO sensors (sensor_id, sensor_type, pin, metadata, last_seen)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (sensor_id, sensor_type, pin, json.dumps(metadata) if metadata else None))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Error adding sensor: {e}")

    def add_sensor_data(self, sensor_id: str, values: list, units: list, raw_data: str = None):
        cursor = self.conn.cursor()
        try:
            values = (values + [None, None, None])[:3]
            units = (units + [None, None, None])[:3]

            cursor.execute('''
                INSERT INTO sensor_data
                (sensor_id, value1, value2, value3, unit1, unit2, unit3, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (sensor_id, *values, *units, raw_data))

            cursor.execute('''
                UPDATE sensors SET last_seen = CURRENT_TIMESTAMP WHERE sensor_id = ?
            ''', (sensor_id,))

            self.conn.commit()
            self.check_alerts(sensor_id, values[0] if values[0] is not None else 0)

        except Exception as e:
            logging.error(f"Error adding sensor data: {e}")

    def check_alerts(self, sensor_id: str, value: float):
        if not self.config.getboolean('ALERTS', 'enabled'):
            return

        alerts_config = self.config.config['ALERTS']
        cursor = self.conn.cursor()
        alert_triggered = False
        alert_type = ""
        threshold = 0
        sid = sensor_id.upper()

        # Temperature sensors: DHT22, DS18B20, BMP280
        if sid in ('DHT22', 'DS18B20', 'BMP280') or 'temp' in sid.lower():
            temp_min = float(alerts_config.get('temp_min', -10))
            temp_max = float(alerts_config.get('temp_max', 50))
            if value < temp_min:
                alert_triggered, alert_type, threshold = True, "LOW_TEMPERATURE", temp_min
            elif value > temp_max:
                alert_triggered, alert_type, threshold = True, "HIGH_TEMPERATURE", temp_max

        # Ultrasonic distance sensor: HC_SR04
        elif sid in ('HC_SR04', 'HC-SR04') or 'ultrasonic' in sid.lower():
            dist_min = float(alerts_config.get('distance_min', 5))
            dist_max = float(alerts_config.get('distance_max', 200))
            if value < dist_min:
                alert_triggered, alert_type, threshold = True, "PROXIMITY_ALERT", dist_min
            elif value > dist_max:
                alert_triggered, alert_type, threshold = True, "DISTANCE_EXCEEDED", dist_max

        # PIR motion sensor
        elif sid == 'PIR' or 'pir' in sid.lower():
            motion_threshold = float(alerts_config.get('motion_threshold', 1))
            if value >= motion_threshold:
                alert_triggered, alert_type, threshold = True, "MOTION_DETECTED", motion_threshold

        if alert_triggered:
            message = (
                f"Sensor {sensor_id}: {alert_type} - "
                f"Value {value:.2f} exceeds threshold {threshold:.2f}"
            )
            cursor.execute('''
                INSERT INTO alerts (sensor_id, alert_type, value, threshold, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (sensor_id, alert_type, value, threshold, message))
            self.conn.commit()
            logging.warning(message)

    def add_event(self, event_type: str, severity: str, message: str, data: dict = None):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO events (event_type, severity, message, data)
                VALUES (?, ?, ?, ?)
            ''', (event_type, severity, message, json.dumps(data) if data else None))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Error adding event: {e}")

    def get_latest_readings(self, limit: int = 100) -> list:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT sensor_id, timestamp, value1, value2, value3, unit1, unit2, unit3
            FROM sensor_data
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def get_sensor_statistics(self, sensor_id: str, days: int = 7) -> dict:
        cursor = self.conn.cursor()
        since = datetime.now() - timedelta(days=days)
        cursor.execute('''
            SELECT
                MIN(value1) as min_val,
                MAX(value1) as max_val,
                AVG(value1) as avg_val,
                COUNT(*) as count
            FROM sensor_data
            WHERE sensor_id = ? AND timestamp > ?
        ''', (sensor_id, since))
        result = cursor.fetchone()
        return {'min': result[0], 'max': result[1], 'avg': result[2], 'count': result[3]}

    def cleanup_old_data(self):
        retention_days = self.config.getint('DATABASE', 'retention_days', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM sensor_data WHERE timestamp < ?', (cutoff_date,))
        cursor.execute('DELETE FROM events WHERE timestamp < ?', (cutoff_date,))
        deleted = cursor.rowcount
        self.conn.commit()
        if deleted > 0:
            logging.info(f"Cleaned up {deleted} old records")
        cursor.execute('VACUUM')

    def backup_database(self):
        if not self.config.getboolean('DATABASE', 'backup_enabled'):
            return
        backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            backup_conn = sqlite3.connect(backup_path)
            self.conn.backup(backup_conn)
            backup_conn.close()
            logging.info(f"Database backed up to {backup_path}")
            self.cleanup_old_backups()
        except Exception as e:
            logging.error(f"Backup failed: {e}")

    def cleanup_old_backups(self):
        backup_files = sorted(Path('.').glob(f"{self.db_path}.backup_*"))
        if len(backup_files) > 5:
            for old_backup in backup_files[:-5]:
                old_backup.unlink()
                logging.info(f"Deleted old backup: {old_backup}")

    def close(self):
        if self.conn:
            self.conn.close()
