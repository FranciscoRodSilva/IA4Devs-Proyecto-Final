# Spec · TKT-010 · Datos semilla con catálogos

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

CIMENTA tiene hoy las tablas del módulo `presupuesto` (TKT-011a) y los seis roles de acceso (TKT-003), pero ninguna fila de negocio. Sin ellas, el alta de obra de TKT-012 falla por clave foránea (`obra.empresa_id` es obligatoria), el selector de tipos de partida de HDU-002 no tiene qué mostrar, el importador de TKT-014 no tiene un catálogo contra el cual buscar insumos y nadie puede iniciar sesión con un rol concreto para probar a mano. Este ticket de fundación entrega ese arranque.

El ticket original pedía «los 27 insumos reales de la explosión de Union Square». Eso no se puede cumplir: los presupuestos del cliente no se versionan porque el repositorio es público y [`RNF-07`](../../../docs/01-descripcion-producto.md) lo prohíbe (`README.md`, sección de documentos de contexto). La persona dueña decidió el 2026-11-01 sembrar **insumos sintéticos con forma real**, y que vivan en una herramienta que solo corre contra una base local, no en una migración, para que producción nunca reciba un catálogo inventado.

Estado de partida, criterio por criterio:

| Criterio del ticket | Estado de partida |
|---|---|
| Fila única de `empresa` | La tabla existe (`v0006`) y está vacía. No hay valor documentado para `rfc`, que es `NOT NULL` |
| Un usuario por cada uno de los seis roles | Los seis `rol` están sembrados por la migración `0002` con identificadores fijos. No existe ningún `usuario`, y `docs/arranque-local.md` dice que no hay alta de usuarios (`PA-T13`). Solo existe `frontend/e2e/sembrar_usuario_humo.py`, que siembra un usuario `COMPRAS` y deriva el hash con `PasswordHash.recommended()` en lugar de `ContrasenasArgon2` |
| Catálogo de `tipo_partida` | La tabla existe y está vacía. Las cuatro claves están en `PA-01` del PRD |
| 27 insumos con unidades y precios, con la clave del importador | Las tablas `insumo` y `precio_insumo` existen y están vacías. La regla de clave del importador no está escrita en ningún documento: TKT-014 solo dice «da de alta los insumos que no existan» y no tiene spec |
| Idempotente | No hay carga alguna |
| Entornos | No existe ajuste de entorno. La única guarda de entorno que existe es la del script de humo: rechaza hosts no locales, `PGHOSTADDR` y `PGSERVICE` |

Decisiones de la persona dueña, tomadas el 2026-11-01 en el intake:

1. **Insumos sintéticos con forma real**, sin precios del cliente. Mismo precedente que TKT-004.
2. **Partición del mecanismo.** Una migración de Alembic siembra lo que es real y necesario en todo entorno (`empresa`, `tipo_partida`). Una herramienta en `herramientas/` siembra lo que no debe existir fuera de una base local: los seis usuarios y los 27 insumos con sus precios.
3. **Usuarios solo en local,** con la contraseña leída del entorno. El «primer usuario en producción» (`PA-T13`) queda abierto y fuera de este ticket.
4. **La clave de insumo** se define aquí `(asumido)` y TKT-014 la hereda.
5. **Detalles menores:** RFC genérico público del SAT `(asumido)`, identificadores fijos, ningún conflicto sobrescribe una fila existente, vigencia de los precios desde el 2026-01-01 `(asumido)`, sin asiento en la bitácora, y guarda de entorno por host local, como el script de humo.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario asociada. El rol que lo usa es quien desarrolla el proyecto, persona o agente.

