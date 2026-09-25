"""Cambiar el nombre de una entidad en un texto, sin tocar nada mas.

Es una sustitucion exacta y no una reescritura: lo que no casa como palabra completa se
queda como estaba, a la vista de quien lee. Adivinar declinaciones o apodos convertiria
un cambio verificable en uno que nadie puede revisar (SPEC-013 N-04).

Funcion pura: no sabe de SQLite ni de novelas, solo de textos.

Cubre RF-NOM-07 a RF-NOM-09.
"""

from __future__ import annotations

import re

from backend.domain.spec.encargo import clave_de_nombre


class SustitucionDeNombre:
    """Las parejas «viejo -> nuevo» de un cambio de nombre, compiladas una vez.

    El nombre completo se sustituye siempre, tal cual y en mayusculas. Cada palabra suelta
    del viejo que empiece por mayuscula se sustituye por la de la misma posicion del
    nuevo si los dos tienen las mismas palabras; si no, solo la primera. Una palabra que
    tambien lleva el nombre de otro personaje (`otros`) no se toca suelta: con dos
    Ortega, «Ortega» no dice cual de los dos es.
    """

    def __init__(self, anterior: str, nuevo: str, *, otros: tuple[str, ...] = ()) -> None:
        anterior, nuevo = " ".join(anterior.split()), " ".join(nuevo.split())
        parejas: dict[str, str] = {anterior: nuevo, anterior.upper(): nuevo.upper()}

        viejas, nuevas = anterior.split(), nuevo.split()
        if len(viejas) > 1 or len(nuevas) > 1:
            sueltas = (
                zip(viejas, nuevas, strict=True)
                if len(viejas) == len(nuevas)
                else [(viejas[0], nuevas[0])]
            )
            ajenas = {clave_de_nombre(p) for otro in otros for p in otro.split()}
            for vieja, nueva in sueltas:
                if vieja[:1].isupper() and clave_de_nombre(vieja) not in ajenas:
                    parejas.setdefault(vieja, nueva)

        self.parejas = {v: n for v, n in parejas.items() if v != n}
        # Una sola expresion, la alternativa mas larga primero: asi «Luis Ortega» gana a
        # «Luis», y lo ya sustituido no se vuelve a sustituir (RF-NOM-09).
        alternativas = sorted(self.parejas, key=len, reverse=True)
        self._patron = (
            re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, alternativas)) + r")(?!\w)")
            if alternativas
            else None
        )

    def aplicar(self, texto: str) -> str:
        if self._patron is None or not texto:
            return texto
        return self._patron.sub(lambda m: self.parejas[m.group(0)], texto)
