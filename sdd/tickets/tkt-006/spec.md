# Spec · TKT-006 · Autenticación y autorización por rol

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

Hoy CIMENTA no sabe quién le habla. La aplicación servible de TKT-005 no tiene ninguna ruta de negocio, el esquema de identidad de TKT-003 existe pero nadie lo lee ni lo escribe, y el manejador de errores ofrece acciones a nadie porque nadie fija los roles de quien llama (fallo seguro deliberado). Sin este ticket no se puede proteger ninguna ruta, no se puede decir quién autorizó un sobregiro (`RN-04`) y la pantalla de inicio de sesión de TKT-008 no tiene contra qué probarse.

Este ticket de fundación entrega el ciclo completo de la sesión con estado ([ADR-014](../../../docs/adr/20260919-sesion-con-estado.md)): iniciar sesión, reconocerla en cada petición, cerrarla, y decidir qué rol puede hacer qué. Entrega también la regla de que nadie autoriza lo suyo, como función pura de `dominio/`, y el asiento `DENEGAR` de todo `403` con usuario autenticado.

Estado de partida, criterio por criterio del ticket:

| Criterio del ticket | Estado de partida |
|---|---|
| Inicio y cierre de sesión con `pwdlib[argon2]` | No existe. `pwdlib` no está en `backend/pyproject.toml`. No hay ninguna ruta de identidad |
| Hash verificado siempre, exista o no el usuario | No existe |
| Sesión con estado, cookie opaca `HttpOnly`/`Secure`/`SameSite=Lax` | La tabla `sesion` existe (TKT-003, `v0001`); ningún código la lee ni la escribe |
| Caducidad absoluta y por inactividad; cerrar escribe `revocada_en` | Las columnas `expira_en`, `ultima_actividad` y `revocada_en` existen; sin lógica |
| Desactivar usuario o retirar rol surte efecto en la petición siguiente | No existe |
| Permiso por rol en `api/` | `contrato_error` ya define `SesionInvalida`, `PermisoDenegado` y el catálogo `Rol`; `servidor/manejadores.py` lee `request.state.roles_de_quien_llama`, que nadie fija |
| Un usuario con varios roles; permiso efectivo = unión | `usuario_rol` existe con `UNIQUE (usuario_id, rol_id)`; los seis roles están sembrados (`v0002`) |
| Regla de no-auto-autorización en `dominio/` | No existe. **Ninguna `RN-xx` la respalda** (ver «Reglas de negocio implicadas») |
| `403` asentado como `DENEGAR` en transacción propia | No existe la tabla `bitacora` ni su servicio: son de TKT-007, que **no es dependencia declarada** del ticket |
| Solo dos rutas sin sesión; test que recorre el enrutador | No existe |
| URL y motor del rol de aplicación, modelos ORM, normalización del correo | `url_aplicacion` y `crear_motor_aplicacion` los entrega TKT-007; modelos ORM y normalización del correo no existen (`herramientas/conexion.py` solo construye la URL de migración; `PA-T10` de TKT-003) |

La spec parte de tres decisiones del usuario, tomadas el 2026-10-21 en el intake, y de la validación del Must:

1. **CSRF.** TKT-006 monta `GET /sesion/csrf`, que **emite** la cookie `cimenta_csrf` y el token, y lo incluye en la lista cerrada de rutas sin sesión. La **verificación** del doble envío, el `429` y `ORIGEN_NO_VERIFICADO` son de TKT-057.
2. **`DENEGAR`.** TKT-007 pasa a ser dependencia de TKT-006 y se ejecuta antes. El asiento de `DENEGAR` es parte del Must.
3. **No-auto-autorización.** La implementa TKT-006, como función pura en `identidad/dominio`, **sin `RN-xx`**, con motivo `AUTO_RESOLUCION`. TKT-026 la reutiliza y no la reescribe.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario propia. Los seis roles del PRD §4 lo usan: todos inician sesión y todos reciben, o se les niega, lo que su rol permite. Los escenarios con nombre `HDU-xxx` que dependen de él —`HDU-003` esc. 7 y 8, `HDU-001` esc. 23, `HDU-002` esc. 11, `HDU-006` esc. 12— los implementan los tickets consumidores; aquí se entrega el mecanismo que esos escenarios invocan.

