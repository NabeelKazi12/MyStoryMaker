import { useCallback, useEffect, useRef, useState } from "react";
import {
  ErrorDeLectura,
  leerGastos,
  type DesgloseDeGasto,
  type GastosDeNovela,
} from "../../shared/api/lectura";
import { Icono } from "../../shared/ui/Icono";

type Estado =
  | { fase: "cargando" }
  | { fase: "error"; mensaje: string }
  | { fase: "listo"; gastos: GastosDeNovela };

const NOMBRE_DEL_ROL: Record<string, string> = {
  planner: "Planner",
  redactor: "Redactor",
};

/** El coste en USD, con más decimales cuando es pequeño: 0,0031 $ no es «0,00 $». */
function dinero(coste: number): string {
  return coste.toLocaleString("es-ES", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: coste !== 0 && Math.abs(coste) < 0.1 ? 4 : 2,
  });
}

function numero(valor: number): string {
  return valor.toLocaleString("es-ES");
}

function duracion(ms: number): string {
  const segundos = Math.round(ms / 1000);
  if (segundos < 60) return `${segundos} s`;
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) return `${minutos} min ${segundos % 60} s`;
  return `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}

/** `AAAA-MM-DD HH:MM:SS` en UTC a la hora local, que es lo que sirve para ubicarla. */
function hora(momento: string): string {
  const fecha = new Date(`${momento.replace(" ", "T")}Z`);
  return Number.isNaN(fecha.getTime())
    ? momento
    : fecha.toLocaleString("es-ES", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
}

/** El panel «Gastos» (SPEC-012): cifras, desglose por rol y por capítulo, y cada llamada.
 *
 *  Todo lo que enseña viene hecho de la ruta: aquí no se suma ni se reparte nada
 *  (RF-CON-07). `refresco` cambia con el progreso de la escritura; mientras el panel está
 *  abierto, cada cambio vuelve a pedir los gastos (RF-LEC-23). */
export function PanelDeGastos({ volumenId, refresco }: { volumenId: string; refresco: number }) {
  const [estado, setEstado] = useState<Estado>({ fase: "cargando" });
  const vigente = useRef(true);

  const cargar = useCallback(
    async (silencioso: boolean) => {
      if (!silencioso) setEstado({ fase: "cargando" });
      try {
        const gastos = await leerGastos(volumenId);
        if (vigente.current) setEstado({ fase: "listo", gastos });
      } catch (error) {
        if (!vigente.current) return;
        setEstado({
          fase: "error",
          mensaje: error instanceof ErrorDeLectura ? error.message : String(error),
        });
      }
    },
    [volumenId],
  );

  useEffect(() => {
    vigente.current = true;
    return () => {
      vigente.current = false;
    };
  }, []);

  // La primera carga enseña el indicador; las siguientes, las del sondeo, no parpadean.
  const primera = useRef(true);
  useEffect(() => {
    void cargar(!primera.current);
    primera.current = false;
  }, [cargar, refresco]);

  if (estado.fase === "cargando")
    return (
      <div className="gastos-estado">
        <div className="cargando" aria-hidden="true" />
        <p>Leyendo los gastos…</p>
      </div>
    );

  // «No he podido leer» es distinto de «no hay nada» (RF-LEC-24).
  if (estado.fase === "error")
    return (
      <div className="gastos-estado">
        <p className="error">No se han podido leer los gastos. El backend dijo: {estado.mensaje}</p>
        <button className="boton secundario" onClick={() => void cargar(false)}>
          Reintentar
        </button>
      </div>
    );

  const { gastos } = estado;
  const { total } = gastos;
  if (total.llamadas === 0)
    return (
      <div className="gastos-estado">
        <p className="vacio">Esta novela todavía no ha hecho ninguna llamada al modelo.</p>
      </div>
    );

  const recientes = [...gastos.llamadas].reverse();

  return (
    <div className="gastos">
      <dl className="cifras">
        <div className="cifra">
          <dt>Gastado</dt>
          <dd>{dinero(total.coste)}</dd>
        </div>
        <div className="cifra">
          <dt>Llamadas</dt>
          <dd>{numero(total.llamadas)}</dd>
          <span className="cifra-nota">
            {total.fallidas > 0 ? `${total.fallidas} fallida(s)` : "ninguna fallida"}
          </span>
        </div>
        <div className="cifra">
          <dt>Tokens</dt>
          {total.llamadas_sin_tokens === total.llamadas ? (
            // Ninguna llamada guardó tokens: un «0» diría que no se gastó ninguno.
            <>
              <dd>—</dd>
              <span className="cifra-nota">sin registrar</span>
            </>
          ) : (
            <>
              <dd>{numero(total.tokens_entrada + total.tokens_salida)}</dd>
              <span className="cifra-nota">
                {numero(total.tokens_entrada)} entrada · {numero(total.tokens_salida)} salida
              </span>
            </>
          )}
        </div>
        <div className="cifra">
          <dt>Tiempo de modelo</dt>
          <dd>{duracion(total.latencia_ms)}</dd>
        </div>
      </dl>

      {total.llamadas_sin_tokens > 0 ? (
        <p className="detalle">
          {total.llamadas_sin_tokens} llamada(s) anteriores a esta pestaña no guardaron sus
          tokens: cuentan en el coste y no en los tokens.
        </p>
      ) : null}

      <p className="detalle langfuse-estado">
        {gastos.langfuse_activo
          ? "Langfuse está configurado: las llamadas que se le enviaron enlazan a su traza."
          : "Langfuse no está configurado: los gastos se leen de la base, sin enlaces a trazas."}
      </p>

      <div className="desgloses">
        <Barras
          titulo="Por rol"
          filas={gastos.por_rol.map((d) => ({ ...d, nombre: NOMBRE_DEL_ROL[d.nombre] ?? d.nombre }))}
        />
        {gastos.por_capitulo.length > 0 ? (
          <Barras titulo="Por capítulo" filas={gastos.por_capitulo} />
        ) : null}
      </div>

      <section className="llamadas" aria-label="Llamadas al modelo">
        <h3>Llamadas, la más reciente primero</h3>
        <div className="tabla-llamadas" role="table">
          <div className="fila-llamada cabecera" role="row">
            <span role="columnheader">Cuándo</span>
            <span role="columnheader">Rol</span>
            <span role="columnheader">Dónde</span>
            <span role="columnheader" className="num">Coste</span>
            <span role="columnheader" className="num">Tokens</span>
            <span role="columnheader" className="num">Tiempo</span>
            <span role="columnheader">Traza</span>
          </div>
          {recientes.map((llamada) => (
            <div
              className={`fila-llamada${llamada.clase_de_fallo ? " fallida" : ""}`}
              role="row"
              key={llamada.id}
            >
              <span role="cell" className="apagado">{hora(llamada.momento)}</span>
              <span role="cell">
                {NOMBRE_DEL_ROL[llamada.agente] ?? llamada.agente}
                <small className="apagado">
                  {" "}
                  v{llamada.version_de_prompt} · {llamada.modelo}
                </small>
              </span>
              <span role="cell">
                {llamada.capitulo_orden !== null
                  ? `Cap. ${llamada.capitulo_orden}`
                  : llamada.tarea === "apertura"
                    ? "Apertura"
                    : llamada.tarea}
                {llamada.intento > 1 ? (
                  <small className="apagado"> · intento {llamada.intento}</small>
                ) : null}
                {llamada.clase_de_fallo ? (
                  <span className="chip-fallo">
                    <Icono nombre="aviso" tamano={12} /> {llamada.clase_de_fallo}
                  </span>
                ) : null}
              </span>
              <span role="cell" className="num">{dinero(llamada.coste)}</span>
              <span role="cell" className="num">
                {llamada.tokens_entrada === null && llamada.tokens_salida === null
                  ? "—"
                  : numero((llamada.tokens_entrada ?? 0) + (llamada.tokens_salida ?? 0))}
              </span>
              <span role="cell" className="num">{duracion(llamada.latencia_ms)}</span>
              <span role="cell">
                {llamada.traza_url ? (
                  <a className="enlace-traza" href={llamada.traza_url} target="_blank" rel="noreferrer">
                    Ver en Langfuse <Icono nombre="externo" tamano={12} />
                  </a>
                ) : (
                  <span className="apagado">—</span>
                )}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

/** Barras horizontales de una sola serie: el coste de cada grupo, con su valor en la
 *  punta y un tooltip al pasar o enfocar con el número de llamadas. Una serie no lleva
 *  leyenda: el título la nombra. */
function Barras({ titulo, filas }: { titulo: string; filas: DesgloseDeGasto[] }) {
  const maximo = Math.max(...filas.map((f) => f.coste), 0);
  return (
    <section className="barras" aria-label={`Coste ${titulo.toLowerCase()}`}>
      <h3>{titulo}</h3>
      <ul>
        {filas.map((fila) => (
          <li key={fila.nombre} className="barra-fila" tabIndex={0}>
            <span className="barra-nombre">{fila.nombre}</span>
            {/* El carril tiene anchura fija y la barra es proporcional dentro de él; el
                valor va en la punta y puede salir del carril, que deja sitio para él. */}
            <span className="barra-carril">
              <span
                className="barra-marca"
                style={{ width: maximo > 0 ? `${(fila.coste / maximo) * 100}%` : "0%" }}
              />
              <span className="barra-valor">{dinero(fila.coste)}</span>
            </span>
            <span className="barra-tooltip" role="tooltip">
              <strong>{fila.nombre}</strong> · {dinero(fila.coste)} · {fila.llamadas}{" "}
              {fila.llamadas === 1 ? "llamada" : "llamadas"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
