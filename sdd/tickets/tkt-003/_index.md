# TKT-003 · PostgreSQL, migraciones y esquema de identidad

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (asimilado a Funcionalidad sin criterios de negocio) |
| **Historia** | Épica 0 · Fundación |
| **Épica / sprint** | Épica 0 · Sprint 0 |
| **Puntos** | Talla M |
| **Reglas implicadas** | Ninguna `RN-xx`. Sostiene `RNF-09`, `RNF-16`, `RNF-07`, `RNF-04` y `RNF-01`; ADR-002, ADR-013 y ADR-014 |
| **Invariantes en riesgo** | Nacen con el ticket: 20 y 21. Dependen de sus `ALTER DEFAULT PRIVILEGES`: 10, 14 y 30 (de TKT-007, TKT-011 y `almacen`). Garantías de TKT-001 y TKT-002 que deben sobrevivir: `CA-R1` a `CA-R6` |
| **Módulos en alcance** | `identidad` (tablas) |
| **Capas en alcance** | infraestructura (migraciones, Compose, pruebas) y configuración; sin dominio, aplicación ni api |
| **Depende de** | TKT-002 (estado: ARCHIVADO, integrado en `Produccion`) |
| **Rama** | `tkt-003-postgresql-identidad` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-17 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-17 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-18; entregas A y B |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-18 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-17 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M9 más M10, consecuencia documental |
| 2026-10-17 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito con 11 filas y 83 casos de prueba; revisión de impacto independiente aplicada. Supera el tope de ~400 líneas (unas 1,450); espera decisiones D-1 a D-9 |
| 2026-10-17 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario resolvió D-1 a D-9 en el gate del diseño |
| 2026-10-18 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | `/sdd-ejecutar` | Entrega A ejecutada (filas 1, 2, 3, 4, 7 y 9-A): 24 pruebas en verde, 14 mutantes del diseño y 13 añadidos, sin commit. Auditorías sin Críticos ni Altos. Falta la entrega B (filas 5, 6, 8, 10 y 11); el estado pasa a `EN REVISIÓN` al cerrarla |
| 2026-10-18 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entregas A y B ejecutadas: 11 filas con TDD, 61 pruebas en verde, 27 mutantes de la B y todos los de la A en rojo, documentación y ADR-019. Arquitectura y seguridad `APROBADO` tras dos ciclos de cierre; el hallazgo N-01 (`CREATEROLE` no basta para migrar) corrigió la documentación de producción. Sin commit |
| 2026-10-18 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el revisor: 61 pruebas en verde, `ruff`, `mypy`, `lint-imports` (14 kept) y `verificar_docs.py` limpios salvo los dos enlaces a `delta.md`. Auditorías independientes desde cero: seguridad `APROBADO` sin hallazgos Media o superior; arquitectura con un Menor (línea «Verificado en copia limpia» de `arranque-local.md`) corregido en un ciclo y dos Menores de trazabilidad en `impl.md` corregidos en el segundo; arquitectura `APROBADO` tras 2 ciclos. Los 17 Must `[M]` cumplidos |
| 2026-10-18 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos, `verificar_docs.py` y `extraer_mermaid.py` sin problemas tras corregir dos Medios y cinco Menores de la auditoría de documentación, commit local; el PR lo abre una persona |

## Decisiones registradas

- 2026-10-17 · El usuario validó el Must M1 a M9 y los non-goals. M10 (`.env.example` y marcas) se añadió como consecuencia documental de M1 a M9, sin ampliar el alcance.
- 2026-10-17 · Columnas de auditoría: solo `usuario` y `usuario_rol`, con `creado_por_id` y `actualizado_por_id` nulos permitidos. `rol`, `sesion` e `intento_acceso` no las llevan. Decidió el usuario.
- 2026-10-17 · `usuario_rol` lleva unicidad sobre (`usuario_id`, `rol_id`), que el modelo de datos §10 no declara. Decidió el usuario.
- 2026-10-17 · Los roles de PostgreSQL de aplicación y de solo lectura se crean sin contraseña en la migración; esta se fija por entorno. Decidió el usuario.
- 2026-10-17 · Gate del diseño, resuelto por el usuario:
  - **D-1 (`PA-T4`):** se revoca al rol de lectura el `SELECT` sobre `sesion` y sobre `usuario.password_hash`. La fila 8 aplica, con TC-44 a TC-46.
  - **D-2 (`PA-T5`) y D-6:** aplicación `lock_timeout` 5 s y `statement_timeout` 15 s; lectura 5 s y 60 s; migración sin tiempos hasta TKT-058; PostgreSQL 18 `(asumido)` como versión de producción.
  - **D-3:** se escribe el ADR de roles y migraciones (`docs/adr/20261017-roles-postgresql-y-migraciones.md`), durante `/sdd-ejecutar`.
  - **D-4:** opción (b), dos entregas dentro del mismo ticket y un PR cada una. La entrega A no se fusiona a `Produccion` hasta que la B esté lista. Aplicado el 2026-10-18 como dos entregas de ejecución sobre una sola rama y un solo PR, porque `v0001` se completó en la entrega B y la A no se fusiona sin ella; si se prefiere, el PR puede abrirse con dos commits.
  - **D-5:** el rol de migración lo crea el entorno; la migración crea los roles de aplicación y de lectura.
  - **D-7:** el comando documentado es `uv run --env-file ../.env alembic upgrade head`. Reinterpreta `CA-2` esc. 1 y `CA-11` esc. 2 de la spec, que se ajustan en `/sdd-completar`.
  - **D-8:** se alinea `conv-sql-postgres` §5 y §8 con los privilegios por omisión.
  - 2026-10-18 · Auditoría de la entrega A, F002 de arquitectura: el usuario decidió aceptar SQLAlchemy 2.1.5 y que la entrega B actualice el stack y `CLAUDE.md` de «2.0» a «2.x síncrono».
- **D-9:** se aprueba la ampliación de archivos respecto a la spec, incluidas las correcciones a `docs/05-tickets-trabajo.md`, `conv-docker` y el agente `ingeniero-devsecops`.

## Tickets futuros sugeridos

Todo lo que salió del alcance está en «Deuda que queda abierta» de [`delta.md`](delta.md), con su ticket sugerido. Lo más urgente:

- **TKT-058:** decidir cómo se contrata el rol de migración en producción. La `0001` exige superusuario o un rol que posea los atributos que ajusta; `NOSUPERUSER` con `CREATEROLE` no basta (N-01).
- **TKT-057:** purga de `sesion` e `intento_acceso` (`PA-T6` y `PA-T7`), rechazo de contraseñas `solo-desarrollo-*` fuera de local y revisión del `DELETE` de la aplicación sobre `sesion`.
- **TKT-006:** URL y motor de la aplicación, modelos ORM y normalización del correo (`PA-T10`).
- **TKT-009:** `uv run pytest` con Docker en el pipeline, `pip-audit`, el verificador de escenarios para `test_tkt003_*` y un contrato de `import-linter` para `tests/`.
- **Primer ticket de `analitica` (TKT-039):** confirmar que `cimenta_lectura` pueda leer `email` y `origen_ip` de `intento_acceso` (N-04).

Resueltos en este ticket: la alineación de `conv-sql-postgres` §5 y §8 con los privilegios por omisión (D-8) y la corrección del modelo de datos §2, §10 y §13 (`S1`).
