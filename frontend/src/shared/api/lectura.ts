// Única puerta de red de la lectura. Ninguna página llama a `fetch` por su cuenta: un
// solo sitio donde mirar cuando algo de la frontera falla.

export interface CapituloDeIndice {
  id: string;
  orden: number;
}

export interface EntidadDeFicha {
  id: string;
  nombre_canonico: string;
  /** Solo en personajes: si es la persona destinataria lo dice el backend (SPEC-013). */
  es_destinatario?: boolean;
}

export interface Lectura {
  volumen_id: string;
  titulo: string;
  dedicatoria: string;
  destinatario: string;
  capitulos: CapituloDeIndice[];
  personajes: EntidadDeFicha[];
  lugares: EntidadDeFicha[];
  /** La aprobación vigente, o `null` si la novela está abierta (SPEC-007 RF-APR-09). */
  aprobacion: Aprobacion | null;
}

export interface Aprobacion {
  id: string;
  version_numero: number;
  /** `AAAA-MM-DD HH:MM:SS` en UTC, tal como lo guarda el backend. */
  aprobada_en: string;
  retirada_en: string | null;
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

/** El cambio se ancla a un hecho o a un personaje; la ficha ancla al personaje. */
export type AnclaDeCambio = { hecho_id: string } | { entidad_id: string };

export const pedirCambio = (volumenId: string, ancla: AnclaDeCambio, descripcion: string) =>
  pedir<{ capitulos_afectados: string[] }>(`/novelas/${volumenId}/cambios`, {
    method: "POST",
    body: JSON.stringify({ ...ancla, descripcion }),
  });

export interface NombreCambiado {
  personaje_id: string;
  anterior: string;
  nuevo: string;
  revision: number;
  /** `null` si la prosa escrita no lo nombraba y no hizo falta versión nueva. */
  version_id: string | null;
  capitulos: CapituloDeIndice[];
}

/** Cambia el nombre en toda la novela (SPEC-013). Lo valida el backend: `422`/`409`. */
export const cambiarNombre = (volumenId: string, personajeId: string, nombre: string) =>
  pedir<NombreCambiado>(`/novelas/${volumenId}/personajes/${personajeId}/nombre`, {
    method: "PUT",
    body: JSON.stringify({ nombre }),
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

export interface AprobacionRegistrada {
  volumen_id: string;
  aprobacion: Aprobacion;
  /** Escenas cuyo borrador sigue sin aceptar y quedan firmadas tal como están. */
  sin_aceptar: number;
}

/** Lo que trae el `409` de aprobar: el motivo y, si la puerta los encontró, los defectos. */
export interface RechazoDeAprobacion {
  motivo: string;
  defectos: { tipo: string; regla_violada: string; evidencia: string }[];
}

/** Aprueba la novela. Si no se puede —sin terminar, ya aprobada, un defecto de la puerta
 *  *Volumen cerrado*—, el backend responde `409` y dice por qué. */
export const aprobarNovela = (volumenId: string) =>
  pedir<AprobacionRegistrada>(`/novelas/${volumenId}/aprobacion`, { method: "POST" });

/** Reabre la novela: la aprobación queda retirada, no borrada. */
export const reabrirNovela = (volumenId: string) =>
  pedir<{ volumen_id: string; aprobacion: Aprobacion }>(
    `/novelas/${volumenId}/aprobacion/retirada`,
    { method: "POST" },
  );

/** Una novela tal como la enseña la biblioteca. Estado, `detalle` y aprobación son los
 *  mismos que dan `/escritura` y `/lectura`: la biblioteca no los calcula (SPEC-008). */
export interface NovelaDeBiblioteca {
  volumen_id: string;
  titulo: string;
  destinatario: string;
  estado: string;
  detalle: string;
  capitulos: number;
  palabras: number;
  ultima_version_en: string | null;
  aprobacion: Aprobacion | null;
}

/** Todas las novelas, la más reciente primero. Sin novelas, lista vacía. */
export const leerBiblioteca = () => pedir<NovelaDeBiblioteca[]>("/novelas");

export interface NovelaEliminada {
  volumen_id: string;
  titulo: string;
  eliminada_en: string;
}

/** Retira la novela (SPEC-009): deja de verse en la biblioteca y en todas las rutas, pero
 *  nada se borra de la base. Aprobada o escribiéndose, el backend responde `409` y dice
 *  por qué. */
export const eliminarNovela = (volumenId: string) =>
  pedir<NovelaEliminada>(`/novelas/${volumenId}`, { method: "DELETE" });

/** Lo que ha costado una novela, leído de SQLite (SPEC-012). La pantalla no suma nada:
 *  totales y desgloses vienen hechos del backend. */
export interface TotalDeGasto {
  coste: number;
  llamadas: number;
  fallidas: number;
  tokens_entrada: number;
  tokens_salida: number;
  latencia_ms: number;
  llamadas_sin_tokens: number;
}

export interface DesgloseDeGasto {
  nombre: string;
  coste: number;
  llamadas: number;
}

export interface LlamadaDeGasto {
  id: string;
  momento: string;
  agente: string;
  modelo: string;
  version_de_prompt: string;
  tarea: string;
  escena_id: string | null;
  capitulo_orden: number | null;
  intento: number;
  coste: number;
  latencia_ms: number;
  tokens_entrada: number | null;
  tokens_salida: number | null;
  clase_de_fallo: string | null;
  /** El enlace a su traza en Langfuse, o `null` si Langfuse no está configurado. */
  traza_url: string | null;
}

export interface GastosDeNovela {
  volumen_id: string;
  moneda: string;
  langfuse_activo: boolean;
  total: TotalDeGasto;
  por_rol: DesgloseDeGasto[];
  por_capitulo: DesgloseDeGasto[];
  llamadas: LlamadaDeGasto[];
}

export const leerGastos = (volumenId: string) =>
  pedir<GastosDeNovela>(`/novelas/${volumenId}/gastos`);

/** Un personaje declarado antes de escribir (SPEC-011). La persona destinataria va
 *  primera, siempre protagonista; su nombre y su papel los pone el backend. */
export type PapelDePersonaje = "protagonico" | "secundario" | "ambiental";

export interface PersonajeDeclarado {
  nombre: string;
  papel: PapelDePersonaje;
  relacion: string;
  descripcion: string;
  es_destinatario: boolean;
}

export const leerPersonajes = (volumenId: string) =>
  pedir<{ volumen_id: string; personajes: PersonajeDeclarado[] }>(
    `/novelas/${volumenId}/personajes`,
  );

/** Reemplaza la lista entera. `422` si un personaje no vale —el backend dice cuál— y
 *  `409` si la escritura ya empezó o la novela está aprobada. */
export const guardarPersonajes = (volumenId: string, personajes: PersonajeDeclarado[]) =>
  pedir<{ volumen_id: string; personajes: PersonajeDeclarado[] }>(
    `/novelas/${volumenId}/personajes`,
    { method: "PUT", body: JSON.stringify({ personajes }) },
  );
