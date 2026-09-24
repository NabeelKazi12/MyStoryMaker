import { useCallback, useEffect, useState } from "react";
import { guardar, recordar } from "./almacen";

/** Cómo quiere leer quien lee. Es preferencia de interfaz, no dato de la novela: vive en
 *  el navegador y se aplica a toda la aplicación, entrevista incluida. */
export interface AjustesDeLectura {
  tema: "papel" | "sepia" | "noche";
  familia: "serifa" | "sinserifa";
  /** Tamaño de la prosa, en píxeles. */
  tamano: number;
  interlineado: "compacto" | "normal" | "amplio";
  ancho: "estrecho" | "normal" | "ancho";
}

export const AJUSTES_POR_DEFECTO: AjustesDeLectura = {
  tema: "papel",
  familia: "serifa",
  tamano: 19,
  interlineado: "normal",
  ancho: "normal",
};

export const TAMANO_MINIMO = 15;
export const TAMANO_MAXIMO = 26;

const INTERLINEADOS = { compacto: "1.55", normal: "1.75", amplio: "2" } as const;
const ANCHOS = { estrecho: "32rem", normal: "38rem", ancho: "46rem" } as const;
const FAMILIAS = {
  serifa: '"Literata", Georgia, "Times New Roman", serif',
  sinserifa: '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif',
} as const;

function aplicar(ajustes: AjustesDeLectura) {
  const raiz = document.documentElement;
  raiz.dataset.tema = ajustes.tema;
  raiz.style.setProperty("--lectura-tamano", `${ajustes.tamano}px`);
  raiz.style.setProperty("--lectura-interlineado", INTERLINEADOS[ajustes.interlineado]);
  raiz.style.setProperty("--lectura-ancho", ANCHOS[ajustes.ancho]);
  raiz.style.setProperty("--lectura-familia", FAMILIAS[ajustes.familia]);
}

export function useAjustes() {
  const [ajustes, setAjustes] = useState<AjustesDeLectura>(() =>
    recordar("ajustes", AJUSTES_POR_DEFECTO),
  );

  useEffect(() => {
    aplicar(ajustes);
    guardar("ajustes", ajustes);
  }, [ajustes]);

  const cambiar = useCallback((parcial: Partial<AjustesDeLectura>) => {
    setAjustes((previos) => ({ ...previos, ...parcial }));
  }, []);

  return { ajustes, cambiar };
}
