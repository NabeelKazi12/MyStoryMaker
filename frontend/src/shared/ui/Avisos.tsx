import { useState, useCallback } from "react";

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
    <section aria-live="polite">
      {avisos.map((aviso) => (
        <div className="aviso" key={aviso.id}>
          <span>{aviso.texto}</span>
          <button onClick={() => cerrar(aviso.id)} aria-label="cerrar aviso">
            cerrar
          </button>
        </div>
      ))}
      {avisos.length > 1 && <button onClick={limpiar}>limpiar todo</button>}
    </section>
  );
}
