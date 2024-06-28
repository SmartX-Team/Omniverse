import json
import psycopg2
import os


# PostgreSQL 데이터베이스 연결을 담당하는 싱글톤 클래스
class PostgreSQLConnectionSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.connection = None
            cls._instance.load_config()
        return cls._instance
    
    def load_config(self):
        """Loads database configuration from a JSON file."""
        config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/dt_server/UWB_GATEWAY/config.json')
        with open(config_path, 'r') as file:
            config = json.load(file)
            self.db_config = config

    def get_connection(self):
        """Gets a database connection, creating one if none exists."""
        if self.connection is None or self.connection.closed:
            self.connection = psycopg2.connect(
                dbname=self.db_config['db_name'],
                user=self.db_config['db_user'],
                password=self.db_config['db_password'],
                host=self.db_config['db_host'],
                port=self.db_config['db_port']
            )
        return self.connection

    def close_connection(self):
        """Closes the database connection."""
        if self.connection is not self.connection.closed:
            self.connection.close()