**Como** cualquiera de los seis roles del PRD §4
**quiero** iniciar sesión con mi correo y mi contraseña y que el sistema me reconozca en cada petición según los roles que tengo en ese momento
**para** que solo yo, y solo con lo que mi rol permite, pueda autorizar o consultar gasto, y para que quitarme un rol o desactivarme surta efecto de inmediato.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** `GET /sesion/csrf` (`obtener_token_csrf`): fija la cookie `cimenta_csrf` (sin `HttpOnly`) y devuelve el mismo valor en el cuerpo. Sin sesión. La verificación en las rutas que mutan no entra |
| | **M2.** `POST /sesion` (`iniciar_sesion`): contraseña verificada con Argon2id vía `pwdlib[argon2]` **siempre**, exista o no el correo, contra un hash de descarte cuando no está. Crea la fila en `sesion` y fija la cookie `cimenta_sesion` con un identificador opaco, `HttpOnly`, `Secure`, `SameSite=Lax`. Cada intento se asienta en `intento_acceso`. Credenciales erróneas: `401` `SESION` `CREDENCIALES_INVALIDAS`, anónimo, sin bitácora |
| | **M3.** `GET /sesion` (`obtener_sesion_actual`): devuelve usuario, roles y caducidades, con los roles leídos de la base en cada petición |
| | **M4.** `POST /sesion/cierre` (`cerrar_sesion`): escribe `revocada_en`, no borra la fila, expira la cookie y responde `204` |
| | **M5.** Caducidad absoluta (`expira_en`) y por inactividad (`ultima_actividad`) `(asumido)`: una sesión vencida responde `401` `SESION_CADUCADA` |
| | **M6.** Desactivar un usuario o retirarle un rol surte efecto en la petición siguiente, con un test por cada caso |
| | **M7.** Dependencia de sesión en `api/` que reconoce la cookie, fija `request.state.roles_de_quien_llama` como `frozenset[str]` en cada petición y lanza `SesionInvalida` o `PermisoDenegado`, nunca `HTTPException`. Comprobación de rol por ruta; permiso efectivo = unión de los roles del usuario |
| | **M8.** Regla de no-auto-autorización en `identidad/dominio`, pura, probada sin HTTP ni base de datos. Quien resuelve una solicitud de autorización no puede ser quien la solicitó, aunque tenga `DIRECCION_GENERAL` |
| | **M9.** Todo `403` con usuario autenticado se asienta como `DENEGAR` mediante el servicio de TKT-007, en una transacción propia. Las denegaciones anónimas no van a la bitácora |
| | **M10.** Test que recorre el enrutador (bajando por `original_router.routes`) y falla si cualquier ruta distinta de `GET /sesion/csrf` y `POST /sesion` queda sin dependencia de sesión |
| | **M11.** Base mínima: URL y motor del rol de aplicación, modelos ORM de `identidad`, configuración de los parámetros de Argon2 y de las caducidades, y el correo normalizado a minúsculas (cierra `PA-T10`) |
| | **M12.** Consecuencia documental: declarar TKT-007 como dependencia de TKT-006 en `docs/05-tickets-trabajo.md`; aclarar en ese ticket que emite el token y no verifica el doble envío; alinear la especificación de la API §4.1, que asigna la ruta solo a TKT-057, y la dependencia de TKT-026 con la regla de M8 |
| **Should** | **S1.** La semilla de roles de `v0002` se ata al enum `Rol` de `contrato_error.catalogos`, con un test que falla si divergen (compromiso de TKT-005) |
| | **S2.** Una restricción de base de datos impide guardar un correo que no esté en minúsculas, además de la normalización en código. Requiere migración |
| **Could** | — |
| **Won't** | Recuperación de contraseña, segundo factor, inicio de sesión federado · permisos por obra y la deuda «obra no asignada → `NO_ENCONTRADO`» (el MVP autoriza por rol) · límite de intentos y `bloqueado_hasta`, verificación CSRF, `429`, `ORIGEN_NO_VERIFICADO` y cabeceras de seguridad (TKT-057) · alta de usuarios y asignación de roles (los tests siembran) · purga de sesiones y destino del `DELETE` sobre `sesion` (`PA-T6`, `PA-T7`) · `origen_ip` como `inet` · de dónde sale la tabla de roles por acción (`PA-T2`) · el escenario `NO_ES_SOLICITANTE` de `HDU-002` · escribir la bitácora de cambios (TKT-007) · pantalla de inicio de sesión (TKT-008) |

## Non-goals

- No implementa ninguna regla `RN-xx` de negocio. La regla de M8 no tiene identificador en el PRD y no se le inventa uno.
- No verifica el token CSRF en ninguna ruta. `iniciar_sesion` y `cerrar_sesion` lo declaran en el borrador, pero quien lo exige es TKT-057.
- No limita intentos ni bloquea cuentas: ignora `usuario.bloqueado_hasta`.
- No crea usuarios ni asigna roles por la API. No hay operación de administración de usuarios en el borrador.
- No añade permisos por obra ni cambia el rol `RESIDENTE` a «solo su obra».
- No cambia el esquema de TKT-003, salvo la restricción opcional de S2.
- No modifica `docs/api/openapi.yaml`: el borrador ya declara las cuatro operaciones.

## Reglas de negocio implicadas

Ninguna `RN-xx` se implementa. La autenticación y la autorización por rol sostienen el cumplimiento de reglas ajenas.

