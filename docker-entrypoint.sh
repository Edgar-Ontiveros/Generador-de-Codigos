#!/bin/sh
# Ciclo de vida de la BD: catalogo.db vive en /app/data (volumen del host).
# - Si NO existe: se crea desde el Excel de SAP (primer arranque).
# - Si YA existe: se preserva tal cual (las altas hechas desde la app viven ahi).
# Nunca se regenera automaticamente; para refrescar el Excel de SAP ejecutar
# build_db.py a mano (preserva las altas GENERADOR).
set -e

DB=/app/data/catalogo.db
XLSX=/app/data/BASE_DE_DATOS.xlsx

if [ ! -f "$DB" ]; then
    echo "[entrypoint] $DB no existe: creandolo desde $XLSX ..."
    python build_db.py "$XLSX" "$DB"
else
    N=$(python -c "import sqlite3; print(sqlite3.connect('$DB').execute('select count(*) from articulos').fetchone()[0])")
    echo "[entrypoint] BD existente preservada: $N articulos en $DB"
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
