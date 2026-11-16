# Delta · TKT-029b · Baja protegida de proveedores

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. El ticket se ejecutó en dos entregas sobre una sola rama, y este delta es **uno solo, del ticket entero**.

| Entrega | Qué aportó |
|---|---|
| TKT-029b-a (bitácora y `compras`) | La migración `0016` con el verbo `DAR_BAJA` y su bajada con guarda, el verbo en `AccionBitacora` y en el borrador, la regla pura que deriva el estado de una orden de compra, las tablas y el repositorio de lectura de órdenes de `compras`, y la primera función publicada en `cimenta.compras.interfaz`: `ordenes_pendientes_de_proveedor` |
| TKT-029b-b (baja, contrato y documentación) | La regla de dominio de la baja, el caso de uso `dar_baja_proveedor`, la ruta `POST /api/v1/proveedores/{proveedor_id}/baja`, los cambios del borrador OpenAPI y los tipos del cliente, y toda la documentación afectada, con el ADR de la decisión `D-3` y la pregunta abierta `PA-24` |

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `0016`: `ALTER TYPE accion_bitacora ADD VALUE 'DAR_BAJA'`; su bajada se niega con asientos `DAR_BAJA` y, si no los hay, recrea el tipo con los 22 verbos de `0003` sin cambiar ningún valor | `backend/migraciones/versions/v0016_auditoria_verbo_dar_baja.py` | Asentar la baja de un proveedor con su propio verbo en la bitácora de solo anexado, y poder revertir la migración sin perder el rastro |
| `EstadoOrden`, `CantidadesRenglon`, `estado_derivado` y `esta_pendiente` | `backend/cimenta/compras/dominio/orden_compra.py` | Derivar el estado de una orden (`ABIERTA`, `PARCIAL`, `CERRADA`) de sus cantidades ordenadas y recibidas, sin almacenarlo |
| Tablas Core `orden_compra` y `orden_compra_renglon`, y `leer_renglones_de_ordenes_vivas` | `backend/cimenta/compras/infraestructura/tablas.py`, `repositorio_orden_compra.py` | Leer los renglones de las órdenes vivas de un proveedor, ordenados por folio |
| `OrdenPendiente` y `ordenes_pendientes_de_proveedor`, publicadas en la interfaz | `backend/cimenta/compras/aplicacion/ordenes_pendientes.py`, `interfaz.py` | Que `proveedores` conozca las órdenes pendientes de un proveedor sin tocar tablas ni repositorios de `compras` |
| `RechazoBaja` y `rechazo_de_baja` | `backend/cimenta/proveedores/dominio/proveedor.py` | La regla pura: `BAJA` es terminal y precede a todo; cualquier orden pendiente impide la baja |
| `dar_baja_proveedor`, `MENSAJE_YA_DADO_DE_BAJA`, `_texto_ordenes` y `_rechazo_ordenes_pendientes` | `backend/cimenta/proveedores/aplicacion/proveedores.py` | Una transacción con `FOR UPDATE`, regla, cambio de estado y asiento `DAR_BAJA`; rechazos con el contrato de error completo |
| Ruta `dar_baja_proveedor` | `backend/cimenta/proveedores/api/rutas.py` | Exponer la baja con sesión, CSRF y rol `COMPRAS` |
| `sembrar_orden_compra` | `backend/herramientas/soporte_tkt029b_ordenes.py` | Sembrar órdenes de compra con el rol de aplicación en las pruebas |
| Seis archivos de pruebas del ticket y la evidencia de rojo por fila | `backend/tests/test_tkt029b_*.py`, `sdd/tickets/tkt-029b/rojo/` | Cubrir `CA-1` a `CA-14` y `CA-R1` a `CA-R4`, y dejar rastro de que cada fila empezó en rojo |
| ADR del verbo `DAR_BAJA` y de la bajada que recrea el tipo | `docs/adr/20261116-verbo-dar-baja-y-bajada-recreando-el-tipo.md` | Registrar la decisión `D-3` con sus alternativas y su evidencia |
| `PA-24` | `docs/01-descripcion-producto.md` | Dejar abierta la pregunta de si un proveedor dado de baja se reactiva y qué pasa con su RFC |
| Sección «Proveedor» con su diagrama de estados, escenario 13 de HDU-004 y entradas de glosario | `docs/03-modelo-datos.md` §14, `docs/04-historias-usuario.md`, `docs/glosario.md` | Documentar la máquina de estados del proveedor y el escenario de la baja sin órdenes pendientes |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `AccionBitacora` y su mensaje | `backend/cimenta/auditoria/dominio/asiento.py` | 22 verbos → 23, con `DAR_BAJA` al final |
| `docs/api/openapi.yaml` | `AccionBitacora`, `dar_baja_proveedor`, `desactivar_proveedor` | Enum de 22 verbos → 23; la baja declara `x-tickets: [TKT-029b]`, escenarios 12 y 13, el `409` con cabeceras `X-Correlacion-Id` y `Retry-After` y un ejemplo de dos órdenes; la desactivación deja de decir «Se admite siempre» y dice que se admite tenga o no órdenes pendientes, siempre que el proveedor esté `ACTIVO` |
| `frontend/src/api/generado/servidor.ts` | tipos generados | Regenerado con la operación de la baja y el verbo nuevo |
| Cinco afirmaciones de TKT-007 y sus docstrings | `test_tkt007_dominio.py`, `test_tkt007_dominio_consulta.py`, `test_tkt007_esquema.py`, `test_tkt007_fronteras.py` | «22 verbos» → «23 verbos» (decisión `D-7`) |
| TC-38 y TC-40 de TKT-029a, y la entrada de `/baja` | `test_tkt029a_api_proveedores.py`, `test_tkt057_csrf.py` | Cinco rutas y «no existe `/baja`» → seis rutas y «existe `/baja`»; la ruta nueva entra en `CUERPOS_VALIDOS` (`D-10`) |
| Documentación | `docs/02`, `docs/03` §9, §10 y §14, `docs/05`, `docs/06`, `docs/07`, `README.md`, `llms.txt`, `CLAUDE.md` | La desactivación ya no «se admite siempre»; «Veintidós verbos» → «Veintitrés»; el puerto `CatalogoProveedores` pasa de TKT-029 a TKT-030; los conteos de escenarios (164 → 165), de ADR (44 → 45) y de preguntas (23 → 24); 69 → 73 tickets en README y `llms.txt` (salvo la fila histórica de `README.md` línea 258) |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| La frase «se admite siempre» de la desactivación y la oferta incondicional de desactivar | `docs/03` §9, `docs/05`, `docs/07`, `docs/api/openapi.yaml` | Era una simplificación de TKT-029a, anterior a que existiera la baja: desde `DESACTIVADO` o `BAJA` desactivar responde `409` `ESTADO_NO_PERMITE_OPERACION`, que ya era el comportamiento. Solo cambia lo que dice la documentación |

