// SimilarTable — artículos más parecidos, el más cercano primero.
// Click en una fila copia su código al campo de código (sirve como plantilla).
export default function SimilarTable({ similares, onSeleccionar }) {
  if (!similares || similares.length === 0) return null

  return (
    <section className="card">
      <div className="card-head">
        <h2>Artículos similares</h2>
        <span className="muted">Click en una fila para usar su código como plantilla</span>
      </div>
      <div className="tabla-wrap">
        <table>
          <thead>
            <tr>
              <th>Score</th>
              <th>Código</th>
              <th>Descripción</th>
              <th>Cod. subl.</th>
              <th>Sublínea</th>
              <th>SAT</th>
              <th>UDM</th>
            </tr>
          </thead>
          <tbody>
            {similares.map((s) => (
              <tr
                key={s.codigo}
                onClick={() => onSeleccionar(s.codigo)}
                title="Usar este código como plantilla"
              >
                <td>{s.score.toFixed(3)}</td>
                <td className="mono">{s.codigo}</td>
                <td>{s.descripcion}</td>
                <td className="mono">{s.cod_sublinea ?? ''}</td>
                <td>{s.sublinea}</td>
                <td className="mono">{s.codigo_sat}</td>
                <td>{s.udm}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
