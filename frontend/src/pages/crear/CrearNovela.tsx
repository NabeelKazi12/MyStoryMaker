import { useState } from "react";
import { cerrarEntrevista, ErrorDeLectura, type EntrevistaFallida } from "../../shared/api/lectura";

/** La primera pantalla: la entrevista.
 *
 *  El formulario **no decide si algo es válido**. Envía lo que haya y muestra lo que el
 *  backend responda. Duplicar aquí la detección de huecos y contradicciones garantizaría
 *  que las dos copias divergen, y la del navegador es siempre la que se queda vieja.
 */
export function CrearNovela({ alCrear }: { alCrear: (volumenId: string) => void }) {
  const [nombre, setNombre] = useState("");
  const [edad, setEdad] = useState("");
  const [rasgos, setRasgos] = useState("");
  const [recuerdos, setRecuerdos] = useState("");
  const [genero, setGenero] = useState("");
  const [tono, setTono] = useState("");
  const [extension, setExtension] = useState("");
  const [dedicatoria, setDedicatoria] = useState("");
  const [vetadas, setVetadas] = useState("");
  const [textoLibre, setTextoLibre] = useState("");

  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<EntrevistaFallida | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [avisos, setAvisos] = useState<string[]>([]);

  const enLineas = (texto: string) =>
    texto
      .split("\n")
      .map((linea) => linea.trim())
      .filter(Boolean);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    setFallo(null);
    setError(null);
    try {
      const resultado = await cerrarEntrevista(
        {
          nombre,
          // Se manda tal cual lo escrito: si no es un número, lo dice el backend.
          edad: edad === "" ? "" : Number(edad),
          rasgos: enLineas(rasgos),
          recuerdos: enLineas(recuerdos),
          genero,
          tono,
          extension: extension === "" ? "" : Number(extension),
          dedicatoria,
          palabras_vetadas: enLineas(vetadas),
        },
        textoLibre,
      );
      if (resultado.intentos_de_injection.length > 0) {
        setAvisos(resultado.intentos_de_injection);
        // No se navega todavía: el aviso tiene que poder leerse antes de irse.
        setEnviando(false);
        setTimeout(() => alCrear(resultado.volumen_id), 0);
        return;
      }
      alCrear(resultado.volumen_id);
    } catch (problema) {
      if (problema instanceof ErrorDeLectura && problema.estado === 422) {
        setFallo(problema.detalle as EntrevistaFallida);
      } else {
        setError(problema instanceof Error ? problema.message : String(problema));
      }
      setEnviando(false);
    }
  }

  const falta = (campo: string) => fallo?.huecos.includes(campo) ?? false;

  return (
    <main>
      <div className="medida">
        <header className="portada">
          <h1>Una novela para alguien</h1>
          <p className="dedicatoria">
            Cuéntame de quién es el regalo. Lo que falte, te lo preguntaré; lo que no
            encaje, te lo diré. Cuando el encargo esté cerrado, podrás mandarla escribir.
          </p>
        </header>

        {error ? <p className="error">{error}</p> : null}

        {avisos.length > 0 ? (
          <div className="aviso">
            <span>
              En el texto que pegaste hay algo escrito como una orden
              {` («${avisos[0]}»)`}. Se ha guardado como texto y no se va a obedecer.
            </span>
          </div>
        ) : null}

        {fallo && fallo.contradicciones.length > 0 ? (
          <div className="aviso">
            <span>
              {fallo.contradicciones.map((c) => (
                <span key={c.campos.join("-")}>
                  <strong>{c.campos.join(" y ")}</strong>: {c.detalle}
                </span>
              ))}
            </span>
          </div>
        ) : null}

        {fallo && fallo.huecos.length > 0 ? (
          <p className="error">Faltan estos datos: {fallo.huecos.join(", ")}.</p>
        ) : null}

        <form onSubmit={enviar} className="entrevista">
          <label>
            Nombre de quien la recibe {falta("nombre") ? <em>· falta</em> : null}
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </label>

          <label>
            Edad {falta("edad") ? <em>· falta</em> : null}
            <input value={edad} onChange={(e) => setEdad(e.target.value)} inputMode="numeric" />
          </label>

          <label>
            Rasgos, uno por línea {falta("rasgos") ? <em>· falta</em> : null}
            <textarea rows={3} value={rasgos} onChange={(e) => setRasgos(e.target.value)} />
          </label>

          <label>
            Recuerdos que tienen que aparecer, uno por línea{" "}
            {falta("recuerdos") ? <em>· falta</em> : null}
            <textarea rows={3} value={recuerdos} onChange={(e) => setRecuerdos(e.target.value)} />
          </label>

          <label>
            Género {falta("genero") ? <em>· falta</em> : null}
            <input value={genero} onChange={(e) => setGenero(e.target.value)} />
          </label>

          <label>
            Tono {falta("tono") ? <em>· falta</em> : null}
            <input value={tono} onChange={(e) => setTono(e.target.value)} />
          </label>

          <label>
            Extensión en palabras {falta("extension") ? <em>· falta</em> : null}
            <input
              value={extension}
              onChange={(e) => setExtension(e.target.value)}
              inputMode="numeric"
            />
          </label>

          <label>
            Dedicatoria
            <input value={dedicatoria} onChange={(e) => setDedicatoria(e.target.value)} />
          </label>

          <label>
            Palabras o temas que no quieres ver, uno por línea
            <textarea rows={2} value={vetadas} onChange={(e) => setVetadas(e.target.value)} />
          </label>

          <label>
            Pega aquí una carta, una anécdota o lo que quieras contar
            <textarea rows={5} value={textoLibre} onChange={(e) => setTextoLibre(e.target.value)} />
            <small>
              Este texto se trata como material narrativo, nunca como instrucción: si
              contiene algo escrito como una orden, se guarda y se avisa, pero no se
              obedece.
            </small>
          </label>

          <button type="submit" disabled={enviando}>
            {enviando ? "Creando…" : "Crear el encargo"}
          </button>
          <small>
            Esto crea el <strong>encargo</strong>, no la novela: recoge para quién es y qué
            tiene que contener. Escribirla se pide después, desde la lectura, y tarda
            minutos. El formulario no comprueba nada por su cuenta: envía y te enseña lo
            que responda el sistema.
          </small>
        </form>
      </div>
    </main>
  );
}
