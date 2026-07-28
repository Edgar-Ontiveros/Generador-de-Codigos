"""
build_db.py — Convierte el export de SAP (data/BASE_DE_DATOS.xlsx, hoja Hoja1)
en catalogo.db (SQLite): tabla articulos + catálogo canónico de familias,
líneas y sublíneas (pares ID-nombre del export).

Uso:
    python build_db.py [ruta_excel] [ruta_db]

Re-ejecutable sin perder altas: al reconstruir se preservan las filas creadas
desde la app (creado_por='GENERADOR') cuyo código aún NO aparece en el export;
cuando el código ya viene en el export gana la versión del export (SAP es la
fuente de verdad). Las entradas de catálogo creadas desde el panel admin se
conservan si su id/nombre no choca con el export. Los pseudo-artículos del
panel admin antiguo (códigos _FAM_*/_LIN_*/_SUBLIN_*) se descartan siempre.
"""

import os
import sys
import sqlite3
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from core import UDM_SAT, norm_text, parse_peso  # noqa: E402

EXCEL_DEFAULT = AQUI.parent / "data" / "BASE_DE_DATOS.xlsx"
DB_DEFAULT = Path(os.environ.get("CATALOGO_DB") or AQUI.parent / "data" / "catalogo.db")

# El export trae además PESO X UDM DESCRIPCI y PES (constante 1000000): se ignoran.
# El peso real se lee de la descripción con parse_peso.
COLUMNAS = [
    "CODIGO", "ARTICULO", "COD.FAMILIA", "FAMILIA", "COD.LINEA", "LINEA",
    "COD.SUBLINEA", "SUBLINEA", "UDM", "CODIGO SAT", "UDM SAT", "CREADO POR",
]

SCHEMA = """
CREATE TABLE articulos (
    codigo       TEXT PRIMARY KEY,
    descripcion  TEXT,
    desc_norm    TEXT,
    cod_familia  INTEGER,
    familia      TEXT,
    cod_linea    INTEGER,
    linea        TEXT,
    cod_sublinea INTEGER,
    sublinea     TEXT,
    udm          TEXT,
    udm_sat      TEXT,
    peso         REAL,
    codigo_sat   TEXT,
    creado_por   TEXT
);
CREATE INDEX idx_articulos_codigo ON articulos(codigo);
CREATE TABLE catalogo_familia  (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE catalogo_linea    (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE catalogo_sublinea (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
"""


# Algunas filas del export traen el código SAT en la columna UDM: se invierte
SAT_A_UDM = {v: k for k, v in UDM_SAT.items()}


def norm_udm(v):
    """Normaliza la unidad de medida a los valores válidos del catálogo."""
    t = norm_text(v)
    if t in ("", "0", "NAN", "NONE", "<NA>"):
        return ""
    if t in ("PIEZA", "PÍEZA", "PIEZAS"):
        return "PIEZA"
    if t.startswith("KILOGR"):
        return "KILOGRAMO"
    return SAT_A_UDM.get(t, t)


def limpiar(v):
    """String limpio: sin NaN/NA, sin espacios sobrantes, sin '.0' de floats enteros."""
    if v is None or pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "<na>", "none"):
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def entero(v):
    """ID entero o None. Los COD.* llegan como float64 por los nulos (224.0)."""
    if v is None or pd.isna(v):
        return None
    return int(v)


def leer_export(ruta_excel):
    """Lee la hoja Hoja1 (encabezado en la fila 1) y tipa los IDs como Int64."""
    df = pd.read_excel(ruta_excel, sheet_name="Hoja1", header=0)
    faltantes = set(COLUMNAS) - set(df.columns)
    if faltantes:
        raise RuntimeError(f"El export no trae las columnas: {sorted(faltantes)}")
    for col in ("COD.FAMILIA", "COD.LINEA", "COD.SUBLINEA"):
        df[col] = df[col].astype("Int64")
    return df.dropna(subset=["CODIGO"])


def pares_catalogo(df, col_id, col_nombre):
    """Pares (id, nombre) distintos de una entidad; valida que el mapeo sea 1 a 1."""
    vistos = {}
    for _, r in df[[col_id, col_nombre]].dropna(subset=[col_id]).drop_duplicates().iterrows():
        i, nombre = int(r[col_id]), limpiar(r[col_nombre])
        if i in vistos and vistos[i] != nombre:
            raise RuntimeError(f"{col_id}={i} con dos nombres: '{vistos[i]}' y '{nombre}'")
        vistos[i] = nombre
    return dict(sorted(vistos.items()))


