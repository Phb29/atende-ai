"""Provedores de IA com a mesma interface: recebem instruções + conversa e devolvem texto.

- regras: não chama IA nenhuma. O agente usa textos prontos (bom para testes e sem internet).
- ollama: modelo local, gratuito, rodando no próprio PC.
- anthropic: Claude pela API (precisa de chave).
"""

import asyncio
import logging

import httpx

from .config import Config

log = logging.getLogger("atende.ia")


class FalhaIA(Exception):
    pass


class Provedor:
    nome = "base"
    usa_ia = True

    async def gerar(self, sistema: str, mensagens: list[dict]) -> str:
        raise NotImplementedError

    async def disponivel(self) -> bool:
        return True


class ProvedorRegras(Provedor):
    nome = "regras"
    usa_ia = False

    async def gerar(self, sistema: str, mensagens: list[dict]) -> str:
        raise FalhaIA("o provedor de regras não gera texto")


class ProvedorOllama(Provedor):
    def __init__(self, url: str, modelo: str, timeout: float, num_gpu: int | None = None):
        self.url, self.modelo, self.timeout, self.num_gpu = url.rstrip("/"), modelo, timeout, num_gpu
        self.nome = f"ollama · {modelo}"

    async def gerar(self, sistema: str, mensagens: list[dict]) -> str:
        opcoes: dict = {"temperature": 0.2}
        if self.num_gpu is not None:
            opcoes["num_gpu"] = self.num_gpu
        corpo = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, *mensagens],
            "stream": False,
            "options": opcoes,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as cliente:
            r = await cliente.post(f"{self.url}/api/chat", json=corpo)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()

    async def disponivel(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as cliente:
                return (await cliente.get(f"{self.url}/api/tags")).status_code == 200
        except httpx.HTTPError:
            return False


class ProvedorAnthropic(Provedor):
    def __init__(self, chave: str, modelo: str, timeout: float):
        if not chave:
            raise ValueError("ANTHROPIC_API_KEY não definida")
        self.chave, self.modelo, self.timeout = chave, modelo, timeout
        self.nome = f"claude · {modelo}"

    async def gerar(self, sistema: str, mensagens: list[dict]) -> str:
        cabecalhos = {"x-api-key": self.chave, "anthropic-version": "2023-06-01"}
        corpo = {"model": self.modelo, "max_tokens": 600, "system": sistema, "messages": mensagens}
        async with httpx.AsyncClient(timeout=self.timeout) as cliente:
            r = await cliente.post("https://api.anthropic.com/v1/messages", headers=cabecalhos, json=corpo)
            r.raise_for_status()
            partes = r.json()["content"]
            return "".join(p.get("text", "") for p in partes if p.get("type") == "text").strip()


def criar_provedor(cfg: Config) -> Provedor:
    if cfg.provedor == "ollama":
        return ProvedorOllama(cfg.ollama_url, cfg.ollama_modelo, cfg.timeout_ia, cfg.ollama_num_gpu)
    if cfg.provedor == "anthropic":
        return ProvedorAnthropic(cfg.anthropic_chave, cfg.anthropic_modelo, cfg.timeout_ia)
    return ProvedorRegras()


async def gerar_com_tentativas(provedor: Provedor, sistema: str, mensagens: list[dict], tentativas: int) -> str | None:
    """Tenta algumas vezes com espera crescente. Devolve None se não deu: quem chamou usa o texto pronto."""
    if not provedor.usa_ia:
        return None
    for n in range(tentativas):
        try:
            texto = await provedor.gerar(sistema, mensagens)
            if texto:
                return texto
        except (httpx.HTTPError, KeyError, ValueError, FalhaIA) as erro:
            log.warning("falha na IA (%s), tentativa %d/%d: %s", provedor.nome, n + 1, tentativas, erro)
        if n + 1 < tentativas:
            await asyncio.sleep(0.4 * 2**n)
    return None
