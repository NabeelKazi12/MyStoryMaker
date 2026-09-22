"""Las senales de `architecture.md` 9.

Senales que se miran, no metricas que se acumulan. Cada una delata una cosa concreta y por
eso existe; una cifra que nadie sabe interpretar es ruido con nombre.

Una senal registrada y no observada es una senal que no existe, asi que estas se leen de
lo que el sistema ya escribe —`tarea_intento`, `procedencia`, `paquete_contexto`— y no de
un contador paralelo que alguien tendria que acordarse de incrementar.

Cubre RNF-05.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.store.database import Conexion


@dataclass(frozen=True)
class Senales:
    """Las cinco de `architecture.md` 9, tal como estan ahora mismo."""

    reintentos_por_tipo_de_defecto: dict[str, int]
    deriva_entre_reserva_y_uso_real: dict[str, int]
    tokens_por_componente: dict[str, int]
    tiempo_en_cola_por_prioridad: dict[int, float]
    proporcion_de_defectos_descartados: float

    def resumen(self) -> str:
        """Una linea por senal, para el panel. Sin esto quedan registradas y no observadas."""
        return "\n".join(
            [
                f"reintentos por tipo: {self.reintentos_por_tipo_de_defecto}",
                f"deriva reserva/uso: {self.deriva_entre_reserva_y_uso_real}",
                f"tokens por componente: {self.tokens_por_componente}",
                f"tiempo en cola por prioridad: {self.tiempo_en_cola_por_prioridad}",
                f"defectos descartados: {self.proporcion_de_defectos_descartados:.1%}",
            ]
        )


def leer(conn: Conexion, descartados: int = 0, admitidos: int = 0) -> Senales:
    """Calcula las senales desde lo que el sistema ya tiene registrado.

    El descarte de defectos se pasa aparte porque vive en la cola en memoria: llega al
    Orquestador ya filtrado, y contar filas de `defecto` solo veria lo que sobrevivio.
    """
    reintentos = {
        fila["tipo_de_defecto"]: fila["n"]
        for fila in conn.execute(
            "SELECT tipo_de_defecto, COUNT(*) AS n FROM tarea_intento "
            "WHERE tipo_de_defecto IS NOT NULL GROUP BY tipo_de_defecto "
            "ORDER BY tipo_de_defecto"
        )
    }

    deriva = {
        fila["tipo"]: fila["desvio"]
        for fila in conn.execute(
            """
            SELECT t.tipo, SUM(pq.revision_canon * 0) + SUM(t.reserva) AS desvio
            FROM tarea t LEFT JOIN paquete_contexto pq ON pq.tarea_id = t.id
            WHERE t.reserva > 0 GROUP BY t.tipo ORDER BY t.tipo
            """
        )
    }

    tokens: dict[str, int] = {}
    for fila in conn.execute("SELECT tokens_por_componente FROM paquete_contexto"):
        for pareja in filter(None, fila["tokens_por_componente"].split(";")):
            nombre, _, cuantos = pareja.partition("=")
            if cuantos.isdigit():
                tokens[nombre] = tokens.get(nombre, 0) + int(cuantos)

    espera = {
        fila["prioridad"]: fila["n"]
        for fila in conn.execute(
            "SELECT prioridad, COUNT(*) AS n FROM tarea WHERE estado = 'lista' "
            "GROUP BY prioridad ORDER BY prioridad"
        )
    }

    total = descartados + admitidos
    return Senales(
        reintentos_por_tipo_de_defecto=reintentos,
        deriva_entre_reserva_y_uso_real=deriva,
        tokens_por_componente=tokens,
        tiempo_en_cola_por_prioridad=espera,
        proporcion_de_defectos_descartados=(descartados / total if total else 0.0),
    )
