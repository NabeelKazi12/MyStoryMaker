import { useEffect, useRef, type ReactNode } from "react";
import { Icono } from "./Icono";

/** Panel lateral. Se abre a petición y se cierra solo por su botón o por Escape: pulsar
 *  fuera no lo cierra, porque perder un panel por un clic de más obliga a buscar otra vez
 *  lo que se estaba mirando. */
export function Panel({
  titulo,
  lado = "izquierda",
  ancho = false,
  abierto,
  alCerrar,
  children,
}: {
  titulo: string;
  lado?: "izquierda" | "derecha";
  /** Para contenido tabular, como los gastos: el panel estrecho parte las filas. */
  ancho?: boolean;
  abierto: boolean;
  alCerrar: () => void;
  children: ReactNode;
}) {
  const cierre = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const previo = document.activeElement as HTMLElement | null;
    cierre.current?.focus();
    const alTeclear = (evento: KeyboardEvent) => {
      // Con un diálogo abierto, Escape es suyo: cerraría los dos de una vez.
      if (evento.key === "Escape" && !document.querySelector("dialog[open]")) alCerrar();
    };
    window.addEventListener("keydown", alTeclear);
    return () => {
      window.removeEventListener("keydown", alTeclear);
      previo?.focus?.();
    };
  }, [abierto, alCerrar]);

  if (!abierto) return null;
  return (
    <>
      <div className="velo" aria-hidden="true" />
      <aside className={`panel panel-${lado}${ancho ? " panel-ancho" : ""}`} role="dialog" aria-modal="false" aria-label={titulo}>
        <header className="panel-cabecera">
          <h2>{titulo}</h2>
          <button ref={cierre} className="boton-icono" onClick={alCerrar} aria-label={`Cerrar ${titulo}`}>
            <Icono nombre="cerrar" />
          </button>
        </header>
        <div className="panel-cuerpo">{children}</div>
      </aside>
    </>
  );
}