def leer_preservables(ruta_db, codigos_export):
    """Del catalogo.db anterior: altas GENERADOR aún no en el export + catálogo admin."""
    altas, catalogos = [], {"familia": {}, "linea": {}, "sublinea": {}}
    if not Path(ruta_db).exists():
        return altas, catalogos
    con = sqlite3.connect(ruta_db)
    con.row_factory = sqlite3.Row
    try:
        for r in con.execute("SELECT * FROM articulos WHERE creado_por = 'GENERADOR'"):
            d = dict(r)
            codigo = str(d.get("codigo") or "").strip()
            if codigo and not codigo.startswith("_") and codigo not in codigos_export:
                altas.append(d)
    except sqlite3.OperationalError:
        pass
    for tipo in catalogos:
        try:
            catalogos[tipo] = {
                r["id"]: r["nombre"]
                for r in con.execute(f"SELECT id, nombre FROM catalogo_{tipo}")
            }
        except sqlite3.OperationalError:
            pass
    con.close()
    return altas, catalogos


def construir(ruta_excel=EXCEL_DEFAULT, ruta_db=DB_DEFAULT):
    df = leer_export(ruta_excel)

    filas = []
    for _, r in df.iterrows():
        codigo = limpiar(r["CODIGO"])
        if not codigo:
            continue
        descripcion = limpiar(r["ARTICULO"])
        udm = norm_udm(r["UDM"])
        filas.append((
            codigo,
            descripcion,
            norm_text(descripcion),
            entero(r["COD.FAMILIA"]),
            limpiar(r["FAMILIA"]),
            entero(r["COD.LINEA"]),
            limpiar(r["LINEA"]),
            entero(r["COD.SUBLINEA"]),
            limpiar(r["SUBLINEA"]),
            udm,
            UDM_SAT.get(udm, limpiar(r["UDM SAT"])),
            parse_peso(descripcion) or 0.0,
            limpiar(r["CODIGO SAT"]),
            limpiar(r["CREADO POR"]),
        ))

    catalogos = {
        "familia": pares_catalogo(df, "COD.FAMILIA", "FAMILIA"),
        "linea": pares_catalogo(df, "COD.LINEA", "LINEA"),
        "sublinea": pares_catalogo(df, "COD.SUBLINEA", "SUBLINEA"),
    }

    codigos_export = {f[0] for f in filas}
    altas, cat_previos = leer_preservables(ruta_db, codigos_export)

    # Altas locales que sobreviven al refresh: se re-insertan con el esquema nuevo,
    # resolviendo los IDs desde el catálogo canónico si la fila vieja no los traía.
    for d in altas:
        filas.append((
            d["codigo"],
            d.get("descripcion") or "",
            d.get("desc_norm") or norm_text(d.get("descripcion")),
            entero(d.get("cod_familia")) or _id_por_nombre(catalogos["familia"], d.get("familia")),
            d.get("familia") or "",
            entero(d.get("cod_linea")) or _id_por_nombre(catalogos["linea"], d.get("linea")),
            d.get("linea") or "",
            entero(d.get("cod_sublinea")) or _id_por_nombre(catalogos["sublinea"], d.get("sublinea")),
            d.get("sublinea") or "",
            d.get("udm") or "",
            d.get("udm_sat") or "",
            float(d.get("peso") or 0.0),
            d.get("codigo_sat") or "",
            "GENERADOR",
        ))

    # Entradas de catálogo creadas desde el panel admin: se conservan mientras
    # ni su id ni su nombre choquen con el export.
    for tipo, previos in cat_previos.items():
        nombres_export = set(catalogos[tipo].values())
        for i, nombre in previos.items():
            if i not in catalogos[tipo] and nombre not in nombres_export:
                catalogos[tipo][i] = nombre

    ruta_db = Path(ruta_db)
    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    if ruta_db.exists():
        ruta_db.unlink()
    con = sqlite3.connect(ruta_db)
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT OR IGNORE INTO articulos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", filas
    )
    for tipo, pares in catalogos.items():
        con.executemany(
            f"INSERT INTO catalogo_{tipo} (id, nombre) VALUES (?, ?)",
            sorted(pares.items()),
        )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM articulos").fetchone()[0]
    con.close()
    print(
        f"catalogo.db generado: {n} artículos "
        f"({len(altas)} altas locales preservadas), catálogo "
        f"{len(catalogos['familia'])} familias / {len(catalogos['linea'])} líneas / "
        f"{len(catalogos['sublinea'])} sublíneas ({ruta_db})"
    )


def _id_por_nombre(pares, nombre):
    """ID cuyo nombre coincide (para completar altas viejas sin IDs)."""
    nombre = (nombre or "").strip()
    for i, n in pares.items():
        if n == nombre:
            return i
    return None


if __name__ == "__main__":
    excel = sys.argv[1] if len(sys.argv) > 1 else EXCEL_DEFAULT
    db = sys.argv[2] if len(sys.argv) > 2 else DB_DEFAULT
    construir(excel, db)
