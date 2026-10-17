---
name: sdd-ejecutar
description: Fase 3 del pipeline SDD de CIMENTA. Implementa un ticket con design aprobado por ciclos TDD rojo, verde y refactor, fila por fila, eligiendo el modelo de cada despacho para ahorrar tokens. Admite modo lote sobre un rango. Úsala cuando el usuario diga /sdd-ejecutar.
argument-hint: TKT-xxx [--lote TKT-yyy]
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill, WebSearch, WebFetch
---

# `/sdd-ejecutar $ARGUMENTS`

Implementa el ticket. Lee [`sdd/metodologia.md`](../../../sdd/metodologia.md).

## Paso 0 · Gate — si falla, STOP

- `_index.md` en estado `LISTO PARA EJECUTAR`. Si está en `DISEÑO PENDIENTE REVISIÓN`, **el usuario aún no aprobó**: dilo y para.
- `design.md` existe y tiene sección para cada capa en alcance.
- Las dependencias declaradas están `ARCHIVADO` o `LISTO PARA PR`.
- El ticket es de la fase que toca. Un ticket de fase 1 no adelanta nómina, destajo, captura sin conexión ni evidencia (regla 17 de `CLAUDE.md`).
- **Docker está corriendo** si el ticket tiene pruebas de integración: `docker info` responde. testcontainers levanta PostgreSQL y MinIO en Docker; sin el demonio, la suite no se salta, falla. Ver [`conv-docker`](../conv-docker/SKILL.md).

## Paso 1 · Rama

Despacha **`git-entrega`** en modo apertura: crea o verifica `tkt-xxx-<slug>` desde la rama base. **Antes de editar nada.**

## Paso 2 · Ciclo TDD, fila por fila

