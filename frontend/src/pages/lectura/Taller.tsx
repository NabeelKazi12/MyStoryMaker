import { useEffect, useState } from "react";
import {
  urlDelPdf,
  type ModoDeEscritura,
  type ProgresoDeEscritura,
  type VersionPublicada,
} from "../../shared/api/lectura";
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
  alVolver,
  portada,
  alGuardarPortada,
}: {
  volumenId: string;
  progreso: ProgresoDeEscritura | null;
  hayProsa: boolean;
  encargando: boolean;
  alEncargar: (modo: ModoDeEscritura) => void;
  versiones: VersionPublicada[];
  alVolver?: () => void;
  portada: DatosDePortada;
  alGuardarPortada: (cambios: { titulo?: string; dedicatoria?: string }) => Promise<void>;
}) {
  const enMarcha = progreso !== null && enCurso(progreso.estado);
  const porcentaje =
    progreso && progreso.totales > 0 ? Math.round((progreso.escritas / progreso.totales) * 100) : 0;

  return (
    <div className="taller">
      <section className="taller-bloque">
        <h3>Escritura</h3>
        <div className="escritura">
          <button
            className="boton principal"
            disabled={encargando || enMarcha}
            onClick={() => alEncargar("modelo")}
          >
            <Icono nombre="taller" tamano={16} />
            {enMarcha ? "Escribiendo…" : "Escribir la novela"}
          </button>
          <button
            className="boton secundario"
            disabled={encargando || enMarcha}
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

      <BloqueDePortada portada={portada} alGuardar={alGuardarPortada} />

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

      {alVolver ? (
        <section className="taller-bloque">
          <button className="boton fantasma" onClick={alVolver}>
            <Icono nombre="volver" tamano={16} /> Crear otro encargo
          </button>
        </section>
      ) : null}
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
}: {
  portada: DatosDePortada;
  alGuardar: (cambios: { titulo?: string; dedicatoria?: string }) => Promise<void>;
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
          <input value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </label>
        <label className="campo">
          <span>Dedicatoria</span>
          <textarea rows={3} value={dedicatoria} onChange={(e) => setDedicatoria(e.target.value)} />
          <small>Va sola en la primera página, detrás de la portada.</small>
        </label>
        <button className="boton principal" type="submit" disabled={guardando || !hayCambios}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </section>
  );
}
