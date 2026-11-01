# Delta · TKT-057 · Endurecimiento de la frontera HTTP

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Regla pura del límite de intentos: `EstadoLimite`, `instante_de_disparo` y `evaluar_limite` | `backend/cimenta/identidad/dominio/limite_intentos.py` | Decidir, con enteros en microsegundos, si una cuenta (5 fallos) o un origen (20 fallos) tiene un bloqueo vigente en una ventana de 15 minutos que es también la duración del bloqueo (`RNF-04`) |
| Columna `intento_acceso.credenciales_verificadas`, restricción `ck_intento_acceso_exito_verificado` y tres índices parciales | `backend/migraciones/versions/v0005_identidad_intento_verificado.py` | Distinguir un fallo de contraseña de un rechazo por bloqueo o por falta de prueba de origen, sin reconstruir la cadena de bloqueos, y leer el recuento en milisegundos aunque un atacante engorde la tabla |
| `verificar_origen`, `par_csrf_valido`, `credenciales_con_origen_verificado` y `origen_de` | `backend/cimenta/identidad/api/dependencias.py` | Exigir el token de doble envío en todo método que muta, con la sesión evaluada antes que el token, y resolver el origen del cliente (IPv6 por /64, `::ffff:` desenvuelta, `desconocido` sin cliente) |
| `registrar_rechazo_de_origen`, `_asentar_rechazo_por_bloqueo` y `_bloquear_si_el_fallo_dispara_el_limite` | `backend/cimenta/identidad/aplicacion/sesiones.py` | Asentar el rechazo anónimo de `POST /sesion` en `intento_acceso` y en el registro técnico, y partir `abrir_sesion` en ramas planas |
| Consultas `bloquear_correo` (candado consultivo por correo), `fallos_de_correo`, `fallos_de_origen`, `ultimo_exito_de_correo` y `fijar_bloqueado_hasta` | `backend/cimenta/identidad/infraestructura/repositorio.py` | Serializar los intentos de una misma cuenta y leer los recuentos con una cota de `2 × ventana` |
| `AjustesServidor`, `ConfiguracionInvalida` y `cargar_ajustes` | `backend/servidor/ajustes.py` | Configuración con `pydantic-settings`: la aplicación no arranca sin `CIMENTA_DB_CONTRASENA_APLICACION` (`RNF-07`) |
| `MiddlewareCabecerasSeguridad`, `cabeceras_de_seguridad` y `cabeceras_para_ruta` | `backend/servidor/cabeceras.py` | `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy`, la política de contenido (con el origen del almacén) y `Cache-Control` en toda respuesta (`RNF-05`, `RNF-06`) |
| Nueve archivos de pruebas `test_tkt057_*.py` | `backend/tests/` | 1403 pruebas de backend en total tras el ticket, con rechazo en cada defensa, concurrencia real, una prueba de plan (`EXPLAIN`) y 17 mutantes |
| ADR `20261030-limite-de-intentos-sobre-intento-acceso` | `docs/adr/` | El límite se cuenta sobre `intento_acceso` con una marca de credenciales verificadas, sin `slowapi` |
| Variables opcionales `CIMENTA_ALMACEN_ORIGEN`, `CIMENTA_LIMITE_FALLOS_CUENTA`, `CIMENTA_LIMITE_FALLOS_ORIGEN` y `CIMENTA_LIMITE_MINUTOS` | `.env.example` | Origen del almacén de objetos para la política de contenido y valores de partida del límite (`PA-T2`, `(asumido)`) |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `abrir_sesion` | `backend/cimenta/identidad/aplicacion/sesiones.py` | Asentaba el intento y verificaba un hash → toma un candado por correo, lee el reloj, evalúa el bloqueo antes de buscar la credencial y de Argon2, asienta también los rechazos y fija `usuario.bloqueado_hasta` como reflejo |
| `intento_acceso.email` | `sesiones.py` | Se guardaba tal como se escribía → se guarda normalizado (minúsculas) |
| `cerrar_sesion` e `iniciar_sesion` | `backend/cimenta/identidad/api/rutas.py` | No verificaban el token CSRF y no lo rotaban → lo verifican (`403` `ORIGEN_NO_VERIFICADO`) y fijan una cookie `cimenta_csrf` nueva en su respuesta |
| `ConfiguracionIdentidad` | `backend/cimenta/identidad/aplicacion/configuracion.py` | Cinco variables → ocho (límites de fallos por cuenta y por origen, y minutos de ventana y bloqueo) |
| `crear_aplicacion` | `backend/servidor/fabrica.py` | Arrancaba sin credenciales → valida los ajustes en su primera línea, registra el middleware de cabeceras y entrega al motor la contraseña ya validada |
| `manejar_error_no_controlado` | `backend/servidor/manejadores.py` | El `500` solo llevaba `X-Correlacion-Id` → añade también las cabeceras de seguridad |
| `url_aplicacion` y `crear_motor_aplicacion` | `backend/herramientas/conexion.py` | Leían siempre la variable de entorno → aceptan la contraseña como argumento |
| `.env.example`, trabajo `humo` de `ci.yml` y `compose.yaml` | raíz y `.github/workflows/` | Contraseñas `solo-desarrollo-*` copiadas tal cual → las tres claves van sin valor y `humo` genera las contraseñas con `openssl rand -hex 24`; `compose.yaml` pide definirlas |
| `frontend/scripts/tipos.ts` y `frontend/src/api/generado/servidor.ts` | `frontend/` | Exportaba el OpenAPI con `crear_aplicacion(entorno={})` → genera una contraseña efímera desechable; `servidor.ts` regenera dos `@description` |
| `docs/api/openapi.yaml` y `docs/07-especificacion-api.md` | `docs/` | `SetCookieSesion` y rotación sin documentar → `SetCookieSesionYCsrf`, `x-tickets` de `cerrar_sesion`, descripciones del `429`, el `403` y el esquema `csrf` |
| Modelo de datos, stack, guía de arranque, README, wireframes, convenciones, skills y agentes | `docs/`, `README.md`, `CLAUDE.md`, `llms.txt`, `.claude/` | Sin `slowapi`, sin semilla CSRF, sin `solo-desarrollo-*`, 29 decisiones, «cinco fallos y el sexto bloqueado» y `verificar_origen` antes de `exigir_rol` |
| Pruebas de TKT-003, TKT-005, TKT-006 y TKT-007 y de `tools/` | `backend/tests/`, `tools/tests/` | Ajustadas por el tester a la columna nueva, al correo normalizado, al token en inicio y cierre, a las dos `Set-Cookie`, al entorno de `crear_aplicacion` y al paso `humo`; TC-75 de TKT-005 reescrito |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Los valores `solo-desarrollo-*` de las contraseñas | `.env.example` | Eran valores de desarrollo sin secreto; ahora cada persona define los suyos y `humo` los genera en el trabajo |
| El componente `SetCookieSesion` | `docs/api/openapi.yaml` | Dejó de usarse al sustituirse por `SetCookieSesionYCsrf` en las dos respuestas que lo referenciaban |
| La «semilla del token CSRF» como secreto obligatorio | `docs/06-stack-tecnologico.md` | El token es de doble envío sin firma ni estado: no hay semilla que guardar |
| `slowapi` como herramienta prevista del límite | `docs/06-stack-tecnologico.md` | Nunca se instaló; el recuento sale de `intento_acceso`, persistente y válido con varios procesos |
| La prueba que exigía arrancar sin `CIMENTA_DB_*` (TC-75 de TKT-005, reescrita en TKT-006) | `backend/tests/test_servidor_arranque.py` | Contradecía `RNF-07`; ahora exige arrancar con solo la contraseña de aplicación |