**Los tests se escriben antes que el código** ([convenciones §12](../../../docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)), y no en bloque: el ciclo rojo → verde → refactor de [metodología §16](../../../sdd/metodologia.md#16--el-ciclo-tdd) se repite **por cada fila** del orden de implementación de `design.md`. La fila siguiente no empieza hasta que la anterior cerró su refactor en verde.

### 2a · Rojo

Despacha **`tester-backend`** con la fila y los casos de su columna «Tests que pone en verde». Escribe un test por escenario —los de la historia y los `x-escenarios` de las operaciones del [borrador OpenAPI](../../../docs/api/openapi.yaml) cuyo `x-tickets` incluye este ticket— y los ejecuta:

- Nombre con el escenario: `test_hduXXX_escNN_...`.
- **Al menos un test de rechazo por regla implicada**, y el test de rechazo comprueba **el contrato de error completo** —`tipo`, `regla` o `codigo`, cifras como cadena y `acciones`—, no solo el código de estado.
- Concurrencia donde hay bloqueo pesimista: dos transacciones simultáneas, pasa una; el vencimiento responde `CONCURRENCIA`.

**Pega en `impl.md` la salida en rojo**: cada test falla por la razón esperada (la función o la ruta no existe, el rechazo no ocurre), no por un error de importación, de sintaxis o de entorno. Un test que nace en verde se investiga antes de seguir.

### 2b · Verde

Despacha al desarrollador de la capa con la fila **y los tests en rojo**. Escribe el código mínimo que los pone en verde, de uno en uno.

| Si el paso toca | Despacha | Precarga | Modelo por omisión |
|---|---|---|---|
| Esquema, migración, consulta | `desarrollador-sql` | `conv-sql-postgres` | `haiku` |
| Reglas de negocio | `desarrollador-dominio` | `conv-dominio-python` | `haiku` |
| Casos de uso | `desarrollador-aplicacion` | `conv-backend-fastapi` | `haiku` |
| Endpoints, DTO | `desarrollador-api` | `conv-backend-fastapi` | `haiku` |
| Pantalla nueva | `disenador-ui-ux`, luego `desarrollador-react` | `conv-frontend-react` | `haiku` |
| Pipeline de CI, imagen, Compose, dependencias, escaneo de secretos | `ingeniero-devsecops` | `conv-docker`, `conv-seguridad` | `sonnet` |

**Los desarrolladores van en secuencia, nunca en paralelo.** Tocan los mismos archivos; dos a la vez producen conflictos que ningún linter detecta.

Si el desarrollador devuelve un test por considerarlo equivocado, vuelve a `tester-backend` con el motivo. **Ningún desarrollador edita un test.**

### 2c · Refactor

El mismo desarrollador, con todo en verde, limpia sin cambiar comportamiento y vuelve a correr la suite. Pega en `impl.md` la salida en verde de la fila y qué se refactorizó.

Marca la fila en `design.md`: `✓ Hecho` o `⚠ Ajustado`.

Si el ticket es **corrección de error**: el primer ciclo arranca con el test que reproduce el fallo, y ese test se commitea en rojo **antes** del arreglo.

## Paso 3 · Elegir el modelo de cada despacho

Antes de cada llamada a `Agent`, el orquestador **decide el modelo y lo pasa en el parámetro `model`**. La tabla completa de disparadores y límites está en [metodología §14.2](../../../sdd/metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho); en resumen:

1. Usa el modelo de la columna Modelo de la fila en `design.md`. Si la fila no lo dice, el del frontmatter del agente.
2. **Sube a `sonnet`** un paso en `haiku` que no pone en verde sus tests tras dos intentos, o que rompe un test que ya estaba en verde.
3. **No subas a `opus`** un paso de ejecución. Si `sonnet` tampoco cierra tras dos intentos, el diseño tiene un hueco → `/sdd-escalar`.
4. **Baja a `haiku`** a un agente `sonnet` solo en tareas mecánicas verificables por comando. Nunca en la primera pasada de una auditoría, y nunca al tester por debajo del desarrollador cuyo trabajo verifica.

Anota cada despacho en la tabla «Modelo por paso» de `impl.md`, con el motivo de cada cambio.

## Paso 4 · Suite completa — paso duro, no se salta

Despacha **`tester-backend`** en su momento de cierre.

- Todos los tests del paso 2 en verde, **sin haberlos tocado** salvo para corregir un error del propio test, hecho por el tester y documentado en `impl.md`.
- Cada criterio de aceptación tiene su test. **Sin un test de rechazo por regla implicada, la fase no cierra.**
- PostgreSQL y MinIO reales con testcontainers, esquema por `alembic upgrade head`, conexión con el rol de aplicación. **Nunca SQLite, nunca `create_all()`.**
- **Mutación** en rutas críticas: muta un operador o un umbral, confirma que algún test se pone rojo, deshaz la mutación y anota qué cayó. Si ninguno se inmuta, falta un test.
- **Pega la salida real** de la suite en `impl.md`. Un «todo en verde» sin evidencia no cuenta.

Prohibido alterar o borrar un test para que la suite pase.

## Paso 5 · Documentación y ADR

En **este mismo cambio**:

- Actualiza la documentación afectada.
- Si `design.md` dijo que merece ADR: créalo en `docs/adr/YYYYMMDD-slug.md`, formato MADR, con su entrada en el índice.
- Corre `python tools/verificar_docs.py`.

## Paso 6 · Auditoría de cierre de fase

Despacha **`auditor-arquitectura`** y, si hubo esquema, **`auditor-sql`**, en `sonnet`. Son los dos que pueden invalidar el trabajo entero; conviene saberlo ahora y no en `/sdd-revisar`.

- `REQUIERE CAMBIOS` → **`corrector-revision`** (`haiku`; `sonnet` si algún hallazgo es Mayor y toca un disparador del paso 3) con los hallazgos → reauditar. Máximo 3 ciclos.
- `RIESGOSO` → detener **todo** el flujo → `/sdd-escalar`.

## Paso 7 · Cerrar

1. Escribe `impl.md` desde [la plantilla](../../../sdd/plantillas/impl.md).
2. `_index.md`: estado `EN REVISIÓN`, fila de Log.
3. Reporta archivos tocados, resultado de la suite, veredictos, y qué quedó fuera de alcance anotado.
4. Siguiente: `/sdd-revisar`.

## Iteración fluida — no vuelvas a `/sdd-disenar` por todo

**Ajuste menor** (otro enfoque técnico, un archivo más, un campo extra): actualiza `design.md` directamente, documenta el ajuste en `impl.md` con fecha y motivo, sigue. No cambies de estado.

**Ajuste mayor** (el alcance crece más de 30 %, aparece un sistema afectado que nadie previó, surge un riesgo nuevo): **detente**, documenta, estado `REQUIERE DECISIÓN`, `/sdd-escalar`.

## Modo lote — `--lote`

`/sdd-ejecutar TKT-011 --lote TKT-014` encadena los tickets del rango.

Condiciones, todas:

- Todos están en `LISTO PARA EJECUTAR` — es decir, **sus diseños ya pasaron el gate humano**. El lote no salta aprobaciones.
- Mismo módulo, sin reglas de negocio nuevas.
- El lote entero suma menos de ~400 líneas estimadas y no cruza más de dos módulos.

Por cada ticket: ejecutar → revisar → completar. Avanza al siguiente **solo** si todo salió verde.

**Para el lote entero** en el primer `REQUIERE DECISIÓN`, `RIESGOSO`, Must incumplido o tercer ciclo de corrección sin cerrar. Reporta en qué ticket paró, qué quedó archivado y qué quedó sin tocar.

## Stop conditions

1. Estado distinto de `LISTO PARA EJECUTAR` → no implementar.
2. `design.md` sin sección para una capa en alcance → no implementar esa capa a ciegas.
3. Cualquier agente devuelve `RIESGOSO` → detener **todo**, no solo ese paso.
4. El alcance crece más de 30 % → `REQUIERE DECISIÓN`.
5. Tres ciclos de corrección con hallazgos críticos o mayores vivos → escalar.
6. Hace falta una regla de negocio que el PRD no tiene → escalar. **No la inventes.**
7. Vas a implementar una regla sin su test de rechazo en rojo → no. Primero el test.
8. Un paso en `sonnet` no cierra tras dos intentos → no subas a `opus`: escalar.
9. El ticket necesita una ruta, un código o un `codigo` de conflicto que no está en el borrador OpenAPI → escalar, salvo que el design ya apruebe el cambio del borrador en este PR.

## Lo que este comando tiene prohibido

Ampliar el alcance · refactorizar de paso · tocar archivos fuera del design · romper compatibilidad sin aprobación · cerrar con auditorías fallidas · añadir funcionalidad que nadie pidió.

Cada ticket declara sus non-goals. Se respetan.
