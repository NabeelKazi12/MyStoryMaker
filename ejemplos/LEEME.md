# Qué hay aquí, y qué falta

## `muestra-de-maquetacion.pdf`

Es lo que produce `backend/export/pdf.py`: portada con dedicatoria, página de novedades
—porque es una versión 2—, índice navegable, ficha de personajes y lugares con enlaces
internos, y cuatro capítulos maquetados como prosa.

**No es la novela de ejemplo.** Su texto es un párrafo de muestra repetido, escrito a
mano para poder ver la maquetación. Sirve para comprobar el exportador; no sirve como
evidencia de que el sistema escribe novelas.

## `novela-ejemplo.pdf` — falta

Lo que RF-EVA-04 pide: una novela completa de diez capítulos generada con el brief de
ejemplo del `README`. Todavía no está generada. El cliente real ya está cableado
—invoca a Haiku a través de Claude Code, sin clave de API—, así que generarla es:

1. Tener Claude Code instalado y con sesión iniciada.
2. Ejecutar la generación con el brief del `README` (`.un.ps1`, «Escribir la novela»).
3. Descargar el PDF desde la lectura y guardarlo aquí.

Poner un PDF con texto inventado en su lugar sería peor que no tenerlo: el fichero existe
precisamente para demostrar que el sistema funciona de principio a fin, y uno falso
demostraría lo contrario de lo que dice demostrar.
