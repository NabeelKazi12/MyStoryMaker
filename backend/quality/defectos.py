"""Forma del `Defecto` y descarte de lo que no trae evidencia.

Todo defecto llega con evidencia citable. Sin ella se descarta antes de llegar al
Orquestador, y el descarte se cuenta: la proporcion descartada es la senal de que un
agente esta opinando en vez de comprobando (`architecture.md` 7.2).

Las dimensiones marcadas **(E)** en `verification.md` 2 son deterministas en su predicado
pero dependen de una extraccion del texto. Su defecto cita ademas contra que bloque
declarado se evaluo: sin eso, el modo de fallo F-01 no es depurable (RF-QUA-19).

Cubre RF-QUA-10 y RF-QUA-19.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.production.ejecucion import Defecto

# Dimensiones cuya entrada la declara un agente leyendo su propia prosa.
# Es la lista de `verification.md` 2, limitada a lo que v1 implementa.
DIMENSIONES_CON_EXTRACCION = frozenset(
    {
        "contradiccion_de_hechos",
        "escena_con_evento",
        "deriva_de_nombres",
        "siembras_sin_pagar",
    }
)


@dataclass
class ColaDeDefectos:
    """Recoge defectos y descarta los que no pueden sostenerse.

    No es un filtro silencioso: lo descartado se cuenta por dimension, porque esa
    proporcion es una de las senales de `architecture.md` 9.
    """

    admitidos: list[Defecto] = field(default_factory=list)
    descartados_por_tipo: dict[str, int] = field(default_factory=dict)

    def ofrecer(self, defecto: Defecto) -> bool:
        """Admite el defecto si se sostiene. Devuelve si entro."""
        if not defecto.tiene_evidencia:
            self._descartar(defecto.tipo)
            return False

        if defecto.tipo in DIMENSIONES_CON_EXTRACCION and not defecto.extraccion_evaluada:
            # Un defecto (E) sin decir contra que declaracion se evaluo no permite
            # distinguir «el texto esta mal» de «la extraccion no lo trajo».
            self._descartar(defecto.tipo)
            return False

        self.admitidos.append(defecto)
        return True

    def _descartar(self, tipo: str) -> None:
        self.descartados_por_tipo[tipo] = self.descartados_por_tipo.get(tipo, 0) + 1

    @property
    def total_descartados(self) -> int:
        return sum(self.descartados_por_tipo.values())

    @property
    def proporcion_descartada(self) -> float:
        """Senal de `architecture.md` 9: agentes que opinan en vez de comprobar."""
        total = len(self.admitidos) + self.total_descartados
        return self.total_descartados / total if total else 0.0

    def criticos(self) -> tuple[Defecto, ...]:
        from backend.domain.vocabularies import Severidad

        return tuple(d for d in self.admitidos if d.severidad is Severidad.CRITICA)