**Como** persona o agente que desarrolla CIMENTA
**quiero** una empresa, los cuatro tipos de partida, seis usuarios de prueba y un catálogo de insumos que puedan cargarse una y otra vez
**para** que TKT-012 dé de alta una obra, TKT-014 encuentre sus insumos y las pruebas manuales entren con cada rol, sin que producción reciba nunca una credencial conocida ni un dato inventado.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Una migración de Alembic que siembra, **con identificadores fijos**, la fila única de `empresa` —Constructora Celsius, RFC genérico `(asumido)`, activa— y los cuatro `tipo_partida` (`MUROS`, `PLAFONES_Y_CAJILLOS`, `ENCHAPES`, `GENERALES`). La empresa se inserta primero. Reversible |
| | **M2.** Una herramienta en `herramientas/` que siembra seis usuarios, uno por cada rol de acceso, con correo en minúsculas, contraseña leída del entorno y hash derivado con la misma clase `ContrasenasArgon2` que usa el inicio de sesión |
| | **M3.** La misma herramienta siembra 27 insumos sintéticos —`MATERIAL`, con unidad del catálogo cerrado y `creado_en_importacion = false`— y un precio general vigente por insumo (`obra_id` nulo, `vigente_desde` 2026-01-01 `(asumido)`) |
| | **M4.** Contrato de clave de insumo: `insumo.codigo` es el texto del código, sin espacios en los extremos y en mayúsculas `(asumido)`, y todo código sembrado ya cumple esa normalización |
| | **M5.** Idempotencia: ejecutar la migración y la herramienta dos veces no duplica ni modifica nada. Una fila existente con otros valores se deja intacta, nunca se sobrescribe |
| | **M6.** Rechazos de la herramienta: sin la contraseña en el entorno no escribe nada; con un host que no es local, o con `PGHOSTADDR` o `PGSERVICE` definidos, se niega **antes de conectar** |
| | **M7.** Lo que no se siembra, comprobado: ninguna obra, empleado, proveedor, `rol_oficio` ni dato simulado |
| | **M8.** Regresión: lo que ya funciona sigue funcionando (sección de invariantes). Incluye que las pruebas de TKT-011, que hoy insertan sus propias filas `MUROS` y `empresa`, sigan en verde con la plantilla ya sembrada |
| **Should** | **S1.** Consecuencia documental de M1 a M7, sin ampliar el alcance: el comando nuevo en `CLAUDE.md` y en `docs/arranque-local.md` (y la línea que dice que no hay usuarios), las variables nuevas en `.env.example`, y la corrección de los criterios del ticket en `docs/05-tickets-trabajo.md` (insumos sintéticos y en la herramienta, no reales y en la migración) |
| | **S2.** La bajada de la migración se niega, sin borrar nada, si una obra ya referencia la empresa o un tipo de partida sembrados |
| **Could** | — |
| **Won't** | Obras, empleados, proveedores, `rol_oficio` y datos simulados de mano de obra y avance (non-goals del ticket) · insumos o precios del cliente, reales o parciales · un ajuste de entorno (`local`, `pruebas`, `produccion`) que ningún ticket pidió · alta de usuarios o primer usuario en producción (`PA-T13`) · rotación de contraseña de un usuario ya sembrado · la lectura del Excel y la reconciliación con `2755187.21` (TKT-014 y TKT-016) · el endpoint de insumos y de tipos de partida (TKT-012) |

## Non-goals

- No importa el catálogo de conceptos: es HDU-001.
- No siembra obras. Darlas de alta es funcionalidad de HDU-001 y debe probarse por su propio camino.
- No siembra empleados ni proveedores: son HDU-007 y HDU-004.
- No siembra `rol_oficio`: su tabla nace en TKT-042.
- No siembra los datos simulados de mano de obra y avance: son un archivo de TKT-060, no filas de la base ([ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md)).
- No resuelve cómo nace el primer usuario en producción (`PA-T13`): los usuarios sembrados existen solo en una base local.
- No define el parser de insumos del importador ni compara contra el Excel real. Solo fija, con una regla `(asumido)`, la clave con la que el importador buscará.
- No crea un ajuste de entorno. La guarda es la del script de humo: el host de la base.

## Reglas de negocio implicadas

Ninguna regla `RN-xx` se implementa en este ticket: no hay lógica de negocio, solo datos. Las reglas siguientes dan sentido a lo que se siembra.

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-02` | Toda requisición, orden de compra y entrada está imputada a una obra y a un tipo de partida: sin el catálogo de tipos no se puede imputar | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RN-03` | El control del límite es por obra y tipo de partida; los cuatro tipos son las cuatro bolsas | PRD §8 |
| `PA-01` | Las cuatro bolsas por obra: `MUROS`, `PLAFONES Y CAJILLOS`, `ENCHAPES` y `GENERALES` | PRD §10 |
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen: la contraseña de los usuarios sembrados sale del entorno | PRD §9 |
| [ADR-008](../../../docs/adr/20260918-despliegue-single-tenant.md) | Una empresa única; `obra.empresa_id` obligatoria | `docs/adr/` |
| [ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md) | Lo simulado no es filas de la base y no arranca en producción | `docs/adr/` |
| Regla 9 de `CLAUDE.md` | La sesión es de estado en el servidor; los hashes se derivan siempre con `ContrasenasArgon2` | [`CLAUDE.md`](../../../CLAUDE.md) |

