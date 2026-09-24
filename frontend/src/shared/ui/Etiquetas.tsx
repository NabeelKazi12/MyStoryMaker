import { useId, useState } from "react";
import { Icono } from "./Icono";

/** Una lista que se escribe elemento a elemento: se añade con Intro o con el botón y se
 *  quita con el aspa. Sustituye al «uno por línea», que obligaba a leer una instrucción
 *  para rellenar un campo. No filtra nada: lo que se añade se envía tal cual. */
export function Etiquetas({
  etiqueta,
  valores,
  alCambiar,
  sugerencia,
  falta,
  forma = "fichas",
}: {
  etiqueta: string;
  valores: string[];
  alCambiar: (valores: string[]) => void;
  sugerencia?: string;
  falta?: boolean;
  /** `fichas` para palabras sueltas; `lista` para frases largas, como un recuerdo. */
  forma?: "fichas" | "lista";
}) {
  const [borrador, setBorrador] = useState("");
  const id = useId();

  function anadir() {
    const limpio = borrador.trim();
    if (!limpio) return;
    alCambiar([...valores, limpio]);
    setBorrador("");
  }

  return (
    <div className={`campo ${falta ? "con-falta" : ""}`}>
      <label htmlFor={id}>
        {etiqueta} {falta ? <em className="marca-falta">falta</em> : null}
      </label>
      {valores.length > 0 ? (
        <ul className={`etiquetas etiquetas-${forma}`}>
          {valores.map((valor, indice) => (
            <li key={`${indice}-${valor}`}>
              <span>{valor}</span>
              <button
                type="button"
                className="boton-icono"
                onClick={() => alCambiar(valores.filter((_, i) => i !== indice))}
                aria-label={`Quitar «${valor}»`}
              >
                <Icono nombre="cerrar" tamano={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="etiquetas-entrada">
        <input
          id={id}
          value={borrador}
          placeholder={sugerencia}
          onChange={(e) => setBorrador(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              // Intro añade la etiqueta; no envía el formulario.
              e.preventDefault();
              anadir();
            }
          }}
        />
        <button type="button" className="boton secundario" onClick={anadir} disabled={!borrador.trim()}>
          <Icono nombre="mas" tamano={16} /> Añadir
        </button>
      </div>
    </div>
  );
}
