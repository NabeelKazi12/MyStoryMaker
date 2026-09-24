import { useEffect, useRef, type ReactNode } from "react";

/** Diálogo modal sobre `<dialog>`: el navegador ya encierra el foco y lo devuelve al
 *  cerrar. Escape se intercepta para que el cierre pase siempre por `alCerrar` y el
 *  estado de React no se quede creyendo que sigue abierto. */
export function Dialogo({
  titulo,
  abierto,
  alCerrar,
  children,
}: {
  titulo: string;
  abierto: boolean;
  alCerrar: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialogo = ref.current;
    if (!dialogo) return;
    if (abierto && !dialogo.open) dialogo.showModal();
    if (!abierto && dialogo.open) dialogo.close();
  }, [abierto]);

  return (
    <dialog
      ref={ref}
      className="dialogo"
      aria-label={titulo}
      onCancel={(evento) => {
        evento.preventDefault();
        alCerrar();
      }}
    >
      <h2>{titulo}</h2>
      {children}
    </dialog>
  );
}
