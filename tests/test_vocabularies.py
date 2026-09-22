"""Los vocabularios controlados estan cerrados y lo hacen cumplir.

Cubre RF-DOM-03: un valor fuera del vocabulario es un error de construccion, no una
cadena aceptada.
"""

from __future__ import annotations

import pytest

from backend.domain import vocabularies
from backend.domain.vocabularies import (
    DimensionDeEstado,
    EstadoDeBorrador,
    EstadoDeTarea,
    ExclusividadDePredicado,
    TipoDeEvento,
    VocabularioCerrado,
)

# Todo vocabulario declarado en el modulo, para no tener que mantener una lista a mano.
VOCABULARIOS = sorted(
    (
        obj
        for obj in vars(vocabularies).values()
        if isinstance(obj, type)
        and issubclass(obj, VocabularioCerrado)
        and obj is not VocabularioCerrado
    ),
    key=lambda cls: cls.__name__,
)


@pytest.mark.invariants
@pytest.mark.parametrize("vocabulario", VOCABULARIOS, ids=lambda v: v.__name__)
def test_rechaza_un_valor_no_declarado(vocabulario: type[VocabularioCerrado]) -> None:
    """Construir con un valor ajeno falla, y el mensaje nombra la clase y lo admitido."""
    with pytest.raises(ValueError) as error:
        vocabulario("valor_que_nadie_ha_declarado")

    mensaje = str(error.value)
    assert vocabulario.__name__ in mensaje
    assert "RegistroDeDecision" in mensaje


@pytest.mark.invariants
@pytest.mark.parametrize("vocabulario", VOCABULARIOS, ids=lambda v: v.__name__)
def test_acepta_todos_sus_valores_declarados(vocabulario: type[VocabularioCerrado]) -> None:
    """Cada valor declarado se puede reconstruir desde su cadena."""
    for miembro in vocabulario:
        assert vocabulario(miembro.value) is miembro


@pytest.mark.invariants
def test_los_valores_son_los_de_definitions() -> None:
    """Los vocabularios que v1 usa traen exactamente los valores del documento.

    Se comprueban los tres que mas facilmente derivan: el de eventos, porque su valor
    `perdida` se confundio una vez con `muerte`; el de borrador, porque lo cobra un
    invariante bloqueante; y el de tarea, porque lo fija `AGENTS.md` 7.1.
    """
    assert {m.value for m in TipoDeEvento} == {
        "accion",
        "decision",
        "revelacion",
        "encuentro",
        "perdida",
        "cambio_de_estado",
    }
    assert {m.value for m in EstadoDeBorrador} == {
        "propuesto",
        "en_revision",
        "aceptado",
        "rechazado",
        "obsoleto",
    }
    assert {m.value for m in EstadoDeTarea} == {
        "pendiente",
        "lista",
        "en_curso",
        "en_verificacion",
        "aceptada",
        "rechazada",
        "escalada",
        "fallida",
        "bloqueada",
        "cancelada",
    }


@pytest.mark.invariants
def test_la_semilla_del_catalogo_de_predicados_esta_completa() -> None:
    """R-7 siembra el catalogo con las siete dimensiones de estado, todas funcionales."""
    assert len(DimensionDeEstado) == 7
    assert set(ExclusividadDePredicado) == {
        ExclusividadDePredicado.FUNCIONAL,
        ExclusividadDePredicado.MULTIVALOR,
    }
