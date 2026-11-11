"""Descobre o que o usuário quer, por regras.

Regras e não IA porque um modelo pequeno erra nisso com frequência, e aqui errar custa caro:
confundir "qual o status do CH-5001" com "abra um chamado" criaria um chamado à toa.
As regras são testadas em tests/test_intencao.py.
"""

import re
from dataclasses import dataclass, field

from .busca import normalizar

RE_CHAMADO = re.compile(r"\bch[-\s]?(\d{4})\b")
RE_PATRIMONIO = re.compile(r"\b(?:pat[-\s]?|patrimonio\s*(?:n[ou]?\.?\s*)?)(\d{4})\b")
RE_MATRICULA = re.compile(r"\bu[-\s]?(\d{3})\b")

RE_ABRIR = re.compile(r"\b(abr\w*|abra|registr\w*|cri\w*|ger\w*|quero|preciso)\b[^.?!]{0,40}\b(chamado|ticket|solicitacao)\b")
RE_SENHA = re.compile(r"\b(reset\w*|redefin\w*|troc\w*|esqueci|recuper\w*|nova)\b[^.?!]{0,30}\bsenha\b|\bsenha\b[^.?!]{0,20}\b(expir\w*|reset\w*)\b")
RE_DESBLOQUEIO = re.compile(r"\bdesbloque\w*\b|\b(conta|usuario|login)\b[^.?!]{0,20}\bbloquead\w*\b|\bbloquead\w*\b[^.?!]{0,20}\b(conta|usuario|login)\b")
RE_MEU_CHAMADO = re.compile(r"\b(meu|minha|o)\s+(chamado|ticket|solicitacao)\b")
RE_STATUS = re.compile(r"\b(status|andamento|situacao|como esta|cade|resolvido|ja foi)\b")
RE_URGENTE =re.compile(r"\b(urgente|parad\w*|ninguem|todos|todo o setor|critico)\b")
SAUDACOES = ("oi", "ola", "bom dia", "boa tarde", "boa noite", "obrigad", "valeu", "tudo bem")
PERGUNTA_POLITICA = re.compile(r"^(como|qual|quais|quantos|quanto|quando|o que|por que|posso|e permitido)\b")


@dataclass
class Intencao:
    tipo: str  # saudacao | consultar_chamado | consultar_equipamento | abrir_chamado | resetar_senha | desbloquear_conta | pedir_dado | duvida
    dados: dict = field(default_factory=dict)


def classificar(mensagem: str) -> Intencao:
    texto = normalizar(mensagem).strip()
    chamado = RE_CHAMADO.search(texto)
    patrimonio = RE_PATRIMONIO.search(texto)
    matricula = RE_MATRICULA.search(texto)
    mat = f"U-{matricula.group(1)}" if matricula else None
    eh_pergunta = PERGUNTA_POLITICA.search(texto) is not None

    # Ações que gravam dados vêm primeiro, mas "como trocar a senha?" é dúvida, não pedido.
    if RE_SENHA.search(texto) and not (eh_pergunta and not mat):
        if not mat:
            return Intencao("pedir_dado", {"falta": "matricula", "para": "resetar_senha"})
        return Intencao("resetar_senha", {"matricula": mat})

    if RE_DESBLOQUEIO.search(texto) and not (eh_pergunta and not mat):
        if not mat:
            return Intencao("pedir_dado", {"falta": "matricula", "para": "desbloquear_conta"})
        return Intencao("desbloquear_conta", {"matricula": mat})

    if RE_ABRIR.search(texto) and not chamado and not RE_STATUS.search(texto):
        return Intencao("abrir_chamado", {
            "titulo": mensagem.strip()[:120],
            "descricao": mensagem.strip(),
            "prioridade": "alta" if RE_URGENTE.search(texto) else "media",
            "solicitante": mat,
            "patrimonio": f"PAT-{patrimonio.group(1)}" if patrimonio else None,
        })

    if chamado:
        return Intencao("consultar_chamado", {"numero": f"CH-{chamado.group(1)}"})

    if patrimonio:
        return Intencao("consultar_equipamento", {"patrimonio": f"PAT-{patrimonio.group(1)}"})

    if RE_MEU_CHAMADO.search(texto) and RE_STATUS.search(texto):
        return Intencao("pedir_dado", {"falta": "numero_chamado", "para": "consultar_chamado"})

    if len(texto) < 40 and any(texto.startswith(s) or f" {s}" in texto for s in SAUDACOES):
        return Intencao("saudacao")

    return Intencao("duvida", {"pergunta": mensagem.strip()})
