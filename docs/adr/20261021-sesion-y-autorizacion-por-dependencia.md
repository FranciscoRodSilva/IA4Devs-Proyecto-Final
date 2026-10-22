# Sesión y autorización por rol como dependencias de FastAPI

## Estado

Aceptado

## Contexto y problema

[ADR-014](20260919-sesion-con-estado.md) decide que la sesión vive en una tabla y que el permiso se lee de la base en cada petición, para que quitar un rol o desactivar a un usuario surta efecto en la petición siguiente. Falta decidir cuatro cosas: dónde se valida esa sesión en FastAPI, cómo declara cada ruta el rol que exige, cómo se asienta un rechazo y de dónde sale la hora que usa la caducidad.

Hay tres piezas cuyas consecuencias no son obvias:

* **La validación escribe.** La caducidad por inactividad mide el tiempo desde el último uso de la sesión, así que cada petición autenticada actualiza `ultima_actividad`. Una lectura que escribe no es lo que alguien espera de una dependencia.
* **Un `403` deja rastro.** Un intento sin permiso de un usuario autenticado se asienta en la bitácora como `DENEGAR` ([arquitectura §7.2](../02-arquitectura.md#72-bitácora)). Si el asiento va en la transacción de la petición, se deshace con ella, porque el rechazo no acompaña ningún cambio. Y si el asiento falla, el rechazo no debe quedar oculto tras un `500`.
* **La regla debe probarse sin HTTP.** La regla de no-auto-autorización ([TKT-026](../05-tickets-trabajo.md#tkt-026--reglas-de-autoridad-en-el-dominio)) y la caducidad se comprueban en el dominio. Si el dominio consulta el reloj, esas reglas dejan de ser funciones puras, y [ADR-021](20261019-lista-blanca-del-dominio.md) deja esa vigilancia a la revisión.

## Opciones consideradas

**Dónde se valida la sesión**

* Dependencia de FastAPI, `sesion_vigente` (elegida)
* *Middleware* de la aplicación
* Decorador propio sobre cada ruta

**Cómo se declara el rol que exige una ruta**

* `dependencies=[Depends(exigir_rol(...))]` en cada ruta, con los roles de `x-roles` (elegida)
* Comprobar el rol dentro del caso de uso
* Tabla central de roles por `operationId`

**Cómo se mantiene `ultima_actividad`**

* Escribirla en cada petición vigente, con `WHERE revocada_en IS NULL` (elegida)
* Escribirla solo cada N minutos
* `SELECT ... FOR UPDATE` sobre la sesión antes de leerla

**Dónde se asienta el `DENEGAR`**

* En una transacción propia que abre `registrar_denegacion`; si falla, registro técnico y `403` igualmente (elegida)
* En la transacción de la petición
* Responder `500` si falla la bitácora

**De dónde sale la hora**

* Reloj inyectable en `aplicacion/`; el dominio compara valores genéricos (elegida)
* `datetime` dentro del dominio

## Decisión

Se elige una **dependencia de FastAPI**, `sesion_vigente`, para validar la sesión. La publica `cimenta.identidad.interfaz` y lee la cookie, la fila de `sesion`, el usuario y sus roles en cada petición.

* **El *middleware* no sabe qué rol exige la ruta.** No publica el esquema `sesion` en el OpenAPI, y corre en el bucle de eventos haciendo E/S bloqueante, que [ADR-013](20260919-sqlalchemy-sincrono.md) prohíbe en una corrutina.
* **El decorador propio no es una dependencia para FastAPI.** El esquema no lo ve y el enrutador no se puede recorrer para comprobar qué rutas quedan protegidas.

Cada ruta que exige un rol la declara con `dependencies=[Depends(exigir_rol(...))]`, con los roles de su `x-roles` del borrador OpenAPI. `exigir_rol` se apoya en `sesion_vigente`, así que una petición sin sesión responde `401` antes de que se evalúe el rol, y una con sesión pero sin el rol responde `403`. El caso de uso no sabe de roles de ruta: recibe lo que ya está autorizado.

**La sesión deslizante se escribe en cada petición.** La validación actualiza `ultima_actividad` con un `UPDATE ... WHERE revocada_en IS NULL ... RETURNING`, de modo que una sesión ya cerrada no se toca ni se vuelve a abrir. Escribir cada N minutos haría la inactividad inexacta, y `SELECT ... FOR UPDATE` bloquea más tiempo para el mismo resultado.

**El `DENEGAR` va en una transacción propia.** `registrar_denegacion` abre su propia transacción con el usuario autenticado como actor y llama a `asentar_denegacion` de `auditoria`. Si esa transacción falla, la petición responde `403` igualmente y se registra `denegacion_no_asentada` en el registro técnico: el rechazo sigue siendo un rechazo.

**La hora la pone la aplicación.** `ContextoIdentidad` lleva un reloj: `datetime.now(UTC)` en producción y un reloj de prueba en las pruebas. El dominio recibe instantes como valores y decide con ellos. `vigencia` y `autorizacion` no importan nada del reloj.

**La regla de auto-autorización** es `evaluar_resolucion`, en `identidad/dominio`. No recibe roles de quien resuelve, porque ningún rol debe eximir de la regla, y no devuelve un identificador `RN-xx`: su rechazo es `AUTO_RESOLUCION`. El caso de uso lo convierte en un `403` del contrato de error ([ADR-022](20261020-contrato-de-error-y-raiz-de-composicion.md)).

## Consecuencias

**Positivas**

* Quitar un rol o desactivar a un usuario surte efecto en la petición siguiente, como exige [ADR-014](20260919-sesion-con-estado.md), sin caché de permisos.
* El esquema `sesion` aparece en el OpenAPI y las rutas se pueden recorrer. Una prueba compara la lista de rutas sin sesión con una lista cerrada, y falla si otra ruta queda sin protección.
* Un rechazo se asienta aunque la bitácora falle, y la petición responde lo que dice: `403`.

**Negativas o costes aceptados**

* **Cada petición autenticada escribe una fila.** Es una actualización por clave primaria. `validar_sesion` abre su propia transacción y su propia conexión antes que cualquier otra de la petición.
* **Una ruta puede olvidar `exigir_rol`.** Conserva `sesion_vigente` y sigue siendo inaccesible sin sesión, pero cualquier usuario autenticado la usa. Lo vigila la revisión de cada ticket, que compara la ruta con su `x-roles`, no una prueba.
* **`auditoria` no puede proteger su ruta importando `identidad`.** Si dependiera de `identidad`, se crearía un ciclo entre módulos que la regla de fronteras no admite. Esa protección se monta desde la raíz de composición. Mientras `rutas_de` no lea el contexto de inclusión, el montaje con `include_router(..., dependencies=[Depends(exigir_rol(...))])` protege en ejecución pero el test del enrutador (TC-47) lo reporta como «sin proteger»: TKT-027 declara `exigir_rol` en el decorador de la propia ruta o amplía `rutas_de`.

**Cómo se verifica**

* Una prueba recorre el enrutador y compara las rutas sin sesión con la lista cerrada.
* Pruebas por HTTP comprueban el `401` sin sesión, el `403` sin rol con su asiento `DENEGAR`, y que un fallo de la bitácora deja el `403` y el registro técnico.
* En la tabla de mutación oficial, MT-9 es el único mutante sobre la cláusula SQL `revocada_en IS NULL`; ninguno quita la escritura de `ultima_actividad`. TC-32 y TC-38 cubren el deslizamiento sin mutante propio en esa tabla.

**Cuándo revisar esta decisión**

* Si la escritura por petición se nota en la carga del servidor.
* Si llega una tabla central de roles por acción, que sustituiría la declaración de cada ruta.