## Comportamiento observable nuevo

- Tras cinco fallos de contraseña contra una cuenta en menos de 15 minutos, el sexto intento responde `429` `LIMITE_INTENTOS` con `reintentar_en_s` (entre 1 y 900) y `Retry-After`, **aunque la contraseña sea correcta**. El bloqueo caduca solo y los intentos rechazados no lo alargan. Un correo que no existe se bloquea igual y el cuerpo es idéntico, de modo que no se revela qué cuentas existen.
- Veinte fallos desde un mismo origen en 15 minutos bloquean ese origen. El origen IPv6 se agrupa por /64, `::ffff:a.b.c.d` cuenta como IPv4 y sin cliente cae en una cubeta fija `desconocido`.
- Toda petición que muta (`POST /sesion` y `POST /sesion/cierre`) sin el par cookie y cabecera coincidente responde `403` `PERMISO` con motivo `ORIGEN_NO_VERIFICADO`. Sin sesión, el cierre responde `401` antes. El rechazo con sesión se asienta como `DENEGAR` a nombre del usuario; el anónimo del inicio queda en `intento_acceso` y en el registro técnico, nunca en la bitácora.
- Iniciar y cerrar sesión entregan una cookie `cimenta_csrf` nueva; el cliente de TKT-008 ya volvía a pedir el token y sigue funcionando (e2e 3 de 3).
- Toda respuesta, también los `401`, `403`, `404`, `422`, `429` y `500`, lleva las cuatro cabeceras de seguridad, y las de `/api/` llevan además `Cache-Control: no-store`. **`/docs` deja de pintarse** en el navegador porque la política de contenido no admite el script en línea ni el CDN de Swagger; `/openapi.json` sigue respondiendo (`D-2`).
- El servidor **no arranca** sin `CIMENTA_DB_CONTRASENA_APLICACION` (una variable vacía cuenta como ausente) y el error nombra la variable, nunca el valor. Quien clone el repositorio tiene que definir las contraseñas en su `.env` antes de `docker compose up`.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `POST /api/v1/sesion` | Exige el token de doble envío; añade el `429`; el `200` fija además `cimenta_csrf` | Sí para un cliente que no envíe el token; el cliente de TKT-008 ya lo enviaba |
| `POST /api/v1/sesion/cierre` | Exige el token; el `204` fija `cimenta_csrf`; `x-tickets` suma TKT-057 | Igual que arriba |
| `docs/api/openapi.yaml` | Nuevo componente `SetCookieSesionYCsrf`; `SetCookieSesion` eliminado; descripciones de `DemasiadosIntentos` y del esquema `csrf` | No: la forma de las respuestas no cambia |
| Esquema `intento_acceso` | Columna `credenciales_verificadas` `NOT NULL` sin `DEFAULT` | Sí para quien inserte filas sin ella (solo el servidor lo hace) |
| `frontend/src/api/generado/servidor.ts` | Dos `@description` regenerados | No |
| Variables de entorno | `CIMENTA_DB_CONTRASENA_APLICACION` obligatoria; cuatro opcionales nuevas | Sí para un despliegue que arrancara sin ella |

