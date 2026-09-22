"""Matriz de permisos de escritura por rol, aplicada en el orquestador.

No es una convencion: es un guardarrail que se comprueba antes de aceptar cualquier
artefacto. Una matriz que no se aplica es una convencion, y las convenciones no
sobreviven al primer atajo.

La matriz es la de `AGENTS.md` 2. El Canonizador es el unico rol con escritura en el
canon, y actua solo sobre borradores ya aceptados.

Cubre RF-ORQ-15 y RF-CAN-01.
"""

from __future__ import annotations

# Clase de artefacto que cada rol puede escribir. Lo que no esta, no se puede.
PERMISOS: dict[str, frozenset[str]] = {
    "orquestador": frozenset({"Tarea", "Plan", "Puerta"}),
    "arquitecto": frozenset({"Hilo", "Escena", "ParSiembraPago"}),
    "worldbuilder": frozenset({"Entidad", "ReglaDelMundo", "Lore"}),
    "investigador": frozenset({"Lore", "Hecho"}),
    "entrenador_de_voz": frozenset({"PerfilDeEstilo"}),
    "redactor": frozenset({"Borrador"}),
    "guardian_de_continuidad": frozenset({"Defecto"}),
    "editor_de_linea": frozenset({"Revision"}),
    "editor_de_desarrollo": frozenset({"Critica"}),
    "juez": frozenset({"Juicio"}),
    "canonizador": frozenset({"Hecho", "EstadoDePersonaje", "EstadoDeConocimiento"}),
}

# Roles con escritura en el canon. Solo uno, y no es casualidad.
ESCRIBEN_CANON = frozenset({"canonizador"})


class PermisoDenegado(Exception):
    """Un rol intento escribir una clase que no le corresponde."""

    def __init__(self, rol: str, clase: str) -> None:
        permitidas = ", ".join(sorted(PERMISOS.get(rol, frozenset()))) or "ninguna"
        super().__init__(
            f"Permisos: el rol {rol!r} no puede escribir {clase!r}. "
            f"Puede escribir: {permitidas}. La matriz esta en AGENTS.md 2 y se aplica "
            f"en el orquestador, no por convencion."
        )


def exigir_permiso(rol: str, clase: str) -> None:
    """Rechaza el artefacto si el rol no puede escribir esa clase."""
    if clase not in PERMISOS.get(rol, frozenset()):
        raise PermisoDenegado(rol, clase)


def puede_escribir_canon(rol: str) -> bool:
    """Si el rol puede tocar el canon. Solo el Canonizador, y tras la puerta."""
    return rol in ESCRIBEN_CANON


def roles_que_generan_y_validan() -> frozenset[str]:
    """Roles que escribirian a la vez prosa y su juicio. Debe estar vacio.

    Es «quien genera no valida» expresado como consulta: si algun dia deja de estar
    vacio, alguien ha roto el principio sin darse cuenta.
    """
    genera = frozenset({"Borrador", "Revision"})
    valida = frozenset({"Defecto", "Juicio", "Critica"})
    return frozenset(
        rol for rol, clases in PERMISOS.items() if (clases & genera) and (clases & valida)
    )
