"""Ferramentas do agente.

Leitura (rodam na hora): consultar_chamado, consultar_equipamento.
Escrita (precisam de aprovação): abrir_chamado, resetar_senha, desbloquear_conta.

Cada ação de escrita tem dois passos separados: `preparar` grava uma Acao pendente
e `executar` aplica a mudança. O agente só chama `preparar`; `executar` só roda
pela rota de aprovação, chamada por uma pessoa.
"""

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .banco import Acao, Chamado, Equipamento, Usuario, agora
from .erros import ErroAPI

SITUACAO_CHAMADO = {
    "aberto": "aberto, na fila", "em_atendimento": "em atendimento",
    "aguardando_usuario": "aguardando resposta sua", "resolvido": "resolvido",
}
SITUACAO_EQUIPAMENTO = {"em_uso": "em uso", "manutencao": "em manutenção", "estoque": "no estoque"}


# ---------- leitura ----------

def consultar_chamado(sessao: Session, numero: str) -> dict:
    c = sessao.get(Chamado, numero.upper())
    if c is None:
        raise ErroAPI(404, "CHAMADO_NAO_ENCONTRADO", f"Não existe chamado {numero.upper()}.")
    return {
        "numero": c.numero, "titulo": c.titulo, "situacao": c.situacao,
        "situacao_texto": SITUACAO_CHAMADO.get(c.situacao, c.situacao), "prioridade": c.prioridade,
        "tecnico": c.tecnico, "solicitante": c.solicitante, "criado_em": c.criado_em.date().isoformat(),
    }


def consultar_equipamento(sessao: Session, patrimonio: str) -> dict:
    e = sessao.get(Equipamento, patrimonio.upper())
    if e is None:
        raise ErroAPI(404, "EQUIPAMENTO_NAO_ENCONTRADO", f"Não existe equipamento {patrimonio.upper()}.")
    dono = sessao.get(Usuario, e.responsavel) if e.responsavel else None
    return {
        "patrimonio": e.patrimonio, "tipo": e.tipo, "modelo": e.modelo, "situacao": e.situacao,
        "situacao_texto": SITUACAO_EQUIPAMENTO.get(e.situacao, e.situacao), "garantia_ate": e.garantia_ate,
        "na_garantia": e.garantia_ate >= agora().date().isoformat(), "responsavel": dono.nome if dono else None,
    }


def listar_chamados(sessao: Session) -> list[dict]:
    linhas = sessao.scalars(select(Chamado).order_by(Chamado.criado_em.desc())).all()
    return [consultar_chamado(sessao, c.numero) for c in linhas]


# ---------- escrita: preparar ----------

def _usuario(sessao: Session, matricula: str) -> Usuario:
    u = sessao.get(Usuario, matricula.upper())
    if u is None:
        raise ErroAPI(404, "USUARIO_NAO_ENCONTRADO", f"Não existe usuário com matrícula {matricula.upper()}.")
    return u


def preparar(sessao: Session, tipo: str, dados: dict) -> Acao:
    if tipo == "abrir_chamado":
        if dados.get("solicitante"):
            _usuario(sessao, dados["solicitante"])
        resumo = f"Abrir chamado ({dados.get('prioridade', 'media')}): {dados['titulo'][:80]}"
    elif tipo == "resetar_senha":
        u = _usuario(sessao, dados["matricula"])
        resumo = f"Resetar a senha de {u.nome} ({u.matricula}) e enviar senha temporária para {u.email}"
    elif tipo == "desbloquear_conta":
        u = _usuario(sessao, dados["matricula"])
        if not u.conta_bloqueada:
            raise ErroAPI(409, "CONTA_NAO_BLOQUEADA", f"A conta de {u.nome} ({u.matricula}) não está bloqueada.")
        resumo = f"Desbloquear a conta de {u.nome} ({u.matricula})"
    else:
        raise ErroAPI(400, "ACAO_DESCONHECIDA", f"Ação {tipo} não existe.")
    acao = Acao(id="A-" + secrets.token_hex(4), tipo=tipo, dados=dados, resumo=resumo)
    sessao.add(acao)
    sessao.commit()
    return acao


# ---------- escrita: decidir ----------

def _proximo_numero(sessao: Session) -> str:
    maior = sessao.scalar(select(func.max(Chamado.numero)))
    return f"CH-{int(maior.split('-')[1]) + 1 if maior else 5001}"


def _executar(sessao: Session, acao: Acao) -> str:
    d = acao.dados
    if acao.tipo == "abrir_chamado":
        numero = _proximo_numero(sessao)
        sessao.add(Chamado(numero=numero, titulo=d["titulo"], descricao=d.get("descricao", ""), situacao="aberto",
                           prioridade=d.get("prioridade", "media"), solicitante=d.get("solicitante")))
        return f"Chamado {numero} aberto."
    u = _usuario(sessao, d["matricula"])
    if acao.tipo == "resetar_senha":
        u.conta_bloqueada = False
        return f"Senha de {u.nome} resetada. Senha temporária enviada para {u.email} (troca obrigatória no próximo login)."
    if acao.tipo == "desbloquear_conta":
        u.conta_bloqueada = False
        return f"Conta de {u.nome} desbloqueada."
    raise ErroAPI(400, "ACAO_DESCONHECIDA", f"Ação {acao.tipo} não existe.")


def decidir(sessao: Session, acao_id: str, aprovar: bool) -> Acao:
    acao = sessao.get(Acao, acao_id)
    if acao is None:
        raise ErroAPI(404, "ACAO_NAO_ENCONTRADA", f"Não existe ação {acao_id}.")
    if acao.situacao != "pendente":
        raise ErroAPI(409, "ACAO_JA_DECIDIDA", f"A ação {acao_id} já foi {acao.situacao}.")
    acao.resultado = _executar(sessao, acao) if aprovar else "Rejeitada. Nada foi alterado."
    acao.situacao = "aprovada" if aprovar else "rejeitada"
    acao.decidida_em = agora()
    sessao.commit()
    return acao


def acao_para_dict(a: Acao) -> dict:
    return {
        "id": a.id, "tipo": a.tipo, "resumo": a.resumo, "dados": a.dados, "situacao": a.situacao,
        "resultado": a.resultado, "criada_em": a.criada_em.isoformat(),
        "decidida_em": a.decidida_em.isoformat() if a.decidida_em else None,
    }