| Referencia | Qué exige | Dónde está |
|---|---|---|
| `RN-04` | Toda autorización y todo rechazo se registran con actor, momento y motivo, de forma permanente. Fundamenta el asiento `DENEGAR` | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RNF-01` | La sesión tiene estado en el servidor y es revocable: cerrar sesión, desactivar o retirar un rol surte efecto en la petición siguiente | PRD §9 |
| `RNF-02` | La credencial de sesión no es legible desde JavaScript y viaja por canal cifrado | PRD §9 |
| `RNF-03` | Contraseñas con derivación lenta y parámetros en configuración | PRD §9 |
| `RNF-04` | Intentos de acceso registrados. **El límite es de TKT-057**; aquí solo se registra el intento | PRD §9 |
| `RNF-13` | Registro técnico con correlación, separado de la bitácora: las denegaciones anónimas van ahí | PRD §9 |
| Regla 9 de `CLAUDE.md` | Ni JWT ni cookie firmada autocontenida | `CLAUDE.md` |
| Regla 11 de `CLAUDE.md` | Rutas `def`, nunca `async def` | `CLAUDE.md` |
| Regla 2 de `CLAUDE.md` | `dominio/` no importa nada: la regla de M8 no puede importar `pwdlib`, `contrato_error` ni `datetime` ([ADR-021](../../../docs/adr/20261019-lista-blanca-del-dominio.md)) | `CLAUDE.md` |

> **Hallazgo documental (`PA-T1`).** La prohibición de auto-autorización **no tiene regla en el PRD**: ninguna de `RN-01` a `RN-25` la enuncia. Solo la sostienen arquitectura §7.1, `HDU-003` esc. 8 y el motivo `AUTO_RESOLUCION` del borrador. Por eso el rechazo lleva `motivo: AUTO_RESOLUCION` y **nunca** `regla`. El usuario decidió implementarla aquí `(asumido)`; queda como pregunta abierta que el PRD la reconozca.

Términos del [glosario](../../../docs/glosario.md): el glosario no define *rol de sistema*, *sesión* ni *bitácora*. No debe confundirse el rol de sistema (`usuario_rol`) con el **rol de oficio** del glosario (pastero, tablaroquero).

## Invariantes que deben sobrevivir al cambio

El ticket modifica archivos que ya funcionan (`pyproject.toml`, `uv.lock`, `servidor/fabrica.py`, `herramientas/conexion.py`, `interfaz.py` de `identidad`) y empieza a leer y escribir tablas que TKT-003 dejó vigiladas.

| Invariante o garantía | Qué protege | Criterio de regresión |
|---|---|---|
| Inv. 20 · `intento_acceso` solo admite `INSERT` y `SELECT` | Que el registro de intentos no se reescriba. El inicio de sesión inserta; nunca actualiza ni borra | `CA-R1` |
| Inv. 21 · el rol de lectura no ve `sesion` ni `usuario.password_hash` | Que ninguna columna nueva ni consulta de TKT-006 abra esa lectura | `CA-R1` |
| Inv. 10 · la bitácora no se modifica | Que el asiento `DENEGAR` solo use `INSERT` | `CA-R1` |
| `v0001` y `v0002` siguen aplicando y revirtiéndose | Esquema de identidad y semilla de los seis roles | `CA-R2` |
| Los 15 contratos de `import-linter` en verde, sin `ignore_imports` | `dominio/` sin framework; `identidad` puede importar `auditoria` y `auditoria` no importa `identidad`; la raíz `servidor/` solo monta `cimenta.<modulo>.api` | `CA-R3` |
| Ruff, mypy y `verificar_float` en verde | Sin `float`; tipos | `CA-R4` |
| La suite existente sigue en verde con el rol de aplicación | TKT-003 a TKT-005, sin tocar `conftest.py` de forma incompatible | `CA-R4` |
| Los cuerpos `401` y `403` siguen cumpliendo `ErrorSesion` y `ErrorPermiso` del borrador, con `correlacion_id` | Contrato de TKT-005; ningún `HTTPException` filtra `{"detail": …}` | `CA-R5` |
| Toda ruta nueva es `def` | Regla 11 | `CA-R6` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde; archivos sin BOM y con LF | Enlaces, identificadores, conteos y codificación | `CA-R7` |

## Criterios de aceptación

Gherkin, en español. Cada respuesta se valida contra su esquema de [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml). Las rutas de prueba para la dependencia de sesión son rutas de la suite, no del producto. Los tests se conectan con el rol de aplicación.

### CA-1 `[M]` · El token CSRF se emite sin sesión · M1

```gherkin
Escenario: Se pide el token sin haber iniciado sesión
  Dado una petición sin cookie de sesión
  Cuando se llama GET /api/v1/sesion/csrf
  Entonces la respuesta es 200 con un cuerpo TokenCsrf de al menos 32 caracteres
  Y la cabecera Set-Cookie fija cimenta_csrf con el mismo valor, sin HttpOnly, con Secure y SameSite=Lax
  Y la respuesta lleva X-Correlacion-Id

Escenario: Rechazo — dos peticiones no comparten token
  Dado dos peticiones consecutivas a GET /api/v1/sesion/csrf
  Cuando se comparan los tokens
  Entonces son distintos
  Y ninguno aparece repetido en una muestra de cien emisiones
```

### CA-2 `[M]` · Inicio de sesión correcto · M2, M11

```gherkin
Escenario: Un usuario activo inicia sesión
  Dado el usuario "ana@cimenta.test" activo, con rol DIRECTOR_PROYECTOS y una contraseña conocida
  Cuando se llama POST /api/v1/sesion con su correo y su contraseña
  Entonces la respuesta es 200 con un cuerpo UsuarioActual: id, nombre, email, roles y las dos caducidades
  Y existe una fila en sesion con usuario_id, creada_en, expira_en, ultima_actividad y revocada_en nulo
  Y Set-Cookie fija cimenta_sesion con el id de esa fila, HttpOnly, Secure, SameSite=Lax y Path=/
  Y el cuerpo no contiene la contraseña ni password_hash
  Y existe una fila en intento_acceso con exitoso verdadero, el usuario y el correo tal como se escribió
  Y usuario.ultimo_acceso queda actualizado

