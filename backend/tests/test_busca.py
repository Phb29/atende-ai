import pytest

from app.busca import BuscaBM25
from app.dados_exemplo import ARTIGOS

busca = BuscaBM25(ARTIGOS)


@pytest.mark.parametrize("pergunta,esperado", [
    ("a vpn não conecta", "KB-01"),
    ("de quanto em quanto tempo a senha expira?", "KB-02"),
    ("a impressora está manchando a folha", "KB-03"),
    ("como configurar o email no celular", "KB-04"),
    ("meu computador está muito lento", "KB-05"),
    ("quero instalar um programa", "KB-06"),
    ("qual a senha do wifi de visitantes", "KB-07"),
    ("meu equipamento está na garantia?", "KB-08"),
])
def test_primeiro_resultado(pergunta, esperado):
    assert busca.buscar(pergunta)[0].id == esperado


def test_vpn_caindo_nao_traz_wifi_de_visitantes():
    ids = [r.id for r in busca.buscar("a VPN fica caindo, o que eu faço?")]
    assert ids[0] == "KB-01"
    assert "KB-07" not in ids


def test_pergunta_sem_relacao_nao_acha_nada():
    assert busca.buscar("receita de bolo de cenoura") == []


def test_cache_conta_acertos():
    b = BuscaBM25(ARTIGOS)
    b.buscar("vpn caindo")
    b.buscar("VPN caindo ")
    assert b.acertos_cache == 1
