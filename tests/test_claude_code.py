"""El cliente real: Claude Code en modo no interactivo, con Haiku y sin clave de API.

Ningun test lanza `claude`: `subprocess.run` se sustituye por uno que devuelve lo que
Claude Code imprime con `--output-format json`. Lo que se comprueba es la frontera -que
argumentos salen y como se traduce lo que vuelve-, no la calidad de la prosa.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from backend.domain.vocabularies import ClaseDeFallo
from backend.worker import modelo
from backend.worker.modelo import (
    MODELO_DE_CLAUDE_CODE,
    ClienteClaudeCode,
    FalloDeInvocacion,
)


def _salida(**cambios: Any) -> str:
    carga: dict[str, Any] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "## prosa\nUn parrafo.",
        "stop_reason": "end_turn",
        "total_cost_usd": 0.01,
        "usage": {"input_tokens": 120, "output_tokens": 30},
        "modelUsage": {"claude-haiku-4-5-20251001": {}},
    }
    carga.update(cambios)
    return json.dumps(carga)


class _Proceso:
    """Sustituto de `subprocess.run` que recuerda como se le llamo."""

    def __init__(self, stdout: str = "", returncode: int = 0, lanza: Exception | None = None):
        self.stdout = stdout
        self.returncode = returncode
        self.lanza = lanza
        self.llamadas: list[dict[str, Any]] = []

    def __call__(
        self, argumentos: list[str], **opciones: Any
    ) -> subprocess.CompletedProcess[str]:
        self.llamadas.append({"argumentos": argumentos, **opciones})
        if self.lanza is not None:
            raise self.lanza
        return subprocess.CompletedProcess(argumentos, self.returncode, self.stdout, "")


def _cliente(monkeypatch: pytest.MonkeyPatch, proceso: _Proceso) -> ClienteClaudeCode:
    monkeypatch.setattr(modelo.subprocess, "run", proceso)
    return ClienteClaudeCode(ejecutable="claude")


@pytest.mark.invariants
def test_invoca_haiku_sin_herramientas_y_con_el_prompt_por_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proceso = _Proceso(stdout=_salida())
    _cliente(monkeypatch, proceso).invocar("el paquete entero", max_tokens=4000)

    llamada = proceso.llamadas[0]
    argumentos = llamada["argumentos"]
    assert argumentos[:2] == ["claude", "-p"]
    assert argumentos[argumentos.index("--model") + 1] == MODELO_DE_CLAUDE_CODE == "haiku"
    # Sin herramientas: un Claude Code que puede leer y escribir ficheros no es un redactor.
    assert argumentos[argumentos.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argumentos
    # Sin pensamiento extendido (`PENSAMIENTO = None`): con el, una escena tardaba 124 s.
    assert json.loads(argumentos[argumentos.index("--settings") + 1]) == {
        "alwaysThinkingEnabled": False
    }
    assert llamada["env"]["MAX_THINKING_TOKENS"] == "0"
    # El prompt no va en la linea de comandos, que en Windows se queda corta.
    assert "el paquete entero" not in argumentos
    assert llamada["input"] == "el paquete entero"
    # Fuera del repositorio, para que no cargue su CLAUDE.md como instrucciones.
    assert Path(llamada["cwd"]) == Path(tempfile.gettempdir())


@pytest.mark.invariants
def test_no_pide_ninguna_clave_de_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    proceso = _Proceso(stdout=_salida())
    respuesta = _cliente(monkeypatch, proceso).invocar("x", max_tokens=4000)
    assert respuesta.texto.startswith("## prosa")


@pytest.mark.invariants
def test_traduce_la_respuesta_con_uso_coste_y_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    respuesta = _cliente(monkeypatch, _Proceso(stdout=_salida())).invocar("x", max_tokens=4000)

    assert respuesta.tokens_entrada == 120
    assert respuesta.tokens_salida == 30
    assert respuesta.coste == pytest.approx(0.01)
    assert respuesta.modelo == "claude-haiku-4-5-20251001"


@pytest.mark.invariants
@pytest.mark.parametrize(
    ("stdout", "clase"),
    [
        (_salida(stop_reason="max_tokens"), ClaseDeFallo.CONTRATO),
        (_salida(is_error=True, subtype="error", api_error_status=400), ClaseDeFallo.CONTRATO),
        (
            _salida(is_error=True, subtype="error", api_error_status=529),
            ClaseDeFallo.TRANSPORTE,
        ),
        (
            _salida(is_error=True, subtype="error", api_error_status=429),
            ClaseDeFallo.TRANSPORTE,
        ),
        ("no es json", ClaseDeFallo.TRANSPORTE),
    ],
)
def test_cada_fallo_cae_en_su_clase(
    monkeypatch: pytest.MonkeyPatch, stdout: str, clase: ClaseDeFallo
) -> None:
    """D-06: un corte no debe gastar reescrituras, y un 4xx no mejora reintentando."""
    with pytest.raises(FalloDeInvocacion) as error:
        _cliente(monkeypatch, _Proceso(stdout=stdout, returncode=1)).invocar(
            "x", max_tokens=4000
        )
    assert error.value.clase is clase


@pytest.mark.invariants
def test_un_vencimiento_es_fallo_de_transporte(monkeypatch: pytest.MonkeyPatch) -> None:
    proceso = _Proceso(lanza=subprocess.TimeoutExpired("claude", 600))
    with pytest.raises(FalloDeInvocacion) as error:
        _cliente(monkeypatch, proceso).invocar("x", max_tokens=4000)
    assert error.value.clase is ClaseDeFallo.TRANSPORTE
