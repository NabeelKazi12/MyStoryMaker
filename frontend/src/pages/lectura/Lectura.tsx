import { useCallback, useEffect, useRef, useState } from "react";
import {
  actualizarPortada,
  aprobarNovela,
  eliminarNovela,
  ErrorDeLectura,
  escribirNovela,
  leerCapitulosDeVersion,
  leerNovela,
  leerProgreso,
  leerTexto,
  leerVersiones,
  pedirCambio,
  reabrirNovela,
  type Aprobacion,
  type CapituloDeVersion,
  type Lectura as DatosDeLectura,
  type ModoDeEscritura,
  type ProgresoDeEscritura,
  type RechazoDeAprobacion,
  type TextoDeNovela,
  type VersionPublicada,
} from "../../shared/api/lectura";
import type { AjustesDeLectura } from "../../shared/ui/ajustes";
import { guardar, recordarValor } from "../../shared/ui/almacen";
import { ListaDeAvisos, useAvisos } from "../../shared/ui/Avisos";
import { Dialogo } from "../../shared/ui/Dialogo";
import { Icono } from "../../shared/ui/Icono";
import { Panel } from "../../shared/ui/Panel";
import { CapituloLeido } from "./CapituloLeido";
import { enCurso, minutosDeLectura } from "./enCurso";
import { MenuAjustes } from "./MenuAjustes";
import { PanelDeGastos } from "./PanelDeGastos";
import { Taller } from "./Taller";

type Estado =
  | { fase: "cargando" }
  | { fase: "error"; mensaje: string }
  | {
      fase: "lista";
      datos: DatosDeLectura;
      versiones: VersionPublicada[];
      cambiados: string[];
    };

type NombreDePanel = "indice" | "ficha" | "taller" | "gastos";

/** Por qué algo está desactivado con la novela aprobada. Es guía de pantalla: si alguien
 *  lo intenta igual, el `409` del backend es el que manda (SPEC-007 RF-APR-08). */
const BLOQUEADA_POR_APROBACION =
  "La novela está aprobada: reábrela desde el Taller para cambiarla.";

/** `AAAA-MM-DD HH:MM:SS` en UTC, como lo guarda el backend, a una fecha legible. */
function fechaDeAprobacion(aprobacion: Aprobacion): string {
  const fecha = new Date(`${aprobacion.aprobada_en.replace(" ", "T")}Z`);
  return Number.isNaN(fecha.getTime())
    ? aprobacion.aprobada_en
    : fecha.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
}

/** Cada cuánto se vuelve a preguntar por el progreso mientras se escribe.
 *
 *  Se sondea, y no se abre el SSE de `/tareas/{id}/eventos`, porque ese flujo emite el
 *  historial ya registrado de **una** tarea y se cierra; lo que esta pantalla necesita es
 *  el estado de la novela entera mientras avanza. Cambiarlo es cosa del backend, y hasta
 *  entonces sondear cada dos segundos es honesto y barato.
 */
const CADA_CUANTO_MS = 2000;

/** La lectura de la novela, como un lector de libros: una cubierta, un capítulo por
 *  pantalla con paso de página, ajustes «Aa», y paneles para el índice, la ficha de
 *  personajes y lugares y el taller de escritura. */
