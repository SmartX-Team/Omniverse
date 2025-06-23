import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
import pytest_asyncio

from app.main import app
from app.websocket.manager import WebSocketManager


@pytest.fixture
def client():
    """FastAPI 테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """비동기 HTTP 클라이언트"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def websocket_manager():
    """WebSocket 매니저 인스턴스"""
    return WebSocketManager()


@pytest.fixture
def sample_coordinate_data():
    """테스트용 좌표 데이터"""
    return {
        "type": "coordinate_update",
        "prim_path": "/World/Husky_01",
        "latitude": 37.123456,
        "longitude": 127.654321,
        "height": 100.0,
        "metadata": {
            "speed": 2.5,
            "heading": 45.0,
            "battery": 85
        }
    }


@pytest.fixture
def sample_client_register_data():
    """테스트용 클라이언트 등록 데이터"""
    return {
        "type": "client_register",
        "client_type": "web_ui"
    }


@pytest.fixture
def sample_select_object_data():
    """테스트용 객체 선택 데이터"""
    return {
        "type": "select_object",
        "prim_path": "/World/Husky_01"
    }