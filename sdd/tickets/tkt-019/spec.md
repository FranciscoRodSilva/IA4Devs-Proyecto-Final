# Spec · TKT-019 · Esquema y migraciones del módulo compras

> [← index](_index.md) | Siguiente: `design.md` (se enlaza en `/sdd-disenar`)

## Contexto y problema

El hilo vertical de la fase 1 va de la línea base a la requisición, el bloqueo o la autorización, la orden de compra, la entrada de material y el semáforo. Hoy el módulo `compras` es solo un esqueleto de carpetas: no tiene ninguna tabla, y por eso no puede existir ninguna regla de `RN-03`, ninguna orden de compra ni ningún folio. Este ticket crea **solo el esquema**: las tablas, sus restricciones, sus índices únicos y sus privilegios por rol, para que TKT-021, TKT-025, TKT-029b, TKT-030, TKT-033 y TKT-054 construyan sobre garantías que el motor ya sostiene. La migración nueva es `0014` y cuelga de `0013` (proveedores).

El ticket lleva además un segundo objetivo, independiente del esquema, que la persona dueña decidió incluir el 2026-11-14: **subir `dnspython`**. La auditoría de dependencias del pipeline (`pip-audit` y `tools/severidad_pip_audit.py`) falla desde hoy por `GHSA-vvf4-9x63-8xvv`, de severidad alta, en `dnspython` 2.9.0, que arrastra solo `email-validator`. El PR 74 y el PR 75 se fusionaron con ese rojo por decisión de la persona dueña. La causa es una vulnerabilidad nueva en una dependencia que no cambió, no un defecto del código: la candidata es la 2.9.2 (`uv lock --dry-run --upgrade-package dnspython` propone `2.9.0 → 2.9.2`), pero **este repositorio no registra que la 2.9.2 corrija el aviso**; solo lo comprobará el trabajo «Dependencias» (`(asumido)`, pregunta 1).

## Historia de usuario

El ticket no tiene historia propia: habilita la de [HDU-002](../../../docs/04-historias-usuario.md) y sus vecinas (HDU-003, HDU-004 y HDU-005), sin probar ninguno de sus escenarios. Por eso ninguna prueba de este ticket lleva el nombre `test_hduXXX_escYY`.

**Como** equipo que construye el control de costos de obra
**quiero** que el esquema de requisiciones, solicitudes de autorización, órdenes de compra y folios haga cumplir en el motor las garantías que el modelo de datos declara
**para** que las reglas de `RN-02`, `RN-03`, `RN-04`, `RN-06` y `RN-07` de los tickets siguientes no dependan de que cada caso de uso se acuerde de validar lo que la base ya puede impedir.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | Migración `0014` con siete tablas del módulo `compras`: `requisicion`, `requisicion_renglon`, `solicitud_autorizacion`, `orden_compra`, `orden_compra_renglon`, `folio_consecutivo` y `reprogramacion_entrega`. Invariantes 1, 2, 8 y 9 hechas cumplir por `NOT NULL` y `CHECK` con nombre. `orden_compra.proveedor_id` sin clave foránea. Privilegios por rol con su prueba ejecutada con el rol de aplicación. Reversible, con subida, bajada y subida probadas |
| **Must** | Subir `dnspython` en `backend/uv.lock` hasta que el trabajo «Dependencias» de `ci.yml` quede en verde, con su rechazo: sin versión corregida, la vulnerabilidad se ignora con `--ignore-vuln` fechado y con quien la decidió (decisión de la persona dueña, 2026-11-14) |
| **Should** | Que la prueba de esquema compruebe también que las tablas existentes no cambian (regresión de la cadena de migraciones y de la siembra local) |
| **Could** | — |
| **Won't** | Índices de rendimiento de [modelo de datos §15](../../../docs/03-modelo-datos.md#15-la-consulta-del-semáforo): pregunta abierta para el diseño (pregunta 10). Ninguna lógica, ruta, repositorio ni tipo del cliente |

## Non-goals

