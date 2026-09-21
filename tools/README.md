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

El último es el que sostiene la [regla de aceptación](../docs/04-historias-usuario.md#regla-de-aceptación): una historia cuyo conteo no cuadra suele ser una historia a la que se le añadió un escenario sin actualizar su criterio de cierre.

**El aviso de requisitos huérfanos existe por cómo aparecieron los `RNF`.** Se añadieron al PRD en la revisión del stack del 2026-09-19, y un requisito no funcional es justo el tipo de cosa que se escribe una vez, se siente resuelta y no la implementa nadie. El aviso no rompe el pipeline —declarar antes de implementar es legítimo— pero deja constancia de cuántos siguen sin dueño.

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

## Pendiente

**Verificador de escenarios sin test**, descrito en [ADR-012](../docs/adr/20260918-trazabilidad-escenario-test.md): recorrerá las historias, extraerá cada `HDU-XXX esc. N` y comprobará que existe al menos un test que lo nombra. Se escribirá en TKT-009, cuando exista código que verificar.