Escenario: El correo se compara sin distinguir mayúsculas
  Dado el usuario guardado como "ana@cimenta.test"
  Cuando inicia sesión escribiendo "Ana@Cimenta.TEST"
  Entonces la respuesta es 200 con el mismo usuario
  Y intento_acceso guarda el correo tal como se escribió: "Ana@Cimenta.TEST"

Escenario: La cookie no lleva datos del usuario
  Dado una sesión recién abierta
  Cuando se lee el valor de cimenta_sesion
  Entonces es el id opaco de la fila de sesion
  Y no contiene ni decodifica a ningún dato del usuario, de sus roles ni una firma
```

### CA-3 `[M]` · Rechazo · Credenciales erróneas, sin revelar qué cuentas existen · M2

```gherkin
Escenario: Contraseña equivocada
  Dado el usuario "ana@cimenta.test" activo
  Cuando se llama POST /api/v1/sesion con una contraseña incorrecta
  Entonces la respuesta es 401 con tipo "SESION" y motivo "CREDENCIALES_INVALIDAS"
  Y el cuerpo valida contra ErrorSesion y lleva correlacion_id
  Y no se crea ninguna fila en sesion ni se fija cimenta_sesion
  Y intento_acceso recibe una fila con exitoso falso y el usuario
  Y la bitácora no recibe ningún asiento

Escenario: Correo que no existe
  Dado que ningún usuario tiene el correo "nadie@cimenta.test"
  Cuando se llama POST /api/v1/sesion con ese correo y cualquier contraseña
  Entonces la respuesta es 401 con el mismo tipo, motivo y mensaje que en la contraseña equivocada
  Y los dos cuerpos solo difieren en correlacion_id
  Y intento_acceso recibe una fila con exitoso falso y usuario_id nulo

Escenario: El hash se verifica siempre
  Dado un contador sobre la verificación de contraseña
  Cuando se inicia sesión con un correo que no existe, y después con un correo que existe y una contraseña errónea
  Entonces cada llamada verifica exactamente una vez contra un hash de Argon2id
  Y el hash de descarte usa los mismos parámetros que los hashes reales

Escenario: El intento fallido sobrevive al rechazo
  Dado una contraseña equivocada que responde 401
  Cuando termina la petición
  Entonces la fila de intento_acceso sigue en la base: el rechazo no deshace el registro del intento
```

### CA-4 `[M]` · Rechazo · Usuario desactivado no inicia sesión · M2, M6

```gherkin
Escenario: Un usuario con activo falso intenta iniciar sesión con su contraseña correcta
  Dado el usuario "ana@cimenta.test" con activo falso
  Cuando se llama POST /api/v1/sesion con su contraseña correcta
  Entonces la respuesta es 401 con motivo "CREDENCIALES_INVALIDAS", indistinguible de la contraseña equivocada
  Y no se crea fila en sesion
  Y se verificó un hash y intento_acceso recibe una fila con exitoso falso y el usuario
```

### CA-5 `[M]` · Rechazo · Forma inválida del inicio de sesión · M2

```gherkin
Escenario: Correo mal formado o contraseña vacía
  Dado un cuerpo con email "no-es-un-correo", o con contrasena ""
  Cuando se llama POST /api/v1/sesion
  Entonces la respuesta es 422 con tipo "VALIDACION" y el campo infractor en el detalle
  Y el cuerpo valida contra ErrorValidacion
  Y no se verifica ningún hash ni se crea fila en sesion `(asumido: un cuerpo mal formado no se asienta en intento_acceso)`
```

### CA-6 `[M]` · La sesión vigente devuelve usuario y roles actuales · M3, M7

```gherkin
Escenario: Se consulta la sesión con la cookie vigente
  Dado una sesión abierta del usuario con los roles RESIDENTE y COMPRAS
  Cuando se llama GET /api/v1/sesion con su cookie
  Entonces la respuesta es 200 con UsuarioActual y los dos roles
  Y roles_de_quien_llama de esa petición es el conjunto {RESIDENTE, COMPRAS}
  Y sesion.ultima_actividad avanza al momento de la petición

Escenario: El permiso efectivo es la unión de los roles
  Dado una ruta de prueba que exige COMPRAS y otra que exige ALMACEN
  Y un usuario con ambos roles
  Cuando llama a cada una
  Entonces las dos responden 200
```

### CA-7 `[M]` · Rechazo · Sin sesión o con una cookie que no corresponde a nada · M7

```gherkin
Escenario: Petición sin cookie
  Dado una petición a GET /api/v1/sesion sin cookie
  Cuando se procesa
  Entonces la respuesta es 401 con tipo "SESION" y motivo "SIN_SESION"
  Y el cuerpo valida contra ErrorSesion y lleva correlacion_id
  Y la bitácora no recibe ningún asiento

Escenario: Cookie con un identificador inexistente o mal formado
  Dado la cookie cimenta_sesion con un UUID que no existe, y otra con el texto "abc"
  Cuando se llama GET /api/v1/sesion con cada una
  Entonces ambas responden 401 con motivo "SIN_SESION"
  Y la respuesta no distingue entre «no existe» y «mal formada»

