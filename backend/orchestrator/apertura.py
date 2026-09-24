"""Apertura del canon: de un encargo cerrado a una novela que se puede redactar.

Una novela recien salida de la entrevista tiene brief, destinatario y volumen, y nada
mas: ni personajes, ni lugares, ni eventos, ni capitulos. El Redactor no puede escribir
contra eso, porque su propio contrato le prohibe introducir entidades con nombre propio
que la escena no le haya dado. Este modulo es el paso que falta.

Vive en `orchestrator/` y no en `agents/` porque coordina un rol -el Planner- con el
almacen, igual que `encargo.py` coordina el Entrevistador. El rol propone; aqui se
persiste o se rechaza entero.

Dos reglas ordenan el modulo:

1. **Los identificadores que propone el rol no se guardan tal cual.** Se traducen a
   identificadores del volumen. Con una novela en la base daria igual; con dos, la
   segunda `esc-1` chocaria contra la primera y el fallo apareceria como una violacion de
   clave primaria en mitad de una escritura, sin decir de quien es la culpa.
2. **O entra todo o no entra nada.** La transaccion es de quien llama, y la validacion
   del plan corre antes de la primera escritura.

Cubre RF-APE-01 a RF-APE-04.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from backend.agents.planner.planner import (
    Apertura,
    EscenaPlanificada,
    prompt_vigente,
)
from backend.domain.spec.encargo import PersonajeDeclarado
from backend.domain.vocabularies import Relevancia, RolEnEvento
from backend.store.database import Conexion
from backend.store.personajes import PersonajesDeclarados


class NovelaDesconocida(LookupError):
    """Se pidio abrir una novela que no existe, o que no tiene encargo asociado."""

    def __init__(self, volumen_id: str, detalle: str) -> None:
        super().__init__(f"No se puede abrir el canon de {volumen_id}: {detalle}")


class AperturaImposible(RuntimeError):
    """El rol se rindio en lugar de inventar. Trae lo que dijo que le faltaba."""

    def __init__(self, falta: Sequence[str]) -> None:
        self.falta = tuple(falta)
        super().__init__(
            f"El Planner declaro contexto insuficiente para abrir la novela y enumero lo "
            f"que le falta: {'; '.join(falta)}. No se rellena con suposiciones: un hueco "
            f"del encargo relleno a ojo no parece una pregunta, parece un dato."
        )


@dataclass(frozen=True)
class RecuerdoObligatorio:
    """Un elemento personalizado que el cliente declaro obligatorio."""

    id: str
    contenido: str


@dataclass(frozen=True)
class EncargoDeNovela:
    """Lo que la apertura necesita saber del encargo, leido de una sola vez."""

    volumen_id: str
    brief_id: str
    titulo: str
    genero: str
    premisa: str
    promesa_al_lector: str
    extension_objetivo: int
    destinatario_id: str
    nombre: str
    edad: int | None
    rasgos: tuple[str, ...]
    dedicatoria: str
    tono: str
    recuerdos: tuple[RecuerdoObligatorio, ...]
    # Los que quien encarga declaro (SPEC-011). Vacio en las novelas de antes de `0008`:
    # entonces solo se comprueba que haya algun protagonista, como hasta ahora.
    personajes_declarados: tuple[PersonajeDeclarado, ...] = ()

    @property
    def ids_de_recuerdos(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.recuerdos)

    @property
    def personajes_a_cobrar(self) -> tuple[tuple[str, Relevancia], ...]:
        """Nombre y papel de cada declarado: lo que la apertura tiene que proponer."""
        return tuple((p.nombre, p.papel) for p in self.personajes_declarados)


@dataclass(frozen=True)
class ResultadoDeApertura:
    """Que dejo la apertura, o por que no dejo nada."""

    ya_estaba: bool
    capitulos: tuple[str, ...] = ()
    escenas: tuple[str, ...] = ()
    personajes: tuple[str, ...] = ()
    lugares: tuple[str, ...] = ()
    eventos: tuple[str, ...] = ()


def leer_encargo(conn: Conexion, volumen_id: str) -> EncargoDeNovela:
    """Todo el encargo en una lectura. Falla nombrando que pieza falta."""
    fila = conn.execute(
        """
        SELECT v.id AS volumen_id, v.titulo, b.id AS brief_id, b.genero, b.premisa,
               b.promesa_al_lector, b.extension_objetivo,
               d.id AS destinatario_id, d.nombre, d.edad, d.rasgos, d.dedicatoria
        FROM volumen v
        JOIN brief b ON b.id = v.brief_id
        LEFT JOIN destinatario d ON d.brief_id = b.id
        WHERE v.id = ?
        """,
        (volumen_id,),
    ).fetchone()
    if fila is None:
        raise NovelaDesconocida(
            volumen_id,
            "no existe el volumen, o existe sin brief asociado. Una novela sin encargo no "
            "se puede abrir: no hay a quien va dirigida ni que tiene que contener",
        )
    if fila["destinatario_id"] is None:
        raise NovelaDesconocida(volumen_id, "el brief no tiene destinatario")

    recuerdos = conn.execute(
        "SELECT id, contenido FROM elemento_personalizado "
        "WHERE destinatario_id = ? AND tipo = 'recuerdo' AND obligatorio = 1 ORDER BY id",
        (fila["destinatario_id"],),
    ).fetchall()

    return EncargoDeNovela(
        volumen_id=fila["volumen_id"],
        brief_id=fila["brief_id"],
        titulo=fila["titulo"],
        genero=fila["genero"],
        premisa=fila["premisa"],
        promesa_al_lector=fila["promesa_al_lector"],
        extension_objetivo=int(fila["extension_objetivo"]),
        destinatario_id=fila["destinatario_id"],
        nombre=fila["nombre"],
        edad=fila["edad"],
        rasgos=tuple(r for r in (fila["rasgos"] or "").split("|") if r),
        dedicatoria=fila["dedicatoria"] or "",
        # El tono no tiene columna propia: viaja dentro de la promesa al lector, que es
        # donde el Entrevistador lo escribio. Leerlo de ahi es feo y es honesto; darle una
        # columna es una migracion y una spec, no un apanio de paso.
        tono=_tono_de(fila["promesa_al_lector"]),
        recuerdos=tuple(
            RecuerdoObligatorio(id=r["id"], contenido=r["contenido"]) for r in recuerdos
        ),
        personajes_declarados=PersonajesDeclarados(conn).de_brief(fila["brief_id"]),
    )


def instruccion_de_apertura(encargo: EncargoDeNovela) -> str:
    """El bloque de instruccion del paquete: el encargo, en filas legibles.

    Las filas llevan la forma `clave: valor` a proposito. No es para el modelo -a un
    modelo le daria igual- sino para que el modo de demostracion pueda componer una
    apertura del **encargo real** en lugar de una generica: si la prosa de muestra no
    habla de quien va a recibir la novela, no demuestra nada.
    """
    lineas = [
        "Abre el canon de esta novela a partir del encargo.",
        "",
        f"destinatario: {encargo.nombre}",
        f"edad: {encargo.edad if encargo.edad is not None else 'sin declarar'}",
        f"genero: {encargo.genero}",
        f"tono: {encargo.tono}",
        f"premisa: {encargo.premisa}",
        f"promesa: {encargo.promesa_al_lector}",
        f"extension: {encargo.extension_objetivo}",
        f"dedicatoria: {encargo.dedicatoria}",
    ]
    lineas += [f"rasgo: {rasgo}" for rasgo in encargo.rasgos]
    lineas += [
        f"recuerdo {recuerdo.id} | {recuerdo.contenido}" for recuerdo in encargo.recuerdos
    ]
    # La barra separa los campos del contrato: un texto que la traiga partiria la fila.
    lineas += [
        "personaje declarado | "
        + " | ".join(
            valor.replace("|", "/")
            for valor in (p.nombre, p.papel.value, p.relacion, p.descripcion)
        )
        for p in encargo.personajes_declarados
    ]
    lineas += [
        "",
        "Cada recuerdo de arriba es obligatorio: tiene que ir en la columna «recuerdos "
        "que cubre» de al menos un capitulo, con su identificador tal cual.",
    ]
    if encargo.personajes_declarados:
        lineas.append(
            "Cada personaje declarado es obligatorio: tiene que estar en el bloque de "
            "personajes con ese nombre canonico exacto y esa relevancia. Puedes anadir "
            "los personajes que la historia necesite."
        )
    return "\n".join(lineas)


def prompt_del_planner() -> str:
    """El contrato del rol, que es el prefijo estatico de su paquete."""
    return prompt_vigente()


def esta_abierta(conn: Conexion, volumen_id: str) -> bool:
    """Si la novela ya tiene capitulos. Es la condicion de idempotencia (RF-APE-04)."""
    fila = conn.execute(
        "SELECT 1 FROM capitulo WHERE volumen_id = ? LIMIT 1", (volumen_id,)
    ).fetchone()
    return fila is not None


def persistir_apertura(
    conn: Conexion, encargo: EncargoDeNovela, apertura: Apertura
) -> ResultadoDeApertura:
    """Escribe el canon propuesto y la estructura, con identificadores del volumen.

    Si la novela ya estaba abierta no se toca nada y se dice que ya estaba: repetir la
    apertura es lo que pasa cuando alguien vuelve a pulsar el boton, y duplicar el canon
    por eso seria un fallo que la pantalla no podria distinguir de un exito.
    """
    if apertura.contexto_insuficiente:
        raise AperturaImposible(apertura.falta)
    if esta_abierta(conn, encargo.volumen_id):
        return ResultadoDeApertura(ya_estaba=True)

    sufijo = _sufijo(encargo.volumen_id)
    personajes = {p.id: f"pe-{sufijo}-{n}" for n, p in enumerate(apertura.personajes, 1)}
    lugares = {lugar.id: f"lu-{sufijo}-{n}" for n, lugar in enumerate(apertura.lugares, 1)}
    eventos = {e.id: f"ev-{sufijo}-{n}" for n, e in enumerate(apertura.eventos, 1)}

    for propuesto in apertura.personajes:
        conn.execute(
            "INSERT INTO personaje (id, nombre_canonico, relevancia, necesidad_interna, "
            "anio_de_nacimiento) VALUES (?, ?, ?, ?, ?)",
            (
                personajes[propuesto.id],
                propuesto.nombre_canonico,
                propuesto.relevancia.value,
                propuesto.necesidad_interna,
                propuesto.anio_de_nacimiento,
            ),
        )

    for propuesto_lugar in apertura.lugares:
        conn.execute(
            "INSERT INTO lugar (id, nombre_canonico, atmosfera_sensorial) VALUES (?, ?, ?)",
            (
                lugares[propuesto_lugar.id],
                propuesto_lugar.nombre_canonico,
                propuesto_lugar.atmosfera_sensorial,
            ),
        )

    for propuesto_evento in apertura.eventos:
        conn.execute(
            "INSERT INTO evento (id, descripcion, posicion_en_historia, tipo, lugar_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                eventos[propuesto_evento.id],
                propuesto_evento.descripcion,
                propuesto_evento.posicion_en_historia,
                propuesto_evento.tipo.value,
                lugares[propuesto_evento.lugar_id],
            ),
        )
        conn.execute(
            "INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento) "
            "VALUES (?, ?, ?)",
            (
                eventos[propuesto_evento.id],
                personajes[propuesto_evento.participante_id],
                RolEnEvento.AGENTE.value,
            ),
        )

    capitulos: dict[int, str] = {}
    for capitulo in sorted(apertura.capitulos, key=lambda c: c.orden):
        identificador = f"cap-{sufijo}-{capitulo.orden}"
        capitulos[capitulo.orden] = identificador
        conn.execute(
            "INSERT INTO capitulo (id, volumen_id, orden, titulo) VALUES (?, ?, ?, ?)",
            (identificador, encargo.volumen_id, capitulo.orden, capitulo.titulo),
        )

    escenas = _persistir_escenas(
        conn,
        apertura.escenas,
        sufijo=sufijo,
        capitulos=capitulos,
        personajes=personajes,
        lugares=lugares,
        eventos=eventos,
        hechos_requeridos=() if apertura.plan is None else apertura.plan.hechos_requeridos,
        palabras_por_escena=palabras_por_escena(
            encargo.extension_objetivo, len(apertura.escenas)
        ),
    )

    return ResultadoDeApertura(
        ya_estaba=False,
        capitulos=tuple(capitulos[o] for o in sorted(capitulos)),
        escenas=escenas,
        personajes=tuple(personajes.values()),
        lugares=tuple(lugares.values()),
        eventos=tuple(eventos.values()),
    )


# Suelo y techo del reparto. Por debajo de 80 palabras no hay escena, hay una frase. El
# techo sale del de salida de 4.000 tokens (`architecture.md` 4.2): 1.200 palabras en
# castellano son unos 2.000 tokens, y deja sitio al bloque de hechos sin rozar el truncado.
PALABRAS_MINIMAS_POR_ESCENA = 80
PALABRAS_MAXIMAS_POR_ESCENA = 1200


def palabras_por_escena(extension_objetivo: int, escenas: int) -> int | None:
    """Cuanto le toca a cada escena de la extension que pidio el cliente.

    Hasta ahora la extension del encargo no llegaba a ninguna parte: toda escena se pedia
    a 800 palabras, y una novela encargada corta salia cuatro veces mas larga.
    """
    if escenas <= 0 or extension_objetivo <= 0:
        return None
    reparto = extension_objetivo // escenas
    return max(PALABRAS_MINIMAS_POR_ESCENA, min(PALABRAS_MAXIMAS_POR_ESCENA, reparto))


def _persistir_escenas(
    conn: Conexion,
    planificadas: Sequence[EscenaPlanificada],
    *,
    sufijo: str,
    capitulos: dict[int, str],
    personajes: dict[str, str],
    lugares: dict[str, str],
    eventos: dict[str, str],
    hechos_requeridos: Sequence[str],
    palabras_por_escena: int | None = None,
) -> tuple[str, ...]:
    """Las escenas, numeradas dentro de su capitulo y enlazadas a lo que renderizan."""
    ordinal: dict[int, int] = {}
    identificadores: list[str] = []

    for numero, escena in enumerate(planificadas, start=1):
        ordinal[escena.capitulo_orden] = ordinal.get(escena.capitulo_orden, 0) + 1
        identificador = f"esc-{sufijo}-{numero}"
        identificadores.append(identificador)
        conn.execute(
            "INSERT INTO escena (id, capitulo_id, orden, pov_id, lugar_id, "
            "momento_en_historia, objetivo, conflicto, resultado, valor_entrada, "
            "valor_salida, funcion_en_trama, tipo, presupuesto_palabras) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identificador,
                capitulos[escena.capitulo_orden],
                ordinal[escena.capitulo_orden],
                personajes[escena.pov_id],
                lugares[escena.lugar_id],
                escena.momento_en_historia,
                escena.objetivo,
                escena.conflicto,
                escena.resultado,
                escena.valor_entrada,
                escena.valor_salida,
                escena.funcion_en_trama.value,
                escena.tipo.value,
                palabras_por_escena,
            ),
        )
        conn.execute(
            "INSERT INTO escena_evento (escena_id, evento_id) VALUES (?, ?)",
            (identificador, eventos[escena.renderiza]),
        )
        for hecho in hechos_requeridos:
            # Los hechos requeridos son del plan, no de la escena: el Planner de v1.1.0 no
            # los reparte todavia. Anotarlos en todas es lo unico honesto mientras no lo
            # haga: la alternativa es no anotarlos, y entonces la fuga epistemica se
            # evaluaria sobre cero hechos y saldria limpia por no haber mirado.
            conn.execute(
                "INSERT OR IGNORE INTO escena_hecho_requerido (escena_id, hecho_id) "
                "VALUES (?, ?)",
                (identificador, hecho),
            )

    return tuple(identificadores)


def _sufijo(volumen_id: str) -> str:
    """La parte distintiva del identificador del volumen, para namespacear el canon."""
    return volumen_id.split("-", 1)[-1] if "-" in volumen_id else volumen_id


def _tono_de(promesa: str) -> str:
    """El tono que el Entrevistador dejo escrito dentro de la promesa al lector."""
    coincidencia = re.search(r"el tono sera (.+?)\.?$", promesa, re.I)
    return coincidencia.group(1).strip() if coincidencia else "el del encargo"