Términos del [glosario](../../../docs/glosario.md) que importan: *tipo de partida* (una de las cuatro bolsas de control, distinta de *partida*), *insumo* (recurso global cuyo precio vive en `precio_insumo` con vigencia, no en el insumo) y *explosión de insumos* (la agregación de los insumos de la obra, que no es el catálogo). No confundir *rol* de acceso con *rol de oficio*.

## Invariantes que deben sobrevivir al cambio

El ticket agrega datos y una migración, pero modifica la plantilla de pruebas que ya usan los tests de TKT-011 y toca documentos que ya funcionan. Estas garantías deben sobrevivir:

| Invariante o garantía | Qué protege | Criterio de regresión |
|---|---|---|
| Pruebas de TKT-011 (estructura, línea base y permisos) | Que la plantilla ya sembrada con `MUROS` y una empresa no choque con `uq_tipo_partida_clave` ni con los tests que esperan tablas vacías | `CA-R1` |
| Ciclo de migraciones: cabeza única, subida, bajada y subida de nuevo | Reversibilidad de la migración nueva (`conv-sql-postgres`) | `CA-R2` |
| Invariante 21 y privilegios por rol | El rol de lectura no ve `usuario.password_hash`; ningún `GRANT` nuevo | `CA-R3` |
| Invariantes 27 y 8, `uq_insumo_codigo`, `uq_tipo_partida_clave`, `ck_usuario_email_minusculas` | Los datos sembrados caben en las restricciones sin relajar ninguna | `CA-R4` |
| Ruff, mypy, `lint-imports`, `verificar_float` | Base de calidad. La herramienta no usa `float` | `CA-R5` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` | Enlaces, anclas, identificadores y conteos de la documentación | `CA-R6` |
| `frontend/e2e/sembrar_usuario_humo.py` | El humo de Playwright sigue sembrando su propio usuario `COMPRAS`, sin chocar con los usuarios sembrados | `CA-R7` |

## Criterios de aceptación

Gherkin, en español. Cada regla de «no sembrar» y de «negarse» tiene su escenario de rechazo, y el rechazo verifica el dato: qué quedó en las tablas, no solo que la herramienta terminó con error. La herramienta no responde con el contrato de error de la API (no es HTTP): el rechazo es una salida con código distinto de cero que nombra la causa, y la base rechaza con la restricción nombrada.

### CA-1 `[M]` · La migración siembra la empresa y los cuatro tipos de partida · `PA-01` · `M1`

```gherkin
Escenario: Una base recién migrada ya tiene la empresa y los cuatro tipos
  Dado una base vacía
  Cuando se aplica `alembic upgrade head` con el rol de migración
  Entonces `empresa` tiene exactamente una fila: «Constructora Celsius», activa, con RFC genérico (asumido)
  Y `tipo_partida` tiene exactamente cuatro filas, con claves MUROS, PLAFONES_Y_CAJILLOS, ENCHAPES y GENERALES
  Y los nombres son «MUROS», «PLAFONES Y CAJILLOS», «ENCHAPES» y «GENERALES»
  Y los identificadores son los mismos que en cualquier otra base migrada

Escenario: Una obra puede referenciar la empresa sembrada sin crearla
  Dado una base recién migrada y un usuario cualquiera
  Cuando se inserta una obra con el `empresa_id` de la única fila de `empresa`
  Entonces la inserción no falla por clave foránea
```

### CA-2 `[M]` · Rechazo · La migración no sobrescribe ni duplica · `M5`

```gherkin
Escenario: Rechazo — una empresa existente con otros valores se deja intacta
  Dado una base donde ya existe la empresa sembrada con el nombre cambiado a «Otra Constructora»
  Cuando se vuelve a ejecutar la sentencia de siembra de la migración
  Entonces `empresa` sigue teniendo una sola fila
  Y su nombre sigue siendo «Otra Constructora»

