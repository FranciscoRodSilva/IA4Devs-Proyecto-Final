---
name: sdd-revisar
description: Fase 4 del pipeline SDD de CIMENTA. Verifica criterio por criterio, corre la suite, despacha las auditorías en paralelo y ejecuta el ciclo de corrección. No implementa nada nuevo. Úsala cuando el usuario diga /sdd-revisar.
argument-hint: TKT-xxx [--paralelo]
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill
---

# `/sdd-revisar $ARGUMENTS`

Verifica la implementación. **No implementa funcionalidad nueva**: valida, detecta desviaciones y mueve el estado.

## Paso 0 · Gate — si falla, STOP

- `_index.md` en estado `EN REVISIÓN`. Si no, di el estado actual y para. En un ticket partido en entregas el estado va calificado (`EN REVISIÓN · entrega TKT-xxxa`) y este comando revisa **esa entrega**, no el ticket entero: sus criterios `[M]`, su sección de `impl.md` y su diff.
- `impl.md` existe. Si no, devuelve a `/sdd-ejecutar`.

## Paso 1 · Completitud, antes de gastar en auditorías

Tres comprobaciones. Si alguna falla, **no corras auditorías sobre un `impl.md` incompleto**:

| Dimensión | Pregunta |
|---|---|
| **Completitud** | ¿Cada criterio `[M]` de `spec.md` tiene resultado explícito y evidencia en `impl.md`? |
| **Corrección** | ¿Se implementó exactamente lo de la spec, sin alcance de más? |
| **Coherencia** | ¿Los archivos y objetos de `impl.md` coinciden con los declarados en `design.md`? |

Si falla: documenta los huecos en `impl.md`, estado `REQUIERE CAMBIOS`, devuelve.

Cada fila del orden de implementación debe traer en `impl.md` la salida literal de su rojo. Una fila sin salida de rojo registrada es hallazgo Mayor. La reproducción apartando el módulo prueba que el test falta, no que falla por comportamiento, y no la sustituye. Solo la acepta la persona dueña con el riesgo escrito en `impl.md`.

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

Despacha las que apliquen. **En paralelo**: son de solo lectura e independientes entre sí. Con `--paralelo` es el comportamiento por defecto; sin el modificador, en secuencia. La auditoría que además aplica mutantes es la excepción y se despacha en serie, como dice el paso 4.

| Auditor | Cuándo | Modelo |
|---|---|---|
| `auditor-arquitectura` | **Siempre** | `sonnet` |
| `auditor-sql` | Hubo esquema, migración o consulta | `sonnet` |
| `auditor-codigo` | Hubo Python o TypeScript | `sonnet` |
| `auditor-seguridad` | Hay endpoint, entrada externa, archivo, sesión, Dockerfile, Compose, *workflow* de CI o dependencia nueva | `sonnet` |
| `auditor-docs` | El cambio altera comportamiento | `haiku` |

El orquestador pasa el modelo en el parámetro `model` de `Agent`. La primera pasada de una auditoría nunca baja de la columna; una reauditoría acotada a hallazgos Menores ya corregidos puede ir en `haiku` ([metodología §14.2](../../../sdd/metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)).
A cada uno le entregas el diff real. **Sin diff, el auditor devuelve `REQUIERE CONTEXTO` y no emite veredicto** — no audites en vacío. En un ticket partido, el diff de la entrega es el de la rama desde el commit de cierre de la entrega anterior (`git diff <ese commit>` más los archivos nuevos), o desde la base si es la primera; el auditor no revisa de nuevo lo que ya aprobó una entrega anterior.
Comprueba también cada veredicto recibido: un `APROBADO` sin la sección «Qué verifiqué» ítem por ítem no es veredicto. Se trata como `REQUIERE CONTEXTO` y se relanza.

## Paso 4 · Ciclo de corrección

