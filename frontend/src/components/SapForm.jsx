// SapForm — datos para dar de alta en SAP; todos los campos son editables.
// Familia / Línea / Sublínea son <select> del catálogo canónico ("ID — Nombre",
// el value es el ID); junto a cada uno el ID queda a un click de copiarse, que
// es lo que se captura en SAP. Al cambiar UDM se recalcula UDM SAT con el mapa
// determinístico.
export default function SapForm({ form, onChange, catalogos }) {
  const set = (campo) => (e) => onChange({ ...form, [campo]: e.target.value })

  const setUdm = (e) => {
    const udm = e.target.value
    const udmSat = (catalogos.udm_sat_map || {})[udm] || form.udm_sat
    onChange({ ...form, udm, udm_sat: udmSat })
  }

  const copiarId = (id) => {
    if (id !== '' && id != null) navigator.clipboard.writeText(String(id))
  }

  const selectCatalogo = (campoId, campoNombre, items) => {
    const actual = form[campoId] ?? ''
    const enLista = items.some((it) => String(it.id) === String(actual))
    const onSel = (e) => {
      const item = items.find((it) => String(it.id) === e.target.value)
      onChange({
        ...form,
        [campoId]: item ? item.id : '',
        [campoNombre]: item ? item.nombre : '',
      })
    }
    return (
      <div className="campo-id">
        <select value={actual} onChange={onSel}>
          {!enLista && (
            <option value={actual}>{form[campoNombre] || '—'}</option>
          )}
          {items.map((it) => (
            <option key={it.id} value={it.id}>
              {it.id} — {it.nombre}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn-id mono"
          title="Copiar ID (lo que se captura en SAP)"
          onClick={() => copiarId(actual)}
          disabled={actual === ''}
        >
          {actual === '' ? '—' : actual} ⧉
        </button>
      </div>
    )
  }

  const selectUdm = (
    <select value={form.udm} onChange={setUdm}>
      {!(catalogos.udms || []).includes(form.udm) && (
        <option value={form.udm}>{form.udm || '—'}</option>
      )}
      {(catalogos.udms || []).map((v) => (
        <option key={v} value={v}>{v}</option>
      ))}
    </select>
  )

  return (
    <section className="card">
      <div className="card-head">
        <h2>Datos para dar de alta en SAP</h2>
      </div>
      <div className="grid-form">
        <label>
          <span>Código</span>
          <input
            className="mono"
            value={form.codigo}
            onChange={set('codigo')}
            spellCheck={false}
          />
        </label>
        <label>
          <span>Familia</span>
          {selectCatalogo('cod_familia', 'familia', catalogos.familias || [])}
        </label>
        <label>
          <span>Línea</span>
          {selectCatalogo('cod_linea', 'linea', catalogos.lineas || [])}
        </label>
        <label>
          <span>Sublínea</span>
          {selectCatalogo('cod_sublinea', 'sublinea', catalogos.sublineas || [])}
        </label>
        <label>
          <span>Código SAP (SAT)</span>
          <input className="mono" value={form.codigo_sat} onChange={set('codigo_sat')} />
        </label>
        <label>
          <span>UDM</span>
          {selectUdm}
        </label>
        <label>
          <span>UDM SAT</span>
          <input className="mono" value={form.udm_sat} onChange={set('udm_sat')} />
        </label>
        <label>
          <span>Peso (KG)</span>
          <input type="number" step="any" value={form.peso} onChange={set('peso')} />
        </label>
      </div>
    </section>
  )
}
