// Lo que la interfaz recuerda en el navegador: ajustes de lectura, último capítulo leído
// y el borrador de la entrevista. Nada de esto es estado del dominio, y por eso puede
// perderse sin daño: en una ventana privada o con el almacenamiento bloqueado, leer
// devuelve el valor por defecto y escribir no hace nada.

export function recordar<T>(clave: string, porDefecto: T): T {
  try {
    const crudo = window.localStorage.getItem(`msm:${clave}`);
    return crudo === null ? porDefecto : { ...porDefecto, ...(JSON.parse(crudo) as T) };
  } catch {
    return porDefecto;
  }
}

/** Como `recordar`, para valores que no son objetos y no se mezclan con el defecto. */
export function recordarValor<T>(clave: string, porDefecto: T): T {
  try {
    const crudo = window.localStorage.getItem(`msm:${clave}`);
    return crudo === null ? porDefecto : (JSON.parse(crudo) as T);
  } catch {
    return porDefecto;
  }
}

export function guardar(clave: string, valor: unknown): void {
  try {
    window.localStorage.setItem(`msm:${clave}`, JSON.stringify(valor));
  } catch {
    // Sin almacenamiento la interfaz sigue funcionando; solo olvida al recargar.
  }
}

export function olvidar(clave: string): void {
  try {
    window.localStorage.removeItem(`msm:${clave}`);
  } catch {
    // Igual que arriba: olvidar algo que no se pudo guardar no es un error.
  }
}
