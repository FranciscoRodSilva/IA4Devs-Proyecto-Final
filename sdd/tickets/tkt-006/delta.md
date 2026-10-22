# Delta · TKT-006 · Autenticación y autorización por rol

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Dominio de identidad, Python puro sin `datetime`, `pwdlib` ni `contrato_error`: `normalizar_correo`; `evaluar_vigencia`, `EstadoSesion` y `Ordenable` (la vigencia es genérica sobre cualquier valor ordenable, así que se prueba con enteros y con instantes con zona); `credenciales_aceptadas`; `rol_suficiente` (el permiso efectivo es la unión de los roles); y `evaluar_resolucion` con `ResultadoResolucion` y `MotivoNegacion`, que no recibe roles y nunca lanza | `backend/cimenta/identidad/dominio/` (`correo.py`, `vigencia.py`, `acceso.py`, `autorizacion.py`) | Decidir sin base de datos ni reloj la vigencia de una sesión, la aceptación de credenciales, el permiso por rol y la prohibición de resolver lo propio (`M8`, que no tiene `RN-xx`) |
| Configuración de identidad con cinco variables opcionales (`CIMENTA_SESION_CADUCIDAD_MINUTOS`, `CIMENTA_SESION_INACTIVIDAD_MINUTOS` y tres de Argon2), con 720 y 30 minutos por omisión `(asumido)`, y un reloj inyectable. Un valor presente que no sea un entero positivo en dígitos ASCII impide arrancar | `backend/cimenta/identidad/aplicacion/configuracion.py` y `reloj.py` | Que las caducidades y los costes de Argon2 salgan de configuración (`RNF-03`) sin adelantar `pydantic-settings`, que es de TKT-057 |
| Contexto y casos de uso de sesión: `ContextoIdentidad`, `UsuarioAutenticado`, `construir_contexto`, `abrir_sesion`, `validar_sesion` y `cerrar_sesion_vigente`. Cada caso de uso abre su propia transacción con `begin()` y lanza el `401` **después** de salir del bloque | `backend/cimenta/identidad/aplicacion/contexto.py` y `sesiones.py` | Abrir, reconocer y cerrar una sesión con estado en la tabla `sesion` (ADR-014) sin que el rechazo deshaga el registro del intento |
| `registrar_denegacion`: abre una transacción propia, llama a `asentar_denegacion` de la interfaz de `auditoria` y, si el asiento falla, registra `denegacion_no_asentada` con el `correlacion_id` y deja que la petición responda `403` | `backend/cimenta/identidad/aplicacion/denegacion.py` | Que todo `403` por rol insuficiente con usuario autenticado quede en la bitácora como `DENEGAR` (`RN-04`) aunque no haya cambio que acompañar |
| Adaptador `ContrasenasArgon2` sobre `pwdlib`, con el protocolo `CostesArgon2` y un hash de descarte derivado al construir con los mismos costes que los hashes reales. `verificar` devuelve `False` ante un hash que no es Argon2 | `backend/cimenta/identidad/infraestructura/contrasenas.py` | Verificar siempre exactamente un hash, exista o no el correo (`CA-3`), y guardar contraseñas con Argon2id (`CA-15`) |
| Modelos ORM de las cinco tablas de `v0001` (`Usuario`, `Rol`, `UsuarioRol`, `Sesion`, `IntentoAcceso`) con su `Base` y `naming_convention`, y ocho funciones de repositorio, ninguna de las cuales confirma. `tocar_sesion` y `revocar_sesion` llevan `WHERE ... revocada_en IS NULL ... RETURNING`; ningún `DELETE` sobre `sesion` ni `UPDATE` o `DELETE` sobre `intento_acceso` | `backend/cimenta/identidad/infraestructura/modelos.py` y `repositorio.py` | Leer y escribir las tablas de identidad con el rol de aplicación y resolver la carrera entre un cierre de sesión y una petición simultánea |
| API de identidad: las cuatro rutas de sesión, todas `def`, los DTO (`TokenCsrf`, `CredencialesInicio`, `UsuarioActual`), `sesion_vigente`, `exigir_rol(*roles)` y `montar_identidad`. Las cookies son `cimenta_sesion` (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`) y `cimenta_csrf` (sin `HttpOnly`) | `backend/cimenta/identidad/api/` (`esquemas.py`, `dependencias.py`, `rutas.py`, `montaje.py`) | Implementar `obtener_token_csrf`, `iniciar_sesion`, `obtener_sesion_actual` y `cerrar_sesion` del borrador, y dar a los demás módulos una dependencia declarativa por ruta |
| Migración `v0004` con la restricción `ck_usuario_email_minusculas` (`CHECK (email = lower(email))`), con su bajada | `backend/migraciones/versions/v0004_identidad_correo_en_minusculas.py` | Que la base rechace un correo con mayúsculas aunque alguien escriba directo (`S2`, `PA-T10`) |
| Diez archivos de pruebas `test_tkt006_*.py`: 255 casos propios al cerrar `/sdd-ejecutar` y 12 más en el ciclo de `/sdd-revisar` (tres casos de aplicación, tres por HTTP, cinco de adaptador y uno de salvaguarda; 267 en total, se infiere de impl.md). Cinco *fixtures* nuevas en `conftest.py`, ninguna `autouse` | `backend/tests/test_tkt006_configuracion.py`, `_dominio.py`, `_repositorio.py`, `_inicio_sesion.py`, `_sesion_vigente.py`, `_csrf.py`, `_cierre.py`, `_enrutador.py`, `_esquema.py` y `_permisos_rol.py`; `backend/tests/conftest.py` | Cada garantía se vio fallar: 16 mutantes en la entrega A y 14 distintos en la B (15 casos, porque MT-10 aparece dos veces), con el SHA-256 de cada archivo restaurado |
| ADR-023, sesión y autorización por dependencia | `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md` y su fila en el índice | Dejar escrito por qué la validación escribe en cada petición, por qué el `DENEGAR` va en otra transacción y por qué el dominio no consulta el reloj |
| Sección «Cómo se protege una ruta», párrafo «Cómo se aplica» de la autorización, nota sobre el correo en minúsculas, bloque de variables opcionales y criterios nuevos en TKT-021, TKT-026 y TKT-027 | `.claude/skills/conv-backend-fastapi/SKILL.md` §9, `docs/02-arquitectura.md` §7.1, `docs/03-modelo-datos.md` §10, `.env.example`, `docs/05-tickets-trabajo.md` | Que quien escriba la siguiente ruta sepa cómo protegerla y qué `403` no se asienta solo |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Fábrica de la aplicación | `backend/servidor/fabrica.py` | `crear_aplicacion(*, destino_registro=None)` sin rutas → `crear_aplicacion(*, destino_registro, motor, reloj, entorno)`, que monta solo `cimenta.identidad.api.montaje` y crea el motor del rol de aplicación de forma perezosa: construir la aplicación no lee `CIMENTA_DB_*` ni abre conexión |
| TC-75 de TKT-005 | `backend/tests/test_servidor_arranque.py` | «Construir la aplicación y responder un `404` no carga `sqlalchemy` ni `psycopg`» → «en un proceso sin ninguna variable `CIMENTA_DB_*`, un `404`, el token CSRF y una consulta de sesión sin cookie no tocan la base». Prueba lo que protegía y no qué módulos se importan. Decisión D-2 del diseño, aprobada por el usuario. Se añadió además el caso de arranque de `fastapi dev` sin variables de base (`CA-R4`) |
| Interfaz publicada de `identidad` | `backend/cimenta/identidad/interfaz.py` | Solo un docstring → seis nombres: `sesion_vigente`, `exigir_rol`, `UsuarioAutenticado`, `evaluar_resolucion`, `ResultadoResolucion` y `MotivoNegacion` |
| Dependencias | `backend/pyproject.toml`, `backend/uv.lock` | Sin hashing de contraseñas ni validador de correo directo → `pwdlib[argon2]>=0.3.1` y `email-validator>=2.3.0`. El bloqueo fija `pwdlib` 0.3.1, `argon2-cffi` 25.1.0, `argon2-cffi-bindings` 26.1.0, `cffi` 2.1.1 y `pycparser` 3.11. `pip-audit` limpio |
| `mypy` | `backend/pyproject.toml` | Override estricto de `cimenta.*.dominio.*`, `cimenta.auditoria.*`, `tipos_base.*`, `contrato_error.*` y `servidor.*` → también `cimenta.identidad.*` |
| *Fixtures* de pruebas | `backend/tests/conftest.py` | Motor y sesión del rol de aplicación → además `ENTORNO_DE_PRUEBA`, `RelojDePrueba` y las *fixtures* `reloj_de_prueba`, `sembrar_usuario`, `registro_tecnico`, `aplicacion_identidad` y `cliente`. Las existentes no cambian y ninguna nueva es `autouse` |
| Comando de desarrollo | `CLAUDE.md`, `docs/arranque-local.md` | `uv run fastapi dev` → `uv run --env-file ../.env fastapi dev`, con la frase de que sin el archivo de entorno la aplicación arranca pero la primera ruta que necesita la base responde `500`. En «Lo que todavía no arranca», iniciar sesión en local: no hay alta de usuarios (`PA-T13`) |
| Conteo de decisiones | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/02-arquitectura.md` §12 | 22 → 23 ADR, con la fila de ADR-023 en el índice y en arquitectura §12 |
| Especificación de la API §2.5 y §4.1 | `docs/07-especificacion-api.md` | `GET /sesion/csrf` asignada solo a TKT-057 → «TKT-006, TKT-057», con la frase «TKT-006 emite el token; la rotación y la verificación llegan con TKT-057» |
| Plan de tickets | `docs/05-tickets-trabajo.md` | TKT-006 «Depende de TKT-003, TKT-005» → también TKT-007, con el criterio de que emite el token y no lo verifica, y «no implementa ... la verificación CSRF». TKT-026 «escribe en `dominio/` el rol requerido y la prohibición de resolver lo propio» → usa `evaluar_resolucion` de TKT-006; la falta de rol es `ROL_INSUFICIENTE` y la decide `api/` con `exigir_rol`. TKT-021, TKT-026 y TKT-027 reciben el criterio de asentar por la interfaz de auditoría los `403` que nacen en el caso de uso |
| Convención de seguridad | `.claude/skills/conv-seguridad/SKILL.md` §2 | Cookies `HttpOnly`, `Secure`, `SameSite` → además «la dependencia es `sesion_vigente`; los roles se leen de la base en cada petición y nunca se cachean» |
| Diseño de TKT-006 | `sdd/tickets/tkt-006/design.md` | Se ajustaron las filas 3, 7 y 11 (`⚠ Ajustado`), se anotó el límite de `rutas_de` en D-4 y la decisión del correo. El código literal que quedó superado por `backend/` sigue en el diseño: manda `backend/` |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| La afirmación de TC-75 de TKT-005 de que construir la aplicación no carga SQLAlchemy | `backend/tests/test_servidor_arranque.py` | Montar `identidad` carga SQLAlchemy por diseño. La propiedad que protegía —que el camino del error no toca la base— la conserva el test reescrito, y `CA-11` esc. 3 de TKT-005 sigue cubierto por la bitácora de TKT-007 |
| `uv run fastapi dev` sin `--env-file` | `CLAUDE.md` y `docs/arranque-local.md` | El comando anterior arrancaba, pero sin el archivo de entorno la primera ruta que necesita la base respondía `500`; el nuevo carga el entorno |

No se eliminó ninguna ruta, columna, tipo ni función de producción.

## Comportamiento observable nuevo

Un integrador, o una persona con uno de los seis roles, nota ahora lo siguiente:

- **Cuatro rutas de sesión.** `GET /api/v1/sesion/csrf` emite el token de doble envío: fija la cookie `cimenta_csrf`, sin `HttpOnly`, y devuelve el mismo valor en el cuerpo, distinto en cada petición. `POST /api/v1/sesion` inicia sesión con correo y contraseña, crea la fila de `sesion`, fija `cimenta_sesion` con un identificador opaco y responde `UsuarioActual`. `GET /api/v1/sesion` devuelve el usuario, sus roles y las dos caducidades. `POST /api/v1/sesion/cierre` escribe `revocada_en`, expira la cookie y responde `204`; la fila no se borra.
- **`exigir_rol`.** Cualquier módulo declara el rol de una ruta con `dependencies=[Depends(exigir_rol(...))]`, importado de `cimenta.identidad.interfaz`, con los roles de su `x-roles`. El permiso efectivo es la unión de los roles del usuario.
- **El `401` va antes que el `403`.** `exigir_rol` se apoya en `sesion_vigente`: sin sesión, con una cookie que no corresponde a nada o con una cookie mal formada responde `401` `SESION` `SIN_SESION` sin distinguir los casos; la sesión vencida responde `SESION_CADUCADA` y la cerrada o la de un usuario desactivado, `SESION_REVOCADA`. Solo con sesión vigente y sin el rol llega el `403` `PERMISO` `ROL_INSUFICIENTE` con `roles_requeridos`. Ningún cuerpo lleva `detail`.
- **Los roles se leen en cada petición.** No hay caché de roles ni del estado del usuario, y `request.state.roles_de_quien_llama` se fija en cada petición como `frozenset[str]`.
- **Revocación inmediata.** Cerrar sesión, desactivar al usuario o retirarle un rol surte efecto en la petición siguiente. Un usuario desactivado con la sesión abierta recibe `401` `SESION_REVOCADA` `(asumido)`.
- **Caducidad.** Absoluta a las 12 horas y por inactividad a los 30 minutos `(asumido)`, ambas configurables. La actividad desliza la inactividad pero no la caducidad absoluta, y en el instante exacto del límite la sesión ya caducó. Cada petición vigente escribe `ultima_actividad`.
- **`DENEGAR` de un `403` con rol insuficiente.** Queda asentado en la bitácora, con el usuario autenticado como actor, `entidad_tipo` igual a `usuario`, método, ruta y roles requeridos en los datos, y sin `regla_negocio`. Va en una transacción propia: persiste aunque nada la acompañe. Si la bitácora falla, la respuesta sigue siendo `403` y el fallo queda en el registro técnico. Las denegaciones anónimas no entran en la bitácora: van a `intento_acceso` y al registro técnico.
- **Inicio de sesión que no revela qué cuentas existen.** Correo inexistente, contraseña errónea, usuario desactivado y un `password_hash` que no es Argon2 responden el mismo `401` `CREDENCIALES_INVALIDAS`, que solo difiere en `correlacion_id`. Cada intento deja su fila en `intento_acceso`, también el fallido.
- **Correo en minúsculas.** Se busca en minúsculas, la base lo exige con `ck_usuario_email_minusculas`, e `intento_acceso` guarda el correo tal como se escribió.
- **Argon2id con parámetros de configuración.** `password_hash` empieza por `$argon2id$` y declara los costes configurados; la contraseña y el hash nunca aparecen en un cuerpo, un registro ni un error.
- **Sin cambios para el usuario final.** No hay pantalla de inicio de sesión (TKT-008) ni alta de usuarios: hoy nadie puede iniciar sesión en producción (`PA-T13`).

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Operaciones `obtener_token_csrf`, `iniciar_sesion`, `obtener_sesion_actual` y `cerrar_sesion` | Las cuatro del borrador quedan implementadas tal cual, validadas contra sus esquemas (`TokenCsrf`, `CredencialesInicio`, `UsuarioActual`, `ErrorSesion`, `ErrorPermiso`, `ErrorValidacion`). **`docs/api/openapi.yaml` no cambia**. El `403` y el `429` que el borrador declara en `iniciar_sesion` y `cerrar_sesion` son de TKT-057 | No |
| `cimenta.identidad.interfaz` | De solo un docstring a seis nombres publicados: `sesion_vigente`, `exigir_rol`, `UsuarioAutenticado`, `evaluar_resolucion`, `ResultadoResolucion` y `MotivoNegacion`. `registrar_denegacion` **no** se publica | No: no existía ningún consumidor |
| Esquema de base de datos | Migración `0004`: restricción `ck_usuario_email_minusculas`, reversible. Una sola cabeza de Alembic. La subida falla si hay un correo con mayúsculas y no los reescribe; hoy no existe ningún usuario | No: aditiva |
| Dependencias de ejecución | `pwdlib[argon2]` y `email-validator` | No, pero el PR añade dos dependencias directas y cinco transitivas |
| `crear_aplicacion` | Firma `crear_aplicacion(*, destino_registro, motor, reloj, entorno)`. Sin los tres parámetros nuevos el comportamiento es el de producción. `principal.py` y `aplicacion_con_secreto.py` no cambian | No: parámetros opcionales |
| Cookies | `cimenta_sesion` (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, identificador opaco) y `cimenta_csrf` (legible desde JavaScript). Con `Secure`, un cliente en `http://` no devuelve la cookie: las pruebas usan `base_url="https://testserver"` | No: las define el borrador |
| TC-75 de TKT-005 | **Reescrito** por la decisión D-2. Afirma ahora que el camino del error no toca la base y deja de mirar qué módulos se cargan. Debe señalarse a la persona que aprueba el PR | Sí, para el test: su afirmación anterior ya no es cierta |
| Variables de entorno | Cinco nuevas y opcionales: `CIMENTA_SESION_CADUCIDAD_MINUTOS`, `CIMENTA_SESION_INACTIVIDAD_MINUTOS`, `CIMENTA_ARGON2_TIEMPO`, `CIMENTA_ARGON2_MEMORIA_KIB` y `CIMENTA_ARGON2_PARALELISMO` | No |
| Contratos de `import-linter` | Ninguno cambia: son 15 antes y después, sin `ignore_imports`. `identidad` importa `auditoria` por su interfaz; `auditoria` no importa `identidad`; la raíz solo importa `cimenta.identidad.api.montaje` | No |
| Invariantes 10, 20 y 21 | Intactos: `intento_acceso` solo recibe `INSERT`, `bitacora` solo `INSERT` desde este ticket y el rol de lectura sigue sin ver `sesion` ni `password_hash` (`CA-R1`) | No |

## Decisiones (ADR)

Se creó [ADR-023](../../../docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md). Las decisiones restantes se recogen aquí con sus opciones descartadas; las que no llevan ADR quedan registradas en `_index.md` y en `design.md`.

### 2026-10-21 — ADR-023: sesión y autorización por dependencia de FastAPI

**Contexto:** ADR-014 fija que la sesión vive en una tabla y que el permiso se lee de la base en cada petición. Faltaba decidir dónde se valida la sesión, cómo declara cada ruta su rol, cómo se mantiene `ultima_actividad`, dónde se asienta un `DENEGAR` y de dónde sale la hora.
**Opciones consideradas:** para la validación, una dependencia `sesion_vigente` (elegida), un *middleware* (no sabe qué rol exige la ruta, no publica el esquema `sesion` y haría E/S bloqueante en el bucle de eventos, que ADR-013 prohíbe) y un decorador propio (FastAPI no lo ve como dependencia y el enrutador no se puede recorrer). Para el rol, `dependencies=[Depends(exigir_rol(...))]` por ruta (elegida), comprobarlo dentro del caso de uso y una tabla central de roles por `operationId`. Para la actividad, escribirla en cada petición con la guarda `revocada_en IS NULL` (elegida), escribirla cada N minutos y `SELECT ... FOR UPDATE`. Para el `DENEGAR`, transacción propia con fallo absorbido (elegida), la transacción de la petición y responder `500` si la bitácora falla. Para la hora, reloj inyectable (elegida) frente a `datetime` en el dominio.
**Decisión:** la elegida en cada caso. La sesión deslizante escribe una fila por petición autenticada, coste que ADR-014 ya aceptó.
**Evidencia:** TC-41, con dos transacciones reales, y MT-9 para la carrera entre cierre y petición; TC-47 para el recorrido del enrutador; TC-62 a TC-64 y MT-13 y MT-14 para el `DENEGAR`; TC-10 y MT-12 para la regla sin roles.
**Consecuencias:** cada petición autenticada escribe una fila. Una ruta que conserve `sesion_vigente` y olvide `exigir_rol` queda abierta a cualquier usuario autenticado, y TC-47 solo vigila la sesión: lo cubre la revisión de cada ticket. `auditoria` no puede proteger su ruta importando `identidad`.

### 2026-10-22 — Validación del correo con `email_validator` y `test_environment=True`

**Contexto:** el diseño validaba el correo con `pydantic.networks.validate_email`. En la fila 7 se vio que rechaza `ana@cimenta.test`, el usuario que usan los escenarios de la spec, porque `.test` es un dominio reservado.
**Opciones consideradas:** `validate_email` de Pydantic (descartada: rechaza los dominios reservados y la spec no entraría); `EmailStr` (descartada desde el diseño: normaliza el dominio y `CA-2` exige guardar el correo tal como se escribió); `email_validator` directo con `check_deliverability=False` y `test_environment=True`, que devuelve el valor original (elegida).
**Decisión:** la tercera, y `email-validator` pasa a dependencia directa. Decidió el usuario.
**Evidencia:** fila 7 de `impl.md` y `CA-2`; `test_tkt006_ca02_*` comprueban el correo original en `intento_acceso`.
**Consecuencias:** `test_environment=True` acepta dominios reservados también en producción. Cuando exista el alta de usuarios, quien la diseñe decide si ese modo sigue siendo el adecuado.

### 2026-10-21 — La no-auto-autorización no lleva `RN-xx` (`PA-T1`) y no recibe roles (D-5)

**Contexto:** ninguna de las reglas `RN-01` a `RN-25` enuncia que nadie autoriza lo suyo; la sostienen arquitectura §7.1, `HDU-003` esc. 8 y el motivo `AUTO_RESOLUCION` del borrador.
**Opciones consideradas:** inventar un `RN-xx` (descartada: el proyecto no inventa reglas); no implementarla hasta que el PRD la numere (descartada: `HDU-003` esc. 8 quedaría sin mecanismo); implementarla `(asumido)` sin identificador y con el motivo (elegida). Para su firma, recibir `roles_resolutor` y no usarlo, o no recibirlo (elegida, D-5).
**Decisión:** `evaluar_resolucion(*, solicitante_id, resolutor_id)`, sin roles: así ningún rol puede eximir por construcción, aunque sea `DIRECCION_GENERAL`. La falta de rol es `ROL_INSUFICIENTE` y la decide `api/`.
**Evidencia:** TC-09 con `DIRECCION_GENERAL` y el mutante MT-12 (`!=` en lugar de `==`).
**Consecuencias:** `CA-13` esc. 1 decía «recibe los roles de quien resuelve»; el diseño lo aclaró y el usuario aprobó D-5. El PRD debería reconocer la regla.

### 2026-10-21 — C-1 y D-3 enmendados por TKT-007

**Contexto:** el diseño atribuía un `403` sin recurso a la sesión. TKT-007 decidió, con el usuario, atribuirlo al usuario (`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`) y sin `correlacion_id` en `datos`, y entregó `url_aplicacion`, `crear_motor_aplicacion` y la *fixture* `motor_aplicacion`.
**Opciones consideradas:** la sesión (descartada: su identificador es la credencial de la cookie y el rol de lectura lee la bitácora, invariante 21) y la correlación (descartada: va al registro técnico).
**Decisión:** la atribución al usuario. La fila 10 comparó la firma real de `asentar_denegacion` con C-1 antes de empezar y coincidió.
**Evidencia:** `impl.md`, fila 10, «Comprobación previa»; MT-21.
**Consecuencias:** el delta de TKT-007 ya señaló la enmienda; el PR de este ticket la hereda.

### Otras decisiones del diseño, sin ADR propio

- **TC-75 reescrito (D-2).** Alternativas descartadas: eliminarlo, o montar `identidad` con importación diferida en la fábrica (más código y una ruta de producción que depende de un indicador).
- **`consultar_bitacora` y `rutas_de` (D-4).** TKT-007 no monta su ruta; la monta TKT-027 desde la raíz de composición con `exigir_rol`. Alternativas descartadas: una arista `auditoria → identidad`, que crea un ciclo con `identidad → auditoria`, o mover la ruta a otro módulo.
- **Dos entregas en un ticket (D-1)** y **escribir `ultima_actividad` en cada petición (D-9)**, frente a un solo PR o a escribir solo si pasó más de un minuto.
- **`PA-T5` y `PA-T6`.** Un `422` no se asienta en `intento_acceso`, y una bitácora caída deja `403` y registro técnico. Se confirmaron con el usuario.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| El test que recorre el enrutador baja por `original_router.routes` y ve las dependencias declaradas en la ruta, pero **no** las que se pasan a `include_router(..., dependencies=[...])`: esa ruta protege en ejecución y el test la reporta como sin proteger. Hay que declarar `exigir_rol` en el decorador de la ruta o ampliar `rutas_de` | TC-47 y su sección en `impl.md`; ADR-023, «Negativas o costes aceptados» | TKT-027, que monta `consultar_bitacora` desde la raíz de composición, y la prueba de contrato de TKT-061 |
| El hash de descarte debe derivarse con el **mismo** `PasswordHash` y los mismos costes que los hashes reales, y calcularse al construir el adaptador. Con costes distintos, la diferencia de tiempo delataría qué cuentas existen. «Tiempo constante» no se prueba por reloj: se prueba por conteo, una verificación por intento | TC-17 (compara los parámetros del hash), TC-26 y la objeción 4 de la spec | Cualquier flujo que verifique credenciales, y el alta de usuarios |
| **Calcular dentro de `begin()` y lanzar fuera.** Un `raise` dentro del bloque de `sessionmaker.begin()` deshace la fila de `intento_acceso`, justo en el rechazo que `RNF-04` necesita contar. El caso de uso guarda el resultado, sale del bloque, la transacción confirma y entonces lanza el `401` | TC-27, MT-7 y la objeción 1 de la pasada adversarial | Todo caso de uso que deba dejar rastro de lo que rechaza (TKT-057 contará esos intentos) |
| `pydantic.networks.validate_email` rechaza dominios reservados como `.test`, y `EmailStr` normaliza el dominio. Para guardar el correo tal como se escribió y aceptar la semilla de las pruebas se usa `email_validator` con `check_deliverability=False` y `test_environment=True` | Fila 7 de `impl.md`; decisión del usuario del 2026-10-22 | Todo DTO con correo, y el alta de usuarios (`PA-T13`) |
| `functools.cache` sobre una función que recibe una `Session` nunca acierta, porque cada petición abre la suya y el argumento no se repite. Un mutante de caché a ese nivel sobrevive aunque la garantía —«los roles se leen en cada petición»— se rompa en la práctica. El test que lo mata trabaja a nivel de repositorio, con la misma sesión | MT-10 literal y `test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada` | Todo mutante de caché; la garantía de no-caché se prueba con el argumento repetido |
| Un test que lanza `lint-imports` como subproceso depende de la codificación de la consola de Windows: sin `env` con `PYTHONIOENCODING=utf-8`, el subproceso escribe en cp1252, el hilo lector muere con `UnicodeDecodeError` y el síntoma es un `TypeError` sobre `None`. Los otros cuatro archivos ya lo hacían; el nuevo copió el `encoding` y no el `env` | `impl.md`, «Revisión · ciclo 1 · fragilidad de codificación en un test»; encontrado por `auditor-seguridad` | Todo test que lance un subproceso en Windows; conviene una ayuda compartida en `conftest.py` |
| El rojo de una fila puede nacer por la **firma de la fábrica** y no por la lógica: `conftest.py` llama a `crear_aplicacion(motor=..., reloj=..., entorno=...)` desde la fila 4, y hasta la fila 7 `mypy .` y `test_tkt005_car2_calidad_estatica_sin_hallazgos[mypy]` fallan con tres `call-arg`. Es un rojo previsto que cada fila intermedia debe anotar para no confundirlo con una regresión | `impl.md`, filas 5, 6 y 8, donde se registran los tres `call-arg` de `tests/conftest.py:494` | Todo ticket cuyas *fixtures* se escriban antes de la firma que usan |
| Un `password_hash` que no es Argon2 hace que `pwdlib` lance `UnknownHashError`: sin capturarla, el inicio de sesión responde `500` para esa cuenta y `401` para las demás (enumera cuentas) y la fila de `intento_acceso` se deshace. `verificar` devuelve `False` ante ese error | `F3` de `/sdd-revisar`, reproducido por dos auditores; 11 casos en rojo y luego en verde | Todo adaptador sobre una biblioteca que lanza ante datos almacenados con forma inesperada |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto. Se añadieron a [`_evolucion.md`](../../_evolucion.md) en `/sdd-completar`; esta tabla las resume.

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Siguen faltando `desarrollador-aplicacion`, `desarrollador-api`, `auditor-sql`, `auditor-codigo`, `auditor-docs`, `revisor-impacto` y `meta-sdd`. Octava vez: ya hay trece filas del tema `agente`, nueve de ellas sobre agentes ausentes antes de esta | Alta |
| `comando` | El diseño dijo `validate_email` y chocó con la spec: rechaza `ana@cimenta.test`. Quinta vez que un diseño afirma sin ejecutar | Alta |
| `comando` | El orden sumó unas 2,700 líneas, casi siete veces el tope de 400, en dos entregas sobre una rama. Quinta vez | Media |
| `herramienta` | Un test dependía de la codificación de la consola de Windows. Quinta vez en la familia de codificación y finales de línea | Media |
| `agente` | La reauditoría dio tres ciclos por la redacción de las secciones de cierre que escribió el orquestador. Tercera vez; se propone un criterio de parada | Media |
| `contexto` | El límite de uso mató a un subagente a mitad y hubo que reanudarlo con `SendMessage`. Tercera vez | Media |
| `guardrail` | `/sdd-revisar` encontró un defecto real de comportamiento, el `500` por un hash no válido, que la auditoría de arquitectura de `/sdd-ejecutar` no vio, que los mutantes no podían ver y que la de seguridad dejó como Menor opcional. Tercera vez | Alta |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Alta de usuarios y del primer usuario (`PA-T13`): sin una operación que cree usuarios y asigne roles, nadie inicia sesión en producción. Al diseñarla, que derive siempre el hash con `ContrasenasArgon2` y que revise si `lower()` de Python y de PostgreSQL difieren con caracteres no ASCII | El borrador no tiene operación de administración de usuarios y el ticket la declaró Won't | Ticket nuevo de alta de usuarios |
| TKT-057: verificación del doble envío CSRF, rotación del token, `429`, límite de intentos y `bloqueado_hasta`, cabeceras de seguridad (`Cache-Control` incluida), tope de cuerpo y de longitud de contraseña, suelo mínimo y re-derivación de los costes de Argon2, `pydantic-settings` para las cinco variables y qué pasa con `/docs` y `/openapi.json` | Son de ese ticket por la decisión del usuario del 2026-10-21 | TKT-057 |
| Desactivar a un usuario no persiste `revocada_en`: si se reactiva dentro de la ventana de inactividad, la cookie vuelve a servir | No existe todavía la operación de desactivar | El ticket de desactivación debe revocar las sesiones en la misma transacción |
| El mensaje de `SESION_REVOCADA` difiere del ejemplo del borrador en dos signos (`.` frente a `;`, y «Inicia» frente a «inicia») | El borrador lo declara en un `example:` y no se tocó | Decide el usuario cuál manda al tocar el borrador |
| La cookie no usa el prefijo `__Host-` (`F003` de seguridad) | Cambiaría el nombre que fija el borrador | Un cambio futuro del borrador |
| `expira_por_inactividad_en` puede mostrar un instante posterior a la caducidad absoluta | El cliente aún no existe | TKT-008: mostrar el mínimo de los dos |
| Cerrar una sesión ya caducada no expira la cookie; `_como_uuid` acepta formas no canónicas de UUID; ningún test fija que el `except` de `verificar` sea estrecho (un `except Exception` mantendría la suite en verde) | Observaciones que no bloquean, de `/sdd-revisar` | Sin ticket; al tocar `contrasenas.py` o `sesiones.py` |
| Una ruta que conserve `sesion_vigente` y olvide `exigir_rol` queda abierta a cualquier usuario autenticado: TC-47 solo vigila la sesión | Es un riesgo aceptado en ADR-023: lo cubre la revisión de cada ticket | TKT-061 puede automatizar la comparación de cada ruta con su `x-roles` |
| Un usuario autenticado sin permiso puede generar `DENEGAR` sin límite | El límite es de TKT-057 | TKT-057 |
| `abrir_sesion` verifica el hash dentro de una transacción abierta y retiene una conexión del pool durante la derivación | El límite de intentos de TKT-057 lo mitiga | TKT-057 |
| `NO_ES_SOLICITANTE` y `AUTO_RESOLUCION` no se asientan solos: nacen en el caso de uso y `exigir_rol` solo asienta `ROL_INSUFICIENTE`. `registrar_denegacion` no se publica en la interfaz | No hay consumidor todavía | TKT-021, TKT-026 y TKT-027 llevan el criterio de asentarlos por la interfaz de auditoría; si hace falta un ayudante compartido, se publica entonces |
| `rutas_de` no lee `include_router(..., dependencies=[...])`, así que TC-47 vería la ruta de `consultar_bitacora` como sin proteger | Se descubrió en la ejecución; el diseño aprobado no lo preveía | TKT-027: declarar `exigir_rol` en el decorador de la ruta o ampliar `rutas_de` |
| Origen de los roles que exige cada acción: hoy cada ruta copia `x-roles` del borrador (`PA-T2` de TKT-005) | Ningún documento fija un lugar único | Ticket que derive el catálogo de `x-roles` del borrador |
| El PRD no reconoce la no-auto-autorización (`PA-T1`) | No se inventa una `RN` | Que el PRD la numere o la anote en `HDU-003` |
| Purga de sesiones y destino del `DELETE` sobre `sesion` (`PA-T9`, `PA-T6` y `PA-T7` de TKT-003); permisos por obra y `NO_ENCONTRADO` (`PA-T11`); `origen_ip` como `inet` | Fuera de alcance declarado | Tickets futuros ya listados en `_index.md` |
| TKT-008: la cookie `Secure` en desarrollo local (un navegador que no trate `http://127.0.0.1` como contexto seguro no la guarda; `arranque-local.md` indica abrir en `http://localhost`) y un usuario con `roles: []` | El cliente no existe | TKT-008 |
| `spec.md` de este ticket conserva en `M11` la URL y el motor del rol de aplicación como alcance propio, aunque los entregó TKT-007 | La enmienda de TKT-007 corrigió `PA-T7` y la tabla de partida, no `M11`; este ticket no lo corrigió al ejecutar | Corregirlo en la rama antes de abrir el PR, o dejarlo como histórico de la spec |
| `servidor/correlacion.py` tiene un `async def __call__` (ASGI puro, anterior a este ticket) | Anterior a este ticket y exigido por ASGI | Sin ticket |
| `design.md` conserva código literal que `backend/` supera | Es el diseño aprobado en el gate | Ninguno: este delta lo supera |
| Las entregas A y B viven en una sola rama y sin commit | Los hunks de `pyproject.toml`, `conftest.py` y la documentación mezclan las dos | Si se quieren dos PR, separarlos al abrirlos |

## Pull request

**Título:** `TKT-006 · autenticación y autorización por rol`
**Origen:** `agent`
**Cuerpo:**

Qué: implementa la sesión con estado y la autorización por rol. `cimenta.identidad` añade las cuatro rutas de sesión del borrador (`GET /api/v1/sesion/csrf`, `POST /api/v1/sesion`, `GET /api/v1/sesion` y `POST /api/v1/sesion/cierre`), todas `def`, con cookie opaca `HttpOnly`, `Secure` y `SameSite=Lax`, contraseñas con Argon2id vía `pwdlib[argon2]` y caducidad absoluta e inactividad configurables. `sesion_vigente` lee la sesión y los roles de la base en cada petición, de modo que cerrar sesión, desactivar al usuario o retirar un rol surte efecto en la petición siguiente. `exigir_rol` declara el rol de cada ruta y asienta `DENEGAR` en una transacción propia. `evaluar_resolucion` implementa en el dominio que nadie autoriza lo suyo, sin `RN-xx`. La migración `0004` obliga a que el correo esté en minúsculas. ADR-023 recoge las decisiones.

Por qué: sin este ticket la aplicación no sabe quién le habla, no se puede proteger ninguna ruta y `RN-04` no puede decir quién autorizó un sobregiro. Es la base de TKT-008, TKT-020, TKT-026 y TKT-057.

Criterios cubiertos: los 15 `[M]` (`CA-1` a `CA-15`), los dos `[S]` (`CA-16` y `CA-17`) y los siete de regresión (`CA-R1` a `CA-R7`) de `sdd/tickets/tkt-006/spec.md`. Suite completa con Docker: 1138 pruebas en verde, sin `PYTHONUTF8`; 15 contratos de `import-linter`, `ruff`, `mypy` y `verificar_float` limpios; una sola cabeza de Alembic (`0004`); `pip-audit` limpio. 16 mutantes en la entrega A y 14 distintos en la B; el único superviviente, el `MT-10` literal, se cubrió con un test nuevo. Auditoría de seguridad `APROBADO` con tres Menores opcionales; auditoría de arquitectura con tres ciclos de corrección y una pasada independiente en `/sdd-revisar` que encontró y corrigió, con el rojo primero, un `500` por un hash que no es Argon2.

**Para quien aprueba, con atención:**
- **Este PR reescribe un test de TKT-005.** TC-75 ya no afirma que construir la aplicación no carga SQLAlchemy, porque montar `identidad` lo carga. Ahora afirma que el camino del error no toca la base. Es la decisión D-2 del diseño.
- **Añade dependencias y una migración.** `pwdlib[argon2]` y `email-validator` (esta última por decisión del usuario del 2026-10-22: `test_environment=True`, para aceptar `ana@cimenta.test`), con sus cinco paquetes transitivos en `uv.lock`, y la migración `0004`.
- **No toca `docs/api/openapi.yaml`**: las cuatro operaciones ya estaban en el borrador.
- Hereda la enmienda de TKT-007 sobre el diseño de este ticket: un `403` sin recurso se atribuye al usuario.
- Los supuestos `(asumido)`: caducidad de 12 horas y 30 minutos, usuario desactivado con sesión abierta responde `SESION_REVOCADA`, y la no-auto-autorización sin `RN-xx` (`PA-T1`).
- Hoy nadie puede iniciar sesión en producción: no hay alta de usuarios (`PA-T13`).
- `desarrollador-aplicacion`, `desarrollador-api`, `auditor-sql`, `auditor-codigo`, `auditor-docs` y `revisor-impacto` no existen en este entorno y se sustituyeron.

Cómo verificarlo, con `uv` y Docker instalados:

```bash
cd backend && uv sync --locked
uv run pytest tests/test_tkt006_dominio.py tests/test_tkt006_enrutador.py tests/test_tkt006_configuracion.py   # sin Docker
uv run pytest && uv run ruff check . && uv run mypy . && uv run lint-imports
uv run python -m herramientas.verificar_float
uv run --env-file ../.env alembic heads   # una sola cabeza: 0004
cd .. && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en `sdd/tickets/tkt-006/delta.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
