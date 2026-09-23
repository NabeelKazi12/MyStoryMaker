"""Puerta de analisis estatico sobre los limites de modulo.

Implementa las reglas de dependencia de `architecture.md` 2.3 como un test, no como
una convencion: una regla que solo esta escrita se rompe el dia que alguien tiene prisa.

La sexta regla de ese apartado --que `frontend/` no contenga reglas de dominio-- no
esta aqui porque no es analizable desde Python: `verification.md` 8 la clasifica como
inspeccion en revision de codigo.

Cubre RNF-01, RNF-02, RNF-03, RF-STO-04, RF-QUA-15, RF-API-06 y RF-API-07.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"

# Bibliotecas que delatan que un paquete esta hablando con algo que no le toca.
SQL_LIBS = frozenset({"sqlite3", "aiosqlite", "alembic"})
VECTOR_LIBS = frozenset({"sqlite_vec", "sqlite-vec"})
MODEL_LIBS = frozenset({"anthropic", "httpx", "requests", "urllib", "urllib3", "http"})
WEB_LIBS = frozenset({"fastapi", "pydantic", "starlette", "uvicorn"})


@dataclass(frozen=True)
class Rule:
    """Una regla de dependencia: quien la sufre, que no puede alcanzar y por que."""

    package: str
    forbidden_internal: frozenset[str]
    forbidden_external: frozenset[str]
    reason: str


RULES: tuple[Rule, ...] = (
    Rule(
        package="domain",
        forbidden_internal=frozenset(
            {
                "context",
                "quality",
                "agents",
                "store",
                "orchestrator",
                "api",
                "worker",
                "migrations",
            }
        ),
        forbidden_external=SQL_LIBS | VECTOR_LIBS | MODEL_LIBS | WEB_LIBS,
        reason="domain/ no importa de ningun otro paquete, ni de FastAPI ni de Pydantic",
    ),
    Rule(
        package="quality",
        forbidden_internal=frozenset({"agents"}),
        forbidden_external=SQL_LIBS | VECTOR_LIBS | MODEL_LIBS,
        reason="quality/ importa de domain/, nunca de agents/, y no alcanza el vectorial",
    ),
    Rule(
        package="store",
        forbidden_internal=frozenset({"agents", "api", "worker", "orchestrator", "quality"}),
        forbidden_external=MODEL_LIBS | WEB_LIBS,
        reason="store/ es el unico acceso a datos, y no invoca modelos ni sirve HTTP",
    ),
    Rule(
        package="api",
        forbidden_internal=frozenset({"agents"}),
        forbidden_external=SQL_LIBS | VECTOR_LIBS | MODEL_LIBS,
        reason="api/ no invoca modelos ni abre la base de datos: encola Tarea y lee estado",
    ),
    Rule(
        package="context",
        forbidden_internal=frozenset({"agents", "api", "worker"}),
        forbidden_external=SQL_LIBS | VECTOR_LIBS | MODEL_LIBS,
        reason="context/ ensambla paquetes; el acceso a datos pasa por store/",
    ),
    Rule(
        package="orchestrator",
        forbidden_internal=frozenset({"api"}),
        forbidden_external=SQL_LIBS | VECTOR_LIBS | MODEL_LIBS,
        reason="orchestrator/ decide; invocar modelos es del worker y abrir SQLite, del store",
    ),
    # SPEC-003, 10.1. El paquete llega en la fase D; la regla se escribe antes de que
    # exista, que es cuando todavia no cuesta nada respetarla.
    Rule(
        package="observability",
        forbidden_internal=frozenset({"agents", "api", "orchestrator", "worker", "quality"}),
        forbidden_external=SQL_LIBS | VECTOR_LIBS | MODEL_LIBS,
        reason="observability/ observa y no participa: no invoca modelos ni abre la base",
    ),
)

# La otra mitad de la regla de observabilidad: quien no puede mirar hacia ella. Un juez
# que sabe que esta siendo observado es un juez distinto, y un verificador que emite su
# propio score deja de ser comprobable sin red.
SIN_ACCESO_A_OBSERVABILIDAD: tuple[str, ...] = ("domain", "quality", "agents")


def _module_name(path: Path) -> str:
    """Nombre punteado del modulo, relativo a la raiz del repositorio."""
    parts = path.relative_to(BACKEND.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path) -> set[str]:
    """Modulos importados por un fichero, en su forma punteada completa."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def _source_files() -> list[Path]:
    return sorted(BACKEND.rglob("*.py"))