- No implementa lógica: ninguna regla de dominio, caso de uso ni función. El ticket entrega esquema y su prueba.
- No crea endpoints, DTO ni modifica el borrador OpenAPI: ninguna operación del borrador lleva `x-tickets: TKT-019`.
- No crea modelos Core ni repositorios en `compras/infraestructura/`: los crea el primer ticket que los consume (TKT-021).
- No crea `entrada_almacen`, `entrada_renglon` ni `movimiento_inventario` (invariante 38 y TKT-033): son del módulo `almacen`.
- No toca `proveedor`: la tabla es de TKT-029a. `orden_compra.proveedor_id` es una referencia lógica sin clave foránea, que valida el puerto `CatalogoProveedores` de TKT-029b y TKT-030.
- No actualiza ninguna otra dependencia del backend ni del frontend: solo `dnspython`.
- No añade una columna de existencia de inventario ni un motivo de cierre de la orden: el cierre con saldo no existe (`RN-06`).

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-02` | Toda requisición, orden de compra y entrada de almacén está imputada a una obra y a un tipo de partida. No existe gasto sin centro de costos | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RN-03` | Una requisición que excede el presupuesto disponible de su tipo de partida se bloquea y requiere autorización de Dirección General. Este ticket solo guarda el estado `BLOQUEADA` y las cifras con que se evaluó | PRD §8 |
| `RN-04` | Toda autorización y todo rechazo se registran con actor, momento y motivo, de forma permanente | PRD §8 |
| `RN-06` | El faltante se reprograma con una nueva fecha y motivo; la orden no se cierra hasta entregarse completa. No existe el cierre con saldo | PRD §8 |
| `RN-07` | No se recibe más de lo ordenado sin autorización de Dirección General; autorizado, el excedente se suma a la recepción | PRD §8 |

Invariantes del modelo de datos que el esquema hace cumplir: **1** (`obra_id` y `tipo_partida_id` no nulos), **2** (lo recibido no pasa de lo ordenado más el excedente autorizado), **8** (importes, precios y cantidades no negativos) y **9** (una solicitud resuelta lleva su motivo). Regla 6 de `CLAUDE.md`: todo gasto lleva `obra_id`, y toda requisición además `tipo_partida_id`.

## Invariantes que deben sobrevivir al cambio

El ticket añade una migración encima de la cabeza `0013`; no modifica tablas existentes, pero toca garantías generales que otras suites vigilan.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Cadena de migraciones, reversibilidad y privilegios por omisión de los tres roles | `0014` cuelga de `0013`, sube y baja limpia, y no abre permisos de más al rol de aplicación ni al de lectura | `CA-R1` |
| Esquema anterior intacto | Ninguna tabla existente cambia de columnas, restricciones ni privilegios; la siembra local sigue dejando vacías las tablas nuevas | `CA-R2` |
| Dependencias bloqueadas | Subir `dnspython` no cambia ninguna otra versión del `uv.lock`, y la suite del backend sigue en verde con la versión nueva | `CA-R3` |

## Dependencias cruzadas

Salida de `Grep` del identificador del ticket sobre `docs/05-tickets-trabajo.md`, los `_index.md` de `sdd/tickets/` y `tools/historias_activas.txt` (2026-11-14):

- `docs/05-tickets-trabajo.md`: TKT-019 es el esquema del hilo vertical (línea 845). Depende de TKT-011a (archivado). Lo necesitan TKT-021 (894), TKT-025 (1208), TKT-029b (1121), TKT-030 (1131), TKT-033 (1290) y TKT-054.
- `sdd/tickets/*/_index.md`: solo `tkt-029a` lo cita, como el ticket del que depende TKT-029b.
- `tools/historias_activas.txt`: sin coincidencias. Ningún escenario de HDU-002 se activa con este ticket.

TKT-019 no activa ninguna historia y no depende de nada de fase 2.

## Criterios de aceptación

Las pruebas de esquema siguen el patrón `test_tkt019_caNN_…`. Cada rechazo comprueba `sqlstate` y `constraint_name`, no solo que falle, y lleva su control positivo en el borde.

### CA-1 `[M]` · Las siete tablas existen con sus tipos y sus llaves · `RN-02`

