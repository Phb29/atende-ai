"""Um formato só para todo erro: {"erro": {"codigo", "mensagem", "id_requisicao"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("atende.erros")


class ErroAPI(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str):
        self.status, self.codigo, self.mensagem = status, codigo, mensagem


def _corpo(request: Request, codigo: str, mensagem: str) -> dict:
    return {"erro": {"codigo": codigo, "mensagem": mensagem, "id_requisicao": getattr(request.state, "id_requisicao", None)}}


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErroAPI)
    async def _erro_api(request: Request, e: ErroAPI):
        return JSONResponse(_corpo(request, e.codigo, e.mensagem), status_code=e.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, e: StarletteHTTPException):
        codigos = {400: "REQUISICAO_INVALIDA", 404: "NAO_ENCONTRADO", 405: "METODO_NAO_PERMITIDO"}
        return JSONResponse(_corpo(request, codigos.get(e.status_code, "ERRO_HTTP"), str(e.detail)), status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, e: RequestValidationError):
        primeiro = e.errors()[0] if e.errors() else {}
        campo = ".".join(str(p) for p in primeiro.get("loc", []) if p != "body")
        return JSONResponse(_corpo(request, "DADOS_INVALIDOS", f"Campo inválido: {campo or 'corpo'}"), status_code=422)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, e: Exception):
        log.exception("erro inesperado")
        return JSONResponse(_corpo(request, "ERRO_INTERNO", "Erro inesperado. Informe o id da requisição ao suporte."), status_code=500)
