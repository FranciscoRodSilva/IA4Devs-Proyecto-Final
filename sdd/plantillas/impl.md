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

| # | Test | Tipo | Criterio | Resultado |
|---|---|---|---|---|
| TC-01 | `test_hduxxx_escNN_...` | feliz | `CA-1` | PASA |
| TC-02 | `test_hduxxx_escNN_...` | **rechazo** | `CA-2` | PASA |

**Evidencia de ejecución:** pegar la línea de resumen real de `pytest` / `vitest` / `playwright`. Sin evidencia, el resultado no cuenta.

```
<salida real>
```

**Mutación en rutas críticas:** qué se mutó, qué test se puso rojo. O «No aplica» con el motivo.

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
- [ ] Suite en verde, con la salida pegada arriba
- [ ] ≥1 test de rechazo por regla implicada
- [ ] Mutación en rutas críticas, o «no aplica» justificado
- [ ] Todas las auditorías `APROBADO`
- [ ] Sin hallazgo crítico o mayor pendiente
- [ ] Documentación afectada actualizada en este mismo cambio
- [ ] `ruff`, `mypy`, `lint-imports` limpios
- [ ] Rama correcta y sin secretos en el diff
