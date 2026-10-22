# Spec · TKT-007 · Bitácora transversal de solo-anexado

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

`RN-04` exige que toda autorización y todo rechazo queden registrados con actor, momento y motivo, de forma permanente. Hoy no existe dónde. La tabla `bitacora` no existe, no hay un servicio para escribir en ella dentro de la transacción de un cambio, y los permisos que la harían inmutable no están definidos. Cerca de una docena de tickets posteriores —TKT-017, TKT-020, TKT-021, TKT-025, TKT-027, los de personal y avance, y el propio TKT-006— asientan en ella, y cada uno inventaría su forma de escribir si este ticket llega tarde.

Este ticket de fundación entrega la tabla, su inmutabilidad a nivel de motor, el servicio de asiento que acompaña a un cambio, el servicio que asienta un `403` como `DENEGAR`, y la consulta paginada. Todo se publica en `cimenta.auditoria.interfaz`, el único lugar por el que otro módulo puede tocar la bitácora.

Estado de partida, criterio por criterio del ticket:

| Criterio del ticket | Estado de partida |
|---|---|
| Tabla `bitacora` según modelo §10, `obra_id` lógico sin clave foránea | No existe. El esquema de TKT-003 llega hasta `intento_acceso`; la cabeza de migraciones es `v0002` |
| Enum `accion` de 22 verbos, igual al modelo y a `AccionBitacora` del borrador | Solo existe como lista en el modelo (`03-modelo-datos.md` §10) y en el borrador; ningún tipo de base de datos |
| Asiento en la misma transacción que el cambio | No existe. `cimenta/auditoria/` solo tiene el esqueleto vacío y un `interfaz.py` con docstring |
| Rol de aplicación con `INSERT` y `SELECT`, sin `UPDATE` ni `DELETE` | Por omisión el rol de aplicación recibe `SELECT, INSERT, UPDATE, DELETE` (`ALTER DEFAULT PRIVILEGES` de `v0001`). Hay que revocar, como hizo `v0001` con `intento_acceso` |
| Un test verifica que un `UPDATE` falla a nivel de motor | No existe |
| Consulta por obra, fechas y `regla_negocio`, paginada, más reciente primero | No existe. El borrador declara `consultar_bitacora` con filtros adicionales y la paginación por desplazamiento |
| Servicio aparte para asentar un `403` como `DENEGAR` en transacción propia | No existe. TKT-006 lo espera con el contrato C-1 de su diseño, **enmendado aquí** (ver más abajo) |
| Índices `(obra_id, ocurrido_en DESC)` y parcial sobre `regla_negocio` | No existen |
| Motor y sesión del rol de aplicación para probar | No existen: `herramientas/conexion.py` solo construye la URL de migración y `conftest.py` solo da conexiones `psycopg`. El diseño de TKT-006 los asignaba a su fila 4; este ticket los adelanta |

La spec parte de cuatro decisiones del usuario, tomadas el 2026-10-21 en el intake:

1. **Un `403` sin recurso se atribuye a quien se le denegó:** `entidad_tipo = 'usuario'` y `entidad_id = usuario_id`. Se descarta `entidad_id = sesion.id` porque ese identificador es la credencial de la cookie: `bitacora.entidad_id` lo lee el rol de lectura y lo devolvería `consultar_bitacora`, lo que choca con el invariante 21. Se descarta meter `correlacion_id` en `datos_despues`, porque [API §2.7](../../../docs/07-especificacion-api.md) dice que la correlación **no se asienta en la bitácora**. Esto **enmienda** el contrato C-1 y la decisión D-3 que el usuario aprobó en el diseño de TKT-006.
2. **El motor y la sesión del rol de aplicación los adelanta este ticket,** en su forma mínima. TKT-006 los reusa y su fila 4 se reduce.
3. **TKT-007 no monta `GET /bitacora`.** Entrega la consulta como caso de uso y función de la interfaz. La ruta la monta TKT-027 con `exigir_rol`, y completa el nombre del usuario por la interfaz de `identidad`, que `auditoria` no puede importar. `bitacora.usuario_id` lleva clave foránea a `usuario` `(asumido)`.
4. Un servicio de asiento no confirma: escribe en la sesión que recibe y **el llamador abre y cierra la transacción**. «Transacción propia» del `DENEGAR` significa «separada de la petición», no «la abre el servicio».

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario propia. Quien lo usa al final es Dirección General y el Director de Proyectos, que consultan la bitácora ([`HDU-003`](../../../docs/04-historias-usuario.md) esc. 11); quien lo invoca es cualquier caso de uso de cualquier módulo.

