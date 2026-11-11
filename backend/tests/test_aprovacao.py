"""A regra mais importante: nada que grava dados acontece sem aprovação humana."""

from .conftest import conversar


def _quantos_chamados(cliente) -> int:
    return len(cliente.get("/api/chamados").json())


def test_abrir_chamado_so_depois_de_aprovar(cliente):
    antes = _quantos_chamados(cliente)
    r = conversar(cliente, "Quero abrir um chamado: o monitor do RH está piscando")
    acao = r["acao"]
    assert acao["situacao"] == "pendente"
    assert _quantos_chamados(cliente) == antes  # ainda não criou

    aprovada = cliente.post(f"/api/acoes/{acao['id']}/aprovar").json()
    assert aprovada["situacao"] == "aprovada"
    assert "CH-5005" in aprovada["resultado"]
    assert _quantos_chamados(cliente) == antes + 1


def test_rejeitar_nao_cria_nada(cliente):
    antes = _quantos_chamados(cliente)
    acao = conversar(cliente, "abra um chamado: teclado com teclas falhando")["acao"]
    r = cliente.post(f"/api/acoes/{acao['id']}/rejeitar").json()
    assert r["situacao"] == "rejeitada"
    assert _quantos_chamados(cliente) == antes


def test_decidir_duas_vezes_da_409(cliente):
    acao = conversar(cliente, "resetar senha do U-101")["acao"]
    assert cliente.post(f"/api/acoes/{acao['id']}/aprovar").status_code == 200
    r = cliente.post(f"/api/acoes/{acao['id']}/aprovar")
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "ACAO_JA_DECIDIDA"


def test_desbloquear_conta(cliente):
    acao = conversar(cliente, "desbloquear a conta do U-102")["acao"]
    assert "Bruno Lima" in acao["resumo"]
    r = cliente.post(f"/api/acoes/{acao['id']}/aprovar").json()
    assert "desbloqueada" in r["resultado"]
    # segunda vez: a conta já não está bloqueada, então nem prepara
    r2 = conversar(cliente, "desbloquear a conta do U-102")
    assert r2["acao"] is None
    assert "não está bloqueada" in r2["resposta"]


def test_matricula_inexistente_nao_prepara(cliente):
    r = conversar(cliente, "resetar senha do U-999")
    assert r["acao"] is None
    assert "U-999" in r["resposta"]


def test_lista_so_pendentes(cliente):
    conversar(cliente, "resetar senha do U-103")
    pendentes = cliente.get("/api/acoes", params={"situacao": "pendente"}).json()
    assert pendentes and all(a["situacao"] == "pendente" for a in pendentes)
