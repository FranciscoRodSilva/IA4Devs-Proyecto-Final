# TKT-008c · Componentes reutilizables

> Hub del ticket. Se lee **primero**, siempre. Es una de las tres partes de [TKT-008](../tkt-008/_index.md).

## Estado

ARCHIVADO

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
| **Depende de** | TKT-008a (ARCHIVADO) |
| **Bloquea a** | Las pantallas de la fase 1 que usan un componente |
| **Rama** | `tkt-008c-componentes` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-26 |
| Design | [design.md común](../tkt-008/design.md), filas 11, 12, 13 y su parte de la 15 | `/sdd-disenar` | Aprobado el 2026-10-26 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-27 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-28 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-26 | — | `LISTO PARA EJECUTAR` | partición de TKT-008 | Nace de la decisión D-1 del diseño de TKT-008, aprobado por el usuario con D-1 a D-11. Spec repartida: M6, M7, M8 y M10 (su parte); `CA-8` a `CA-12` y `CA-R1` a `CA-R3`. No se ejecuta hasta que TKT-008a esté `ARCHIVADO` o `LISTO PARA PR` |
| 2026-10-27 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas 11, 12, 13 y la parte de la 15 en verde: 192 pruebas de Vitest y el humo de Playwright; ningún mutante de MT-24 a MT-32 sobrevive. Incluye el ajuste de marca que pidió el usuario al lanzar la ejecución (logo de AP Buildings y paleta derivada), solo de presentación. `auditor-arquitectura` APROBADO con cuatro observaciones |
| 2026-10-27 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite ejecutada de nuevo: 214 pruebas de Vitest y 1138 de `pytest`, linters limpios. Arquitectura, código, seguridad y documentación en APROBADO tras tres ciclos de corrección (dos Mayores de código, la espera del reintento que no se reiniciaba y el ayudante que descartaba los rechazos; tres Mayores de documentación, D1, D2 y F005). Se abren `PA-T13` a `PA-T17` en la spec común. La excepción de non-goals del ajuste de marca, de `dialog.tsx` y de un comentario de `cliente.test.ts` queda registrada en la spec |
| 2026-10-28 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta escrito; `auditor-docs` APROBADO sobre el cierre tras corregir los hallazgos de redacción con su texto literal; siete observaciones en `sdd/_evolucion.md` y `meta-sdd` actualizó tres patrones sin crear ninguno nuevo. Commit en la rama `tkt-008c-componentes`; el PR lo abre una persona a mano, con base `Produccion` |

## Condiciones heredadas de TKT-008a

De la revisión de código de TKT-008a ([delta](../tkt-008a/delta.md#deuda-que-queda-abierta)):

- `normalizarError` no valida `acciones` ni `detalle` (O1). La pantalla de bloqueo, en la fila 11, los trata como posiblemente ausentes: sin `acciones`, solo «Cerrar»; sin `detalle`, ninguna cifra.

## Decisiones registradas

Las de [TKT-008](../tkt-008/_index.md#decisiones-registradas), que valen para las tres partes.