**Como** persona o agente que desarrolla CIMENTA
**quiero** un único servicio para asentar quién hizo qué, cuándo y por qué, en la misma transacción que el cambio, sobre una tabla que nadie puede reescribir
**para** que `RN-04` se cumpla igual en todos los módulos, que un cambio sin asiento no pueda confirmarse, y que cada consulta de excepciones por regla tenga con qué responder.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Tabla `bitacora` con sus columnas del modelo §10 y el enum `accion` de 22 verbos. `usuario_id` `NOT NULL` con clave foránea a `usuario` `(asumido)`; `obra_id` lógico, sin clave foránea. Migración reversible |
| | **M2.** Índices `(obra_id, ocurrido_en DESC)` y parcial sobre `regla_negocio` |
| | **M3.** Inmutabilidad a nivel de motor: el rol de aplicación solo tiene `INSERT` y `SELECT` sobre `bitacora`; `UPDATE`, `DELETE` y `TRUNCATE` fallan. Con su prueba en el mismo cambio |
| | **M4.** Servicio genérico de asiento en `cimenta.auditoria.interfaz`: escribe en la sesión recibida, **sin confirmar**, dentro de la transacción del cambio. Si el asiento falla, el cambio se deshace |
| | **M5.** `asentar_denegacion` en la misma interfaz, con el contrato C-1 enmendado: `accion = 'DENEGAR'`, `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`, `regla_negocio` y `obra_id` nulos, sin `correlacion_id`. Siempre con usuario autenticado; escribe en la sesión recibida sin confirmar |
| | **M6.** Consulta paginada: por obra, rango de fechas (`desde` inclusivo, `hasta` exclusivo) y `regla_negocio`, más los filtros del borrador (`entidad_tipo`, `entidad_id`, `accion`, `usuario_id`). Más reciente primero, con desempate estable `(ocurrido_en DESC, id DESC)` `(asumido)`. Caso de uso y función de la interfaz, **sin ruta HTTP** |
| | **M7.** Motor y sesión síncronos del rol de aplicación, en forma mínima: `url_aplicacion`, `crear_motor_aplicacion` y la *fixture* de `Session` de las pruebas. TKT-006 los reusa |
| | **M8.** Interfaz publicada de `auditoria`: las funciones son atributos de `cimenta.auditoria.interfaz`, y `auditoria` no importa ningún otro módulo |
| | **M9.** Consecuencia documental: enmendar el diseño de TKT-006 (C-1, fila 4, `PA-T7` y su documentación), el modelo de datos §10 en lo de `entidad_tipo` y `entidad_id` del `DENEGAR`, y el ticket TKT-007 en `docs/05-tickets-trabajo.md` (consulta sin ruta; la ruta es de TKT-027) |
| **Should** | **S1.** Los dos índices se comprueban con `EXPLAIN`: la consulta por obra y fecha usa el índice, y la de regla usa el parcial |
| | **S2.** `CHECK` de formato `RN-\d{2}` sobre `bitacora.regla_negocio` `(asumido)` |
| **Could** | — |
| **Won't** | La ruta `GET /bitacora` y su protección con `exigir_rol` (TKT-027) · el nombre del usuario en la respuesta (TKT-027, por la interfaz de `identidad`) · retención y purga (RN-04 dice «permanente») · un esquema por acción para `datos_antes` y `datos_despues` · asentar un intento rechazado por el motor (`HDU-001` esc. 18, del consumidor) · el hash de evidencia (fase 2) · `CHECK` de motivo obligatorio por acción · revocar `SELECT` al rol de lectura · quién consume qué asiento: cada caso de uso decide qué asienta |

