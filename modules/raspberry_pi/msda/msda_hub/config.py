"""
msda_hub.config — Configuration Management
Reads and writes iot_config.ini
"""

import os
import configparser


class ConfigManager:
    def __init__(self, config_file='iot_config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser(inline_comment_prefixes=('#',))
        self.load_or_create_config()

    def load_or_create_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.create_default_config()

    def create_default_config(self):
        self.config['SERIAL'] = {
            'port': '/dev/ttyAMA0',
            'baudrate': '115200',
            'timeout': '1'
        }
        self.config['DATABASE'] = {
            'path': 'iot_sensors.db',
            'retention_days': '30',
            'backup_enabled': 'true',
            'backup_interval_hours': '24'
        }
        self.config['MONITORING'] = {
            'sensor_read_interval': '2000',
            'heartbeat_timeout': '30',
            'auto_reconnect': 'true',
            'max_reconnect_attempts': '10'
        }
        self.config['ALERTS'] = {
            'enabled': 'true',
            'temp_min': '-10',
            'temp_max': '50',
            'humidity_min': '20',
            'humidity_max': '80',
            'distance_min': '5',
            'distance_max': '200',
            'motion_threshold': '1'
        }
        self.config['LOGGING'] = {
            'level': 'INFO',
            'file': 'iot_system.log',
            'max_size_mb': '100',
            'backup_count': '5'
        }
        self.config['API'] = {
            'enabled': 'false',
            'host': '0.0.0.0',
            'port': '8080'
        }
        self.save_config()

    def save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def get(self, section, key, fallback=None):
        try:
            return self.config.get(section, key)
        except Exception:
            return fallback

    def getint(self, section, key, fallback=0):
        try:
            return self.config.getint(section, key)
        except Exception:
            return fallback

    def getboolean(self, section, key, fallback=False):
        try:
            return self.config.getboolean(section, key)
        except Exception:
            return fallback

    def set(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
        self.save_config()
