import type { CapituloConTexto } from "../../shared/api/lectura";
import { minutosDeLectura } from "./enCurso";

/** Un capítulo tal como se lee: su prosa si la tiene, y si no, por qué no la tiene. La
 *  marca de borrador va al pie de cada escena y no depende del tema: no es cosmética. */
export function CapituloLeido({
  orden,
  escrito,
  escribiendo,
  cambiado,
}: {
  orden: number;
  escrito?: CapituloConTexto;
  escribiendo: boolean;
  cambiado: boolean;
}) {
  const escenas = escrito?.escenas ?? [];
  return (
    <article className="capitulo">
      <header className="capitulo-cabecera">
        <span className="antetitulo">
          Capítulo {orden}
          {cambiado ? <span className="cambiado">cambiado</span> : null}
        </span>
        <h1>{escrito?.titulo || `Capítulo ${orden}`}</h1>
        {escrito && escrito.palabras > 0 ? (
          <p className="capitulo-meta">
            {escrito.palabras.toLocaleString("es-ES")} palabras · {minutosDeLectura(escrito.palabras)} min de lectura
          </p>
        ) : null}
        <span className="ornamento" aria-hidden="true">❦</span>
      </header>

      {escenas.length === 0 ? (
        <p className="vacio capitulo-vacio">
          {escribiendo
            ? "Este capítulo se está escribiendo ahora mismo."
            : "Este capítulo todavía no tiene prosa. Ábrela desde el taller con «Escribir la novela»."}
        </p>
      ) : (
        escenas.map((escena, indice) => (
          <section className="escena" key={escena.id}>
            {indice > 0 ? <p className="separador" aria-hidden="true">⁂</p> : null}
            <div className="prosa">
              {escena.texto.split(/\n{2,}/).map((parrafo, numero) => (
                <p key={numero}>{parrafo.trim()}</p>
              ))}
            </div>
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
