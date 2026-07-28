// api.js — llamadas centralizadas al backend.
// Base URL configurable: VITE_API_BASE > /api (mismo origen; en dev Vite proxea al 8000).
const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detalle = await res.text().catch(() => '')
    throw new Error(`Error ${res.status}: ${detalle || res.statusText}`)
  }
  return res.json()
}

export const getCatalogos = () => request('/catalogos')

export const generar = (descripcion) =>
  request('/generar', { method: 'POST', body: JSON.stringify({ descripcion }) })

export const guardar = (payload) =>
  request('/guardar', { method: 'POST', body: JSON.stringify(payload) })

export const crearFamilia = (nombre, id = null) =>
  request('/crear-familia', { method: 'POST', body: JSON.stringify({ nombre, id }) })

export const crearLinea = (nombre, id = null) =>
  request('/crear-linea', { method: 'POST', body: JSON.stringify({ nombre, id }) })

export const crearSublinea = (nombre, id = null) =>
  request('/crear-sublinea', { method: 'POST', body: JSON.stringify({ nombre, id }) })
