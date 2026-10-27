# TKT-008c · Componentes reutilizables

> Hub del ticket. Se lee **primero**, siempre. Es una de las tres partes de [TKT-008](../tkt-008/_index.md).

## Estado

LISTO PARA EJECUTAR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia; sus componentes los usan `HDU-001` a `HDU-007` |
| **Épica / sprint** | Épica 0 · Sprint 1; si el sprint no aguanta, cada componente viaja con su primer consumidor |
| **Puntos** | Talla M; unas 1,430 líneas según el diseño común |
| **Reglas implicadas** | `RN-03`, `RN-07` como contenido; `RN-04`; `RNF-13`, `RNF-16`; regla 1 de `CLAUDE.md` |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R1` a `CA-R3` |
| **Módulos en alcance** | `frontend/src/compartido/componentes/` y `frontend/src/compartido/formularios/` |
| **Capas en alcance** | Cliente: componentes reutilizables |
| **Depende de** | TKT-008a (LISTO PARA EJECUTAR) |
| **Bloquea a** | Las pantallas de la fase 1 que usan un componente |
| **Rama** | `tkt-008c-componentes` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-26 |
| Design | [design.md común](../tkt-008/design.md), filas 11, 12, 13 y su parte de la 15 | `/sdd-disenar` | Aprobado el 2026-10-26 |
| Impl | impl.md | `/sdd-ejecutar` | Pendiente |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-26 | — | `LISTO PARA EJECUTAR` | partición de TKT-008 | Nace de la decisión D-1 del diseño de TKT-008, aprobado por el usuario con D-1 a D-11. Spec repartida: M6, M7, M8 y M10 (su parte); `CA-8` a `CA-12` y `CA-R1` a `CA-R3`. No se ejecuta hasta que TKT-008a esté `ARCHIVADO` o `LISTO PARA PR` |

## Condiciones heredadas de TKT-008a

De la revisión de código de TKT-008a ([delta](../tkt-008a/delta.md#deuda-que-queda-abierta)):

- `normalizarError` no valida `acciones` ni `detalle` (O1). La pantalla de bloqueo, en la fila 11, los trata como posiblemente ausentes: sin `acciones`, solo «Cerrar»; sin `detalle`, ninguna cifra.

## Decisiones registradas

Las de [TKT-008](../tkt-008/_index.md#decisiones-registradas), que valen para las tres partes.