- `REQUIERE CAMBIOS` → **`corrector-revision`** (`haiku` por omisión) con los hallazgos, literales. Aplica eso y nada más: no refactoriza de paso, no mejora lo que nadie señaló.
- Reauditar. Cada hallazgo se reclasifica `Resuelto` / `Persiste` / `Nuevo` por su identificador.
- **Máximo 3 ciclos.** Al tercero con hallazgos críticos o mayores vivos → `REQUIERE DECISIÓN` → `/sdd-escalar`.
- **Criterio de parada para la redacción.** Las secciones de cierre (`Verificación final`, `Resultado`, resúmenes de corrección) se generan copiando la salida real de los comandos, sin reformularla, y el auditor las compara con esa salida. Cada hallazgo trae el **texto literal esperado** y el corrector lo copia sin reformular. Tras el segundo ciclo, un hallazgo que solo afecte a la redacción de una sección de cierre no abre una tercera reauditoría: lo resuelve el orquestador con la salida real, lo anota en el log de estados y se lo comunica a la persona dueña. Un hallazgo sobre código, un criterio o un contrato sí obliga a reauditar.
- **Menor vivo al tercer ciclo.** Tras el segundo ciclo, un hallazgo Menor u Observación que no cambie el comportamiento del producto, sea de redacción o de código de pruebas, no abre una tercera reauditoría. Lo resuelve el orquestador con el texto literal del auditor, lo anota en el log de estados con su identificador y se lo comunica a la persona dueña. Ese auditor queda en `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`. Un Crítico o un Mayor sí obliga a reauditar o a `REQUIERE DECISIÓN`.
- **Sin mutación sobre el árbol en uso.** Mientras corre la suite completa no se despacha ningún agente que escriba en el árbol. Una auditoría con mutación se despacha en serie, tras la suite, y muta sobre una copia fuera del repositorio.
- **La reauditoría recibe el informe previo literal**, con sus identificadores, para poder reclasificar cada hallazgo. Sin el informe previo, un auditor no puede decir `Resuelto`, `Persiste` o `Nuevo` y encuentra menudencias nuevas en cada ciclo.
- `RIESGOSO` o `BLOQUEAR` → **`corrector-revision` no actúa**. Estado `RIESGOSO` → `/sdd-escalar`.

## Paso 5 · Veredicto de aprobación

| Nivel pendiente | ¿Puede aprobar? |
|---|---|
| Must `[M]` incumplido | **Nunca** |
| Should `[S]` incumplido | Solo si se recortó vía `/sdd-escalar` y consta en `_index.md` |
| Could `[C]` no hecho | Sí — ni se reporta como pendiente |

**Bloqueos duros.** No emitas el veredicto de aprobación de la entrega (`LISTO PARA PR` si es la última o el ticket no está partido; `LISTO PARA EJECUTAR · TKT-xxxb` si falta alguna) si:

- algún test falla sin justificación registrada;
- algún criterio `[M]` no tiene cobertura de test verificada. Quedan fuera los que solo pueden verificarse con el pipeline de un PR real (por ejemplo, «los nueve trabajos de `ci.yml` en verde»): se anotan en `impl.md` como «se verifica en `/sdd-completar`» y ese comando no fusiona sin esa evidencia. Este comando no abre PR;
- no hay **ningún test de rechazo** para una regla implicada;
- hay ruta crítica sin mutación probada ni justificación;
- cualquier auditor quedó en `REQUIERE CAMBIOS` o `RIESGOSO`, salvo el caso del paso 4: Menores resueltos sin reauditar y comunicados a la persona dueña;
- alguna fila no tiene registrada la salida literal de su rojo, salvo que la persona dueña acepte el riesgo y conste escrito en `impl.md` (paso 1);
- la documentación afectada no se actualizó en este mismo cambio;
- el alcance cambió sin autorización registrada.

## Paso 6 · Cerrar

1. Añade «Verificación final» a `impl.md` con el resultado por criterio, la suite, los veredictos y las desviaciones. Copia las cifras (`passed`, casos por archivo) de la salida del comando de la última corrida, no de la anterior: tras un ciclo de corrección cambian. En un ticket partido, una «Verificación final» **por entrega**.
2. `_index.md`: estado resultante y fila de Log. Si la entrega aprobada **no es la última** de un ticket partido, el estado es `LISTO PARA EJECUTAR · TKT-xxxb` (la entrega siguiente) y el Log dice que la entrega quedó revisada y acumulada en la rama del ticket, **sin PR**. Solo al aprobar la **última** entrega el estado es `LISTO PARA PR`, sin calificador.
3. Si la entrega aprobada no es la última, despacha **`git-entrega`** en modo **cierre de entrega**: un commit local en la rama del ticket, sin push ni PR, que deja a salvo el trabajo y marca el límite del diff de la entrega siguiente. Si es la última o el ticket no está partido, no commitea: lo hace `/sdd-completar`.
4. Reporta en pocas líneas: criterios cumplidos sobre el total, resultado de la suite, veredicto de cada auditor, ciclos de corrección, y qué quedó anotado fuera de alcance.
5. Siguiente: si falta una entrega, `/sdd-ejecutar` sobre la siguiente. **No sugieras `/sdd-completar`** hasta que no quede ninguna. Si `LISTO PARA PR` → `/sdd-completar` sobre el ticket.

## Qué NO hace este comando

No implementa funcionalidad nueva · no amplía alcance · no aprueba con auditorías pendientes · no arregla por su cuenta lo que debe arreglar `corrector-revision`.