Escenario: Rechazo — bajar y subir no duplica los tipos de partida
  Dado una base migrada hasta la cabeza
  Cuando se baja una revisión y se sube de nuevo
  Entonces `tipo_partida` tiene exactamente cuatro filas y `empresa` exactamente una
```

### CA-3 `[S]` · Rechazo · La bajada se niega si una obra usa lo sembrado · `S2`

```gherkin
Escenario: Rechazo — no se baja la migración con una obra apuntando a la empresa
  Dado una base migrada con una obra cuyo `empresa_id` es el de la empresa sembrada
  Cuando se intenta bajar la revisión de la semilla
  Entonces la bajada falla con una violación de clave foránea (`ON DELETE RESTRICT`)
  Y la empresa, los tipos de partida y la obra siguen presentes
```

### CA-4 `[M]` · La herramienta siembra los seis usuarios · `M2`

```gherkin
Escenario: Un usuario por cada rol de acceso
  Dado una base local migrada y la contraseña de siembra en el entorno
  Cuando se ejecuta la herramienta de siembra
  Entonces `usuario` tiene seis filas activas, con correo en minúsculas y sin bloqueo
  Y cada una tiene exactamente una fila en `usuario_rol`, con un rol distinto de los seis
  Y el hash de cada usuario es Argon2id y lo verifica `ContrasenasArgon2` con la contraseña del entorno
  Y la contraseña en claro no aparece en la salida de la herramienta ni en ninguna columna
```

### CA-5 `[M]` · La herramienta siembra los 27 insumos y sus precios · `M3` · `M4`

```gherkin
Escenario: Veintisiete insumos sintéticos con un precio general
  Dado una base local migrada
  Cuando se ejecuta la herramienta de siembra
  Entonces `insumo` tiene 27 filas con código único, tipo MATERIAL, unidad dentro del catálogo cerrado, `activo = true` y `creado_en_importacion = false`
  Y `precio_insumo` tiene 27 filas, una por insumo, con `obra_id` nulo, `vigente_desde` 2026-01-01 (asumido), `vigente_hasta` nulo y costo no negativo

Escenario: Todo código sembrado ya está normalizado
  Dado los 27 códigos sembrados
  Cuando se normaliza cada uno quitando espacios de los extremos y pasándolo a mayúsculas (asumido)
  Entonces el resultado es idéntico al código sembrado
  Y no hay dos códigos que coincidan tras normalizar
```

### CA-6 `[M]` · La herramienta es idempotente · `M5`

```gherkin
Escenario: Ejecutarla dos veces no duplica nada
  Dado la herramienta ya ejecutada una vez
  Cuando se ejecuta de nuevo
  Entonces siguen existiendo seis usuarios, seis asignaciones de rol, 27 insumos y 27 precios
  Y ninguna fila cambió de identificador

Escenario: Rechazo — un usuario existente con otra contraseña no se modifica
  Dado un usuario sembrado cuyo hash se cambió a mano
  Cuando se ejecuta la herramienta con la contraseña del entorno
  Entonces el hash de ese usuario sigue siendo el que tenía (el conflicto no sobrescribe)

Escenario: Rechazo — un insumo existente con otra unidad no se modifica
  Dado un insumo sembrado cuya unidad se cambió a KG
  Cuando se ejecuta la herramienta
  Entonces su unidad sigue siendo KG y no se añade un segundo precio general para ese insumo
```

### CA-7 `[M]` · Rechazo · La herramienta se niega sin contraseña · `RNF-07` · `M6`

```gherkin
Escenario: Rechazo — falta la contraseña de siembra
  Dado una base local migrada y el entorno sin la variable de la contraseña de siembra
  Cuando se ejecuta la herramienta
  Entonces termina con código distinto de cero y el mensaje nombra la variable que falta
  Y `usuario`, `insumo` y `precio_insumo` siguen sin filas
```

### CA-8 `[M]` · Rechazo · La herramienta se niega fuera de una base local · `RNF-07` · `M6`

```gherkin
Escenario: Rechazo — el host de la base no es local
  Dado `CIMENTA_DB_HOST` apuntando a un host que no es 127.0.0.1, localhost ni ::1
  Cuando se ejecuta la herramienta
  Entonces se niega con un mensaje que nombra el host
  Y no abre ninguna conexión a la base