export function Lectura({
  volumenId,
  alBiblioteca,
  alNueva,
  alEliminada,
  ajustes,
  cambiarAjustes,
}: {
  volumenId: string;
  /** Vuelve a la estantería de novelas (SPEC-008). */
  alBiblioteca: () => void;
  /** Abre la entrevista de una novela nueva. */
  alNueva: () => void;
  /** La novela se ha eliminado: quien la abrió decide a dónde se vuelve (SPEC-009). */
  alEliminada: (titulo: string) => void;
  ajustes: AjustesDeLectura;
  cambiarAjustes: (parcial: Partial<AjustesDeLectura>) => void;
}) {
  const [estado, setEstado] = useState<Estado>({ fase: "cargando" });
  const [progreso, setProgreso] = useState<ProgresoDeEscritura | null>(null);
  const [texto, setTexto] = useState<TextoDeNovela | null>(null);
  const [encargando, setEncargando] = useState(false);
  const { avisos, anadir, cerrar, limpiar } = useAvisos();
  const vigente = useRef(true);

  // Estado de interfaz, separado del de dominio: un refresco del progreso no lo toca.
  const claveDeCapitulo = `lectura:${volumenId}:capitulo`;
  const [actual, setActual] = useState<number | null>(null);
  // La página de dedicatoria va entre la cubierta y el capítulo 1 (SPEC-006 RF-LEC-11).
  // Es un estado aparte y no un índice más: no es un capítulo, no cuenta en «n de N» y no
  // se recuerda como último leído.
  const [enDedicatoria, setEnDedicatoria] = useState(false);
  const [panel, setPanel] = useState<NombreDePanel | null>(null);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [cambio, setCambio] = useState<{ id: string; nombre: string } | null>(null);
  const [descripcion, setDescripcion] = useState("");
  const [pestanaFicha, setPestanaFicha] = useState<"personajes" | "lugares">("personajes");
  const [leido, setLeido] = useState(0);
  // Sube con cada «Reintentar» y vuelve a lanzar la lectura inicial.
  const [intento, setIntento] = useState(0);
  // El diálogo de firma abierto, si hay alguno: aprobar o reabrir (SPEC-007).
  const [confirmando, setConfirmando] = useState<"aprobar" | "reabrir" | null>(null);
  const [firmando, setFirmando] = useState(false);
  // La confirmación de eliminar pide escribir el título (SPEC-009 RF-LEC-18).
  const [eliminando, setEliminando] = useState(false);
  const [tituloEscrito, setTituloEscrito] = useState("");
  const [borrando, setBorrando] = useState(false);

  useEffect(() => {
    vigente.current = true;
    return () => {
      vigente.current = false;
    };
  }, [volumenId]);

  useEffect(() => {
    void (async () => {
      try {
        const datos = await leerNovela(volumenId);
        const versiones = await leerVersiones(volumenId);
        let cambiados: string[] = [];
        if (versiones.length > 1) {
          const ultima = versiones[versiones.length - 1];
          const capitulos: CapituloDeVersion[] = await leerCapitulosDeVersion(ultima.id);
          cambiados = capitulos.filter((c) => c.cambiado === 1).map((c) => c.capitulo_id);
        }
        if (vigente.current) setEstado({ fase: "lista", datos, versiones, cambiados });
      } catch (error) {
        const mensaje = error instanceof ErrorDeLectura ? error.message : String(error);
        if (vigente.current) setEstado({ fase: "error", mensaje });
      }
    })();
  }, [volumenId, intento]);

  const refrescar = useCallback(async () => {
    // Progreso y texto se piden juntos: una pantalla que dijera «escritas 3 de 4» y
    // enseñara dos capítulos obligaría a recargar para saber cuál de las dos miente.
    const [comoVa, escrito] = await Promise.all([
      leerProgreso(volumenId),
      leerTexto(volumenId),
    ]);
    if (!vigente.current) return comoVa;
    setProgreso(comoVa);
    setTexto(escrito);
    return comoVa;
  }, [volumenId]);

  useEffect(() => {
    void refrescar().catch(() => undefined);
  }, [refrescar]);

  // Mientras hay escritura en curso se vuelve a preguntar. Cuando deja de haberla, el
  // intervalo se retira solo: sondear una novela terminada es ruido permanente.
  useEffect(() => {
    if (!progreso || !enCurso(progreso.estado)) return;
    const reloj = window.setInterval(() => {
      void refrescar().catch(() => undefined);
    }, CADA_CUANTO_MS);
    return () => window.clearInterval(reloj);
  }, [progreso, refrescar]);

  const capitulos = estado.fase === "lista" ? estado.datos.capitulos : [];
  const total = capitulos.length;

  const irA = useCallback(
    (indice: number | null) => {
      setEnDedicatoria(false);
      setActual(indice);
      if (indice !== null && capitulos[indice]) guardar(claveDeCapitulo, capitulos[indice].id);
      window.scrollTo({ top: 0 });
    },
    [capitulos, claveDeCapitulo],
  );

  const irADedicatoria = useCallback(() => {
    setActual(null);
    setEnDedicatoria(true);
    window.scrollTo({ top: 0 });
  }, []);

  const hayDedicatoria =
    estado.fase === "lista" && estado.datos.dedicatoria.trim() !== "";

  // Paso de página con las flechas, salvo escribiendo en un campo o con un diálogo encima.
  // El recorrido es cubierta → dedicatoria (si la hay) → capítulos, en los dos sentidos.
  useEffect(() => {
    if (actual === null && !enDedicatoria) return;
    const alTeclear = (evento: KeyboardEvent) => {
      const destino = evento.target as HTMLElement | null;
      if (destino?.closest("input, textarea, select, [contenteditable]")) return;
      if (document.querySelector("dialog[open]")) return;
      if (enDedicatoria) {
        if (evento.key === "ArrowRight" && total > 0) irA(0);
        if (evento.key === "ArrowLeft") irA(null);
        return;
      }
      if (actual === null) return;
      if (evento.key === "ArrowRight" && actual < total - 1) irA(actual + 1);
      if (evento.key === "ArrowLeft") {
        if (actual > 0) irA(actual - 1);
        else if (hayDedicatoria) irADedicatoria();
        else irA(null);
      }
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [actual, enDedicatoria, hayDedicatoria, total, irA, irADedicatoria]);

  // La barra de progreso de lectura: cuánto del capítulo actual queda por encima.
  useEffect(() => {
    const medir = () => {
      const recorrido = document.documentElement.scrollHeight - window.innerHeight;
      setLeido(recorrido > 0 ? Math.min(1, window.scrollY / recorrido) : 1);
    };
    medir();
    window.addEventListener("scroll", medir, { passive: true });
    window.addEventListener("resize", medir);
    return () => {
      window.removeEventListener("scroll", medir);
      window.removeEventListener("resize", medir);
    };
  }, [actual, texto]);

  useEffect(() => {
    if (!menuAbierto) return;
    const alTeclear = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") setMenuAbierto(false);
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [menuAbierto]);

  const cerrarPanel = useCallback(() => setPanel(null), []);

  async function encargar(modo: ModoDeEscritura) {
    setEncargando(true);
    try {
      const aceptada = await escribirNovela(volumenId, modo);
      anadir(aceptada.aviso);
      await refrescar();
    } catch (error) {
      if (error instanceof ErrorDeLectura && error.estado === 503) {
        // El backend dice exactamente qué falta y qué alternativa hay. Se traslada
        // íntegro: reescribirlo aquí acabaría diciendo algo distinto de lo que pasó.
        anadir(String(error.detalle ?? error.message));
      } else {
        anadir(error instanceof Error ? error.message : String(error));
      }
    } finally {
      if (vigente.current) setEncargando(false);
    }
  }

  async function guardarPortada(cambios: { titulo?: string; dedicatoria?: string }) {
    try {
      const guardada = await actualizarPortada(volumenId, cambios);
      setEstado((previo) =>
        previo.fase === "lista"
          ? {
              ...previo,
              datos: { ...previo.datos, titulo: guardada.titulo, dedicatoria: guardada.dedicatoria },
            }
          : previo,
      );
      anadir(
        guardada.dedicatoria
          ? `Portada guardada: «${guardada.titulo}», con su dedicatoria en la primera página.`
          : `Portada guardada: «${guardada.titulo}», sin dedicatoria.`,
      );
    } catch (error) {
      // El motivo lo redacta el backend —qué límite falla, qué término está vetado—, y se
      // traslada tal cual.
      anadir(
        error instanceof ErrorDeLectura
          ? `No se ha guardado la portada: ${String(error.detalle ?? error.message)}`
          : String(error),
      );
    }
  }

  /** Pone la aprobación nueva —o `null`— en los datos de la lectura, sin recargar. */
  function ponerAprobacion(aprobacion: Aprobacion | null) {
    setEstado((previo) =>
      previo.fase === "lista" ? { ...previo, datos: { ...previo.datos, aprobacion } } : previo,
    );
  }

  async function abrirAprobacion() {
    // Las versiones se vuelven a pedir: la que se firma es la última publicada, y puede
    // haberse publicado después de abrir la lectura.
    try {
      const versiones = await leerVersiones(volumenId);
      setEstado((previo) => (previo.fase === "lista" ? { ...previo, versiones } : previo));
    } catch {
      // Si falla, el diálogo enseña la que ya había: aprobar lo decide el backend igual.
    }
    setConfirmando("aprobar");
  }

  async function firmar() {
    setFirmando(true);
    try {
      if (confirmando === "aprobar") {
        const registrada = await aprobarNovela(volumenId);
        ponerAprobacion(registrada.aprobacion);
        anadir(
          `Novela aprobada sobre la versión ${registrada.aprobacion.version_numero}.` +
            (registrada.sin_aceptar > 0
              ? ` ${registrada.sin_aceptar} escena(s) quedan firmadas con el borrador sin aceptar.`
              : ""),
        );
      } else {
        const reabierta = await reabrirNovela(volumenId);
        ponerAprobacion(null);
        anadir(
          `Novela reabierta: la versión ${reabierta.aprobacion.version_numero} deja de estar aprobada y se puede volver a cambiar.`,
        );
      }
    } catch (error) {
      anadir(motivoDelRechazo(error));
    } finally {
      if (vigente.current) {
        setFirmando(false);
        setConfirmando(null);
      }
    }
  }

  async function confirmarEliminacion() {
    setBorrando(true);
    try {
      const retirada = await eliminarNovela(volumenId);
      setEliminando(false);
      alEliminada(retirada.titulo);
    } catch (error) {
      // Un `409` o un `404` se enseña aquí mismo y no se sale de la lectura (RF-LEC-19).
      anadir(
        error instanceof ErrorDeLectura
          ? `No se ha eliminado: ${String(error.detalle ?? error.message)}`
          : String(error),
      );
      if (vigente.current) setEliminando(false);
    } finally {
      if (vigente.current) setBorrando(false);
    }
  }

  async function enviarCambio() {
    if (!cambio || !descripcion.trim()) return;
    const hechoId = cambio.id;
    setCambio(null);
    try {
      const respuesta = await pedirCambio(volumenId, hechoId, descripcion);
      const afectados = respuesta.capitulos_afectados;
      anadir(
        afectados.length === 0
          ? "Ese hecho no consta usado en ningún capítulo, así que no se regenera nada."
          : `Se regenerarán ${afectados.length} capítulo(s): ${afectados.join(", ")}.`,
      );
    } catch (error) {
      anadir(error instanceof ErrorDeLectura ? error.message : String(error));
    }
    setDescripcion("");
  }

  if (estado.fase === "cargando")
    return (
      <div className="pantalla-centrada">
        <div className="cargando" aria-hidden="true" />
        <p>Abriendo la novela…</p>
      </div>
    );

  // «No he podido leer» es distinto de «no hay nada»: confundirlos pinta un fallo de
  // lectura como una novela vacía, y nadie va a investigar una novela vacía.
  if (estado.fase === "error")
    return (
      <div className="pantalla-centrada">
        <div className="tarjeta">
          <p className="error">No se ha podido leer la novela. El backend dijo: {estado.mensaje}</p>
          <button
            className="boton principal"
            onClick={() => {
              setEstado({ fase: "cargando" });
              setIntento((n) => n + 1);
              void refrescar().catch(() => undefined);
            }}
          >
            Reintentar
          </button>
          <button className="boton secundario" onClick={alBiblioteca}>
            <Icono nombre="volver" tamano={16} /> Volver a la biblioteca
          </button>
        </div>
      </div>
    );

  const { datos, versiones, cambiados } = estado;
  const escribiendo = progreso !== null && enCurso(progreso.estado);
  const escritos = new Map((texto?.capitulos ?? []).map((c) => [c.id, c]));
  const hayProsa = texto !== null && texto.palabras > 0;
  const tituloDe = (indice: number) =>
    escritos.get(capitulos[indice].id)?.titulo || `Capítulo ${capitulos[indice].orden}`;

  const aprobacion = datos.aprobacion ?? null;
  const sinAceptar = (texto?.capitulos ?? []).reduce(
    (cuenta, capitulo) => cuenta + capitulo.escenas.filter((e) => !e.aceptado).length,
    0,
  );
  const ultimaVersion = versiones.length > 0 ? versiones[versiones.length - 1] : null;

  const ultimoId = recordarValor<string | null>(claveDeCapitulo, null);
  const ultimo = capitulos.findIndex((c) => c.id === ultimoId);

  const alternar = (nombre: NombreDePanel) => {
    setMenuAbierto(false);
    setPanel((abierto) => (abierto === nombre ? null : nombre));
  };

  return (
    <div className="lector">
      <header className="barra-superior">
        <div className="barra-grupo">
          <button
            className="boton-icono"
            onClick={alBiblioteca}
            aria-label="Biblioteca"
            title="Volver a la biblioteca"
          >
            <Icono nombre="estante" />
          </button>
          <button className="boton-icono" onClick={() => alternar("indice")} aria-label="Índice" aria-pressed={panel === "indice"} title="Índice">
            <Icono nombre="indice" />
          </button>
          <button className="barra-titulo" onClick={() => irA(null)} title="Volver a la cubierta">
            <Icono nombre="libro" tamano={18} />
            <span>{datos.titulo}</span>
          </button>
        </div>

        <div className="barra-centro">
          {actual !== null && total > 0 ? (
            <span>
              Capítulo {actual + 1} de {total}
            </span>
          ) : null}
        </div>

        <div className="barra-grupo derecha">
          {aprobacion ? (
            <button className="sello-aprobada" onClick={() => alternar("taller")} title="Novela aprobada">
              <Icono nombre="sello" tamano={14} />
              Aprobada · v{aprobacion.version_numero}
            </button>
          ) : null}
          {escribiendo && progreso ? (
            <button className="chip-escribiendo" onClick={() => alternar("taller")}>
              <span className="punto-vivo" aria-hidden="true" />
              Escribiendo {progreso.totales > 0 ? `${progreso.escritas}/${progreso.totales}` : "…"}
            </button>
          ) : null}
          <div className="ancla-menu">
            <button
              className="boton-icono boton-aa"
              onClick={() => {
                setPanel(null);
                setMenuAbierto((abierto) => !abierto);
              }}
              aria-expanded={menuAbierto}
              aria-label="Ajustes de lectura"
              title="Ajustes de lectura"
            >
              <span className="aa-pequena">A</span>A
            </button>
            {menuAbierto ? <MenuAjustes ajustes={ajustes} cambiar={cambiarAjustes} /> : null}
          </div>
          <button className="boton-icono" onClick={() => alternar("gastos")} aria-label="Gastos" aria-pressed={panel === "gastos"} title="Gastos">
            <Icono nombre="gastos" />
          </button>
          <button className="boton-icono" onClick={() => alternar("ficha")} aria-label="Quién es quién" aria-pressed={panel === "ficha"} title="Quién es quién">
            <Icono nombre="ficha" />
          </button>
          <button className="boton-icono" onClick={() => alternar("taller")} aria-label="Taller" aria-pressed={panel === "taller"} title="Taller">
            <Icono nombre="taller" />
          </button>
        </div>
        {actual !== null ? (
          <div className="progreso-lectura" aria-hidden="true">
            <span style={{ transform: `scaleX(${leido})` }} />
          </div>
        ) : null}
      </header>

      <ListaDeAvisos avisos={avisos} cerrar={cerrar} limpiar={limpiar} />

      <main className="pagina">
        {texto?.de_demostracion ? (
          <p className="marca-demostracion">
            Esta previa está escrita en <strong>modo demostración</strong>: la compone el
            sistema a partir del encargo, sin modelo. Queda marcada como tal en la
            procedencia de cada borrador y no debe confundirse con una novela escrita.
          </p>
        ) : null}

        {actual === null && !enDedicatoria ? (
          <section className="cubierta">
            <div className="cubierta-libro">
              <span className="antetitulo">Una novela de MyStoryMaker</span>
              <h1>{datos.titulo}</h1>
              {datos.destinatario && !datos.titulo.includes(datos.destinatario) ? (
                <p className="cubierta-para">Para {datos.destinatario}</p>
              ) : null}
              <span className="ornamento" aria-hidden="true">❦</span>
            </div>

            {aprobacion ? (
              <p className="sello-cubierta">
                <Icono nombre="sello" tamano={16} />
                Aprobada · versión {aprobacion.version_numero} · {fechaDeAprobacion(aprobacion)}
              </p>
            ) : null}

            <dl className="cubierta-datos">
              <div>
                <dt>Capítulos</dt>
                <dd>{total}</dd>
              </div>
              <div>
                <dt>Palabras</dt>
                <dd>{hayProsa ? texto.palabras.toLocaleString("es-ES") : "—"}</dd>
              </div>
              <div>
                <dt>Lectura</dt>
                <dd>{hayProsa ? `${minutosDeLectura(texto.palabras)} min` : "—"}</dd>
              </div>
            </dl>

            <div className="cubierta-acciones">
              {total === 0 ? (
                <p className="vacio">Esta novela todavía no tiene capítulos.</p>
              ) : (
                <button
                  className="boton principal grande"
                  onClick={() => {
                    if (ultimo > 0) irA(ultimo);
                    else if (hayDedicatoria) irADedicatoria();
                    else irA(0);
                  }}
                >
                  {ultimo > 0 ? `Seguir leyendo · ${tituloDe(ultimo)}` : "Empezar a leer"}
                  <Icono nombre="siguiente" tamano={18} />
                </button>
              )}
              {!hayProsa && !escribiendo && !aprobacion ? (
                <button className="boton secundario grande" onClick={() => setPanel("taller")}>
                  <Icono nombre="taller" tamano={18} /> Escribir la novela
                </button>
              ) : null}
            </div>
          </section>
        ) : enDedicatoria ? (
          <>
            <section className="pagina-dedicatoria" aria-label="Dedicatoria">
              <span className="ornamento" aria-hidden="true">❦</span>
              <p>{datos.dedicatoria}</p>
            </section>
            <nav className="paso-de-pagina" aria-label="Paso de página">
              <button className="tarjeta-paso" onClick={() => irA(null)}>
                <span className="antetitulo">
                  <Icono nombre="anterior" tamano={14} /> Cubierta
                </span>
                <span>{datos.titulo}</span>
              </button>
              {total > 0 ? (
                <button className="tarjeta-paso siguiente" onClick={() => irA(0)}>
                  <span className="antetitulo">
                    Siguiente <Icono nombre="siguiente" tamano={14} />
                  </span>
                  <span>{tituloDe(0)}</span>
                </button>
              ) : null}
            </nav>
          </>
        ) : actual === null ? null : (
          <>
            <CapituloLeido
              key={capitulos[actual].id}
              orden={capitulos[actual].orden}
              escrito={escritos.get(capitulos[actual].id)}
              escribiendo={escribiendo}
              cambiado={cambiados.includes(capitulos[actual].id)}
            />
            <nav className="paso-de-pagina" aria-label="Paso de capítulo">
              <button
                className="tarjeta-paso"
                onClick={() => {
                  if (actual > 0) irA(actual - 1);
                  else if (hayDedicatoria) irADedicatoria();
                  else irA(null);
                }}
              >
                <span className="antetitulo">
                  <Icono nombre="anterior" tamano={14} />{" "}
                  {actual > 0 ? "Anterior" : hayDedicatoria ? "Dedicatoria" : "Cubierta"}
                </span>
                <span>{actual > 0 ? tituloDe(actual - 1) : hayDedicatoria ? "Dedicatoria" : datos.titulo}</span>
              </button>
              {actual < total - 1 ? (
                <button className="tarjeta-paso siguiente" onClick={() => irA(actual + 1)}>
                  <span className="antetitulo">
                    Siguiente <Icono nombre="siguiente" tamano={14} />
                  </span>
                  <span>{tituloDe(actual + 1)}</span>
                </button>
              ) : (
                <FinDeLaNovela
                  aprobacion={aprobacion}
                  progreso={progreso}
                  alAprobar={() => void abrirAprobacion()}
                />
              )}
            </nav>
          </>
        )}
      </main>

      <Panel titulo="Índice" abierto={panel === "indice"} alCerrar={cerrarPanel}>
        {total === 0 ? (
          <p className="vacio">Esta novela todavía no tiene capítulos.</p>
        ) : (
          <ol className="lista-indice">
            {capitulos.map((capitulo, indice) => {
              const escrito = escritos.get(capitulo.id);
              return (
                <li key={capitulo.id}>
                  <button
                    className={indice === actual ? "actual" : undefined}
                    aria-current={indice === actual ? "page" : undefined}
                    onClick={() => {
                      irA(indice);
                      setPanel(null);
                    }}
                  >
                    <span className="indice-numero">{capitulo.orden}</span>
                    <span className="indice-titulo">
                      {tituloDe(indice)}
                      {cambiados.includes(capitulo.id) ? <span className="cambiado">cambiado</span> : null}
                    </span>
                    <span className="indice-meta">
                      {escrito && escrito.palabras > 0 ? `${minutosDeLectura(escrito.palabras)} min` : "sin prosa"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </Panel>

      <Panel titulo="Quién es quién" lado="derecha" abierto={panel === "ficha"} alCerrar={cerrarPanel}>
        <div className="pestanas" role="tablist">
          <button role="tab" aria-selected={pestanaFicha === "personajes"} onClick={() => setPestanaFicha("personajes")}>
            Personajes <span className="contador">{datos.personajes.length}</span>
          </button>
          <button role="tab" aria-selected={pestanaFicha === "lugares"} onClick={() => setPestanaFicha("lugares")}>
            Lugares <span className="contador">{datos.lugares.length}</span>
          </button>
        </div>
        {aprobacion && pestanaFicha === "personajes" ? (
          <p className="nota-bloqueo">{BLOQUEADA_POR_APROBACION}</p>
        ) : null}
        {(pestanaFicha === "personajes" ? datos.personajes : datos.lugares).length === 0 ? (
          <p className="vacio">La ficha se llena cuando la novela abre su canon.</p>
        ) : (
          <ul className="fichas">
            {(pestanaFicha === "personajes" ? datos.personajes : datos.lugares).map((entidad) => (
              <li key={entidad.id} className="ficha-entidad">
                <span className="inicial" aria-hidden="true">
                  {entidad.nombre_canonico.charAt(0).toUpperCase()}
                </span>
                <div>
                  <strong>{entidad.nombre_canonico}</strong>
                  <div className="ficha-acciones">
                    {total > 0 ? (
                      <button
                        className="enlace"
                        onClick={() => {
                          irA(0);
                          setPanel(null);
                        }}
                      >
                        Dónde aparece
                      </button>
                    ) : null}
                    {pestanaFicha === "personajes" ? (
                      <button
                        className="enlace"
                        disabled={aprobacion !== null}
                        title={aprobacion ? BLOQUEADA_POR_APROBACION : undefined}
                        onClick={() => setCambio({ id: entidad.id, nombre: entidad.nombre_canonico })}
                      >
                        Pedir un cambio
                      </button>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel titulo="Gastos" lado="derecha" ancho abierto={panel === "gastos"} alCerrar={cerrarPanel}>
        {/* Se vuelve a pedir cada vez que el sondeo trae una escena más (RF-LEC-23). */}
        <PanelDeGastos volumenId={volumenId} refresco={progreso?.escritas ?? 0} />
      </Panel>

      <Panel titulo="Taller" lado="derecha" abierto={panel === "taller"} alCerrar={cerrarPanel}>
        <Taller
          volumenId={volumenId}
          progreso={progreso}
          hayProsa={hayProsa}
          encargando={encargando}
          alEncargar={(modo) => void encargar(modo)}
          versiones={versiones}
          alNueva={alNueva}
          portada={{
            titulo: datos.titulo,
            dedicatoria: datos.dedicatoria,
            destinatario: datos.destinatario,
          }}
          alGuardarPortada={guardarPortada}
          aprobacion={aprobacion}
          bloqueo={BLOQUEADA_POR_APROBACION}
          alReabrir={() => setConfirmando("reabrir")}
          alEliminar={() => {
            setTituloEscrito("");
            setEliminando(true);
          }}
        />
      </Panel>

      <Dialogo titulo={cambio ? `Pedir un cambio sobre ${cambio.nombre}` : "Pedir un cambio"} abierto={cambio !== null} alCerrar={() => setCambio(null)}>
        <form
          className="dialogo-cuerpo"
          onSubmit={(e) => {
            e.preventDefault();
            void enviarCambio();
          }}
        >
          <label className="campo">
            <span>¿Qué hay que cambiar?</span>
            <textarea rows={4} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} autoFocus />
            <small>Se regeneran solo los capítulos en los que se usa este hecho.</small>
          </label>
          <div className="dialogo-acciones">
            <button type="button" className="boton fantasma" onClick={() => setCambio(null)}>
              Cancelar
            </button>
            <button type="submit" className="boton principal" disabled={!descripcion.trim()}>
              Pedir el cambio
            </button>
          </div>
        </form>
      </Dialogo>

      <Dialogo
        titulo={confirmando === "reabrir" ? "Reabrir la novela" : "Aprobar la novela"}
        abierto={confirmando !== null}
        alCerrar={() => {
          if (!firmando) setConfirmando(null);
        }}
      >
        <div className="dialogo-cuerpo">
          {confirmando === "aprobar" ? (
            <>
              <p className="dialogo-texto">
                Vas a firmar <strong>{datos.titulo}</strong> tal como está. Con tu firma se
                cierra el volumen, y la novela deja de poder reescribirse, cambiarse o
                retitularse hasta que la reabras.
              </p>
              <dl className="resumen-firma">
                <div>
                  <dt>Versión</dt>
                  <dd>{ultimaVersion ? `v${ultimaVersion.numero}` : "—"}</dd>
                </div>
                <div>
                  <dt>Capítulos</dt>
                  <dd>{total}</dd>
                </div>
                <div>
                  <dt>Palabras</dt>
                  <dd>{texto ? texto.palabras.toLocaleString("es-ES") : "—"}</dd>
                </div>
              </dl>
              {sinAceptar > 0 ? (
                <p className="aviso aviso-en-linea">
                  <Icono nombre="aviso" tamano={18} />
                  <span>
                    <strong>{sinAceptar} escena(s)</strong> tienen el borrador sin aceptar: las
                    comprobaciones automáticas no pudieron darlas por buenas, y quedan firmadas
                    tal como están.
                  </span>
                </p>
              ) : null}
            </>
          ) : (
            <p className="dialogo-texto">
              La aprobación de la versión {aprobacion?.version_numero} se retira —queda en el
              historial— y la novela vuelve a poder reescribirse, cambiarse y retitularse. Para
              darla por buena otra vez habrá que volver a aprobarla.
            </p>
          )}
          <div className="dialogo-acciones">
            <button
              type="button"
              className="boton fantasma"
              disabled={firmando}
              onClick={() => setConfirmando(null)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="boton principal"
              disabled={firmando}
              onClick={() => void firmar()}
              autoFocus
            >
              <Icono nombre={confirmando === "reabrir" ? "volver" : "sello"} tamano={16} />
              {firmando
                ? "Un momento…"
                : confirmando === "reabrir"
                  ? "Reabrir la novela"
                  : "Aprobar la novela"}
            </button>
          </div>
        </div>
      </Dialogo>

      <Dialogo
        titulo="Eliminar esta novela"
        abierto={eliminando}
        alCerrar={() => {
          if (!borrando) setEliminando(false);
        }}
      >
        <form
          className="dialogo-cuerpo"
          onSubmit={(e) => {
            e.preventDefault();
            if (tituloEscrito.trim() === datos.titulo.trim()) void confirmarEliminacion();
          }}
        >
          <p className="dialogo-texto">
            <strong>{datos.titulo}</strong> desaparecerá de la biblioteca y ya no se podrá
            abrir. Esto no se puede deshacer desde aquí.
          </p>
          <label className="campo">
            <span>Escribe el título para confirmar</span>
            <input
              value={tituloEscrito}
              onChange={(e) => setTituloEscrito(e.target.value)}
              placeholder={datos.titulo}
              autoComplete="off"
              autoFocus
            />
          </label>
          <div className="dialogo-acciones">
            <button
              type="button"
              className="boton fantasma"
              disabled={borrando}
              onClick={() => setEliminando(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="boton peligro"
              disabled={borrando || tituloEscrito.trim() !== datos.titulo.trim()}
            >
              <Icono nombre="papelera" tamano={16} />
              {borrando ? "Eliminando…" : "Eliminar"}
            </button>
          </div>
        </form>
      </Dialogo>
    </div>
  );
}

/** El final de la lectura: donde se firma la novela.
 *
 *  El botón aparece cuando el backend dice que la escritura está `escrita`; si no, se
 *  enseña su explicación. Si aprobar procede o no lo decide la ruta (RF-CON-04). */
function FinDeLaNovela({
  aprobacion,
  progreso,
  alAprobar,
}: {
  aprobacion: Aprobacion | null;
  progreso: ProgresoDeEscritura | null;
  alAprobar: () => void;
}) {
  if (aprobacion) {
    return (
      <div className="tarjeta-paso fin aprobada">
        <span className="antetitulo">
          <Icono nombre="sello" tamano={14} /> Fin · Aprobada
        </span>
        <span>
          Versión {aprobacion.version_numero}, aprobada el {fechaDeAprobacion(aprobacion)}.
        </span>
      </div>
    );
  }
  if (progreso?.estado === "escrita") {
    return (
      <div className="tarjeta-paso fin firmable">
        <span className="antetitulo">Fin</span>
        <span>¿Es la novela que querías regalar?</span>
        <button className="boton principal" onClick={alAprobar}>
          <Icono nombre="sello" tamano={16} /> Aprobar la novela
        </button>
      </div>
    );
  }
  return (
    <div className="tarjeta-paso fin">
      <span className="antetitulo">Fin</span>
      <span>{progreso?.detalle ?? "Has llegado al último capítulo."}</span>
    </div>
  );
}

/** El texto de un rechazo tal como lo redacta el backend, defectos incluidos. */
function motivoDelRechazo(error: unknown): string {
  if (!(error instanceof ErrorDeLectura)) return String(error);
  const detalle = error.detalle as RechazoDeAprobacion | string | undefined;
  if (typeof detalle === "string") return `No se ha podido: ${detalle}`;
  if (detalle && typeof detalle === "object" && "motivo" in detalle) {
    const defectos = detalle.defectos.map((d) => d.evidencia).join("; ");
    return `No se ha aprobado: ${detalle.motivo}${defectos ? ` — ${defectos}` : ""}`;
  }
  return error.message;
}
