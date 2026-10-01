# `sdd/` — El toolkit de trabajo de CIMENTA

Aquí vive **cómo se trabaja**. Lo que se construye vive en [`docs/`](../docs/).

| Archivo | Qué es |
|---|---|
| [`00-propuesta-toolkit.md`](00-propuesta-toolkit.md) | El diseño y su porqué: por qué no OpenSpec, qué se tomó de SDD-Nice, convenciones investigadas, catálogo de agentes |
| [`metodologia.md`](metodologia.md) | El núcleo: estados, veredictos, escalera de decisión, cuándo se escala |
| [`plantillas/`](plantillas/) | `_index` · `spec` · `design` · `impl` · `delta` |
| [`tickets/`](tickets/) | Un directorio por ticket, versionado. Es la trazabilidad del proyecto |
| [`_evolucion.md`](_evolucion.md) | Fricción del proceso. `meta-sdd` la lee para proponer mejoras |

El pipeline y los comandos están resumidos en [`CLAUDE.md`](../CLAUDE.md). Los agentes en [`.claude/agents/`](../.claude/agents/), las convenciones por stack en [`.claude/skills/`](../.claude/skills/).

## El flujo, en una pantalla

```
/sdd-definir  →  /sdd-disenar  →  [GATE humano]  →  /sdd-ejecutar  →  /sdd-revisar  →  /sdd-completar
                                                                            │
                                                               auditorías en paralelo
                                                                            │
                                                     REQUIERE CAMBIOS → corrector → reauditar (máx. 3)
                                                     RIESGOSO          → /sdd-escalar

/sdd-avance  ─── en cualquier momento, no modifica nada
```

## Los tres principios que lo sostienen

**Nadie aprueba su propio trabajo.** El que escribe no audita; el que audita no corrige; el que corrige vuelve a auditoría.

**El agente no decide lo que no le corresponde.** Un invariante que estorba, una regla que el PRD no tiene, un alcance que creció: se escala. No se resuelve por iniciativa propia.

**Un guardrail que no corre no es un guardrail.** Lo innegociable se verifica con un linter, un hook o una auditoría — no con un recordatorio en un Markdown.