## Comportamiento observable nuevo

- Compras puede dar de baja a un proveedor `ACTIVO` o `DESACTIVADO` con un motivo obligatorio. El proveedor pasa a `BAJA`, desaparece del listado por omisión, se sigue pudiendo consultar y la bitácora asienta `DAR_BAJA` con el estado anterior real y el motivo recortado.
- Si el proveedor tiene órdenes `ABIERTA` o `PARCIAL`, la baja responde `409` `CONFLICTO` con el código `PROVEEDOR_CON_ORDENES_ABIERTAS`, el nombre del proveedor, la cuenta de órdenes en singular o plural, y cada orden con `id`, `folio` y `estado`, ordenadas por folio. Desde `ACTIVO` ofrece la acción `DESACTIVAR_PROVEEDOR`; desde `DESACTIVADO` no ofrece ninguna. Las órdenes cerradas, las canceladas, las de otro proveedor y las que no tienen renglones no cuentan como pendientes, y una recepción con excedente autorizado deja la orden cerrada.
- Desde `BAJA`, la baja responde `409` `CONFLICTO` con `ESTADO_NO_PERMITE_OPERACION`: `BAJA` es terminal, y se evalúa antes que las órdenes pendientes. La baja no libera el RFC: un alta nueva con el mismo RFC sigue respondiendo `RFC_DUPLICADO`.
- Un motivo ausente, en blanco, de más de 2000 caracteres o con `NUL` responde `422`; un rol distinto de `COMPRAS` recibe `403` con el rechazo asentado; sin sesión, `401`; sin el par CSRF válido, `403`; un proveedor inexistente, `404`.
- Dos bajas simultáneas del mismo proveedor se serializan: la primera tiene éxito y la segunda recibe `ESTADO_NO_PERMITE_OPERACION`, con un solo asiento. Si otra transacción retiene la fila más de 5 s, o la consulta pasa de 15 s, la baja responde `409` `CONCURRENCIA` con `Retry-After: 1` y la acción «reintentar».
- `DAR_BAJA` pasa a ser el verbo número 23 de la bitácora, con el mismo orden en la base, en el dominio y en el borrador.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `POST /api/v1/proveedores/{proveedor_id}/baja` (`dar_baja_proveedor`) | Nueva: `200` con el `Proveedor` releído, `409` `PROVEEDOR_CON_ORDENES_ABIERTAS`, `409` `ESTADO_NO_PERMITE_OPERACION`, `409` `CONCURRENCIA`, `422`, `404`, `403`, `401` | No |
| `AccionBitacora` | Nuevo valor `DAR_BAJA`, al final del enum | No para quien lee la bitácora, salvo un cliente que valide el enum de forma cerrada con la lista anterior de 22 verbos |
| `POST /api/v1/proveedores/{proveedor_id}/desactivacion` | Solo cambia su descripción; el comportamiento no cambia | No |
| `accion_bitacora` (tipo de PostgreSQL) | Un valor nuevo; la bajada de `0016` se niega mientras haya asientos `DAR_BAJA` | No |
| `cimenta.compras.interfaz` | Primera función publicada: `ordenes_pendientes_de_proveedor` y el tipo `OrdenPendiente` | No |
| `frontend/src/api/generado/servidor.ts` | Regenerado con la operación de la baja | No |

