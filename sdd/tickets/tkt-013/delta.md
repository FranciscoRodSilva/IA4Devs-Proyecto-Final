# Delta · TKT-013 · Lector del catálogo de conceptos

> [← index](_index.md) | [← impl](impl.md)

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Modelo en memoria del catálogo leído (`CatalogoLeido`, `Hallazgo`, jerarquía) | `backend/cimenta/presupuesto/dominio/catalogo.py`, `lectura_catalogo.py` | Interpretar Excel sin escribir en PostgreSQL (HDU-001 esc. 5–8, 27) |
| Totales de previsualización (S1) | `backend/cimenta/presupuesto/dominio/totales_catalogo.py` | Conteos e importe calculado; «no calculable» nunca cero |
| Adaptador openpyxl (único import de la librería) | `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | Leer bytes `.xlsx` y delegar reglas al dominio |
| Dependencias `openpyxl`, `defusedxml`, `types-openpyxl` | `backend/pyproject.toml`, `uv.lock` | Lectura posicional y XML endurecido |
| ADR-033 lectura posicional del catálogo | `docs/adr/20261102-lectura-posicional-del-catalogo.md` | Profundidad por corrida y `Decimal(repr(f))` |
| Pruebas TC-01–TC-43, TC-INV, regresión | `backend/tests/test_tkt013_*.py`, `herramientas/soporte_tkt013.py` | Cobertura sintética, CI y archivos reales opcionales (PA-T3) |
| Variables locales de catálogo | `docs/arranque-local.md` | `CIMENTA_CATALOGO_ENITI` / `UNION` |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Conteo de ADR (33) | `CLAUDE.md`, `README.md`, `llms.txt` | 32 → 33 |
| Stack: Excel y defusedxml | `docs/06-stack-tecnologico.md` | openpyxl en runtime; defusedxml desde TKT-013b |
| Partición TKT-013a/b y dependencia TKT-014 | `docs/05-tickets-trabajo.md` | TKT-014 depende de TKT-013b |
| TC-56 resumen escenarios | `tools/tests/test_verificar_escenarios.py` | `tests HDU 0` fijo → recuento dinámico |
| Fixture `LibroCatalogo` | `backend/tests/conftest.py` | — → libros sintéticos para TKT-013b |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| — | — | Nada eliminado |

## Comportamiento observable nuevo

El backend puede **leer un catálogo de conceptos desde bytes `.xlsx`**, localizar la hoja y el encabezado, reconstruir obra › nivel › área › partida › concepto, normalizar unidades, convertir cifras a `Decimal` y devolver **hallazgos crudos** (sin clasificación TKT-015). No persiste ni expone HTTP en este ticket. Con variables de entorno, las pruebas validan los archivos ENITI y Union Square reales.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI / endpoints | Sin cambios | No |
| Esquema PostgreSQL | Sin cambios | No |
| Tipos generados frontend | Sin cambios | No |
| Dependencias backend | `openpyxl`, `defusedxml` | No (nuevas) |

## Decisiones (ADR)

→ [ADR-033 · Lectura posicional del catálogo](../../../docs/adr/20261102-lectura-posicional-del-catalogo.md): primera corrida alineada a raíz, demás a partida; números vía `Decimal(repr(float))`; resultado solo en memoria.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Imports `from tests.test_*` rompen `mypy .` | Error módulo duplicado en revisión | Soporte en `herramientas/soporte_tkt013.py` |
| Union Square exige libro P.U. para `#REF!` en E/F | 8562 hallazgos vs catálogo exportado solo | CA-7, variables de entorno |
| `repr(float)` de openpyxl ≠ literal decimal | CA-1 cantidad 16.089000000000002 | ADR-033, materialización futura |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | TC-56 asumía cero tests HDU con historias inactivas; TKT-013 añadió 47 `test_hdu001_esc*` | Baja |
| `convención` | Soporte de pruebas fuera de `tests/` por mypy e `importlib` | Baja |
| `agente` | Reauditoría acotada + corrector cerró mayores en dos ciclos | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Códigos repetidos por obra (PA-T1) | Fuera de alcance del lector | Escalada persona dueña / TKT-015 |
| Clasificación de hallazgos en `importacion_error` | TKT-015 | TKT-015 |
| Lectura APU | Won't de TKT-013 | TKT-014 |
| CRLF en árbol Windows (DOC-F010) | Menor; no bloquea PR | Higiene local o verificador |
| `impl.md` detalle E/M completo (DOC-F009) | Menor | Opcional en cierre documental |

## Pull request

**Título:** `TKT-013 · Lector del catálogo de conceptos`
**Origen:** `agent+human-review`
**Cuerpo:** ver PR en GitHub (generado en `/sdd-completar`).
