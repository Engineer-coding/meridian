from fastapi.testclient import TestClient

from meridian_ai.app import create_app
from meridian_ai.settings import Settings


def test_unreachable_broker_is_live_but_not_ready() -> None:
    # 1 numaralı portta broker yok: tüketici bağlanamaz, süreç yine de ayakta kalır.
    settings = Settings(rabbitmq_user="test", rabbitmq_password="test", rabbitmq_port=1, _env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").json() == {"status": "UP"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "DOWN"}