## Non-goals

- No implementa ninguna regla de negocio concreta. Las reglas `RN-03` o `RN-07` aparecen como valores de ejemplo.
- No decide **qué** asienta cada módulo ni con qué `datos_antes` y `datos_despues`. Ofrece la firma y la garantía de que el asiento viaja con el cambio.
- No monta rutas ni toca `servidor/fabrica.py`.
- No lee la tabla `usuario` ni importa `identidad`: la bitácora guarda `usuario_id` y nada más.
- No cuantiza importes. Los importes de `datos_*` entran ya como cadena.
- No añade verbos a `accion`: «un verbo nuevo es una migración del enum y un cambio del borrador en el mismo PR».

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-04` | Toda autorización y todo rechazo se registran con actor, momento y motivo, de forma permanente | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RNF-09` | Privilegio mínimo con tres roles; la inmutabilidad de la bitácora (invariante 10) depende de esto | PRD §9 |
| `RNF-13` | Registro técnico separado de la bitácora, con correlación: la correlación no se asienta aquí | PRD §9 |
| Regla 8 de `CLAUDE.md` | La bitácora se escribe en la misma transacción que el cambio y no admite `UPDATE` ni `DELETE` | `CLAUDE.md` |
| Regla 3 de `CLAUDE.md` | Un módulo solo habla con otro por su interfaz publicada | `CLAUDE.md` |
| Regla 1 de `CLAUDE.md` | Sin `float`; los importes en JSON viajan como cadena | `CLAUDE.md` |
| Regla 11 de `CLAUDE.md` | SQLAlchemy síncrono | `CLAUDE.md` |

El glosario no define *bitácora* ni *asiento*: viven en [modelo de datos §10](../../../docs/03-modelo-datos.md) y arquitectura §7.2.

## Invariantes que deben sobrevivir al cambio

El ticket añade una tabla y modifica archivos que ya funcionan: `herramientas/conexion.py`, `tests/conftest.py`, `pyproject.toml` y la cadena de migraciones.

| Invariante o garantía | Qué protege | Criterio de regresión |
|---|---|---|
| Inv. 10 · la bitácora no se modifica | **Es el objeto del ticket** | `CA-3` |
| Inv. 20 · `intento_acceso` solo admite `INSERT` y `SELECT` | Que el patrón de revocación nuevo no altere el de TKT-003 | `CA-R1` |
| Inv. 21 · el rol de lectura no ve `sesion` ni `usuario.password_hash` | Que la tabla nueva no abra esa lectura. El rol de lectura conserva `SELECT` sobre `bitacora` `(asumido)` | `CA-R1` |
| `v0001` y `v0002` siguen aplicando y revirtiéndose; la nueva se aplica y revierte | Cadena con una sola cabeza | `CA-R2` |
| Los contratos de `import-linter` en verde, sin `ignore_imports` | `auditoria` no importa a ningún módulo; solo `grafo-auditoria` lo importa | `CA-R3` |
| Ruff, mypy y `verificar_float` en verde; la suite de TKT-001 a TKT-005 sigue en verde con el rol de aplicación | Calidad y las pruebas existentes; ninguna *fixture* `autouse` nueva | `CA-R4` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde; sin BOM y con LF | Enlaces, identificadores y conteos | `CA-R5` |

## Criterios de aceptación

Gherkin, en español. Los rechazos de la consulta usan el contrato de error `VALIDACION` de TKT-005. Las pruebas se conectan con el rol de aplicación.

### CA-1 `[M]` · La tabla y el enum son los del modelo · M1

