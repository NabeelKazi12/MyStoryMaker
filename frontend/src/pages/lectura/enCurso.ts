/** Los dos estados en los que todavía queda trabajo. El conjunto es del backend; aquí
 *  solo se pregunta si hay que seguir sondeando. */
export function enCurso(estado: string): boolean {
  return estado === "abriendo" || estado === "escribiendo";
}

/** Minutos de lectura a unas 230 palabras por minuto. Es una estimación de interfaz,
 *  como la de cualquier lector de libros, no un dato de la novela. */
export function minutosDeLectura(palabras: number): number {
  return Math.max(1, Math.round(palabras / 230));
}
