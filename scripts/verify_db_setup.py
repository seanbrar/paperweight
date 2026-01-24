import logging
import sys
from pathlib import Path

import yaml

# Add src to sys.path to import paperweight modules
sys.path.append(str(Path(__file__).parent.parent / "src"))

from paperweight.db import connect_db, is_db_enabled

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify_db")

def load_config():
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def verify_db_connection(config):
    if not is_db_enabled(config):
        logger.info("ℹ️  Database is NOT enabled in config.yaml")
        return True

    logger.info("🔍 Connecting to database...")
    db_config = config.get("db", {})

    try:
        with connect_db(db_config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                if result and result[0] == 1:
                    logger.info(f"✅ Successfully connected to database '{db_config.get('database')}' at '{db_config.get('host')}:{db_config.get('port')}'")

                    # Optional: Check if tables exist
                    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                    tables = cur.fetchall()
                    table_names = [t[0] for t in tables]
                    if table_names:
                        logger.info(f"   Found tables: {', '.join(table_names)}")
                    else:
                        logger.warning("   ⚠️  Connected, but no tables found in 'public' schema.")

                    return True
                else:
                    logger.error("❌ Connected, but SELECT 1 failed.")
                    return False
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Paperweight Database Verification...")
    config = load_config()
    if verify_db_connection(config):
        print("\n🎉 SUCCESS: Database connection verified.")
        sys.exit(0)
    else:
        print("\n❌ FAILURE: Database verification failed.")
        sys.exit(1)
