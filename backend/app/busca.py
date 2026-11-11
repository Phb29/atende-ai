"""Busca na base de soluções com BM25.

BM25 dá nota a cada artigo pelas palavras da pergunta que aparecem nele:
palavra rara vale mais que palavra comum, e texto longo não ganha só por ser longo.
Não precisa de modelo nem de internet, e o resultado é sempre o mesmo para a mesma pergunta.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

PALAVRAS_VAZIAS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas",
    "que", "para", "pra", "por", "com", "sem", "se", "meu", "minha", "eu", "voce", "como", "qual", "quais",
    "ao", "aos", "ou", "mais", "muito", "esta", "estou", "isso", "esse", "essa", "tem", "ter", "faco",
    "fazer", "posso", "pode", "nao", "sim", "me", "ja", "so", "ele", "ela", "quando", "onde", "porque",
    "fica", "ficar", "ficou", "faz", "faco", "esta", "estar", "sempre", "toda", "todo", "hora", "agora", "ta",
}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def _radical(palavra: str) -> str:
    """Corta finais comuns para 'senhas' achar 'senha' e 'impressoras' achar 'impressora'."""
    for fim in ("coes", "cao", "mente", "s"):
        if palavra.endswith(fim) and len(palavra) - len(fim) >= 4:
            return palavra[: -len(fim)]
    return palavra


def termos(texto: str) -> list[str]:
    return [_radical(p) for p in re.findall(r"[a-z0-9-]+", normalizar(texto)) if p not in PALAVRAS_VAZIAS and len(p) > 1]


@dataclass(frozen=True)
class Resultado:
    id: str
    titulo: str
    texto: str
    nota: float


class BuscaBM25:
    def __init__(self, artigos: list[dict], k1: float = 1.4, b: float = 0.75):
        self.artigos = artigos
        self.k1, self.b = k1, b
        self._docs = [Counter(termos(a["titulo"] + " " + a["titulo"] + " " + a["texto"])) for a in artigos]
        self._tamanhos = [sum(d.values()) for d in self._docs]
        self._media = sum(self._tamanhos) / max(len(self._docs), 1)
        frequencia = Counter(t for d in self._docs for t in d)
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in frequencia.items()}
        self._cache: dict[tuple[str, int], list[Resultado]] = {}
        self.acertos_cache = 0

    def buscar(self, pergunta: str, quantos: int = 3) -> list[Resultado]:
        chave = (normalizar(pergunta).strip(), quantos)
        if chave in self._cache:
            self.acertos_cache += 1
            return self._cache[chave]
        consulta = termos(pergunta)
        notas = []
        for i, doc in enumerate(self._docs):
            nota = 0.0
            for t in consulta:
                f = doc.get(t, 0)
                if f:
                    ajuste = 1 - self.b + self.b * self._tamanhos[i] / self._media
                    nota += self._idf[t] * f * (self.k1 + 1) / (f + self.k1 * ajuste)
            if nota > 0:
                a = self.artigos[i]
                notas.append(Resultado(a["id"], a["titulo"], a["texto"], round(nota, 3)))
        notas.sort(key=lambda r: r.nota, reverse=True)
        self._cache[chave] = notas[:quantos]
        return self._cache[chave]
