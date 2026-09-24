import { useState, useCallback } from "react";
import { Icono } from "./Icono";

export interface Aviso {
  id: string;
  texto: string;
}

/** Avisos que **no** se autodestruyen: decidir cuándo se ha terminado de leer algo es de
 *  quien lee, no de un temporizador. Hay cierre por aviso y un «limpiar todo». */
export function useAvisos() {
  const [avisos, setAvisos] = useState<Aviso[]>([]);

  const anadir = useCallback((texto: string) => {
    setAvisos((previos) => [...previos, { id: `${Date.now()}-${previos.length}`, texto }]);
  }, []);
  const cerrar = useCallback((id: string) => {
    setAvisos((previos) => previos.filter((a) => a.id !== id));
  }, []);
  const limpiar = useCallback(() => setAvisos([]), []);

  return { avisos, anadir, cerrar, limpiar };
}

export function ListaDeAvisos({
  avisos,
  cerrar,
  limpiar,
}: {
  avisos: Aviso[];
  cerrar: (id: string) => void;
  limpiar: () => void;
}) {
  if (avisos.length === 0) return null;
  return (
    <section className="avisos" aria-live="polite" aria-label="Avisos">
      {avisos.map((aviso) => (
        <div className="aviso" key={aviso.id}>
          <Icono nombre="aviso" tamano={18} />
          <span>{aviso.texto}</span>
          <button className="boton-icono" onClick={() => cerrar(aviso.id)} aria-label="Cerrar aviso">
            <Icono nombre="cerrar" tamano={16} />
          </button>
        </div>
      ))}
      {avisos.length > 1 ? (
        <button className="boton secundario limpiar" onClick={limpiar}>
          Limpiar todo
        </button>
      ) : null}
    </section>
  );
}
