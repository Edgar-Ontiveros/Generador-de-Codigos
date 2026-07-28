#!/bin/sh
# Backup diario consistente de catalogo.db (sqlite3 .backup, seguro con la app corriendo).
# Conserva solo los ultimos 7 dias. Corre via cron del usuario ubuntu en la instancia.
set -e
DB=/home/ubuntu/generador_codigos/data/catalogo.db
DEST=/home/ubuntu/generador_codigos/backups
mkdir -p "$DEST"
[ -f "$DB" ] || exit 0
sqlite3 "$DB" ".backup '$DEST/catalogo_$(date +%Y%m%d).db'"
find "$DEST" -name "catalogo_*.db" -mtime +7 -delete