Escenario: Ninguna ruta devuelve el cuerpo por omisión de FastAPI
  Dado cualquier rechazo de sesión o de permiso
  Cuando se lee el cuerpo
  Entonces no existe la clave "detail" y existe correlacion_id
```

### CA-8 `[M]` · Rechazo · Caducidad absoluta y por inactividad · M5

```gherkin
Escenario: Una sesión pasa su caducidad absoluta
  Dado una sesión cuya expira_en ya pasó
  Cuando se llama GET /api/v1/sesion con su cookie
  Entonces la respuesta es 401 con motivo "SESION_CADUCADA"
  Y la fila de sesion no se borra

Escenario: Una sesión pasa su caducidad por inactividad
  Dado una sesión cuya ultima_actividad es anterior al límite de inactividad y expira_en todavía no llega
  Cuando se llama GET /api/v1/sesion
  Entonces la respuesta es 401 con motivo "SESION_CADUCADA"

Escenario: La actividad desliza la inactividad pero no la caducidad absoluta
  Dado una sesión activa que hace peticiones espaciadas por menos del límite de inactividad
  Cuando se acerca expira_en
  Entonces la sesión sigue viva mientras no pase expira_en
  Y al pasar expira_en responde 401 con motivo "SESION_CADUCADA" aunque la última petición fuera reciente

Escenario: Los valores salen de la configuración
  Dado caducidad absoluta y de inactividad distintas en la configuración
  Cuando se abre una sesión
  Entonces expira_en refleja la caducidad absoluta configurada `(asumido: 12 h absoluta, 30 min de inactividad)`
```

### CA-9 `[M]` · Cerrar sesión revoca sin borrar · M4

```gherkin
Escenario: Se cierra la sesión vigente
  Dado una sesión abierta
  Cuando se llama POST /api/v1/sesion/cierre con su cookie
  Entonces la respuesta es 204
  Y la fila de sesion sigue existiendo con revocada_en escrito
  Y Set-Cookie expira cimenta_sesion

Escenario: Rechazo — la sesión cerrada ya no sirve
  Dado una sesión recién cerrada
  Cuando se llama GET /api/v1/sesion con la misma cookie
  Entonces la respuesta es 401 con motivo "SESION_REVOCADA"

Escenario: Rechazo — cerrar sin sesión
  Dado una petición a POST /api/v1/sesion/cierre sin cookie
  Cuando se procesa
  Entonces la respuesta es 401 con motivo "SIN_SESION"
  Y ninguna fila de sesion cambia

Escenario: El rol de aplicación no necesita borrar
  Dado el flujo completo de iniciar y cerrar sesión
  Cuando se revisan las sentencias ejecutadas
  Entonces ninguna es DELETE sobre sesion
```

### CA-10 `[M]` · Rechazo · Desactivar un usuario surte efecto en la petición siguiente · M6

```gherkin
Escenario: Se desactiva a un usuario con la sesión abierta
  Dado una sesión vigente del usuario "ana@cimenta.test"
  Cuando se pone usuario.activo en falso y a continuación llega la siguiente petición de esa sesión
  Entonces la respuesta es 401 con motivo "SESION_REVOCADA" `(asumido)`
  Y no hay caché de roles ni de estado que retrase el efecto
```

### CA-11 `[M]` · Rechazo · Retirar un rol surte efecto en la petición siguiente · M6, M7

```gherkin
Escenario: Se retira el rol exigido por una ruta
  Dado una ruta de prueba que exige COMPRAS y un usuario con COMPRAS que acaba de usarla con 200
  Cuando se borra su fila de usuario_rol para COMPRAS y llega la siguiente petición con la misma cookie
  Entonces la respuesta es 403 con tipo "PERMISO", motivo "ROL_INSUFICIENTE" y roles_requeridos ["COMPRAS"]
  Y el cuerpo valida contra ErrorPermiso y no incluye cifras del recurso
  Y roles_de_quien_llama de esa petición ya no contiene COMPRAS
```

### CA-12 `[M]` · Rechazo · Falta de permiso por rol, asentada como `DENEGAR` · M7, M9 · `RN-04`

```gherkin
Escenario: Un rol sin permiso intenta una ruta protegida
  Dado una ruta de prueba que exige DIRECCION_GENERAL y un usuario autenticado con RESIDENTE
  Cuando la llama
  Entonces la respuesta es 403 con tipo "PERMISO", motivo "ROL_INSUFICIENTE" y roles_requeridos ["DIRECCION_GENERAL"]
  Y la bitácora recibe un asiento con accion "DENEGAR", el usuario autenticado, el momento y el motivo
  Y el asiento no lleva regla_negocio

Escenario: El asiento va en una transacción propia
  Dado un 403 en una petición cuyo manejador deshace su propia transacción
  Cuando se consulta la bitácora tras la respuesta
  Entonces el asiento DENEGAR persiste: no depende de ningún cambio que acompañar

Escenario: Las denegaciones anónimas no entran en la bitácora
  Dado un inicio de sesión con credenciales erróneas y una petición sin cookie
  Cuando se revisa la bitácora
  Entonces no contiene ningún asiento de esas dos peticiones
  Y el intento fallido sí está en intento_acceso y el registro técnico lleva su correlacion_id

