import { useEffect, useState } from "react";
import { cerrarEntrevista, ErrorDeLectura, type EntrevistaFallida } from "../../shared/api/lectura";
import { guardar, olvidar, recordar } from "../../shared/ui/almacen";
import { Etiquetas } from "../../shared/ui/Etiquetas";
import { Icono } from "../../shared/ui/Icono";

/** La primera pantalla: la entrevista, en cuatro pasos y un repaso.
 *
 *  El formulario **no decide si algo es válido**. «Siguiente» no comprueba nada y «Crear
 *  el encargo» envía lo que haya; lo que falte o no encaje lo dice el backend, y aquí
 *  solo se lleva a quien escribe al paso donde está. Duplicar la detección de huecos
 *  garantizaría que las dos copias divergen.
 */

interface Respuestas {
  nombre: string;
  edad: string;
  rasgos: string[];
  recuerdos: string[];
  genero: string;
  tono: string;
  extension: string;
  dedicatoria: string;
  vetadas: string[];
  textoLibre: string;
}

const VACIAS: Respuestas = {
  nombre: "",
  edad: "",
  rasgos: [],
  recuerdos: [],
  genero: "",
  tono: "",
  extension: "",
  dedicatoria: "",
  vetadas: [],
  textoLibre: "",
};

/** Qué campos del backend viven en qué paso. Es un mapa de presentación: sirve para
 *  llevar a quien escribe al hueco, no para decidir si hay hueco. */
const PASOS = [
  { titulo: "Para quién", lema: "Empecemos por la persona que va a recibirla.", campos: ["nombre", "edad", "rasgos"] },
  { titulo: "Lo que no puede faltar", lema: "Los recuerdos que harán que se reconozca en la historia.", campos: ["recuerdos"] },
  { titulo: "La historia", lema: "Qué clase de libro quieres regalar.", campos: ["genero", "tono", "extension"] },
  { titulo: "El toque final", lema: "La dedicatoria, lo que no quieres ver y lo que quieras contar.", campos: ["dedicatoria", "palabras_vetadas", "texto_libre"] },
] as const;
const REPASO = PASOS.length;

const CLAVE = "entrevista";

