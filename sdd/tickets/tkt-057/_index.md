# TKT-057 · Endurecimiento de la frontera HTTP

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia: los requisitos son `RNF-04`, `RNF-05`, `RNF-06` (política de contenido) y `RNF-07` |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M en el ticket; reserva de talla en INVEST (ocho Must), el diseño puede proponer partirlo en dos entregas |
| **Reglas implicadas** | Ninguna `RN-xx` se implementa. `RNF-04`, `RNF-05`, `RNF-06`, `RNF-07`; toca `RNF-03`, `RNF-09` y `RNF-13` sin cambiarlos |
| **Invariantes en riesgo** | 10, 20 y 21 del modelo de datos. Regresión sobre TKT-005 y TKT-006: `CA-R1` a `CA-R8` |
| **Módulos en alcance** | `identidad` (límite de intentos, verificación y rotación del token), `auditoria` (consume `DENEGAR`); `servidor` (cabeceras, configuración) |
| **Capas en alcance** | aplicación · api · infraestructura (configuración, cabeceras) · posible migración aditiva (`PA-T11`). Sin frontend |
| **Depende de** | TKT-006 (ARCHIVADO) |
| **Rama** | `tkt-057-endurecimiento-http` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-30 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-30 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-31; verificado en `/sdd-revisar` el 2026-10-31 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-31 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-30 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por la persona dueña: M1 a M7 más M8, consecuencia documental. 18 criterios `[M]`, uno `[S]` y ocho de regresión, con rechazo en cada defensa. INVEST con una reserva (talla). Pasada adversarial: 5 objeciones, una cambió una decisión ya validada (secretos obligatorios) |
| 2026-10-30 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño con 16 filas en dos entregas (A: filas 1 a 10, B: 11 a 16), unas 540 líneas de producción (supera el tope de ~400; se propone partir, como TKT-006), ADR propuesto, 67 casos de prueba y 14 mutantes. `revisor-impacto`: sin frontera cruzada; cuatro bloqueantes (exportación de tipos, `test_definicion_ci.py`, conteo de ADR en `llms.txt` y pruebas de esquema de TKT-003) y nueve menores, todos incorporados al diseño. Nada se ejecutó: tres experimentos quedan `(sin ejecutar)` en la fila 1. Espera las decisiones D-1 a D-10 |
| 2026-10-30 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | La persona dueña aprobó el diseño con todas las recomendaciones D-1 a D-10. La fila 1 de la ejecución corre primero los experimentos E1 a E3 y, si alguno falla, se escala con `/sdd-escalar` |
| 2026-10-31 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Las 16 filas en dos entregas, con rojo antes de verde en cada una. Experimentos E1 a E3 confirmados. Suites en verde: 1373 en `backend` (Docker), 474 en `tools`, 214 en `frontend` y 3 de `e2e`. 16 mutantes de `CA-19`, todos rojos donde se esperaba. Auditorías de cierre: `auditor-arquitectura` y `auditor-sql` dieron `REQUIERE CAMBIOS` con Menores (el reloj leído antes del candado, índices completos que recorrían los rechazos por bloqueo, una docstring); un ciclo de corrección con el rojo escrito antes, y reauditoría `APROBADO` en las dos. Ajustes al diseño anotados en `impl.md`: `dominio/` sin `collections.abc`, un `# type: ignore[call-arg]` en `ajustes.py`, la suite completa en rojo entre las filas 2 y 5 por el orden del diseño y tres índices parciales en lugar de dos completos. Se interrumpió una vez por el límite semanal de la API y Docker Desktop estaba apagado; se reanudó sin pérdida. `auditor-seguridad`, `auditor-codigo` y `auditor-docs` quedan para `/sdd-revisar`. Sin commit. **El PR cambia el contrato (`openapi.yaml`), añade la migración `0005` y una dependencia directa (`pydantic-settings`), reescribe TC-75 de TKT-005 y pruebas de TKT-003 y TKT-006, cambia `.env.example`, el trabajo `humo`, `compose.yaml` y `frontend/scripts/tipos.ts`, y regenera `servidor.ts`: señalarlo a la persona que aprueba** |