Escenario: Rechazo — PGHOSTADDR o PGSERVICE redirigen la conexión
  Dado `PGHOSTADDR` definido, o `PGSERVICE` definido, con un host local en la URL
  Cuando se ejecuta la herramienta
  Entonces se niega con un mensaje que nombra la variable
  Y no abre ninguna conexión a la base
```

### CA-9 `[M]` · Rechazo · Lo sembrado no relaja ninguna restricción · `INV-27` · `INV-8` · `M4`

```gherkin
Escenario: Rechazo — la base sigue rechazando un insumo con unidad fuera del catálogo
  Dado la siembra aplicada
  Cuando se inserta un insumo con unidad «LITRO» con el rol de aplicación
  Entonces la base lo rechaza con `ck_insumo_unidad`

Escenario: Rechazo — la base sigue rechazando un código repetido, un costo negativo y un correo con mayúsculas
  Dado la siembra aplicada
  Cuando se inserta un insumo con el código de uno sembrado, un precio con costo −1.0000 y un usuario con correo «Ana@Cimenta.TEST»
  Entonces se rechazan con `uq_insumo_codigo`, `ck_precio_insumo_costo_unitario_no_negativo` y `ck_usuario_email_minusculas`
```

### CA-10 `[M]` · Rechazo · Lo que no se siembra · `M7`

```gherkin
Escenario: Rechazo — ninguna tabla fuera del alcance recibe filas
  Dado la migración aplicada y la herramienta ejecutada
  Cuando se cuentan las filas de `obra`, `nivel`, `area`, `partida`, `concepto`, `apu` y `linea_base`
  Entonces todas están en cero
  Y no existe ninguna fila de empleado, proveedor ni rol de oficio, que todavía no tienen tabla, ni dato simulado

Escenario: Rechazo — la migración no siembra usuarios ni insumos
  Dado una base recién migrada, sin ejecutar la herramienta
  Cuando se cuentan las filas de `usuario`, `usuario_rol`, `insumo` y `precio_insumo`
  Entonces todas están en cero, de modo que producción nunca recibe credenciales conocidas ni un catálogo inventado
```

### Criterios de regresión

### CA-R1 `[M]` · Las pruebas de TKT-011 siguen en verde

```gherkin
Escenario: La plantilla sembrada no rompe las pruebas de presupuesto
  Dado la migración nueva incluida en la plantilla de pruebas
  Cuando se ejecutan `test_tkt011_estructura`, `test_tkt011_linea_base`, `test_tkt011_permisos` y `test_tkt011_migracion_linea_base`
  Entonces pasan sin modificar lo que cada prueba verifica
  Y las que esperaban tablas vacías o insertaban `MUROS` y una empresa propia ya no chocan con `uq_tipo_partida_clave`
```

### CA-R2 `[M]` · El ciclo de migraciones sigue funcionando

```gherkin
Escenario: Subir, bajar y subir
  Dado la cabeza de migraciones con la revisión nueva
  Cuando se sube, se baja una revisión y se sube otra vez
  Entonces hay una sola cabeza, la bajada elimina solo lo que la subida insertó y las pruebas de ciclo de identidad siguen en verde
```

### CA-R3 `[M]` · Los privilegios por rol no cambian

```gherkin
Escenario: Ningún permiso nuevo
  Dado la siembra aplicada
  Cuando se consultan los privilegios de los tres roles sobre `usuario`, `empresa`, `tipo_partida`, `insumo` y `precio_insumo`
  Entonces son los mismos que antes y el rol de lectura sigue sin poder leer `usuario.password_hash`
```

### CA-R4 `[M]` · Las restricciones existentes siguen intactas

```gherkin
Escenario: La migración no relaja nada
  Dado la migración nueva
  Cuando se compara el catálogo de restricciones de las tablas del módulo antes y después
  Entonces no hay restricciones añadidas, quitadas ni modificadas
```

### CA-R5 `[M]` · Los linters y el verificador de `float` siguen en verde

```gherkin
Escenario: La herramienta nueva cumple las reglas de calidad
  Dado el código nuevo
  Cuando se ejecutan Ruff, mypy, `lint-imports` y `verificar_float`
  Entonces terminan sin errores, y los precios se tratan como `Decimal` o cadena, nunca como `float`
```

### CA-R6 `[M]` · La documentación sigue verificándose

```gherkin
Escenario: Los verificadores de documentación pasan
  Dado los cambios documentales de S1
  Cuando se ejecutan `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py`
  Entonces terminan en verde, sin enlaces rotos ni identificadores inexistentes
