# Delta · TKT-029a · Catálogo de proveedores, sin baja

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. El ticket se ejecutó en dos entregas, más una fila de revisión (B3), sobre una sola rama, y este delta es **uno solo, del ticket entero**.

| Entrega | Qué aportó |
|---|---|
| TKT-029a-a (esquema, dominio, repositorio y casos de uso) | La tabla `proveedor` con la migración `0013`, el dominio del catálogo (`EstadoProveedor`, los días por omisión de `RN-17`, `normalizar_rfc` y `admite_desactivacion`), el repositorio y los cinco casos de uso con bitácora en la misma transacción |
| TKT-029a-b (API, contrato y tipos) | Las cinco rutas HTTP del catálogo, sus DTO, el montaje en la fábrica del servidor, los ajustes del borrador OpenAPI y los tipos del cliente regenerados |
| Revisión (fila B3) | La traducción de `lock_timeout` (`55P03`) y `statement_timeout` (`57014`) a `409` `CONCURRENCIA` en el alta, el cambio y la desactivación, por decisión de la persona dueña; y las correcciones de la revisión (RFC con caracteres que `upper()` reescribe, guarda de campos cambiables, código de `RFC_DUPLICADO`) |

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Tabla `proveedor` con seis restricciones nombradas, incluido el índice único `uq_proveedor_rfc`, y los privilegios del rol de aplicación sin `DELETE` | `backend/migraciones/versions/v0013_proveedores_catalogo.py` | Persistir el catálogo; que el motor impida el proveedor duplicado (invariante 28) y que un proveedor nunca se borre |
| `EstadoProveedor`, `DIA_CORTE_POR_OMISION`, `DIA_PAGO_POR_OMISION`, `normalizar_rfc` y `admite_desactivacion` | `backend/cimenta/proveedores/dominio/proveedor.py` | Reglas puras: los días por omisión de `RN-17`, el RFC recortado de espacios y en mayúsculas (`D-1`) y que solo un proveedor `ACTIVO` se desactiva |
| Modelo Core de `proveedor` y repositorio (`insertar_proveedor`, `leer_proveedor`, `leer_proveedor_por_rfc`, `listar_proveedores`, `actualizar_proveedor`) | `backend/cimenta/proveedores/infraestructura/tablas.py`, `repositorio_proveedor.py` | Leer y escribir el catálogo, con `FOR UPDATE` opcional, búsqueda literal de `q` y página inalcanzable que devuelve la lista vacía |
| Contexto y casos de uso `crear_proveedor`, `obtener_proveedor`, `listar_proveedores`, `actualizar_proveedor` y `desactivar_proveedor` | `backend/cimenta/proveedores/aplicacion/contexto.py`, `proveedores.py` | Una transacción por operación con su asiento de bitácora dentro; el `23505` de `uq_proveedor_rfc` arbitra el duplicado y la carrera; `FOR UPDATE` en el cambio y la desactivación |
| Gestor de contexto `_traducir_concurrencia` | `backend/cimenta/proveedores/aplicacion/proveedores.py` | Traducir `55P03` y `57014` a `ConcurrenciaVencida` (`RNF-16`), de modo que el rollback ocurra antes de traducir y no quede fila ni asiento |
| Rutas `crear_proveedor`, `listar_proveedores`, `obtener_proveedor`, `actualizar_proveedor` y `desactivar_proveedor`, y los DTO `ProveedorNuevo`, `ProveedorCambios`, `Proveedor` y `ListaProveedores` | `backend/cimenta/proveedores/api/rutas.py`, `esquemas.py`, `montaje.py` | Publicar el catálogo tal como lo fija el borrador OpenAPI; copias locales de `MetaPagina` y `Motivo` (`D-7`) |
| `borrador_comparable()` | `backend/herramientas/soporte_tkt017_api.py` | Comparar el esquema publicado contra el borrador en las pruebas de contrato (`TC-40`) |
| Cinco archivos de pruebas del ticket (158 casos) y la evidencia de rojo por fila | `backend/tests/test_tkt029a_*.py`, `sdd/tickets/tkt-029a/rojo/` | Cubrir `CA-1` a `CA-11`, `CA-R1` y `CA-R2`, y dejar rastro de que cada fila empezó en rojo |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `docs/api/openapi.yaml` | `listar_proveedores` y `ProveedorNuevo` | Sin tope de longitud en `nombre` ni en `q` → `maxLength: 200` en `nombre` (alta y cambio) y `pattern: '^[^\x00]*$'` con `maxLength: 200` en `q` (`D-5`, `D-9`) |
| `frontend/src/api/generado/servidor.ts` | tipos generados | Regenerado con las cinco operaciones del catálogo |
| `backend/servidor/fabrica.py` | montaje de enrutadores | Sin el enrutador de `proveedores` → montado |
| `docs/03-modelo-datos.md` | §9 | Tabla `proveedor` sin `creado_en` ni `creado_por_id` ni nota de permisos → ambas columnas y la explicación de que el motor hace cumplir «nunca se borra» (`DELETE` revocado) |
| `docs/05-tickets-trabajo.md` | TKT-029a | Migración `0012` → `0013` sobre `0012` (TKT-059 ocupó `0012`) |
| `presupuesto/api/esquemas.py` | docstring de `Motivo` | Docstring distinto → igualado al de la copia de `proveedores`, para que Pydantic fusione las dos clases en el OpenAPI (`D-7`; lo guardan `TC-42` y `M-12`) |
| `test_tkt010_semilla_local.py`, `test_tkt059_migracion.py` y `test_tkt057_csrf.py` | pruebas de otros tickets | Declaradas en `impl.md`: TC-B15 pasa `proveedor` de las tablas inexistentes a las que la siembra deja vacías; la prueba de TKT-059 lee la cabeza única del guion en vez de la cadena `"0012"`; `CUERPOS_VALIDOS` gana tres entradas. No cambia lo que afirman |
| `spec.md` y `design.md` | documentación del ticket | Migración, atribución a la historia, cita de ADR y la fila B3 (`TC-43`, `M-13`) añadidas durante la revisión |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Ninguno | — | — |

