"""Tests for the database connection module."""

from unittest.mock import MagicMock, patch

import pytest

from paperweight.db import connect_db


class TestConnectDb:
    """Tests for connect_db context manager."""

    @patch("psycopg.connect")
    def test_connect_db_basic(self, mock_connect):
        """Test basic database connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
            "sslmode": "prefer",
        }

        with connect_db(db_config) as conn:
            assert conn == mock_conn

        mock_connect.assert_called_once_with(
            host="localhost",
            port=5432,
            dbname="testdb",
            user="testuser",
            password="testpass",
            sslmode="prefer",
            autocommit=False,
        )
        mock_conn.close.assert_called_once()

    @patch("psycopg.connect")
    def test_connect_db_autocommit(self, mock_connect):
        """Test database connection with autocommit enabled."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
        }

        with connect_db(db_config, autocommit=True):
            pass

        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["autocommit"] is True

    @patch("psycopg.connect")
    def test_connect_db_default_sslmode(self, mock_connect):
        """Test that sslmode defaults to 'prefer' when not specified."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
        }

        with connect_db(db_config):
            pass

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["sslmode"] == "prefer"

    @patch("psycopg.connect")
    def test_connect_db_closes_on_exception(self, mock_connect):
        """Test that connection is closed even when an exception occurs."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
        }

        with pytest.raises(ValueError):
            with connect_db(db_config):
                raise ValueError("Test error")

        mock_conn.close.assert_called_once()
