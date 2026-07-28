"""
core.py — Lógica central del generador de códigos (clase Catalog).

Matching por PRODUCTO: antes de comparar, la descripción se reduce a su
"signature" (tipo + material + grado + acabado, sin medidas ni peso). La
similitud se calcula con dos TF-IDF sobre las signatures (word y char_wb) y
se desempata por cercanía dimensional, de modo que los similares sean del
mismo producto y de la medida más cercana.

Generación de código en dos modos, según la familia clasificada:
  - Activos (familia "Artículos"): [PREFIJO ALFABETICO][CONSECUTIVO], p. ej.
    EQCOADM76 -> EQCOADM77. Determinístico, sin huecos en el registro.
  - Productos de acero (el resto): prefijo por signature + cola de medidas +
    sufijo de variante, anclado al vecino más cercano con auto-validación.
"""

import os
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_DEFAULT = Path(
    os.environ.get("CATALOGO_DB")
    or Path(__file__).resolve().parent.parent / "data" / "catalogo.db"
)

# Mapa determinístico UDM -> UDM SAT (verificado contra el registro)
UDM_SAT = {
    "KILOGRAMO": "KGM",
    "PIEZA": "H87",
    "METRO CUADRADO": "MTK",
    "METRO LINEAL": "LM",
    "METRO CUBICO": "MTQ",
    "SERVICIO": "E48",
}

# Fracciones de pulgada -> 2 dígitos, para el tramo numérico del código
FRACCIONES = {0.0: "00", 0.5: "12", 0.25: "14", 0.75: "34",
              0.125: "18", 0.375: "38", 0.625: "58", 0.875: "78"}

ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def strip_accents(s):
    """Quita acentos con descomposición NFKD."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)
    )


def norm_text(s):
    """Normaliza: sin acentos, mayúsculas, espacios colapsados."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", strip_accents(s).upper()).strip()


