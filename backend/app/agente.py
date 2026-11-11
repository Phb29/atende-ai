"""O agente do Atende.ai como um grafo do LangGraph.

    START → classificar ─┬─ consultar ───────────────→ END
                         ├─ preparar_acao ───────────→ END   (só deixa a ação pendente)
                         ├─ buscar_base → redigir ───→ END   (a IA escreve com base nos artigos)
                         └─ responder_fixo ──────────→ END   (saudação, pedir um dado que falta)

Respostas sobre chamados, equipamentos e ações usam texto pronto, montado a partir do banco.
Assim a IA nunca inventa um status. A IA só escreve no nó `redigir`.
"""

import operator
import re
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import sessionmaker

from . import ferramentas
from .busca import BuscaBM25, normalizar
from .erros import ErroAPI
from .ia import Provedor, gerar_com_tentativas
from .intencao import classificar


class Estado(TypedDict, total=False):
    mensagem: str
    historico: list[dict]
    intencao: str
    dados: dict
    resultado: dict | None
    fontes: list[dict]
    acao: dict | None
    resposta: str
    provedor: str
    passos: Annotated[list[str], operator.add]  # cada nó acrescenta o seu; vira o "rastro" na tela


@dataclass
class Contexto:
    fabrica: sessionmaker
    busca: BuscaBM25
    provedor: Provedor
    tentativas: int


INSTRUCAO_BASE = (
    "Você é o Atende.ai, assistente do help desk de TI de uma empresa. Responda em português do Brasil, "
    "em no máximo 5 frases, com passos práticos. Use SOMENTE as informações dos artigos abaixo. "
    "Cite o código do artigo entre colchetes, por exemplo [KB-01]. Se os artigos não responderem à pergunta, "
    "diga que não encontrou e sugira abrir um chamado.\n\nArtigos:\n{artigos}"
)
INSTRUCAO_CONVERSA = (
    "Você é o Atende.ai, assistente do help desk de TI de uma empresa. Responda em português do Brasil, em até 3 frases. "
    "Você ajuda com chamados (CH-0000), equipamentos (PAT-0000), senhas e contas (matrícula U-000) e dúvidas de TI. "
    "Não invente procedimentos da empresa. Se o assunto não for de TI, diga educadamente que só ajuda com TI."
)
RE_CITACAO = re.compile(r"\[(KB-\d{2})\]")

TEXTO_PEDIR_DADO = {
    "resetar_senha": "Posso resetar a senha. Qual é a matrícula da pessoa? (formato U-000, por exemplo U-101)",
    "desbloquear_conta": "Posso desbloquear a conta. Qual é a matrícula? (formato U-000, por exemplo U-102)",
    "consultar_chamado": "Qual é o número do chamado? (formato CH-0000, por exemplo CH-5001)",
}
TEXTO_SAUDACAO = (
    "Olá! Sou o Atende.ai. Posso consultar um chamado ou equipamento, tirar dúvidas de TI, "
    "abrir chamados e resetar senhas. As ações que mudam algo passam pela sua aprovação."
)


TEXTO_FORA_DO_ASSUNTO = (
    "Só consigo ajudar com assuntos de TI: chamados, equipamentos, senhas, acesso, rede e programas. "
    "Se for um problema técnico, me conte o que está acontecendo."
)
PALAVRAS_TI = {
    "computador", "notebook", "pc", "sistema", "rede", "internet", "wifi", "wi-fi", "vpn", "senha", "email",
    "e-mail", "impressora", "programa", "software", "instalar", "mouse", "teclado", "monitor", "acesso", "login",
    "conta", "servidor", "arquivo", "pasta", "backup", "erro", "tela", "celular", "teams", "office", "excel",
    "windows", "travou", "travando", "lento", "chamado", "suporte", "ti", "cabo", "certificado", "atualiza",
}


def parece_ti(mensagem: str) -> bool:
    palavras = set(re.findall(r"[a-z0-9-]+", normalizar(mensagem)))
    return any(p in palavras or p.rstrip("s") in palavras for p in PALAVRAS_TI) or any(
        p.startswith(("atualiz", "configur", "instal", "conect", "trav", "imprim")) for p in palavras
    )


def _primeiras_frases(texto: str, n: int = 2) -> str:
    frases = re.split(r"(?<=[.!?])\s+", texto)
    return " ".join(frases[:n])


