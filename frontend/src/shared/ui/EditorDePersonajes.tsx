import { useState } from "react";
import type { PapelDePersonaje, PersonajeDeclarado } from "../api/lectura";
import { Icono } from "./Icono";

export const NOMBRE_DEL_PAPEL: Record<PapelDePersonaje, string> = {
  protagonico: "Protagonista",
  secundario: "Secundario",
  ambiental: "De fondo",
};

const VACIO: PersonajeDeclarado = {
  nombre: "",
  papel: "secundario",
  relacion: "",
  descripcion: "",
  es_destinatario: false,
};

/** Los personajes de la novela, como fichas: la persona destinataria primero y fija, los
 *  demás con su formulario para añadir, editar y quitar (SPEC-011).
 *
 *  No valida nada: lo que se escribe se envía, y el backend dice qué personaje falla y por
 *  qué (RF-CON-08). `conFalta` marca las fichas que el backend nombró. */
export function EditorDePersonajes({
  destinataria,
  descripcionDeLaDestinataria,
  otros,
  alCambiarDescripcion,
  alCambiarOtros,
  bloqueado = false,
  conFalta = [],
}: {
  destinataria: string;
  descripcionDeLaDestinataria: string;
  otros: PersonajeDeclarado[];
  alCambiarDescripcion: (descripcion: string) => void;
  alCambiarOtros: (otros: PersonajeDeclarado[]) => void;
  bloqueado?: boolean;
  conFalta?: string[];
}) {
  // El índice que se edita, `nuevo` para uno que aún no está en la lista, o nada.
  const [editando, setEditando] = useState<number | "nuevo" | null>(null);
  const [borrador, setBorrador] = useState<PersonajeDeclarado>(VACIO);
  const [editandoDestinataria, setEditandoDestinataria] = useState(false);
  const [descripcion, setDescripcion] = useState(descripcionDeLaDestinataria);

  const falla = (nombre: string) =>
    conFalta.some((f) => f.trim().toLowerCase() === nombre.trim().toLowerCase());

  function abrir(indice: number | "nuevo") {
    setBorrador(indice === "nuevo" ? VACIO : otros[indice]);
    setEditando(indice);
  }

  function aplicar() {
    if (editando === "nuevo") alCambiarOtros([...otros, borrador]);
    else if (editando !== null) alCambiarOtros(otros.map((p, i) => (i === editando ? borrador : p)));
    setEditando(null);
  }

  return (
    <div className="editor-personajes">
      <ul className="fichas-personaje">
        <li className="ficha-personaje destinataria">
          <span className="inicial" aria-hidden="true">
            {(destinataria || "?").charAt(0).toUpperCase()}
          </span>
          <div className="ficha-personaje-cuerpo">
            <strong>{destinataria || "La persona destinataria"}</strong>
            <span className="ficha-personaje-meta">
              Protagonista · a quien va dedicada
            </span>
            {editandoDestinataria ? (
              <div className="formulario-personaje">
                <label className="campo">
                  <span>Descripción</span>
                  <textarea
                    rows={3}
                    value={descripcion}
                    onChange={(e) => setDescripcion(e.target.value)}
                    placeholder="Cómo es, qué la mueve… (opcional)"
                  />
                </label>
                <div className="formulario-acciones">
                  <button
                    type="button"
                    className="boton fantasma"
                    onClick={() => {
                      setDescripcion(descripcionDeLaDestinataria);
                      setEditandoDestinataria(false);
                    }}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    className="boton secundario"
                    onClick={() => {
                      alCambiarDescripcion(descripcion);
                      setEditandoDestinataria(false);
                    }}
                  >
                    Hecho
                  </button>
                </div>
              </div>
            ) : (
              <>
                {descripcionDeLaDestinataria ? (
                  <p className="ficha-personaje-texto">{descripcionDeLaDestinataria}</p>
                ) : null}
                {!bloqueado ? (
                  <button
                    type="button"
                    className="enlace"
                    onClick={() => {
                      setDescripcion(descripcionDeLaDestinataria);
                      setEditandoDestinataria(true);
                    }}
                  >
                    {descripcionDeLaDestinataria ? "Editar la descripción" : "Añadir una descripción"}
                  </button>
                ) : null}
              </>
            )}
          </div>
        </li>

        {otros.map((personaje, indice) =>
          editando === indice ? (
            <li key={indice} className="ficha-personaje editando">
              <FormularioDePersonaje
                personaje={borrador}
                alCambiar={setBorrador}
                alAplicar={aplicar}
                alCancelar={() => setEditando(null)}
                textoAplicar="Hecho"
              />
            </li>
          ) : (
            <li
              key={indice}
              className={`ficha-personaje${falla(personaje.nombre) ? " con-falta" : ""}`}
            >
              <span className="inicial" aria-hidden="true">
                {(personaje.nombre || "?").charAt(0).toUpperCase()}
              </span>
              <div className="ficha-personaje-cuerpo">
                <strong>
                  {personaje.nombre || <span className="vacio">Sin nombre</span>}
                  {falla(personaje.nombre) ? <em className="marca-falta">falta</em> : null}
                </strong>
                <span className="ficha-personaje-meta">
                  {NOMBRE_DEL_PAPEL[personaje.papel] ?? personaje.papel}
                  {personaje.relacion ? ` · ${personaje.relacion}` : ""}
                </span>
                {personaje.descripcion ? (
                  <p className="ficha-personaje-texto">{personaje.descripcion}</p>
                ) : null}
                {!bloqueado ? (
                  <div className="ficha-acciones">
                    <button type="button" className="enlace" onClick={() => abrir(indice)}>
                      Editar
                    </button>
                    <button
                      type="button"
                      className="enlace"
                      onClick={() => alCambiarOtros(otros.filter((_, i) => i !== indice))}
                    >
                      Quitar
                    </button>
                  </div>
                ) : null}
              </div>
            </li>
          ),
        )}
      </ul>

      {bloqueado ? null : editando === "nuevo" ? (
        <div className="ficha-personaje editando">
          <FormularioDePersonaje
            personaje={borrador}
            alCambiar={setBorrador}
            alAplicar={aplicar}
            alCancelar={() => setEditando(null)}
            textoAplicar="Añadir"
          />
        </div>
      ) : (
        <button
          type="button"
          className="boton secundario anadir-personaje"
          onClick={() => abrir("nuevo")}
          disabled={editando !== null}
        >
          <Icono nombre="mas" tamano={16} /> Añadir un personaje
        </button>
      )}
    </div>
  );
}

