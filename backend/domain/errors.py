"""Errores del dominio.

`CLAUDE.md` 5.3 exige que todo mensaje de error vaya en espanol y nombre la clase y el
invariante violado. Centralizarlo aqui evita que cada clase lo formatee a su manera, que
es como se acaba con mensajes que no dicen contra que regla se choco.

Cubre RF-DOM-08.
"""

from __future__ import annotations


class ErrorDeDominio(ValueError):
    """Un invariante del dominio no se cumple.

    Hereda de `ValueError` a proposito: construir un objeto invalido es un error de
    valor, y asi el codigo que ya captura `ValueError` no se rompe.
    """

    def __init__(self, clase: str, invariante: str, detalle: str = "") -> None:
        self.clase = clase
        self.invariante = invariante
        self.detalle = detalle
        mensaje = f"{clase}: {invariante}"
        if detalle:
            mensaje = f"{mensaje}. {detalle}"
        super().__init__(mensaje)


def exigir(condicion: bool, clase: str, invariante: str, detalle: str = "") -> None:
    """Lanza `ErrorDeDominio` si la condicion no se cumple.

    Se usa en los `__post_init__` para que cada invariante se lea como una frase.
    """
    if not condicion:
        raise ErrorDeDominio(clase, invariante, detalle)