export function CrearNovela({ alCrear }: { alCrear: (volumenId: string) => void }) {
  const [r, setR] = useState<Respuestas>(() => recordar(CLAVE, VACIAS));
  const [paso, setPaso] = useState(() => recordar(`${CLAVE}:paso`, { n: 0 }).n);

  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<EntrevistaFallida | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creado, setCreado] = useState<{ volumenId: string; ordenes: string[] } | null>(null);

  useEffect(() => guardar(CLAVE, r), [r]);
  useEffect(() => guardar(`${CLAVE}:paso`, { n: paso }), [paso]);

  const poner = <K extends keyof Respuestas>(campo: K, valor: Respuestas[K]) =>
    setR((previas) => ({ ...previas, [campo]: valor }));

  const huecos: string[] = fallo?.huecos ?? [];
  const falta = (campo: string) => huecos.includes(campo);
  const pasoConFalta = (n: number) => PASOS[n].campos.some((c) => huecos.includes(c));

  function olvidarBorrador() {
    olvidar(CLAVE);
    olvidar(`${CLAVE}:paso`);
  }

  function empezarDeCero() {
    olvidarBorrador();
    setR(VACIAS);
    setPaso(0);
    setFallo(null);
    setError(null);
  }

  async function enviar() {
    setEnviando(true);
    setFallo(null);
    setError(null);
    try {
      const resultado = await cerrarEntrevista(
        {
          nombre: r.nombre,
          // Se manda tal cual lo escrito: si no es un número, lo dice el backend.
          edad: r.edad === "" ? "" : Number(r.edad),
          rasgos: r.rasgos,
          recuerdos: r.recuerdos,
          genero: r.genero,
          tono: r.tono,
          extension: r.extension === "" ? "" : Number(r.extension),
          dedicatoria: r.dedicatoria,
          palabras_vetadas: r.vetadas,
        },
        r.textoLibre,
      );
      olvidarBorrador();
      if (resultado.intentos_de_injection.length > 0) {
        // No se navega todavía: el aviso tiene que poder leerse antes de irse, y quien
        // lo lee decide cuándo seguir.
        setCreado({ volumenId: resultado.volumen_id, ordenes: resultado.intentos_de_injection });
        setEnviando(false);
        return;
      }
      alCrear(resultado.volumen_id);
    } catch (problema) {
      if (problema instanceof ErrorDeLectura && problema.estado === 422) {
        const detalle = problema.detalle as EntrevistaFallida;
        setFallo(detalle);
        const primero = PASOS.findIndex((p) => p.campos.some((c) => detalle.huecos?.includes(c)));
        if (primero >= 0) setPaso(primero);
      } else {
        setError(problema instanceof Error ? problema.message : String(problema));
      }
      setEnviando(false);
    }
  }

  if (creado) {
    return (
      <div className="entrevista-pantalla">
        <div className="tarjeta confirmacion">
          <div className="aviso aviso-en-linea" role="status">
            <Icono nombre="aviso" tamano={18} />
            <span>
              En el texto que pegaste hay algo escrito como una orden
              {` («${creado.ordenes[0]}»)`}. Se ha guardado como texto y no se va a obedecer.
            </span>
          </div>
          <p>El encargo está creado.</p>
          <button className="boton principal" onClick={() => alCrear(creado.volumenId)}>
            Ir a la novela <Icono nombre="siguiente" tamano={16} />
          </button>
        </div>
      </div>
    );
  }

  const paginas = r.extension && !Number.isNaN(Number(r.extension)) ? Math.max(1, Math.round(Number(r.extension) / 250)) : null;

  return (
    <div className="entrevista-pantalla">
      <aside className="entrevista-escaparate" aria-hidden="true">
        <p className="marca-app">
          <Icono nombre="libro" /> MyStoryMaker
        </p>
        {/* La cubierta se compone mientras se escribe: es lo que se está encargando. */}
        <div className="libro-muestra">
          <div className="libro-lomo" />
          <div className="libro-tapa">
            <span className="libro-genero">{r.genero || "Novela"}</span>
            <strong className="libro-titulo">
              {r.nombre ? `Una historia para ${r.nombre}` : "Una novela para alguien"}
            </strong>
            <span className="libro-tono">{r.tono}</span>
            {r.dedicatoria ? <em className="libro-dedicatoria">«{r.dedicatoria}»</em> : null}
          </div>
        </div>
        <p className="escaparate-pie">
          {r.recuerdos.length > 0
            ? `${r.recuerdos.length} ${r.recuerdos.length === 1 ? "recuerdo" : "recuerdos"} para tejer en la trama`
            : "Un libro escrito a partir de sus recuerdos"}
        </p>
      </aside>

      <main className="entrevista-principal">
        <ol className="pasos" aria-label="Pasos de la entrevista">
          {[...PASOS.map((p) => p.titulo), "Repaso"].map((titulo, n) => (
            <li key={titulo}>
              <button
                type="button"
                className={[
                  "paso",
                  n === paso ? "actual" : "",
                  n < paso ? "hecho" : "",
                  n < REPASO && pasoConFalta(n) ? "con-falta" : "",
                ].join(" ")}
                aria-current={n === paso ? "step" : undefined}
                onClick={() => setPaso(n)}
              >
                <span className="paso-numero">{n + 1}</span>
                <span className="paso-titulo">{titulo}</span>
              </button>
            </li>
          ))}
        </ol>

        <div className="tarjeta entrevista-tarjeta">
          {error ? <p className="error">{error}</p> : null}
          {fallo && fallo.contradicciones.length > 0 ? (
            <div className="aviso aviso-en-linea">
              <Icono nombre="aviso" tamano={18} />
              <span>
                {fallo.contradicciones.map((c) => (
                  <span key={c.campos.join("-")} className="contradiccion">
                    <strong>{c.campos.join(" y ")}</strong>: {c.detalle}
                  </span>
                ))}
              </span>
            </div>
          ) : null}
          {fallo && huecos.length > 0 ? (
            <p className="error">Faltan estos datos: {huecos.join(", ")}.</p>
          ) : null}

          {paso < REPASO ? (
            <header className="paso-cabecera">
              <span className="antetitulo">
                Paso {paso + 1} de {PASOS.length}
              </span>
              <h1>{PASOS[paso].titulo}</h1>
              <p>{PASOS[paso].lema}</p>
            </header>
          ) : (
            <header className="paso-cabecera">
              <span className="antetitulo">Último vistazo</span>
              <h1>Repasa el encargo</h1>
              <p>Esto crea el encargo; la novela se manda escribir después, desde la lectura.</p>
            </header>
          )}

          <form
            className="entrevista"
            onSubmit={(e) => {
              e.preventDefault();
              if (paso < REPASO) setPaso(paso + 1);
              else void enviar();
            }}
          >
            {paso === 0 ? (
              <>
                <div className="fila-dos">
                  <Campo etiqueta="Nombre" falta={falta("nombre")}>
                    <input value={r.nombre} onChange={(e) => poner("nombre", e.target.value)} placeholder="¿Cómo se llama?" autoFocus />
                  </Campo>
                  <Campo etiqueta="Edad" falta={falta("edad")} estrecho>
                    <input value={r.edad} onChange={(e) => poner("edad", e.target.value)} inputMode="numeric" placeholder="Años" />
                  </Campo>
                </div>
                <Etiquetas
                  etiqueta="Cómo es"
                  valores={r.rasgos}
                  alCambiar={(v) => poner("rasgos", v)}
                  sugerencia="Curiosa, cabezota, ríe fuerte…"
                  falta={falta("rasgos")}
                />
              </>
            ) : null}

            {paso === 1 ? (
              <Etiquetas
                etiqueta="Recuerdos que tienen que aparecer"
                valores={r.recuerdos}
                alCambiar={(v) => poner("recuerdos", v)}
                sugerencia="El verano en que aprendió a nadar en el río…"
                falta={falta("recuerdos")}
                forma="lista"
              />
            ) : null}

            {paso === 2 ? (
              <>
                <div className="fila-dos">
                  <Campo etiqueta="Género" falta={falta("genero")}>
                    <input value={r.genero} onChange={(e) => poner("genero", e.target.value)} placeholder="Aventura, fantasía, misterio…" />
                  </Campo>
                  <Campo etiqueta="Tono" falta={falta("tono")}>
                    <input value={r.tono} onChange={(e) => poner("tono", e.target.value)} placeholder="Tierno, divertido, épico…" />
                  </Campo>
                </div>
                <Campo
                  etiqueta="Extensión en palabras"
                  falta={falta("extension")}
                  ayuda={paginas ? `Unas ${paginas} páginas de libro.` : undefined}
                >
                  <input value={r.extension} onChange={(e) => poner("extension", e.target.value)} inputMode="numeric" placeholder="Por ejemplo, 20000" />
                </Campo>
              </>
            ) : null}

            {paso === 3 ? (
              <>
                <Campo etiqueta="Dedicatoria" falta={falta("dedicatoria")}>
                  <input value={r.dedicatoria} onChange={(e) => poner("dedicatoria", e.target.value)} placeholder="Para quien siempre…" />
                </Campo>
                <Etiquetas
                  etiqueta="Palabras o temas que no quieres ver"
                  valores={r.vetadas}
                  alCambiar={(v) => poner("vetadas", v)}
                  sugerencia="Opcional"
                  falta={falta("palabras_vetadas")}
                />
                <Campo
                  etiqueta="Una carta, una anécdota o lo que quieras contar"
                  ayuda="Se lee como material para la historia, nunca como una instrucción."
                >
                  <textarea rows={6} value={r.textoLibre} onChange={(e) => poner("textoLibre", e.target.value)} placeholder="Opcional" />
                </Campo>
              </>
            ) : null}

            {paso === REPASO ? (
              <dl className="repaso">
                <Repaso titulo="Para quién" alEditar={() => setPaso(0)} conFalta={pasoConFalta(0)}>
                  {[r.nombre, r.edad && `${r.edad} años`].filter(Boolean).join(" · ") || <Vacio />}
                  {r.rasgos.length > 0 ? <span className="repaso-lista">{r.rasgos.join(", ")}</span> : null}
                </Repaso>
                <Repaso titulo="Recuerdos" alEditar={() => setPaso(1)} conFalta={pasoConFalta(1)}>
                  {r.recuerdos.length > 0 ? (
                    <ul>{r.recuerdos.map((x, i) => <li key={i}>{x}</li>)}</ul>
                  ) : <Vacio />}
                </Repaso>
                <Repaso titulo="La historia" alEditar={() => setPaso(2)} conFalta={pasoConFalta(2)}>
                  {[r.genero, r.tono, r.extension && `${Number(r.extension).toLocaleString("es-ES")} palabras`].filter(Boolean).join(" · ") || <Vacio />}
                </Repaso>
                <Repaso titulo="El toque final" alEditar={() => setPaso(3)} conFalta={pasoConFalta(3)}>
                  {r.dedicatoria ? <em>«{r.dedicatoria}»</em> : <Vacio texto="Sin dedicatoria" />}
                  {r.vetadas.length > 0 ? <span className="repaso-lista">Sin: {r.vetadas.join(", ")}</span> : null}
                  {r.textoLibre ? <span className="repaso-lista">Con texto libre ({r.textoLibre.length} caracteres)</span> : null}
                </Repaso>
              </dl>
            ) : null}

            <footer className="entrevista-pie">
              {paso > 0 ? (
                <button type="button" className="boton fantasma" onClick={() => setPaso(paso - 1)}>
                  <Icono nombre="anterior" tamano={16} /> Anterior
                </button>
              ) : (
                <button type="button" className="boton fantasma" onClick={empezarDeCero}>
                  Empezar de cero
                </button>
              )}
              <button type="submit" className="boton principal" disabled={enviando}>
                {paso < REPASO ? (
                  <>Siguiente <Icono nombre="siguiente" tamano={16} /></>
                ) : enviando ? (
                  "Creando…"
                ) : (
                  "Crear el encargo"
                )}
              </button>
            </footer>
          </form>
        </div>
      </main>
    </div>
  );
}

function Campo({
  etiqueta,
  falta,
  ayuda,
  estrecho,
  children,
}: {
  etiqueta: string;
  falta?: boolean;
  ayuda?: string;
  estrecho?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={`campo ${falta ? "con-falta" : ""} ${estrecho ? "estrecho" : ""}`}>
      <span>
        {etiqueta} {falta ? <em className="marca-falta">falta</em> : null}
      </span>
      {children}
      {ayuda ? <small>{ayuda}</small> : null}
    </label>
  );
}

function Repaso({
  titulo,
  alEditar,
  conFalta,
  children,
}: {
  titulo: string;
  alEditar: () => void;
  conFalta: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={conFalta ? "con-falta" : undefined}>
      <dt>
        {titulo} {conFalta ? <em className="marca-falta">falta</em> : null}
        <button type="button" className="enlace" onClick={alEditar}>
          Editar
        </button>
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

function Vacio({ texto = "Sin rellenar" }: { texto?: string }) {
  return <span className="vacio">{texto}</span>;
}