Escenario: Si la bitácora falla, el acceso sigue denegado
  Dado que el servicio de TKT-007 falla al asentar la denegación
  Cuando un usuario sin permiso llama a la ruta
  Entonces la respuesta sigue siendo 403 y no 200 ni 500 `(asumido)`
  Y el fallo queda en el registro técnico con el correlacion_id
```

### CA-13 `[M]` · Rechazo · Nadie autoriza lo suyo, probado sin HTTP · M8 · sin `RN-xx` · `HDU-003 esc. 8`

```gherkin
Escenario: Quien solicitó no puede resolver, aunque tenga DIRECCION_GENERAL
  Dado una función de dominio que recibe el identificador de quien solicitó, el de quien resuelve y los roles de quien resuelve
  Y quien resuelve es la misma persona que solicitó y tiene DIRECCION_GENERAL
  Cuando evalúa si puede resolver
  Entonces devuelve un rechazo con motivo AUTO_RESOLUCION
  Y el resultado no lleva ningún RN-xx
  Y se probó sin servidor ni base de datos

Escenario: Otra persona con el rol sí puede resolver
  Dado quien resuelve distinto de quien solicitó, con DIRECCION_GENERAL
  Cuando evalúa
  Entonces devuelve que puede resolver

Escenario: Rechazo — otra persona sin el rol no resuelve
  Dado quien resuelve distinto de quien solicitó y sin DIRECCION_GENERAL
  Cuando evalúa
  Entonces la ausencia del rol es ROL_INSUFICIENTE, no AUTO_RESOLUCION, y lo decide api/

Escenario: La regla es pura
  Dado el módulo de la regla
  Cuando import-linter y la revisión lo analizan
  Entonces importa solo la biblioteca estándar y tipos_base, sin pwdlib, contrato_error ni datetime
  Y nunca lanza una excepción: devuelve un resultado que el caso de uso convierte en 403 AUTO_RESOLUCION
```

### CA-14 `[M]` · Solo dos rutas sin sesión, comprobado recorriendo el enrutador · M10

```gherkin
Escenario: La lista cerrada coincide con el enrutador
  Dado la aplicación con todos los enrutadores montados, recorrida bajando por original_router.routes
  Cuando se listan las rutas que no tienen la dependencia de sesión
  Entonces son exactamente GET /api/v1/sesion/csrf y POST /api/v1/sesion

Escenario: Rechazo — una ruta nueva sin proteger rompe la suite
  Dado una ruta de prueba añadida al enrutador sin la dependencia de sesión
  Cuando corre el test del enrutador
  Entonces falla nombrando la ruta infractora

Escenario: Rechazo — una ruta de la lista pierde su excepción
  Dado que la lista cerrada se vacía de una de sus dos rutas
  Cuando corre el test
  Entonces falla, porque la ruta quedaría sin protección declarada
```

### CA-15 `[M]` · Contraseñas con Argon2id y parámetros en configuración · M2, M11 · `RNF-03`

```gherkin
Escenario: El hash guardado es Argon2id con los parámetros configurados
  Dado la configuración con unos parámetros de Argon2id
  Cuando se guarda la contraseña de un usuario de prueba
  Entonces password_hash empieza por "$argon2id$" y declara esos parámetros

Escenario: Rechazo — no se usa un hash de propósito general ni passlib
  Dado las dependencias del proyecto y el código de identidad
  Cuando se revisan
  Entonces no existe passlib, hashlib ni bcrypt sobre contraseñas
  Y pwdlib[argon2] está fijada en uv.lock

Escenario: La contraseña nunca viaja en un cuerpo, un registro ni un error
  Dado un inicio de sesión que falla
  Cuando se revisan la respuesta y las líneas del registro técnico
  Entonces ni la contraseña ni password_hash aparecen en ninguna
```

### CA-16 `[S]` · La semilla de roles y el enum `Rol` no divergen · S1

```gherkin
Escenario: Los seis roles coinciden
  Dado la tabla rol sembrada por v0002 y el enum Rol de contrato_error
  Cuando se comparan sus claves
  Entonces son los mismos seis

Escenario: Rechazo — una clave de más o de menos falla la suite
  Dado un enum Rol al que se le añade o quita una clave
  Cuando corre la comparación
  Entonces falla nombrando la clave que difiere
```

### CA-17 `[S]` · El correo en minúsculas lo exige la base · S2

```gherkin
Escenario: Rechazo — la base rechaza un correo con mayúsculas
  Dado una inserción directa en usuario con email "Ana@Cimenta.test"
  Cuando el rol de aplicación ejecuta la sentencia
  Entonces el motor la rechaza por la restricción nombrada de correo en minúsculas
```

### Criterios de regresión

#### CA-R1 `[M]` · Invariantes 10, 20 y 21 intactos

```gherkin
Escenario: Los permisos de TKT-003 no cambian
  Dado el rol de aplicación tras migrar
  Cuando intenta UPDATE o DELETE sobre intento_acceso y UPDATE sobre bitacora
  Entonces el motor los rechaza
  Y el rol de lectura sigue sin ver sesion ni usuario.password_hash
