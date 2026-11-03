# CIMENTA — instrucciones para agentes (Cursor y cualquier herramienta que lea `AGENTS.md`)

**Lee primero [`CLAUDE.md`](CLAUDE.md), completo.** Es la única fuente de las instrucciones de este proyecto: el orden de lectura de `docs/`, las 17 reglas que ninguna implementación puede romper, el stack, la estructura del backend, los comandos, lo que no se hace y el pipeline SDD. Este archivo no las repite con detalle: si algo de aquí contradice a `CLAUDE.md`, gana `CLAUDE.md`.

El proyecto se trabaja con dos herramientas, Claude Code y Cursor, y las dos deben tener el mismo contexto. Por eso `CLAUDE.md` no se duplica en otro archivo.

## Las 17 reglas, en una línea cada una

Es un recordatorio por si el agente no abre `CLAUDE.md`. El texto completo, con su porqué y sus enlaces, está allí.

1. El dinero nunca es flotante: `Decimal` / `NUMERIC` / cadena en JSON / `decimal.js`. Sin `float` en `dominio/` ni `tipos_base/`.
2. `dominio/` no importa nada: solo la biblioteca estándar y `tipos_base`. Sin reloj ni E/S.
3. Un módulo solo habla con otro por `cimenta.<modulo>.interfaz`.
4. La línea base congelada es inmutable.
5. Los límites bloquean, no advierten. `consumido = requisiciones vivas + comprometido + ejercido`; una requisición `EVALUADA` consume.
6. Todo gasto lleva `obra_id`; toda requisición, además `tipo_partida_id`.
7. El inventario es un libro mayor de solo-anexado. Sin columna de existencia.
8. La bitácora se escribe en la misma transacción y no admite `UPDATE` ni `DELETE`.
9. Sesión con estado en el servidor. Ni JWT ni cookie autocontenida.
10. En la obra no hay internet: solo `avance` y `entrada_almacen` se capturan sin conexión, y el cliente nunca evalúa una regla.
11. SQLAlchemy síncrono; rutas `def`, nunca `async def`.
12. El avance físico se divide entre `alcance_destajo`; sin avance validado el porcentaje es `NULL`.
13. Quien mide no fija el número contra el que se le mide.
14. Ningún criterio de aceptación cubre solo el camino feliz.
15. Los archivos no pasan por el API ni viven en PostgreSQL; tipo leído de los bytes, `SVG` prohibido, adjuntos anulados con motivo.
16. La evidencia no condiciona ninguna regla ni viaja en la cola sin conexión (`PA-14`).
17. Dos fases: la fase 1 es el hilo vertical; nómina, destajo, captura sin conexión y evidencia son fase 2. Lo simulado nunca entra en el `consumido`.

Y dos más del apartado «Qué no hacer»: **no asumas nada** (toda duda se le pregunta a la persona dueña, con tu recomendación) y **no amplíes el alcance de un ticket**.

## Cómo se organiza el trabajo para las dos herramientas

| Qué | Dónde vive | Cómo lo usa Cursor |
|---|---|---|
| Instrucciones de proyecto | `CLAUDE.md` | Se lee desde este archivo |
| Agentes de Claude Code (fuente única) | `.claude/agents/*.md` | Cursor los escanea también, pero su `model: haiku` o `sonnet` no es un identificador de Cursor |
| Agentes de Cursor (generados) | `.cursor/agents/*.md` | Tienen precedencia sobre `.claude/agents/` cuando el nombre coincide. Los 23 usan `composer-2.5[fast=false]` (Composer 2.5, sin *fast*) |
| Skills y comandos `/sdd-*` | `.claude/skills/*/SKILL.md` | Cursor las carga desde `.claude/skills/`; se invocan con `/` en el chat del agente |
| Convenciones por capa | `.claude/skills/conv-*` | Cursor no las precarga: cada agente generado empieza con la orden de leer las suyas |

**`.cursor/agents/` es un derivado.** No se edita a mano. Se cambia el agente en `.claude/agents/` y se regenera:

```bash
python tools/agentes_cursor.py --generar
python tools/agentes_cursor.py --verificar
```

La verificación corre también en la suite de `tools/tests/`, así que un desfase entre los dos directorios rompe el pipeline.

## Qué cambia al trabajar desde Cursor

- **El modelo lo fija el agente.** En Claude Code el orquestador elige el modelo en cada despacho ([metodología §14](sdd/metodologia.md#14--enrutamiento-de-modelo)). En Cursor los 23 agentes corren en Composer 2.5 sin *fast*; no hay subida a `sonnet` tras dos intentos fallidos. Si un paso no cierra tras dos intentos, el diseño tiene un hueco: `/sdd-escalar`, no insistir.
- **No hay *hooks* de Claude Code.** El recordatorio de comunicación de `.claude/hooks/` no se ejecuta, así que se repite aquí: en la **conversación** (respuestas de chat, reportes de avance, veredictos) sé breve, sin relleno y sin repetir lo ya dicho. **Nunca** apliques esa brevedad a lo que se escribe a disco —`spec.md`, `design.md`, `impl.md`, `delta.md`, ADR, docstrings, documentación de `docs/` ni mensajes de commit—: va en prosa completa y con acentos, porque es el entregable y pasa por Vale.
- **Las herramientas tienen otros nombres.** Los agentes citan `Read`, `Write`, `Edit`, `Bash`, `PowerShell`, `Skill` y `Agent` (Claude Code); usa el equivalente de Cursor. Context7 se usa igual si el servidor MCP está conectado en Cursor.
- **Los permisos de `.claude/settings.json` no aplican.** Pide aprobación según la política de Cursor; las reglas del proyecto no cambian.
- **Las transiciones con dueño humano siguen siéndolo:** aprobar el diseño, resolver lo escalado y aprobar la fusión a `Produccion`.

## Antes de dar un cambio por terminado

Los comandos están en `CLAUDE.md`, apartado «Comandos». Como mínimo, según lo que tocaste: `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run pytest` desde `backend/`; `npm run lint`, `npm run typecheck` y `npm test` desde `frontend/`; `python tools/verificar_docs.py` si cambiaste documentación.
