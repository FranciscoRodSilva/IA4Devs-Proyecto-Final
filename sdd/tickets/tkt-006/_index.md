# TKT-006 · Autenticación y autorización por rol

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia; los escenarios `HDU-003` esc. 7 y 8, `HDU-001` esc. 23, `HDU-002` esc. 11 y `HDU-006` esc. 12 los implementan los tickets consumidores |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M en el ticket; riesgo de subir a L por los once Must (se propone partir en entregas A y B en el diseño) |
| **Reglas implicadas** | Ninguna `RN-xx` se implementa. `RN-04` fundamenta el asiento `DENEGAR`; `RNF-01` a `RNF-04` y `RNF-13` fijan sesión, cookie, contraseña, intentos y registro. La no-auto-autorización no tiene `RN-xx` (`PA-T1`) |
| **Invariantes en riesgo** | 10, 20 y 21 del modelo de datos. Regresión sobre TKT-001 a TKT-005: `CA-R1` a `CA-R7` |
| **Módulos en alcance** | `identidad` (sesión, regla de auto-autorización) y `auditoria` (consume el servicio `DENEGAR` de TKT-007) |
| **Capas en alcance** | dominio (regla de M8) · aplicación (casos de uso de sesión) · api (rutas, dependencia de sesión) · infraestructura (modelos ORM, motor del rol de aplicación) |
| **Depende de** | TKT-003 y TKT-005 (ARCHIVADOS) y **TKT-007**, que el ticket no declaraba y se ejecuta antes (decisión del usuario, 2026-10-21) |
| **Rama** | `tkt-006-autenticacion-y-roles` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-21 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-21 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-22; verificado en `/sdd-revisar` |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-22 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-21 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M11 más M12, consecuencia documental. 15 criterios `[M]`, dos `[S]` y siete de regresión, con rechazo en cada regla. INVEST con una reserva (talla) |
| 2026-10-21 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño con 12 filas en dos entregas (A: filas 1 a 9, B: 10 a 12), unas 2,700 líneas (supera el tope de ~400; se propone partir, como TKT-004 y TKT-005), ADR-023 propuesto, 63 pruebas y 22 mutantes. Se diseñó con TKT-007 aún sin spec, por confirmación del usuario; su contrato C-1 queda como riesgo. `revisor-impacto` ausente: el impacto lo hizo el arquitecto por sustitución. El arquitecto no ejecutó nada. Espera decisiones D-1 a D-9 |
| 2026-10-21 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño con todas las recomendaciones D-1 a D-9. **No ejecutar hasta que TKT-007 esté archivado**: TKT-006 depende de él y de su contrato C-1 |
| 2026-10-22 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entregas A y B ejecutadas (filas 1 a 12): 1126 pruebas en verde con Docker (255 propias de este ticket), 31 mutantes en rojo y un único superviviente (el `MT-10` literal) cubierto con un test nuevo, 15 contratos de `import-linter`, una sola cabeza de Alembic (`0004`), `pip-audit` limpio. Se ejecutó después de TKT-007, archivado e integrado en `Produccion`. Decisión del usuario durante la ejecución: la validación del correo usa `email_validator` con `test_environment=True` y `email-validator` pasa a dependencia directa (el diseño decía `validate_email` de Pydantic, que rechaza `ana@cimenta.test`). Auditoría de seguridad: `APROBADO`, tres Menores opcionales. Auditoría de arquitectura: `REQUIERE CAMBIOS` con cuatro Menores documentales; tres ciclos de corrección y reauditorías; la última dejó un único bloqueo de redacción (la evidencia de las reejecuciones de la suite), que el orquestador resolvió registrando las salidas reales en `impl.md`, **sin una cuarta reauditoría**: lo confirma `/sdd-revisar`. Una fragilidad de codificación de un test (dependía de `PYTHONUTF8` en Windows) se corrigió con su rojo. `desarrollador-aplicacion`, `desarrollador-api`, `auditor-sql`, `auditor-codigo`, `auditor-docs` y `revisor-impacto` ausentes, sustituidos. Sin commit |
| 2026-10-22 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el revisor sin `PYTHONUTF8`: 1126 pruebas en verde y 1138 tras el ciclo de corrección; `ruff`, `format`, `mypy`, 15 contratos, `verificar_float`, `verificar_docs` y una sola cabeza de Alembic (`0004`) en verde. Pasada independiente de arquitectura: `REQUIERE CAMBIOS` con tres Menores; el usuario decidió corregir `F3` en código (un `password_hash` que no es Argon2 daba `500`, reproducido por dos auditores; rojo primero) y dejar `F1` y `F2` como documentación en los tickets TKT-021, TKT-026 y TKT-027, el ADR-023 y el diseño; reauditoría `APROBADO`. Los 15 criterios `[M]`, los 2 `[S]` y los 7 de regresión cumplidos. `auditor-sql`, `auditor-codigo` y `auditor-docs` ausentes, sustituidos por `auditor-arquitectura` y los verificadores. **El PR no toca `docs/api/openapi.yaml`; reescribe un test de TKT-005 (TC-75, decisión D-2), añade dependencias (`pwdlib[argon2]` y `email-validator`) y la migración `0004`: señalarlo a la persona que aprueba** |
| 2026-10-22 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos (observaciones nuevas en `_evolucion.md`; los patrones `agente`, `herramienta` y `comando` suben de conteo y se añaden tres patrones nuevos con propuesta de mejora al toolkit, sin aplicar); `verificar_docs.py`, `extraer_mermaid.py` y los tests de `tools/` sin problemas; `auditor-docs` y `meta-sdd` ausentes, sustituidos por los verificadores y por el orquestador; commit local; el PR lo abre una persona. **El PR reescribe un test de TKT-005 (TC-75), añade dependencias y la migración `0004`, y no toca `docs/api/openapi.yaml`** |

