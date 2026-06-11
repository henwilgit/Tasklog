import gc
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    app_module.app.config['DATABASE'] = db_path
    app_module.app.config['TESTING'] = True
    app_module.init_db()

    with app_module.app.test_client() as client:
        yield client

    os.close(db_fd)
    # sqlite3 connections opened via `with conn:` are committed but not
    # closed, so on Windows the file stays locked until they're collected.
    gc.collect()
    os.remove(db_path)
