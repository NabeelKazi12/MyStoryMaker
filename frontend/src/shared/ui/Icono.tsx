// Iconos de trazo en línea. Pocos y dibujados aquí: una librería de iconos entera para
// una docena de glifos es una dependencia que no paga su peso.

const TRAZOS = {
  indice: "M4 6h16M4 12h16M4 18h10",
  ficha: "M16 19v-1a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v1M10 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6M20 19v-1a4 4 0 0 0-3-3.9M16 4.1a3 3 0 0 1 0 5.8",
  taller: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z",
  cerrar: "M6 6l12 12M18 6 6 18",
  anterior: "M15 18l-6-6 6-6",
  siguiente: "M9 18l6-6-6-6",
  descargar: "M12 4v11M7 10l5 5 5-5M5 20h14",
  libro: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2ZM4 21V5M8 7h7",
  mas: "M12 5v14M5 12h14",
  volver: "M10 19l-7-7 7-7M3 12h18",
  aviso: "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
} as const;

export type NombreDeIcono = keyof typeof TRAZOS;

export function Icono({ nombre, tamano = 20 }: { nombre: NombreDeIcono; tamano?: number }) {
  return (
    <svg
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={TRAZOS[nombre]} />
    </svg>
  );
}
