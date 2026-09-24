import { useCallback, useEffect, useRef, useState } from "react";
import {
  ErrorDeLectura,
  escribirNovela,
  leerCapitulosDeVersion,
  leerNovela,
  leerProgreso,
  leerTexto,
  leerVersiones,
  pedirCambio,
  type CapituloConTexto,
  type CapituloDeVersion,
  type Lectura as DatosDeLectura,
  type ModoDeEscritura,
  type ProgresoDeEscritura,
  type TextoDeNovela,
  type VersionPublicada,
} from "../../shared/api/lectura";
import { ListaDeAvisos, useAvisos } from "../../shared/ui/Avisos";

type Estado =
  | { fase: "cargando" }
  | { fase: "error"; mensaje: string }
  | {
      fase: "lista";
      datos: DatosDeLectura;
      versiones: VersionPublicada[];
      cambiados: string[];
    };

/** Cada cuánto se vuelve a preguntar por el progreso mientras se escribe.
 *
 *  Se sondea, y no se abre el SSE de `/tareas/{id}/eventos`, porque ese flujo emite el
 *  historial ya registrado de **una** tarea y se cierra; lo que esta pantalla necesita es
 *  el estado de la novela entera mientras avanza. Cambiarlo es cosa del backend, y hasta
 *  entonces sondear cada dos segundos es honesto y barato.
 */
const CADA_CUANTO_MS = 2000;

/** La lectura de la novela: portada con dedicatoria, índice navegable, la prosa escrita,
 *  ficha de personajes y lugares enlazada a su capítulo, y marca de qué cambió. */
