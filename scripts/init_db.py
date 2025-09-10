


import logging
from radar.db.session import ENGINE
from radar.db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=ENGINE)
    logger.info("Database schema initialized successfully.")

if __name__ == "__main__":
    main()