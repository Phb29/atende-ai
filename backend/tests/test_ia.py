"""O agente com uma IA de mentira, para testar o nó `redigir` sem chamar modelo de verdade."""

import asyncio

from app.agente import Contexto, montar_grafo, responder
from app.banco import criar_fabrica
from app.busca import BuscaBM25
from app.dados_exemplo import ARTIGOS, popular
from app.ia import Provedor


class IAFalsa(Provedor):
    nome = "ia-falsa"

    def __init__(self, texto: str | None):
        self.texto, self.chamadas = texto, 0

    async def gerar(self, sistema, mensagens):
        self.chamadas += 1
        if self.texto is None:
            raise ValueError("fora do ar")
        return self.texto


def _rodar(ia: Provedor, mensagem: str):
    fabrica = criar_fabrica("sqlite:///:memory:")
    with fabrica() as s:
        popular(s)
    grafo = montar_grafo(Contexto(fabrica, BuscaBM25(ARTIGOS), ia, tentativas=2))
    return asyncio.run(responder(grafo, mensagem, []))


def test_ia_responde_com_citacao_valida():
    e = _rodar(IAFalsa("Reinicie o FortiClient [KB-01]."), "a vpn não conecta")
    assert e["provedor"] == "ia-falsa"
    assert e["resposta"] == "Reinicie o FortiClient [KB-01]."


def test_ia_que_inventa_artigo_e_descartada():
    e = _rodar(IAFalsa("Veja o artigo [KB-99]."), "a vpn não conecta")
    assert e["provedor"] == "regras"
    assert "[KB-01]" in e["resposta"]
    assert "KB-99" not in e["resposta"]


def test_ia_fora_do_ar_usa_texto_pronto_depois_das_tentativas():
    ia = IAFalsa(None)
    e = _rodar(ia, "a vpn não conecta")
    assert ia.chamadas == 2
    assert e["provedor"] == "regras"
    assert "[KB-01]" in e["resposta"]


def test_fora_do_assunto_nem_chama_ia():
    ia = IAFalsa("A capital da França é Paris.")
    e = _rodar(ia, "qual a capital da França?")
    assert ia.chamadas == 0
    assert "Só consigo ajudar com assuntos de TI" in e["resposta"]


def test_assunto_de_ti_sem_artigo_chama_ia():
    ia = IAFalsa("Tente reiniciar o Teams.")
    e = _rodar(ia, "o teams não abre a câmera")
    assert ia.chamadas == 1
    assert e["provedor"] == "ia-falsa"


def test_consulta_nunca_usa_ia():
    ia = IAFalsa("inventado")
    e = _rodar(ia, "status do CH-5001")
    assert ia.chamadas == 0
    assert "em atendimento" in e["resposta"]
