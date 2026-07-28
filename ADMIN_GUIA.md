# Guía de Administración del Catálogo

## Panel de Administración

Puedes crear nuevas familias, líneas y sublíneas directamente desde la interfaz web
**sin necesidad de tocar el export de SAP**. Los elementos se guardan en el
**catálogo canónico** (tablas `catalogo_familia`, `catalogo_linea`,
`catalogo_sublinea` de `data/catalogo.db`), cada uno con su **ID**, que es lo que
se captura en SAP.

### Acceso

1. Abre la aplicación en **http://localhost:8010/**
2. En la esquina inferior derecha, encontrarás un botón flotante **⚙️ Admin**
3. Haz clic para abrir el panel de administración

### Crear una Familia / Línea / Sublínea

1. Elige la pestaña correspondiente
2. Ingresa el nombre (ej: `LAMINA INOX. 304 BA`)
3. (Opcional) Indica el **ID de SAP**; si lo dejas vacío se asigna uno automático
4. Haz clic en **"Crear"**: el elemento aparece de inmediato en los selectores de
   la aplicación como `ID — Nombre`

## Validaciones

- ✅ No puedes dejar el nombre vacío
- ✅ No puedes crear un nombre que ya existe, ni repetir un ID
- ✅ Los cambios se guardan en `data/catalogo.db` inmediatamente
- ✅ Sobreviven a los refresh del export (`build_db.py`) mientras su ID/nombre no
  choque con lo que venga de SAP (SAP es la fuente de verdad)

## API (Uso avanzado)

```bash
# ID automático
curl -X POST http://localhost:8010/api/crear-familia \
  -H "Content-Type: application/json" \
  -d '{"nombre": "NUEVA FAMILIA"}'

# Con el ID de SAP
curl -X POST http://localhost:8010/api/crear-sublinea \
  -H "Content-Type: application/json" \
  -d '{"nombre": "NUEVA SUBLINEA", "id": 300}'
```

Respuestas:
- **Éxito**: `{"ok": true, "familia": {"id": 142, "nombre": "NUEVA FAMILIA"}}`
- **Error**: `{"ok": false, "error": "descripción del error"}`

## Preguntas Frecuentes

**¿Dónde se almacenan los cambios?**
En `data/catalogo.db` (SQLite), junto al export. En producción ese directorio es el
volumen montado, así que los cambios sobreviven a los redeploys.

**¿Puedo eliminar familias/líneas/sublíneas?**
Por ahora no desde la UI. Un elemento creado por error desaparece al reconstruir la
base si le pones el mismo nombre/ID a uno del export, o puede borrarse a mano de la
tabla `catalogo_*` correspondiente.

**¿Los cambios afectan los cálculos del generador?**
Los selectores y la resolución de IDs usan el catálogo canónico de inmediato. La
clasificación automática sigue saliendo de los artículos históricos: una familia
nueva se usará automáticamente cuando existan artículos guardados con ella.
