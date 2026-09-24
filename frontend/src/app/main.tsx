import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { CrearNovela } from "../pages/crear/CrearNovela";
import { Lectura } from "../pages/lectura/Lectura";
import "../shared/ui/estilos.css";

function App() {
  const inicial = new URLSearchParams(window.location.search).get("volumen");
  const [volumenId, setVolumenId] = useState<string | null>(inicial);

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

  return <Lectura volumenId={volumenId} alVolver={() => {
    window.history.replaceState(null, "", window.location.pathname);
    setVolumenId(null);
  }} />;
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