| 2026-10-31 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el revisor: 1403 pruebas de `backend` (Docker), 474 de `tools`, 214 de `frontend` y 3 de `e2e` en verde; `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios; `verificar_docs` solo con los dos enlaces a `delta.md`. Cuatro auditorías independientes (arquitectura, código, seguridad, documentación) dieron `REQUIERE CAMBIOS` con Menores y tres Medias de seguridad. La persona dueña decidió: `F001` de seguridad riesgo aceptado con ticket futuro, `F002` mantener las filas con la retención como condición de salida a producción, `F003` corregir en este ticket. Dos ciclos de corrección con el rojo escrito antes (17 pruebas en rojo en el primero; el mutante 17 de `CA-19`, que murió al aplicarlo); `auditor-arquitectura`, `auditor-seguridad` y `auditor-codigo` `APROBADO`. `auditor-docs` dejó un único bloqueo, `N001` (`verificar_docs` en rojo por los enlaces a `delta.md`): la persona dueña lo aceptó como cierre condicionado a `/sdd-completar`, que no fusiona sin `verificar_docs` en verde y sin la comprobación de las diez comprobaciones requeridas. Las redacciones `N002` a `N004` las resolvió el orquestador con la salida real. `auditor-sql` no se repitió (aprobó el mismo código en `/sdd-ejecutar`). **El PR cambia el contrato (`openapi.yaml`), añade la migración `0005` y una dependencia directa (`pydantic-settings`), reescribe TC-75 de TKT-005 y pruebas de TKT-003 y TKT-006, cambia `.env.example`, el trabajo `humo`, `compose.yaml` y `frontend/scripts/tipos.ts`, regenera `servidor.ts` y deja `/docs` sin pintar por la política de contenido (`D-2`): señalarlo a la persona que aprueba** |
| 2026-10-31 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos (nueve observaciones nuevas en `_evolucion.md`; `meta-sdd` hace subir de conteo cuatro patrones y abre uno nuevo, con propuestas sin aplicar); `verificar_docs.py`, `markdownlint-cli2`, Vale y los tests de `tools/` sin problemas; `auditor-docs` dio seis Menores de cifras y coherencia, resueltos por el orquestador. El ticket queda archivado al fusionarse su PR; el número consta en el comentario de registro de la fusión. |

## Decisiones registradas

- 2026-10-31 · **Revisión.** `N001` aceptado como cierre condicionado a `/sdd-completar`; seguridad `F001` y `F002` aceptados con su registro; `F003` corregido en este ticket. Decidió la persona dueña.
- 2026-10-30 · **Diseño aprobado, D-1 a D-10:** migración aditiva `v0005` (D-1); valores de cabeceras y política también sobre `/docs` (D-2); un éxito reinicia la cuenta y no el origen, los rechazos no cuentan (D-3); correo normalizado en `intento_acceso` (D-4); `422` antes que el token en `POST /sesion` (D-5); las cinco variables de `ConfiguracionIdentidad` no se migran (D-6); el trabajo `humo` genera las contraseñas (D-7); dos entregas en un PR (D-8); el límite por origen no se serializa (D-9); rotar el token es fijar una cookie nueva sin estado (D-10). Decidió la persona dueña.
- 2026-10-30 · **Exportación de tipos.** `frontend/scripts/tipos.ts` pasa una contraseña efímera a `crear_aplicacion`, en lugar de una costura sin secretos en la fábrica. Decidió la persona dueña.

- 2026-10-30 · **Alcance.** Solo `Cache-Control` de la deuda de TKT-006 entra; el resto va a tickets futuros. Decidió la persona dueña.
- 2026-10-30 · **Valores del límite** `(asumido)`: 5 fallos por cuenta en 15 minutos con bloqueo fijo de 15 minutos; 20 fallos por origen en 15 minutos; un inicio correcto reinicia el recuento; los `422` no cuentan. Sin `slowapi`: se cuenta desde `intento_acceso`. Decidió la persona dueña.
- 2026-10-30 · **Enumeración.** El bloqueo se decide por correo normalizado en `intento_acceso`, exista o no el usuario. Decidió la persona dueña.
- 2026-10-30 · **Rechazo CSRF anónimo.** En `POST /sesion` va a `intento_acceso` (si hay correo legible) y al registro técnico; en otras rutas sin sesión responde `401` primero. Sin migración. Decidió la persona dueña.
- 2026-10-30 · **Contrato.** Quinto fallo `401`, sexto `429`; sesión antes que CSRF; `roles_requeridos` vacío en `ORIGEN_NO_VERIFICADO`. Decidió la persona dueña.
- 2026-10-30 · **Cabeceras.** `connect-src` también admite el origen del almacén (ampliación del texto del ticket); `HSTS` con `max-age=31536000` sin `includeSubDomains` ni `preload`. Decidió la persona dueña.
- 2026-10-30 · **Secretos.** Solo `CIMENTA_DB_CONTRASENA_APLICACION` es obligatoria al arrancar el servidor; `.env.example` lleva las claves sin valor; TC-75 se reescribe. Decidió la persona dueña tras la objeción 1 de la pasada adversarial.

## Tickets futuros sugeridos

- **Deuda de TKT-006 fuera de alcance:** topes de tamaño de cuerpo y de longitud de contraseña; suelo mínimo y re-derivación de los costes de Argon2; `/docs` y `/openapi.json` en producción (y Swagger desde un CDN sin SRI); `DENEGAR` sin límite de un usuario autenticado; conexión retenida durante Argon2.
- **Origen del cliente detrás de un proxy** (`PA-T5`): qué cabecera de reenvío se acepta y de qué proxies. Natural en TKT-058.
- **Desbloqueo por una persona administradora o bloqueo combinado cuenta y origen** (`PA-T12`), solo si el negocio no tolera el riesgo residual.
- **Purga de `intento_acceso`:** el rol de aplicación no puede borrar (invariante 20) y cada petición anónima rechazada escribe una fila; hace falta una política de retención con otro rol.
- **Cookies con prefijo `__Host-` o token CSRF atado a la sesión** (seguridad F001 de `/sdd-revisar`, decidido por la persona dueña el 2026-10-31 como riesgo aceptado): sin él, quien controle un subdominio hermano o un tramo HTTP del dominio padre puede fijar `cimenta_csrf` y `cimenta_sesion`. Va ligado a TKT-058, cuando se fije el dominio, junto con `includeSubDomains` en HSTS (F004).
- **Retención de `intento_acceso` como condición de salida a producción** (seguridad F002, decidido el 2026-10-31): se mantienen las filas por cada rechazo; la purga con otro rol queda como criterio de TKT-058.
- **Endurecimientos Bajos de seguridad:** `::add-mask::` para las contraseñas generadas en `humo` (F006) y no dejar el secreto en un `partial` de la fábrica (F007), a considerar al conectar Sentry.
- **Comprobación de `Origin` o `Referer`** como defensa añadida, solo si la persona dueña la pide.