## Comportamiento observable nuevo

- Compras puede dar de alta un proveedor con nombre y RFC. Nace `ACTIVO`, con `dia_corte` 4 (jueves) y `dia_pago` 6 (sábado) si no se indican, el tope de consignación opcional y la fecha de creación. El RFC se guarda recortado de espacios y en mayúsculas.
- Un RFC repetido, también con otra capitalización o con espacios, y dos altas simultáneas con el mismo RFC responden `409` `CONFLICTO` con el código `RFC_DUPLICADO`, el identificador del proveedor existente y su «nombre · RFC».
- Un RFC que no tiene la forma de un RFC, un nombre vacío o de más de 200 caracteres, un día fuera de 1 a 7, un importe negativo o con más de cuatro decimales, o un cuerpo de cambio sin ningún dato, responden `422`. Un RFC con `ß`, `ı` o `ſ` también se rechaza, porque `str.upper()` los reescribiría como `SS`, `I` y `S`.
- Compras puede cambiar nombre, tope de consignación y días de un proveedor, aun si está `DESACTIVADO` (`D-3`), y desactivarlo con un motivo. Desactivar un proveedor que ya no está `ACTIVO` responde `409` `CONFLICTO` con el código `ESTADO_NO_PERMITE_OPERACION`.
- Los seis roles con acceso al catálogo lo consultan: la lista, por omisión solo los proveedores `ACTIVO`, ordenada por nombre y después por identificador, con búsqueda literal por nombre o RFC y paginación; y cada proveedor por identificador (`404 NO_ENCONTRADO` si no existe). Los roles que no son Compras no pueden dar de alta, cambiar ni desactivar (`403`).
- Si otra transacción retiene la fila o el índice más de 5 s (`lock_timeout`), o la consulta pasa de 15 s (`statement_timeout`), el alta, el cambio y la desactivación responden `409` `CONCURRENCIA` con `Retry-After: 1` y la acción «reintentar», y no dejan fila ni asiento de bitácora. Antes de este ticket esa respuesta no existía para proveedores; sin la traducción habría sido un `500`.
- No existe ninguna ruta `DELETE` ni baja de proveedor.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `POST /api/v1/proveedores` (`crear_proveedor`) | Nueva: `201` con `Location`, `409 RFC_DUPLICADO`, `409 CONCURRENCIA`, `422`, `403`, `401` | No |
| `GET /api/v1/proveedores` (`listar_proveedores`) | Nueva: `estado` repetible, `q` (hasta 200 caracteres, sin `NUL`), `pagina`, `tamano_pagina` | No |
| `GET /api/v1/proveedores/{proveedor_id}` (`obtener_proveedor`) | Nueva: `200`, `404 NO_ENCONTRADO` | No |
| `PATCH /api/v1/proveedores/{proveedor_id}` (`actualizar_proveedor`) | Nueva: `200`, `404`, `422`, `403`, `409 CONCURRENCIA`. El `409` que el borrador ya declaraba para `PATCH` no se emite aparte (`D-3`) | No |
| `POST /api/v1/proveedores/{proveedor_id}/desactivacion` (`desactivar_proveedor`) | Nueva: `200`, `404`, `409 CONFLICTO` (`ESTADO_NO_PERMITE_OPERACION`), `409 CONCURRENCIA`, `422`, `403` | No |
| `ProveedorNuevo`, `ProveedorCambios`, `Proveedor`, `ListaProveedores` | Nuevos; `nombre` lleva `maxLength: 200` y `q` lleva `pattern` y `maxLength: 200` en el borrador | No |
| `Motivo` y `MetaPagina` | Dos clases idénticas en `presupuesto` y en `proveedores` que Pydantic fusiona en un solo componente | No |
| Tipos generados del cliente | `servidor.ts` regenerado | No |
| Esquema de base de datos | Migración `0013`: tabla `proveedor`, sin `DELETE` para el rol de aplicación | No |
| `docs/api/openapi.yaml` | Cambia, y es una de las compuertas que el PR modifica: quien apruebe debe revisarlo | No |

