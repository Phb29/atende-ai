"""Dados fictícios para o help desk funcionar logo na primeira vez que liga."""

from datetime import timedelta

from sqlalchemy.orm import Session

from .banco import Chamado, Equipamento, Usuario, agora

USUARIOS = [
    ("U-101", "Ana Ribeiro", "ana.ribeiro@empresa.local", "Financeiro", False),
    ("U-102", "Bruno Lima", "bruno.lima@empresa.local", "Comercial", True),
    ("U-103", "Carla Souza", "carla.souza@empresa.local", "RH", False),
    ("U-104", "Diego Martins", "diego.martins@empresa.local", "Jurídico", False),
]

EQUIPAMENTOS = [
    ("PAT-3001", "Notebook", "Dell Latitude 5450", "em_uso", "2027-03-10", "U-101"),
    ("PAT-3002", "Notebook", "Lenovo ThinkPad E14", "manutencao", "2026-06-30", "U-102"),
    ("PAT-3003", "Monitor", "LG 24MP400", "em_uso", "2028-01-15", "U-103"),
    ("PAT-3004", "Impressora", "HP LaserJet M428", "em_uso", "2026-12-01", None),
    ("PAT-3005", "Notebook", "Dell Latitude 5450", "estoque", "2028-08-20", None),
]

CHAMADOS = [
    ("CH-5001", "VPN cai a cada 10 minutos", "em_atendimento", "alta", "U-101", "Marcos (Redes)", 2),
    ("CH-5002", "Notebook não liga", "aguardando_usuario", "media", "U-102", "Júlia (Suporte)", 5),
    ("CH-5003", "Instalar Power BI", "aberto", "baixa", "U-103", None, 1),
    ("CH-5004", "Impressora do 2º andar manchando", "resolvido", "media", "U-104", "Júlia (Suporte)", 9),
]

# Base de soluções: o agente busca aqui e cita o código do artigo.
ARTIGOS = [
    {
        "id": "KB-01",
        "titulo": "VPN não conecta ou cai",
        "texto": (
            "Confirme que a internet funciona sem a VPN. Feche o cliente FortiClient e abra de novo. "
            "Se aparecer erro de certificado, atualize o cliente pelo Portal da Empresa. "
            "Se a VPN cair com frequência, troque do Wi-Fi para o cabo ou para outra rede. "
            "Persistindo, abra um chamado informando o horário das quedas."
        ),
    },
    {
        "id": "KB-02",
        "titulo": "Política de senhas",
        "texto": (
            "A senha expira a cada 90 dias e precisa ter no mínimo 12 caracteres, com letras e números. "
            "Não é permitido repetir as últimas 5 senhas. Após 5 tentativas erradas a conta é bloqueada por segurança. "
            "O reset de senha e o desbloqueio de conta são feitos pelo help desk com aprovação de um técnico."
        ),
    },
    {
        "id": "KB-03",
        "titulo": "Impressora não imprime",
        "texto": (
            "Verifique se a impressora está ligada e com papel. Cancele os documentos presos na fila de impressão. "
            "Remova e adicione de novo a impressora pelo endereço \\\\print01. "
            "Manchas na folha costumam indicar toner no fim: abra um chamado para troca do toner."
        ),
    },
    {
        "id": "KB-04",
        "titulo": "E-mail corporativo no celular",
        "texto": (
            "Instale o aplicativo Outlook, entre com o e-mail corporativo e aprove o acesso no Authenticator. "
            "O celular precisa ter bloqueio de tela ativo. Celular pessoal só acessa e-mail, não acessa a VPN."
        ),
    },
    {
        "id": "KB-05",
        "titulo": "Computador lento",
        "texto": (
            "Reinicie o computador: muitos travamentos somem depois de reiniciar. "
            "Feche abas e programas que não estão em uso. Confira se há atualização do Windows pendente. "
            "Se o disco estiver acima de 90% de uso, apague arquivos temporários. "
            "Lentidão persistente pode ser defeito: abra um chamado com o número de patrimônio."
        ),
    },
    {
        "id": "KB-06",
        "titulo": "Pedido de instalação de software",
        "texto": (
            "Programas só podem ser instalados pelo help desk. Abra um chamado com o nome do programa e o motivo. "
            "Softwares pagos precisam de aprovação do gestor. O prazo de atendimento é de até 2 dias úteis."
        ),
    },
    {
        "id": "KB-07",
        "titulo": "Wi-Fi de visitantes",
        "texto": (
            "A rede de visitantes se chama EMPRESA-CONVIDADO. A senha muda toda segunda-feira e fica na recepção. "
            "Essa rede não acessa sistemas internos nem a impressora."
        ),
    },
    {
        "id": "KB-08",
        "titulo": "Equipamento na garantia",
        "texto": (
            "Equipamento com defeito dentro da garantia é enviado ao fabricante pelo help desk. "
            "Durante o conserto, um notebook reserva do estoque pode ser emprestado. Consulte a garantia pelo número de patrimônio."
        ),
    },
]


def popular(sessao: Session) -> None:
    """Insere os dados de exemplo só se o banco estiver vazio."""
    if sessao.get(Usuario, "U-101") is not None:
        return
    for matricula, nome, email, setor, bloqueada in USUARIOS:
        sessao.add(Usuario(matricula=matricula, nome=nome, email=email, setor=setor, conta_bloqueada=bloqueada))
    for patrimonio, tipo, modelo, situacao, garantia, responsavel in EQUIPAMENTOS:
        sessao.add(Equipamento(patrimonio=patrimonio, tipo=tipo, modelo=modelo, situacao=situacao,
                               garantia_ate=garantia, responsavel=responsavel))
    for numero, titulo, situacao, prioridade, solicitante, tecnico, dias in CHAMADOS:
        sessao.add(Chamado(numero=numero, titulo=titulo, descricao=titulo, situacao=situacao,
                           prioridade=prioridade, solicitante=solicitante, tecnico=tecnico,
                           criado_em=agora() - timedelta(days=dias)))
    sessao.commit()
