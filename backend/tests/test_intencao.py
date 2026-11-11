import pytest

from app.intencao import classificar

CASOS = [
    ("Qual o status do CH-5001?", "consultar_chamado", {"numero": "CH-5001"}),
    ("cadê o chamado ch 5002", "consultar_chamado", {"numero": "CH-5002"}),
    ("o notebook PAT-3002 ta na garantia?", "consultar_equipamento", {"patrimonio": "PAT-3002"}),
    ("patrimônio 3001", "consultar_equipamento", {"patrimonio": "PAT-3001"}),
    ("Esqueci minha senha, matrícula U-101", "resetar_senha", {"matricula": "U-101"}),
    ("resetar senha do u102", "resetar_senha", {"matricula": "U-102"}),
    ("minha conta está bloqueada, sou U-102", "desbloquear_conta", {"matricula": "U-102"}),
    ("desbloquear usuário U-102", "desbloquear_conta", {"matricula": "U-102"}),
]


@pytest.mark.parametrize("mensagem,tipo,dados", CASOS)
def test_classifica_com_dados(mensagem, tipo, dados):
    i = classificar(mensagem)
    assert i.tipo == tipo
    for chave, valor in dados.items():
        assert i.dados[chave] == valor


@pytest.mark.parametrize("mensagem", [
    "Quero abrir um chamado: a impressora do RH não liga",
    "abra um chamado urgente, o sistema caiu para todos",
    "preciso registrar uma solicitação de instalação do Excel",
])
def test_abrir_chamado(mensagem):
    assert classificar(mensagem).tipo == "abrir_chamado"


def test_urgente_vira_prioridade_alta():
    assert classificar("abra um chamado urgente, a VPN caiu").dados["prioridade"] == "alta"
    assert classificar("abra um chamado, o mouse falha").dados["prioridade"] == "media"


@pytest.mark.parametrize("mensagem,para", [
    ("esqueci minha senha", "resetar_senha"),
    ("minha conta está bloqueada", "desbloquear_conta"),
    ("qual o status do meu chamado?", "consultar_chamado"),
])
def test_pede_o_dado_que_falta(mensagem, para):
    i = classificar(mensagem)
    assert i.tipo == "pedir_dado"
    assert i.dados["para"] == para


@pytest.mark.parametrize("mensagem", [
    "Como faço para trocar a senha?",
    "Quantos dias a senha expira?",
    "a VPN não conecta",
    "como acessar o e-mail no celular",
])
def test_pergunta_nao_vira_acao(mensagem):
    assert classificar(mensagem).tipo == "duvida"


def test_status_de_chamado_nao_abre_chamado():
    assert classificar("quero saber o andamento do meu chamado").tipo == "pedir_dado"


@pytest.mark.parametrize("mensagem", ["oi", "Bom dia!", "valeu, obrigado"])
def test_saudacao(mensagem):
    assert classificar(mensagem).tipo == "saudacao"