## Decisiones (ADR)

Este ticket no crea un ADR. Las nueve decisiones del diseño (`D-1` a `D-9`) las aprobó la persona dueña el 2026-11-10 y constan en `_index.md` y en `design.md`. La única con opciones descartadas y tamaño de ADR, `D-7`, tuvo una objeción de `auditor-docs` (F002, Mayor) y la persona dueña la **mantuvo sin ADR** el 2026-11-14. Excepción de la persona dueña (2026-11-14): `D-7` no tiene ADR; sus alternativas constan en `design.md`, `D-7`. Las demás decisiones (`D-1` a `D-6`, `D-8` y `D-9`) también descartaron alternativas, pero son elecciones locales del ticket, sin estructura nueva ni alcance fuera de `proveedores`, y su porqué consta en `design.md`.

### 2026-11-14 — La traducción de `lock_timeout` y `statement_timeout` entra en este ticket, también en el alta

**Contexto:** el diseño aceptó sin decisión de la persona dueña que el vencimiento de `lock_timeout` respondiera `500`, contra `RNF-16`; `auditor-docs` lo marcó Mayor en la revisión.
**Opciones consideradas:** dejarlo como `500` y diferir la traducción a otro ticket; traducir solo el cambio y la desactivación; traducir también el alta.
**Decisión:** traducir los tres, con un gestor de contexto que envuelve a `begin()` (el rollback ocurre antes de traducir). La persona dueña decidió primero el cambio y la desactivación y, a la pregunta de la revisión sobre el alta, la amplió el mismo día.
**Evidencia:** `TC-43`, los mutantes `M-13` y `M-14` y `rojo/fila-B3.txt` y `fila-B3-alta.txt`.
**Consecuencias:** el catálogo de proveedores queda alineado con `RNF-16`; la traducción de `55P03` y `57014` existe ahora en tres módulos (`archivos`, `presupuesto` y `proveedores`) como copias locales. Si aparece una cuarta, hay que valorar un ADR para llevarla a `contrato_error`.

