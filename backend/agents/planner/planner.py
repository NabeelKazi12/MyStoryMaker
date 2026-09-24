"""Contrato del Planner: el canon minimo de la novela y su reparto en capitulos.

El planner no escribe prosa y no toca el canon. Produce lo que el orquestador convierte en
filas y en `Tarea`s, y declara los `hechos_requeridos`, que son el cuello de botella de
anotacion que SPEC-001 dejo declarado como riesgo: sin ellos la fuga epistemica se evalua
sobre menos hechos de los que la escena usa, que es F-02 de `verification.md` 11.

Desde `v1.1.0` el rol abre ademas el canon (SPEC-004, RF-APE-01): una novela recien salida
de la entrevista no tiene personajes, ni lugares, ni eventos, y sin ellos no hay escena que
redactar. Lo que este modulo hace con esa apertura es **validarla**, no arreglarla: una fila
que no valida rechaza el plan entero, porque parchear una referencia rota aqui produce una
escena que apunta a un lugar que nadie declaro y que nadie va a echar de menos.

Cubre RF-HAR-01 y RF-APE-01 a RF-APE-05.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backend.domain.spec.encargo import clave_de_nombre
from backend.domain.vocabularies import (
    FuncionEnTrama,
    Relevancia,
    TipoDeEscena,
    TipoDeEvento,
)

VERSION_DE_PROMPT = "1.3.0"
PROMPTS = Path(__file__).parent / "prompts"


# Hash del fichero de cada version publicada, igual que en el Redactor. Editar un prompt
# sin subir la version rompe la reproducibilidad de todo lo generado antes, y se detecta
# porque el hash cambia y la version no (RF-WRK-07, RF-APE-05).
MANIFIESTO = {
    "1.0.0": "e35f5b786041155820ffb1b76850c394c25d4650aa2149e474a4f3672eb8320d",
    "1.1.0": "1b2011b94a788b9de6424e0e2f949ee3377177e89f293641fe4dbe5fd9c3b930",
    # v1.2.0 no cambia el esquema: dice el tipo de cada columna y trae un ejemplo, porque
    # con un modelo real la v1.1.0 recibia «inicio» donde el esquema pide un numero.
    "1.2.0": "2f5eb97b7d58f6fecb8ed460af1e6676ad351deec2039c6d59face61e291daa9",
    # v1.3.0 recibe los personajes declarados del encargo y la regla de usarlos todos con
    # su nombre y su relevancia (SPEC-011). El esquema de salida no cambia.
    "1.3.0": "50a7dfdeaecc15b807d9f50c710b360169e8867d60c3e6e7e35b73797c46bd63",
}


class PromptDelPlannerAlterado(Exception):
    """El fichero de prompt no coincide con el hash de su version declarada."""

    def __init__(self, version: str, esperado: str, encontrado: str) -> None:
        super().__init__(
            f"Prompt del Planner v{version}: el fichero ha cambiado sin que suba la "
            f"version. Esperado {esperado[:12]}..., encontrado {encontrado[:12]}.... "
            f"Incrementa la version en lugar de editar en sitio: si no, todo lo generado "
            f"antes deja de ser reproducible y nada lo avisa."
        )


class SalidaInvalidaDelPlanner(Exception):
    """El plan no valida contra su esquema. Es fallo de contrato (D-06)."""

    def __init__(self, motivo: str) -> None:
        super().__init__(f"PlanDeCapitulos: {motivo}")


@dataclass(frozen=True)
class CapituloPlanificado:
    """Un capitulo del plan: que numero ocupa, como se llama y que evento narra.

    `cubre` son los recuerdos obligatorios del encargo que este capitulo se compromete a
    contener. Es una columna declarada y no una inferencia por parecido del texto: buscar
    el recuerdo dentro de la sinopsis acertaria a veces, y las veces que fallara nadie las
    vería, porque el regalo seguiria pareciendo completo.
    """

    orden: int
    titulo: str
    evento_id: str
    sinopsis: str
    cubre: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanDeCapitulos:
    """El reparto entero, con los hechos que la novela necesita tener anotados."""

    capitulos: tuple[CapituloPlanificado, ...]
    hechos_requeridos: tuple[str, ...]

    @property
    def orden_de_lectura(self) -> tuple[str, ...]:
        """Los titulos en el orden en que se leen. Es lo que alimenta el checkpoint."""
        return tuple(c.titulo for c in sorted(self.capitulos, key=lambda c: c.orden))


@dataclass(frozen=True)
class PersonajePropuesto:
    """Un personaje que la novela necesita. Propuesta, no canon: se contrasta al entrar."""

    id: str
    nombre_canonico: str
    relevancia: Relevancia
    necesidad_interna: str
    anio_de_nacimiento: int | None = None


@dataclass(frozen=True)
class LugarPropuesto:
    """Un lugar de la novela, con la atmosfera que el Redactor puede usar."""

    id: str
    nombre_canonico: str
    atmosfera_sensorial: str = ""


@dataclass(frozen=True)
class EventoPropuesto:
    """Algo que pasa en la historia, con su posicion, su lugar y quien participa."""

    id: str
    descripcion: str
    posicion_en_historia: int
    tipo: TipoDeEvento
    lugar_id: str
    participante_id: str


@dataclass(frozen=True)
class EscenaPlanificada:
    """El esqueleto de una escena, con los campos obligatorios de `AGENTS.md` 4.2."""

    id: str
    capitulo_orden: int
    pov_id: str
    lugar_id: str
    momento_en_historia: int
    objetivo: str
    conflicto: str
    resultado: str
    valor_entrada: str
    valor_salida: str
    funcion_en_trama: FuncionEnTrama
    tipo: TipoDeEscena
    renderiza: str


@dataclass(frozen=True)
class Apertura:
    """El canon minimo mas el reparto. Es lo que convierte un encargo en algo redactable."""

    personajes: tuple[PersonajePropuesto, ...] = ()
    lugares: tuple[LugarPropuesto, ...] = ()
    eventos: tuple[EventoPropuesto, ...] = ()
    plan: PlanDeCapitulos | None = None
    escenas: tuple[EscenaPlanificada, ...] = ()
    contexto_insuficiente: bool = False
    falta: tuple[str, ...] = ()

    @property
    def capitulos(self) -> tuple[CapituloPlanificado, ...]:
        return () if self.plan is None else self.plan.capitulos


# --- parseo ---------------------------------------------------------------------------


def parsear_plan(texto: str) -> PlanDeCapitulos:
    """Convierte el reparto en capitulos en un plan tipado, o falla nombrando el motivo.

    Acepta la fila de tres campos de `v1.0.0` y la de cuatro de `v1.1.0`. Que la columna
    nueva sea opcional aqui no la hace opcional en la apertura: alli la cobertura de los
    recuerdos obligatorios se exige, y es donde importa.
    """
    capitulos: list[CapituloPlanificado] = []
    for linea in _seccion(texto, "capitulos").splitlines():
        if not linea.strip():
            continue
        coincidencia = re.match(r"\s*(\d+)\.\s*(.+)", linea)
        if coincidencia is None:
            raise SalidaInvalidaDelPlanner(f"linea de capitulo sin numero: {linea.strip()!r}")
        partes = [parte.strip() for parte in coincidencia.group(2).split("|")]
        if len(partes) not in (3, 4):
            raise SalidaInvalidaDelPlanner(
                f"un capitulo necesita titulo, evento y sinopsis: {linea.strip()!r}"
            )
        capitulos.append(
            CapituloPlanificado(
                orden=int(coincidencia.group(1)),
                titulo=partes[0],
                evento_id=partes[1],
                sinopsis=partes[2],
                cubre=_referencias(partes[3]) if len(partes) == 4 else (),
            )
        )

    if not capitulos:
        raise SalidaInvalidaDelPlanner("el plan no declara ningun capitulo")

    ordenes = [c.orden for c in capitulos]
    if len(set(ordenes)) != len(ordenes):
        raise SalidaInvalidaDelPlanner(
            f"hay orden de capitulo repetido: {sorted(ordenes)}. Con dos capitulos en la "
            f"misma posicion, reanudar desde checkpoint no sabe cual falta"
        )

    hechos = tuple(
        linea.strip("- ").strip()
        for linea in _seccion(texto, "hechos_requeridos").splitlines()
        if linea.strip()
    )
    if not hechos:
        raise SalidaInvalidaDelPlanner(
            "el plan no declara hechos_requeridos: sin ellos la fuga epistemica se evalua "
            "sobre menos hechos de los que la escena usa"
        )

    return PlanDeCapitulos(capitulos=tuple(capitulos), hechos_requeridos=hechos)


def parsear_apertura(
    texto: str,
    *,
    recuerdos_obligatorios: Sequence[str] = (),
    personajes_declarados: Sequence[tuple[str, Relevancia]] = (),
) -> Apertura:
    """Convierte la salida de `v1.1.0` en canon propuesto, o rechaza el plan entero.

    El rechazo es total y no selectivo a proposito (RF-APE-02). Quedarse con las filas que
    validan deja una novela con escenas que apuntan a lugares inexistentes: la base lo
    aceptaria -la clave foranea se comprueba, pero el hueco narrativo no- y el fallo
    aparecería tres capitulos despues, cuando ya cuesta invocaciones.
    """
    # Las vallas de codigo no son contenido: un modelo que envuelve la respuesta en ```
    # no ha cambiado el plan, y esa linea acabaria leida como un hecho requerido.
    texto = "\n".join(
        linea for linea in texto.splitlines() if not linea.strip().startswith("```")
    )
    if "contexto_insuficiente" in texto.lower():
        falta = tuple(
            linea.strip("- ").strip()
            for linea in _seccion(texto, "falta").splitlines()
            if linea.strip()
        )
        if not falta:
            raise SalidaInvalidaDelPlanner(
                "declara contexto_insuficiente sin enumerar que le falta"
            )
        return Apertura(contexto_insuficiente=True, falta=falta)

    personajes = _personajes(_seccion(texto, "personajes"))
    lugares = _lugares(_seccion(texto, "lugares"))
    eventos = _eventos(_seccion(texto, "eventos"))
    plan = parsear_plan(texto)
    escenas = _escenas(_seccion(texto, "escenas"))

    apertura = Apertura(
        personajes=personajes, lugares=lugares, eventos=eventos, plan=plan, escenas=escenas
    )
    _exigir_coherencia(apertura)
    _exigir_cobertura_de_recuerdos(apertura, recuerdos_obligatorios)
    _exigir_personajes_declarados(apertura, personajes_declarados)
    return apertura


def _personajes(bloque: str) -> tuple[PersonajePropuesto, ...]:
    propuestos: list[PersonajePropuesto] = []
    for partes in _filas(bloque, esperados=5, que="un personaje"):
        propuestos.append(
            PersonajePropuesto(
                id=partes[0],
                nombre_canonico=partes[1],
                relevancia=_valor(Relevancia, partes[2], "relevancia"),
                necesidad_interna=partes[3],
                anio_de_nacimiento=_entero_opcional(partes[4]),
            )
        )
    if not propuestos:
        raise SalidaInvalidaDelPlanner("la apertura no declara ningun personaje")
    if not any(p.relevancia is Relevancia.PROTAGONICO for p in propuestos):
        raise SalidaInvalidaDelPlanner(
            "ningun personaje es protagonico: el destinatario del encargo tiene que "
            "reconocerse en la novela, y un reparto sin protagonista no lo permite"
        )
    return tuple(propuestos)


def _lugares(bloque: str) -> tuple[LugarPropuesto, ...]:
    lugares = tuple(
        LugarPropuesto(id=partes[0], nombre_canonico=partes[1], atmosfera_sensorial=partes[2])
        for partes in _filas(bloque, esperados=3, que="un lugar")
    )
    if not lugares:
        raise SalidaInvalidaDelPlanner("la apertura no declara ningun lugar")
    return lugares


def _eventos(bloque: str) -> tuple[EventoPropuesto, ...]:
    eventos = tuple(
        EventoPropuesto(
            id=partes[0],
            descripcion=partes[1],
            posicion_en_historia=_entero(partes[2], "la posicion en la historia"),
            tipo=_valor(TipoDeEvento, partes[3], "tipo de evento"),
            lugar_id=partes[4],
            participante_id=partes[5],
        )
        for partes in _filas(bloque, esperados=6, que="un evento")
    )
    if not eventos:
        raise SalidaInvalidaDelPlanner("la apertura no declara ningun evento")
    return eventos


def _escenas(bloque: str) -> tuple[EscenaPlanificada, ...]:
    escenas = tuple(
        EscenaPlanificada(
            id=partes[0],
            capitulo_orden=_entero(partes[1], "el orden del capitulo"),
            pov_id=partes[2],
            lugar_id=partes[3],
            momento_en_historia=_entero(partes[4], "el momento en la historia"),
            objetivo=partes[5],
            conflicto=partes[6],
            resultado=partes[7],
            valor_entrada=partes[8],
            valor_salida=partes[9],
            funcion_en_trama=_valor(FuncionEnTrama, partes[10], "funcion en trama"),
            tipo=_valor(TipoDeEscena, partes[11], "tipo de escena"),
            renderiza=partes[12],
        )
        for partes in _filas(bloque, esperados=13, que="una escena")
    )
    if not escenas:
        raise SalidaInvalidaDelPlanner("la apertura no declara ninguna escena")
    return escenas


def _exigir_coherencia(apertura: Apertura) -> None:
    """Que nada referencie lo que no se ha declarado, y que ninguna escena sea inerte."""
    personajes = {p.id for p in apertura.personajes}
    lugares = {lugar.id for lugar in apertura.lugares}
    eventos = {e.id for e in apertura.eventos}
    ordenes = {c.orden for c in apertura.capitulos}

    _exigir_sin_repetidos([p.id for p in apertura.personajes], "personaje")
    _exigir_sin_repetidos([lugar.id for lugar in apertura.lugares], "lugar")
    _exigir_sin_repetidos([e.id for e in apertura.eventos], "evento")
    _exigir_sin_repetidos([e.id for e in apertura.escenas], "escena")

    for evento in apertura.eventos:
        _exigir_referencia(evento.lugar_id, lugares, f"el evento {evento.id}", "lugar")
        _exigir_referencia(
            evento.participante_id, personajes, f"el evento {evento.id}", "personaje"
        )

    for capitulo in apertura.capitulos:
        _exigir_referencia(
            capitulo.evento_id, eventos, f"el capitulo {capitulo.orden}", "evento"
        )

    for escena in apertura.escenas:
        _exigir_referencia(escena.pov_id, personajes, f"la escena {escena.id}", "personaje")
        _exigir_referencia(escena.lugar_id, lugares, f"la escena {escena.id}", "lugar")
        _exigir_referencia(escena.renderiza, eventos, f"la escena {escena.id}", "evento")
        if escena.capitulo_orden not in ordenes:
            raise SalidaInvalidaDelPlanner(
                f"la escena {escena.id} dice ir en el capitulo {escena.capitulo_orden}, "
                f"que el plan no declara"
            )
        if escena.valor_entrada == escena.valor_salida:
            # RF-DOM-04. La base tambien lo comprueba, pero aqui se puede decir cual es la
            # escena y por que: alli solo se sabria que un CHECK fallo.
            raise SalidaInvalidaDelPlanner(
                f"la escena {escena.id} entra y sale con el mismo valor "
                f"«{escena.valor_entrada}»: una escena que no cambia nada no es una escena"
            )

    sin_escena = ordenes - {e.capitulo_orden for e in apertura.escenas}
    if sin_escena:
        raise SalidaInvalidaDelPlanner(
            f"estos capitulos no tienen ninguna escena: {sorted(sin_escena)}. Un capitulo "
            f"sin escena no se puede redactar y en la lectura aparece vacio"
        )


def _exigir_cobertura_de_recuerdos(
    apertura: Apertura, recuerdos_obligatorios: Sequence[str]
) -> None:
    """RF-APE-03: lo que el cliente declaro obligatorio tiene capitulo asignado."""
    cubiertos = {recuerdo for c in apertura.capitulos for recuerdo in c.cubre}
    huerfanos = [r for r in recuerdos_obligatorios if r not in cubiertos]
    if huerfanos:
        raise SalidaInvalidaDelPlanner(
            f"estos recuerdos obligatorios no los cubre ningun capitulo: "
            f"{', '.join(huerfanos)}. El cliente los declaro obligatorios, y una novela "
            f"que se los deja fuera parece completa pero no cumple lo que se pidio"
        )


def _exigir_personajes_declarados(
    apertura: Apertura, declarados: Sequence[tuple[str, Relevancia]]
) -> None:
    """SPEC-011 RF-PER-06: cada declarado esta, con su nombre y su papel.

    El nombre se compara sin mayusculas ni acentos: «Lucia» por «Lucía» no deja a nadie
    fuera. El papel, exacto: una hermana declarada protagonista y propuesta de fondo es
    otra novela. El Planner puede anadir los que quiera (RF-PER-07).
    """
    propuestos = {clave_de_nombre(p.nombre_canonico): p for p in apertura.personajes}
    # «Aparecer» es salir en la historia: participar en algun evento o ser el punto de
    # vista de alguna escena. Estar solo en la lista no cuenta: un personaje que ninguna
    # escena usa no sale en la novela, aunque figure en el canon.
    en_la_historia = {e.participante_id for e in apertura.eventos} | {
        s.pov_id for s in apertura.escenas
    }
    ausentes: list[str] = []
    cambiados: list[str] = []
    sin_escena: list[str] = []
    for nombre, papel in declarados:
        propuesto = propuestos.get(clave_de_nombre(nombre))
        if propuesto is None:
            ausentes.append(f"«{nombre}»")
        elif propuesto.relevancia is not papel:
            cambiados.append(
                f"«{nombre}» se declaro {papel.value} y llega {propuesto.relevancia.value}"
            )
        elif propuesto.id not in en_la_historia:
            sin_escena.append(f"«{nombre}»")
    if ausentes or cambiados or sin_escena:
        partes = []
        if ausentes:
            partes.append(f"faltan personajes declarados: {', '.join(ausentes)}")
        if cambiados:
            partes.append("; ".join(cambiados))
        if sin_escena:
            partes.append(
                f"estos personajes declarados no salen en ninguna escena ni evento: "
                f"{', '.join(sin_escena)}"
            )
        raise SalidaInvalidaDelPlanner(
            ". ".join(partes) + ". Quien encarga los declaro antes de escribir, y una "
            "novela que los cambia o se los deja fuera no es la que se pidio"
        )


# --- piezas ----------------------------------------------------------------------------


def _seccion(texto: str, nombre: str) -> str:
    patron = re.compile(rf"^##\s*{nombre}\s*$(.*?)(?=^##\s|\Z)", re.M | re.S | re.I)
    coincidencia = patron.search(texto)
    return coincidencia.group(1) if coincidencia else ""


def _filas(bloque: str, *, esperados: int, que: str) -> list[list[str]]:
    filas: list[list[str]] = []
    for linea in bloque.splitlines():
        if not linea.strip():
            continue
        partes = [parte.strip() for parte in linea.strip("- ").split("|")]
        if len(partes) != esperados:
            raise SalidaInvalidaDelPlanner(
                f"{que} lleva {esperados} campos y esta fila trae {len(partes)}: "
                f"{linea.strip()!r}"
            )
        if not partes[0]:
            raise SalidaInvalidaDelPlanner(f"{que} sin identificador: {linea.strip()!r}")
        filas.append(partes)
    return filas


def _referencias(campo: str) -> tuple[str, ...]:
    if campo.strip() in ("", "-"):
        return ()
    return tuple(parte.strip() for parte in campo.split(",") if parte.strip())


def _entero(campo: str, que: str) -> int:
    try:
        return int(campo)
    except ValueError:
        raise SalidaInvalidaDelPlanner(
            f"{que} tiene que ser un numero, y es {campo!r}"
        ) from None


def _entero_opcional(campo: str) -> int | None:
    if campo.strip() in ("", "-"):
        return None
    return _entero(campo, "el anio de nacimiento")


def _valor[V: Enum](enumeracion: type[V], crudo: str, que: str) -> V:
    """Traduce una celda al valor del vocabulario cerrado, o dice cuales hay.

    Nombrar los permitidos en el mensaje es la diferencia entre corregir el plan de una
    pasada y tener que ir a buscar la enumeracion al codigo.
    """
    # Mayusculas y tildes no cambian el valor: «Protagónico» es `protagonico`.
    normalizado = unicodedata.normalize("NFKD", crudo.strip().lower())
    normalizado = "".join(c for c in normalizado if not unicodedata.combining(c))
    try:
        return enumeracion(normalizado)
    except ValueError:
        permitidos = ", ".join(sorted(str(miembro.value) for miembro in enumeracion))
        raise SalidaInvalidaDelPlanner(
            f"{que} no esta en el vocabulario cerrado: {crudo!r}. Hay {permitidos}"
        ) from None


def _exigir_sin_repetidos(identificadores: list[str], que: str) -> None:
    repetidos = sorted({i for i in identificadores if identificadores.count(i) > 1})
    if repetidos:
        raise SalidaInvalidaDelPlanner(
            f"hay identificador de {que} repetido: {', '.join(repetidos)}"
        )


def _exigir_referencia(identificador: str, declarados: set[str], quien: str, que: str) -> None:
    if identificador not in declarados:
        raise SalidaInvalidaDelPlanner(
            f"{quien} referencia el {que} {identificador!r}, que la apertura no declara"
        )


# --- integridad del prompt ---------------------------------------------------------------


def hash_del_prompt(version: str = "") -> str:
    """Hash del fichero de prompt de una version."""
    objetivo = version or VERSION_DE_PROMPT
    return hashlib.sha256((PROMPTS / f"v{objetivo}.md").read_bytes()).hexdigest()


def verificar_integridad_del_prompt(version: str = "") -> None:
    """Falla si el fichero cambio sin que subiera la version. Corre en integracion continua."""
    objetivo = version or VERSION_DE_PROMPT
    esperado = MANIFIESTO.get(objetivo)
    if esperado is None:
        raise PromptDelPlannerAlterado(
            objetivo, "sin registrar en el manifiesto", "desconocido"
        )
    encontrado = hash_del_prompt(objetivo)
    if encontrado != esperado:
        raise PromptDelPlannerAlterado(objetivo, esperado, encontrado)


def prompt_vigente() -> str:
    return (PROMPTS / f"v{VERSION_DE_PROMPT}.md").read_text(encoding="utf-8")
