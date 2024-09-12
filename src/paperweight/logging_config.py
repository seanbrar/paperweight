import logging
import logging.config
import os


def setup_logging(logging_config):
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    logging_level = logging_config.get('level', 'INFO').upper()
    if logging_level not in valid_levels:
        logging_level = 'INFO'

    log_file = logging_config['file']
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'level': 'WARNING',
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': log_file,
                'formatter': 'standard',
                'level': logging_level,
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': logging_level,
        },
    }
    logging.config.dictConfig(logging_config)

    logging.getLogger().setLevel(logging_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging setup completed with level: {logging_level}")