def _root(dotted: str) -> str:
    return dotted.split(".", 1)[0]


@pytest.mark.invariants
@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.package)
def test_paquete_respeta_sus_limites(rule: Rule) -> None:
    """Ningun modulo del paquete alcanza lo que su regla le prohibe."""
    offences: list[str] = []
    prefix = f"backend.{rule.package}"

    for path in _source_files():
        module = _module_name(path)
        if module != prefix and not module.startswith(prefix + "."):
            continue
        for imported in _imports(path):
            if imported.startswith("backend."):
                target = imported.split(".")[1]
                if target in rule.forbidden_internal:
                    offences.append(f"{module} importa {imported}")
            elif _root(imported) in rule.forbidden_external:
                offences.append(f"{module} importa {imported}")

    assert not offences, (
        f"Violacion de limites en backend/{rule.package}/: {rule.reason}. "
        f"Importaciones ofensoras: {offences}"
    )


@pytest.mark.invariants
def test_ningun_rol_importa_de_otro_rol() -> None:
    """agents/ no importa de agents/: la coordinacion entre roles vive en orchestrator/."""
    offences: list[str] = []
    for path in _source_files():
        module = _module_name(path)
        if not module.startswith("backend.agents."):
            continue
        own_role = module.split(".")[2]
        for imported in _imports(path):
            if not imported.startswith("backend.agents."):
                continue
            other_role = imported.split(".")[2]
            if other_role != own_role:
                offences.append(f"{module} importa {imported}")

    assert not offences, (
        "Violacion de limites en backend/agents/: ningun rol importa de otro rol. "
        f"Importaciones ofensoras: {offences}"
    )


@pytest.mark.invariants
def test_el_esqueleto_de_paquetes_esta_completo() -> None:
    """Los paquetes de architecture.md 2.3 existen, para que las reglas corran sobre algo."""
    expected = {
        "domain",
        "domain/diegetic",
        "domain/discursive",
        "domain/production",
        "domain/spec",
        "context",
        "quality",
        "agents",
        "store",
        "orchestrator",
        "api",
        "worker",
        "migrations",
    }
    missing = {name for name in expected if not (BACKEND / name / "__init__.py").is_file()}
    assert not missing, f"Faltan paquetes del esqueleto: {sorted(missing)}"


@pytest.mark.invariants
@pytest.mark.parametrize("paquete", SIN_ACCESO_A_OBSERVABILIDAD)
def test_nadie_que_juzgue_importa_la_observabilidad(paquete: str) -> None:
    """SPEC-003, 10.1: `domain/`, `quality/` y `agents/` no conocen a Langfuse.

    La instrumentacion vive en `orchestrator/`, `worker/` y `api/`. Si un verificador
    emitiera su propio score, dejaria de poder ejecutarse sin red y la suite pasaria a
    depender de un servicio externo para comprobar una regla del dominio.
    """
    raiz = BACKEND / paquete
    if not raiz.exists():
        pytest.skip(f"{paquete}/ no existe todavia")

    infracciones = [
        f"{_module_name(fichero)} importa {importado}"
        for fichero in sorted(raiz.rglob("*.py"))
        for importado in _imports(fichero)
        if importado.startswith("backend.observability")
        or _root(importado) in {"langfuse", "opentelemetry"}
    ]

    assert not infracciones, "; ".join(infracciones)
