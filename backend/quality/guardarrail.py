"""Guardarrail de palabras prohibidas.

Corre en codigo sobre cada capitulo **antes de aceptarlo**, no despues de publicarlo: un
termino vetado que llega a la lectura ya ha hecho el dano que el veto existia para evitar.

Tres decisiones que conviene leer aqui y no deducirlas del codigo:

1. **Normaliza antes de comparar, pero no lo suficiente como para juntar palabras
   distintas.** Sin normalizar, esquivar el veto cuesta una tilde. Normalizando de mas,
   un veto sobre `casa` bloquearia `caza` y el guardarrail se volveria imposible de
   razonar. La lista de transformaciones esta cerrada en `normalizar` y es la que
   SPEC-003 5.2 exigia declarar.
2. **Detecta, no corrige.** Una coincidencia devuelve el capitulo al writer para que lo
   reescriba. Tachar la palabra desde aqui produciria prosa que nadie ha escrito y que no
   pasa por ningun validador.
3. **El limite es del guardarrail, no del writer.** Sin limite, un writer que insiste
   deja el sistema girando y pagando invocaciones. Al agotarlo, la generacion se detiene
   nombrando el termino y los intentos: «no se pudo generar» obligaria a reproducir la
   ejecucion entera para saber que paso.

Cubre RF-GRD-01 a RF-GRD-06 y RF-VAL-05.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.store.database import Conexion
from backend.store.repositories import AuditLog, ListasProhibidas, TerminoProhibido

# Cuantas veces se le pide al writer que reescriba antes de parar. Tres es lo mismo que
# la escalera de reintentos de `architecture.md` 6.3: mas intentos sobre el mismo veto
# rara vez cambian el resultado y siempre cuestan invocaciones.
LIMITE_DE_REESCRITURAS = 3

# Lo que se quita del texto antes de comparar. Cerrada a proposito: cada transformacion
# nueva amplia lo que el guardarrail considera «la misma palabra», y eso son falsos
# positivos que bloquean capitulos correctos.
SEPARADORES = re.compile(r"[\s\-_.,;:¡!¿?()\[\]«»\"']+")
PLURALES = ("es", "s")


class LimiteDeReescriturasAgotado(RuntimeError):
    """Se agotaron los intentos y el texto sigue trayendo un termino vetado.

    No es un error de programacion: es el caso previsto de RF-GRD-04. La generacion se
    detiene y se informa, en lugar de publicar el capitulo o girar indefinidamente.
    """

    def __init__(self, terminos: tuple[str, ...], intentos: int) -> None:
        self.terminos = terminos
        self.intentos = intentos
        super().__init__(
            f"Guardarrail: agotado el limite de {LIMITE_DE_REESCRITURAS} reescrituras "
            f"en el intento {intentos}. Siguen apareciendo: {', '.join(terminos)}. "
            f"La generacion se detiene; subir el limite solo aplaza el problema."
        )


def normalizar(texto: str) -> str:
    """Minusculas, sin acentos y sin separadores. Nada mas.

    Las transformaciones son exactamente estas tres porque son las que producen la misma
    palabra escrita de otra manera. No se aplica ninguna que junte palabras distintas
    -ni fonetica, ni raiz, ni distancia de edicion-, porque un falso positivo aqui
    bloquea un capitulo correcto y obliga a reescribir prosa que estaba bien.
    """
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(caracter) != "Mn"
    )
    return SEPARADORES.sub("", sin_acentos)


def _formas(termino: str) -> frozenset[str]:
    """El termino normalizado y su plural simple.

    El plural va en las formas del **termino**, no del texto: quitar la `s` final a cada
    palabra del texto convertiria `mas` en `ma` y `dos` en `do`, y empezaria a haber
    coincidencias que nadie escribio.
    """
    base = normalizar(termino)
    return frozenset({base, *(base + sufijo for sufijo in PLURALES)})


@dataclass(frozen=True)
class Coincidencia:
    """Un termino vetado que aparece en el texto, con donde aparece."""

    termino: str
    nivel: str
    fragmento: str
    motivo: str = ""


@dataclass(frozen=True)
class Veredicto:
    """Lo que el guardarrail dice de un texto."""

    limpio: bool
    coincidencias: tuple[Coincidencia, ...] = ()

    @property
    def reescribir(self) -> bool:
        """Si el capitulo vuelve al writer. El guardarrail no corrige el texto."""
        return not self.limpio


@dataclass(frozen=True)
class Guardarrail:
    """Revisa un capitulo contra las tres listas y deja constancia de lo que decide."""

    conn: Conexion
    limite: int = LIMITE_DE_REESCRITURAS
    _palabras: re.Pattern[str] = field(
        default=re.compile(r"\w+", re.UNICODE), repr=False, compare=False
    )

    def revisar(
        self,
        texto: str,
        *,
        brief_id: str | None = None,
        destinatario_id: str | None = None,
        capitulo_id: str | None = None,
        tarea_id: str | None = None,
        intento: int = 1,
    ) -> Veredicto:
        """Compara el texto con lo vetado y registra cada coincidencia.

        Lanza `LimiteDeReescriturasAgotado` cuando el intento supera el limite y el texto
        sigue sucio.
        """
        coincidencias = self.coincidencias(
            texto, brief_id=brief_id, destinatario_id=destinatario_id
        )

        if not coincidencias:
            return Veredicto(limpio=True)

        self._registrar(coincidencias, capitulo_id=capitulo_id, tarea_id=tarea_id)

        if intento > self.limite:
            raise LimiteDeReescriturasAgotado(tuple(c.termino for c in coincidencias), intento)

        return Veredicto(limpio=False, coincidencias=coincidencias)

    def coincidencias(
        self,
        texto: str,
        *,
        brief_id: str | None = None,
        destinatario_id: str | None = None,
    ) -> tuple[Coincidencia, ...]:
        """Lo vetado que aparece en el texto, sin registrar nada.

        Para textos que no son un capitulo -el titulo, la dedicatoria-: alli no hay writer
        al que devolver nada, y dejar en el audit log un «devolver_al_writer» mentiria.
        """
        vetados = ListasProhibidas(self.conn).aplicables(
            brief_id=brief_id, destinatario_id=destinatario_id
        )
        return tuple(self._buscar(texto, vetados))

    # --- piezas ----------------------------------------------------------------------

    def _buscar(self, texto: str, vetados: Sequence[TerminoProhibido]) -> list[Coincidencia]:
        encontradas: list[Coincidencia] = []
        for vetado in vetados:
            formas = _formas(vetado.termino)
            for frase in _frases(texto):
                if any(normalizar(p) in formas for p in self._palabras.findall(frase)):
                    encontradas.append(
                        Coincidencia(
                            termino=normalizar(vetado.termino),
                            nivel=vetado.nivel,
                            fragmento=frase.strip(),
                            motivo=vetado.motivo,
                        )
                    )
                    break
        return encontradas

    def _registrar(
        self,
        coincidencias: tuple[Coincidencia, ...],
        *,
        capitulo_id: str | None,
        tarea_id: str | None,
    ) -> None:
        log = AuditLog(self.conn)
        for coincidencia in coincidencias:
            log.registrar(
                f"al-{uuid.uuid4().hex[:12]}",
                decision="devolver_al_writer",
                motivo=(
                    f"el termino «{coincidencia.termino}» esta vetado en el nivel "
                    f"{coincidencia.nivel} y aparece en el capitulo"
                ),
                ambito=coincidencia.nivel,
                tarea_id=tarea_id,
                capitulo_id=capitulo_id,
                termino=coincidencia.termino,
            )


def _frases(texto: str) -> list[str]:
    """Parte el texto en frases para poder citar donde aparecio el termino.

    Sin el fragmento, quien reescribe tiene que buscar la palabra a ojo en el capitulo
    entero, y la evidencia deja de ser citable.
    """
    partes = re.split(r"(?<=[.!?])\s+", texto)
    return [parte for parte in partes if parte.strip()]