## Decisiones (ADR)

### 2026-10-30 — El límite de intentos se cuenta sobre `intento_acceso`, con una marca de credenciales verificadas

**Contexto:** `RNF-04` pide límite por cuenta y por origen con bloqueo temporal, y el borrador OpenAPI prohíbe revelar qué cuentas existen. `usuario.bloqueado_hasta` solo existe para cuentas reales y `slowapi` guarda el estado en memoria.
**Opciones consideradas:** (1) `slowapi` por origen y `bloqueado_hasta` por cuenta; (2) recuento sobre `intento_acceso` sin columna nueva; (3) recuento sobre `intento_acceso` con una columna `credenciales_verificadas`.
**Decisión:** la 3, con la ventana igual a la duración del bloqueo y un candado consultivo por correo.
**Evidencia:** la demostración de que distinguir un fallo de un rechazo sin columna obliga a reconstruir hacia atrás la cadena de bloqueos sin cota de lectura; la medición de la auditoría de SQL (33 ms leyendo 300 000 filas con índices completos frente a 0,02 a 0,04 ms con los parciales); TC-27 y TC-37 (mismo bloqueo y mismo cuerpo exista o no la cuenta); TC-33 (concurrencia).
**Consecuencias:** la tabla crece sin purga y cada rechazo anónimo inserta una fila; la política de retención con otro rol es condición de salida a producción (TKT-058). El límite por origen no se serializa y puede superarse con peticiones simultáneas.

