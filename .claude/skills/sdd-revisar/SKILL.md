---
name: sdd-revisar
description: Fase 4 del pipeline SDD de CIMENTA. Verifica criterio por criterio, corre la suite, despacha las auditorías en paralelo y ejecuta el ciclo de corrección. No implementa nada nuevo. Úsala cuando el usuario diga /sdd-revisar.
argument-hint: TKT-xxx [--paralelo]
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill
---

# `/sdd-revisar $ARGUMENTS`

Verifica la implementación. **No implementa funcionalidad nueva**: valida, detecta desviaciones y mueve el estado.

## Paso 0 · Gate — si falla, STOP

- `_index.md` en estado `EN REVISIÓN`. Si no, di el estado actual y para.
- `impl.md` existe. Si no, devuelve a `/sdd-ejecutar`.

## Paso 1 · Completitud, antes de gastar en auditorías

Tres comprobaciones. Si alguna falla, **no corras auditorías sobre un `impl.md` incompleto**:

| Dimensión | Pregunta |
|---|---|
| **Completitud** | ¿Cada criterio `[M]` de `spec.md` tiene resultado explícito y evidencia en `impl.md`? |
| **Corrección** | ¿Se implementó exactamente lo de la spec, sin alcance de más? |
| **Coherencia** | ¿Los archivos y objetos de `impl.md` coinciden con los declarados en `design.md`? |

Si falla: documenta los huecos en `impl.md`, estado `REQUIERE CAMBIOS`, devuelve.

## Paso 2 · Correr la suite de verdad

No te fíes de lo que dice `impl.md`: ejecútala.

```bash
docker info
uv run pytest
uv run ruff check .
uv run mypy cimenta/
uv run lint-imports
python tools/verificar_docs.py
```

`docker info` va primero: testcontainers necesita el demonio, y una suite que no levanta PostgreSQL o MinIO no es una suite en verde. Y lo que aplique del frontend. **Pega la salida real.** Si algo falla, eso es un hallazgo, no una nota al pie.

Comprueba además, en el diff:

- Que el ciclo TDD dejó rastro en `impl.md`: por cada fila, la salida en rojo **antes** de la de verde, y ningún test editado por un desarrollador. Un test sin su salida en rojo no demuestra que prueba algo.
- Que cada test de rechazo afirma **el contrato de error completo** —`tipo`, `regla` o `codigo`, cifras y `acciones`—, no solo el código de estado.
- Que las rutas y los códigos coinciden con el [borrador OpenAPI](../../../docs/api/openapi.yaml). **Todo PR que toca `docs/api/openapi.yaml` se señala** a la persona que aprueba, tenga o no un defecto ([convenciones §12](../../../docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)).

## Paso 3 · Auditorías

Despacha las que apliquen. **En paralelo**: son de solo lectura e independientes entre sí. Con `--paralelo` es el comportamiento por defecto; sin el modificador, en secuencia.

| Auditor | Cuándo | Modelo |
|---|---|---|
| `auditor-arquitectura` | **Siempre** | `sonnet` |
| `auditor-sql` | Hubo esquema, migración o consulta | `sonnet` |
| `auditor-codigo` | Hubo Python o TypeScript | `sonnet` |
| `auditor-seguridad` | Hay endpoint, entrada externa, archivo, sesión, Dockerfile, Compose, *workflow* de CI o dependencia nueva | `sonnet` |
| `auditor-docs` | El cambio altera comportamiento | `haiku` |

El orquestador pasa el modelo en el parámetro `model` de `Agent`. La primera pasada de una auditoría nunca baja de la columna; una reauditoría acotada a hallazgos Menores ya corregidos puede ir en `haiku` ([metodología §14.2](../../../sdd/metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)).
A cada uno le entregas el diff real. **Sin diff, el auditor devuelve `REQUIERE CONTEXTO` y no emite veredicto** — no audites en vacío.

## Paso 4 · Ciclo de corrección

- `REQUIERE CAMBIOS` → **`corrector-revision`** (`haiku` por omisión) con los hallazgos, literales. Aplica eso y nada más: no refactoriza de paso, no mejora lo que nadie señaló.
- Reauditar. Cada hallazgo se reclasifica `Resuelto` / `Persiste` / `Nuevo` por su identificador.
- **Máximo 3 ciclos.** Al tercero con hallazgos críticos o mayores vivos → `REQUIERE DECISIÓN` → `/sdd-escalar`.
- **Criterio de parada para la redacción.** Las secciones de cierre (`Verificación final`, `Resultado`, resúmenes de corrección) se generan copiando la salida real de los comandos, sin reformularla, y el auditor las compara con esa salida. Cada hallazgo trae el **texto literal esperado** y el corrector lo copia sin reformular. Tras el segundo ciclo, un hallazgo que solo afecte a la redacción de una sección de cierre no abre una tercera reauditoría: lo resuelve el orquestador con la salida real, lo anota en el log de estados y se lo comunica a la persona dueña. Un hallazgo sobre código, un criterio o un contrato sí obliga a reauditar.
- **La reauditoría recibe el informe previo literal**, con sus identificadores, para poder reclasificar cada hallazgo. Sin el informe previo, un auditor no puede decir `Resuelto`, `Persiste` o `Nuevo` y encuentra menudencias nuevas en cada ciclo.
- `RIESGOSO` o `BLOQUEAR` → **`corrector-revision` no actúa**. Estado `RIESGOSO` → `/sdd-escalar`.

## Paso 5 · Veredicto de aprobación

| Nivel pendiente | ¿Puede aprobar? |
|---|---|
| Must `[M]` incumplido | **Nunca** |
| Should `[S]` incumplido | Solo si se recortó vía `/sdd-escalar` y consta en `_index.md` |
| Could `[C]` no hecho | Sí — ni se reporta como pendiente |

**Bloqueos duros.** No emitas `LISTO PARA PR` si:

- algún test falla sin justificación registrada;
- algún criterio `[M]` no tiene cobertura de test verificada. Quedan fuera los que solo pueden verificarse con el pipeline de un PR real (por ejemplo, «los nueve trabajos de `ci.yml` en verde»): se anotan en `impl.md` como «se verifica en `/sdd-completar`» y ese comando no fusiona sin esa evidencia. Este comando no abre PR;
- no hay **ningún test de rechazo** para una regla implicada;
- hay ruta crítica sin mutación probada ni justificación;
- cualquier auditor quedó en `REQUIERE CAMBIOS` o `RIESGOSO`;
- la documentación afectada no se actualizó en este mismo cambio;
- el alcance cambió sin autorización registrada.

## Paso 6 · Cerrar

1. Añade «Verificación final» a `impl.md` con el resultado por criterio, la suite, los veredictos y las desviaciones.
2. `_index.md`: estado resultante y fila de Log.
3. Reporta en pocas líneas: criterios cumplidos sobre el total, resultado de la suite, veredicto de cada auditor, ciclos de corrección, y qué quedó anotado fuera de alcance.
4. Si `LISTO PARA PR` → siguiente: `/sdd-completar`.

## Qué NO hace este comando

No implementa funcionalidad nueva · no amplía alcance · no aprueba con auditorías pendientes · no arregla por su cuenta lo que debe arreglar `corrector-revision`.