function FormularioDePersonaje({
  personaje,
  alCambiar,
  alAplicar,
  alCancelar,
  textoAplicar,
}: {
  personaje: PersonajeDeclarado;
  alCambiar: (personaje: PersonajeDeclarado) => void;
  alAplicar: () => void;
  alCancelar: () => void;
  textoAplicar: string;
}) {
  const poner = <K extends keyof PersonajeDeclarado>(campo: K, valor: PersonajeDeclarado[K]) =>
    alCambiar({ ...personaje, [campo]: valor });

  return (
    <div className="formulario-personaje">
      <div className="fila-dos">
        <label className="campo">
          <span>Nombre</span>
          <input
            value={personaje.nombre}
            onChange={(e) => poner("nombre", e.target.value)}
            placeholder="¿Cómo se llama?"
            autoFocus
          />
        </label>
        <div className="campo">
          <span>Papel</span>
          <div className="segmentado" role="group" aria-label="Papel en la novela">
            {(Object.keys(NOMBRE_DEL_PAPEL) as PapelDePersonaje[]).map((papel) => (
              <button
                type="button"
                key={papel}
                aria-pressed={personaje.papel === papel}
                onClick={() => poner("papel", papel)}
              >
                {NOMBRE_DEL_PAPEL[papel]}
              </button>
            ))}
          </div>
        </div>
      </div>
      <label className="campo">
        <span>Relación con la persona destinataria</span>
        <input
          value={personaje.relacion}
          onChange={(e) => poner("relacion", e.target.value)}
          placeholder="Su hermana, su mejor amigo, su perro…"
        />
      </label>
      <label className="campo">
        <span>Descripción</span>
        <textarea
          rows={3}
          value={personaje.descripcion}
          onChange={(e) => poner("descripcion", e.target.value)}
          placeholder="Cómo es, qué papel juega en su vida… (opcional)"
        />
      </label>
      <div className="formulario-acciones">
        <button type="button" className="boton fantasma" onClick={alCancelar}>
          Cancelar
        </button>
        <button type="button" className="boton secundario" onClick={alAplicar}>
          {textoAplicar}
        </button>
      </div>
    </div>
  );
}
