"""Configuração lida das variáveis de ambiente. Nenhuma chave fica no código."""

import os
from dataclasses import dataclass


def _env(nome: str, padrao: str = "") -> str:
    return os.environ.get(nome, padrao).strip()


@dataclass(frozen=True)
class Config:
    chave_api: str
    provedor: str  # regras | ollama | anthropic
    ollama_url: str
    ollama_modelo: str
    ollama_num_gpu: int | None  # 0 = só processador (contorna erro de CUDA em algumas placas)
    anthropic_chave: str
    anthropic_modelo: str
    banco_url: str
    timeout_ia: float
    tentativas_ia: int


def carregar() -> Config:
    return Config(
        chave_api=_env("ATENDE_CHAVE_API", "demo-key"),
        provedor=_env("ATENDE_PROVEDOR", "regras").lower(),
        ollama_url=_env("OLLAMA_URL", "http://localhost:11434"),
        ollama_modelo=_env("OLLAMA_MODELO", "qwen2.5:3b"),
        ollama_num_gpu=int(_env("OLLAMA_NUM_GPU")) if _env("OLLAMA_NUM_GPU") else None,
        anthropic_chave=_env("ANTHROPIC_API_KEY"),
        anthropic_modelo=_env("ANTHROPIC_MODELO", "claude-haiku-5-5"),
        banco_url=_env("ATENDE_BANCO", "sqlite:///./dados/atende.db"),
        timeout_ia=float(_env("ATENDE_TIMEOUT_IA", "60")),
        tentativas_ia=int(_env("ATENDE_TENTATIVAS_IA", "2")),
    )
