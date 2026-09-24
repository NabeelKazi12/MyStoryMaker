"""Aprobar una novela: la firma de una persona cierra el volumen.

Vive en `orchestrator/` porque es el unico sitio que junta una puerta de `quality/` con el
almacen: `quality/` recibe la firma como argumento y no sabe de tablas, y `api/` solo
traduce el resultado a HTTP (SPEC-007, PLAN-007 §Modulos).

La firma aporta la evidencia `humano` de *promesa al lector* y nada mas. Lo determinista
de *Volumen cerrado* —siembras sin pagar, hilos sin pregunta dramatica— sigue parando la
linea aunque haya firma (N-02), y aprobar no cambia el estado de ningun borrador (N-01).

Cubre RF-APR-01 a RF-APR-08 y RF-APR-10.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.domain.production.ejecucion import Defecto
from backend.orchestrator.escritura import progreso
from backend.quality.puertas import volumen_cerrado
from backend.quality.verificadores import hilos_con_pregunta_dramatica, siembras_sin_pagar
from backend.store.database import Conexion
from backend.store.escritura import Puertas, TextoDeLaNovela
from backend.store.repositories import (
    Aprobacion,
    AprobacionesDeVolumen,
    AuditLog,
    ConsultasDeCalidad,
    VersionesDeNovela,
)

MOTIVO_DEL_BLOQUEO = "La novela está aprobada; reábrela para cambiarla"


class VolumenDesconocido(LookupError):
    """La novela que se quiere aprobar o reabrir no existe."""


class AprobacionRechazada(Exception):
    """No se aprueba ni se retira, y se dice por que: el motivo y, si los hay, los defectos."""

    def __init__(self, motivo: str, defectos: tuple[Defecto, ...] = ()) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.defectos = defectos


class NovelaAprobada(Exception):
    """Se ha pedido cambiar una novela con aprobacion vigente."""


@dataclass(frozen=True)
class ResultadoDeAprobacion:
    aprobacion: Aprobacion
    # Escenas cuyo borrador sigue sin aceptar y quedan firmadas tal como estan. Se cuenta
    # para decirlo, no para impedirlo: en v1 ningun borrador llega a aceptado (D-21).
    sin_aceptar: int


def aprobar(conn: Conexion, volumen_id: str) -> ResultadoDeAprobacion:
    """Evalua *Volumen cerrado* con la firma y, si se supera, la registra."""
    _exigir_volumen(conn, volumen_id)
    aprobaciones = AprobacionesDeVolumen(conn)
    if aprobaciones.vigente(volumen_id) is not None:
        raise AprobacionRechazada("la novela ya esta aprobada")

    estado = progreso(conn, volumen_id)
    if estado.estado != "escrita":
        raise AprobacionRechazada(
            f"solo se aprueba una novela escrita; esta en «{estado.estado}»: {estado.detalle}"
        )

    versiones = VersionesDeNovela(conn).historial(volumen_id)
    if not versiones:
        raise AprobacionRechazada("no hay ninguna version publicada que firmar")

    consultas = ConsultasDeCalidad(conn)
    defectos = siembras_sin_pagar(
        consultas.siembras_abiertas_del_volumen(volumen_id), cierre_de_volumen=True
    ) + hilos_con_pregunta_dramatica(consultas.hilos_del_volumen(volumen_id))
    resultado = volumen_cerrado(firmada=True).evaluar(defectos)
    Puertas(conn).registrar(
        f"pu-vc-{uuid.uuid4().hex[:10]}",
        fase=resultado.fase,
        politica=resultado.politica.value,
        superada=resultado.superada,
        evidencia_ausente=resultado.evidencia_ausente,
        ambito_id=volumen_id,
    )
    if not resultado.superada:
        raise AprobacionRechazada(resultado.explicacion(), resultado.bloqueantes)

    aprobacion = aprobaciones.registrar(
        f"apr-{uuid.uuid4().hex[:10]}", volumen_id=volumen_id, version_id=versiones[-1]
    )
    AuditLog(conn).registrar(
        f"al-{uuid.uuid4().hex[:12]}",
        decision="aprobar_volumen",
        motivo=f"{volumen_id} aprobado sobre la version {aprobacion.version_numero}",
        ambito="aprobacion",
    )
    sin_aceptar = sum(
        1
        for capitulo in TextoDeLaNovela(conn).por_capitulos(volumen_id)
        for escena in capitulo.escenas
        if not escena.aceptado
    )
    return ResultadoDeAprobacion(aprobacion=aprobacion, sin_aceptar=sin_aceptar)


def retirar(conn: Conexion, volumen_id: str) -> Aprobacion:
    """Reabre la novela. La aprobacion queda en el historial, retirada y con fecha."""
    _exigir_volumen(conn, volumen_id)
    actual = AprobacionesDeVolumen(conn).vigente(volumen_id)
    if actual is None:
        raise AprobacionRechazada("la novela no esta aprobada: no hay nada que reabrir")
    retirada = AprobacionesDeVolumen(conn).retirar(actual.id)
    AuditLog(conn).registrar(
        f"al-{uuid.uuid4().hex[:12]}",
        decision="retirar_aprobacion",
        motivo=(
            f"{volumen_id} reabierto; la version {retirada.version_numero} "
            "deja de estar aprobada"
        ),
        ambito="aprobacion",
    )
    return retirada


def vigente(conn: Conexion, volumen_id: str) -> Aprobacion | None:
    return AprobacionesDeVolumen(conn).vigente(volumen_id)


def exigir_abierta(conn: Conexion, volumen_id: str) -> None:
    """Lo llaman las rutas que cambian la novela antes de encolar o guardar nada."""
    if AprobacionesDeVolumen(conn).vigente(volumen_id) is not None:
        raise NovelaAprobada(MOTIVO_DEL_BLOQUEO)


def _exigir_volumen(conn: Conexion, volumen_id: str) -> None:
    if conn.execute("SELECT 1 FROM volumen WHERE id = ?", (volumen_id,)).fetchone() is None:
        raise VolumenDesconocido(f"no existe el volumen {volumen_id}")