## Decisiones registradas

- 2026-10-21 · **CSRF.** TKT-006 emite el token y monta `GET /sesion/csrf`; la verificación del doble envío, el `429` y `ORIGEN_NO_VERIFICADO` son de TKT-057. Decidió el usuario.
- 2026-10-21 · **`DENEGAR`.** TKT-007 pasa a dependencia de TKT-006 y se ejecuta antes. Decidió el usuario.
- 2026-10-21 · **No-auto-autorización.** La implementa TKT-006 en `identidad/dominio`, sin `RN-xx`, con motivo `AUTO_RESOLUCION`; TKT-026 la reutiliza. Decidió el usuario.
- 2026-10-21 · El usuario validó el Must, el Won't y los supuestos: caducidad de 12 h absoluta y 30 min de inactividad, usuario desactivado con sesión abierta → `401` `SESION_REVOCADA`, correo en minúsculas, parámetros de Argon2 por configuración mínima sin `pydantic-settings`, `DELETE` sobre `sesion` sin tocar. Decidió el usuario.
- 2026-10-21 · **C-1 y D-3 enmendados por TKT-007.** Un `403` sin recurso se atribuye al usuario —`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`— y `datos` no lleva `correlacion_id`. `url_aplicacion`, `crear_motor_aplicacion` y la *fixture* `motor_aplicacion` los entrega TKT-007. Decidió el usuario en el intake de TKT-007.

- 2026-10-22 · **Validación del correo.** `email_validator` con `check_deliverability=False` y `test_environment=True`, devolviendo el valor tal como se escribió; `email-validator` se declara dependencia directa. Decidió el usuario.

## Tickets futuros sugeridos

- **Alta de usuarios y primer usuario** (`PA-T13`): sin una operación que cree usuarios y asigne roles, nadie puede iniciar sesión en producción.
- **Purga de sesiones y destino del `DELETE`** (`PA-T9`, `PA-T6` y `PA-T7` de TKT-003).
- **Origen de los roles que exige cada acción** (`PA-T2` de TKT-005): un lugar único para no repetir `x-roles` en cada caso de uso.
- **El PRD reconoce la no-auto-autorización** (`PA-T1`): una `RN` o una nota de `HDU-003`.
- **Permisos por obra y la deuda de `NO_ENCONTRADO`** (`PA-T11`): solo si el PRD los incorpora.
- **`origen_ip` como `inet`.**
- **Menores de seguridad opcionales de TKT-006:** `UnknownHashError` sin capturar si algún `password_hash` no es Argon2 (anotarlo en el alta de usuarios, `PA-T13`); suelo mínimo y re-derivación de los costes de Argon2 (configuración de TKT-057); prefijo `__Host-` de la cookie (al tocar el borrador).
- **Mensaje de `SESION_REVOCADA`:** el código y el ejemplo del borrador difieren en dos signos; decidir cuál manda al tocar el borrador.
