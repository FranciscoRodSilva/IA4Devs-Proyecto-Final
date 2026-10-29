# TKT-009 · Pipeline de integración continua

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO · partido en TKT-009a, TKT-009b, TKT-009c y TKT-009d

> **Ticket paraguas.** No se ejecuta como un solo ticket: por la decisión del gate de diseño se parte en cuatro hermanos, registrados en `docs/05-tickets-trabajo.md` y con la spec repartida. Se cerró al archivarse los cuatro. El orden de fusión es fijo: **a → c → b → d**.
>
> | Parte | Hub | Depende de |
> |---|---|---|
> | TKT-009a · Pipeline de pruebas y fronteras | [tkt-009a](../tkt-009a/_index.md) | TKT-002, TKT-008a, TKT-008b, TKT-008c |
> | TKT-009c · Verificador de escenarios | [tkt-009c](../tkt-009c/_index.md) | TKT-009a |
> | TKT-009b · Cadena de suministro | [tkt-009b](../tkt-009b/_index.md) | TKT-009a |
> | TKT-009d · Calidad de documentación | [tkt-009d](../tkt-009d/_index.md) | TKT-009a |
>
> Este directorio guarda la spec y el diseño **comunes**: las cuatro partes los leen de aquí.

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla S en el backlog; con reservas de que crezca a M por la línea base de documentación y el verificador de escenarios |
| **Reglas implicadas** | `RNF-07`, `RNF-08`; reglas 1, 2 y 3 de `CLAUDE.md`; [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md). Ninguna `RN-xx` |
| **Invariantes en riesgo** | Ninguna tabla. Regresión sobre la suite contra PostgreSQL, los 15 contratos de `import-linter`, la ausencia de secretos y las suites existentes: `CA-R1` a `CA-R4` |
| **Módulos en alcance** | `.github/`, `tools/`, configuración de documentación, `backend/pyproject.toml` (dependencias de desarrollo) y las marcas «desde TKT-009» de la documentación. Ningún archivo de `backend/cimenta/` ni de `frontend/src/` |
| **Capas en alcance** | Entrega continua y herramientas. Ninguna capa de la aplicación |
| **Depende de** | TKT-002 (ARCHIVADO) · TKT-008a, TKT-008b y TKT-008c (ARCHIVADOS); el paraguas TKT-008 sigue «EN CURSO» |
| **Bloquea a** | TKT-061, TKT-062 y los tickets que dependen del pipeline |
| **Rama** | `tkt-009a-pipeline-pruebas` (a) · `tkt-009c-verificador-escenarios` (c) · `tkt-009b-cadena-suministro` (b) · `tkt-009d-calidad-documental` (d) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-28 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-28 |
| Impl | — | `/sdd-ejecutar` | No aplica: lo ejecutaron los cuatro hermanos, cada uno con su `impl.md` |
| Delta | — | `/sdd-completar` | No aplica: lo escribió cada hermano en su `delta.md` |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M12, con S1 (`mermaid-cli`). 16 criterios con rechazo más cuatro de regresión. Pasada adversarial hecha por el orquestador con `abogado-del-diablo`: cinco objeciones acogidas. INVEST con tres reservas y ningún fallo |
| 2026-10-28 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño de `arquitecto-tecnico` (opus): 29 filas en cuatro partes y unas 1,230 líneas a mano, tres veces el tope de ~400, por lo que propone partir. `revisor-impacto` (sonnet) devolvió `DISEÑO INCOMPLETO` con tres hallazgos Mayores y nueve Menores, sin frontera cruzada; el arquitecto corrigió los doce. La pasada adversarial del orquestador añadió dos objeciones, ya aplicadas. Tres ADR nuevos previstos. Espera decisiones del gate |
| 2026-10-28 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño con todas las recomendaciones: partición en cuatro tickets hermanos con orden de fusión a → c → b → d, las dos interpretaciones señaladas en el gate (`CA-11` esc. 3 y `CA-13` esc. 1) y `Vale` sin estilo Microsoft. Falta registrar los hermanos y repartir la spec antes de ejecutar |
| 2026-10-28 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | partición | Los cuatro tickets quedan registrados en `docs/05-tickets-trabajo.md`, como subsecciones de TKT-009, y cada uno tiene su `_index.md` y su `spec.md`, que reparten Must, criterios y filas del diseño sin redactar criterios nuevos. TKT-009 queda como paraguas |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `ARCHIVADO` | `/sdd-completar` | Cierre del paraguas: TKT-009a, TKT-009b, TKT-009c y TKT-009d están `ARCHIVADO` y fusionados en `Produccion` en el orden a → c → b → d. El paraguas no tiene impl ni delta propios |

## Decisiones registradas

- 2026-10-28 · **MinIO fuera del sprint 1.** El trabajo de backend levanta solo PostgreSQL con testcontainers. MinIO llega con TKT-059, que no depende de TKT-009; se anota la desviación del criterio original. Decidió el usuario.
- 2026-10-28 · **`Vale` como error en CI.** Se configuran `Vale` y `markdownlint` y se limpia en este ticket la línea base de avisos; aviso en local, error en CI. Decidió el usuario.
- 2026-10-28 · **Deuda heredada fuera.** La segunda puerta `__init__.py`, los contratos para `tests/` y `servidor/`, `interrogate`, el *digest* de Compose y los tests lentos pasan a tickets futuros. `mermaid-cli` entra como Should. Decidió el usuario.
- 2026-10-28 · **Verificador solo de escenarios HDU.** Admite los nombres de fundación sin contarlos huérfanos, ignora los tests sin prefijo y no renombra tests archivados. Decidió el usuario.

- 2026-10-28 · **Diseño aprobado.** Se parte en cuatro tickets hermanos con este diseño como plan común, en el orden de fusión **a → c → b → d**:
  - **TKT-009a**: pruebas y fronteras; M1–M4, M6, M9; filas A0 a A8.
  - **TKT-009c**: verificador de escenarios; M5; filas C1 a C6.
  - **TKT-009b**: cadena de suministro; M7, M8; filas B1 a B7.
  - **TKT-009d**: calidad documental; M10, M11, S1; filas D1 a D7.

  M12 se reparte en las cuatro. Las dos interpretaciones del diseño valen: no hay archivo de excepción para `.env.example` y «sin avisos» aplica a `markdownlint-cli2`, `Vale` y `lychee`. Quedan a tu cargo los ajustes del repositorio de la fila B5 y abrir a mano los PR de ensayo. Decidió el usuario.

## Tickets futuros sugeridos

- **Un `it("hdu…")` dentro de un `describe.skip` cuenta como cobertura; `it.skip(...)` no**: el verificador debería excluir los bloques saltados (objeción 8 del diseño).

- **Deuda de `import-linter`:** segunda puerta `cimenta/<m>/__init__.py`, contratos para `tests/`, `servidor/` y `contrato_error`, y un verificador de que arquitectura §5 y los contratos dicen el mismo grafo.
- **`interrogate`** (cobertura de docstrings), previsto en convenciones y stack.
- **Fijar la imagen de Compose por *digest*** y marcar como lentos TC-51 y TC-52.
- **Política de versiones de `eslint` y `@eslint/js`.**
- **Anotar en TKT-059** que añade el servicio y los tests de MinIO al trabajo de backend.