```

#### CA-R2 `[M]` · Las migraciones se aplican y se revierten
`alembic upgrade head`, `downgrade` y `upgrade` otra vez sobre una base vacía terminan sin error, con los seis roles sembrados.

#### CA-R3 `[M]` · Fronteras
`uv run lint-imports` termina en verde y cada contrato sigue fallando ante su violación. `identidad/dominio` no importa nada fuera de la lista blanca; `auditoria` no importa `identidad`.

#### CA-R4 `[M]` · Calidad y suite
`ruff`, `mypy`, `verificar_float` y la suite completa de TKT-001 a TKT-005 terminan en verde con Docker en marcha.

#### CA-R5 `[M]` · Contrato de error de TKT-005
Los `401` y `403` de este ticket usan `SesionInvalida` y `PermisoDenegado`; un `HTTPException` de las ayudas de seguridad de FastAPI nunca llega al cliente.

#### CA-R6 `[M]` · Rutas síncronas
La prueba que recorre las rutas de TKT-005 (TC-78) sigue verde y cubre las rutas de identidad: ninguna es `async def`.

#### CA-R7 `[M]` · Documentación
`python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` terminan sin problemas; los archivos nuevos sin BOM y con LF.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí, con condición | Depende de TKT-003 y TKT-005, archivados, y de **TKT-007**, que el ticket no declaraba. El usuario decidió declararlo y ejecutarlo antes (M12). Bloquea a TKT-008, TKT-026, TKT-057 |
| **N** | Describe el qué, no impone el cómo | Sí | Nombra contratos y columnas existentes; nada sobre capas ni archivos |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Los seis roles pueden iniciar sesión y quedar protegidos |
| **E** | Estimable sin investigar antes | Sí | El esquema, el contrato y el borrador existen |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Talla M con once Must y 17 criterios. Se propone al diseño partir en entrega A (dominio, base mínima, inicio y cierre) y entrega B (dependencia de sesión, `DENEGAR`, test del enrutador), como en TKT-004 y TKT-005 |
| **T** | Sus criterios se pueden ejecutar | Sí | Con Docker; los de tiempo se prueban por conteo de verificaciones, no por reloj |

Una sola reserva: pasa.

## Definition of Done

La de **Fundación**, de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md):

- [ ] Los 15 criterios `[M]` y los 7 de regresión pasan con Docker en marcha, cada uno con su test nombrado por el criterio.
- [ ] Cada rechazo comprueba el contrato de error completo —`tipo`, `motivo`, `correlacion_id` y ausencia de `detail`—, no solo el código de estado.
- [ ] Las rutas de identidad son `def` y la dependencia de sesión fija `request.state.roles_de_quien_llama`.
- [ ] `ruff`, `mypy`, `lint-imports` y `verificar_float` en verde.
- [ ] Ningún `float`, ningún `passlib`, ninguna cookie firmada autocontenida.
- [ ] TKT-007 ejecutado antes, y `docs/05-tickets-trabajo.md` actualizado (M12).
- [ ] Auditoría de arquitectura y de seguridad sin hallazgos abiertos.

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | La no-auto-autorización no tiene `RN-xx` en el PRD; se implementa por arquitectura §7.1 y `HDU-003` esc. 8 `(asumido)` | Si el PRD la numera, el docstring y el motivo cambian | Abierta. Que el PRD la reconozca |
| PA-T2 | Caducidad absoluta de 12 horas e inactividad de 30 minutos, en configuración `(asumido)` | Sesiones más cortas o largas de lo que quiere el negocio | Abierta. Valor de configuración, no de código |
| PA-T3 | Un usuario desactivado con sesión abierta recibe `401` `SESION_REVOCADA`; ningún documento fija el motivo `(asumido)` | El cliente muestra otro aviso | Abierta |
| PA-T4 | El inicio de sesión de un usuario desactivado responde igual que una contraseña errónea `(asumido)` | Revelaría qué cuentas están desactivadas | Abierta |
| PA-T5 | Un cuerpo mal formado (`422`) no se asienta en `intento_acceso` `(asumido)` | Un atacante enviaría formas inválidas sin dejar rastro de intento | Abierta; TKT-057 lo revisa al contar intentos |
| PA-T6 | Si la bitácora falla al asentar un `DENEGAR`, la respuesta sigue siendo `403` y el fallo va al registro técnico `(asumido)` | Un `500` ocultaría la denegación o dejaría pasar la petición | Abierta |
| PA-T7 | `entidad_tipo` y `entidad_id` de un `DENEGAR` sin recurso (por ejemplo `HDU-006` esc. 12) no están definidos en ningún documento | El asiento no tendría a qué entidad atribuirse | **Resuelta por TKT-007: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`** |
| PA-T8 | El parámetro de configuración de Argon2 y de caducidades se lee de variables de entorno con una configuración mínima; `pydantic-settings` completo es de TKT-057 `(asumido)` | Dos mecanismos de configuración | Abierta; el diseño elige |
| PA-T9 | `PA-T6` y `PA-T7` de TKT-003 (`DELETE` sobre `sesion`, purga) siguen abiertas: el rol de aplicación conserva `DELETE` sin usarlo | Una purga futura necesita otro rol | Abierta, ticket sugerido |
| PA-T10 | `uq_usuario_email` distingue mayúsculas; M11 normaliza en código y S2 lo exige en la base | Dos cuentas «Ana@…» y «ana@…» si se omite S2 y alguien escribe directo | Cerrada para el código; S2 pendiente de diseño |
| PA-T11 | TKT-005 dejó una deuda —«obra existente no asignada → `NO_ENCONTRADO`»— que contradice «no hay permiso por obra en el MVP» (`HDU-006` esc. 12, wireframes §880) | Se construiría un permiso por obra que el PRD no tiene | Fuera de alcance. Se registra como Won't |
| PA-T12 | La regla de no-auto-autorización también está en TKT-026, que dice escribirla «una vez» en `identidad` | Dos implementaciones | Decidida: TKT-006; M12 corrige TKT-026 |
| PA-T13 | Cómo nace el primer usuario y cómo se le asignan roles: ninguna operación del borrador lo hace | Sin ello, nadie puede iniciar sesión en producción | Abierta, ticket sugerido |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Un inicio de sesión fallido responde `401` lanzando una excepción; si el manejador deshace la transacción, la fila de `intento_acceso` desaparece justo en el caso que `RNF-04` y TKT-057 necesitan contar | `CA-3` último escenario: el intento fallido sobrevive al rechazo. El diseño decide cómo (commit antes de lanzar, o transacción propia) |
| 2 | Alta | El asiento `DENEGAR` depende de TKT-007, no declarada, y de campos sin definir (`entidad_tipo`, `entidad_id`) para un `403` sin recurso | M9 y M12: TKT-007 pasa a dependencia; `PA-T7` queda abierta y la decide el diseño de TKT-007. Escenario de fallo de la bitácora en `CA-12` |
| 3 | Alta | La no-auto-autorización suena a regla de negocio pero no existe en el PRD; implementarla como `RN` inventaría una regla, y dejarla sin motivo rompe `HDU-003` esc. 8 | Se implementa con `AUTO_RESOLUCION` y sin `regla`; `PA-T1` la declara `(asumido)`. `CA-13` verifica que el resultado no lleva `RN-xx` |
| 4 | Media | «Tiempo constante» no es verificable por reloj en una suite; un test de tiempos sería frágil y no probaría nada | `CA-3` lo prueba por conteo: una verificación de hash por intento, con el hash de descarte de los mismos parámetros. El test de tiempos queda fuera |
| 5 | Media | Una sesión «deslizante» actualiza `ultima_actividad` en cada petición: escribe en toda lectura y puede competir con un cierre de sesión simultáneo | `CA-8` fija el comportamiento observable; el diseño decide la frecuencia de escritura y la carrera con `revocada_en`. Sin objeción que cambie los criterios |
| 6 | Media | Sin alta de usuarios ni primer usuario, el inicio de sesión funciona en pruebas pero no en producción | Won't explícito y `PA-T13`, ticket sugerido; no se resuelve aquí |

