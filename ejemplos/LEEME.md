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
ejemplo del `README`. No está, y el motivo es concreto: `construir_cliente_real()` en
`backend/worker/modelo.py` sigue sin cablear —es la desviación 1 de SPEC-001— y este
entorno no tiene credenciales del proveedor.

Para generarla hacen falta tres cosas, en este orden:

1. Cablear el cliente real del modelo y confirmar el identificador de D-17 contra la
   Models API.
2. Poner `ANTHROPIC_API_KEY` en `.env`.
3. Ejecutar la generación con el brief del `README` y exportar el resultado aquí.

Poner un PDF con texto inventado en su lugar sería peor que no tenerlo: el fichero existe
precisamente para demostrar que el sistema funciona de principio a fin, y uno falso
demostraría lo contrario de lo que dice demostrar.
