"""Contrato del Entrevistador: que recoge, que detecta y que se niega a inventar.

Este rol es el unico que habla con el cliente, y por eso es el unico por el que entra
texto que nadie del sistema ha escrito. De ahi salen sus tres obligaciones:

1. **Lo que falta se pregunta.** Rellenar un hueco con una suposicion razonable es el
   fallo caro de este paso: nadie la revisa despues, porque no parece una pregunta,
   parece un dato (`AGENTS.md` 10.2 dice lo mismo de las specs).
2. **Lo que choca se nombra.** Una contradiccion detectada y no dicha se traslada al
   capitulo 1, donde ya cuesta invocaciones. Y decir «hay una contradiccion» no sirve:
   hay que decir entre que campos.
3. **El texto libre es dato, no instruccion.** Va envuelto y marcado, y lo que parezca
   una orden se anota como intento en lugar de ejecutarse. Un sistema que obedece al
   texto que le pegan no tiene politica, tiene sugerencias.

Cubre RF-CFG-01 a RF-CFG-07.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.domain.errors import ErrorDeDominio
from backend.domain.spec.encargo import (
    LARGO_MAXIMO_DE_LA_DESCRIPCION,
    LARGO_MAXIMO_DE_LA_RELACION,
    LARGO_MAXIMO_DEL_NOMBRE,
    MAXIMO_DE_PERSONAJES,
    RELACION_DE_LA_DESTINATARIA,
    Brief,
    Destinatario,
    ElementoPersonalizado,
    PersonajeDeclarado,
    clave_de_nombre,
)
from backend.domain.vocabularies import Relevancia, TipoDeElementoPersonalizado

VERSION_DE_PROMPT = "1.0.0"
PROMPTS = Path(__file__).parent / "prompts"

# Los siete del alcance. Ni uno menos: cada uno alimenta algo que se comprueba despues.
CAMPOS_DE_LA_ENTREVISTA: tuple[str, ...] = (
    "nombre",
    "edad",
    "rasgos",
    "recuerdos",
    "genero",
    "tono",
    "extension",
)

# Edad minima declarada por tono. Es una **politica del entrevistador**, no un vocabulario
# del dominio: por eso vive aqui y no en `domain/vocabularies.py`. Un tono que no esta en
# la tabla no tiene edad minima declarada y por tanto no choca con ninguna edad; inventarle
# una haria que el rol rechazara encargos que nadie ha vetado.
EDAD_MINIMA_POR_TONO: dict[str, int] = {
    "noir": 16,
    "terror": 16,
    "erotico": 18,
    "satirico": 14,
}

# Formas en que un texto pegado intenta dejar de ser dato. La lista es corta a proposito:
# cada patron nuevo aumenta los falsos positivos, y marcar todo como sospechoso es lo
# mismo que no marcar nada. Los que no caza el patron los caza el envoltorio, que es la
# defensa de verdad: el texto nunca se concatena como instruccion.
PATRONES_DE_INJECTION: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignora\s+(las\s+)?instrucciones", re.I),
    re.compile(r"olvida\s+(todo\s+)?lo\s+anterior", re.I),
    re.compile(r"^\s*(system|assistant)\s*:", re.I | re.M),
    re.compile(r"revela\s+(el\s+)?(prompt|sistema)", re.I),
    re.compile(r"actua\s+como\s+si\s+no\s+tuvieras", re.I),
)

APERTURA = "<<<texto_no_confiable"
CIERRE = "texto_no_confiable>>>"


class BriefIncompleto(ValueError):
    """La entrevista no da para construir un encargo, y se dice por que.

    Nombra los huecos y las contradicciones: «datos invalidos» obligaria a volver a
    preguntarlo todo.
    """

    def __init__(self, faltan: Sequence[str], choques: Sequence[Contradiccion]) -> None:
        self.faltan = tuple(faltan)
        self.choques = tuple(choques)
        partes = []
        if faltan:
            partes.append(f"faltan: {', '.join(faltan)}")
        if choques:
            # El par de campos va delante del detalle: es lo que le dice al cliente entre
            # que dos respuestas suyas tiene que elegir.
            partes.append(
                "; ".join(f"{c.campos[0]} vs {c.campos[1]}: {c.detalle}" for c in choques)
            )
        super().__init__(f"La entrevista no esta cerrada. {'. '.join(partes)}.")


@dataclass(frozen=True)
class Contradiccion:
    """Dos datos de la entrevista que no pueden ser ciertos a la vez."""

    campos: tuple[str, str]
    detalle: str


@dataclass(frozen=True)
class TextoNoConfiable:
    """Texto aportado por el cliente, enmarcado para que no pueda leerse como orden."""

    texto: str
    intentos_de_injection: tuple[str, ...] = ()


@dataclass(frozen=True)
class HechoPropuesto:
    """Algo que el texto libre afirma. Propuesta, nunca canon.

    Entra por el mismo camino de canonizacion que todo lo demas: contrastado contra el
    canon vigente y promovido solo si no contradice. Dejarlo entrar directo seria la via
    de exfiltracion mas simple que existe.
    """

    enunciado: str
    origen: str
    confiable: bool = False


@dataclass(frozen=True)
class Encargo:
    """Lo que la entrevista produce cuando esta cerrada: dos objetos tipados."""

    brief: Brief
    destinatario: Destinatario
    palabras_vetadas: tuple[str, ...] = ()
    # La persona destinataria primero, siempre protagonista; despues, los demas en el
    # orden en que se declararon (SPEC-011).
    personajes: tuple[PersonajeDeclarado, ...] = ()


@dataclass(frozen=True)
class Entrevista:
    """Las respuestas recogidas, con lo que falta y lo que choca a la vista."""

    respuestas: Mapping[str, Any]

    @property
    def huecos(self) -> tuple[str, ...]:
        return huecos(self.respuestas)

    @property
    def contradicciones(self) -> tuple[Contradiccion, ...]:
        return contradicciones(self.respuestas)

    @property
    def completa(self) -> bool:
        return not self.huecos and not self.contradicciones


def huecos(respuestas: Mapping[str, Any]) -> tuple[str, ...]:
    """Los campos de la entrevista que no tienen dato.

    Una clave presente con cadena vacia o coleccion vacia cuenta como hueco: el dato no
    esta, y que la clave exista solo lo disimula.
    """
    faltan = []
    for campo in CAMPOS_DE_LA_ENTREVISTA:
        valor = respuestas.get(campo)
        if valor is None:
            faltan.append(campo)
        elif isinstance(valor, str) and not valor.strip():
            faltan.append(campo)
        elif isinstance(valor, (list, tuple, set, dict)) and not valor:
            faltan.append(campo)
    return tuple(faltan)


def contradicciones(respuestas: Mapping[str, Any]) -> tuple[Contradiccion, ...]:
    """Las incompatibilidades declaradas entre datos de la entrevista.

    Hoy una: edad frente a tono, que es la que RF-CFG-04 exige. Anadir otra es anadir una
    fila a `EDAD_MINIMA_POR_TONO` o una funcion aqui, no reescribir el rol.
    """
    choques: list[Contradiccion] = []

    edad = respuestas.get("edad")
    tono = respuestas.get("tono")
    if isinstance(edad, int) and isinstance(tono, str):
        minima = EDAD_MINIMA_POR_TONO.get(tono.strip().lower())
        if minima is not None and edad < minima:
            choques.append(
                Contradiccion(
                    campos=("edad", "tono"),
                    detalle=(
                        f"el destinatario tiene {edad} anos y el tono «{tono}» se declara "
                        f"a partir de {minima}: uno de los dos datos esta mal"
                    ),
                )
            )

    nombre = respuestas.get("nombre")
    _, problemas = leer_personajes(
        nombre if isinstance(nombre, str) else "", respuestas.get("personajes"), prefijo="x"
    )
    choques.extend(problemas)

    return tuple(choques)


def leer_personajes(
    nombre_de_la_destinataria: str, crudos: object, *, prefijo: str
) -> tuple[tuple[PersonajeDeclarado, ...], tuple[Contradiccion, ...]]:
    """Los personajes declarados, con la destinataria delante, o lo que falla en ellos.

    Lo usan la entrevista y la edicion desde el Taller, para que las dos digan lo mismo
    del mismo personaje. La destinataria no la elige quien escribe la lista: sale del
    nombre de la entrevista, es protagonista y su relacion es fija; de lo que se mande
    para ella solo se toma la descripcion (SPEC-011 RF-PER-02).

    Un problema se dice nombrando al personaje: «un personaje no vale» obligaria a
    revisarlos todos (RF-PER-04).
    """
    problemas: list[Contradiccion] = []

    def problema(quien: str, detalle: str) -> None:
        problemas.append(Contradiccion(campos=("personajes", quien), detalle=detalle))

    if crudos is None:
        crudos = []
    if not isinstance(crudos, (list, tuple)):
        problema("personajes", "los personajes tienen que llegar como una lista")
        return (), tuple(problemas)

    descripcion_de_la_destinataria = ""
    otros: list[object] = []
    for crudo in crudos:
        if isinstance(crudo, Mapping) and crudo.get("es_destinatario"):
            descripcion_de_la_destinataria = str(crudo.get("descripcion") or "").strip()
        else:
            otros.append(crudo)

    if 1 + len(otros) > MAXIMO_DE_PERSONAJES:
        problema(
            "personajes",
            f"hay {1 + len(otros)} personajes y el maximo es {MAXIMO_DE_PERSONAJES}, "
            "contando a la persona destinataria",
        )

    vistos: dict[str, str] = {}
    destinataria = nombre_de_la_destinataria.strip()
    if destinataria:
        vistos[clave_de_nombre(destinataria)] = destinataria

    validos: list[tuple[str, Relevancia, str, str]] = []
    for numero, crudo in enumerate(otros, start=2):
        if not isinstance(crudo, Mapping):
            problema(
                f"personaje {numero}",
                f"el personaje {numero} no tiene la forma nombre, papel, relacion y "
                "descripcion",
            )
            continue
        nombre = str(crudo.get("nombre") or "").strip()
        papel = str(crudo.get("papel") or "").strip()
        relacion = str(crudo.get("relacion") or "").strip()
        descripcion = str(crudo.get("descripcion") or "").strip()
        quien = nombre or f"personaje {numero}"
        if not nombre:
            problema(quien, f"el personaje {numero} no tiene nombre")
            continue
        if len(nombre) > LARGO_MAXIMO_DEL_NOMBRE:
            problema(
                quien,
                f"«{nombre[:20]}…» tiene {len(nombre)} caracteres de nombre y el maximo es "
                f"{LARGO_MAXIMO_DEL_NOMBRE}",
            )
            continue
        if papel not in {r.value for r in Relevancia}:
            problema(
                quien,
                f"«{nombre}»: el papel «{papel}» no existe; hay protagonico, secundario y "
                "ambiental",
            )
            continue
        if len(relacion) > LARGO_MAXIMO_DE_LA_RELACION:
            problema(
                quien,
                f"«{nombre}»: la relacion tiene {len(relacion)} caracteres y el maximo es "
                f"{LARGO_MAXIMO_DE_LA_RELACION}",
            )
            continue
        if len(descripcion) > LARGO_MAXIMO_DE_LA_DESCRIPCION:
            problema(
                quien,
                f"«{nombre}»: la descripcion tiene {len(descripcion)} caracteres y el maximo "
                f"es {LARGO_MAXIMO_DE_LA_DESCRIPCION}",
            )
            continue
        clave = clave_de_nombre(nombre)
        if clave in vistos:
            igual = vistos[clave]
            problema(
                quien,
                f"«{nombre}» se llama igual que la persona destinataria"
                if destinataria and igual == destinataria
                else f"«{nombre}» esta repetido: ya hay un personaje llamado «{igual}»",
            )
            continue
        vistos[clave] = nombre
        validos.append((nombre, Relevancia(papel), relacion, descripcion))

    if problemas or not destinataria:
        return (), tuple(problemas)

    try:
        personajes = [
            PersonajeDeclarado(
                id=f"{prefijo}-personaje-1",
                nombre=destinataria,
                papel=Relevancia.PROTAGONICO,
                relacion=RELACION_DE_LA_DESTINATARIA,
                descripcion=descripcion_de_la_destinataria,
                es_destinatario=True,
            )
        ] + [
            PersonajeDeclarado(
                id=f"{prefijo}-personaje-{orden}",
                nombre=nombre,
                papel=papel,
                relacion=relacion,
                descripcion=descripcion,
            )
            for orden, (nombre, papel, relacion, descripcion) in enumerate(validos, start=2)
        ]
    except ErrorDeDominio as error:
        # Lo unico que puede llegar aqui es la descripcion de la destinataria, que no pasa
        # por los filtros de arriba.
        problema(destinataria, str(error))
        return (), tuple(problemas)
    return tuple(personajes), ()


def envolver_texto_no_confiable(texto: str) -> TextoNoConfiable:
    """Enmarca el texto del cliente y anota lo que parezca una orden.

    El texto **no se censura**: se conserva entero, porque de el salen los recuerdos que
    la novela tiene que contar. Lo que cambia es su estatus: entra delimitado, y ningun
    prompt lo concatena como instruccion.
    """
    intentos = tuple(
        coincidencia.group(0).strip()
        for patron in PATRONES_DE_INJECTION
        for coincidencia in patron.finditer(texto)
    )
    enmarcado = f"{APERTURA}\n{texto.strip()}\n{CIERRE}"
    return TextoNoConfiable(texto=enmarcado, intentos_de_injection=intentos)


def extraer_hechos_propuestos(texto: str, *, origen: str) -> tuple[HechoPropuesto, ...]:
    """Parte el texto libre en afirmaciones, todas marcadas como no confiables.

    La extraccion es deliberadamente tonta -una frase, una propuesta- porque su salida no
    decide nada: es material para que el planner pregunte y para que la canonizacion
    contraste. Una extraccion lista aqui daria la impresion de que el canon ya esta hecho.
    """
    frases = [frase.strip() for frase in re.split(r"(?<=[.!?])\s+", texto) if frase.strip()]
    return tuple(
        HechoPropuesto(enunciado=frase, origen=origen, confiable=False) for frase in frases
    )


def construir_encargo(brief_id: str, respuestas: Mapping[str, Any]) -> Encargo:
    """Convierte una entrevista cerrada en `Brief` mas `Destinatario`.

    Falla si queda algun hueco o alguna contradiccion: dejar pasar cualquiera de los dos
    traslada el problema al capitulo 1, donde ya cuesta invocaciones.
    """
    entrevista = Entrevista(respuestas=respuestas)
    if not entrevista.completa:
        raise BriefIncompleto(entrevista.huecos, entrevista.contradicciones)

    recuerdos = tuple(respuestas["recuerdos"])
    rasgos = tuple(str(r) for r in respuestas["rasgos"])

    elementos = [
        ElementoPersonalizado(
            id=f"{brief_id}-recuerdo-{numero}",
            tipo=TipoDeElementoPersonalizado.RECUERDO,
            contenido=str(recuerdo),
        )
        for numero, recuerdo in enumerate(recuerdos, start=1)
    ]
    # Los rasgos enriquecen y no bloquean: exigir que cada uno aparezca en algun capitulo
    # convertiria el validador de RF-VAL-04 en un bloqueo permanente.
    elementos += [
        ElementoPersonalizado(
            id=f"{brief_id}-rasgo-{numero}",
            tipo=TipoDeElementoPersonalizado.RASGO,
            contenido=rasgo,
            obligatorio=False,
        )
        for numero, rasgo in enumerate(rasgos, start=1)
    ]

    brief = Brief(
        id=brief_id,
        genero=str(respuestas["genero"]),
        premisa=f"Novela de regalo para {respuestas['nombre']}",
        promesa_al_lector=(
            f"quien la lea reconocera a {respuestas['nombre']} en ella, y el tono "
            f"sera {respuestas['tono']}"
        ),
        extension_objetivo=int(respuestas["extension"]),
    )
    destinatario = Destinatario(
        id=f"{brief_id}-destinatario",
        nombre=str(respuestas["nombre"]),
        edad=int(respuestas["edad"]),
        rasgos=rasgos,
        elementos=tuple(elementos),
        dedicatoria=str(respuestas.get("dedicatoria", "")),
    )
    vetadas = tuple(str(p) for p in respuestas.get("palabras_vetadas", ()))
    personajes, _ = leer_personajes(
        destinatario.nombre, respuestas.get("personajes"), prefijo=brief_id
    )

    return Encargo(
        brief=brief, destinatario=destinatario, palabras_vetadas=vetadas, personajes=personajes
    )


def prompt_vigente() -> str:
    """El prompt de la version declarada."""
    return (PROMPTS / f"v{VERSION_DE_PROMPT}.md").read_text(encoding="utf-8")
