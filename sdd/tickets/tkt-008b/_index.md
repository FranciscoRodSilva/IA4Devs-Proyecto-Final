# TKT-008b · Inicio de sesión, armazón por rol y humo

> Hub del ticket. Se lee **primero**, siempre. Es una de las tres partes de [TKT-008](../tkt-008/_index.md).

## Estado

ARCHIVADO

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
| **Depende de** | TKT-008a (ARCHIVADO) |
| **Bloquea a** | Las pantallas de la fase 1 |
| **Rama** | `tkt-008b-sesion-armazon` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-26 |
| Design | [design.md común](../tkt-008/design.md), filas 8, 9, 10, 14, 16 y su parte de la 15 | `/sdd-disenar` | Aprobado el 2026-10-26 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-27; verificado en `/sdd-revisar` el 2026-10-27 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-27 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-26 | — | `LISTO PARA EJECUTAR` | partición de TKT-008 | Nace de la decisión D-1 del diseño de TKT-008, aprobado por el usuario con D-1 a D-11. Spec repartida: M1 (enrutado), M3 (sesión), M4, M5, M10 (su parte) y S1; `CA-1` esc. 2 y 3, `CA-3` esc. 3, `CA-5`, `CA-6`, `CA-7`, `CA-14` y `CA-R1` a `CA-R4`. No se ejecuta hasta que TKT-008a esté `ARCHIVADO` o `LISTO PARA PR` |
| 2026-10-27 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas 8, 9, 10, 14, 16 y la parte de la 15 con MT-15 a MT-23, en la rama `tkt-008b-sesion-armazon`, apilada sobre `tkt-008a-andamiaje-cliente`. Cliente: 133 pruebas de Vitest y 3 de Playwright contra el backend real, en dos corridas seguidas; backend intacto con 1138 pruebas. Mutación MT-15 a MT-23 sin supervivientes. Condiciones heredadas de 008a cumplidas. Se instaló el Chromium de Playwright, con permiso del usuario. `auditor-arquitectura`: `REQUIERE CAMBIOS` con un Mayor (F201) y dos ciclos de corrección; la verificación en copia limpia (F203) falló primero porque `uv` eligió Python 3.15 y `pyyaml` no compila, y el usuario decidió fijar `--python 3.14` en la guía sin tocar `backend/`; después pasó completa. Reauditoría `APROBADO`. Sin commit |
| 2026-10-27 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el orquestador: 154 pruebas del cliente, humo 3 de 3, 12 de `tools/`, `lint`, `typecheck`, `build`, `tipos:verificar` y `verificar_docs` limpios; backend intacto con 1138 pruebas, `ruff`, `mypy`, 15 contratos y `verificar_float`. Cuatro auditorías en paralelo: seguridad `APROBADO` con cinco Bajas; arquitectura (pasada independiente), código y documentación `REQUIERE CAMBIOS`, con tres Mayores de código (ramas sin test tras iniciar sesión y en la cuenta atrás) y dos de documentación. Dos ciclos de corrección, tester en rojo y corrector en verde: cerraron, entre otros, que el token CSRF sobrevivía a una sesión terminada, que la caché del usuario anterior sobrevivía a un nuevo inicio de sesión, que la cuenta atrás contaba ticks y no reloj, y que la guarda de la siembra no tenía test ni contemplaba `PGHOSTADDR` ni `PGSERVICE`. Las cuatro quedaron `APROBADO`. No toca `docs/api/openapi.yaml` ni `backend/`. Queda para quien aprueba si `--python 3.14` merece ADR. Sin commit |
| 2026-10-27 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | `delta.md` escrito; la auditoría de documentación del cierre devolvió cuatro Menores (el recuento de pruebas nuevas, la relación entre `reiniciarToken` y `terminarSesion`, una cita textual y la fila de modelo), corregidos aquí; `verificar_docs` y `extraer_mermaid` en verde. Seis observaciones en `_evolucion.md`; `meta-sdd` sube dos patrones y abre dos nuevos que cruzan el umbral (el verde no se escribe de uno en uno y la mutación se limita a la lista del diseño) y recomienda aprobar primero una mutación exploratoria. Commit local en la rama del ticket, apilada sobre la de TKT-008a; el PR lo abre una persona. Queda para quien aprueba si `--python 3.14` merece ADR |

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

## Tickets futuros sugeridos

La deuda de este ticket está en [delta.md](delta.md#deuda-que-queda-abierta): fijar el intérprete de Python en `backend/` y que el pipeline de `tools/` instale `uv` (TKT-009), el umbral del `429` frente al humo (TKT-057), y un ticket propio de herramientas para que `verificar_docs.py` ignore los bloques de código.
