// Única puerta de red de la lectura. Ninguna página llama a `fetch` por su cuenta: un
// solo sitio donde mirar cuando algo de la frontera falla.

export interface CapituloDeIndice {
  id: string;
  orden: number;
}

export interface EntidadDeFicha {
  id: string;
  nombre_canonico: string;
}

export interface Lectura {
  volumen_id: string;
  titulo: string;
  dedicatoria: string;
  destinatario: string;
  capitulos: CapituloDeIndice[];
  personajes: EntidadDeFicha[];
  lugares: EntidadDeFicha[];
}

export interface VersionPublicada {
  id: string;
  numero: number;
  anterior_id: string | null;
  publicada_en: string;
  motivo: string;
}

export interface CapituloDeVersion {
  capitulo_id: string;
  borrador_id: string | null;
  cambiado: number;
}

/** Con qué se escribe la novela. Los dos valores son los del contrato: el frontend no
 *  inventa un tercero ni decide cuál toca. */
export type ModoDeEscritura = "modelo" | "demostracion";

export interface EscrituraAceptada {
  volumen_id: string;
  plan_id: string;
  modo: ModoDeEscritura;
  tareas: string[];
  aviso: string;
}

export interface EscenaEnProgreso {
  escena_id: string;
  capitulo_id: string;
  capitulo_orden: number;
  estado: string;
  intentos_narrativos: number;
  falta: string[];
}

export interface ProgresoDeEscritura {
  volumen_id: string;
  estado: string;
  modo: ModoDeEscritura | null;
  plan_id: string | null;
  escritas: number;
  totales: number;
  /** La línea que explica el estado. La compone el backend: es una regla del dominio. */
  detalle: string;
  escenas: EscenaEnProgreso[];
}

export interface EscenaConTexto {
  id: string;
  orden: number;
  texto: string;
  palabras: number;
  estado: string;
  aceptado: boolean;
  /** Por qué este borrador no está aceptado. También viene hecho del backend. */
  motivo: string;
  modelo: string;
}

export interface CapituloConTexto {
  id: string;
  orden: number;
  titulo: string;
  palabras: number;
  escenas: EscenaConTexto[];
}

export interface TextoDeNovela {
  volumen_id: string;
  titulo: string;
  palabras: number;
  de_demostracion: boolean;
  capitulos: CapituloConTexto[];
}

export interface Contradiccion {
  campos: string[];
  detalle: string;
}

export interface EntrevistaFallida {
  huecos: string[];
  contradicciones: Contradiccion[];
}

export interface EntrevistaCerrada {
  brief_id: string;
  volumen_id: string;
  titulo: string;
  destinatario: string;
  palabras_vetadas: string[];
  intentos_de_injection: string[];
  hechos_propuestos: string[];
}

export class ErrorDeLectura extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
    // El detalle estructurado del 422: huecos y contradicciones tal como los nombra el
    // backend. La pantalla los muestra; no los vuelve a calcular.
    readonly detalle?: unknown,
  ) {
    // El mensaje del backend se traslada íntegro: el del dominio es el que sabe qué pasó.
    super(mensaje);
  }
}

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, {
    ...opciones,
    headers: { "Content-Type": "application/json", ...(opciones?.headers ?? {}) },
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    let detalle: unknown;
    try {
      detalle = (JSON.parse(cuerpo) as { detail?: unknown }).detail;
    } catch {
      detalle = undefined;
    }
    throw new ErrorDeLectura(respuesta.status, cuerpo || respuesta.statusText, detalle);
  }
  return (await respuesta.json()) as T;
}

export const leerNovela = (volumenId: string) =>
  pedir<Lectura>(`/novelas/${volumenId}/lectura`);

export const leerVersiones = (volumenId: string) =>
  pedir<VersionPublicada[]>(`/novelas/${volumenId}/versiones`);

export const leerCapitulosDeVersion = (versionId: string) =>
  pedir<CapituloDeVersion[]>(`/versiones/${versionId}/capitulos`);

export const pedirCambio = (volumenId: string, hechoId: string, descripcion: string) =>
  pedir<{ capitulos_afectados: string[] }>(`/novelas/${volumenId}/cambios`, {
    method: "POST",
    body: JSON.stringify({ hecho_id: hechoId, descripcion }),
  });

export const leerTexto = (volumenId: string) =>
  pedir<TextoDeNovela>(`/novelas/${volumenId}/texto`);

export const leerProgreso = (volumenId: string) =>
  pedir<ProgresoDeEscritura>(`/novelas/${volumenId}/escritura`);

export const escribirNovela = (volumenId: string, modo: ModoDeEscritura) =>
  pedir<EscrituraAceptada>(`/novelas/${volumenId}/escritura`, {
    method: "POST",
    body: JSON.stringify({ modo }),
  });

export const cerrarEntrevista = (
  respuestas: Record<string, unknown>,
  textoLibre: string,
) =>
  pedir<EntrevistaCerrada>("/entrevista", {
    method: "POST",
    body: JSON.stringify({ respuestas, texto_libre: textoLibre }),
  });

/** Dónde se descarga la novela en PDF. Es un enlace y no un `fetch`: la descarga la hace
 *  el navegador, que es quien sabe guardar un fichero. La ruta sigue viviendo aquí para
 *  que la frontera con el backend esté en un solo sitio. */
export const urlDelPdf = (volumenId: string) => `/api/novelas/${volumenId}/pdf`;

export interface PortadaGuardada {
  volumen_id: string;
  titulo: string;
  dedicatoria: string;
}

/** Cambia el título, la dedicatoria o los dos. Lo que no se envía no cambia; los límites
 *  y los términos vetados los comprueba el backend, que responde `422` con el motivo. */
export const actualizarPortada = (
  volumenId: string,
  cambios: { titulo?: string; dedicatoria?: string },
) =>
  pedir<PortadaGuardada>(`/novelas/${volumenId}/portada`, {
    method: "PATCH",
    body: JSON.stringify(cambios),
  });
