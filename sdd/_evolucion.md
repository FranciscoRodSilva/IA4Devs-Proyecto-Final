# Evolución del toolkit

> Dónde se anota la fricción del **proceso**, no del producto. Cada `/sdd-completar` añade sus filas; `meta-sdd` las agrupa por tema y, cuando un patrón se repite **tres veces o más**, propone una mejora al toolkit.
>
> `meta-sdd` **propone**. No aplica nada sin aprobación.

## Observaciones

| Fecha | Ticket | Tema | Observación | Severidad |
|---|---|---|---|---|
| 2026-10-01 | — (construcción del toolkit) | `convención` | Al escribir `conv-dominio-python` se inventó una regla —«los rechazos son valores, nunca excepciones»— que contradice `TKT-005`, el cual define una excepción de dominio con manejador global. La documentación del proyecto decía lo contrario y nadie lo habría notado hasta implementar TKT-005. Corregido. **El patrón a vigilar: una convención que suena razonable y no está escrita en ningún documento es una regla inventada.** | Alta |
| 2026-10-01 | — (construcción del toolkit) | `herramienta` | Reescribir frontmatter con `Set-Content -Encoding UTF8` en Windows PowerShell 5.1 añade BOM, y el BOM rompe el parseo del `---` inicial de un agente o una skill. Seis agentes quedaron ilegibles sin que nada lo avisara. Refuerza el criterio de `TKT-001`: el `.editorconfig` del repositorio debe fijar `charset = utf-8` sin BOM para `.md`. | Media |
| 2026-10-01 | — (construcción del toolkit) | `agente` | Los comandos del pipeline nombran trece agentes que todavía no existen. Se resolvió con la regla de sustitución de [metodologia §13](metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe) en vez de recortar los comandos: el comando debe nombrar al especialista correcto aunque no esté construido. | Baja |
| 2026-10-17 | — (alineación con la Entrega 2) | `documentación` | El toolkit se construyó sobre la Entrega 1 y la Entrega 2 lo dejó desfasado en silencio: citaba 26 invariantes (ahora 38), 16 reglas (ahora 17, con la de fases y ADR-017), un contrato de error de tres códigos (ahora siete `tipo`, con `CONFLICTO` y `CONCURRENCIA`), ignoraba el borrador OpenAPI y los wireframes, y ordenaba implementar antes de probar cuando convenciones §12 exige tests primero. Corregido, y añadida `conv-docker`. **El patrón a vigilar: el toolkit copia cifras y reglas de `docs/`; cada cambio de `docs/` que mueva un conteo o una regla tiene que revisar `.claude/` y `sdd/` en el mismo PR.** | Alta |
| 2026-10-17 | — (revisión de agentes) | `modelo` | Se redistribuyeron los modelos: `opus` con esfuerzo medio solo para definir y diseñar; `haiku` por omisión para ejecutar y `sonnet` para el tester, los auditores y DevSecOps. El orquestador elige el modelo en cada despacho con la tabla de disparadores de [metodología §14](metodologia.md#14--enrutamiento-de-modelo). Los auditores bajan de `opus` a `sonnet`: **vigilar si aumentan los hallazgos que llegan a la revisión humana sin haberse detectado**; si pasa, es la señal para devolver `auditor-arquitectura` a `opus`. | Media |

Temas en uso: `plantilla` · `agente` · `comando` · `guardrail` · `convención` · `documentación` · `contexto` · `herramienta` · `modelo`.

## Patrones detectados

Un patrón entra aquí cuando aparece en tres tickets o más.

| Tema | Veces | Qué pasa | Propuesta | Estado |
|---|---|---|---|---|

Estado: `Propuesto` · `Aprobado` · `Aplicado` · `Descartado` (con motivo).

## Tendencias

Lo que escribe `/sdd-completar` cuando hay suficientes tickets cerrados: dónde se va el tiempo, qué auditor encuentra más, cuántos ciclos de corrección de media, qué tipo de hallazgo se repite.