def montar_grafo(ctx: Contexto):
    # ---------- nós ----------

    def no_classificar(estado: Estado) -> Estado:
        i = classificar(estado["mensagem"])
        return {"intencao": i.tipo, "dados": i.dados, "provedor": "regras", "passos": [f"classificar → {i.tipo}"]}

    def no_consultar(estado: Estado) -> Estado:
        tipo, d = estado["intencao"], estado["dados"]
        with ctx.fabrica() as sessao:
            try:
                if tipo == "consultar_chamado":
                    r = ferramentas.consultar_chamado(sessao, d["numero"])
                    tecnico = f", com {r['tecnico']}" if r["tecnico"] else ""
                    texto = (f"O chamado **{r['numero']}** ({r['titulo']}) está **{r['situacao_texto']}**{tecnico}. "
                             f"Prioridade {r['prioridade']}, aberto em {r['criado_em']}.")
                else:
                    r = ferramentas.consultar_equipamento(sessao, d["patrimonio"])
                    garantia = "na garantia" if r["na_garantia"] else "fora da garantia"
                    dono = f", com {r['responsavel']}" if r["responsavel"] else ""
                    texto = (f"**{r['patrimonio']}** é um {r['tipo']} {r['modelo']}, **{r['situacao_texto']}**{dono}. "
                             f"Está {garantia} (até {r['garantia_ate']}).")
            except ErroAPI as e:
                return {"resultado": None, "resposta": f"{e.mensagem} Confira o número e tente de novo.",
                        "passos": [f"{tipo} → não encontrado"]}
        return {"resultado": r, "resposta": texto, "passos": [f"{tipo} → ok"]}

    def no_preparar_acao(estado: Estado) -> Estado:
        tipo = estado["intencao"]
        with ctx.fabrica() as sessao:
            try:
                acao = ferramentas.acao_para_dict(ferramentas.preparar(sessao, tipo, estado["dados"]))
            except ErroAPI as e:
                return {"acao": None, "resposta": e.mensagem, "passos": [f"preparar {tipo} → recusado"]}
        texto = f"Preparei a ação: **{acao['resumo']}**. Ela só será feita depois que alguém aprovar."
        return {"acao": acao, "resposta": texto, "passos": [f"preparar {tipo} → aguardando aprovação"]}

    def no_buscar_base(estado: Estado) -> Estado:
        achados = ctx.busca.buscar(estado["mensagem"], quantos=3)
        # Fica só com artigos com nota próxima do melhor: evita citar artigo que não tem a ver.
        if achados:
            achados = [a for a in achados if a.nota >= achados[0].nota * 0.6]
        fontes = [{"id": a.id, "titulo": a.titulo, "texto": a.texto, "nota": a.nota} for a in achados]
        return {"fontes": fontes, "passos": [f"buscar_base → {len(fontes)} artigo(s)"]}

    async def no_redigir(estado: Estado) -> Estado:
        fontes = estado.get("fontes", [])
        historico = estado.get("historico", [])[-6:]
        mensagens = [*historico, {"role": "user", "content": estado["mensagem"]}]

        if fontes:
            artigos = "\n".join(f"[{f['id']}] {f['titulo']}: {f['texto']}" for f in fontes)
            texto = await gerar_com_tentativas(ctx.provedor, INSTRUCAO_BASE.format(artigos=artigos), mensagens, ctx.tentativas)
            if texto:
                citadas = set(RE_CITACAO.findall(texto))
                permitidas = {f["id"] for f in fontes}
                # Proteção: se a IA citar um artigo que não recebeu, descartamos e usamos o texto pronto.
                if citadas <= permitidas:
                    if not citadas:
                        texto += f" [{fontes[0]['id']}]"
                    return {"resposta": texto, "provedor": ctx.provedor.nome, "passos": ["redigir → ia"]}
                return {**_redigir_fixo(fontes), "passos": ["redigir → ia citou artigo inexistente, usei texto pronto"]}
            return {**_redigir_fixo(fontes), "passos": ["redigir → texto pronto"]}

        if not parece_ti(estado["mensagem"]):
            # Modelo pequeno ignora "só fale de TI". A regra barra antes, sem gastar chamada de IA.
            return {"resposta": TEXTO_FORA_DO_ASSUNTO, "passos": ["redigir → fora do assunto (sem ia)"]}
        texto = await gerar_com_tentativas(ctx.provedor, INSTRUCAO_CONVERSA, mensagens, ctx.tentativas)
        if texto:
            return {"resposta": texto, "provedor": ctx.provedor.nome, "passos": ["redigir → ia (sem artigo)"]}
        return {"resposta": ("Não encontrei isso na base de soluções. Se for um problema, escreva "
                             "**abrir chamado:** e descreva o que acontece."), "passos": ["redigir → sem resposta"]}

    def _redigir_fixo(fontes: list[dict]) -> Estado:
        partes = [f"{_primeiras_frases(f['texto'])} [{f['id']}]" for f in fontes[:2]]
        return {"resposta": " ".join(partes)}

    def no_responder_fixo(estado: Estado) -> Estado:
        if estado["intencao"] == "saudacao":
            return {"resposta": TEXTO_SAUDACAO, "passos": ["responder_fixo → saudação"]}
        return {"resposta": TEXTO_PEDIR_DADO[estado["dados"]["para"]], "passos": ["responder_fixo → pedir dado"]}

    # ---------- arestas ----------

    def rota(estado: Estado) -> str:
        tipo = estado["intencao"]
        if tipo in ("consultar_chamado", "consultar_equipamento"):
            return "consultar"
        if tipo in ("abrir_chamado", "resetar_senha", "desbloquear_conta"):
            return "preparar_acao"
        if tipo == "duvida":
            return "buscar_base"
        return "responder_fixo"

    g = StateGraph(Estado)
    g.add_node("classificar", no_classificar)
    g.add_node("consultar", no_consultar)
    g.add_node("preparar_acao", no_preparar_acao)
    g.add_node("buscar_base", no_buscar_base)
    g.add_node("redigir", no_redigir)
    g.add_node("responder_fixo", no_responder_fixo)

    g.add_edge(START, "classificar")
    g.add_conditional_edges("classificar", rota, ["consultar", "preparar_acao", "buscar_base", "responder_fixo"])
    g.add_edge("buscar_base", "redigir")
    for fim in ("consultar", "preparar_acao", "redigir", "responder_fixo"):
        g.add_edge(fim, END)
    return g.compile()


async def responder(grafo: Any, mensagem: str, historico: list[dict]) -> Estado:
    return await grafo.ainvoke({"mensagem": mensagem, "historico": historico, "passos": []})
