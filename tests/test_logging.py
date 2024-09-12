from unittest.mock import patch

from paperweight.logging_config import setup_logging


def test_setup_logging_invalid_level():
    config = {
        'logging': {
            'level': 'INVALID_LEVEL',
            'file': 'test.log'
        }
    }

    with patch('paperweight.utils.load_config', return_value=config):
        with patch('paperweight.logging_config.logging.config.dictConfig') as mock_dict_config:
            setup_logging(config['logging'])
            called_config = mock_dict_config.call_args[0][0]
            assert called_config['root']['level'] == 'INFO'
