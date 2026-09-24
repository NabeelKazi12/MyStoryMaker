import { StrictMode, useCallback, useState } from "react";
import { createRoot } from "react-dom/client";
import { Biblioteca } from "../pages/biblioteca/Biblioteca";
import { CrearNovela } from "../pages/crear/CrearNovela";
import { Lectura } from "../pages/lectura/Lectura";
import { useAjustes } from "../shared/ui/ajustes";
import { ListaDeAvisos, useAvisos } from "../shared/ui/Avisos";
import "../shared/ui/estilos.css";

type Vista = { tipo: "biblioteca" } | { tipo: "entrevista" } | { tipo: "lectura"; volumenId: string };

function App() {
  const inicial = new URLSearchParams(window.location.search).get("volumen");
  const [vista, setVista] = useState<Vista>(
    inicial ? { tipo: "lectura", volumenId: inicial } : { tipo: "biblioteca" },
  );
  // Si hay alguna novela a la que volver. Hasta que la biblioteca no lo dice, se supone que
  // sí: ofrecer «Volver a la biblioteca» de más solo lleva a una lista que ya lo explica.
  const [hayNovelas, setHayNovelas] = useState(true);
  // Los ajustes de lectura viven aquí para que el tema alcance también a la entrevista.
  const { ajustes, cambiar } = useAjustes();
  // Los avisos que sobreviven a un cambio de pantalla, como «Se ha eliminado…»: la lectura
  // que lo produjo ya no está para enseñarlo (SPEC-009 RF-LEC-19). No se cierran solos.
  const { avisos, anadir, cerrar, limpiar } = useAvisos();

  const abrir = useCallback((volumenId: string) => {
    window.history.replaceState(null, "", `?volumen=${volumenId}`);
    setVista({ tipo: "lectura", volumenId });
  }, []);
  const irABiblioteca = useCallback(() => {
    window.history.replaceState(null, "", window.location.pathname);
    setVista({ tipo: "biblioteca" });
  }, []);
  const irAEntrevista = useCallback(() => {
    window.history.replaceState(null, "", window.location.pathname);
    setVista({ tipo: "entrevista" });
  }, []);
  // Sin ninguna novela, lo primero es la entrevista: es donde empieza el encargo.
  const alVacia = useCallback(() => {
    setHayNovelas(false);
    setVista({ tipo: "entrevista" });
  }, []);

  let pantalla;
  if (vista.tipo === "biblioteca") {
    pantalla = <Biblioteca alAbrir={abrir} alNueva={irAEntrevista} alVacia={alVacia} />;
  } else if (vista.tipo === "entrevista") {
    pantalla = (
      <CrearNovela
        alCrear={(id) => {
          setHayNovelas(true);
          abrir(id);
        }}
        alVolver={hayNovelas ? irABiblioteca : undefined}
      />
    );
  } else {
    pantalla = (
      <Lectura
        key={vista.volumenId}
        volumenId={vista.volumenId}
        ajustes={ajustes}
        cambiarAjustes={cambiar}
        alBiblioteca={irABiblioteca}
        alNueva={irAEntrevista}
        alEliminada={(titulo) => {
          anadir(`Se ha eliminado «${titulo}».`);
          // La biblioteca vuelve a pedir la lista; si ya no queda ninguna, abre la entrevista.
          irABiblioteca();
        }}
      />
    );
  }

  return (
    <>
      {pantalla}
      {/* La lectura tiene su propia lista; aquí solo se enseñan fuera de ella. */}
      {vista.tipo !== "lectura" ? (
        <ListaDeAvisos avisos={avisos} cerrar={cerrar} limpiar={limpiar} />
      ) : null}
    </>
  );
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