```

### CA-R7 `[M]` · El humo de Playwright sigue sembrando su usuario

```gherkin
Escenario: El script de humo convive con los usuarios sembrados
  Dado los seis usuarios sembrados con correos distintos del de humo
  Cuando se ejecuta `frontend/e2e/sembrar_usuario_humo.py`
  Entonces crea o actualiza su propio usuario `COMPRAS` sin tocar ninguno de los seis
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Sus dependencias, TKT-003, TKT-011a y TKT-011b, están fusionadas. Se despliega solo |
| **N** | Describe el qué, no impone el cómo | Sí | El mecanismo (migración y herramienta) lo decidió la persona dueña; los nombres de archivos, variables y el modo de sembrar los ids son de `/sdd-disenar` |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Parcial | Es fundación: el valor lo recibe quien desarrolla y TKT-012. Aceptado en el precedente de TKT-004 |
| **E** | Estimable sin investigar antes | Sí | Talla S. El único riesgo, la plantilla de pruebas (`CA-R1`), está identificado |
| **S** | Cabe en una sesión sin romper contexto | Sí | Una migración, una herramienta y el ajuste de la plantilla |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es una consulta a tablas reales con testcontainers |

Un solo fallo parcial, **V**, explicado por ser un ticket de fundación. Pasa.

## Definition of Done