def signature(s):
    """Reduce la descripción a tipo + material + grado + acabado.

    Quita medidas físicas (pulgadas, pies, metros, peso entre paréntesis) y
    conserva grados (304, 316L, 4140, A-36...) y calibre/cédula, que son los
    que discriminan el producto.
    """
    t = strip_accents(s).upper().replace("''", '"')
    t = re.sub(r"\([^)]*\)", " ", t)                  # (peso)
    t = re.sub(r"[\d.]+\s*LBS?\s*/?\s*FT", " ", t)    # 11.5 LBS/FT
    t = re.sub(r"\d+\s*'", " ", t)                    # pies 20'
    t = re.sub(r'\d+\s+\d+\s*/\s*\d+\s*"?', " ", t)   # 1 1/2"
    t = re.sub(r'\d+\s*/\s*\d+\s*"?', " ", t)         # 3/4"
    t = re.sub(r'\d+(?:\.\d+)?\s*"', " ", t)          # 4"  0.175" (requiere comilla)
    t = re.sub(r"\b\d+\s*M\b", " ", t)                # 8 M
    t = re.sub(r"\b(DE|X|A)\b", " ", t)               # conectores
    t = re.sub(r"[^A-Z0-9/]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_peso(descripcion):
    """Lee el peso en KG que trae la descripción entre paréntesis (no se calcula)."""
    m = re.search(r"\(\s*([\d.,]+)\s*KG", strip_accents(descripcion).upper())
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_medidas(descripcion):
    """Extrae las medidas en el orden de la descripción.

    Devuelve una lista de tuplas ("in", valor) / ("ft", valor). Reconoce
    fracciones (1 1/2", 3/4"), decimales (0.175") y enteros, con " para
    pulgadas y ' para pies. Ignora lo que va entre paréntesis (el peso).
    """
    t = strip_accents(descripcion).upper().replace("''", '"')
    t = re.sub(r"\([^)]*\)", " ", t)
    medidas = []
    patron = re.compile(
        r"(?:(\d+)\s+)?(\d+)\s*/\s*(\d+)\s*\"|"   # [entero] num/den "
        r"(\d+(?:\.\d+)?)\s*\"|"                    # decimal o entero "
        r"(\d+(?:\.\d+)?)\s*'"                      # pies '
    )
    for m in patron.finditer(t):
        if m.group(2):  # fracción, con entero opcional
            entero = int(m.group(1)) if m.group(1) else 0
            medidas.append(("in", entero + int(m.group(2)) / int(m.group(3))))
        elif m.group(4):
            medidas.append(("in", float(m.group(4))))
        else:
            medidas.append(("ft", float(m.group(5))))
    return medidas


def dist_medidas(a, b):
    """Distancia entre dos listas de medidas: menor = dimensiones más cercanas."""
    d = abs(len(a) - len(b)) * 50.0
    for (ua, va), (ub, vb) in zip(a, b):
        d += abs(va - vb) if ua == ub else 100.0 + abs(va - vb)
    return d


def enc_pulg(x):
    """Codifica pulgadas como [entero][fracción 2 dígitos].

    Verificado: 1/2" -> "012", 1" -> "100", 1 1/2" -> "112", 10" -> "1000".
    """
    entero = int(x)
    frac = round(x - entero, 4)
    if frac not in FRACCIONES:
        # Fracción atípica: se aproxima al octavo más cercano
        frac = min(FRACCIONES, key=lambda f: abs(f - frac))
    return f"{entero}{FRACCIONES[frac]}"


def encode_medidas(descripcion):
    """Cola del código: dimensiones en el orden de la descripción.

    Pulgadas con enc_pulg ([entero][fracción 2 dígitos]); pies a 2 dígitos con
    cero a la izquierda (20' -> "20", 4' -> "04", 4' X 10' -> "0410"). El
    calibre/cédula NO va aquí: ya viene en el prefijo.
    """
    partes = []
    for unidad, valor in parse_medidas(descripcion):
        if unidad == "in":
            partes.append(enc_pulg(valor))
        else:
            partes.append(f"{int(valor):02d}")
    return "".join(partes)


def sufijo_variante(descripcion):
    """Sufijo de variante detectado en la descripción.

    REC = recortes, RL = radio largo, SP = skin pass, CD/CS = tipo de malla.
    """
    t = " " + norm_text(descripcion).replace(".", " ") + " "
    t = re.sub(r"\s+", " ", t)
    if re.search(r"\bRECORTES?\b|\bREC\b", t):
        return "REC"
    if re.search(r"\bRADIO LARGO\b|\bRL\b|\bR L\b", t):
        return "RL"
    if re.search(r"\bSKIN PASS\b|\bSP\b", t):
        return "SP"
    if re.search(r"\bCD\b", t):
        return "CD"
    if re.search(r"\bCS\b", t):
        return "CS"
    return ""


def _calibre(sig):
    """Número de calibre/cédula dentro de una signature ("CAL 16" / "CED 40")."""
    m = re.search(r"\b(?:CAL|CED)\s*(\d+)\b", sig)
    return m.group(1) if m else ""


def _sig_sin_calibre(sig):
    """Signature sin el bloque de calibre/cédula, para comparar productos."""
    return re.sub(r"\s+", " ", re.sub(r"\b(?:CAL|CED)\s*\d+\b", " ", sig)).strip()


def _moda_ponderada(pares):
    """Moda ponderada por score de una lista de (valor, peso); ignora vacíos."""
    acumulado = defaultdict(float)
    for valor, peso in pares:
        if valor:
            acumulado[valor] += peso
    if not acumulado:
        return "", 0.0
    ganador = max(acumulado, key=acumulado.get)
    return ganador, acumulado[ganador] / sum(acumulado.values())


def majority_prefix(codes, share=0.6, mx=20):
    """Prefijo compartido por la mayoría (share) de los códigos, el más largo primero.

    A diferencia de os.path.commonprefix (intersección), un solo código con otra
    convención no arruina el prefijo del grupo. OJO: puede extenderse de más y
    comerse dígitos de la medida; por eso es respaldo (estado "revisar"), no la
    vía principal.
    """
    codes = [c for c in codes if c]
    if not codes:
        return ""
    up = min(mx, max(len(c) for c in codes))
    for L in range(up, 0, -1):
        prefs = [c[:L] for c in codes if len(c) >= L]
        if not prefs:
            continue
        top, cnt = Counter(prefs).most_common(1)[0]
        if cnt / len(codes) >= share:
            return top
    return ""


class Catalog:
    """Catálogo en memoria: similares, clasificación y generación de códigos."""

    def __init__(self, db=DB_DEFAULT):
        self.db_path = str(db)
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        self.articulos = [dict(r) for r in con.execute(
            "SELECT codigo, descripcion, cod_familia, familia, cod_linea, linea, "
            "cod_sublinea, sublinea, udm, udm_sat, peso, codigo_sat FROM articulos"
        )]
        # Catálogo canónico (id, nombre) de SAP: manda sobre lo que digan las filas
        self.catalogos = {}
        self.id_por_nombre = {}
        for tipo in ("familia", "linea", "sublinea"):
            items = [
                {"id": r["id"], "nombre": r["nombre"]}
                for r in con.execute(f"SELECT id, nombre FROM catalogo_{tipo}")
            ]
            items.sort(key=lambda c: c["nombre"])
            self.catalogos[tipo] = items
            self.id_por_nombre[tipo] = {c["nombre"]: c["id"] for c in items}
        con.close()

        for art in self.articulos:
            for campo in ("descripcion", "familia", "linea", "sublinea",
                          "udm", "udm_sat", "codigo_sat"):
                art[campo] = art[campo] or ""
            art["signature"] = signature(art["descripcion"])
            art["medidas"] = parse_medidas(art["descripcion"])

        self.codes = {a["codigo"] for a in self.articulos}
        self.udms = sorted({a["udm"] for a in self.articulos if a["udm"]})
        self._fit()

    def _fit(self):
        """Entrena los dos TF-IDF (word 1-2 y char_wb 3-5) sobre las signatures."""
        corpus = [a["signature"] or " " for a in self.articulos]
        self.vec_word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2))
        self.vec_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        self.mat_word = self.vec_word.fit_transform(corpus)
        self.mat_char = self.vec_char.fit_transform(corpus)

    # ------------------------------------------------------------------ #
    def similares(self, descripcion, k=8):
        """Top-k de artículos del mismo producto, la medida más cercana primero."""
        firma = signature(descripcion) or " "
        sim = (
            0.6 * cosine_similarity(self.vec_word.transform([firma]), self.mat_word)[0]
            + 0.4 * cosine_similarity(self.vec_char.transform([firma]), self.mat_char)[0]
        )
        # Candidatos con mayor similitud de signature (mismo producto)
        n_cand = min(len(sim), max(40, k * 5))
        candidatos = sim.argsort()[::-1][:n_cand]
        medidas_q = parse_medidas(descripcion)
        # Empates de signature se resuelven por cercanía dimensional
        orden = sorted(
            candidatos,
            key=lambda i: (
                -round(float(sim[i]), 3),
                dist_medidas(medidas_q, self.articulos[i]["medidas"]),
            ),
        )
        out = []
        for i in orden[:k]:
            a = self.articulos[i]
            out.append({
                "score": round(float(sim[i]), 4),
                "codigo": a["codigo"],
                "descripcion": a["descripcion"],
                "familia": a["familia"],
                "linea": a["linea"],
                "sublinea": a["sublinea"],
                "cod_sublinea": a["cod_sublinea"],
                "codigo_sat": a["codigo_sat"],
                "udm": a["udm"],
            })
        return out

    def _ids_de_nombres(self, res):
        """IDs resueltos DESDE los nombres elegidos, para que nunca se descuadren."""
        return {
            "cod_familia": self.id_por_nombre["familia"].get(res.get("familia", "")),
            "cod_linea": self.id_por_nombre["linea"].get(res.get("linea", "")),
            "cod_sublinea": self.id_por_nombre["sublinea"].get(res.get("sublinea", "")),
        }

    def clasificar(self, descripcion, topn=8):
        """Clasificación por moda ponderada por score de los vecinos con score>=0.5.

        Si el producto YA está en el registro (misma signature), la moda se toma
        sobre TODAS sus filas y no solo sobre la ventana top-k: así un subgrupo
        mal clasificado en SAP no gana por quedar dimensionalmente más cerca, y
        el programa reproduce lo que dice la mayoría del registro.
        """
        sims = self.similares(descripcion, k=topn)
        firma = signature(descripcion)
        exactos = [a for a in self.articulos if a["signature"] == firma] if firma else []
        if exactos:
            res, conf = {}, {}
            for campo in ("familia", "linea", "sublinea", "codigo_sat", "udm"):
                res[campo], conf[campo] = _moda_ponderada(
                    [(a[campo], 1.0) for a in exactos]
                )
            udm_sat = UDM_SAT.get(res["udm"], "")
            if not udm_sat:
                udm_sat, _ = _moda_ponderada([(a["udm_sat"], 1.0) for a in exactos])
            return {
                **res, "udm_sat": udm_sat, "confianza": round(conf["sublinea"], 3),
                **self._ids_de_nombres(res), "similares": sims,
            }
        vecinos = [s for s in sims if s["score"] >= 0.5]
        if not vecinos:
            return {
                "familia": "", "linea": "", "sublinea": "", "codigo_sat": "",
                "udm": "", "udm_sat": "", "confianza": 0.0,
                "cod_familia": None, "cod_linea": None, "cod_sublinea": None,
                "similares": sims,
            }
        res, conf = {}, {}
        for campo in ("familia", "linea", "sublinea", "codigo_sat", "udm"):
            res[campo], conf[campo] = _moda_ponderada(
                [(v[campo], v["score"]) for v in vecinos]
            )
        # UDM SAT: determinístico desde UDM; fallback, moda de los similares
        udm_sat = UDM_SAT.get(res["udm"], "")
        if not udm_sat:
            arts = {a["codigo"]: a for a in self.articulos}
            udm_sat, _ = _moda_ponderada(
                [(arts[v["codigo"]]["udm_sat"], v["score"]) for v in vecinos]
            )
        # Confianza: qué tan de acuerdo están los vecinos, pesado por su cercanía
        confianza = round(conf["sublinea"] * vecinos[0]["score"], 3)
        return {
            **res, "udm_sat": udm_sat, "confianza": confianza,
            **self._ids_de_nombres(res), "similares": sims,
        }

    # ------------------------------------------------------------------ #
    def _codigo_activo(self, similares):
        """MODO A — activos: [prefijo alfabético del vecino][consecutivo siguiente].

        Verificado en el registro: 969/981 activos cumplen ^[A-Z]+\\d+$ y los
        consecutivos no tienen huecos (EQCOADM 1..77, MOBMAT 1..65).
        """
        m = re.fullmatch(r"([A-Z]+)(\d+)", similares[0]["codigo"])
        if not m:
            return "", "revisar"
        prefijo = m.group(1)
        patron = re.compile(re.escape(prefijo) + r"(\d+)$")
        ultimo = max(
            (int(mc.group(1)) for c in self.codes if (mc := patron.fullmatch(c))),
            default=0,
        )
        return f"{prefijo}{ultimo + 1}", "nuevo"

    @staticmethod
    def _prefijo_sin_cola(similar):
        """Prefijo del similar quitándole SU propia cola, si es reproducible.

        Es la vía principal (exacta y auto-validada): si el encoder reproduce la
        cola del código del vecino, lo que queda es el prefijo estable.
        """
        cola = encode_medidas(similar["descripcion"]) + sufijo_variante(
            similar["descripcion"]
        )
        if cola and similar["codigo"].endswith(cola):
            return similar["codigo"][: -len(cola)]
        return None

    def generar_codigo(self, descripcion, similares, familia=""):
        """Código COMPLETO según el modo (activos o productos de acero).

        El duplicado se detecta por producto + medida (misma signature y mismas
        medidas), no comparando la cadena del código: la codificación histórica
        es inconsistente.
        """
        firma = signature(descripcion)
        medidas = parse_medidas(descripcion)

        # 1. Duplicado por producto + medida: se devuelve el código REAL existente
        for art in self.articulos:
            if art["signature"] == firma and art["medidas"] == medidas:
                return art["codigo"], "duplicado"

        if not similares:
            return "", "revisar"

        # MODO A — activos (familia "Artículos"): prefijo alfabético + consecutivo
        if norm_text(familia) == "ARTICULOS":
            return self._codigo_activo(similares)

        # MODO B — productos de acero: prefijo por signature + cola + sufijo
        estado = "nuevo"
        prefijo = None
        grupo = [s for s in similares if signature(s["descripcion"]) == firma]

        # 2a. Vía principal: al similar más cercano de la MISMA signature se le
        #     quita su propia cola (auto-validado, inmune a códigos con otra
        #     convención dentro del grupo). SOLO el más cercano: probar todo el
        #     grupo produce falsos positivos cuando la cola de un vecino lejano
        #     coincide con los dígitos de peso de su código viejo
        if grupo:
            prefijo = self._prefijo_sin_cola(grupo[0])

        # 2b. Mismo producto con distinto calibre/cédula: se toma el prefijo del
        #     vecino y se sustituye su bloque de calibre por el solicitado
        if prefijo is None:
            cal_q = _calibre(firma)
            if cal_q:
                for s in similares:
                    sig_s = signature(s["descripcion"])
                    cal_s = _calibre(sig_s)
                    if not cal_s or _sig_sin_calibre(sig_s) != _sig_sin_calibre(firma):
                        continue
                    base = self._prefijo_sin_cola(s)
                    if base is None:
                        continue
                    idx = base.rfind(cal_s)
                    if idx > 0:
                        prefijo = base[:idx] + cal_q + base[idx + len(cal_s):]
                        break

        # 2c. Respaldo: prefijo por mayoría (puede extenderse de más, por eso
        #     el usuario valida con el similar a la vista)
        if prefijo is None:
            estado = "revisar"
            prefijo = majority_prefix([s["codigo"] for s in (grupo or similares)])
            if not prefijo:
                prefijo = similares[0]["codigo"]

        # 3. Cola (dimensiones + largo) y sufijo de variante
        cola = encode_medidas(descripcion)
        if not cola:
            estado = "revisar"
        codigo = prefijo + cola + sufijo_variante(descripcion)

        # 4. Completo: si quedó más corto que el similar más cercano, algo faltó
        if estado == "nuevo" and len(codigo) < len(similares[0]["codigo"]):
            estado = "revisar"

        # 5. Unicidad obligatoria: sufijos A..Z y luego AA..ZZ; con todo agotado
        #    (702 colisiones) se devuelve la base a revisión manual
        if codigo in self.codes:
            base = codigo
            sufijos = (a + b for a in [""] + list(ALFABETO) for b in ALFABETO)
            codigo = next(
                (base + s for s in sufijos if base + s not in self.codes), None
            )
            if codigo is None:
                return base, "revisar"
        return codigo, estado

    def datos_alta(self, descripcion):
        """Junta clasificación, peso y código: el objeto completo para SAP."""
        clas = self.clasificar(descripcion)
        codigo, estado = self.generar_codigo(
            descripcion, clas["similares"], clas["familia"]
        )
        peso = parse_peso(descripcion)
        return {
            "codigo": codigo,
            "estado": estado,
            "familia": clas["familia"],
            "linea": clas["linea"],
            "sublinea": clas["sublinea"],
            "cod_familia": clas["cod_familia"],
            "cod_linea": clas["cod_linea"],
            "cod_sublinea": clas["cod_sublinea"],
            "codigo_sat": clas["codigo_sat"],
            "udm": clas["udm"],
            "udm_sat": clas["udm_sat"],
            "peso": peso if peso is not None else 0.0,
            "confianza": clas["confianza"],
            "similares": clas["similares"],
        }

    # ------------------------------------------------------------------ #
    @staticmethod
    def _id_entero(v):
        """ID entero o None; nunca cadenas tipo '224.0' ni 'nan'."""
        if v in (None, ""):
            return None
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    def guardar(self, payload):
        """Da de alta el artículo en SQLite; rechaza códigos ya existentes."""
        codigo = str(payload["codigo"]).strip()
        if not codigo:
            return {"ok": False, "error": "el codigo es obligatorio"}
        if codigo in self.codes:
            return {"ok": False, "error": "el codigo ya existe"}
        descripcion = str(payload.get("articulo", "")).strip()
        fila = {
            "codigo": codigo,
            "descripcion": descripcion,
            "desc_norm": norm_text(descripcion),
            "familia": str(payload.get("familia", "") or "").strip(),
            "linea": str(payload.get("linea", "") or "").strip(),
            "sublinea": str(payload.get("sublinea", "") or "").strip(),
            "udm": str(payload.get("udm", "") or "").strip(),
            "udm_sat": str(payload.get("udm_sat", "") or "").strip(),
            "peso": float(payload.get("peso") or 0),
            "codigo_sat": str(payload.get("codigo_sat", "") or "").strip(),
            "creado_por": str(payload.get("creado_por") or "GENERADOR").strip(),
        }
        # IDs: los enviados por la UI o, en su defecto, resueltos desde el nombre
        for campo, tipo in (("cod_familia", "familia"), ("cod_linea", "linea"),
                            ("cod_sublinea", "sublinea")):
            fila[campo] = self._id_entero(payload.get(campo))
            if fila[campo] is None:
                fila[campo] = self.id_por_nombre[tipo].get(fila[tipo])
        con = sqlite3.connect(self.db_path)
        con.execute(
            "INSERT INTO articulos VALUES (:codigo,:descripcion,:desc_norm,"
            ":cod_familia,:familia,:cod_linea,:linea,:cod_sublinea,:sublinea,"
            ":udm,:udm_sat,:peso,:codigo_sat,:creado_por)",
            fila,
        )
        con.commit()
        con.close()
        # Se incorpora al catálogo en memoria para las siguientes consultas
        art = {k: fila[k] for k in (
            "codigo", "descripcion", "cod_familia", "familia", "cod_linea", "linea",
            "cod_sublinea", "sublinea", "udm", "udm_sat", "peso", "codigo_sat",
        )}
        art["signature"] = signature(descripcion)
        art["medidas"] = parse_medidas(descripcion)
        self.articulos.append(art)
        self.codes.add(codigo)
        self._fit()
        return {"ok": True, "codigo": codigo}

    # ------------------------------------------------------------------ #
    def _agregar_catalogo(self, tipo, nombre, id=None):
        """Alta en catalogo_<tipo>: id autoincremental o el indicado."""
        nombre = str(nombre or "").strip()
        if not nombre:
            return {"ok": False, "error": "nombre requerido"}
        if nombre in self.id_por_nombre[tipo]:
            return {"ok": False, "error": f"{tipo} '{nombre}' ya existe"}
        con = sqlite3.connect(self.db_path)
        try:
            if id is None:
                cur = con.execute(
                    f"INSERT INTO catalogo_{tipo} (nombre) VALUES (?)", (nombre,)
                )
                nuevo_id = cur.lastrowid
            else:
                nuevo_id = int(id)
                con.execute(
                    f"INSERT INTO catalogo_{tipo} (id, nombre) VALUES (?, ?)",
                    (nuevo_id, nombre),
                )
            con.commit()
        except sqlite3.IntegrityError:
            return {"ok": False, "error": f"el id {id} ya existe en {tipo}"}
        finally:
            con.close()
        item = {"id": nuevo_id, "nombre": nombre}
        self.catalogos[tipo].append(item)
        self.catalogos[tipo].sort(key=lambda c: c["nombre"])
        self.id_por_nombre[tipo][nombre] = nuevo_id
        return {"ok": True, tipo: item}

    def agregar_familia(self, nombre, id=None):
        return self._agregar_catalogo("familia", nombre, id)

    def agregar_linea(self, nombre, id=None):
        return self._agregar_catalogo("linea", nombre, id)

    def agregar_sublinea(self, nombre, id=None):
        return self._agregar_catalogo("sublinea", nombre, id)