```gherkin
Escenario: La tabla tiene las columnas y el enum del modelo
  Dado la base migrada hasta la cabeza
  Cuando se consulta el catálogo de la base
  Entonces bitacora tiene id, entidad_tipo, entidad_id, accion, usuario_id, ocurrido_en, datos_antes, datos_despues, motivo, regla_negocio y obra_id
  Y accion es un enum con los 22 verbos de AccionBitacora del borrador, en el mismo orden
  Y usuario_id, entidad_tipo, entidad_id, accion y ocurrido_en son NOT NULL
  Y usuario_id tiene clave foránea a usuario y obra_id no tiene ninguna

Escenario: Rechazo — un verbo fuera del enum
  Dado una inserción directa con accion "BORRAR"
  Cuando el rol de aplicación la ejecuta
  Entonces el motor la rechaza por valor de enum inválido

Escenario: Rechazo — sin usuario autenticado
  Dado una inserción con usuario_id nulo, y otra con un usuario_id que no existe en usuario
  Cuando el rol de aplicación las ejecuta
  Entonces el motor rechaza la primera por NOT NULL y la segunda por la clave foránea

Escenario: Rechazo — el enum no diverge del borrador
  Dado el enum de la base y AccionBitacora de docs/api/openapi.yaml
  Cuando se comparan
  Entonces coinciden, y una prueba falla nombrando el verbo que difiera
```

### CA-2 `[M]` · El asiento viaja con el cambio, en la misma transacción · M4 · `RN-04`

```gherkin
Escenario: Cambio y asiento se confirman juntos
  Dado una sesión de base de datos del rol de aplicación con una transacción abierta por el llamador
  Y un cambio de prueba sobre un usuario
  Cuando el caso de uso llama al servicio de asiento con CREAR, el usuario, la entidad, el motivo y datos_despues
  Y el llamador confirma
  Entonces el cambio y el asiento existen, con el mismo usuario y el momento dado por el llamador

Escenario: Rechazo — si el asiento falla, el cambio se deshace
  Dado un cambio de prueba y un asiento que el motor rechaza (por ejemplo, un usuario_id que no existe)
  Cuando el llamador intenta confirmar
  Entonces la transacción entera se deshace: ni el cambio ni el asiento quedan

Escenario: El servicio no confirma por su cuenta
  Dado un asiento escrito en una sesión
  Cuando el llamador deshace la transacción
  Entonces el asiento no queda en la tabla: el servicio nunca llama a commit
```

### CA-3 `[M]` · La bitácora no se reescribe, probado a nivel de motor · M3 · inv. 10

```gherkin
Escenario: El rol de aplicación solo puede insertar y leer
  Dado un asiento existente
  Cuando el rol de aplicación ejecuta INSERT y SELECT sobre bitacora
  Entonces ambos tienen éxito

Escenario: Rechazo — UPDATE
  Dado un asiento existente
  Cuando el rol de aplicación ejecuta UPDATE bitacora SET motivo = 'otro'
  Entonces el motor responde permiso denegado y el asiento no cambia

Escenario: Rechazo — DELETE y TRUNCATE
  Dado un asiento existente
  Cuando el rol de aplicación ejecuta DELETE y TRUNCATE sobre bitacora
  Entonces el motor responde permiso denegado y el asiento sigue ahí

Escenario: El rol de lectura puede leer y no escribir
  Cuando el rol de lectura ejecuta SELECT, y después INSERT, sobre bitacora
  Entonces el SELECT tiene éxito y el INSERT es rechazado `(asumido)`
```

### CA-4 `[M]` · Un `403` se asienta como `DENEGAR` atribuido al usuario · M5 · `RN-04`

```gherkin
Escenario: Se asienta la denegación de un usuario autenticado
  Dado el usuario "ana@cimenta.test" autenticado y una sesión con una transacción abierta por el llamador
  Cuando se llama a asentar_denegacion con el usuario, el momento, el motivo "ROL_INSUFICIENTE" y datos con método, ruta y roles requeridos
  Entonces el asiento tiene accion "DENEGAR", entidad_tipo "usuario" y entidad_id igual al usuario_id
  Y regla_negocio, obra_id y datos_antes son nulos, y los datos van en datos_despues
  Y el servicio no confirma: persiste solo si el llamador confirma

Escenario: Rechazo — nunca anónimo
  Dado un usuario_id nulo o que no existe
  Cuando se llama a asentar_denegacion
  Entonces falla sin escribir ningún asiento

Escenario: La credencial y la correlación no entran en la bitácora
  Dado la firma de asentar_denegacion
  Cuando se revisan sus parámetros y un asiento escrito
  Entonces no hay parámetro de sesión ni de correlación, y ningún valor de entidad_id es un identificador de sesión

Escenario: Es un atributo del módulo de la interfaz
  Dado cimenta.auditoria.interfaz
  Cuando una prueba de otro módulo sustituye asentar_denegacion con monkeypatch
  Entonces la sustitución surte efecto, porque la función es un atributo del módulo
```

