"""Semilla de demostracion: una novela minima para poder ver el sistema funcionando.

`uv run python -m backend.store.semilla_demo`

Existe por un motivo concreto: con la base recien migrada, la lectura devuelve `404` y la
pantalla muestra -correctamente- que no ha podido leer nada. Eso esta bien como
comportamiento y esta mal como primera impresion, porque no permite distinguir «la novela
no existe» de «algo esta roto».

Lo que siembra **no es prosa generada**: son las piezas que el sistema necesita para que
la lectura, las versiones y la regeneracion selectiva se puedan recorrer de verdad. El
texto de los capitulos sigue llegando del Redactor, que necesita credenciales.

No se ejecuta en ningun test: los tests construyen su propio material, y una semilla
compartida acabaria decidiendo lo que los tests comprueban.
"""

from __future__ import annotations

import sys

from backend.store import database
from backend.store.repositories import (
    ListasProhibidas,
    UsoDeHechos,
    VersionesDeNovela,
)

VOLUMEN = "vol-1"
BRIEF = "br-demo"
DESTINATARIO = "de-demo"


def sembrar(ruta: str | None = None) -> None:
    """Deja la base con una novela legible de extremo a extremo."""
    with database.conexion(ruta) as conn:
        ya = conn.execute("SELECT 1 FROM volumen WHERE id = ?", (VOLUMEN,)).fetchone()
        if ya is not None:
            print(f"La semilla ya estaba puesta: existe el volumen {VOLUMEN}.")
            return

        conn.executescript(
            f"""
            INSERT INTO brief (id, genero, premisa, promesa_al_lector, extension_objetivo)
            VALUES ('{BRIEF}', 'memoria novelada',
                    'Novela de regalo para Marta',
                    'quien la lea reconocera a Marta en ella', 30000);

            INSERT INTO volumen (id, titulo, brief_id)
            VALUES ('{VOLUMEN}', 'El verano en que aprendiste a nadar', '{BRIEF}');

            INSERT INTO capitulo (id, volumen_id, orden) VALUES ('cap-1', '{VOLUMEN}', 1);
            INSERT INTO capitulo (id, volumen_id, orden) VALUES ('cap-2', '{VOLUMEN}', 2);
            INSERT INTO capitulo (id, volumen_id, orden) VALUES ('cap-3', '{VOLUMEN}', 3);

            INSERT INTO destinatario (id, brief_id, nombre, edad, rasgos, dedicatoria)
            VALUES ('{DESTINATARIO}', '{BRIEF}', 'Marta', 34, 'terca|nada sentimental',
                    'Para Marta, que siempre vuelve al mar.');

            INSERT INTO elemento_personalizado
                (id, destinatario_id, tipo, contenido, obligatorio)
            VALUES ('ep-1', '{DESTINATARIO}', 'recuerdo',
                    'el verano en que aprendio a nadar en Gijon', 1);

            INSERT INTO lugar (id, nombre_canonico, atmosfera_sensorial)
            VALUES ('lu-gijon', 'Gijon', 'olor a salitre y a madera mojada');
            INSERT INTO lugar (id, nombre_canonico) VALUES ('lu-espigon', 'El espigon');

            INSERT INTO personaje
                (id, nombre_canonico, relevancia, necesidad_interna, anio_de_nacimiento)
            VALUES ('pe-marta', 'Marta', 'protagonico',
                    'dejar de tenerle miedo al fondo', 1990);
            INSERT INTO personaje (id, nombre_canonico, anio_de_nacimiento)
            VALUES ('pe-abuelo', 'El abuelo', 1931);

            INSERT INTO evento
                (id, descripcion, posicion_en_historia, tipo, momento, lugar_id)
            VALUES ('ev-1', 'Marta llega a la casa de Gijon', 10, 'accion', 1998,
                    'lu-gijon');
            INSERT INTO evento
                (id, descripcion, posicion_en_historia, tipo, momento, lugar_id)
            VALUES ('ev-2', 'Marta se mete en el agua por primera vez', 20, 'accion',
                    1998, 'lu-espigon');

            INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento)
            VALUES ('ev-1', 'pe-marta', 'agente');
            INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento)
            VALUES ('ev-2', 'pe-marta', 'agente');
            INSERT INTO evento_participante (evento_id, entidad_id, rol_en_evento)
            VALUES ('ev-2', 'pe-abuelo', 'testigo');

            INSERT INTO hecho (id, sujeto_id, predicado, objeto, valido_desde)
            VALUES ('he-perro', 'pe-marta', 'posee', 'un perro llamado Tobi', 'ev-1');
            INSERT INTO hecho (id, sujeto_id, predicado, objeto, valido_desde)
            VALUES ('he-casa', 'pe-marta', 'ubicacion', 'la casa de Gijon', 'ev-1');

            -- Las escenas son lo que hace que la ficha tenga de donde salir: la lectura
            -- muestra quien aparece en **esta** novela, y eso se sabe por lo que narra.
            INSERT INTO escena (id, capitulo_id, orden, pov_id, lugar_id,
                                momento_en_historia, objetivo, conflicto, resultado,
                                valor_entrada, valor_salida, funcion_en_trama, tipo)
            VALUES ('esc-1', 'cap-1', 1, 'pe-marta', 'lu-gijon', 10,
                    'Marta vuelve a la casa y reconoce el olor',
                    'la casa ya no es la que recordaba', 'se queda a dormir',
                    'nostalgia', 'incomodidad', 'giro', 'accion');
            INSERT INTO escena (id, capitulo_id, orden, pov_id, lugar_id,
                                momento_en_historia, objetivo, conflicto, resultado,
                                valor_entrada, valor_salida, funcion_en_trama, tipo)
            VALUES ('esc-2', 'cap-2', 1, 'pe-marta', 'lu-espigon', 20,
                    'Marta se mete en el agua por primera vez',
                    'el fondo no se ve', 'nada veinte metros',
                    'miedo', 'orgullo', 'climax', 'accion');

            INSERT INTO escena_evento (escena_id, evento_id) VALUES ('esc-1', 'ev-1');
            INSERT INTO escena_evento (escena_id, evento_id) VALUES ('esc-2', 'ev-2');
            """
        )

        # El perro sale en dos capitulos y la casa en uno: es lo que permite ver que
        # pedir un cambio sobre el perro regenera dos, y sobre la casa, uno.
        usos = UsoDeHechos(conn)
        usos.registrar("he-perro", "cap-1")
        usos.registrar("he-perro", "cap-3")
        usos.registrar("he-casa", "cap-1")

        # Un termino vetado por el cliente, para poder ver saltar el guardarrail.
        listas = ListasProhibidas(conn)
        listas.anadir("lp-global", nivel="global", termino="imbecil")
        listas.anadir(
            "lp-cliente",
            nivel="cliente",
            termino="Ricardo",
            ambito_id=DESTINATARIO,
            motivo="el cliente pidio que no aparezca",
        )

        # Dos versiones, para que la lectura tenga algo que marcar como cambiado.
        versiones = VersionesDeNovela(conn)
        versiones.publicar(
            "ver-1",
            volumen_id=VOLUMEN,
            capitulos=("cap-1", "cap-2", "cap-3"),
            motivo="primera version",
        )
        versiones.publicar(
            "ver-2",
            volumen_id=VOLUMEN,
            capitulos=("cap-1", "cap-2", "cap-3"),
            cambiados=("cap-3",),
            motivo="el perro se llama Nala",
        )

    print("Semilla puesta.")
    print(f"  volumen      : {VOLUMEN} (3 capitulos, 2 versiones)")
    print("  destinatario : Marta, con un recuerdo obligatorio")
    print("  hechos       : he-perro (cap-1 y cap-3), he-casa (cap-1)")
    print("  vetados      : 'imbecil' (global) y 'Ricardo' (cliente)")
    print()
    print("Abre http://localhost:5173 con el backend en marcha.")


def main() -> int:
    try:
        sembrar(sys.argv[1] if len(sys.argv) > 1 else None)
    except Exception as error:  # noqa: BLE001 - es una herramienta de linea de comandos
        print(f"No se pudo sembrar: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
