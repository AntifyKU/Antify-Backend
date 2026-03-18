"""Stubs Firebase & socketio BEFORE any app import"""
import sys
from unittest.mock import MagicMock

class _ExpiredIdTokenError(Exception):
    def __init__(self, message="expired", _cause=None, _http_response=None):
        super().__init__(message)

class _RevokedIdTokenError(Exception):
    def __init__(self, message="revoked", _cause=None, _http_response=None):
        super().__init__(message)

class _InvalidIdTokenError(Exception):
    def __init__(self, message="invalid", _cause=None, _http_response=None):
        super().__init__(message)

# Build firebase_admin.auth stub that carries the real exception classes
auth_stub = MagicMock()
auth_stub.ExpiredIdTokenError = _ExpiredIdTokenError
auth_stub.RevokedIdTokenError = _RevokedIdTokenError
auth_stub.InvalidIdTokenError = _InvalidIdTokenError

firestore_stub = MagicMock()
credentials_stub = MagicMock()

firebase_stub = MagicMock()
firebase_stub.auth = auth_stub
firebase_stub.firestore = firestore_stub
firebase_stub.credentials = credentials_stub

# Register stubs — use direct assignment (not setdefault) so they always win
sys.modules["firebase_admin"] = firebase_stub
sys.modules["firebase_admin.auth"] = auth_stub
sys.modules["firebase_admin.firestore"] = firestore_stub
sys.modules["firebase_admin.credentials"] = credentials_stub

# Stub socketio so importing main.py doesn't require a running server
sys.modules["socketio"] = MagicMock()

# Stub openai so openrouter.py imports cleanly without a real API key
openai_stub = MagicMock()
openai_stub.AsyncOpenAI = MagicMock(return_value=MagicMock())
sys.modules["openai"] = openai_stub

# Stub app.config with dummy values so service modules import cleanly
config_stub = MagicMock()
config_stub.AI_SERVICE_URL = "http://localhost:8001"
config_stub.OPENROUTER_API_KEY = "test-key"
config_stub.OPENROUTER_MODEL = "test-model"
config_stub.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
sys.modules["app.config"] = config_stub