### CA-5 `[M]` · El asiento genérico cuida la forma de lo que recibe · M4 · `RN-04`

```gherkin
Escenario: Un asiento con regla de negocio y obra
  Dado una autorización de ejemplo con la regla "RN-03", la obra y datos con importes como cadena
  Cuando se asienta con AUTORIZAR
  Entonces regla_negocio guarda "RN-03", obra_id la obra, y datos_antes y datos_despues guardan los datos con los importes como cadena

Escenario: Rechazo — una regla mal formada
  Dado la regla "rn-03", y otra "XX-03"
  Cuando se asienta
  Entonces el servicio rechaza antes de escribir, con tipo VALIDACION y el campo regla_negocio

Escenario: Rechazo — un importe flotante
  Dado datos_despues con un float como valor
  Cuando se asienta
  Entonces el servicio rechaza antes de escribir, nombrando el campo, y no se escribe ningún asiento

Escenario: Rechazo — un verbo que no existe
  Dado una acción fuera de los 22 verbos
  Cuando se asienta
  Entonces el servicio rechaza antes de llegar a la base
```

### CA-6 `[M]` · La consulta filtra, ordena y pagina · M6

```gherkin
Escenario: Filtro por obra y por rango de fechas
  Dado asientos de dos obras y de distintos días
  Cuando se consulta una obra con desde inclusivo y hasta exclusivo
  Entonces solo vuelven los asientos de esa obra dentro del rango
  Y un asiento exactamente en desde entra y uno exactamente en hasta no entra

Escenario: Filtro por regla de negocio y por los demás filtros del borrador
  Dado asientos con RN-03, con RN-07 y sin regla, de distintos usuarios, entidades y acciones
  Cuando se consulta con regla_negocio "RN-03", y después con entidad_tipo, entidad_id, accion[] y usuario_id
  Entonces cada consulta devuelve solo los asientos que cumplen todos los filtros dados

Escenario: El más reciente primero, con desempate estable
  Dado tres asientos con el mismo ocurrido_en
  Cuando se pagina de a un elemento
  Entonces el orden es (ocurrido_en DESC, id DESC) y ningún asiento se repite ni se pierde entre páginas

Escenario: Paginación por desplazamiento
  Dado 120 asientos
  Cuando se pide pagina 2 con tamano_pagina 50
  Entonces vuelven los elementos 51 a 100 y el total es 120
  Y sin parámetros, pagina es 1 y tamano_pagina es 50

Escenario: Rechazo — paginación y filtros inválidos
  Dado pagina 0, tamano_pagina 0 y tamano_pagina 201, regla_negocio "rn-03", y desde posterior a hasta `(asumido)`
  Cuando se consulta
  Entonces cada caso responde con tipo VALIDACION y el campo infractor, sin tocar la base

Escenario: La consulta no es una ruta
  Dado la aplicación servible
  Cuando se recorre el enrutador
  Entonces no existe ninguna ruta /bitacora: la monta TKT-027
```

### CA-7 `[M]` · Los índices existen · M2

```gherkin
Escenario: Existen los dos índices con su definición
  Dado la base migrada
  Cuando se consulta el catálogo
  Entonces existe un índice sobre (obra_id, ocurrido_en DESC)
  Y existe un índice parcial sobre regla_negocio con el predicado regla_negocio IS NOT NULL

Escenario: Rechazo — sin índice, la prueba falla
  Dado una migración que omite uno de los dos índices
  Cuando corre la prueba del catálogo
  Entonces falla nombrando el índice ausente
```