```gherkin
Escenario: La migración crea el esquema de compras
  Dado una base migrada hasta 0013
  Cuando se aplica la migración 0014
  Entonces existen las siete tablas del módulo compras con llave primaria nombrada
  Y los importes son NUMERIC(18,4) y los precios y las cantidades NUMERIC(14,4)
  Y las fechas de negocio son DATE y los instantes TIMESTAMPTZ
  Y cada enumeración es text NOT NULL con un CHECK ... IN nombrado ck_<tabla>_<columna>, nunca un ENUM
  Y las claves foráneas hacia obra, tipo_partida, insumo y usuario existen con ON DELETE RESTRICT (asumido, pregunta 7)
```

### CA-2 `[M]` · Rechazo · Requisición sin obra o sin tipo de partida · `RN-02` · `INV-1`

```gherkin
Escenario: El motor rechaza una requisición sin centro de costos
  Dado una obra y un tipo de partida existentes
  Cuando se inserta una requisición con obra_id nulo
  Entonces el motor rechaza con 23502 sobre la columna obra_id
  Y lo mismo ocurre con tipo_partida_id nulo y con obra_id nulo en orden_compra
  Y una requisición con ambos valores se inserta sin error
```

### CA-3 `[M]` · Estados de la requisición, con `RECHAZADA` distinta de `CANCELADA` · `RN-04`

```gherkin
Escenario: El estado admite los siete valores y ninguno más
  Dado la tabla requisicion
  Cuando se inserta con estado BORRADOR, EVALUADA, BLOQUEADA, AUTORIZADA, RECHAZADA, CANCELADA y CONVERTIDA
  Entonces cada inserción prospera
  Cuando se inserta con estado "SIN_EFECTO" o con estado nulo
  Entonces el motor rechaza el valor desconocido con 23514 sobre ck_requisicion_estado y el estado nulo con 23502
  Y RECHAZADA y CANCELADA son valores distintos, y requisicion lleva motivo_cancelacion
```

### CA-4 `[M]` · Rechazo · Cifras negativas · `INV-8`

```gherkin
Escenario: Ninguna cantidad ni importe es negativo, salvo el disponible
  Dado un renglón de requisición y un renglón de orden válidos
  Cuando cantidad, costo_unitario_estimado, importe, importe_solicitado, cantidad_ordenada, cantidad_recibida o costo_unitario valen -0.0001
  Entonces el motor rechaza con 23514 sobre ck_<tabla>_<columna>_no_negativo
  Y el valor 0 se inserta sin error
  Pero importe_disponible y cantidad_disponible aceptan valores negativos, porque una excepción autorizada puede dejar el consumido por encima del tope (decisión de la persona dueña, 2026-11-14)
```

### CA-5 `[M]` · Folio consecutivo y único · `RN-02`

```gherkin
Escenario: Cada serie guarda su último folio y cada documento tiene folio único
  Dado la tabla folio_consecutivo con las series REQUISICION y ORDEN_COMPRA
  Cuando el rol de aplicación ejecuta SELECT ... FOR UPDATE y UPDATE sobre una serie
  Entonces ambas operaciones prosperan
  Y una serie distinta de las dos se rechaza con 23514
  Y dos requisiciones con el mismo folio, o dos órdenes con el mismo folio, se rechazan con 23505 sobre su índice único
  Y el último folio de una serie no puede ser negativo
```

### CA-6 `[M]` · Rechazo · Solicitud resuelta sin motivo · `RN-04` · `INV-9`

```gherkin
Escenario: Autorizar o rechazar exige motivo
  Dado una solicitud de autorización
  Cuando se inserta con estado AUTORIZADA o RECHAZADA y motivo_resolucion nulo
  Entonces el motor rechaza con 23514 sobre el CHECK del invariante 9
  Pero una solicitud PENDIENTE sin motivo se inserta sin error
  Y una AUTORIZADA o RECHAZADA con motivo se inserta sin error
  Y un estado fuera de PENDIENTE, AUTORIZADA y RECHAZADA se rechaza con 23514
```

### CA-7 `[M]` · Rechazo · La solicitud por excedente de lo ordenado apunta a su renglón · `RN-07`

