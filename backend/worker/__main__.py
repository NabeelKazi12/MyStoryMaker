"""Punto de entrada del worker: `uv run python -m backend.worker`.

Consume la cola de `Tarea` e invoca modelos. Es el unico proceso que lo hace: la API
encola y lee estado, y el trabajo ocurre aqui (`architecture.md` 2.3, regla 5).

Tres cosas que este arranque hace y que conviene no perder:

1. **Reanuda antes de empezar.** Lo que quedo `en_curso` cuando el proceso se cayo vuelve
   a `lista`, y lo que se pago y se perdio queda anotado. Sin esto, una caida deja tareas
   que parecen vivas y que nadie va a mover nunca.
2. **Una transaccion por vuelta.** El artefacto y la transicion que lo acompana se
   escriben juntos; separarlos produce borradores huerfanos y tareas que parecen
   pendientes con el trabajo ya hecho (RF-STO-06).
3. **El modo lo dice el plan, no el proceso.** Dos novelas encargadas con modos distintos
   conviven en la misma cola, y cada una se escribe con el suyo.

Cubre RF-ESC-01 y RF-ESC-04.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

from backend.domain.vocabularies import EstadoDeTarea, ModoDeEscritura
from backend.observability.langfuse import cliente_desde_el_entorno
from backend.observability.trazas import ClienteDeObservabilidad
from backend.orchestrator.admision import Semaforo
from backend.orchestrator.ejecucion import reanudar_al_arrancar, registrar_transicion
from backend.store import database
from backend.store.escritura import ColaDeTareas
from backend.worker.bucle import Bucle
from backend.worker.modelo import ClaudeCodeAusente, ClienteDeModelo, construir_cliente
from backend.worker.transporte import transporte_urllib

# Cada cuanto se vuelve a mirar la cola cuando esta vacia. Un segundo es holgado: lo que
# se espera aqui es que alguien pulse un boton, no un flujo continuo de trabajo.
ESPERA_ENTRE_SONDEOS_S = 1.0


@dataclass
class Servicio:
    """El worker como proceso. Guarda el credito y los clientes entre vueltas.

    El semaforo tiene que sobrevivir a la vuelta: es el que acota los tokens en vuelo de
    **todo el sistema** (D-13), y uno nuevo por tarea no acotaria nada.
    """

    ruta: str | None = None
    semaforo: Semaforo = field(default_factory=Semaforo)
    _clientes: dict[ModoDeEscritura, ClienteDeModelo] = field(default_factory=dict)
    # Langfuse si estan las claves en el entorno; si no, nulo (SPEC-012 RF-LAN-01). El
    # transporte HTTP lo pone el worker: `observability/` no puede hacer red (DV-1).
    observabilidad: ClienteDeObservabilidad = field(
        default_factory=lambda: cliente_desde_el_entorno(None, transporte_urllib)
    )

    def cliente_de(self, modo: ModoDeEscritura) -> ClienteDeModelo:
        if modo not in self._clientes:
            self._clientes[modo] = construir_cliente(modo)
        return self._clientes[modo]

    def reanudar(self) -> None:
        with database.conexion(self.ruta) as conn:
            recuperadas = reanudar_al_arrancar(conn)
        if recuperadas.devueltas_a_lista:
            print(f"worker: devueltas a la cola {len(recuperadas.devueltas_a_lista)} tarea(s).")
        if recuperadas.pagadas_y_perdidas:
            # Es la metrica que revela caidas recurrentes: se dice en voz alta, no se
            # esconde en una tabla que nadie consulta.
            print(
                f"worker: {len(recuperadas.pagadas_y_perdidas)} invocacion(es) se pagaron "
                f"y se perdieron en la caida anterior."
            )

    def una_vuelta(self) -> bool:
        """Una tarea. Devuelve si hizo algo, para que el bucle exterior sepa si dormir."""
        with database.conexion(self.ruta) as conn:
            siguiente = ColaDeTareas(conn).siguiente_lista()
            if siguiente is None:
                return False
            modo = ModoDeEscritura(siguiente["modo"])
            try:
                cliente = self.cliente_de(modo)
            except ClaudeCodeAusente as ausente:
                # No se cae al modo de demostracion por su cuenta (D-08): se detiene esa
                # tarea diciendo exactamente que falta, y el resto de la cola sigue.
                registrar_transicion(conn, siguiente["id"], EstadoDeTarea.ESCALADA.value)
                ColaDeTareas(conn).anotar_falta(siguiente["id"], (str(ausente),))
                print(f"worker: {siguiente['id']} detenida. {ausente}", file=sys.stderr)
                return True

            bucle = Bucle(
                conn=conn,
                modo=modo,
                cliente=cliente,
                semaforo=self.semaforo,
                observabilidad=self.observabilidad,
            )
            resultado = bucle.una_vuelta()

        if resultado is not None:
            print(f"worker: {resultado.tarea_id} -> {resultado.estado}. {resultado.detalle}")
        return resultado is not None

    def servir(self, vueltas: int | None = None) -> int:
        """El bucle del proceso. Con `vueltas` acotadas, util para probarlo."""
        self.reanudar()
        print("worker: a la escucha de la cola de tareas.")
        hechas = 0
        try:
            while vueltas is None or hechas < vueltas:
                if self.una_vuelta():
                    hechas += 1
                else:
                    if vueltas is not None:
                        break
                    time.sleep(ESPERA_ENTRE_SONDEOS_S)
        except KeyboardInterrupt:
            print("\nworker: parado.")
        return 0


def main() -> int:
    return Servicio().servir()


if __name__ == "__main__":
    raise SystemExit(main())
