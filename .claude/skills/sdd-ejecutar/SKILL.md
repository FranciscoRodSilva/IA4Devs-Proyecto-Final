---
name: sdd-ejecutar
description: Fase 3 del pipeline SDD de CIMENTA. Implementa un ticket con design aprobado y genera sus tests en paralelo, paso por paso con verificación. Admite modo lote sobre un rango. Úsala cuando el usuario diga /sdd-ejecutar.
argument-hint: TKT-xxx [--lote TKT-yyy]
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill, WebSearch, WebFetch
---

# `/sdd-ejecutar $ARGUMENTS`

Implementa el ticket. Lee [`sdd/metodologia.md`](../../../sdd/metodologia.md).

## Paso 0 · Gate — si falla, STOP

- `_index.md` en estado `LISTO PARA EJECUTAR`. Si está en `DISEÑO PENDIENTE REVISIÓN`, **el usuario aún no aprobó**: dilo y para.
- `design.md` existe y tiene sección para cada capa en alcance.
- Las dependencias declaradas están `ARCHIVADO` o `LISTO PARA PR`.

## Paso 1 · Rama

Despacha **`git-entrega`** en modo apertura: crea o verifica `tkt-xxx-<slug>` desde la rama base. **Antes de editar nada.**

## Paso 2 · Ejecutar el orden de implementación

Fila por fila de la tabla de `design.md`. **La verificación de cada paso corre antes de pasar al siguiente.**

| Si el paso toca | Despacha | Precarga |
|---|---|---|
| Esquema, migración, consulta | `desarrollador-sql` | `conv-sql-postgres` |
| Reglas de negocio | `desarrollador-dominio` | `conv-dominio-python` |
| Casos de uso | `desarrollador-aplicacion` | `conv-backend-fastapi` |
| Endpoints, DTO | `desarrollador-api` | `conv-backend-fastapi` |
| Pantalla nueva | `disenador-ui-ux`, luego `desarrollador-react` | `conv-frontend-react` |
| Tests | `tester-backend`, `tester-api`, `tester-frontend` | `conv-pruebas` |

**Los desarrolladores van en secuencia, nunca en paralelo.** Tocan los mismos archivos; dos a la vez producen conflictos que ningún linter detecta.

Si el ticket es **corrección de error**, o el design pide ciclo TDD: despacha **`desarrollador-tdd`** primero. El test que reproduce el fallo se commitea **antes** del arreglo y falla.

Marca cada fila en `design.md`: `✓ Hecho` o `⚠ Ajustado`.

## Paso 3 · Probar — paso duro, no se salta

El test nace con el código, no «después si da tiempo».

- Cada criterio de aceptación tiene su test, con el escenario en el nombre: `test_hduXXX_escNN_...`.
- **Al menos un test de rechazo por regla implicada.** Sin eso, la fase no cierra.
- Concurrencia donde hay bloqueo pesimista: dos transacciones simultáneas, pasa una.
- PostgreSQL real con testcontainers, esquema por `alembic upgrade head`, conexión con el rol de aplicación. **Nunca SQLite, nunca `create_all()`.**
- **Mutación** en rutas críticas: muta un operador o un umbral, confirma que algún test se pone rojo, deshaz la mutación y anota qué cayó. Si ninguno se inmuta, falta un test.
- **Pega la salida real** de la suite en `impl.md`. Un «todo en verde» sin evidencia no cuenta.

Prohibido alterar o borrar un test para que la suite pase.

## Paso 4 · Documentación y ADR

En **este mismo cambio**:

- Actualiza la documentación afectada.
- Si `design.md` dijo que merece ADR: créalo en `docs/adr/YYYYMMDD-slug.md`, formato MADR, con su entrada en el índice.
- Corre `python tools/verificar_docs.py`.

## Paso 5 · Auditoría de cierre de fase

Despacha **`auditor-arquitectura`** y, si hubo esquema, **`auditor-sql`**. Son los dos que pueden invalidar el trabajo entero; conviene saberlo ahora y no en `/sdd-revisar`.

- `REQUIERE CAMBIOS` → **`corrector-revision`** con los hallazgos → reauditar. Máximo 3 ciclos.
- `RIESGOSO` → detener **todo** el flujo → `/sdd-escalar`.

## Paso 6 · Cerrar

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
7. Vas a implementar una regla sin su test de rechazo → no. Primero el test.

## Lo que este comando tiene prohibido

Ampliar el alcance · refactorizar de paso · tocar archivos fuera del design · romper compatibilidad sin aprobación · cerrar con auditorías fallidas · añadir funcionalidad que nadie pidió.

Cada ticket declara sus non-goals. Se respetan.
