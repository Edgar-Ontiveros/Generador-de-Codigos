// AdminPanel — alta de familias/líneas/sublíneas en el catálogo canónico.
// Escribe en las tablas catalogo_* (id autoincremental, o el ID de SAP si se
// indica); el nuevo elemento aparece de inmediato en los selectores.
import { useState } from 'react'
import { crearFamilia, crearLinea, crearSublinea } from '../api'

const TABS = [
  { clave: 'familia', titulo: 'Familia', placeholder: 'Ej: ACEROS INOXIDABLES' },
  { clave: 'linea', titulo: 'Línea', placeholder: 'Ej: LAMINADO EN FRIO' },
  { clave: 'sublinea', titulo: 'Sublínea', placeholder: 'Ej: LAMINA INOX. 304 BA' },
]

const CREAR = { familia: crearFamilia, linea: crearLinea, sublinea: crearSublinea }
const LISTA = { familia: 'familias', linea: 'lineas', sublinea: 'sublineas' }

export default function AdminPanel({ catalogos, onActualizar }) {
  const [abierto, setAbierto] = useState(false)
  const [tab, setTab] = useState('familia')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [nombre, setNombre] = useState('')
  const [id, setId] = useState('')

  const resetear = () => {
    setError('')
    setExito('')
  }

  const onCrear = async () => {
    resetear()
    if (!nombre.trim()) {
      setError('Nombre requerido')
      return
    }
    setCargando(true)
    try {
      const res = await CREAR[tab](nombre.trim(), id === '' ? null : Number(id))
      if (res.ok) {
        const item = res[tab]
        setExito(`${TABS.find((t) => t.clave === tab).titulo} "${item.nombre}" creada con ID ${item.id}`)
        setNombre('')
        setId('')
        onActualizar()
      } else {
        setError(res.error || 'No se pudo crear')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  if (!abierto) {
    return (
      <button
        className="btn-admin"
        onClick={() => setAbierto(true)}
        title="Administrar catálogo"
      >
        ⚙️ Admin
      </button>
    )
  }

  const activo = TABS.find((t) => t.clave === tab)
  const existentes = catalogos[LISTA[tab]] || []

  return (
    <div className="admin-panel">
      <div className="admin-overlay" onClick={() => setAbierto(false)} />
      <div className="admin-modal">
        <div className="admin-header">
          <h2>Administrar Catálogo</h2>
          <button className="btn-close" onClick={() => setAbierto(false)}>✕</button>
        </div>

        <div className="admin-tabs">
          {TABS.map((t) => (
            <button
              key={t.clave}
              className={`tab ${tab === t.clave ? 'activo' : ''}`}
              onClick={() => { setTab(t.clave); setNombre(''); setId(''); resetear() }}
            >
              {t.titulo}
            </button>
          ))}
        </div>

        {error && <div className="admin-error">{error}</div>}
        {exito && <div className="admin-exito">{exito}</div>}

        <div className="admin-form">
          <label>
            <span>Nombre de la {activo.titulo.toLowerCase()}</span>
            <input
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder={activo.placeholder}
              disabled={cargando}
            />
          </label>
          <label>
            <span>ID (opcional, el de SAP; vacío = automático)</span>
            <input
              type="number"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="Automático"
              disabled={cargando}
            />
          </label>
          <button onClick={onCrear} disabled={cargando} className="btn-crear">
            {cargando ? 'Creando...' : `Crear ${activo.titulo}`}
          </button>
          <div className="admin-listado">
            <h4>{activo.titulo}s existentes ({existentes.length})</h4>
            <ul>
              {existentes.slice(0, 10).map((it) => (
                <li key={it.id}>
                  <span className="mono">{it.id}</span> — {it.nombre}
                </li>
              ))}
              {existentes.length > 10 && <li>... y {existentes.length - 10} más</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