→ Sin ADR del repositorio: la decisión es de alcance de un ticket y su evidencia consta en `impl.md`.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `str.upper()` reescribe `ß` como `SS`, `ı` como `I` y `ſ` como `S`: un RFC normalizado a mayúsculas puede aceptar entradas que no eran RFC. Hay que rechazar todo lo que no sea ASCII, `Ñ`, `ñ` o `&` **antes** de pasar a mayúsculas; el patrón sin `IGNORECASE` no sirve porque `ñ` minúscula debe seguir pasando | `F001` de `auditor-seguridad` en la entrega b, TC-23 con `ß`, `ı` y `ſ` y la regresión de `ñ` | Cualquier campo que se normalice con `upper()` o `lower()` antes de validarse contra un patrón |
| Un gestor de contexto que traduce errores del motor debe envolver a `begin()` y no estar dentro: así el rollback ocurre antes de traducir y no queda estado a medias | `TC-43`, `M-13d` y `M-14` | Cualquier caso de uso que deba traducir `55P03` o `57014` |
| Un `raise ... from error` conserva la causa original del `DBAPIError`, y ninguna aserción de estado lo ve: hay que afirmar `__cause__` | El mutante `M-13h2` sobrevivió hasta que el test comprobó `__cause__` | Todo test de traducción de excepciones |
| Pydantic fusiona dos clases en un solo componente del OpenAPI solo si su forma **y su docstring** coinciden | `TC-42` y `M-12`; el docstring de `Motivo` de `presupuesto` se igualó | Cualquier copia local de un DTO compartido (`D-7`) |
| Un `UPDATE` sin columnas no es válido en SQLAlchemy | `actualizar_proveedor` del repositorio devuelve sin ejecutar si recibe un mapa vacío | Cualquier actualización parcial por columnas |
| Los `.py` con CRLF en el árbol de trabajo se normalizan a LF al confirmar; un `sed -i` que reescribe todo el archivo cambia los finales de línea y rompe la huella SHA-256 de la mutación | Un tester convirtió `proveedores.py` con `sed -i`; se restauró byte a byte desde la copia | La aplicación de mutantes: Python por bytes, nunca `sed -i` |
| La matriz de `TC-43` incluye un caso de «error ajeno sigue siendo `500`» para el gestor; sin él, un `except DBAPIError` demasiado ancho pasa en verde | `M-13c` y `M-13h` | Cualquier traducción selectiva de excepciones |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | El diseño aceptó sin decisión de la persona dueña que `lock_timeout` respondiera `500`, contra `RNF-16`. `auditor-docs` lo halló como Mayor en `/sdd-revisar`, y costó una fila nueva (B3), dos mutantes sobrevivientes y una ampliación al alta decidida después. La plantilla de `design.md` no pide revisar cada operación con espera de bloqueo contra `RNF-16` | Media |
| `comando` | El alcance de B3 creció dos veces tras el diseño: primero el cambio y la desactivación, luego el alta (`O11` de `auditor-codigo`). Cada ampliación repitió rojo, mutación y reauditoría. Una pregunta única, «¿en qué operaciones?», habría decidido las tres | Media |
| `comando` | `auditor-codigo` revisó la entrega a por primera vez en `/sdd-revisar` del ticket completo, con cuatro Menores; la entrega a se había cerrado con `auditor-arquitectura` y `auditor-sql`. En un ticket partido, la revisión de la entrega a no corrió auditoría de código antes de acumularse | Baja |
| `herramienta` | Un tester aplicó un mutante con `sed -i` y convirtió el CRLF de `proveedores.py` a LF. La huella SHA-256 lo delató y se restauró desde la copia. El protocolo de mutación no dice cómo aplicar el cambio ni que debe preservar los finales de línea | Media |
| `herramienta` | El escaneo de secretos de `git-entrega` se detuvo con ocho falsos positivos por nombres de variables de CSRF en las pruebas; se verificó a mano con un `grep` propio y se confirmó que no había secretos | Baja |
| `herramienta` | Docker apagado al empezar la revisión: auditoría de código y la suite se detuvieron hasta que la persona lo encendió | Baja |
| `documentación` | La spec citaba la migración `0012` y la cabeza `0011` cuando TKT-059 ocupó `0012` durante el diseño, y `design.md` citaba un `ADR-041` equivocado. Es el desfase del diseño respecto de lo fusionado entre dos tickets | Baja |
| `herramienta` | `docs/api/openapi.yaml` cambió y obliga a decir «modifica las compuertas» al pedir la fusión; la propia ficha del ticket no lo anticipaba en su sección de cierre | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `dar_baja_proveedor`, `PROVEEDOR_CON_ORDENES_ABIERTAS` y la máquina de estados del proveedor (reactivación, baja desde `DESACTIVADO`) | Necesita órdenes de compra; partición de TKT-029 por el plazo de la tercera entrega | TKT-029b, tras TKT-019. Resolver antes el verbo de bitácora de la baja |
| Puerto `CatalogoProveedores` | Se construye con su primer consumidor | TKT-030 |
| Pantalla del catálogo y el desplegable de `FormularioCatalogo` | Fuera de alcance: es solo backend | TKT-032 |
| Reconciliar `docs/08-wireframes.md` con el borrador sobre la baja del proveedor | El boceto y el borrador difieren; no es de este ticket | TKT-032 |
| `409` de `PATCH` declarado en el borrador pero no emitido por una regla propia (`D-3`), y `422` y `403` sin documentar en las operaciones de lectura (`O1` y `O2` de `auditor-arquitectura`) | El borrador es el contrato y su corrección es otro cambio | TKT-029b o TKT-032 |
| Tres copias de la traducción de `55P03` y `57014` (`archivos`, `presupuesto`, `proveedores`) | Una cuarta decidiría un ADR para llevarla a `contrato_error` (`O12` de `auditor-codigo`) | Ticket por abrir si aparece la cuarta; id pendiente de la persona dueña |
| `D-7`: copias locales de `MetaPagina` y `Motivo` en `proveedores`, sin ADR | La persona dueña lo mantuvo así el 2026-11-14; el porqué consta en el comentario de cada copia, en `design.md` y en `TC-42` | Revisar si una tercera copia exige promover el DTO a un paquete común |
| Texto de los mensajes de `BLOQUEO_VENCIDO` y `TIEMPO_EJECUCION_VENCIDO`, elegido por el tester y no fijado en el diseño (asumido: pendiente de confirmar por la persona dueña) | Llega al cliente tal cual; nadie lo confirmó | Decisión pendiente de la persona dueña · ticket por abrir tras decidir |
| Observaciones opcionales de `auditor-codigo` y `auditor-arquitectura` sobre el alta: anidamiento de `crear_proveedor`, su docstring sin mencionar la traducción, un argumento de más en un helper de test y la lectura vencida sin variante HTTP (`O13` a `O16`, `O-5`) | No cambian el comportamiento | Ticket de limpieza por abrir; id pendiente de la persona dueña |
| CRLF en el árbol de trabajo de `proveedores.py` | Git lo normaliza al confirmar | Sin ticket: `.gitattributes` fija `eol=lf` y Git lo normaliza |

## Pull request

**Título:** `TKT-029a · Catálogo de proveedores, sin baja`
**Origen:** `agent`. El código lo escribieron agentes; la persona dueña decidió el alcance y las decisiones de la sesión.
**Cuerpo:** qué (las cinco rutas del catálogo de proveedores y su esquema), por qué (HDU-004 escenarios 2, 3 y la parte de desactivación del 12; el catálogo se adelanta para la tercera entrega y es lo que necesita la orden de compra), criterios cubiertos (`CA-1` a `CA-11`, `CA-R1` y `CA-R2`), cómo verificarlo (`uv run pytest`, `npm run tipos:verificar`) y una línea por entrega. Debe decir que **modifica las compuertas** (`docs/api/openapi.yaml`).

**Fusión con omisión:** el registro no va en este archivo. Va en un comentario del PR que el orquestador deja justo después de la fusión, con la aprobación explícita de la persona dueña en la sesión.