## Decisiones (ADR)

### 2026-11-16 — El verbo `DAR_BAJA` entra con `ALTER TYPE … ADD VALUE` y su bajada recrea el tipo tras una guarda

**Contexto:** la bitácora es de solo anexado y permanente (`RN-04`, invariante 10); la baja necesitaba su propio verbo; un valor no se puede quitar de un `ENUM` de PostgreSQL sin recrear el tipo; y el valor nuevo no se puede usar en la transacción que lo añade (`55P04`), mientras que `env.py` corre todas las migraciones en una.
**Opciones consideradas:** (a) una bajada que se niega siempre; (b) una bajada que deja el valor en el tipo; (c) una bajada que recrea el tipo tras una guarda que se niega si hay asientos `DAR_BAJA`.
**Decisión:** la opción (c): reversible mientras no haya asientos, y nunca pierde un asiento.
**Evidencia:** la sonda del supuesto 5 del diseño (PostgreSQL 17) y TC-03, TC-04 y TC-05 contra el PostgreSQL de las pruebas.
**Consecuencias:** la bajada reescribe `bitacora.accion` sin cambiar ningún valor, con el rol de migración y bajo `ACCESS EXCLUSIVE`; ninguna migración posterior en el mismo `upgrade head` puede usar `DAR_BAJA`.

