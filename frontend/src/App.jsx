// App — página única: entrada de descripción, resultado, formulario SAP y similares.
import { useEffect, useState } from 'react'
import { getCatalogos, generar, guardar } from './api.js'
import ResultCard from './components/ResultCard.jsx'
import SapForm from './components/SapForm.jsx'
import SimilarTable from './components/SimilarTable.jsx'
import AdminPanel from './components/AdminPanel.jsx'

const FORM_VACIO = {
  codigo: '', familia: '', linea: '', sublinea: '',
  cod_familia: '', cod_linea: '', cod_sublinea: '',
  codigo_sat: '', udm: '', udm_sat: '', peso: 0,
}

export default function App() {
  const [descripcion, setDescripcion] = useState('')
  const [catalogos, setCatalogos] = useState({})
  const [resultado, setResultado] = useState(null)
  const [form, setForm] = useState(FORM_VACIO)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [guardado, setGuardado] = useState(null)

  useEffect(() => {
    getCatalogos().then(setCatalogos).catch(() => setError('No se pudo cargar el catálogo'))
  }, [])

  const recargarCatalogo = () => {
    getCatalogos().then(setCatalogos).catch(() => setError('No se pudo recargar el catálogo'))
  }

  const onGenerar = async () => {
    if (!descripcion.trim() || cargando) return
    setCargando(true)
    setError('')
    setGuardado(null)
    try {
      const r = await generar(descripcion.trim())
      setResultado(r)
      setForm({
        codigo: r.codigo,
        familia: r.familia,
        linea: r.linea,
        sublinea: r.sublinea,
        cod_familia: r.cod_familia ?? '',
        cod_linea: r.cod_linea ?? '',
        cod_sublinea: r.cod_sublinea ?? '',
        codigo_sat: r.codigo_sat,
        udm: r.udm,
        udm_sat: r.udm_sat,
        peso: r.peso,
      })
    } catch (e) {
      setError(e.message)
      setResultado(null)
    } finally {
      setCargando(false)
    }
  }

  const onGuardar = async () => {
    setError('')
    try {
      const r = await guardar({
        ...form,
        cod_familia: form.cod_familia === '' ? null : Number(form.cod_familia),
        cod_linea: form.cod_linea === '' ? null : Number(form.cod_linea),
        cod_sublinea: form.cod_sublinea === '' ? null : Number(form.cod_sublinea),
        peso: Number(form.peso) || 0,
        articulo: descripcion.trim(),
      })
      if (r.ok) {
        setGuardado({ codigo: r.codigo })
      } else {
        setError(r.error || 'No se pudo guardar')
      }
    } catch (e) {
      setError(e.message)
    }
  }

  const filaCsv = () => {
    const campos = [
      form.codigo, descripcion.trim(),
      form.cod_familia, form.familia, form.cod_linea, form.linea,
      form.cod_sublinea, form.sublinea,
      form.udm, form.udm_sat, form.peso, form.codigo_sat,
    ]
    const encabezado =
      'CODIGO,ARTICULO,COD.FAMILIA,FAMILIA,COD.LINEA,LINEA,COD.SUBLINEA,SUBLINEA,UDM,UDM SAT,PESO,CODIGO SAT'
    const fila = campos.map((v) => `"${String(v ?? '').replaceAll('"', '""')}"`).join(',')
    return `${encabezado}\n${fila}\n`
  }

  const copiarFila = () => navigator.clipboard.writeText(filaCsv())

  const descargarFila = () => {
    const url = URL.createObjectURL(new Blob([filaCsv()], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `alta_${form.codigo || 'articulo'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="contenedor">
      <header className="encabezado">
        <div className="logo" aria-hidden="true">H</div>
        <div>
          <h1>Generador de códigos de artículos</h1>
          <p className="subtitulo">
            Alta de artículos en SAP a partir de los registros históricos de Herinox
          </p>
        </div>
        <AdminPanel catalogos={catalogos} onActualizar={recargarCatalogo} />
      </header>

      <section className="card entrada">
        <label className="etiqueta" htmlFor="descripcion">
          Descripción del artículo nuevo
        </label>
        <div className="fila-entrada">
          <input
            id="descripcion"
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onGenerar()}
            placeholder={'Ej. TUBO INOX. 316 CED. 40 C/C DE 4" X 20\' (98.02 KG/PZ)'}
            spellCheck={false}
          />
          <button className="btn-primario" onClick={onGenerar} disabled={cargando}>
            {cargando ? 'Generando…' : 'Generar'}
          </button>
        </div>
      </section>

      {error && <div className="aviso aviso-danger">{error}</div>}

      {resultado && (
        <>
          <ResultCard
            resultado={resultado}
            codigo={form.codigo}
            onCodigo={(codigo) => setForm({ ...form, codigo })}
          />
          <SapForm form={form} onChange={setForm} catalogos={catalogos} />
          <SimilarTable
            similares={resultado.similares}
            onSeleccionar={(codigo) => setForm({ ...form, codigo })}
          />

          <div className="acciones">
            <button
              className="btn-primario"
              onClick={onGuardar}
              disabled={resultado.estado === 'duplicado' || !!guardado}
            >
              Guardar
            </button>
            {guardado && (
              <>
                <span className="confirmacion">
                  Artículo guardado con el código <strong>{guardado.codigo}</strong>
                </span>
                <button className="btn-secundario" onClick={copiarFila}>
                  Copiar fila
                </button>
                <button className="btn-secundario" onClick={descargarFila}>
                  Descargar CSV
                </button>
              </>
            )}
          </div>
        </>
      )}

      <footer className="pie">
        Herramienta externa · sin conexión a SAP ni a la base de datos de la empresa
      </footer>
    </div>
  )
}
