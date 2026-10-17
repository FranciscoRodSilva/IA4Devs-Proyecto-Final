# Impl · TKT-xxx · <título>

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

## Qué se implementó

Narrativa breve. Lo detallado va en las tablas.

## Ajustes respecto al design

Todo paso marcado `⚠ Ajustado` aparece aquí. Si no hubo: «Ninguno».

| Fecha | Cambio | Motivo |
|---|---|---|

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| | nuevo · modificado · eliminado | dominio · aplicación · api · infraestructura · frontend · pruebas |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_hduxxx_escNN_...` | feliz | `CA-1` | FALLA | PASA |
| TC-02 | `test_hduxxx_escNN_...` | **rechazo** | `CA-2` | FALLA | PASA |

### Ciclo TDD por fila

Una entrada por fila del orden de implementación de `design.md`, en el orden en que se ejecutaron ([metodología §16](../metodologia.md#16--el-ciclo-tdd)).

#### Fila N · <paso>

**Rojo** — cada test de la fila falla, y por la razón esperada:

```
<salida real en rojo>
```

**Verde** — los tests de la fila y la suite previa:

```
<salida real en verde>
```

**Refactor:** qué se limpió, o «sin refactor».

**Tests devueltos al tester:** cuál, por qué, qué se corrigió. O «ninguno».

**Evidencia de ejecución al cerrar:** pegar la línea de resumen real de `pytest` / `vitest` / `playwright`, con `docker info` respondiendo. Sin evidencia, el resultado no cuenta.

```
<salida real>
```

**Mutación en rutas críticas:** qué se mutó, qué test se puso rojo. O «No aplica» con el motivo.

## Modelo por paso

Un registro por despacho a un agente ([metodología §14.2](../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)).

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 1 · verde | `desarrollador-dominio` | `haiku` | `sonnet` | Dos intentos en `haiku` sin verde en TC-02 |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-01 |

Un Must incumplido **no se aprueba**. Un Should recortado solo vale si consta en `_index.md` vía `/sdd-escalar`.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | | | |
| `auditor-sql` | | | |
| `auditor-codigo` | | | |
| `auditor-seguridad` | | | |
| `auditor-docs` | | | |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | | | `archivo.py:42` | | Resuelto · Persiste · Nuevo |

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí** — se anotan para su propio ticket.

| Archivo | Observación | Prioridad |
|---|---|---|

## Documentación actualizada

| Documento | Qué cambió |
|---|---|

`python tools/verificar_docs.py` → resultado:

## Verificación final

- [ ] Todos los criterios `[M]` cumplidos con evidencia
- [ ] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [ ] Suite en verde, con la salida pegada arriba
- [ ] ≥1 test de rechazo por regla implicada
- [ ] Mutación en rutas críticas, o «no aplica» justificado
- [ ] Todas las auditorías `APROBADO`
- [ ] Sin hallazgo crítico o mayor pendiente
- [ ] Documentación afectada actualizada en este mismo cambio
- [ ] `ruff`, `mypy`, `lint-imports` limpios
- [ ] Rama correcta y sin secretos en el diff