→ `docs/adr/20261030-limite-de-intentos-sobre-intento-acceso.md`, ya en el índice con estado `Aceptado`.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| El doble envío sin estado no puede «invalidar» un token por rotación: solo deja de coincidir con la cookie vigente. Un criterio que pida rechazar el par (T1, T1) tras rotar es inalcanzable | La pasada adversarial de la spec reescribió `CA-12`: cookie T2 con cabecera T1 se rechaza | Cualquier criterio sobre rotación de un token sin estado |
| `FastAPI` evalúa los parámetros de cuerpo de una dependencia antes de llamarla: con un cuerpo inválido responde `422` sin ejecutarla | Experimento E1 de la fila 1 | Dependencias que necesitan el cuerpo ya validado (rechazos anónimos que registran el correo) |
| `hide_input_in_errors=True` solo oculta el valor en `str(error)`: `error.errors()` conserva la clave `input`. Hay que leer solo `loc` | Experimento E2 | Cualquier mensaje de error construido a partir de `ValidationError` |
| Un `pg_advisory_xact_lock` con el rol de aplicación sirve para serializar por clave sin tabla de bloqueos, y `lock_timeout` también lo corta (`55P03`) | Experimento E3 y la auditoría de SQL | Recuentos que deben ser exactos bajo concurrencia |
| Un índice completo no protege una lectura acotada si un atacante puede insertar filas que la consulta descarta; hace falta un índice parcial con el mismo predicado literal (`IS FALSE`, `IS TRUE`) | EXPLAIN con 1,3 M de filas en la auditoría de SQL y la prueba de plan | Tablas de solo-anexado con filas de rechazo |
| `ruff` (`UP035`) obliga a `collections.abc.Sequence` y la prueba de pureza del dominio de identidad solo admite `typing`: se tipa `tuple[int, ...] \| list[int]` | `impl.md`, fila 3 | Dominio de `identidad/`, hasta ampliar su lista blanca |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | `verificar_docs.py` falla durante todo el ticket por los enlaces del hub y de `impl.md` a `delta.md`, que no existe hasta `/sdd-completar`. Esta vez `auditor-docs` lo clasificó Mayor por regla y hubo que pedir a la persona dueña que aceptara un cierre condicionado | Alta |
| `guardrail` | La tabla de mutantes del diseño omitió la constante `2 ×` de la ventana de lectura: el mutante sobrevivió a 16 mutaciones y a dos auditorías de cierre, y solo lo halló la pasada independiente de `/sdd-revisar`. El diseño debería enumerar un mutante por cada literal y cada operador de una fórmula de dominio | Media |
| `comando` | La revisión de impacto encontró cuatro bloqueantes que el arquitecto no vio (la exportación de tipos, `test_definicion_ci.py`, el conteo de ADR en `llms.txt` y las pruebas de esquema de TKT-003) porque el arquitecto no tiene terminal para buscar consumidores. Pagó su coste, pero `/sdd-disenar` debería exigir a quien diseña un `grep` de los consumidores de cada símbolo que cambia de firma o se vuelve obligatorio | Media |
| `guardrail` | El orden de implementación de la fila 2 a la 5 dejó la suite completa en rojo (110 fallos) y las verificaciones intermedias corrían solo sus archivos, así que una violación de la prueba de pureza del dominio (fila 3) no apareció hasta la fila 5. Conviene exigir la suite completa al cerrar cada fila o agrupar el cambio obligatorio y su consumidor en una fila | Media |
| `comando` | `/sdd-ejecutar` paso 6 audita solo arquitectura y SQL, pero la pasada de `auditor-seguridad` en `/sdd-revisar` halló tres Medias (cookies sin `__Host-`, filas sin tope, origen IPv6) en un ticket cuyo objeto es la seguridad. Si hay endpoint, sesión o entrada externa, la auditoría de seguridad debería correr ya al cierre de la ejecución | Media |
| `herramienta` | Docker Desktop estaba apagado tras un reinicio y un tester produjo `49 passed, 157 errors` con salida que no vale como rojo; además, el límite semanal de la API cortó un agente a medias (se reanudó con `SendMessage` sin pérdida). El gate de `/sdd-ejecutar` comprueba `docker info` una vez, no antes de cada despacho | Media |
| `convención` | `sesiones.py` está en CRLF en la copia de trabajo y en LF en el índice; los correctores tuvieron que detectar el fin de línea archivo a archivo. Es la tercera vez que aparece (TKT-001, TKT-003 y este) sin una regla escrita en `conv-*` | Media |
| `modelo` | Los desarrolladores en `haiku` cerraron bien la mayoría de las filas; las que tocaban concurrencia, permisos de un rol y el refactor de `abrir_sesion` fueron a `sonnet` por disparador del diseño y salieron a la primera. Ningún paso necesitó subir de nivel | Baja |
| `guardrail` | El experimento previo funcionó: la fila 1 del diseño ejecutó tres afirmaciones `(sin ejecutar)` sobre bibliotecas antes de construir nada (las tres se confirmaron) y la pasada adversarial de la spec reescribió un criterio inalcanzable (`CA-12`) y reabrió una decisión de secretos que contradecía el privilegio mínimo. Conviene que la pasada adversarial pregunte siempre «¿quién necesita este secreto en ejecución?» | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Cookies con prefijo `__Host-` o token atado a la sesión, y `includeSubDomains` en HSTS | La persona dueña aceptó el riesgo (2026-10-31): cambiar el nombre de las cookies altera el contrato de TKT-006 y el dominio de despliegue aún no existe | Ligado a TKT-058 |
| Purga o retención de `intento_acceso` con un rol distinto del de aplicación | Se mantienen las filas por cada rechazo (decisión de la persona dueña); es condición de salida a producción | Criterio de TKT-058 |
| Origen del cliente detrás de un proxy (`--proxy-headers`, `FORWARDED_ALLOW_IPS`, `X-Forwarded-For`) y colapsar hosts no parseables | Depende del despliegue real; ahora la cubeta `desconocido` y el /64 se comparten entre clientes si el servidor no entrega la IP real | TKT-058 (`PA-T5`) |
| Topes de tamaño de cuerpo y de longitud de contraseña, suelo mínimo y re-derivación de los costes de Argon2, `/docs` y `/openapi.json` en producción, `DENEGAR` sin límite de un autenticado y la conexión retenida durante Argon2 | Deuda de TKT-006 fuera del alcance validado por la persona dueña | Ticket de endurecimiento de identidad |
| `::add-mask::` para las contraseñas generadas en `humo` y no dejar el secreto en un `partial` de la fábrica | Observaciones Bajas de seguridad; hoy ningún paso las imprime y no hay Sentry | Al conectar Sentry |
| Mutación manual de `origen_de` y limpieza de las observaciones de código (`abrir_sesion` aún con 88 líneas, frases repetidas, ayudas de arranque duplicadas entre dos archivos de prueba) | Observaciones que no bloquean | Ticket de limpieza de TKT-057 |
| Validar el diagrama ER de `intento_acceso` en un navegador y ejecutar `lychee` | `lychee` no está instalado en la máquina de la ejecución; el parser de Mermaid solo corre en un navegador | CI |
| `SET LOCAL lock_timeout` y `CREATE INDEX CONCURRENTLY` en migraciones sobre tablas que crecen | Con la tabla de hoy el bloqueo de la migración es irrelevante (6,7 s con 3 M de filas) | Ticket de operación |
| Ocho hallazgos de `code-review` antes del PR (todos Menores o de diseño, sin fallo reproducible): el recuento que se repite tras cada fallo de una cuenta real (`sesiones.py`), guardar la cubeta del origen en lugar de la dirección real, hosts no parseables que abren cubetas distintas, validación del puerto y del host de `CIMENTA_ALMACEN_ORIGEN`, la diferencia de mayúsculas entre las dos ramas de `cargar_ajustes`, el rechazo CSRF duplicado en dos dependencias, tres mecanismos de lectura del entorno y el cálculo por petición del middleware de cabeceras | No bloquean y reabrir el código habría ampliado el alcance validado por la persona dueña; los dos con efecto de seguridad dependen del despliegue | Ticket de limpieza de TKT-057 y TKT-058 |
| Precisión forense de `origen_ip` (guarda la cubeta, no la IP) | Decisión derivada de agrupar por /64; falta decirlo en el ADR | Resuelta: nota en el ADR, sección Consecuencias (`docs/adr/20261030-limite-de-intentos-sobre-intento-acceso.md`) |

## Pull request

**Título:** `TKT-057 · Endurecimiento de la frontera HTTP`
**Origen:** `agent+human-review` — lo escribieron agentes y lo revisan y aprueban la persona dueña (decisiones `D-1` a `D-10`, riesgos de seguridad, cierre condicionado) y `/sdd-revisar`.
**Cuerpo:** qué (límite de intentos por cuenta y por origen, verificación y rotación del token CSRF, cabeceras de seguridad, configuración que no arranca sin secretos), por qué (`RNF-04`, `RNF-05`, `RNF-06`, `RNF-07`), criterios cubiertos (`CA-1` a `CA-19` y `CA-R1` a `CA-R8`) y cómo verificarlo (`uv run pytest`, `npm test`, `npm run e2e`, `python tools/verificar_docs.py`).

**Fusión con omisión:** la fusión a `Produccion` será con omisión de la protección y solo con la aprobación explícita de la persona dueña en la sesión. El registro va en un comentario del PR, no en este archivo.
