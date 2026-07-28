// ResultCard — código generado en monospace grande + estado; el código es editable.
import StatusBadge from './StatusBadge.jsx'

export default function ResultCard({ resultado, codigo, onCodigo }) {
  const { estado, confianza, similares } = resultado
  const referencia = similares && similares.length > 0 ? similares[0] : null

  return (
    <section className="card">
      <div className="card-head">
        <h2>Código generado</h2>
        <StatusBadge estado={estado} />
      </div>

      <input
        className="codigo-grande"
        value={codigo}
        onChange={(e) => onCodigo(e.target.value.toUpperCase())}
        spellCheck={false}
        aria-label="Código generado (editable)"
      />

      {estado === 'duplicado' && (
        <div className="aviso aviso-danger">
          Este código ya existe en el registro: el artículo probablemente ya está
          dado de alta. Revisa la tabla de similares antes de continuar.
        </div>
      )}

      {estado === 'revisar' && referencia && (
        <div className="aviso aviso-warn">
          El tramo numérico no pudo auto-validarse con el registro histórico.
          Valida la cola del código tomando como referencia el similar más
          cercano: <code>{referencia.codigo}</code> —{' '}
          <span className="muted">{referencia.descripcion}</span>
        </div>
      )}

      <p className="confianza">
        Confianza de clasificación:{' '}
        <strong>{Math.round((confianza || 0) * 100)}%</strong>
      </p>
    </section>
  )
}