```gherkin
Escenario: EXCEDE_ORDENADO exige el renglón y la cantidad, y solo él
  Dado una solicitud con motivo EXCEDE_ORDENADO
  Cuando orden_compra_renglon_id o cantidad_excedente es nulo
  Entonces el motor rechaza con 23514
  Y con cualquier otro motivo, si alguno de los dos viene con valor, el motor rechaza con 23514
  Y con EXCEDE_ORDENADO y los dos valores, y cantidad_excedente mayor que cero, la solicitud se inserta
  Y los motivos admitidos son EXCEDE_PRESUPUESTO, EXCEDE_ORDENADO, EXCEDE_CONSIGNACION y TRABAJO_EXTRA
```

### CA-8 `[M]` · Rechazo · Recibir más de lo ordenado sin autorización · `RN-07` · `INV-2`

```gherkin
Escenario: Lo recibido solo pasa de lo ordenado por el excedente autorizado
  Dado un renglón de orden con cantidad_ordenada 10 y cantidad_excedente_autorizada 0 por omisión
  Cuando cantidad_recibida pasa a 10.0001
  Entonces el motor rechaza con 23514 sobre ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado
  Pero con cantidad_excedente_autorizada 2 y cantidad_recibida 12 la actualización prospera
  Y cantidad_excedente_autorizada negativa se rechaza con 23514
  Y cantidad_recibida nace en 0
```

### CA-9 `[M]` · La orden de compra: sin clave foránea al proveedor y sin cierre con saldo · `RN-06`

```gherkin
Escenario: La orden guarda al proveedor como referencia lógica y no tiene motivo de cierre
  Dado la tabla orden_compra
  Cuando se inspecciona el catálogo
  Entonces proveedor_id no tiene ninguna clave foránea
  Y la orden tiene motivo_cancelacion y no tiene ninguna columna de motivo de cierre
  Y el estado ABIERTA, PARCIAL o CERRADA no se guarda: se deriva de las cantidades (decisión de la persona dueña, 2026-11-14)
  Y solo la cancelación se persiste, junto con su motivo, y no puede haber motivo sin cancelación ni cancelación sin motivo (asumido, pregunta 3)
```

### CA-10 `[M]` · Reprogramación de la entrega · `RN-06`

```gherkin
Escenario: Toda reprogramación guarda su motivo
  Dado la tabla reprogramacion_entrega y un renglón de orden con fecha_compromiso
  Cuando se inserta una reprogramación con motivo nulo o vacío
  Entonces el motor rechaza con 23502 o con 23514
  Y con fecha anterior, fecha nueva, saldo pendiente no negativo, motivo, quien la registró y cuándo se inserta sin error
  Y orden_compra_renglon tiene la columna fecha_compromiso de tipo DATE
```

### CA-11 `[M]` · Privilegios por rol, con su prueba · `RN-04`

```gherkin
Escenario: El rol de aplicación solo borra lo que puede borrarse
  Dado la migración aplicada y la conexión con el rol de aplicación
  Cuando intenta DELETE sobre solicitud_autorizacion, reprogramacion_entrega, orden_compra, orden_compra_renglon o folio_consecutivo
  Entonces el motor responde 42501
  Y también responde 42501 a un UPDATE sobre reprogramacion_entrega y a un INSERT sobre folio_consecutivo (design D-17)
  Y el rol de aplicación tiene exactamente SELECT, INSERT, UPDATE y DELETE sobre requisicion y requisicion_renglon; SELECT, INSERT y UPDATE sobre solicitud_autorizacion, orden_compra y orden_compra_renglon; SELECT e INSERT sobre reprogramacion_entrega; y SELECT y UPDATE sobre folio_consecutivo (design D-17)
  Pero un DELETE sobre una requisicion que no está en BORRADOR, o sobre un renglón de ella, se rechaza con IN002 sobre trg_requisicion_borrado_solo_borrador o trg_requisicion_renglon_borrado_solo_borrador (design D-3, opción B; con la opción A el DELETE se revoca en las dos tablas y responde 42501)
  Y un BORRADOR se borra con sus renglones sin error
  Y el rol de lectura solo tiene SELECT sobre las siete tablas
  Y nadie recibe TRUNCATE, REFERENCES, TRIGGER ni MAINTAIN
```

