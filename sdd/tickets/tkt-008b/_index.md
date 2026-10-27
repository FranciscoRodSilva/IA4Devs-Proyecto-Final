# TKT-008b · Inicio de sesión, armazón por rol y humo

> Hub del ticket. Se lee **primero**, siempre. Es una de las tres partes de [TKT-008](../tkt-008/_index.md).

## Estado

LISTO PARA EJECUTAR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M; unas 1,600 líneas según el diseño común |
| **Reglas implicadas** | `RNF-01`, `RNF-02`, `RNF-03`, `RNF-04`, `RNF-05`; reglas 9 y 10 de `CLAUDE.md` |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R1` a `CA-R4` |
| **Módulos en alcance** | `frontend/` (`src/app/`, `src/modulos/`, `e2e/`), `CLAUDE.md` y `docs/arranque-local.md` (solo lo que la fila 16 aún no cubre), `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `tools/verificar_docs.py` y `tools/tests/` |
| **Capas en alcance** | Cliente: enrutado, inicio de sesión, armazón; humo de Playwright; documentación |
| **Depende de** | TKT-008a (LISTO PARA EJECUTAR) |
| **Bloquea a** | Las pantallas de la fase 1 |
| **Rama** | `tkt-008b-sesion-armazon` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-26 |
| Design | [design.md común](../tkt-008/design.md), filas 8, 9, 10, 14, 16 y su parte de la 15 | `/sdd-disenar` | Aprobado el 2026-10-26 |
| Impl | impl.md | `/sdd-ejecutar` | Pendiente |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-26 | — | `LISTO PARA EJECUTAR` | partición de TKT-008 | Nace de la decisión D-1 del diseño de TKT-008, aprobado por el usuario con D-1 a D-11. Spec repartida: M1 (enrutado), M3 (sesión), M4, M5, M10 (su parte) y S1; `CA-1` esc. 2 y 3, `CA-3` esc. 3, `CA-5`, `CA-6`, `CA-7`, `CA-14` y `CA-R1` a `CA-R4`. No se ejecuta hasta que TKT-008a esté `ARCHIVADO` o `LISTO PARA PR` |

## Condiciones heredadas de TKT-008a

De la reauditoría de arquitectura de TKT-008a ([impl](../tkt-008a/impl.md#auditorías)):

- La fila 9 importa `src/index.css` desde `main.tsx`, y su verificación incluye `npm run build` con el CSS generado.
- Las filas 9 y 10 dan su primera prueba a `sesionOptions`, `ProveedorApi` y `useApi` (deuda F006).
- Las pantallas no muestran `GENERICO` con `estado: 0` como un código HTTP (O-6).
- Un test comprueba que `npm run tipos:verificar` no escribe archivos (N-1 de la revisión de código).
- La frase de invariantes de la spec de 008b añade `tools/tests/` a lo que este ticket modifica (D013).
- Reasignación del 2026-10-26: los cambios de `CLAUDE.md` (bloque de comandos de frontend), de `docs/arranque-local.md` (sección «Frontend» y tabla «Lo que todavía no arranca») y de `conv-frontend-react` (D-11) se hicieron en TKT-008a por decisión del usuario. La fila 16 conserva el resto: `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `tools/`, el humo, la línea «Verificado en copia limpia» y lo que añada el armazón.
- La fila 16 registra en `docs/06-stack-tecnologico.md` la elección de primitivas de shadcn (`base-nova`, `@base-ui/react`, `cn`) y matiza que la regla de conversión numérica no cubre las coerciones aritméticas (F001).

## Decisiones registradas

Las de [TKT-008](../tkt-008/_index.md#decisiones-registradas), que valen para las tres partes.
