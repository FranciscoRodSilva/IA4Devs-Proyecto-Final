# Verificadores de documentación

Tres comprobaciones que no existen como herramienta de terceros y que este proyecto necesita **porque su documentación es el entregable**. Se escribieron durante la Entrega 1 y ya detectaron fallos reales: un diagrama con sintaxis inválida, enlaces a un documento que aún no existía, un conteo de escenarios descuadrado tras renumerar y un ancla rota al renumerar las secciones del stack.

Complementan a las herramientas estándar del pipeline —`markdownlint-cli2`, `Vale` y `lychee`—, que cubren sintaxis Markdown, prosa y enlaces externos. Ver [`docs/convenciones.md` §10](../docs/convenciones.md#10-validación-de-documentación-en-ci).

## `verificar_docs.py`

```bash
python tools/verificar_docs.py
```

Sin dependencias. Devuelve código de salida `1` si encuentra algún problema, para que falle el pipeline.

| Comprueba | Qué detecta |
|---|---|
| **Enlaces relativos** | Un enlace a un documento que no existe |
| **Anclas internas** | Un `#seccion` que no resuelve, reproduciendo el algoritmo de anclas de GitHub |
| **Identificadores** | Una regla `RN-xx`, requisito no funcional `RNF-xx`, pregunta `PA-xx`, funcionalidad `Fx.y`, historia `HDU-xxx`, ticket `TKT-xxx` o invariante citado pero inexistente |
| **Requisitos huérfanos** | Un `RNF-xx` que solo aparece donde se declara: está escrito pero ningún ticket lo recoge. Es un **aviso**, no un fallo |
| **ADRs** | Un ADR sin entrada en el índice, o una entrada sin archivo |
| **Rangos de tickets** | Un `TKT-011 … TKT-018` del plan de sprints que cita tickets que no existen |
| **Story points** | Que la suma de la tabla de historias coincida con el total declarado |
| **Escenarios** | Numeración contigua, y que cada Definition of Done declare el número real de escenarios de su historia |
| **Codificación** | Documentos `.md` y `llms.txt` que empiezan por BOM, y scripts `.ps1` que no empiezan por él. Windows PowerShell 5.1 lee un `.ps1` sin BOM como ANSI y corrompe los acentos |

El último es el que sostiene la [regla de aceptación](../docs/04-historias-usuario.md#regla-de-aceptación): una historia cuyo conteo no cuadra suele ser una historia a la que se le añadió un escenario sin actualizar su criterio de cierre.

**El aviso de requisitos huérfanos existe por cómo aparecieron los `RNF`.** Se añadieron al PRD en la revisión del stack del 2026-09-19, y un requisito no funcional es justo el tipo de cosa que se escribe una vez, se siente resuelta y no la implementa nadie. El aviso no rompe el pipeline —declarar antes de implementar es legítimo— pero deja constancia de cuántos siguen sin dueño.

## Pruebas

```bash
python -m unittest discover -s tools/tests -v
```

Las pruebas de `verificar_docs.py` usan solo la biblioteca estándar y se ejecutan desde la raíz del repositorio. Cada caso construye su árbol de archivos en un directorio temporal.

El pipeline las corre en el trabajo `herramientas`, con `unittest` y sin `-v`, y falla si la salida contiene `skipped=`: una prueba saltada no cuenta como verde. Sin `-v`, `unittest` no imprime los docstrings, así que un docstring que contenga `skipped=` no provoca un falso rojo.

`test_definicion_ci.py` comprueba la definición de `.github/workflows/ci.yml`: que cada compuerta esté en su trabajo, en el orden que exige el criterio, con sus comandos, permisos y disparadores. Lee el texto del flujo con expresiones regulares, porque la biblioteca estándar no trae analizador de YAML. El fijado de las acciones por SHA no lo comprueba este archivo: lo revisa `zizmor`, que sí analiza los flujos. Se ejecuta desde la raíz con `python -m unittest tools.tests.test_definicion_ci -v`.

## `extraer_mermaid.py`

```bash
python tools/extraer_mermaid.py
python -m http.server 8000 --directory tools
# abrir http://127.0.0.1:8000/mermaid-check.html
```

Extrae los diagramas Mermaid de toda la documentación y genera una página que los parsea con Mermaid 11. El título de la pestaña dice `TODO OK` o `FALLOS: n`.

**Por qué importa:** un diagrama con error de sintaxis no se ve como un diagrama roto en GitHub — se ve como un bloque de error en medio del documento.

**Por qué necesita navegador:** el único parser fiable de Mermaid es el suyo. En integración continua conviene sustituirlo por [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli), que hace lo mismo sin navegador; este script existe para verificar en local sin instalar Node.

Sírvelo por HTTP: con `file://` los navegadores bloquean la carga del módulo.

## `verificar_escenarios.py`

```bash
python tools/verificar_escenarios.py [--raiz ruta] [--activas-base ruta]
```

Comprueba la regla de aceptación de [ADR-012](../docs/adr/20260918-trazabilidad-escenario-test.md): cada escenario que cuenta tiene al menos un test que lo nombra. Lee los escenarios de `docs/04-historias-usuario.md`, los nombres de los tests de `backend/tests/`, `frontend/src/`, `frontend/scripts/` y `frontend/e2e/` (sin `node_modules`). En TypeScript ignora las líneas que empiezan por `//` o `*` y los bloques `/* … */`, aunque ocupen varias líneas; un `/*` a mitad de una línea de código no abre bloque (límite de A-8). Lee además `tools/historias_activas.txt`. Usa solo la biblioteca estándar. El trabajo `herramientas` del pipeline lo ejecuta en cada PR y, cuando la base del PR contiene el archivo, le pasa esa copia con `--activas-base`.

**Argumentos.** `--raiz` indica la raíz del repositorio; por omisión, la que contiene `tools/`. `--activas-base` indica el `historias_activas.txt` de la base del PR: si existe, se compara con el actual, y si no existe, no se compara.

**Qué cuenta.** Un escenario cuenta si su historia figura en `tools/historias_activas.txt` y no está retirado, y además su fase es 1, o es 2 y el archivo contiene la línea `fase 2`. La fase 2 se marca con el segmento ` · fase 2` en el título, o con la columna `Fase` de la tabla «El conjunto» igual a `2`. Un escenario se retira con el segmento ` · retirado por TKT-0NN` en su título; una nota en prosa no lo retira.

**Etiquetas de la salida.** Cada línea empieza por su etiqueta:

| Etiqueta | Qué significa | Efecto |
|---|---|---|
| `FALTA` | Un escenario que cuenta no tiene ningún test que lo nombre | Falla (código 1) |
| `ERROR` | Un test nombra una historia o un escenario que no existe, o una historia o la línea `fase 2` salió de la lista respecto de la base del PR | Falla (código 1) |
| `PENDIENTE` | Un escenario que todavía no cuenta: su historia no tiene ticket en curso, o es de fase 2 sin iniciar | Informa |
| `RETIRADO` | Un escenario con el segmento de retiro en su título | Informa |

La última línea resume los recuentos: escenarios, exigidos, cubiertos, faltan, pendientes, retirados, tests HDU y tests de fundación.

**Códigos de salida.** `0` si no hay `FALTA` ni `ERROR`; `1` si hay alguno; `2` si la entrada está mal formada: una línea de `historias_activas.txt` que no es `HDU-NNN`, `fase 2`, comentario ni vacía; una historia activa que no existe en el documento; una historia sin fila en «El conjunto»; una historia que aparece dos veces en el documento; una fila de «El conjunto» sin columna `Fase`; la falta de `docs/04-historias-usuario.md` o de `tools/historias_activas.txt`; un `historias_activas.txt` de la base del PR mal formado; o un archivo que no está en UTF-8 (el mensaje nombra su ruta relativa).

**Cómo se actualiza `tools/historias_activas.txt`.** La planificación de cada sprint añade una línea `HDU-NNN` por cada historia que entra en él, y añade la línea `fase 2` cuando empieza la fase 2. Las líneas que empiezan por `#` son comentarios. Ninguna línea sale del archivo: si una historia sale, el verificador da `ERROR` contra la base del PR. Un escenario retirado se marca con su segmento en el título del documento de historias, nunca quitando la historia de la lista.

**Pruebas.** `python -m unittest discover -s tools/tests -v` las ejecuta junto con el resto de `tools/`, y el trabajo `herramientas` las corre con esa misma orden. Los casos de `tools/tests/test_verificar_escenarios.py` construyen documentos de ejemplo en un directorio temporal; el de «árbol real» lee el repositorio.