Los privilegios exactos y los disparadores salen de las decisiones `D-3` y `D-17` del diseño, aprobadas el 2026-11-15.

### CA-12 `[M]` · Auditoría de dependencias en verde · `RNF-08`

Se verifica en el pipeline de un PR real (y en local con `pip-audit` y el filtro): ninguna prueba de `pytest` lo cubre, y se anota en `impl.md` como «se verifica en `/sdd-completar`».

```gherkin
Escenario: Tras subir dnspython la auditoría ya no marca ningún hallazgo alto
  Dado backend/uv.lock con dnspython 2.9.0 y el aviso GHSA-vvf4-9x63-8xvv de severidad alta
  Cuando se sube dnspython con uv lock --upgrade-package dnspython
  Y se corre el trabajo «Dependencias» (pip-audit y tools/severidad_pip_audit.py)
  Entonces el filtro sale con 0
  Y el único cambio de versión del lock es el de dnspython (y sus hashes)
```

### CA-13 `[M]` · Rechazo · Si no hay versión corregida, se ignora con fecha · `RNF-08`

```gherkin
Escenario: Sin parche, el aviso se ignora de forma visible y fechada
  Dado que la versión más nueva de dnspython sigue marcada con GHSA-vvf4-9x63-8xvv
  Cuando el trabajo «Dependencias» corre
  Entonces el filtro sigue saliendo con 1 mientras no exista la excepción
  Y la excepción se añade como --ignore-vuln GHSA-vvf4-9x63-8xvv en el paso de pip-audit de ci.yml
  Y un comentario nombra a la persona dueña que la decidió, el motivo y la fecha de revisión
  Y ninguna otra vulnerabilidad queda ignorada
```

### CA-R1 `[M]` · Regresión · La migración encaja en la cadena

```gherkin
Escenario: 0014 cuelga de 0013, 0015 de 0014, y las dos son reversibles
  Dado la cadena de migraciones
  Cuando se lista la cabeza
  Entonces 0014 cuelga de 0013 y 0015 de 0014, y hay una sola cabeza, 0015 (design D-8: la siembra de los folios va en su propia migración)
  Y subir hasta 0014, bajar a 0013 y volver a subir deja el esquema idéntico
  Y subir hasta 0015 siembra las dos series, bajar a 0014 las quita y volver a subir las siembra igual
  Y la bajada no deja ninguna tabla, restricción ni privilegio de compras
```

### CA-R2 `[M]` · Regresión · El esquema anterior no cambia

```gherkin
Escenario: Las tablas existentes siguen igual
  Dado la fotografía del esquema de 0013 (tablas, columnas, restricciones, privilegios)
  Cuando se aplica 0014
  Entonces la fotografía de todo lo anterior es idéntica
  Y la siembra local deja vacías las siete tablas nuevas
```

### CA-R3 `[M]` · Regresión · Solo cambia dnspython