### CA-8 `[M]` · La interfaz de `auditoria` es la única entrada y no depende de nadie · M8

```gherkin
Escenario: Las funciones son atributos de la interfaz
  Dado cimenta.auditoria.interfaz
  Cuando se importan el servicio de asiento, asentar_denegacion y la consulta
  Entonces los tres se obtienen desde ese módulo

Escenario: Rechazo — auditoria no importa a ningún módulo
  Dado un archivo de auditoria que importa cimenta.identidad
  Cuando corre lint-imports
  Entonces el contrato falla y el pipeline se detiene

Escenario: Rechazo — otro módulo no importa sus repositorios
  Dado un módulo que importa cimenta.auditoria.infraestructura
  Cuando corre lint-imports
  Entonces el contrato de interfaz publicada falla
```

### CA-9 `[M]` · Motor y sesión del rol de aplicación, para las pruebas y para TKT-006 · M7

```gherkin
Escenario: Las pruebas disponen de una Session del rol de aplicación
  Dado la base de prueba migrada
  Cuando una prueba pide la fixture de sesión de base de datos
  Entonces recibe una Session síncrona conectada con cimenta_aplicacion y no con el propietario

Escenario: Rechazo — la guarda no deja conectar con el propietario
  Dado una prueba que intenta conectarse con el rol de migración como si fuera de aplicación
  Cuando la fixture se construye
  Entonces la guarda de rol la rechaza, para que las pruebas de permisos no queden verdes sin verificar nada

Escenario: Crear el motor no exige una base de datos viva
  Dado un proceso sin conexión a la base
  Cuando se construye el motor
  Entonces no abre ninguna conexión hasta la primera consulta

Escenario: Ninguna fixture nueva es autouse
  Dado el conftest tras el cambio
  Cuando se revisa
  Entonces ninguna fixture añadida es autouse
```

### Criterios que cubren sin sustituir lo existente

### CA-10 `[M]` · La migración se aplica, se revierte y deja una sola cabeza · M1, M3

```gherkin
Escenario: Subir, bajar y volver a subir
  Dado una base vacía
  Cuando se ejecuta alembic upgrade head, downgrade a v0002 y upgrade head
  Entonces las tres terminan sin error y bitacora y su enum existen solo cuando corresponde

Escenario: Rechazo — una sola cabeza
  Dado la cadena de migraciones
  Cuando se listan las cabezas
  Entonces hay exactamente una
```

### CA-11 `[S]` · Los índices se usan · S1

```gherkin
Escenario: La consulta por obra y fecha usa el índice, la de regla el parcial
  Dado un volumen de asientos suficiente
  Cuando se ejecuta EXPLAIN de cada consulta
  Entonces el plan usa el índice de (obra_id, ocurrido_en) y el parcial de regla_negocio respectivamente
```

### CA-12 `[S]` · El formato de la regla lo exige la base · S2

```gherkin
Escenario: Rechazo — el motor rechaza una regla mal formada
  Dado una inserción directa con regla_negocio "rn-03"
  Cuando el rol de aplicación la ejecuta
  Entonces el motor la rechaza por la restricción nombrada de formato
```

### Criterios de regresión

#### CA-R1 `[M]` · Invariantes 20 y 21 intactos
El rol de aplicación sigue sin `UPDATE` ni `DELETE` sobre `intento_acceso`; el rol de lectura sigue sin ver `sesion` ni `usuario.password_hash`.

#### CA-R2 `[M]` · Cadena de migraciones
`v0001` y `v0002` se aplican y se revierten; las pruebas de TKT-003 siguen en verde.

#### CA-R3 `[M]` · Fronteras
`uv run lint-imports` en verde y cada contrato sigue fallando ante su violación, sin `ignore_imports`.

#### CA-R4 `[M]` · Calidad y suite
`ruff`, `mypy`, `verificar_float` y la suite de TKT-001 a TKT-005 en verde con Docker.

