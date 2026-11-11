"""API do Atende.ai (FastAPI). Também serve a tela React já compilada, em /."""

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import ferramentas
from .agente import Contexto, montar_grafo, responder
from .banco import Acao, criar_fabrica
from .busca import BuscaBM25
from .config import Config, carregar
from .dados_exemplo import ARTIGOS, popular
from .erros import ErroAPI, registrar
from .ia import criar_provedor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("atende")
PASTA_TELA = Path(__file__).resolve().parent.parent / "static"


class Mensagem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class Pergunta(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    historico: list[Mensagem] = Field(default_factory=list, max_length=20)


def criar_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or carregar()

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        fabrica = criar_fabrica(cfg.banco_url)
        with fabrica() as s:
            popular(s)
        provedor = criar_provedor(cfg)
        ctx = Contexto(fabrica=fabrica, busca=BuscaBM25(ARTIGOS), provedor=provedor, tentativas=cfg.tentativas_ia)
        app.state.ctx = ctx
        app.state.grafo = montar_grafo(ctx)
        log.info("Atende.ai no ar com o provedor %s", provedor.nome)
        yield

    app = FastAPI(title="Atende.ai", version="0.1.0", lifespan=ciclo)
    registrar(app)

    @app.middleware("http")
    async def id_e_log(request: Request, chamar):
        request.state.id_requisicao = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        inicio = time.perf_counter()
        resposta = await chamar(request)
        ms = (time.perf_counter() - inicio) * 1000
        resposta.headers["X-Request-ID"] = request.state.id_requisicao
        if request.url.path.startswith("/api"):
            log.info("%s %s %d %.1fms id=%s", request.method, request.url.path, resposta.status_code, ms, request.state.id_requisicao)
        return resposta

    def exigir_chave(x_api_key: str | None = Header(default=None)):
        if x_api_key != cfg.chave_api:
            raise ErroAPI(401, "NAO_AUTORIZADO", "Envie o cabeçalho X-API-Key com a chave certa.")

    protegido = [Depends(exigir_chave)]

    # ---------- saúde ----------

    @app.get("/saude")
    async def saude():
        return {"ok": True}

    @app.get("/pronto")
    async def pronto(request: Request):
        p = request.app.state.ctx.provedor
        return {"provedor": p.nome, "usa_ia": p.usa_ia, "ia_disponivel": await p.disponivel(),
                "cache_busca": request.app.state.ctx.busca.acertos_cache}

    # ---------- conversa ----------

    async def _rodar(request: Request, p: Pergunta) -> dict:
        estado = await responder(request.app.state.grafo, p.mensagem, [m.model_dump() for m in p.historico])
        return {
            "resposta": estado["resposta"], "intencao": estado["intencao"], "passos": estado["passos"],
            "fontes": [{"id": f["id"], "titulo": f["titulo"]} for f in estado.get("fontes", [])],
            "acao": estado.get("acao"), "provedor": estado.get("provedor", "regras"),
            "id_requisicao": request.state.id_requisicao,
        }

    @app.post("/api/conversa", dependencies=protegido)
    async def conversa(p: Pergunta, request: Request):
        return await _rodar(request, p)

    @app.post("/api/conversa/fluxo", dependencies=protegido)
    async def conversa_fluxo(p: Pergunta, request: Request):
        """Mesma resposta, enviada aos poucos por SSE: evento 'inicio', vários 'texto' e 'fim'."""
        r = await _rodar(request, p)

        async def eventos():
            meta = {k: v for k, v in r.items() if k != "resposta"}
            yield f"event: inicio\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"
            palavras = r["resposta"].split(" ")
            for i in range(0, len(palavras), 3):
                pedaco = " ".join(palavras[i:i + 3]) + (" " if i + 3 < len(palavras) else "")
                yield f"event: texto\ndata: {json.dumps(pedaco, ensure_ascii=False)}\n\n"
            yield "event: fim\ndata: {}\n\n"

        return StreamingResponse(eventos(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    # ---------- dados ----------

    @app.get("/api/chamados", dependencies=protegido)
    async def chamados(request: Request):
        with request.app.state.ctx.fabrica() as s:
            return ferramentas.listar_chamados(s)

    @app.get("/api/chamados/{numero}", dependencies=protegido)
    async def chamado(numero: str, request: Request):
        with request.app.state.ctx.fabrica() as s:
            return ferramentas.consultar_chamado(s, numero)

    @app.get("/api/equipamentos/{patrimonio}", dependencies=protegido)
    async def equipamento(patrimonio: str, request: Request):
        with request.app.state.ctx.fabrica() as s:
            return ferramentas.consultar_equipamento(s, patrimonio)

    @app.get("/api/base", dependencies=protegido)
    async def base(q: str, request: Request, quantos: int = 3):
        return [r.__dict__ for r in request.app.state.ctx.busca.buscar(q, min(max(quantos, 1), 8))]

    # ---------- aprovação ----------

    @app.get("/api/acoes", dependencies=protegido)
    async def acoes(request: Request, situacao: str | None = None):
        with request.app.state.ctx.fabrica() as s:
            q = select(Acao).order_by(Acao.criada_em.desc()).limit(50)
            if situacao:
                q = q.where(Acao.situacao == situacao)
            return [ferramentas.acao_para_dict(a) for a in s.scalars(q).all()]

    @app.post("/api/acoes/{acao_id}/aprovar", dependencies=protegido)
    async def aprovar(acao_id: str, request: Request):
        with request.app.state.ctx.fabrica() as s:
            return ferramentas.acao_para_dict(ferramentas.decidir(s, acao_id, aprovar=True))

    @app.post("/api/acoes/{acao_id}/rejeitar", dependencies=protegido)
    async def rejeitar(acao_id: str, request: Request):
        with request.app.state.ctx.fabrica() as s:
            return ferramentas.acao_para_dict(ferramentas.decidir(s, acao_id, aprovar=False))

    # ---------- tela ----------

    if PASTA_TELA.exists():
        app.mount("/assets", StaticFiles(directory=PASTA_TELA / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        async def tela(caminho: str):
            arquivo = PASTA_TELA / caminho
            if caminho and arquivo.is_file() and PASTA_TELA in arquivo.resolve().parents:
                return FileResponse(arquivo)
            return FileResponse(PASTA_TELA / "index.html")

    return app


app = criar_app()
