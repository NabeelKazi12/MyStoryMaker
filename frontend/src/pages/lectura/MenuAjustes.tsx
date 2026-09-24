import {
  TAMANO_MAXIMO,
  TAMANO_MINIMO,
  type AjustesDeLectura,
} from "../../shared/ui/ajustes";

/** El menú «Aa» de los lectores de libros: cada cambio se ve en el acto sobre la prosa
 *  que hay debajo, sin botón de aplicar. */
export function MenuAjustes({
  ajustes,
  cambiar,
}: {
  ajustes: AjustesDeLectura;
  cambiar: (parcial: Partial<AjustesDeLectura>) => void;
}) {
  return (
    <div className="menu-ajustes" role="group" aria-label="Ajustes de lectura">
      <div className="ajuste">
        <span className="ajuste-nombre">Tamaño</span>
        <div className="tamano">
          <button
            className="boton-icono letra-pequena"
            onClick={() => cambiar({ tamano: Math.max(TAMANO_MINIMO, ajustes.tamano - 1) })}
            disabled={ajustes.tamano <= TAMANO_MINIMO}
            aria-label="Letra más pequeña"
          >
            A
          </button>
          <input
            type="range"
            min={TAMANO_MINIMO}
            max={TAMANO_MAXIMO}
            value={ajustes.tamano}
            onChange={(e) => cambiar({ tamano: Number(e.target.value) })}
            aria-label="Tamaño de letra"
          />
          <button
            className="boton-icono letra-grande"
            onClick={() => cambiar({ tamano: Math.min(TAMANO_MAXIMO, ajustes.tamano + 1) })}
            disabled={ajustes.tamano >= TAMANO_MAXIMO}
            aria-label="Letra más grande"
          >
            A
          </button>
        </div>
      </div>

      <div className="ajuste">
        <span className="ajuste-nombre">Tema</span>
        <div className="temas">
          {(["papel", "sepia", "noche"] as const).map((tema) => (
            <button
              key={tema}
              className={`muestra-tema tema-${tema}`}
              aria-pressed={ajustes.tema === tema}
              onClick={() => cambiar({ tema })}
            >
              {tema[0].toUpperCase() + tema.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <Selector
        nombre="Letra"
        valor={ajustes.familia}
        opciones={[
          ["serifa", "Literata"],
          ["sinserifa", "Inter"],
        ]}
        alElegir={(familia) => cambiar({ familia })}
      />
      <Selector
        nombre="Interlineado"
        valor={ajustes.interlineado}
        opciones={[
          ["compacto", "Compacto"],
          ["normal", "Normal"],
          ["amplio", "Amplio"],
        ]}
        alElegir={(interlineado) => cambiar({ interlineado })}
      />
      <Selector
        nombre="Ancho"
        valor={ajustes.ancho}
        opciones={[
          ["estrecho", "Estrecho"],
          ["normal", "Normal"],
          ["ancho", "Ancho"],
        ]}
        alElegir={(ancho) => cambiar({ ancho })}
      />
    </div>
  );
}

function Selector<T extends string>({
  nombre,
  valor,
  opciones,
  alElegir,
}: {
  nombre: string;
  valor: T;
  opciones: [T, string][];
  alElegir: (valor: T) => void;
}) {
  return (
    <div className="ajuste">
      <span className="ajuste-nombre">{nombre}</span>
      <div className="segmentado">
        {opciones.map(([clave, texto]) => (
          <button key={clave} aria-pressed={valor === clave} onClick={() => alElegir(clave)}>
            {texto}
          </button>
        ))}
      </div>
    </div>
  );
}
