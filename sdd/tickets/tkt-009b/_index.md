# TKT-009b · Cadena de suministro

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

EN REVISIÓN

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M; unas 300 líneas según el diseño común |
| **Reglas implicadas** | `RNF-07`, `RNF-08` |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R2`, `CA-R3` y `CA-R4` |
| **Módulos en alcance** | `tools/severidad_pip_audit.py`, el trabajo `dependencias` de `ci.yml`, `.github/dependabot.yml`, `backend/pyproject.toml` (`pip-audit`) y los ajustes del repositorio |
| **Capas en alcance** | Entrega continua y herramientas. Ninguna capa de la aplicación |
| **Depende de** | TKT-009a; fusiona después de TKT-009c |
| **Bloquea a** | TKT-009d (por el orden de fusión) |
| **Rama** | `tkt-009b-cadena-suministro` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-28 |
| Design | [design.md común](../tkt-009/design.md), filas B1 a B7 | `/sdd-disenar` | Aprobado el 2026-10-28 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-28; B5 y B6 pendientes de la persona dueña |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009. Spec repartida: M7, M8 y su parte de M12; `CA-10`, `CA-11`, `CA-R2`, `CA-R3` y `CA-R4`. No se ejecuta hasta que TKT-009a esté `ARCHIVADO` o `LISTO PARA PR`. Tercera parte en fusionar. La fila B5 exige acciones de la persona dueña del repositorio |
| 2026-10-28 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas B1 a B4 y B7 hechas con su ciclo TDD y mutación; 247 pruebas de `tools/` en verde. **Quedan pendientes B5 (ajustes del repositorio) y B6 (ensayo en el pipeline), que ejecuta la persona dueña con la guía [ajustes-repositorio.md](ajustes-repositorio.md); sin ellas `CA-10` esc. 2 y 3, `CA-11` esc. 2 y `CA-R3` esc. 2 no tienen evidencia y el ticket no puede pasar a `LISTO PARA PR`.** Arquitectura: dos Menores documentales corregidos |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: la severidad «alta» sale del aviso de GitHub en OSV y falla si no se puede determinar, y no hay archivo de excepción para las credenciales de `.env.example`.