export function Lectura({
  volumenId,
  alVolver,
}: {
  volumenId: string;
  alVolver?: () => void;
}) {
  const [estado, setEstado] = useState<Estado>({ fase: "cargando" });
  const [progreso, setProgreso] = useState<ProgresoDeEscritura | null>(null);
  const [texto, setTexto] = useState<TextoDeNovela | null>(null);
  const [encargando, setEncargando] = useState(false);
  const { avisos, anadir, cerrar, limpiar } = useAvisos();
  const vigente = useRef(true);

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
  }, [volumenId]);

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

  if (estado.fase === "cargando") return <p className="medida">Abriendo la novela…</p>;

  // «No he podido leer» es distinto de «no hay nada»: confundirlos pinta un fallo de
  // lectura como una novela vacía, y nadie va a investigar una novela vacía.
  if (estado.fase === "error")
    return (
      <p className="medida error">
        No se ha podido leer la novela. El backend dijo: {estado.mensaje}
      </p>
    );

  const { datos, versiones, cambiados } = estado;
  const escribiendo = progreso !== null && enCurso(progreso.estado);

  async function solicitarCambio(hechoId: string) {
    const descripcion = window.prompt("¿Qué hay que cambiar?");
    if (!descripcion) return;
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
  }

  const primerCapitulo = datos.capitulos[0]?.id ?? "";
  const escritos = new Map((texto?.capitulos ?? []).map((c) => [c.id, c]));

  return (
    <div className="disposicion">
      <nav className="indice" aria-label="Índice de capítulos">
        <h2>Índice</h2>
        {datos.capitulos.length === 0 ? (
          <p className="vacio">Esta novela todavía no tiene capítulos.</p>
        ) : (
          datos.capitulos.map((capitulo) => {
            const escrito = escritos.get(capitulo.id);
            return (
              <a
                key={capitulo.id}
                href={`#${capitulo.id}`}
                className={cambiados.includes(capitulo.id) ? "cambiado" : undefined}
              >
                {capitulo.orden}. {escrito?.titulo || `Capítulo ${capitulo.orden}`}
              </a>
            );
          })
        )}

        <h2 style={{ marginTop: "2rem" }}>Escritura</h2>
        <PanelDeEscritura
          progreso={progreso}
          encargando={encargando}
          alEncargar={encargar}
        />

        {alVolver ? (
          <button onClick={alVolver} style={{ marginTop: "1.5rem" }}>
            Crear otro encargo
          </button>
        ) : null}

        <h2 style={{ marginTop: "2rem" }}>Versiones</h2>
        {versiones.length === 0 ? (
          <p className="vacio">Sin versiones publicadas.</p>
        ) : (
          versiones.map((version) => (
            <span key={version.id} style={{ display: "block" }}>
              v{version.numero} · {version.motivo || "sin motivo declarado"}
            </span>
          ))
        )}
      </nav>

      <main>
        <div className="medida">
          <ListaDeAvisos avisos={avisos} cerrar={cerrar} limpiar={limpiar} />

          {texto?.de_demostracion ? (
            <p className="marca-demostracion">
              Esta previa está escrita en <strong>modo demostración</strong>: la compone el
              sistema a partir del encargo, sin modelo. Queda marcada como tal en la
              procedencia de cada borrador y no debe confundirse con una novela escrita.
            </p>
          ) : null}

          <header className="portada">
            <h1>{datos.titulo}</h1>
            <p className="dedicatoria">{datos.dedicatoria}</p>
            {datos.destinatario ? (
              <p className="dedicatoria">Para {datos.destinatario}</p>
            ) : null}
            {texto && texto.palabras > 0 ? (
              <p className="dedicatoria">{texto.palabras.toLocaleString("es-ES")} palabras</p>
            ) : null}
          </header>

          {datos.capitulos.map((capitulo) => (
            <CapituloLeido
              key={capitulo.id}
              id={capitulo.id}
              orden={capitulo.orden}
              escrito={escritos.get(capitulo.id)}
              escribiendo={escribiendo}
            />
          ))}

          <section className="ficha" id="ficha">
            <h2>Quién es quién</h2>
            {datos.personajes.length === 0 ? (
              <p className="vacio">La ficha se llena cuando la novela abre su canon.</p>
            ) : null}
            <dl>
              {datos.personajes.map((personaje) => (
                <div key={personaje.id}>
                  <dt>{personaje.nombre_canonico}</dt>
                  <dd>
                    <a href={`#${primerCapitulo}`}>dónde aparece</a>{" "}
                    <button onClick={() => void solicitarCambio(personaje.id)}>
                      pedir un cambio
                    </button>
                  </dd>
                </div>
              ))}
            </dl>

            <h2>Lugares</h2>
            <dl>
              {datos.lugares.map((lugar) => (
                <div key={lugar.id}>
                  <dt>{lugar.nombre_canonico}</dt>
                  <dd>
                    <a href={`#${primerCapitulo}`}>dónde aparece</a>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </main>
    </div>
  );
}

/** Un capítulo tal como se lee: su prosa si la tiene, y si no, por qué no la tiene. */
function CapituloLeido({
  id,
  orden,
  escrito,
  escribiendo,
}: {
  id: string;
  orden: number;
  escrito?: CapituloConTexto;
  escribiendo: boolean;
}) {
  const escenas = escrito?.escenas ?? [];
  return (
    <article id={id}>
      <h2>
        {orden}. {escrito?.titulo || `Capítulo ${orden}`}
      </h2>

      {escenas.length === 0 ? (
        <p className="vacio">
          {escribiendo
            ? "Escribiéndose ahora mismo."
            : "Este capítulo todavía no tiene prosa. Pulsa «Escribir la novela»."}
        </p>
      ) : (
        escenas.map((escena, indice) => (
          <section className="escena" key={escena.id}>
            {indice > 0 ? <p className="separador">· · ·</p> : null}
            {escena.texto.split(/\n{2,}/).map((parrafo, numero) => (
              <p key={numero}>{parrafo.trim()}</p>
            ))}
            <p className={escena.aceptado ? "estado-borrador aceptado" : "estado-borrador"}>
              <strong>{escena.aceptado ? "Borrador aceptado" : "Borrador sin aceptar"}</strong>
              {escena.motivo ? ` · ${escena.motivo}` : null}
            </p>
          </section>
        ))
      )}
    </article>
  );
}

/** El botón de escribir y por dónde va. El estado y su explicación vienen del backend. */
function PanelDeEscritura({
  progreso,
  encargando,
  alEncargar,
}: {
  progreso: ProgresoDeEscritura | null;
  encargando: boolean;
  alEncargar: (modo: ModoDeEscritura) => void;
}) {
  const enMarcha = progreso !== null && enCurso(progreso.estado);

  return (
    <div className="escritura">
      <button
        className="principal"
        disabled={encargando || enMarcha}
        onClick={() => alEncargar("modelo")}
      >
        {enMarcha ? "Escribiendo…" : "Escribir la novela"}
      </button>
      <button disabled={encargando || enMarcha} onClick={() => alEncargar("demostracion")}>
        Escribir una muestra
      </button>

      {progreso ? (
        <>
          <p className="detalle">{progreso.detalle}</p>
          {progreso.totales > 0 ? (
            <p className="detalle">
              <progress value={progreso.escritas} max={progreso.totales} />{" "}
              {progreso.escritas}/{progreso.totales}
            </p>
          ) : null}
          {progreso.escenas
            .filter((escena) => escena.falta.length > 0)
            .map((escena) => (
              <p className="detalle error" key={escena.escena_id}>
                {escena.escena_id}: {escena.falta.join("; ")}
              </p>
            ))}
        </>
      ) : null}
    </div>
  );
}

/** Los dos estados en los que todavía queda trabajo. El conjunto es del backend; aquí
 *  solo se pregunta si hay que seguir sondeando. */
function enCurso(estado: string): boolean {
  return estado === "abriendo" || estado === "escribiendo";
}
