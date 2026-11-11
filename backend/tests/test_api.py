from fastapi.testclient import TestClient

from app.main import criar_app

from .conftest import config_teste, conversar


def test_sem_chave_da_401():
    with TestClient(criar_app(config_teste())) as c:
        r = c.post("/api/conversa", json={"mensagem": "oi"})
    assert r.status_code == 401
    assert r.json()["erro"]["codigo"] == "NAO_AUTORIZADO"
    assert r.json()["erro"]["id_requisicao"]


def test_saude_e_pronto_sem_chave():
    with TestClient(criar_app(config_teste())) as c:
        assert c.get("/saude").json() == {"ok": True}
        assert c.get("/pronto").json()["provedor"] == "regras"


def test_mensagem_vazia_da_422(cliente):
    r = cliente.post("/api/conversa", json={"mensagem": ""})
    assert r.status_code == 422
    assert r.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_json_quebrado_vem_no_formato_padrao(cliente):
    r = cliente.post("/api/conversa", content=b"{nao e json", headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 422)
    assert "erro" in r.json()


def test_consulta_chamado(cliente):
    r = conversar(cliente, "status do CH-5001")
    assert r["intencao"] == "consultar_chamado"
    assert "em atendimento" in r["resposta"]
    assert r["acao"] is None


def test_chamado_inexistente_nao_quebra(cliente):
    r = conversar(cliente, "status do CH-9999")
    assert "Não existe chamado CH-9999" in r["resposta"]


def test_consulta_equipamento(cliente):
    r = conversar(cliente, "o PAT-3002 está na garantia?")
    assert "fora da garantia" in r["resposta"]
    assert "em manutenção" in r["resposta"]


def test_duvida_cita_artigo(cliente):
    r = conversar(cliente, "a vpn fica caindo")
    assert r["fontes"][0]["id"] == "KB-01"
    assert "[KB-01]" in r["resposta"]
    assert r["passos"][0] == "classificar → duvida"
    assert r["passos"][-1] == "redigir → texto pronto"
    assert r["provedor"] == "regras"


def test_fluxo_sse(cliente):
    with cliente.stream("POST", "/api/conversa/fluxo", json={"mensagem": "oi"}) as r:
        corpo = "".join(r.iter_text())
    assert "event: inicio" in corpo
    assert "event: texto" in corpo
    assert corpo.strip().endswith("data: {}")


def test_lista_chamados(cliente):
    numeros = [c["numero"] for c in cliente.get("/api/chamados").json()]
    assert set(numeros) >= {"CH-5001", "CH-5002", "CH-5003", "CH-5004"}
