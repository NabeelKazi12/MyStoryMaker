import { useEffect, useState } from "react";
import {
  ErrorDeLectura,
  guardarPersonajes,
  leerPersonajes,
  urlDelPdf,
  type Aprobacion,
  type EntrevistaFallida,
  type ModoDeEscritura,
  type PersonajeDeclarado,
  type ProgresoDeEscritura,
  type VersionPublicada,
} from "../../shared/api/lectura";
import { EditorDePersonajes } from "../../shared/ui/EditorDePersonajes";
import { Icono } from "../../shared/ui/Icono";
import { enCurso } from "./enCurso";

/** Lo que se puede cambiar de cómo se presenta la novela: título y dedicatoria. */
export interface DatosDePortada {
  titulo: string;
  dedicatoria: string;
  destinatario: string;
}

/** Todo lo que no es leer: pedir la escritura, ver por dónde va, el título y la portada,
 *  descargar el PDF, las versiones y volver a la entrevista. El estado y su explicación
 *  vienen del backend. */
export function Taller({
  volumenId,
  progreso,
  hayProsa,
  encargando,
  alEncargar,
  versiones,
  alNueva,
  portada,
  alGuardarPortada,
  aprobacion,
  bloqueo,
  alReabrir,
  alEliminar,
}: {
  volumenId: string;
  progreso: ProgresoDeEscritura | null;
  hayProsa: boolean;
  encargando: boolean;
  alEncargar: (modo: ModoDeEscritura) => void;
  versiones: VersionPublicada[];
  alNueva: () => void;
  portada: DatosDePortada;
  alGuardarPortada: (cambios: { titulo?: string; dedicatoria?: string }) => Promise<void>;
  /** La aprobación vigente. Con ella, escribir y editar la portada quedan desactivados. */
  aprobacion: Aprobacion | null;
  /** Por qué, en una línea: la pantalla lo enseña junto a lo que desactiva. */
  bloqueo: string;
  alReabrir: () => void;
  /** Abre la confirmación de «Eliminar esta novela» (SPEC-009). */
  alEliminar: () => void;
}) {
  const enMarcha = progreso !== null && enCurso(progreso.estado);
  const aprobada = aprobacion !== null;
  // Por qué no se puede eliminar ahora, según el estado que da el backend. Si se intenta
  // igual, el `409` de la ruta es el que manda (RF-CON-06).
  const sinEliminar = aprobada
    ? "Está aprobada: reábrela antes de eliminarla."
    : enMarcha
      ? "Se está escribiendo: espera a que termine o se detenga para eliminarla."
      : null;
  const porcentaje =
    progreso && progreso.totales > 0 ? Math.round((progreso.escritas / progreso.totales) * 100) : 0;

  return (
    <div className="taller">
      {aprobacion ? (
        <section className="taller-bloque bloque-aprobada">
          <h3>Aprobación</h3>
          <p className="sello-cubierta">
            <Icono nombre="sello" tamano={16} />
            Aprobada · versión {aprobacion.version_numero}
          </p>
          <p className="detalle">{bloqueo}</p>
          <button className="boton secundario" onClick={alReabrir}>
            <Icono nombre="volver" tamano={16} /> Reabrir la novela
          </button>
        </section>
      ) : null}

      <section className="taller-bloque">
        <h3>Escritura</h3>
        <div className="escritura">
          <button
            className="boton principal"
            disabled={encargando || enMarcha || aprobada}
            title={aprobada ? bloqueo : undefined}
            onClick={() => alEncargar("modelo")}
          >
            <Icono nombre="taller" tamano={16} />
            {enMarcha ? "Escribiendo…" : "Escribir la novela"}
          </button>
          <button
            className="boton secundario"
            disabled={encargando || enMarcha || aprobada}
            title={aprobada ? bloqueo : undefined}
            onClick={() => alEncargar("demostracion")}
          >
            Escribir una muestra
          </button>
        </div>

        {progreso ? (
          <div className="progreso-escritura">
            {progreso.totales > 0 ? (
              <>
                <div className="progreso-cifras">
                  <span>
                    {progreso.escritas} de {progreso.totales} escenas
                  </span>
                  <span>{porcentaje}%</span>
                </div>
                <div
                  className={`barra ${enMarcha ? "viva" : ""}`}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={progreso.totales}
                  aria-valuenow={progreso.escritas}
                  aria-label="Escenas escritas"
                >
                  <span style={{ width: `${porcentaje}%` }} />
                </div>
              </>
            ) : null}
            <p className="detalle">{progreso.detalle}</p>
            {progreso.escenas
              .filter((escena) => escena.falta.length > 0)
              .map((escena) => (
                <p className="detalle error" key={escena.escena_id}>
                  {escena.escena_id}: {escena.falta.join("; ")}
                </p>
              ))}
          </div>
        ) : null}
      </section>

      <BloqueDePersonajes
        volumenId={volumenId}
        bloqueo={
          aprobada
            ? bloqueo
            : progreso === null
              ? "Comprobando si la escritura ha empezado…"
              : progreso.estado !== "sin_empezar"
                ? "La escritura ya ha empezado: los personajes están en la novela. Para cambiar uno, pide un cambio desde «Quién es quién»."
                : null
        }
      />

      <BloqueDePortada
        portada={portada}
        alGuardar={alGuardarPortada}
        bloqueo={aprobada ? bloqueo : null}
      />

      {hayProsa ? (
        <section className="taller-bloque">
          <h3>Descargar</h3>
          <a className="boton secundario" href={urlDelPdf(volumenId)} download>
            <Icono nombre="descargar" tamano={16} />
            {enMarcha ? "Lo escrito hasta ahora (PDF)" : "La novela en PDF"}
          </a>
        </section>
      ) : null}

      <section className="taller-bloque">
        <h3>Versiones</h3>
        {versiones.length === 0 ? (
          <p className="vacio">Sin versiones publicadas.</p>
        ) : (
          <ol className="versiones">
            {versiones.map((version) => (
              <li key={version.id}>
                <span className="version-numero">v{version.numero}</span>
                <span>{version.motivo || "sin motivo declarado"}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="taller-bloque">
        <button className="boton fantasma" onClick={alNueva}>
          <Icono nombre="mas" tamano={16} /> Nueva novela
        </button>
      </section>

      <section className="taller-bloque bloque-peligro">
        <h3>Eliminar esta novela</h3>
        <p className="detalle">
          {sinEliminar ?? "Desaparece de la biblioteca y no se puede recuperar desde aquí."}
        </p>
        <button
          className="boton peligro"
          disabled={sinEliminar !== null}
          title={sinEliminar ?? undefined}
          onClick={alEliminar}
        >
          <Icono nombre="papelera" tamano={16} /> Eliminar esta novela
        </button>
      </section>
    </div>
  );
}

/** Título y dedicatoria, con la portada y la página de dedicatoria tal como van a quedar.
 *
 *  La vista previa usa la misma cubierta que la lectura: una previa en texto plano no
 *  enseña cómo queda, que es lo único que se quiere saber antes de guardar. No se valida
 *  nada aquí: lo que se escribe se envía, y el backend dice si cabe (SPEC-006 RF-TAL-02). */
function BloqueDePortada({
  portada,
  alGuardar,
  bloqueo,
}: {
  portada: DatosDePortada;
  alGuardar: (cambios: { titulo?: string; dedicatoria?: string }) => Promise<void>;
  /** Si la novela está aprobada, por qué no se puede guardar; si no, `null`. */
  bloqueo: string | null;
}) {
  const [titulo, setTitulo] = useState(portada.titulo);
  const [dedicatoria, setDedicatoria] = useState(portada.dedicatoria);
  const [guardando, setGuardando] = useState(false);

  // Lo guardado es la nueva referencia: tras guardar, «sin cambios» vuelve a ser cierto.
  useEffect(() => {
    setTitulo(portada.titulo);
    setDedicatoria(portada.dedicatoria);
  }, [portada.titulo, portada.dedicatoria]);

  const cambios: { titulo?: string; dedicatoria?: string } = {};
  if (titulo !== portada.titulo) cambios.titulo = titulo;
  if (dedicatoria !== portada.dedicatoria) cambios.dedicatoria = dedicatoria;
  const hayCambios = Object.keys(cambios).length > 0;

  const para =
    portada.destinatario && !titulo.includes(portada.destinatario)
      ? `Para ${portada.destinatario}`
      : "";

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    setGuardando(true);
    try {
      await alGuardar(cambios);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section className="taller-bloque">
      <h3>Título y portada</h3>

      <div className="portada-previa" aria-label="Vista previa de la portada y la dedicatoria">
        <div className="cubierta-libro previa">
          <span className="antetitulo">Una novela de MyStoryMaker</span>
          <strong className="previa-titulo">{titulo.trim() || "Sin título"}</strong>
          <span className="ornamento" aria-hidden="true">❦</span>
          {para ? <span className="cubierta-para">{para}</span> : null}
        </div>
        <div className="pagina-previa">
          {dedicatoria.trim() ? (
            <em>{dedicatoria.trim()}</em>
          ) : (
            <span className="vacio">Sin dedicatoria: esta página no aparecerá.</span>
          )}
        </div>
      </div>

      <form className="formulario-portada" onSubmit={(e) => void guardar(e)}>
        <label className="campo">
          <span>Título</span>
          <input value={titulo} onChange={(e) => setTitulo(e.target.value)} disabled={bloqueo !== null} />
        </label>
        <label className="campo">
          <span>Dedicatoria</span>
          <textarea
            rows={3}
            value={dedicatoria}
            onChange={(e) => setDedicatoria(e.target.value)}
            disabled={bloqueo !== null}
          />
          <small>{bloqueo ?? "Va sola en la primera página, detrás de la portada."}</small>
        </label>
        <button
          className="boton principal"
          type="submit"
          disabled={guardando || !hayCambios || bloqueo !== null}
        >
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </section>
  );
}

/** Los personajes declarados (SPEC-011): se editan mientras la escritura no ha empezado.
 *
 *  `bloqueo` dice por qué no se pueden editar, según el estado que da el backend; si se
 *  intenta igual, manda su `409`. Los problemas de un personaje los redacta el backend y
 *  se enseñan aquí mismo, sin cerrarse solos. */
function BloqueDePersonajes({ volumenId, bloqueo }: { volumenId: string; bloqueo: string | null }) {
  const [guardados, setGuardados] = useState<PersonajeDeclarado[] | null>(null);
  const [otros, setOtros] = useState<PersonajeDeclarado[]>([]);
  const [descripcion, setDescripcion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState<{ error: boolean; texto: string } | null>(null);
  const [conFalta, setConFalta] = useState<string[]>([]);

  function poner(lista: PersonajeDeclarado[]) {
    setGuardados(lista);
    setOtros(lista.filter((p) => !p.es_destinatario));
    setDescripcion(lista.find((p) => p.es_destinatario)?.descripcion ?? "");
  }

  useEffect(() => {
    let vigente = true;
    leerPersonajes(volumenId)
      .then((r) => {
        if (vigente) poner(r.personajes);
      })
      .catch((error: unknown) => {
        if (vigente)
          setMensaje({
            error: true,
            texto: `No se han podido leer los personajes: ${error instanceof Error ? error.message : String(error)}`,
          });
      });
    return () => {
      vigente = false;
    };
  }, [volumenId]);

  if (guardados === null)
    return (
      <section className="taller-bloque">
        <h3>Personajes</h3>
        <p className={mensaje?.error ? "detalle error" : "detalle"}>
          {mensaje?.texto ?? "Leyendo los personajes…"}
        </p>
      </section>
    );

  const destinataria = guardados.find((p) => p.es_destinatario);

  // Una novela de antes de SPEC-011 no tiene personajes declarados: se dice, sin inventarlos.
  if (!destinataria)
    return (
      <section className="taller-bloque">
        <h3>Personajes</h3>
        <p className="detalle">
          Esta novela se encargó antes de poder declarar personajes: los eligió el Planner.
          Están en «Quién es quién».
        </p>
      </section>
    );

  const original = guardados.filter((p) => !p.es_destinatario);
  const hayCambios =
    descripcion !== destinataria.descripcion || JSON.stringify(otros) !== JSON.stringify(original);

  async function guardar() {
    setGuardando(true);
    setMensaje(null);
    setConFalta([]);
    try {
      const r = await guardarPersonajes(volumenId, [{ ...destinataria!, descripcion }, ...otros]);
      poner(r.personajes);
      setMensaje({ error: false, texto: "Personajes guardados. El Planner los usará al escribir." });
    } catch (error) {
      if (error instanceof ErrorDeLectura && error.estado === 422) {
        const detalle = error.detalle as EntrevistaFallida;
        const choques = detalle?.contradicciones ?? [];
        setConFalta(choques.filter((c) => c.campos[0] === "personajes").map((c) => c.campos[1]));
        setMensaje({ error: true, texto: `No se han guardado: ${choques.map((c) => c.detalle).join("; ")}` });
      } else {
        setMensaje({
          error: true,
          texto: `No se han guardado: ${error instanceof ErrorDeLectura ? String(error.detalle ?? error.message) : String(error)}`,
        });
      }
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section className="taller-bloque">
      <h3>Personajes</h3>
      {bloqueo ? <p className="detalle">{bloqueo}</p> : null}
      <EditorDePersonajes
        key={JSON.stringify(guardados)}
        destinataria={destinataria.nombre}
        descripcionDeLaDestinataria={descripcion}
        otros={otros}
        alCambiarDescripcion={setDescripcion}
        alCambiarOtros={setOtros}
        bloqueado={bloqueo !== null}
        conFalta={conFalta}
      />
      {mensaje ? (
        <p className={mensaje.error ? "detalle error" : "detalle"} role="status">
          {mensaje.texto}
        </p>
      ) : null}
      {bloqueo === null ? (
        <button
          className="boton principal"
          onClick={() => void guardar()}
          disabled={guardando || !hayCambios}
        >
          {guardando ? "Guardando…" : "Guardar los personajes"}
        </button>
      ) : null}
    </section>
  );
}
