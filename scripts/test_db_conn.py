"""Simple script to test database connectivity."""

from pathlib import Path

import psycopg
import yaml


def test_db_connection():
    config_path = Path("config.yaml")
    with config_path.open("r") as handle:
        config = yaml.safe_load(handle)
        db_config = config["db"]

    try:
        conn_str = f"host={db_config['host']} port={db_config['port']} dbname={db_config['database']} user={db_config['user']} password={db_config['password']} sslmode={db_config['sslmode']}"
        with psycopg.connect(conn_str) as conn:
            print("Successfully connected to the database!")
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()
                print(f"PostgreSQL version: {version[0]}")
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
        return False
    return True


if __name__ == "__main__":
    test_db_connection()
