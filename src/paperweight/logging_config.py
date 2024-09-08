import logging
import logging.config

from paperweight.utils import load_config


def setup_logging():
    config = load_config()
    logging_config = {
        'version': 1,
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
                'level': config['logging']['level'],
            },
            'file': {
                'class': 'logging.FileHandler',
                'filename': config['logging']['file'],
                'formatter': 'standard',
                'level': config['logging']['level'],
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': config['logging']['level'],
        },
    }
    logging.config.dictConfig(logging_config)