#### CA-R5 `[M]` · Documentación
`python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y los tests de `tools/` sin problemas.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-003, archivado. Bloquea a TKT-006 y a todo el que asiente |
| **N** | Describe el qué, no impone el cómo | Sí | Nombra contratos y tablas existentes; el diseño decide capas y archivos |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Dirección General y el Director de Proyectos podrán consultar quién autorizó qué; ningún módulo inventa su registro |
| **E** | Estimable sin investigar antes | Sí | El modelo, el borrador y el patrón de revocación de `v0001` existen |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Talla S en el ticket, pero sumó el motor de aplicación adelantado y la enmienda de TKT-006: riesgo de pasar a M |
| **T** | Sus criterios se pueden ejecutar | Sí | Con Docker; la inmutabilidad se prueba contra el motor real |

Una sola reserva: pasa.

## Definition of Done

La de **Fundación**, de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md):

- [ ] Los 10 criterios `[M]` y los 5 de regresión pasan con Docker en marcha, cada uno con su test nombrado por el criterio.
- [ ] Un `UPDATE`, un `DELETE` y un `TRUNCATE` sobre `bitacora` fallan a nivel de motor.
- [ ] Cada rechazo comprueba el contrato de error o el error del motor completo, no solo que algo falló.
- [ ] `ruff`, `mypy`, `lint-imports` y `verificar_float` en verde.
- [ ] El diseño de TKT-006 enmendado (M9) y reconocido por el usuario.
- [ ] Auditoría de arquitectura y de seguridad sin hallazgos abiertos.

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | `bitacora.usuario_id` lleva clave foránea a `usuario` `(asumido)`. El modelo §10 la dibuja, pero §2 dice que una referencia a un módulo que no es ancestro es lógica y `usuario_id` no está en su lista cerrada | Si es lógica, un asiento podría apuntar a un usuario que no existe | Abierta. Se resuelve en el diseño y se corrige el documento que se contradiga |
| PA-T2 | `ocurrido_en` lo fija el llamador con su reloj; el contrato C-1 lo recibe `(asumido)` | Un llamador con un reloj equivocado escribiría un momento falso en el registro que debe ser irrefutable | Abierta; el diseño valora `DEFAULT now()` como respaldo |
| PA-T3 | `entidad_tipo` y `entidad_id` son `NOT NULL`, como pide `AsientoBitacora` `(asumido)` | Un asiento sin entidad no cabría | Cerrada para `DENEGAR` (se atribuye al usuario) |
| PA-T4 | El rol de lectura conserva `SELECT` sobre `bitacora` por los privilegios por omisión `(asumido)`; `analitica` lo lee con «(asumido)» en arquitectura §5 | La bitácora, con importes en `datos_*`, la lee quien tenga el rol de lectura | Abierta |
| PA-T5 | `datos_antes` y `datos_despues` son `jsonb` con importes como cadena y sin cuantizar aquí; no hay esquema por acción | Un importe con escala distinta entre asientos | Abierta |
| PA-T6 | `regla_negocio` con formato `RN-\d{2}` se valida en el servicio y, como Should, en la base `(asumido)` | Una regla mal escrita contaminaría la consulta de excepciones | Abierta |
| PA-T7 | La paginación es por desplazamiento, como declara el borrador; con asientos nuevos entre dos peticiones, las páginas pueden correrse | Un asiento visto dos veces o no visto al paginar | Abierta; el desempate lo acota, no lo elimina |
| PA-T8 | El `403` con usuario autenticado cuenta como «rechazo» de `RN-04`; si falla el asiento, TKT-006 responde `403` y lo registra en el registro técnico (D-7 de TKT-006) | Una denegación sin asiento | Aprobada en TKT-006 |
| PA-T9 | Retención, purga y respaldo: `RN-04` dice «permanente» y `RNF-10` habla de recuperación a un punto en el tiempo; nada fija cuánto crece | Una tabla que crece sin límite | Fuera de alcance, ticket sugerido |
| PA-T10 | El asiento de un intento rechazado por el motor (`HDU-001` esc. 18) ocurre cuando la transacción se deshace y no tiene verbo ni mecanismo documentado | Un rechazo sin rastro | Fuera de alcance; es del consumidor |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `entidad_id = sesion.id` habría puesto la credencial de la cookie en una columna que lee el rol de lectura y devuelve la consulta (invariante 21); y `correlacion_id` en `datos_despues` contradice API §2.7 | Resuelto por el usuario: el `403` se atribuye al usuario y no lleva correlación. `CA-4` lo vigila con un escenario de rechazo y `M9` enmienda TKT-006 |
| 2 | Alta | «Misma transacción» es una promesa del llamador: el servicio no puede forzarla, y un consumidor que confirme antes dejaría un cambio sin asiento | `CA-2` fija que el servicio nunca confirma y que un asiento fallido deshace el cambio; la comprobación por consumidor es de cada ticket (TKT-021, TKT-025). Sin objeción que cambie los criterios |
| 3 | Alta | Paginación por desplazamiento sobre una tabla que solo crece: entre página 1 y 2 entran asientos nuevos, y sin desempate estable se repiten o se pierden filas | `CA-6` exige el desempate `(ocurrido_en DESC, id DESC)` y lo prueba con tres asientos del mismo momento; `PA-T7` declara el límite que queda |
| 4 | Media | Si `ocurrido_en` lo pone el llamador, la bitácora irrefutable depende de que cada módulo acierte con su reloj | `PA-T2`; el diseño valora el respaldo en la base. No cambia criterios |
| 5 | Media | `auditoria` no puede mostrar el nombre del usuario sin leer `identidad` | Won't explícito: lo completa TKT-027 por la interfaz de `identidad`. `CA-6` no lo exige |
| 6 | Media | El diseño aprobado de TKT-006 ya asumió C-1 con la sesión; enmendarlo toca un diseño aprobado | `M9` y la sección de decisiones lo declaran; el usuario eligió la enmienda. El diseño de TKT-006 se corrige antes de ejecutar |

Ninguna objeción reveló una regla que el PRD no tenga, así que no hace falta `/sdd-escalar`.

## Contexto técnico

Archivos, módulos y tablas relevantes. No son decisiones: el *cómo* es de `/sdd-disenar`.

- **Módulo:** `auditoria`, transversal. Lo pueden importar `identidad`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores` y `analitica` (contrato `grafo-auditoria`). Él no importa a ninguno.
- **Migraciones:** la cabeza es `v0002_semilla_roles_de_negocio`. El patrón de revocación está en `v0001` (`REVOKE UPDATE, DELETE ON intento_acceso FROM cimenta_aplicacion`). TKT-006 también añade una migración (S2): ambas parten de la cabeza vigente.
- **Pruebas:** `tests/conftest.py` tiene `conectar(rol, base)`, `base_de_prueba` y `migrar`, con una guarda del rol de aplicación. No existe motor ni `Session` de SQLAlchemy.
- **Conexión:** `herramientas/conexion.py` solo tiene `url_migracion()`.
- **Contrato de error:** la consulta rechaza con `VALIDACION` de TKT-005.
- **Borrador:** `consultar_bitacora` (`GET /bitacora`), `x-tickets: [TKT-007, TKT-027]`, roles `DIRECCION_GENERAL` y `DIRECTOR_PROYECTOS`, regla `RN-04`, escenarios `HDU-003` esc. 11 y `HDU-001` esc. 22. Esquemas `AccionBitacora`, `AsientoBitacora`, `ListaBitacora`. La ruta es de TKT-027.
- **Documentación a alinear (M9):** `sdd/tickets/tkt-006/design.md` y `_index.md`, `docs/03-modelo-datos.md` §10, `docs/05-tickets-trabajo.md` (TKT-007 y TKT-027).
- **Consumidores:** TKT-006 (`DENEGAR`), TKT-017, TKT-020, TKT-021, TKT-025, TKT-027, TKT-058 y los de personal, avance e idempotencia.
