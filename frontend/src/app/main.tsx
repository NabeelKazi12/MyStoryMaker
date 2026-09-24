import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { CrearNovela } from "../pages/crear/CrearNovela";
import { Lectura } from "../pages/lectura/Lectura";
import { useAjustes } from "../shared/ui/ajustes";
import "../shared/ui/estilos.css";

function App() {
  const inicial = new URLSearchParams(window.location.search).get("volumen");
  const [volumenId, setVolumenId] = useState<string | null>(inicial);
  // Los ajustes de lectura viven aquí para que el tema alcance también a la entrevista.
  const { ajustes, cambiar } = useAjustes();

  // Sin novela elegida, lo primero es la entrevista: es donde empieza el encargo.
  if (!volumenId) {
    return (
      <CrearNovela
        alCrear={(id) => {
          window.history.replaceState(null, "", `?volumen=${id}`);
          setVolumenId(id);
        }}
      />
    );
  }

  return (
    <Lectura
      volumenId={volumenId}
      ajustes={ajustes}
      cambiarAjustes={cambiar}
      alVolver={() => {
        window.history.replaceState(null, "", window.location.pathname);
        setVolumenId(null);
      }}
    />
  );
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
