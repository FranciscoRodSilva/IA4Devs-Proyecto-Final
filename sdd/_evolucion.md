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
| 2026-10-17 | TKT-001 | `herramienta` | `verificar_docs.py` falla durante todo el ticket porque el hub y `design.md` enlazan `impl.md` y `delta.md`, que aún no existen. Afecta a todos los tickets: el verificador que el pipeline manda correr antes de cerrar no puede dar código 0 hasta `/sdd-completar`. | Alta |
| 2026-10-17 | TKT-001 | `agente` | Faltan los agentes `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `meta-sdd` y `desarrollador-aplicacion`, que los comandos nombran. Se sustituyeron según metodología §13. Segunda vez que aparece esta fricción (ver la observación del 2026-10-01). | Media |
| 2026-10-17 | TKT-001 | `comando` | `/sdd-ejecutar` y `/sdd-revisar` asumen `pytest`, testcontainers, Docker y `lint-imports`, que un ticket de fundación no tiene. Se resolvió con una excepción registrada en la spec y el diseño. Falta una variante «ticket de fundación» en esos dos comandos. | Media |
| 2026-10-17 | TKT-001 | `guardrail` | `/sdd-ejecutar` no comprueba el entorno antes de empezar. El diseño fijó Node 24 y el equipo tenía Node 22: la verificación se detuvo hasta que el usuario instaló Node 24. El gate debería comparar las versiones de `engines` y `requires-python` con las instaladas. | Media |
| 2026-10-17 | TKT-001 | `agente` | `arquitecto-tecnico` no tiene terminal, así que no pudo consultar versiones ni valores por omisión reales. Tres supuestos del diseño fallaron al ejecutar: el rojo de `npm ci`, `I001` en el conjunto por omisión de Ruff y la existencia de `@eslint/js` 10.13.0. | Baja |
| 2026-10-17 | TKT-001 | `agente` | Cada reauditoría de `auditor-arquitectura` devolvió hallazgos sobre el texto exacto de una marca que el corrector había escrito de forma aproximada: tres ciclos para dos celdas de texto. Conviene que el hallazgo incluya el texto literal esperado y que el corrector lo copie sin reformular. | Media |
| 2026-10-17 | TKT-001 | `convención` | El `.editorconfig` fija LF y la copia de trabajo en Windows está en CRLF porque Git convierte al descargar. El índice está en LF y `.gitattributes` lo mantiene, pero ningún documento lo aclara para quien edite en Windows. | Baja |
| 2026-10-17 | TKT-001 | `guardrail` | `git-entrega` en modo apertura manda parar si hay cambios ajenos sin commitear. Había dos archivos de `.claude/` modificados antes del ticket y la rama se abrió arrastrándolos. El procedimiento no dice cómo separarlos del commit del ticket. | Baja |

Temas en uso: `plantilla` · `agente` · `comando` · `guardrail` · `convención` · `documentación` · `contexto` · `herramienta` · `modelo`.

## Patrones detectados

Un patrón entra aquí cuando aparece en tres tickets o más.

| Tema | Veces | Qué pasa | Propuesta | Estado |
|---|---|---|---|---|

Estado: `Propuesto` · `Aprobado` · `Aplicado` · `Descartado` (con motivo).

## Tendencias

Lo que escribe `/sdd-completar` cuando hay suficientes tickets cerrados: dónde se va el tiempo, qué auditor encuentra más, cuántos ciclos de corrección de media, qué tipo de hallazgo se repite.
