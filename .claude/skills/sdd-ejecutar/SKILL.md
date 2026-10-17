---
name: sdd-ejecutar
description: Fase 3 del pipeline SDD de CIMENTA. Implementa un ticket con design aprobado, tests primero y en rojo, después el código que los pone en verde, paso por paso con verificación. Admite modo lote sobre un rango. Úsala cuando el usuario diga /sdd-ejecutar.
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

## Paso 2 · Tests primero, en rojo

**Los tests se escriben antes que el código** ([convenciones §12](../../../docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)). Por cada escenario en alcance —los de la historia y los `x-escenarios` de las operaciones del [borrador OpenAPI](../../../docs/api/openapi.yaml) cuyo `x-tickets` incluye este ticket—, el tester correspondiente (`tester-backend` con `conv-pruebas`) escribe el test que lo nombra:

- Nombre con el escenario: `test_hduXXX_escNN_...`.
- **Al menos un test de rechazo por regla implicada**, y el test de rechazo comprueba **el contrato de error completo** —`tipo`, `regla` o `codigo`, cifras como cadena y `acciones`—, no solo el código de estado.
- Concurrencia donde hay bloqueo pesimista: dos transacciones simultáneas, pasa una; el vencimiento responde `CONCURRENCIA`.

Ejecuta la suite y **pega en `impl.md` la salida en rojo**: cada test nuevo falla, y falla por la razón esperada (la función o la ruta no existe, el rechazo no ocurre), no por un error de importación o de entorno. Un test que nace en verde no prueba nada: o el comportamiento ya existía, o el test no afirma lo que dice.

## Paso 3 · Implementar hasta verde

Fila por fila de la tabla de `design.md`. **La verificación de cada paso corre antes de pasar al siguiente**, y la verificación incluye los tests del paso 2 que esa fila debe poner en verde.

| Si el paso toca | Despacha | Precarga |
|---|---|---|
| Esquema, migración, consulta | `desarrollador-sql` | `conv-sql-postgres` |
| Reglas de negocio | `desarrollador-dominio` | `conv-dominio-python` |
| Casos de uso | `desarrollador-aplicacion` | `conv-backend-fastapi` |
| Endpoints, DTO | `desarrollador-api` | `conv-backend-fastapi` |
| Pantalla nueva | `disenador-ui-ux`, luego `desarrollador-react` | `conv-frontend-react` |
| Imagen, Compose, servicio local | — lo hace el orquestador | `conv-docker` |

**Los desarrolladores van en secuencia, nunca en paralelo.** Tocan los mismos archivos; dos a la vez producen conflictos que ningún linter detecta.

Si el ticket es **corrección de error**: el test que reproduce el fallo se commitea **antes** del arreglo y falla.

Marca cada fila en `design.md`: `✓ Hecho` o `⚠ Ajustado`.

## Paso 4 · Suite completa — paso duro, no se salta

- Todos los tests del paso 2 en verde, **sin haberlos tocado** salvo para corregir un error del propio test, documentado en `impl.md`.
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

Despacha **`auditor-arquitectura`** y, si hubo esquema, **`auditor-sql`**. Son los dos que pueden invalidar el trabajo entero; conviene saberlo ahora y no en `/sdd-revisar`.

- `REQUIERE CAMBIOS` → **`corrector-revision`** con los hallazgos → reauditar. Máximo 3 ciclos.
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
8. El ticket necesita una ruta, un código o un `codigo` de conflicto que no está en el borrador OpenAPI → escalar, salvo que el design ya apruebe el cambio del borrador en este PR.

## Lo que este comando tiene prohibido

Ampliar el alcance · refactorizar de paso · tocar archivos fuera del design · romper compatibilidad sin aprobación · cerrar con auditorías fallidas · añadir funcionalidad que nadie pidió.

Cada ticket declara sus non-goals. Se respetan.