→ `docs/adr/20261116-verbo-dar-baja-y-bajada-recreando-el-tipo.md`, con su entrada en el índice.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Una lectura de `FOR UPDATE` y el `UPDATE` que le sigue vencen el mismo `lock_timeout`: una prueba por HTTP no distingue que falte el bloqueo de la lectura. Ese mutante solo lo mata una prueba de concurrencia que observe a la segunda transacción esperando | `M-9` sobrevivió a TC-42 y lo mató TC-30 | Todo diseño que declare «mutante X cae en la prueba Y» para un bloqueo pesimista |
| Un rojo escrito con importaciones dinámicas (para que la colección no falle) deja una limpieza que hay que planificar: con el código en verde esas importaciones son deuda y el `auditor-codigo` las marca | `F003` del `auditor-codigo`, en dos archivos | Filas cuyo rojo nace sobre símbolos aún inexistentes |
| Las cifras de la documentación que `verificar_docs.py` no comprueba (`llms.txt`, README) se desfasan en silencio: el verificador contó 73 tickets mientras dos documentos decían 69 | `F003` del `auditor-docs` | Todo ticket que añade un escenario, un ADR o una pregunta |
| Una oferta de acción condicional («desactivar solo si está `ACTIVO`») tiene que quedar escrita también en la historia de usuario, no solo en el diseño: el escenario 12 seguía diciendo que siempre se ofrece | `F007` de la reauditoría de `auditor-docs` | Toda regla que restringe una acción que la historia describía sin condición |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | El diseño nombró mal un identificador que el verificador de coherencia no pudo comprobar (`PETICIONES_VALIDAS` en lugar de `CUERPOS_VALIDOS`) y afirmó que `M-9` caía en TC-42 sin haberlo ejecutado. Es la misma raíz del diseño con un hueco que solo destapa la ejecución: una afirmación sobre qué prueba mata qué mutante, o sobre un nombre de archivo, se redacta sin comprobarla | Media |
| `agente` | `desarrollador-api` cambió `x-tickets` y `x-escenarios` de `desactivar_proveedor` además de su descripción, porque el encargo del orquestador mezcló las dos operaciones. El orquestador lo detectó al leer el diff del borrador; sin esa lectura habría llegado al PR | Media |
| `convención` | `auditor-codigo` pidió renombrar once tests para que llevaran el escenario en el nombre, contra el diseño aprobado, que fija `test_tkt029b_…` para los criterios sin escenario de la historia. La convención de nombres de los tests que no tienen un escenario HDU no está escrita en un solo lugar, y cada auditor la lee distinto | Media |
| `agente` | `auditor-docs` pidió un ADR para una decisión que el diseño aprobado había dicho que no lo merecía, y una pregunta abierta nueva. Las dos eran razonables y las aprobó la persona dueña, pero el criterio de «merece ADR» del diseño y el del auditor no coinciden y la divergencia solo apareció al final | Media |
| `comando` | La reauditoría acotada de documentación halló tres Mayores nuevos de redacción (escenario 12 sin la condición, dos supuestos sin `(asumido)`) que la primera pasada no vio. Con el paso 4 de `/sdd-revisar` se aplicaron sin una tercera reauditoría, pero un auditor que revisa por capas descubre cada vez algo distinto | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Reactivación de proveedores y qué hacer con un RFC en `BAJA` | Decisión de negocio que el PRD no toma; registrada como `PA-24` | Ticket futuro, según la respuesta del cliente |
| Índice por `orden_compra.proveedor_id` y medición de la consulta de órdenes pendientes | `D-9`: sin índice con el volumen de la fase 1; la lista del `409` tampoco tiene tope | TKT-032 |
| Puerto `CatalogoProveedores` y lectura del proveedor con `FOR SHARE` al emitir una orden | Hoy no existe la emisión, así que no hay carrera; el puerto lo estrena su primer consumidor | TKT-030 |
| Pantalla del catálogo y boceto de `docs/08-wireframes.md` que no refleja la baja protegida | Depende de TKT-030 y TKT-031 | TKT-032 |
| Si `COMPRAS` se limita algún día a obras asignadas, la lista de órdenes del `409` se vuelve una fuga entre obras | Hoy `COMPRAS` es un rol global y no hay asignación usuario-obra (observación `O3` de `auditor-seguridad`) | El ticket que introduzca la asignación |
| Enlazar el ADR nuevo desde la docstring de la migración `0016` | Es un archivo de código y la entrega b solo tocó documentación | Cualquier ticket que vuelva a tocar la migración |
| Un `# type: ignore[arg-type]` sin motivo en `test_tkt019_migracion.py`, `test_tkt029a_migracion.py` y `test_tkt059_migracion.py` | De tickets ya fusionados: no se tocan aquí | Una limpieza de pruebas |

## Pull request

**Título:** `TKT-029b · Baja protegida de proveedores`
**Origen:** `agent`: el código lo escribieron los agentes de la herramienta bajo la dirección del orquestador, y la persona dueña aprueba el diseño, las decisiones y la fusión.
**Cuerpo:** qué (la baja de un proveedor con motivo, protegida por las órdenes pendientes y atómica con su asiento), por qué (`HDU-004` escenarios 12 y 13), criterios cubiertos (`CA-1` a `CA-14` y `CA-R1` a `CA-R4`, todos `[M]`), y cómo verificarlo (suite completa `3654 passed, 26 skipped`, mutación, cuatro auditorías, y las diez comprobaciones del pipeline). Una línea por entrega. Se señala que el PR modifica `docs/api/openapi.yaml`, y que añade un ADR y la pregunta abierta `PA-24`.
