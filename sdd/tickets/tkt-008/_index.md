# TKT-008 · Esqueleto del frontend y cliente de API

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO · partido en TKT-008a, TKT-008b y TKT-008c

El estado vive en los tres hermanos: cada uno lleva el suyo en su `_index.md`.

> **Ticket paraguas.** No se ejecuta como un solo ticket: por D-1 se parte en tres hermanos, registrados en `docs/05-tickets-trabajo.md` y con la spec repartida. Se cerró al archivarse los tres.
>
> | Parte | Hub | Depende de |
> |---|---|---|
> | TKT-008a · Andamiaje, tipos, cliente de API y dinero | [tkt-008a](../tkt-008a/_index.md) | TKT-005, TKT-006 |
> | TKT-008b · Inicio de sesión, armazón por rol y humo | [tkt-008b](../tkt-008b/_index.md) | TKT-008a |
> | TKT-008c · Componentes reutilizables | [tkt-008c](../tkt-008c/_index.md) | TKT-008a |
>
> Este directorio guarda la spec y el diseño **comunes**: las tres partes los leen de aquí.

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia; habilita los componentes que usan `HDU-001`, `HDU-003`, `HDU-004`, `HDU-005` y `HDU-007`, y la pantalla de bloqueo de `HDU-001`, `HDU-002`, `HDU-004`, `HDU-005` y `HDU-006`, que implementan los tickets consumidores |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M |
| **Reglas implicadas** | Ninguna `RN-xx` se implementa en el cliente: el cliente nunca evalúa una regla. `RN-03`, `RN-04` y `RN-07` aparecen como contenido; `RNF-01`, `RNF-02`, `RNF-03`, `RNF-04`, `RNF-05`, `RNF-13` y `RNF-16` fijan su comportamiento |
| **Invariantes en riesgo** | Ninguna tabla. Regresión sobre el esqueleto de TKT-001, el backend intacto, la cookie ilegible y el dinero como cadena: `CA-R1` a `CA-R4` |
| **Módulos en alcance** | `frontend/` entero; `CLAUDE.md` y `docs/arranque-local.md`. Ningún archivo de `backend/` |
| **Capas en alcance** | Cliente: aplicación, enrutado, cliente de API, tipos generados, componentes reutilizables, pantalla de inicio de sesión y armazón |
| **Depende de** | TKT-005 (ARCHIVADO) · TKT-006 (ARCHIVADO) |
| **Bloquea a** | TKT-009, TKT-061, TKT-063 y toda pantalla de la fase 1 |
| **Rama** | `tkt-008a-andamiaje-cliente`, `tkt-008b-sesion-armazon` y `tkt-008c-componentes` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-26 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-26 |
| Impl | — | `/sdd-ejecutar` | No aplica: lo ejecutaron los tres hermanos, cada uno con su `impl.md` |
| Delta | — | `/sdd-completar` | No aplica: lo escribió cada hermano en su `delta.md` |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-26 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M10, más S1 (humo de Playwright). 13 criterios `[M]`, uno `[S]` y cuatro de regresión, con al menos un rechazo en cada criterio. Pasada adversarial hecha por el orquestador con la skill `abogado-del-diablo`: cinco objeciones acogidas. INVEST con una reserva (talla) |
| 2026-10-26 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño de `arquitecto-tecnico` (opus) con 16 filas, unas 4,600 líneas escritas a mano —muy por encima del tope de ~400—, 92 casos de prueba más los de regresión y 32 mutantes; sin ADR. `revisor-impacto` (sonnet) devolvió `DISEÑO INCOMPLETO` con tres hallazgos Mayores y cinco Menores, sin frontera cruzada; la pasada adversarial del orquestador añadió dos objeciones (usuarios del humo y tamaño). El arquitecto corrigió los diez en el mismo diseño. La fila 16 toca `tools/`, `docs/05-tickets-trabajo.md` y `docs/06-stack-tecnologico.md`, fuera de los módulos de la spec: se aprueba en el gate. Espera decisiones D-1 a D-11, con D-1 proponiendo partir el ticket |
| 2026-10-26 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño con todas las recomendaciones, D-1 a D-11, y aceptó que la fila 16 toque `tools/`, `docs/05-tickets-trabajo.md` y `docs/06-stack-tecnologico.md`. Por D-1 se ejecuta como tres tickets hermanos, TKT-008a, TKT-008b y TKT-008c; falta registrarlos y repartir la spec antes de ejecutar |
| 2026-10-26 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | partición | Los tres tickets quedan registrados en `docs/05-tickets-trabajo.md`, como subsecciones de TKT-008, y cada uno tiene su `_index.md` y su `spec.md`, que reparten Must, criterios, filas del diseño y mutantes sin redactar criterios nuevos. TKT-008 queda como paraguas |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `ARCHIVADO` | `/sdd-completar` | Cierre del paraguas: TKT-008a, TKT-008b y TKT-008c están `ARCHIVADO`, cada uno con su delta. El paraguas no tiene impl ni delta propios |

## Decisiones registradas

- 2026-10-26 · **Tipos del contrato de error.** Los del servidor salen del OpenAPI publicado; los del contrato de error, del borrador, como provisionales ([API §6.2](../../../docs/07-especificacion-api.md#62-para-generar-los-tipos-del-cliente)), porque FastAPI todavía no publica esos esquemas. Decidió el usuario.
- 2026-10-26 · **Comprobación de tipos.** Se recorta a un comando del proyecto que falla si el archivo difiere. El enganche a CI es de TKT-009 y la comparación con el borrador, de TKT-061. Decidió el usuario.
- 2026-10-26 · **Navegación.** La tabla de secciones por rol del wireframe §2 vive en el cliente, con una ruta marcador por sección. Sin selector de obra ni contador de autorizaciones. Decidió el usuario.
- 2026-10-26 · **Playwright.** Entra como Should, con un recorrido de humo de inicio y cierre de sesión. Decidió el usuario.

- 2026-10-26 · **Diseño aprobado con D-1 a D-11.** Se parte en tres tickets hermanos con este diseño como plan común:
  - **TKT-008a**: andamiaje, tipos, cliente y dinero; filas 1 a 7.
  - **TKT-008b**: inicio de sesión, armazón, humo y documentación; filas 8, 9, 10, 14, la 16 y su parte de la 15.
  - **TKT-008c**: los tres componentes; filas 11 a 13 y su parte de la 15.

  TKT-008b y TKT-008c dependen de TKT-008a y no entre sí. Además se aprueban MSW como doble del servidor y la prohibición del `+` unario. El humo corre con un usuario fijo sobre la base de Compose, y la exportación del OpenAPI se hace con `uv` sin crear archivos en `backend/`. Decidió el usuario.

## Tickets futuros sugeridos

- **Publicar los esquemas de error en FastAPI** con `responses=` en cada ruta, para que el OpenAPI publicado declare `ErrorConflicto`, `ErrorValidacion`, `ErrorSesion` y los demás, y retirar los tipos provisionales del cliente. Debe llegar antes de TKT-061 (`PA-T1`).
- **Admitir en el verificador de escenarios de TKT-009** los tests de un ticket de fundación nombrados por criterio `CA-n` (`PA-T4`).
- **Prueba de inicio de sesión contra el servidor real** para el `429` y el `403` `ORIGEN_NO_VERIFICADO`, cuando TKT-057 los produzca (`PA-T6`).
