"""Vocabularios controlados del dominio.

Son los de `definitions.md`, apartado «Vocabularios controlados», limitados a los que v1
usa. Estan cerrados a proposito: una enumeracion que crece sin control vuelve a ser texto
libre y ninguna regla es ya ejecutable (`CLAUDE.md` 5.2). Anadir un valor exige un
`RegistroDeDecision`.

Los nombres de clase y los valores van en espanol porque son vocabulario compartido con
los documentos y con los prompts (`CLAUDE.md` 5.1 y 5.3).

Cubre RF-DOM-03.
"""

from __future__ import annotations

from enum import Enum


class VocabularioCerrado(Enum):
    """Base de todos los vocabularios: rechaza lo que no esta declarado.

    `Enum` ya impide construir un valor ajeno, pero su mensaje no nombra la clase ni
    enumera lo admitido, y `CLAUDE.md` 5.3 exige las dos cosas.
    """

    @classmethod
    def _missing_(cls, value: object) -> None:
        admitidos = ", ".join(sorted(member.value for member in cls))
        raise ValueError(
            f"{cls.__name__}: valor no declarado en el vocabulario cerrado. "
            f"Recibido {value!r}; admitidos: {admitidos}. "
            f"Anadir uno exige un RegistroDeDecision (CLAUDE.md 5.2)."
        )


class Relevancia(VocabularioCerrado):
    """Peso de una `Entidad` en la obra. De `definitions.md`, apartado Entidad."""

    PROTAGONICO = "protagonico"
    SECUNDARIO = "secundario"
    AMBIENTAL = "ambiental"


class EstatusOntologico(VocabularioCerrado):
    """Que tipo de existencia tiene una `Entidad` dentro de la diegesis.

    Permite manejar informacion falsa dentro de la ficcion sin corromper el canon.
    """

    REAL = "real_en_la_diegesis"
    RUMOR = "rumor"
    LEGENDARIO = "legendario"
    INVENTADO = "inventado_por_un_personaje"


class TipoDeEvento(VocabularioCerrado):
    """Naturaleza de un `EventoNarrativo`."""

    ACCION = "accion"
    DECISION = "decision"
    REVELACION = "revelacion"
    ENCUENTRO = "encuentro"
    PERDIDA = "perdida"
    CAMBIO_DE_ESTADO = "cambio_de_estado"


class VisibilidadDeEvento(VocabularioCerrado):
    """Quien puede llegar a saber que un `EventoNarrativo` ocurrio."""

    PUBLICO = "publico"
    PRIVADO = "privado"
    SECRETO = "secreto"


class RolEnEvento(VocabularioCerrado):
    """Papel de una `Entidad` dentro de un `EventoNarrativo`."""

    AGENTE = "agente"
    PACIENTE = "paciente"
    TESTIGO = "testigo"
    MENCIONADO = "mencionado"


class FuncionEnTrama(VocabularioCerrado):
    """Papel estructural de una `Escena`."""

    DETONANTE = "detonante"
    COMPLICACION = "complicacion"
    GIRO = "giro"
    REVELACION = "revelacion"
    CRISIS = "crisis"
    CLIMAX = "climax"
    SECUELA = "secuela"
    RESOLUCION = "resolucion"


class TipoDeEscena(VocabularioCerrado):
    """Escena de accion frente a secuela reflexiva, y el resto del reparto."""

    ACCION = "accion"
    SECUELA = "secuela"
    DIALOGO = "dialogo"
    TRANSICION = "transicion"
    INTERLUDIO = "interludio"


class TipoDeHilo(VocabularioCerrado):
    """Clase de subtrama. Determina cada cuantas escenas puede estar inactiva."""

    PRINCIPAL = "principal"
    SECUNDARIO = "secundario"
    ROMANTICO = "romantico"
    MISTERIO = "misterio"
    TEMATICO = "tematico"
    DE_PERSONAJE = "de_personaje"


class TipoDeArco(VocabularioCerrado):
    """Forma del arco de un `Personaje`."""

    POSITIVO = "positivo"
    NEGATIVO = "negativo"
    PLANO = "plano"
    CORRUPTOR = "corruptor"
    REDENTOR = "redentor"


class TipoDeSiembra(VocabularioCerrado):
    """Que se siembra en un `ParSiembraPago`."""

    OBJETO = "objeto"
    HABILIDAD = "habilidad"
    INFORMACION = "informacion"
    AMENAZA = "amenaza"
    RELACION = "relacion"
    PREGUNTA = "pregunta"


class EstadoDeSiembra(VocabularioCerrado):
    """Estado de un `ParSiembraPago`. Al cierre del volumen ninguno queda `abierto`."""

    ABIERTO = "abierto"
    RESUELTO = "resuelto"
    SUBVERTIDO = "subvertido"
    ABANDONADO = "abandonado"


class EstadoDeBorrador(VocabularioCerrado):
    """Estado de un `Borrador`. Solo uno por escena puede estar `aceptado`."""

    PROPUESTO = "propuesto"
    EN_REVISION = "en_revision"
    ACEPTADO = "aceptado"
    RECHAZADO = "rechazado"
    OBSOLETO = "obsoleto"


class EstadoDeTarea(VocabularioCerrado):
    """Estado de una `Tarea`. El vocabulario es el de `AGENTS.md` 7.1."""

    PENDIENTE = "pendiente"
    LISTA = "lista"
    EN_CURSO = "en_curso"
    EN_VERIFICACION = "en_verificacion"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    ESCALADA = "escalada"
    FALLIDA = "fallida"
    BLOQUEADA = "bloqueada"
    CANCELADA = "cancelada"


class Severidad(VocabularioCerrado):
    """Gravedad de un `Defecto`. Ordena lo que hace el Orquestador al detectarlo."""

    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    INFORMATIVA = "informativa"


class DimensionDeEstado(VocabularioCerrado):
    """Dimensiones variables de un personaje. Son la semilla del catalogo de predicados."""

    SALUD = "salud"
    UBICACION = "ubicacion"
    LEALTAD = "lealtad"
    EMOCION = "emocion"
    RECURSOS = "recursos"
    REPUTACION = "reputacion"
    CONOCIMIENTO = "conocimiento"


class ExclusividadDePredicado(VocabularioCerrado):
    """Si un predicado admite un solo valor vigente por sujeto o varios.

    Lo introduce esta version del backend (SPEC-001, 9.2 R-7) y es lo que convierte
    «contradiccion de hechos» en un predicado ejecutable.
    """

    FUNCIONAL = "funcional"
    MULTIVALOR = "multivalor"


class TipoDeElementoPersonalizado(VocabularioCerrado):
    """Que ata una novela a quien la recibe. De `definitions.md`, apartado Destinatario.

    Tres valores y no mas: son los que el rol entrevistador sabe recoger y los que el
    validador de RF-VAL-04 sabe buscar en los capitulos. Un cuarto valor que nadie
    comprueba seria vocabulario decorativo (`CLAUDE.md` 5.2).
    """

    RECUERDO = "recuerdo"
    RASGO = "rasgo"
    VINCULO = "vinculo"


class ClaseDeFallo(VocabularioCerrado):
    """Las cuatro clases de `architecture.md` 6.5 D-06.

    Solo contrato y contenido suman intento narrativo.
    """

    TRANSPORTE = "transporte"
    CONTRATO = "contrato"
    CONTENIDO = "contenido"
    PRESUPUESTO = "presupuesto"