```gherkin
Escenario: El lock cambia lo mínimo
  Dado el uv.lock antes y después de subir dnspython
  Cuando se comparan los paquetes
  Entonces solo difiere dnspython
  Y uv sync --locked sigue funcionando
  Y la suite del backend sigue en verde
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Con reserva | Reúne dos objetivos independientes (esquema y dependencia) por decisión de la persona dueña. Cada uno se verifica y se despliega por separado |
| **N** | Describe el qué, no impone el cómo | Sí | Nombres de columna y de restricción salen del modelo de datos; el cómo (orden de sentencias, nombres finales) es del diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Habilita HDU-002 a HDU-005 para el equipo; destraba el pipeline de dependencias |
| **E** | Estimable sin investigar antes | Sí | El patrón de `0013` y de sus pruebas existe. El bump de `dnspython` no necesita investigación previa, solo su comprobación |
| **S** | Cabe en una sesión sin romper contexto | Con reserva | El backlog lo marca S; con siete tablas, sus restricciones y las pruebas es más probable M. El diseño decide si se parte |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es una prueba de esquema con `sqlstate` y `constraint_name`, o una corrida del trabajo de CI |

Sin fallos. Dos reservas (I y S) que no suman un fallo.

## Definition of Done

La de una funcionalidad de esquema, de `sdd/metodologia.md` §8 «Definition of Done por tipo».

- [ ] `CA-1` a `CA-13`, `CA-R1`, `CA-R2` y `CA-R3` cubiertos por pruebas, cada rechazo con `sqlstate` y `constraint_name`
- [ ] Ciclo TDD por fila del diseño, con el rojo registrado
- [ ] Prueba de subida, bajada y subida, y de privilegios con el rol de aplicación
- [ ] Mutación sobre las restricciones críticas (invariantes 1, 2, 8 y 9)
- [ ] `docs/03-modelo-datos.md` actualizado: el diagrama de `orden_compra`, la excepción del disponible al invariante 8, las referencias lógicas nuevas, los privilegios y los índices
- [ ] `docs/05-tickets-trabajo.md` del ticket actualizado con las decisiones de esta spec
- [ ] Trabajo «Dependencias» de `ci.yml` en verde en el PR (se verifica en `/sdd-completar`)
- [ ] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios; `python tools/verificar_docs.py` en verde

## Preguntas abiertas y supuestos

Las preguntas 1 a 4 están **decididas** por la persona dueña (2026-11-14). De la 5 en adelante son preguntas para el diseño, cada una con mi recomendación; ninguna se rellena con un supuesto silencioso.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| 1 | `dnspython` 2.9.2 (candidata de `uv lock --dry-run`) corrige `GHSA-vvf4-9x63-8xvv` `(asumido)` | `CA-12` no se cumple con esa versión; se aplica `CA-13` | Se comprueba en la fila del diseño que corre `pip-audit` |
| 2 | Sin versión corregida, se ignora con `--ignore-vuln` fechado y firmado por la persona dueña | — | **Decidido** por la persona dueña, 2026-11-14 |
| 3 | `importe_disponible` y `cantidad_disponible` quedan exentos del `CHECK >= 0` del invariante 8 | Si no, se perdería cuánto se sobregiró | **Decidido** por la persona dueña, 2026-11-14. Hay que documentar la excepción en el modelo de datos |
| 4 | El estado de la orden (`ABIERTA`, `PARCIAL`, `CERRADA`) no se guarda: se deriva de las cantidades. Solo la cancelación se persiste | El diagrama ER de `docs/03` y el OpenAPI (`estado` de la orden) hay que reconciliarlos: el modelo dice «no se fija a mano» y el diagrama le pone columna | **Decidido** por la persona dueña, 2026-11-14. El diseño reconcilia `docs/03` y avisa del cambio de contrato si lo hay |
| 4b | Cómo se guarda la cancelación de la orden, ya que el estado derivado no se guarda: recomiendo `cancelada_en` (nulable) con `motivo_cancelacion`, y un `CHECK` de que ambos son nulos o ambos tienen valor | Sin ese `CHECK` cabría una orden con motivo y sin cancelar, o cancelada sin motivo. Y la consulta del `consumido` de §15 filtra órdenes `ABIERTA` y `PARCIAL`: sin columna de estado tendrá que excluir las canceladas con `cancelada_en IS NULL`, y TKT-021 debe saberlo | Abierta para el diseño |
| 5 | `solicitud_autorizacion.entidad_id` es polimórfica (`REQUISICION` u `ORDEN_COMPRA`): no puede tener clave foránea y **no está en la lista cerrada de referencias sin clave foránea de §2** | La regla de cierre de §2 no la acepta sin su motivo. Recomiendo añadirla a §2 con su motivo, y un `CHECK` de que `entidad_tipo` es una de las dos | Abierta para el diseño |
| 6 | Privilegios de `DELETE`: ningún documento los fija por tabla. Recomiendo `DELETE` solo sobre `requisicion` y `requisicion_renglon` (HDU-002 esc. 2 deja eliminar un borrador), y revocado en las demás; la bitácora y `solicitud_autorizacion` son permanentes (`RN-04`) | Un `DELETE` de más rompería el «permanente» de `RN-04`. Además, un privilegio de `DELETE` no distingue estados: concedido sobre `requisicion`, permitiría borrar una requisición `EVALUADA` y con ella su peso en el `consumido`, que es justo lo que la regla 5 de `CLAUDE.md` prohíbe. Hay que decidir entre revocar `DELETE` en todas y que el borrador se cancele, o un disparador que solo deje borrar `BORRADOR` | Abierta para el diseño; es la objeción 1 de la pasada adversarial |
| 7 | `ON DELETE` de las claves foráneas de compras: solo está fijado para las de `presupuesto`. Recomiendo `RESTRICT` en todas | Un `CASCADE` borraría gasto al borrar una obra | Abierta para el diseño |
| 8 | Cuántas órdenes por requisición: TKT-030 dice «como mucho una», pero cancelar una orden devuelve la requisición y permite convertirla otra vez. Recomiendo un índice único parcial `WHERE` la orden no está cancelada | Un `UNIQUE (requisicion_id)` simple impediría reconvertir; ninguno permitiría dos órdenes vivas | Abierta para el diseño |
| 9 | `fecha_compromiso` del renglón: ¿nulable? `OrdenCompraNueva` la marca obligatoria, TKT-030 la da como opcional `(asumido)`. Y `primera_fecha_compromiso` del API no tiene columna. Recomiendo `NULL` y que `reprogramacion_entrega` guarde la primera | `RN-06` no podría distinguir «sin fecha» de «reprogramada» | Abierta para el diseño y para TKT-030 |
| 10 | Índices de §15 (`requisicion (obra_id, tipo_partida_id, estado)` y el parcial de `orden_compra_renglon`): ¿los crea este ticket? Recomiendo sí, porque son parte del esquema que la consulta del semáforo exige y no dependen de lógica | El `consumido` de `RN-03` lee sin índice hasta que alguien los cree | Abierta para el diseño |
| 11 | Formato y alcance del folio: los ejemplos del API son `REQ-AP05825-0042` (con el código de obra), y el ticket dice consecutivo global por serie. ¿Quién siembra las dos filas de `folio_consecutivo`? Recomiendo que la migración las siembre en cero, y que el formato lo arme el caso de uso (TKT-021) | Sin filas sembradas, el primer alta no tiene qué bloquear | Abierta para el diseño |
| 12 | Columnas del API sin columna en el modelo: `requisicion.observaciones`, `creado_en` y `actualizado_en` de requisición y de orden, `SolicitudAutorizacion.obra` y `entidad_tipo` cerrado a `REQUISICION, ORDEN_COMPRA`. Recomiendo añadirlas | El API no podría devolver lo que promete | Abierta para el diseño |
| 13 | `requisicion_renglon.costo_unitario` en el ticket frente a `costo_unitario_estimado` en el modelo y el OpenAPI. Recomiendo `costo_unitario_estimado` | Un nombre equivocado obliga a otra migración | Abierta para el diseño |
| 14 | Inv. 9 incompleto: ¿una resolución exige también `resuelta_por_id` y `resuelta_en`? HDU-003 esc. 4 los nombra. Recomiendo que el `CHECK` los exija junto con el motivo | Una resolución sin actor ni momento viola `RN-04` | Abierta para el diseño |
| 15 | `cantidad_excedente` de la solicitud: el API la tipa positiva. Recomiendo `CHECK > 0` | Con `>= 0` cabría una solicitud de excedente cero | Abierta para el diseño |
| 16 | Valores de `regla_negocio`, `regla_bloqueo` y `rol_autorizador`, y si `rol_autorizador` lleva clave foránea a `rol`. Recomiendo `CHECK IN` con las reglas conocidas y clave foránea | Textos libres dejan pasar valores que ninguna regla entiende | Abierta para el diseño |
| 17 | Glosario: dice que la orden «nace de una requisición autorizada», pero el modelo también la emite desde `EVALUADA`. «Autorizada» ahí no es el estado `AUTORIZADA` | Un desarrollador podría exigir el estado y bloquear órdenes de requisiciones evaluadas | Se corrige el glosario en este cambio, con tu visto bueno al aprobar el diseño |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Un privilegio `DELETE` sobre `requisicion` no distingue estados: el rol de aplicación podría borrar una requisición `EVALUADA` o `AUTORIZADA` y con ella su peso en el `consumido`, contra la regla 5 de `CLAUDE.md`. El criterio `CA-11` lo daba por bueno | `CA-11` y la pregunta 6 ahora dependen de la decisión del diseño (revocar todo o disparador solo para `BORRADOR`); se pide la decisión a la persona dueña |
| 2 | Alta | `CA-13` decía que el filtro «sale con 2»: `tools/severidad_pip_audit.py` sale con 1 si hay hallazgos que fallan y con 2 solo si falta el informe. Un test escrito del criterio habría esperado el código equivocado | Corregido a 1 con el dato de `severidad_pip_audit.py` (líneas 230 a 246) |
| 3 | Media | `CA-12` y `CA-13` no se pueden probar con `pytest`: dependen del pipeline. Sin decirlo, la Definition of Done quedaría con criterios `[M]` sin test | Añadida la nota en `CA-12`: se verifica en `/sdd-completar`, como ya hace el gate para los criterios de pipeline |
| 4 | Media | Persistir solo la cancelación deja a la consulta del `consumido` de §15 filtrando por estado derivado: una orden cancelada con saldo pendiente se contaría si TKT-021 no la excluye | Pregunta 4b ampliada: la consulta debe usar `cancelada_en IS NULL`, y TKT-021 debe saberlo |
| 5 | Baja | `CA-3` aceptaba «23514 o 23502» para el mismo caso: una prueba tan laxa no distingue un `CHECK` roto de una columna sin `NOT NULL` | Separado: valor desconocido es 23514 y estado nulo es 23502 |

Veredicto: cinco objeciones sustantivas, todas acogidas. La 1 queda como decisión abierta de la persona dueña. Verificación adversarial independiente: no se activa, porque el ticket no es de comisiones, precios, inventario ni pedidos y no es irreversible.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

- **Migración:** `backend/migraciones/versions/v0014_compras_esquema.py` (nombre por confirmar en el diseño), con `down_revision = "0013"`. Patrón de `v0013_proveedores_catalogo.py`: una tupla de sentencias, cada una en su `op.execute`, y la bajada con `DROP TABLE`.
- **Modelo de datos:** `docs/03-modelo-datos.md` §5 (tablas `REQUISICION`, `REQUISICION_RENGLON`, `FOLIO_CONSECUTIVO`, `SOLICITUD_AUTORIZACION`, `ORDEN_COMPRA`, `ORDEN_COMPRA_RENGLON` y `REPROGRAMACION_ENTREGA`), §2 (convenciones y lista cerrada de referencias sin clave foránea), §13 (invariantes 1, 2, 8, 9) y §15 (el `consumido`).
- **Pruebas:** nuevo `backend/tests/test_tkt019_migracion.py`, con el patrón de `test_tkt029a_migracion.py` (`fotografia()`, `base_vacia`, `migrar`, `conectar("aplicacion")`) y los datos de `datos_presupuesto` (`usuario`, `obra`, `tipo_partida`, `insumo`).
- **Permisos:** los privilegios por omisión de `0001` conceden `SELECT, INSERT, UPDATE, DELETE` al rol de aplicación y `SELECT` al de lectura sobre toda tabla nueva; cada migración declara el `GRANT` y el `REVOKE` explícitos.
- **Dependencia:** `dnspython` solo la arrastra `email-validator` 2.3.0 (`backend/uv.lock`, `{ name = "dnspython" }` sin especificador). Comando previsto: `uv lock --upgrade-package dnspython`, sin tocar `pyproject.toml`. El trabajo «Dependencias» de `.github/workflows/ci.yml` exporta el lock, corre `pip-audit` con `|| true` y decide `tools/severidad_pip_audit.py`, que falla con alta, crítica o desconocida.
- **Compuertas del PR:** `backend/uv.lock` y, si se tocara, `backend/pyproject.toml` están en la lista de compuertas que el resumen de fusión debe nombrar («modifica las compuertas»), y un `--ignore-vuln` en `ci.yml` también (`.github/`).
- **Esqueleto actual:** `backend/cimenta/compras/` solo tiene los `__init__.py` de `api`, `aplicacion`, `dominio` e `infraestructura` y un `interfaz.py` con su docstring.
