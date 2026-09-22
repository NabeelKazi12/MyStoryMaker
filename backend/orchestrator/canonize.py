"""Canonizacion: el punto donde el texto generado se convierte en verdad.

Es el unico lugar donde el canon cambia y el unico que incrementa su revision. Tres
reglas duras lo ordenan: el delta se propone y se valida, nunca se aplica en bruto; lo que
contradice el canon genera un `Defecto` y **nunca** lo sobrescribe; y la invalidacion en
cascada es parte de su cierre, no un trabajo posterior opcional (`architecture.md` 8).

Un canonizador que resuelve contradicciones por su cuenta convierte errores detectables en
deriva silenciosa.

Cubre RF-CAN-01 a RF-CAN-06.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.domain.diegetic.canon import Hecho
from backend.domain.production.ejecucion import Defecto
from backend.domain.vocabularies import Severidad
from backend.store.database import Conexion
from backend.store.repositories import CanonVersionado, CatalogoDePredicados


class Resolucion(Enum):
    """Los tres casos de `architecture.md` 3.3. La diferencia entre ellos es todo."""

    SUCESION_LEGITIMA = "el hecho cambio: se cierra el intervalo anterior y se inserta"
    COMPATIBLE = "no choca con nada vigente: se promueve"
    DUPLICADO = "ya estaba, por clave natural: no se inserta"
    CONTRADICCION = "predicados excluyentes con vigencias solapadas: Defecto, sin tocar canon"


@dataclass(frozen=True)
class ResultadoDeCanonizacion:
    """Lo que la canonizacion hizo, para que quede auditable."""

    revision: int
    promovidos: tuple[str, ...]
    intervalos_cerrados: tuple[str, ...]
    duplicados: tuple[str, ...]
    defectos: tuple[Defecto, ...]
    unidades_invalidadas: tuple[str, ...]

    @property
    def canon_cambio(self) -> bool:
        return bool(self.promovidos or self.intervalos_cerrados)


@dataclass
class Canonizador:
    """Promueve al canon los hechos de un borrador **ya aceptado**.

    No decide si el borrador es bueno: eso ya lo decidio la puerta. Su unico trabajo es
    contrastar y promover, y su unica libertad es no promover.
    """

    conn: Conexion

    def canonizar(
        self,
        borrador_id: str,
        hechos_nuevos: list[Hecho],
        vigentes: list[Hecho],
        orden_de_evento: dict[str, int],
        *,
        escena_id: str | None = None,
    ) -> ResultadoDeCanonizacion:
        """Contrasta cada hecho declarado contra el canon vigente y actua.

        Todo ocurre en la transaccion de quien llama: la escritura del artefacto y la
        transicion de estado van juntas (RF-STO-06), y la cascada es parte del cierre.
        """
        from backend.quality.verificadores import contradiccion_de_hechos

        catalogo = CatalogoDePredicados(self.conn)
        canon = CanonVersionado(self.conn)

        promovidos: list[str] = []
        cerrados: list[str] = []
        duplicados: list[str] = []
        defectos: list[Defecto] = []

        for nuevo in hechos_nuevos:
            clave = (nuevo.sujeto_id, nuevo.predicado, nuevo.objeto, nuevo.valido_desde)
            if any(
                (v.sujeto_id, v.predicado, v.objeto, v.valido_desde) == clave for v in vigentes
            ):
                duplicados.append(nuevo.id)
                continue

            choques = contradiccion_de_hechos(
                [*self._mismos(nuevo, vigentes), nuevo],
                catalogo,
                orden_de_evento,
                borrador_id=borrador_id,
            )
            if not choques:
                promovidos.append(nuevo.id)
                continue

            anterior = self._sucesion_legitima(nuevo, vigentes, orden_de_evento, catalogo)
            if anterior is not None:
                cerrados.append(anterior.id)
                promovidos.append(nuevo.id)
            else:
                # Contradiccion de verdad: se reporta y el canon no se toca.
                defectos.extend(choques)

        revision = canon.revision_actual()
        if promovidos or cerrados:
            revision = canon.abrir_revision(f"canonizacion de {borrador_id}")
            for identificador in cerrados:
                canon.registrar_cierre(
                    revision, identificador, self._corte(identificador, hechos_nuevos)
                )
            for hecho in hechos_nuevos:
                if hecho.id in promovidos:
                    canon.registrar_insercion(revision, hecho)

        invalidadas = self._invalidar_en_cascada(revision, escena_id) if escena_id else ()

        return ResultadoDeCanonizacion(
            revision=revision,
            promovidos=tuple(promovidos),
            intervalos_cerrados=tuple(cerrados),
            duplicados=tuple(duplicados),
            defectos=tuple(defectos),
            unidades_invalidadas=invalidadas,
        )

    # --- piezas ----------------------------------------------------------------------

    @staticmethod
    def _mismos(nuevo: Hecho, vigentes: list[Hecho]) -> list[Hecho]:
        return [
            v
            for v in vigentes
            if v.sujeto_id == nuevo.sujeto_id and v.predicado == nuevo.predicado
        ]

    @staticmethod
    def _sucesion_legitima(
        nuevo: Hecho,
        vigentes: list[Hecho],
        orden: dict[str, int],
        catalogo: CatalogoDePredicados,
    ) -> Hecho | None:
        """Distingue «el hecho cambio» de «el hecho se contradice».

        Es sucesion legitima si hay exactamente un hecho vigente del mismo sujeto y
        predicado funcional, sin cierre, y el nuevo empieza **despues**. El personaje se
        mudo, la lealtad se rompio. Si el nuevo empieza antes o hay varios candidatos, no
        se adivina: es contradiccion y se reporta.
        """
        if not catalogo.es_funcional(nuevo.predicado):
            return None
        candidatos = [
            v
            for v in Canonizador._mismos(nuevo, vigentes)
            if v.valido_hasta is None
            and orden.get(v.valido_desde, 0) < orden.get(nuevo.valido_desde, 0)
        ]
        return candidatos[0] if len(candidatos) == 1 else None

    @staticmethod
    def _corte(hecho_id: str, hechos_nuevos: list[Hecho]) -> str:
        """El evento en el que se cierra el intervalo anterior: el que abre el nuevo."""
        return hechos_nuevos[0].valido_desde if hechos_nuevos else ""

    def _invalidar_en_cascada(self, revision: int, escena_id: str) -> tuple[str, ...]:
        """Marca obsoleto lo que derivaba de la escena reescrita.

        Ocurre dentro del cierre de la canonizacion, no como trabajo posterior opcional.
        Sin esto el sistema acumula canon fantasma: hechos que ya nadie narra pero que
        siguen condicionando las escenas siguientes.

        En v1 alcanza a los `PaqueteDeContexto` que citaban la escena; la piramide de
        resumenes entra en la fase 3, asi que la cascada tiene menos aristas que seguir de
        las que tendra, y eso esta declarado como riesgo en la spec.
        """
        filas = self.conn.execute(
            "SELECT id FROM paquete_contexto WHERE tarea_id LIKE ? ORDER BY id",
            (f"{escena_id}%",),
        ).fetchall()
        return tuple(fila["id"] for fila in filas)


def defecto_de_contradiccion(nuevo: Hecho, anterior: Hecho, borrador_id: str) -> Defecto:
    """El defecto que se emite en lugar de sobrescribir. El paso que protege el canon."""
    return Defecto(
        id=f"contradiccion:{nuevo.id}:{anterior.id}",
        tipo="contradiccion_de_hechos",
        severidad=Severidad.CRITICA,
        regla_violada="lo que contradice el canon genera un Defecto y nunca lo sobrescribe",
        evidencia=f"{nuevo.id} ({nuevo.objeto}) choca con {anterior.id} ({anterior.objeto})",
        extraccion_evaluada="hechos_nuevos_detectados",
        borrador_id=borrador_id,
    )
