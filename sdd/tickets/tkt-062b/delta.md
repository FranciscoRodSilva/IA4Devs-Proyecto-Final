# Delta · TKT-062b · Revisión automatizada

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Este ticket se entrega **recortado** (decisión del 2026-10-30, registrada en `_index.md`): la revisión automatizada queda construida pero inactiva, por falta de presupuesto para una clave de API.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Flujo `revision-ia.yml`: trabajo `revision` (lee el PR con permisos de solo lectura, sin `Bash`) y trabajo `publicar` (comenta tras el filtro) | `.github/workflows/revision-ia.yml` | Comentar en cada PR los hallazgos con cita, cuando se active. Hoy está inactivo |
| Filtro de publicación | `tools/publicar_revision.py` | Descartar todo hallazgo sin cita válida o con forma de clave, anteponer los hallazgos mecánicos y componer un único comentario |
| Instrucciones de la revisión | `.claude/revision-pr.md` | Decirle al modelo qué fuentes usar y cómo citar, sin copiar las reglas |
| Pruebas del filtro y del flujo | `tools/tests/test_publicar_revision.py`, `tools/tests/test_definicion_revision.py` | Fijar el comportamiento, con mutantes por compuerta |
| ADR-028 | `docs/adr/20261029-revision-automatizada-de-pr-con-unica-excepcion-de-secretos.md` | Registrar la excepción de `secrets.`, el riesgo residual y el estado de la activación |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Comprobación de `secrets.` | `tools/tests/test_definicion_ci.py`, `test_definicion_dependabot.py` | Ningún flujo podía leer un secreto → solo `revision-ia.yml`, una vez, en `anthropic_api_key` del paso de la acción del trabajo `revision` |
| Convenciones §12, stack §10, `tools/README.md`, `CLAUDE.md`, `README.md`, `llms.txt`, agente `ingeniero-devsecops` | `docs/`, raíz, `.claude/agents/` | La revisión era «comentarios en línea» y un trabajo del pipeline → un comentario único, en un flujo aparte, inactivo hasta que haya clave; 27 → 28 ADR |
| Pasos de `/sdd-completar` | `.claude/skills/sdd-completar/SKILL.md` | Sin esos pasos → invoca `code-review` antes de abrir el PR y deshabilita el flujo al fusionar si falta la clave |
| Registro de evolución | `sdd/_evolucion.md` | Sin filas de TKT-062b → cuatro filas nuevas en la tabla de observaciones |
| Spec y diseño del ticket | `sdd/tickets/tkt-062b/spec.md`, `sdd/tickets/tkt-062/design.md`, `docs/05-tickets-trabajo.md` | Musts completos → recorte registrado del 2026-10-30 |

## Eliminado

Nada.

## Comportamiento observable nuevo

- **Hoy, ninguno visible para quien abre un PR**: el flujo está inactivo y `/sdd-completar` lo deshabilita al fusionar si no hay clave. El primer PR, el de este ticket, mostrará una ejecución de `revision-ia.yml` en rojo que no es comprobación requerida.
- `/sdd-completar` invoca `code-review` antes de abrir cada PR.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| API, DTO, tipos generados, esquema | Ninguno | No |
| Comprobaciones requeridas de `Produccion` | Ninguno: la revisión no es requerida | No |

## Decisiones (ADR)

### 2026-10-29 — Revisión automatizada de PR con única excepción de secretos

Registrada como ADR-028. Contexto, seis opciones descartadas y consecuencias están en `docs/adr/20261029-revision-automatizada-de-pr-con-unica-excepcion-de-secretos.md`, con la sección «Estado de la activación» del 2026-10-30. No se crea otro ADR.

### 2026-10-30 — Recorte por falta de presupuesto

**Contexto:** no hay presupuesto para una clave de API de Anthropic.
**Opciones consideradas:** crédito mínimo prepagado; token de la suscripción; dejar el flujo sin clave; revisión local.
**Decisión:** la revisión local con `code-review`, y lo construido queda inactivo. La tomó la persona responsable.
**Evidencia:** `_index.md`, «Decisiones registradas».
**Consecuencias:** Musts recortados, sin ensayos ni clave; la activación exige un ticket propio. Se resume en el ADR-028, no es un ADR nuevo.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `Read(./**)` solo acota la herramienta `Read`; `Grep` y `Glob` excluyen las rutas denegadas solo «de mejor esfuerzo». El aislamiento real es no darle `Bash` al modelo | Auditoría de seguridad, Context7 (`/websites/code_claude`) | Cualquier agente de IA que lea texto ajeno con un secreto en el entorno |
| `//ruta` es una ruta absoluta en las reglas de Claude Code; `/ruta` se ancla al directorio de trabajo | Context7 | Reglas de permisos de `--disallowedTools` |
| `gh workflow disable` solo puede ver un flujo que ya existe en la rama por omisión | Lectura de `gh workflow list --all` | Desactivar un flujo recién añadido |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | La spec y el diseño asumieron una clave de API de pago sin comprobar el presupuesto; se descubrió al ejecutar B4 | Alta |
| `agente` | El diseño aprobado afirmó que `Read(./**)` impedía leer el entorno; la auditoría de seguridad lo refutó | Alta |
| `comando` | No hay un procedimiento para recortar Musts después de ejecutar: el recorte tuvo que reflejarse a mano en `_index.md`, `spec.md`, `impl.md` y el ADR | Media |
| `agente` | Cada reauditoría acotada de `auditor-arquitectura` o `auditor-docs`, sin el informe anterior, no puede reclasificar y encuentra menudencias nuevas de redacción | Media |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Activar la revisión: clave dedicada con tope, secreto, ronda R2c (N003) y demás rondas de ensayo | Sin presupuesto | Ticket de activación de la revisión automatizada |
| Sanear `@menciones` e imágenes del comentario publicado | Fuera de alcance | Ticket de endurecimiento del filtro |
| `concurrency` en los flujos nuevos | Won't de la spec | Ticket de `concurrency` |
| Primer PR de Dependabot con su etiqueta `agent` y la revisión omitida | Solo se observa tras fusionar | Seguimiento en el cierre del ticket abierto entonces |

## Pull request

**Título:** `TKT-062b · Revisión automatizada`
**Origen:** `agent`. Lo escribieron agentes; la revisión humana es la persona que aprueba.
**Cuerpo:** qué (flujo, filtro, instrucciones, ADR-028, recorte), por qué (comentar hallazgos con cita sin aprobar ni bloquear), criterios cubiertos (los vigentes tras el recorte, de forma estática), cómo verificarlo (`python -m unittest discover -s tools/tests`, `zizmor`, `verificar_docs`) y qué no se hizo (clave, ensayos).

**Fusión con omisión:** esta fusión será con omisión de la protección de `Produccion`. El registro va en un comentario del PR que el orquestador deja justo después de `gh pr merge --admin`, con la aprobación explícita de la persona dueña.
