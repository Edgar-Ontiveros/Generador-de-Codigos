// StatusBadge — estado del código generado: NUEVO / YA EXISTE / REVISAR.
const ESTADOS = {
  nuevo: { texto: 'NUEVO', clase: 'badge badge-ok' },
  duplicado: { texto: 'YA EXISTE', clase: 'badge badge-danger' },
  revisar: { texto: 'REVISAR', clase: 'badge badge-warn' },
}

export default function StatusBadge({ estado }) {
  const e = ESTADOS[estado]
  if (!e) return null
  return <span className={e.clase}>{e.texto}</span>
}