El de «Fundación» no existe en [convenciones §6](../../../docs/convenciones.md#6-definition-of-done-por-tipo-de-trabajo); se aplica el precedente de TKT-004: el de funcionalidad, sin criterios de negocio.

- [ ] Todos los criterios `[M]` tienen su prueba, vista fallar primero, con PostgreSQL real y el esquema construido con `alembic upgrade head`
- [ ] Los rechazos comprueban el dato (filas que quedaron o no quedaron), no solo el código de salida
- [ ] Las pruebas de la herramienta se conectan como la herramienta lo hace, con el rol de migración, y las de restricciones con el rol de aplicación
- [ ] Ninguna contraseña en el repositorio, en la salida ni en los registros
- [ ] Documentación de S1 actualizada en el mismo cambio

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| A1 | RFC de la empresa: el genérico público del SAT, `XAXX010101000` `(asumido)` | Hay que cambiar la fila de `empresa` al configurar la empresa real. Al no sobrescribir, no se corrige solo | Confirmado por la persona dueña el 2026-11-01 como supuesto |
| A2 | Clave de insumo: `codigo` recortado y en mayúsculas `(asumido)` | Si TKT-014 elige otra, los insumos sembrados no coincidirían y se duplicarían. Solo afecta a una base local | Confirmado el 2026-11-01. **Dependencia para TKT-014:** debe heredar esta regla o cambiarla con un ticket de por medio |
| A3 | Vigencia de los precios sembrados desde el 2026-01-01 `(asumido)` | Un precio posterior de TKT-014 con vigencia anterior no sería el vigente | Confirmado el 2026-11-01 |
| A4 | Los correos de los seis usuarios siguen el patrón `<rol en minúsculas>@cimenta.test` y una sola contraseña para los seis, desde una variable de entorno `(asumido)` | Si se quiere una contraseña por usuario o correos reales, cambia la herramienta y `.env.example` | Confirmado por la persona dueña el 2026-11-02 |
| A5 | Los 27 insumos sintéticos: nombres y códigos inventados con forma de insumo de tablaroca, unidades del catálogo, precios plausibles | Ninguno: son sintéticos por decisión | Cerrado |
| A6 | Una fila existente con otros valores se deja intacta, también el hash de un usuario sembrado | Rotar la contraseña de un usuario sembrado exige borrarlo o un ticket aparte (Won't) | Cerrado el 2026-11-01 |
| A7 | La siembra no asienta en la bitácora: no tiene autor ([modelo de datos §2](../../../docs/03-modelo-datos.md#2-convenciones)) | La regla 8 de `CLAUDE.md` no aclara este caso | Cerrado el 2026-11-01 |
| A8 | Cómo hace la plantilla de pruebas compatibles los tests de TKT-011 con filas ya sembradas | Pruebas rotas o que dejan de verificar lo que verificaban | **Cerrado en el diseño**, sección «Convivencia con la plantilla sembrada» (`A8` de `design.md`); lo cubre `CA-R1` |
| A9 | Cómo se resuelve `empresa_id` en el alta de obra de TKT-012, que no lo recibe | Si TKT-012 no encuentra la empresa única, falla | **Sugerido a TKT-012**: ver «Tickets futuros» |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Con la migración y la herramienta separadas, los 27 insumos sintéticos habrían llegado a producción como catálogo falso | Se cambió el reparto: solo `empresa` y `tipo_partida` van en la migración. Decisión de la persona dueña, 2026-11-01. `CA-10` lo verifica |
| 2 | Alta | Los tests de TKT-011 insertan `MUROS` y una empresa propia y chocan con la plantilla sembrada; además «quien escribe el código no toca los tests» | Se elevó a regresión `[M]` (`CA-R1`) y a pregunta `A8`. El diseño debe resolverlo sin cambiar lo que cada prueba verifica |
| 3 | Media | «Idempotente» es ambiguo si la fila existe con otros valores | `M5` y `CA-2` y `CA-6` fijan: se deja intacta |
| 4 | Media | Una herramienta con contraseña conocida contra una base remota sería un acceso abierto | `CA-8` cubre host no local, `PGHOSTADDR` y `PGSERVICE`; la guarda se comprueba antes de conectar |
| 5 | Media | El humo de Playwright también siembra un usuario con otro hash | `CA-R7` |
| 6 | Baja | La bajada borraría la empresa referenciada | `S2`/`CA-3`: `ON DELETE RESTRICT` la detiene sin código nuevo |
| 7 | Baja | El criterio original de «27 insumos reales» ya no se cumple | `S1` corrige `docs/05-tickets-trabajo.md`; la persona dueña decidió el 2026-11-01 |
| 8 | Baja | Un APU de TKT-016 podría esperar los 27 insumos reales de Union Square | Anotado: TKT-016 no depende de esta semilla, que es sintética; su oráculo tampoco está en el repositorio |

Ninguna objeción reveló una regla de negocio que el PRD no tenga.

## Contexto técnico

Siempre al final, para que `/sdd-disenar` lo lea después del producto.

- **Migraciones:** `backend/migraciones/versions/`. La última es `v0007_presupuesto_linea_base_e_importacion.py`; el patrón de semilla en migración es `v0002_semilla_roles_de_negocio.py` (identificadores fijos, una sentencia por `op.execute`, bajada que borra por identificador).
- **Tablas:** `empresa` (`nombre`, `rfc`, `activa` obligatorias; `dias_semana_laboral` con valor por omisión), `tipo_partida` (`clave`, `nombre`; `uq_tipo_partida_clave`), `insumo` (`codigo`, `descripcion`, `tipo`, `unidad`, `activo`, `creado_en_importacion`; `uq_insumo_codigo`, `ck_insumo_tipo`, `ck_insumo_unidad`), `precio_insumo` (`insumo_id`, `obra_id`, `costo_unitario numeric(14,4)`, `vigente_desde`, `vigente_hasta`), `usuario` y `usuario_rol`. Todas en `v0001` y `v0006`.
- **Herramientas existentes:** `backend/herramientas/conexion.py` (`url_migracion`, `leer_variable`), `contrasenas_roles.py` (patrón: lee de `.env`, nunca imprime secretos) y `frontend/e2e/sembrar_usuario_humo.py` (guarda de host local y variables de `libpq`). La clase de hash es `cimenta.identidad.infraestructura.contrasenas.ContrasenasArgon2`; la herramienta está fuera de `cimenta/` y `import-linter` no la analiza, pero el diseño debe respetar la frontera entre módulos.
- **Pruebas:** `backend/tests/conftest.py` construye una plantilla con `alembic upgrade head` una vez por sesión y la copia por prueba; la fábrica `DatosPresupuesto` inserta `tipo_partida(clave="MUROS")`, empresa e `insumo(codigo="INS-001")`.
- **Documentación afectada:** `CLAUDE.md` (Comandos), `docs/arranque-local.md` (la línea sobre alta de usuarios), `.env.example`, `docs/05-tickets-trabajo.md` (criterios de TKT-010), `docs/api/openapi.yaml` (la descripción de `listar_tipos_partida` ya dice «sembrado por TKT-010»: no cambia).
- **Fase:** 1. No adelanta nada de la fase 2.
