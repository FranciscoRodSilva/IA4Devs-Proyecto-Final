# TKT-008a · Andamiaje, tipos, cliente de API y dinero

> Hub del ticket. Se lee **primero**, siempre. Es una de las tres partes de [TKT-008](../tkt-008/_index.md).

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M; unas 1,570 líneas según el diseño común |
| **Reglas implicadas** | `RNF-05`, `RNF-13`; reglas 1, 9 y 10 de `CLAUDE.md` |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R1` a `CA-R3` |
| **Módulos en alcance** | `frontend/` (andamiaje, `src/api/`, `src/compartido/dinero/`, `scripts/`), `.gitignore` |
| **Capas en alcance** | Cliente: configuración, tipos generados, cliente de API, dinero |
| **Depende de** | TKT-005 (ARCHIVADO) · TKT-006 (ARCHIVADO) |
| **Bloquea a** | TKT-008b, TKT-008c |
| **Rama** | `tkt-008a-andamiaje-cliente` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-26 |
| Design | [design.md común](../tkt-008/design.md), filas 1 a 7 | `/sdd-disenar` | Aprobado el 2026-10-26 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-26; verificado en `/sdd-revisar` el 2026-10-27 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-27 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-26 | — | `LISTO PARA EJECUTAR` | partición de TKT-008 | Nace de la decisión D-1 del diseño de TKT-008, aprobado por el usuario con D-1 a D-11. Spec repartida: M1 (andamiaje), M2, M3 (cliente), M9 y M10 (su parte); `CA-1` esc. 1, `CA-2`, `CA-3` esc. 1 y 2, `CA-4`, `CA-13` y `CA-R1` a `CA-R3`. Filas 1 a 7 del diseño común |
| 2026-10-26 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas 1 a 7 ejecutadas en la rama `tkt-008a-andamiaje-cliente`, que sale de `Produccion` por decisión del usuario. Cliente: 7 archivos y 50 tests en verde, con `lint`, `typecheck`, `build` y `tipos:verificar` limpios. Backend intacto: 1138 tests en verde. Mutación MT-1 a MT-14 sin supervivientes (MT-6 se mató con TC-M6) y tres tests nuevos que cubren huecos (TC-H1, TC-H2, TC-M6). `auditor-arquitectura`: `REQUIERE CAMBIOS` con seis Menores; un ciclo de corrección (que destapó que el cliente enviaba `X-CSRF-Token: undefined`) y reauditoría `APROBADO`. Filas 1, 3 y 7 `⚠ Ajustado`; el resto `✓ Hecho`. Sin commit |
| 2026-10-27 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el orquestador: 78 tests del cliente en verde, `lint`, `typecheck`, `build`, `tipos:verificar` y `verificar_docs` limpios; backend intacto con 1138 tests en verde. Cuatro auditorías en paralelo:<br>• Arquitectura, pasada independiente: dos Menores.<br>• Código: un Mayor (`generar` sin test) y cinco Menores.<br>• Seguridad: `APROBADO` con cuatro Bajas.<br>• Documentación: tres Mayores y dos Menores, porque 008a no documentaba lo que entrega.<br>El usuario decidió que 008a documente su parte (`CLAUDE.md`, `docs/arranque-local.md`, `conv-frontend-react`), que sale de la fila 16 de 008b. El ciclo de corrección siguió el orden tester en rojo, corrector en verde; destapó que `RED` se aplicaba a cualquier `TypeError` y que un `Decimal` no finito se pintaba como `$∞`. Una segunda pasada de documentación cerró un supuesto sin marcar (Safari, `PA-T7`) y finales CRLF. Las cuatro auditorías quedaron en `APROBADO`. D009 (¿merece ADR los tipos de error provisionales?) queda para la persona que aprueba. La reauditoría de código se cortó por el límite de uso y se reanudó. Sin commit |
| 2026-10-27 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | `delta.md` escrito; la auditoría de documentación del cierre devolvió un Mayor (un identificador que solo vivía en el chat) y tres Menores (la sección de `docs/06` era §5.1 y no §5.4, una afirmación de ESLint más fuerte que la regla, y el `e2e` sin configuración), corregidos aquí; `verificar_docs` y `extraer_mermaid` en verde. Siete observaciones en `_evolucion.md`; `meta-sdd` sube de conteo cuatro patrones (tamaño del diseño, codificación en Windows, límite de uso, entradas hostiles) y deja sus propuestas en `Propuesto`. Commit local en la rama del ticket; el PR lo abre una persona. Queda para quien aprueba: si los tipos de error provisionales merecen ADR |

## Decisiones registradas

Las de [TKT-008](../tkt-008/_index.md#decisiones-registradas), que valen para las tres partes, más:

- 2026-10-26 · La rama sale de `Produccion` y no de `feature/entrega-2-JFRS`. Decidió el usuario.
- 2026-10-27 · TKT-008a documenta lo que entrega (`CLAUDE.md`, `docs/arranque-local.md`, `conv-frontend-react`), que sale de la fila 16 de TKT-008b. Decidió el usuario.

## Tickets futuros sugeridos

La deuda de este ticket está en [delta.md](delta.md#deuda-que-queda-abierta), repartida entre TKT-008b, TKT-008c, TKT-057 y el ticket ya sugerido en [TKT-008](../tkt-008/_index.md#tickets-futuros-sugeridos) para publicar los esquemas de error en FastAPI. TKT-008b la recoge en sus «Condiciones heredadas».
