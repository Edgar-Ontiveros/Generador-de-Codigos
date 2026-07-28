# Generador de códigos de artículos · Herinox

Herramienta **externa** (sin conexión a SAP ni a la BD de la empresa) que, dada la
descripción de un artículo nuevo, genera todo lo necesario para darlo de alta en SAP:
código único, familia / línea / sublínea **con sus IDs de SAP**, código SAP (SAT),
UDM y UDM SAT, y peso. Todo se infiere de los artículos más similares del export
histórico de SAP; cada alta se guarda en SQLite.

## Stack

- **Backend**: Python 3.11 + FastAPI (uvicorn), scikit-learn, rapidfuzz, pandas, openpyxl
- **Base de datos**: SQLite (`data/catalogo.db`, generada desde el export de SAP)
- **Frontend**: React + Vite (JavaScript), CSS propio con design tokens
- **Empaquetado**: Docker multi-stage + docker-compose para desarrollo

## Fuente de datos

El export de SAP vive en `data/BASE_DE_DATOS.xlsx` (hoja `Hoja1`, encabezado en la
fila 1). De ahí salen la tabla `articulos` y el **catálogo canónico**
(`catalogo_familia`, `catalogo_linea`, `catalogo_sublinea`: pares ID–nombre).
El peso no viene en el export: se lee de la descripción (`(98.02 KG/PZ)`).

`build_db.py` es **re-ejecutable sin perder altas**: al reconstruir se preservan
las filas creadas desde la app (`creado_por='GENERADOR'`) cuyo código aún no
aparece en el export; cuando el código ya viene en el export gana la versión del
export (SAP es la fuente de verdad). Las familias/líneas/sublíneas creadas desde
el panel admin también se conservan mientras no choquen con el export.

## Puesta en marcha (desarrollo local)

1. Coloca el export de SAP en `data/BASE_DE_DATOS.xlsx` (hoja `Hoja1`).
2. Backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   python build_db.py          # Excel -> ../data/catalogo.db
   uvicorn main:app --reload --port 8000
   ```
3. Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev                 # http://localhost:5173 (proxy /api -> 8000)
   ```

La ruta de la base puede sobreescribirse con la variable de entorno `CATALOGO_DB`.

## Docker (producción: AWS EC2 + volumen EBS)

```bash
# Un solo contenedor (API + frontend estático en el puerto 8000)
docker build -t generador-codigos .
docker run -p 8000:8000 -v ./data:/app/data generador-codigos

# Entorno de desarrollo (api en 8000 con reload + vite en 5173)
docker compose up
```

Monta `-v ./data:/app/data` (el volumen EBS): ahí viven el export **y**
`catalogo.db`, así las altas sobreviven a los redeploys. En cada arranque se
re-ejecuta `build_db.py` (refresca el export preservando las altas locales).
**No** agregar contenedor de base de datos (SQLite es una librería sobre un
archivo) ni replicar el backend (el catálogo vive en memoria y el índice se
reconstruye al guardar; dos réplicas se desincronizarían).

## API

- `GET /api/catalogos` — `{familias|lineas|sublineas: [{id, nombre}], udms, udm_sat_map}`
- `POST /api/generar` — `{ "descripcion": "..." }` → código, estado
  (`nuevo | duplicado | revisar`), clasificación con IDs
  (`cod_familia/cod_linea/cod_sublinea`), peso, confianza y similares
- `POST /api/guardar` — da de alta el artículo con nombres e IDs (rechaza códigos existentes)
- `POST /api/crear-familia|crear-linea|crear-sublinea` — `{ "nombre": "...", "id": opcional }`
  alta en el catálogo canónico (id autoincremental si no se indica)

## Cómo funciona el matching

Antes de comparar, cada descripción se reduce a su **signature** (tipo + material +
grado + acabado, sin medidas ni peso). La similitud combina dos TF-IDF sobre las
signatures (word 1-2 y char_wb 3-5) y desempata por cercanía dimensional. La
clasificación sale de la moda ponderada de los vecinos y, si el producto ya existe
en el registro, de **todas** sus filas (reproduce lo que dice la mayoría en SAP);
los IDs se resuelven desde el nombre con el catálogo canónico, para que ID y
nombre nunca se descuadren.

## Generación de código: dos modos

- **Activos** (familia `Artículos`: laptops, mobiliario, maquinaria; sin línea ni
  sublínea): `[PREFIJO ALFABETICO][CONSECUTIVO]`. Se toma el prefijo del similar
  más cercano y el consecutivo siguiente (`EQCOADM77` → `EQCOADM78`). Es
  determinístico y siempre `nuevo`.
- **Productos de acero** (el resto): prefijo estable + cola de medidas + sufijo de
  variante. El prefijo se deriva del similar más cercano de la misma signature
  quitándole su propia cola (exacto y auto-validado); si no se puede reproducir,
  se usa un prefijo por mayoría (`majority_prefix`) y el resultado queda en
  `revisar` para validarse con el similar a la vista. El duplicado se detecta por
  producto + medida (signature + medidas), no comparando la cadena del código.

## Nota de alcance

La clasificación (familia/línea/sublínea/SAT/UDM/UDM SAT) y el peso son automáticos y
confiables, y reproducen lo que dice SAP (si un dato está mal en SAP, se corrige en
SAP, no aquí). El tramo numérico del código en productos de acero puede requerir
validación: la codificación histórica es inconsistente entre familias, por eso el
campo es editable y existe el estado `revisar`.
