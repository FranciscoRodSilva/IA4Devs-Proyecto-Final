# TKT-005 · Contrato de error de regla de negocio

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (asimilado a Funcionalidad sin criterios de negocio) |
| **Historia** | Épica 0 · Fundación |
| **Épica / sprint** | Épica 0 · Sprint 0 |
| **Puntos** | Talla S en el ticket; riesgo de subir a M por `PA-T3` (ubicación de la excepción y de la raíz de composición) |
| **Reglas implicadas** | Ninguna `RN-xx` se implementa. `RN-03`, `RN-02` y `RN-04` aparecen como ejemplos y como razón del catálogo cerrado; `RNF-13` y `RNF-16` fijan la correlación y la forma `CONCURRENCIA` |
| **Invariantes en riesgo** | Ninguno de los 38 del modelo de datos. Regresión sobre TKT-001 a TKT-004: `CA-R1` a `CA-R7`. Reglas 1, 2, 11 y la convención de errores de `CLAUDE.md` |
| **Módulos en alcance** | Ninguno de negocio. Aplicación web, excepción única, manejador global y registro, ubicados donde decida el diseño (`PA-T3`) |
| **Capas en alcance** | aplicación (la excepción la lanza el caso de uso) · api (manejador, fábrica de la aplicación) · configuración de herramientas; sin dominio ni infraestructura de base de datos |
| **Depende de** | TKT-002 (estado: ARCHIVADO). Aprovecha `serializar()` de TKT-004 (ARCHIVADO) |
| **Rama** | `tkt-005-contrato-de-error` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-20 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-21 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-21; verificado en `/sdd-revisar` |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-21 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-20 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M8 más M9, consecuencia documental. 13 criterios `[M]`, dos `[S]` y siete de regresión |
| 2026-10-21 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño con 9 filas, unas 2,100 líneas (supera el tope de ~400; se propone partir en entregas A y B, como TKT-004), ADR-022 propuesto, 24 mutantes. `revisor-impacto` ausente: el impacto lo hizo el arquitecto por sustitución. Espera decisiones D-1 a D-8 |
| 2026-10-21 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario resolvió D-1 a D-8 en el gate del diseño, una por una: todas las recomendaciones |
| 2026-10-21 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entregas A y B ejecutadas (filas 1 a 9): 692 pruebas en verde con Docker (245 propias), 25 mutantes en rojo, 15 contratos. Auditorías: arquitectura y seguridad `REQUIERE CAMBIOS` en la primera pasada; un ciclo de corrección y reauditoría con `APROBADO` en seguridad y un Menor documental de arquitectura resuelto (`F005`). Sin commit |
| 2026-10-21 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el revisor: 692 pruebas en verde con Docker (245 propias), `ruff`, `mypy`, 15 contratos y `verificar_float` limpios. Reauditorías de arquitectura: `F006` (Mayor, contrato: el usuario aprobó que `REINTENTAR` no se filtre por rol y se enmendó `docs/api/openapi.yaml`) y `F007` (Mayor) más `F008` a `F015` (Menores), resueltos en el ciclo 2 con `APROBADO` final; seguridad `APROBADO`. Los 15 criterios y los 7 de regresión cumplidos. **El PR toca `docs/api/openapi.yaml`: señalarlo a la persona que aprueba** |
| 2026-10-21 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos (seis filas nuevas en `_evolucion.md`, y los patrones `agente`, `herramienta` y `comando` suben a 6, 5 y 4 repeticiones); `verificar_docs.py`, `extraer_mermaid.py` y los tests de `tools/` sin problemas; `auditor-docs` y `meta-sdd` ausentes, sustituidos por los verificadores y por el orquestador; commit local; el PR lo abre una persona. **El PR toca `docs/api/openapi.yaml`** |

## Decisiones registradas

- 2026-10-20 · El usuario validó el Must propuesto: todo lo que pide el ticket más la aplicación servible. El `500` genérico entra como Should y sustituir el `HTTPValidationError` del OpenAPI publicado es de TKT-061. Decidió el usuario.
- 2026-10-20 · La excepción de rechazo de regla la lanza el **caso de uso**, a partir del resultado de la función de regla; la función de `dominio/` sigue pura. Cierra el `(asumido)` de `conv-dominio-python` §4. Decidió el usuario.
- 2026-10-20 · El filtrado de acciones por rol recibe los roles de quien llama y los que exige cada acción como datos; TKT-006 conecta la sesión real. Decidió el usuario.
- 2026-10-20 · Una ruta inexistente responde `NO_ENCONTRADO` y un error no controlado responde `500` con cuerpo mínimo y `correlacion_id`, ambos `(asumido)`. Decidió el usuario.
- 2026-10-20 · Hallazgo documental sin decisión humana todavía: los motivos de `PERMISO` difieren entre arquitectura §7.3, API §3.1, API §7 y el borrador (`PA-T8`). La spec sigue al borrador; se confirma en el gate del diseño.
- 2026-10-21 · Gate del diseño, resuelto por el usuario: **D-1** dos entregas dentro del ticket, A (contrato puro) y B (servidor); **D-2** `contrato_error` y `servidor` fuera de `root_packages`, vigilados por pruebas; **D-3** `CA-11` esc. 3 se sustituye por TC-75 y la prueba contra la tabla `bitacora` es de TKT-007; **D-4** el `TypeError` de un validador queda como convención documentada; **D-5** manda el borrador en los motivos de `PERMISO` (cierra `PA-T8`); **D-6** el servidor siempre genera el identificador de correlación (cierra `PA-T7`); **D-7** el `500` no lleva `tipo` hasta que el borrador lo declare (cierra `PA-T5`); **D-8** las filas 2, 3, 5 y 6 se ejecutan por sustitución de los agentes ausentes.

- 2026-10-21 · `/sdd-revisar`, resuelto por el usuario: aprobó que `REINTENTAR` de una `CONCURRENCIA` no se filtre por rol y que el borrador (`docs/api/openapi.yaml`) y la especificación de la API se enmienden en este mismo PR (`F006`). **El PR toca `docs/api/openapi.yaml`: señalarlo a la persona que aprueba.**

## Tickets futuros sugeridos

Todo lo que salió del alcance está en «Deuda que queda abierta» de [`delta.md`](delta.md), con su ticket sugerido. Resumen:

- **Origen de los roles que exige cada acción** (`PA-T2`): un lugar único del que un caso de uso lea qué rol puede ejecutar cada `clave` de acción, por ejemplo derivado de `x-roles` del borrador. Hasta entonces, cada caso de uso lo declara al lanzar.
- **Noveno `tipo` o cuerpo oficial del `500`** (`PA-T5`): corregir el borrador y API §3 para que el error no controlado tenga forma declarada.
- **`405` y otros errores de enrutado** (`Method Not Allowed`) con su `tipo`.
- **Propagación de un identificador de correlación del cliente** (`PA-T7`), si TKT-008 la necesita.
