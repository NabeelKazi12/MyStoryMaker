"""Cierre del encargo: de la entrevista a la novela creada.

Vive en `orchestrator/` y no en `api/` porque coordina un rol -el Entrevistador- con el
almacen, y `CLAUDE.md` 4 dice que `api/` no importa de `agents/`. La ruta HTTP encola y
lee estado; quien habla con los roles es esto.

Cubre RF-CFG-06 y RF-CFG-02.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.agents.entrevistador.entrevistador import (
    BriefIncompleto,
    Encargo,
    Entrevista,
    construir_encargo,
    envolver_texto_no_confiable,
    extraer_hechos_propuestos,
)
from backend.store.database import Conexion
from backend.store.personajes import PersonajesDeclarados
from backend.store.repositories import AuditLog, ListasProhibidas


class EntrevistaSinCerrar(Exception):
    """La entrevista no da para crear la novela, con lo que falta y lo que choca.

    Existe para que `api/` pueda traducirlo a un `422` sin importar de `agents/`: la
    frontera de `CLAUDE.md` 4 no se rompe ni «solo para el tipo de la excepcion».
    """

    def __init__(
        self, huecos: tuple[str, ...], contradicciones: tuple[tuple[tuple[str, str], str], ...]
    ) -> None:
        self.huecos = huecos
        self.contradicciones = contradicciones
        super().__init__(
            f"Entrevista sin cerrar. Faltan: {', '.join(huecos) or 'nada'}. "
            f"Chocan: {len(contradicciones)} par(es)."
        )


@dataclass(frozen=True)
class NovelaCreada:
    """Lo que queda cuando una entrevista se cierra bien."""

    brief_id: str
    volumen_id: str
    titulo: str
    destinatario: str
    palabras_vetadas: tuple[str, ...] = ()
    intentos_de_injection: tuple[str, ...] = ()
    hechos_propuestos: tuple[str, ...] = field(default_factory=tuple)


def crear_novela_desde_entrevista(
    conn: Conexion, respuestas: dict[str, Any], texto_libre: str = ""
) -> NovelaCreada:
    """Construye el encargo y lo persiste entero, o no escribe nada.

    Lanza `EntrevistaSinCerrar` si la entrevista no esta cerrada: un brief a medias es
    peor que ninguno, porque parece que el encargo existe.
    """
    brief_id = f"br-{uuid.uuid4().hex[:10]}"
    try:
        encargo = construir_encargo(brief_id, respuestas)
    except BriefIncompleto:
        entrevista = Entrevista(respuestas=respuestas)
        raise EntrevistaSinCerrar(
            huecos=entrevista.huecos,
            contradicciones=tuple((c.campos, c.detalle) for c in entrevista.contradicciones),
        ) from None

    intentos: tuple[str, ...] = ()
    propuestos: tuple[str, ...] = ()
    if texto_libre.strip():
        envuelto = envolver_texto_no_confiable(texto_libre)
        intentos = envuelto.intentos_de_injection
        propuestos = tuple(
            h.enunciado for h in extraer_hechos_propuestos(texto_libre, origen="texto_libre")
        )

    volumen_id = f"vol-{uuid.uuid4().hex[:10]}"
    titulo = f"Para {encargo.destinatario.nombre}"

    _persistir(conn, encargo, volumen_id=volumen_id, titulo=titulo)
    _registrar_intentos(conn, intentos, brief_id=brief_id)

    return NovelaCreada(
        brief_id=brief_id,
        volumen_id=volumen_id,
        titulo=titulo,
        destinatario=encargo.destinatario.nombre,
        palabras_vetadas=encargo.palabras_vetadas,
        intentos_de_injection=intentos,
        hechos_propuestos=propuestos,
    )


def _persistir(conn: Conexion, encargo: Encargo, *, volumen_id: str, titulo: str) -> None:
    conn.execute(
        "INSERT INTO brief (id, genero, premisa, promesa_al_lector, extension_objetivo) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            encargo.brief.id,
            encargo.brief.genero,
            encargo.brief.premisa,
            encargo.brief.promesa_al_lector,
            encargo.brief.extension_objetivo,
        ),
    )
    conn.execute(
        "INSERT INTO volumen (id, titulo, brief_id) VALUES (?, ?, ?)",
        (volumen_id, titulo, encargo.brief.id),
    )
    conn.execute(
        "INSERT INTO destinatario (id, brief_id, nombre, edad, rasgos, dedicatoria) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            encargo.destinatario.id,
            encargo.brief.id,
            encargo.destinatario.nombre,
            encargo.destinatario.edad,
            "|".join(encargo.destinatario.rasgos),
            encargo.destinatario.dedicatoria,
        ),
    )
    for elemento in encargo.destinatario.elementos:
        conn.execute(
            "INSERT INTO elemento_personalizado "
            "(id, destinatario_id, tipo, contenido, obligatorio) VALUES (?, ?, ?, ?, ?)",
            (
                elemento.id,
                encargo.destinatario.id,
                elemento.tipo.value,
                elemento.contenido,
                1 if elemento.obligatorio else 0,
            ),
        )

    # Los personajes declarados, con la destinataria delante (SPEC-011).
    PersonajesDeclarados(conn).reemplazar(encargo.brief.id, encargo.personajes)

    listas = ListasProhibidas(conn)
    for numero, palabra in enumerate(encargo.palabras_vetadas, start=1):
        listas.anadir(
            f"lp-{encargo.brief.id}-{numero}",
            nivel="cliente",
            termino=palabra,
            ambito_id=encargo.destinatario.id,
            motivo="lo pidio el cliente en la entrevista",
        )


def _registrar_intentos(conn: Conexion, intentos: tuple[str, ...], *, brief_id: str) -> None:
    """Un intento de injection es una decision de politica, y esas se registran siempre.

    Aunque no bloquee nada: si algun dia una se cuela, el rastro es lo unico que permite
    saber cuando empezo.
    """
    log = AuditLog(conn)
    for numero, intento in enumerate(intentos, start=1):
        log.registrar(
            f"al-inj-{brief_id}-{numero}",
            decision="texto_libre_marcado",
            motivo=f"el texto pegado contiene «{intento}», tratado como dato y no como orden",
            ambito="entrevista",
            termino=intento,
        )
