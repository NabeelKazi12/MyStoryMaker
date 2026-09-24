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
  // Una moneda: los gastos de la novela (SPEC-012).
  gastos: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6.5v11",
  // Una flecha que sale de una caja: abre en otra pestaña.
  externo: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  // Una papelera: eliminar la novela (SPEC-009).
  papelera: "M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3",
  // Una estantería con tres lomos: la biblioteca (SPEC-008).
  estante: "M4 4v16M9 4v16M14 6l4 14M3 20h18",
  // Un sello: círculo con la marca dentro. Es la firma de la novela (SPEC-007).
  sello: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM8 12l3 3 5-6",
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
