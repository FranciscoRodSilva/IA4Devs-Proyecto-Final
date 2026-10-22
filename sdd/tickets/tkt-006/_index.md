# TKT-006 · Autenticación y autorización por rol

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR

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
| Impl | impl.md | `/sdd-ejecutar` | Pendiente |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-21 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M11 más M12, consecuencia documental. 15 criterios `[M]`, dos `[S]` y siete de regresión, con rechazo en cada regla. INVEST con una reserva (talla) |
| 2026-10-21 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño con 12 filas en dos entregas (A: filas 1 a 9, B: 10 a 12), unas 2,700 líneas (supera el tope de ~400; se propone partir, como TKT-004 y TKT-005), ADR-023 propuesto, 63 pruebas y 22 mutantes. Se diseñó con TKT-007 aún sin spec, por confirmación del usuario; su contrato C-1 queda como riesgo. `revisor-impacto` ausente: el impacto lo hizo el arquitecto por sustitución. El arquitecto no ejecutó nada. Espera decisiones D-1 a D-9 |
| 2026-10-21 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño con todas las recomendaciones D-1 a D-9. **No ejecutar hasta que TKT-007 esté archivado**: TKT-006 depende de él y de su contrato C-1 |

## Decisiones registradas

- 2026-10-21 · **CSRF.** TKT-006 emite el token y monta `GET /sesion/csrf`; la verificación del doble envío, el `429` y `ORIGEN_NO_VERIFICADO` son de TKT-057. Decidió el usuario.
- 2026-10-21 · **`DENEGAR`.** TKT-007 pasa a dependencia de TKT-006 y se ejecuta antes. Decidió el usuario.
- 2026-10-21 · **No-auto-autorización.** La implementa TKT-006 en `identidad/dominio`, sin `RN-xx`, con motivo `AUTO_RESOLUCION`; TKT-026 la reutiliza. Decidió el usuario.
- 2026-10-21 · El usuario validó el Must, el Won't y los supuestos: caducidad de 12 h absoluta y 30 min de inactividad, usuario desactivado con sesión abierta → `401` `SESION_REVOCADA`, correo en minúsculas, parámetros de Argon2 por configuración mínima sin `pydantic-settings`, `DELETE` sobre `sesion` sin tocar. Decidió el usuario.
- 2026-10-21 · **C-1 y D-3 enmendados por TKT-007.** Un `403` sin recurso se atribuye al usuario —`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`— y `datos` no lleva `correlacion_id`. `url_aplicacion`, `crear_motor_aplicacion` y la *fixture* `motor_aplicacion` los entrega TKT-007. Decidió el usuario en el intake de TKT-007.

## Tickets futuros sugeridos

- **Alta de usuarios y primer usuario** (`PA-T13`): sin una operación que cree usuarios y asigne roles, nadie puede iniciar sesión en producción.
- **Purga de sesiones y destino del `DELETE`** (`PA-T9`, `PA-T6` y `PA-T7` de TKT-003).
- **Origen de los roles que exige cada acción** (`PA-T2` de TKT-005): un lugar único para no repetir `x-roles` en cada caso de uso.
- **El PRD reconoce la no-auto-autorización** (`PA-T1`): una `RN` o una nota de `HDU-003`.
- **Permisos por obra y la deuda de `NO_ENCONTRADO`** (`PA-T11`): solo si el PRD los incorpora.
- **`origen_ip` como `inet`.**
