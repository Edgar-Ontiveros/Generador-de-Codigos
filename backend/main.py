"""
main.py — API FastAPI del generador de códigos.

Endpoints bajo /api; en producción sirve además el build de React desde /.
"""

import base64
import hmac
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel

from core import Catalog, UDM_SAT

app = FastAPI(title="Generador de códigos Herinox", version="5.0")

# Autenticación HTTP Basic con UNA sola credencial, tomada del entorno.
# Si AUTH_PASS no está definida (p. ej. en desarrollo local) no se exige nada.
AUTH_USER = os.environ.get("AUTH_USER", "herinox")
AUTH_PASS = os.environ.get("AUTH_PASS", "")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not AUTH_PASS:
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if header.startswith("Basic "):
        try:
            user, _, pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            ok_user = hmac.compare_digest(user.encode(), AUTH_USER.encode())
            ok_pass = hmac.compare_digest(pwd.encode(), AUTH_PASS.encode())
            if ok_user and ok_pass:
                return await call_next(request)
        except (ValueError, UnicodeDecodeError):
            pass
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Generador Herinox"'},
    )

# CORS abierto para desarrollo (el dev server de Vite corre en otro puerto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

catalog = Catalog()


# ----------------------------- Modelos pydantic ----------------------------- #
class GenerarRequest(BaseModel):
    descripcion: str


class Similar(BaseModel):
    score: float
    codigo: str
    descripcion: str
    familia: str
    linea: str
    sublinea: str
    cod_sublinea: Optional[int] = None
    codigo_sat: str
    udm: str


class GenerarResponse(BaseModel):
    codigo: str
    estado: str  # "nuevo" | "duplicado" | "revisar"
    familia: str
    linea: str
    sublinea: str
    cod_familia: Optional[int] = None
    cod_linea: Optional[int] = None
    cod_sublinea: Optional[int] = None
    codigo_sat: str
    udm: str
    udm_sat: str
    peso: float
    confianza: float
    similares: List[Similar]


class GuardarRequest(BaseModel):
    codigo: str
    articulo: str
    familia: str = ""
    linea: str = ""
    sublinea: str = ""
    cod_familia: Optional[int] = None
    cod_linea: Optional[int] = None
    cod_sublinea: Optional[int] = None
    udm: str = ""
    udm_sat: str = ""
    peso: float = 0.0
    codigo_sat: str = ""
    creado_por: str = "GENERADOR"


class GuardarResponse(BaseModel):
    ok: bool
    codigo: Optional[str] = None
    error: Optional[str] = None


class CatalogoItem(BaseModel):
    id: int
    nombre: str


class Catalogos(BaseModel):
    familias: List[CatalogoItem]
    lineas: List[CatalogoItem]
    sublineas: List[CatalogoItem]
    udms: List[str]
    udm_sat_map: dict


class CrearEntidadRequest(BaseModel):
    nombre: str
    id: Optional[int] = None


class ResultadoResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
    familia: Optional[CatalogoItem] = None
    linea: Optional[CatalogoItem] = None
    sublinea: Optional[CatalogoItem] = None


# -------------------------------- Endpoints --------------------------------- #
@app.get("/api/catalogos", response_model=Catalogos)
def catalogos():
    return {
        "familias": catalog.catalogos["familia"],
        "lineas": catalog.catalogos["linea"],
        "sublineas": catalog.catalogos["sublinea"],
        "udms": catalog.udms,
        "udm_sat_map": UDM_SAT,
    }


@app.post("/api/generar", response_model=GenerarResponse)
def generar(req: GenerarRequest):
    return catalog.datos_alta(req.descripcion)


@app.post("/api/guardar", response_model=GuardarResponse)
def guardar(req: GuardarRequest):
    return catalog.guardar(req.model_dump())


@app.post("/api/crear-familia", response_model=ResultadoResponse)
def crear_familia(req: CrearEntidadRequest):
    return catalog.agregar_familia(req.nombre, req.id)


@app.post("/api/crear-linea", response_model=ResultadoResponse)
def crear_linea(req: CrearEntidadRequest):
    return catalog.agregar_linea(req.nombre, req.id)


@app.post("/api/crear-sublinea", response_model=ResultadoResponse)
def crear_sublinea(req: CrearEntidadRequest):
    return catalog.agregar_sublinea(req.nombre, req.id)


# En producción, el build de React se copia a ./static y se sirve en /
STATIC = Path(__file__).resolve().parent / "static"
if STATIC.is_dir():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="frontend")