Ninguna objeción reveló una regla del PRD que falte más allá de la ya escalada (`PA-T1`), así que no hace falta `/sdd-escalar`.

## Contexto técnico

Archivos, módulos y tablas que el diseño debe considerar. No son decisiones: el *cómo* es de `/sdd-disenar`.

- **Módulos:** `identidad` (todo lo de sesión y la regla de M8) y `auditoria` (consume el servicio de TKT-007). La arista `identidad → auditoria` ya está permitida en `import-linter`; `auditoria` no importa `identidad`.
- **Raíz de composición:** [`backend/servidor/fabrica.py`](../../../backend/servidor/fabrica.py) monta los enrutadores de `cimenta.<modulo>.api` «desde TKT-006». El manejador [`manejadores.py`](../../../backend/servidor/manejadores.py) lee `request.state.roles_de_quien_llama`.
- **Contrato de error existente:** [`backend/contrato_error/`](../../../backend/contrato_error/) con `SesionInvalida(motivo, mensaje)`, `PermisoDenegado(motivo, mensaje, roles_requeridos)`, los catálogos `Rol`, `MotivoPermiso` y `MotivoSesion`.
- **Tablas de TKT-003:** `usuario`, `rol`, `usuario_rol`, `sesion`, `intento_acceso` (`v0001`); semilla de roles con UUID fijos (`v0002`). `origen_ip` es `text`. La tabla `bitacora` y su servicio son de TKT-007.
- **Dependencias nuevas:** `pwdlib[argon2]`. `pydantic-settings` no está en el proyecto.
- **Borrador:** operaciones `obtener_token_csrf`, `iniciar_sesion`, `obtener_sesion_actual` y `cerrar_sesion`; esquemas `TokenCsrf`, `CredencialesInicio`, `UsuarioActual`; cabeceras `SetCookieSesion` y `SetCookieCsrf`; seguridad `sesion` y `csrf`.
- **Documentación a alinear (M12):** [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md) (TKT-006, TKT-026), [`docs/07-especificacion-api.md`](../../../docs/07-especificacion-api.md) §4.1.
- **Deja para otros:** TKT-007 (`bitacora` y servicio `DENEGAR`), TKT-008 (pantalla), TKT-026 y TKT-027 (el `403` `AUTO_RESOLUCION` de HDU-003), TKT-057 (CSRF, límite de intentos), `PA-T2` de TKT-005 (roles por acción).
