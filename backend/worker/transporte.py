"""El transporte HTTP del cliente de Langfuse.

Vive en `worker/` y no en `observability/` porque `observability/` no puede usar
bibliotecas de red (`test_import_boundaries`): observa y no participa. El worker ya habla
con la red —es quien invoca al modelo—, asi que es quien le presta el transporte
(SPEC-012 DV-1).
"""

from __future__ import annotations

import urllib.error
import urllib.request


def transporte_urllib(
    metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None, espera: float
) -> tuple[int, bytes]:
    """Una peticion con tiempo de espera corto. Los `4xx` y `5xx` vuelven como estado."""
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=espera) as respuesta:  # noqa: S310
            return int(respuesta.status), respuesta.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()
