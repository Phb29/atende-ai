"""Tabelas do help desk: usuários, equipamentos, chamados e ações à espera de aprovação."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"
    matricula: Mapped[str] = mapped_column(String(8), primary_key=True)  # U-101
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    setor: Mapped[str] = mapped_column(String(60))
    conta_bloqueada: Mapped[bool] = mapped_column(Boolean, default=False)


class Equipamento(Base):
    __tablename__ = "equipamentos"
    patrimonio: Mapped[str] = mapped_column(String(10), primary_key=True)  # PAT-3001
    tipo: Mapped[str] = mapped_column(String(40))
    modelo: Mapped[str] = mapped_column(String(80))
    situacao: Mapped[str] = mapped_column(String(20))  # em_uso | manutencao | estoque
    garantia_ate: Mapped[str] = mapped_column(String(10))  # AAAA-MM-DD
    responsavel: Mapped[str | None] = mapped_column(ForeignKey("usuarios.matricula"), nullable=True)


class Chamado(Base):
    __tablename__ = "chamados"
    numero: Mapped[str] = mapped_column(String(10), primary_key=True)  # CH-5001
    titulo: Mapped[str] = mapped_column(String(160))
    descricao: Mapped[str] = mapped_column(Text, default="")
    situacao: Mapped[str] = mapped_column(String(24))  # aberto | em_atendimento | aguardando_usuario | resolvido
    prioridade: Mapped[str] = mapped_column(String(10))  # baixa | media | alta
    solicitante: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tecnico: Mapped[str | None] = mapped_column(String(80), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Acao(Base):
    """Uma ação que grava dados. Nasce 'pendente' e só roda depois de aprovada por uma pessoa."""

    __tablename__ = "acoes"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30))  # abrir_chamado | resetar_senha | desbloquear_conta
    dados: Mapped[dict] = mapped_column(JSON)
    resumo: Mapped[str] = mapped_column(String(240))
    situacao: Mapped[str] = mapped_column(String(12), default="pendente")  # pendente | aprovada | rejeitada
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    decidida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def criar_fabrica(url: str) -> sessionmaker:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    opcoes = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if ":memory:" in url:
        from sqlalchemy.pool import StaticPool

        motor = create_engine(url, connect_args=opcoes, poolclass=StaticPool)
    else:
        motor = create_engine(url, connect_args=opcoes, pool_pre_ping=True)
    Base.metadata.create_all(motor)
    return sessionmaker(bind=motor, expire_on_commit=False)
