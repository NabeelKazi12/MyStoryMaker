import { useCallback, useEffect, useRef, useState } from "react";
import {
  ErrorDeLectura,
  leerBiblioteca,
  type NovelaDeBiblioteca,
} from "../../shared/api/lectura";
import { Icono } from "../../shared/ui/Icono";

type Estado =
  | { fase: "cargando" }
  | { fase: "error"; mensaje: string }
  | { fase: "lista"; novelas: NovelaDeBiblioteca[] };

/** El nombre de cada estado de escritura, para la etiqueta de la cubierta. El estado lo
 *  decide el backend; aquí solo se le pone nombre, y uno desconocido se enseña tal cual. */
const NOMBRE_DEL_ESTADO: Record<string, string> = {
  sin_empezar: "Sin escribir",
  abriendo: "Abriéndose",
  escribiendo: "Escribiéndose",
  escrita: "Escrita",
  detenida: "Detenida",
  fallida: "No se pudo abrir",
};

/** La biblioteca: las novelas encargadas, como una estantería de cubiertas.
 *
 *  Es la pantalla de inicio cuando hay alguna novela (SPEC-008). Sin ninguna, avisa con
 *  `alVacia` y la aplicación abre la entrevista, como antes. La lista se pide cada vez que
 *  se entra: al volver de una lectura, el título y el estado tienen que ser los de ahora. */
export function Biblioteca({
  alAbrir,
  alNueva,
  alVacia,
}: {
  alAbrir: (volumenId: string) => void;
  alNueva: () => void;
  alVacia: () => void;
}) {
  const [estado, setEstado] = useState<Estado>({ fase: "cargando" });
  const vigente = useRef(true);

  const cargar = useCallback(async () => {
    setEstado({ fase: "cargando" });
    try {
      const novelas = await leerBiblioteca();
      if (!vigente.current) return;
      if (novelas.length === 0) {
        alVacia();
        return;
      }
      setEstado({ fase: "lista", novelas });
    } catch (error) {
      if (!vigente.current) return;
      setEstado({
        fase: "error",
        mensaje: error instanceof ErrorDeLectura ? error.message : String(error),
      });
    }
  }, [alVacia]);

  useEffect(() => {
    vigente.current = true;
    void cargar();
    return () => {
      vigente.current = false;
    };
  }, [cargar]);

  return (
    <div className="biblioteca">
      <header className="biblioteca-cabecera">
        <p className="marca-app">
          <Icono nombre="libro" /> MyStoryMaker
        </p>
        <button className="boton principal" onClick={alNueva}>
          <Icono nombre="mas" tamano={16} /> Nueva novela
        </button>
      </header>

      <main className="biblioteca-cuerpo">
        <div className="biblioteca-titular">
          <span className="antetitulo">Tu biblioteca</span>
          <h1>Las novelas que has encargado</h1>
        </div>

        {estado.fase === "cargando" ? (
          <div className="pantalla-centrada biblioteca-estado">
            <div className="cargando" aria-hidden="true" />
            <p>Abriendo la biblioteca…</p>
          </div>
        ) : estado.fase === "error" ? (
          // «No he podido leer» es distinto de «no hay nada» (RF-BIB-09): con el fallo a la
          // vista, y sin cerrar el camino a una novela nueva.
          <div className="tarjeta biblioteca-estado">
            <p className="error">No se ha podido leer la biblioteca. El backend dijo: {estado.mensaje}</p>
            <div className="cubierta-acciones">
              <button className="boton principal" onClick={() => void cargar()}>
                Reintentar
              </button>
              <button className="boton secundario" onClick={alNueva}>
                <Icono nombre="mas" tamano={16} /> Nueva novela
              </button>
            </div>
          </div>
        ) : (
          <ul className="estanteria">
            {estado.novelas.map((novela) => (
              <li key={novela.volumen_id}>
                <button
                  className="libro-de-estante"
                  onClick={() => alAbrir(novela.volumen_id)}
                  aria-label={`Abrir ${novela.titulo}`}
                >
                  <span className="cubierta-libro estante">
                    <span className="antetitulo">Una novela de MyStoryMaker</span>
                    <strong className="estante-titulo">{novela.titulo}</strong>
                    {novela.destinatario && !novela.titulo.includes(novela.destinatario) ? (
                      <span className="cubierta-para">Para {novela.destinatario}</span>
                    ) : null}
                    <span className="ornamento" aria-hidden="true">❦</span>
                  </span>
                  <span className="estante-ficha">
                    <span className="estante-etiquetas">
                      {novela.aprobacion ? (
                        <span className="sello-aprobada estatico">
                          <Icono nombre="sello" tamano={13} /> Aprobada · v
                          {novela.aprobacion.version_numero}
                        </span>
                      ) : (
                        <span className={`chip-estado estado-${novela.estado}`}>
                          {NOMBRE_DEL_ESTADO[novela.estado] ?? novela.estado}
                        </span>
                      )}
                    </span>
                    <span className="estante-detalle">{novela.detalle}</span>
                    <span className="estante-cifras">
                      {novela.capitulos} {novela.capitulos === 1 ? "capítulo" : "capítulos"}
                      {novela.palabras > 0
                        ? ` · ${novela.palabras.toLocaleString("es-ES")} palabras`
                        : ""}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
