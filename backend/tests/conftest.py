import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import criar_app

CHAVE = "chave-teste"


def config_teste(**troca) -> Config:
    base = dict(chave_api=CHAVE, provedor="regras", ollama_url="http://localhost:1", ollama_modelo="x", ollama_num_gpu=None,
                anthropic_chave="", anthropic_modelo="x", banco_url="sqlite:///:memory:", timeout_ia=1, tentativas_ia=1)
    base.update(troca)
    return Config(**base)


@pytest.fixture
def cliente():
    with TestClient(criar_app(config_teste()), headers={"X-API-Key": CHAVE}) as c:
        yield c


def conversar(cliente, mensagem: str) -> dict:
    r = cliente.post("/api/conversa", json={"mensagem": mensagem})
    assert r.status_code == 200, r.text
    return r.json()
