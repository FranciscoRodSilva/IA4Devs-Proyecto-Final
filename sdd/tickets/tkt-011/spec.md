# Spec · TKT-011 · Esquema y migraciones del módulo presupuesto

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

HDU-001 (línea base desde el Excel) y todo lo que viene después, la requisición bloqueada contra un tope (HDU-002), las compras (HDU-004) y el semáforo (HDU-006), leen y escriben el mismo núcleo de datos: la jerarquía de la obra, el catálogo de conceptos y de insumos, el análisis de precios unitarios, la línea base congelada y el presupuesto de control. Hoy ese esquema no existe: la base solo tiene identidad, auditoría y la bitácora (migraciones `0001` a `0005`), y `backend/cimenta/presupuesto/` es un esqueleto con las cuatro capas vacías.

Este ticket crea **solo el esquema** del módulo `presupuesto`, en dos migraciones nuevas, `0006` (TKT-011a, estructura y catálogos) y `0007` (TKT-011b, línea base, importación, disparadores y permisos), según la partición aprobada en el diseño el 2026-11-01, con las garantías que deben vivir en la base y no en el código: unicidad, rangos, catálogos cerrados y, sobre todo, la inmutabilidad de la línea base congelada (invariante 14), que el motor impone con un disparador y con privilegios mínimos del rol de aplicación. No hay caso de uso, ruta ni lógica de negocio: la primera consumidora del esquema es TKT-012 (obras) y la siguiente, TKT-013 a TKT-018 (importación).

Se corrigieron en el plan, el 2026-11-01, la dependencia de TKT-059 (ya no depende de él) y quedan registradas varias decisiones de la persona dueña tomadas durante la definición, que están en `_index.md`.

## Historia de usuario

Ticket de esquema del bloque HDU-001, sin escenarios propios: los escenarios de HDU-001 que dependen de garantías de este ticket los implementan TKT-012 a TKT-018 (ver «Contexto técnico»). Lo usa quien desarrolla el proyecto, persona o agente; quien lo recibe al final es Dirección General y el Director de Proyectos, cuya línea base no puede alterarse.

**Como** persona que desarrolla los casos de uso de línea base, requisición y compras
**quiero** que la base de datos tenga el esquema del módulo `presupuesto` con sus garantías de integridad, de inmutabilidad y de permisos
**para** que ninguna regla de negocio dependa de que el código recuerde no tocar la línea base, y para que los tickets siguientes no inventen tablas ni restricciones.

## Alcance

El Must lo validó la persona dueña el 2026-11-01.

| Nivel | Ítem |
|---|---|
| **Must** | **M1** Estructura y catálogos: `empresa` (con `dias_semana_laboral`), `obra` (con `empresa_id` obligatoria y `codigo` único), `nivel`, `area`, `tipo_partida`, `partida`, `concepto` (con `obra_id` denormalizado), `insumo`, `precio_insumo`, `apu`, `apu_insumo` y `apu_cargo`, tal como los define el [modelo de datos §4.1](../../../docs/03-modelo-datos.md#41-jerarquía-y-catálogo) |
| | **M2** Línea base y control: `linea_base`, `linea_base_concepto`, `explosion_presupuesto` y `presupuesto_control`, con el índice único parcial de una sola línea base `CONGELADA` por obra (invariante 5), `UNIQUE (linea_base_id, tipo_partida_id)` en el control (invariante 6) y `UNIQUE (linea_base_id, tipo_partida_id, insumo_id)` en la explosión `(asumido)` |
| | **M3** Importación: `importacion` (con `latido`, `progreso` y `archivo_id` **sin** clave foránea), `importacion_error` (con los siete tipos) y `rendimiento_observado`, creada vacía y separada de la explosión (invariante 19) |
| | **M4** Restricciones de dominio: unidades admitidas (invariante 27), `UNIQUE (obra_id, codigo)` en `concepto` (invariante 13), `CHECK >= 0` en toda cantidad, precio, importe y rendimiento (invariante 8 ampliado) y rango de los porcentajes |
| | **M5** Inmutabilidad de la línea base (invariante 14, ampliado el 2026-11-01): las copias `linea_base_concepto` y `explosion_presupuesto` rechazan `INSERT`, `UPDATE` y `DELETE` cuando su línea base no es `BORRADOR`; y la fila `linea_base` solo avanza `BORRADOR` → `CONGELADA` → `SUPERSEDIDA`, no vuelve atrás, no se borra si no es `BORRADOR` y, una vez congelada, no cambia más que su estado hacia `SUPERSEDIDA` |
| | **M6** Permisos por rol: el rol de aplicación solo `SELECT` e `INSERT` sobre `linea_base_concepto`; `UPDATE` sobre `explosion_presupuesto` y `presupuesto_control` para que `SELECT … FOR UPDATE` funcione; el rol de lectura solo `SELECT`. Con sus pruebas, cada una con el rol que corresponde |
| | **M7** Reversibilidad probada: subir, bajar y subir; la bajada se niega si existe una línea base `CONGELADA` o `SUPERSEDIDA` |
| | **M8** Consecuencia documental: el modelo de datos, la ficha de TKT-011 y la arquitectura §9 quedan alineados con lo que crea la migración, en el mismo PR |
| **Should** | **S1** Todas las restricciones, índices y el disparador llevan nombre explícito con los prefijos de `conv-sql-postgres` (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`, `trg_`) |
| **Could** | Ninguno |
| **Won't** | Modelos ORM y repositorios (los añade el primer caso de uso que los use) · datos semilla (TKT-010) · la «zona de preparación» de la importación (TKT-013) · `UNIQUE (apu.concepto_id)` · `UNIQUE (linea_base.obra_id, version)` y el `CHECK` de que una línea base `CONGELADA` lleve `congelada_en` y `congelada_por_id` · la coherencia de `concepto.obra_id` con su jerarquía · cualquier ruta, caso de uso o regla de negocio |

## Non-goals

- **No crea modelos ORM, repositorios ni casos de uso.** Es un ticket de esquema; el primer consumidor (TKT-012) añade lo que necesite. Por eso `backend/cimenta/presupuesto/` sigue sin código en este ticket.
- **No siembra datos.** `empresa`, `tipo_partida` e `insumo` los carga TKT-010; la migración no inserta filas.
- **No define la zona de preparación** de las filas válidas de una importación: la decide TKT-013.
- **No cruza la frontera de módulos por el esquema.** Las únicas claves foráneas hacia otro módulo son las de `usuario` (`*_por_id`), porque `identidad` es ancestro de `presupuesto`. `importacion.archivo_id` es un identificador lógico, sin clave foránea (modelo de datos §2).
- **No protege por sí mismo** lo que se deja fuera a propósito (ver «Won't»): la unicidad 1:1 del APU, la versión de la línea base, la coherencia de `concepto.obra_id` y el `CHECK` de congelado quedan a cargo de los casos de uso y de los tickets futuros sugeridos en `_index.md`.
- **No implementa el cálculo de rendimiento observado** (`RN-24`, v1.1): `rendimiento_observado` queda vacía y sin escritor.
- **No toca** identidad, auditoría ni el rol de lectura más allá de heredar `SELECT` en las tablas nuevas.

## Reglas de negocio implicadas

Ninguna regla se implementa: el ticket da la base física a las que implementan otros tickets.

| Regla | Qué exige del esquema | Dónde está |
|---|---|---|
| `RN-01` | Una línea base congelada no se altera: el disparador y los privilegios lo imponen en la base | PRD §8 — `docs/01-descripcion-producto.md` |
| `RN-02` y `RN-03` | El control es por obra **y tipo de partida**: `presupuesto_control` y `explosion_presupuesto` se identifican por `(linea_base_id, tipo_partida_id)` | PRD §8 |
| `RN-24` | El rendimiento congelado vive en `explosion_presupuesto` y el observado, en otra tabla; no se sobrescriben entre sí (invariante 19) | PRD §8 |
| `RN-25` | El tratamiento del IVA se configura por obra: `obra.iva_acreditable` | PRD §8 |
| `RNF-09` | Privilegio mínimo con tres roles; cada migración revoca lo que su tabla no admite y lo prueba | PRD §9 |
| `RNF-17` | `importacion.latido`, `progreso` y el error `PROCESO_INTERRUMPIDO` hacen detectable un trabajo interrumpido | PRD §9 |
| ADR-004 | El bloqueo pesimista `SELECT … FOR UPDATE` sobre el control y la explosión exige el privilegio `UPDATE` | `docs/adr/20260918-bloqueo-pesimista-presupuesto.md` |
| ADR-008 | `obra.empresa_id` es obligatoria aunque el despliegue sea de un solo inquilino | `docs/adr/20260918-despliegue-single-tenant.md` |

## Invariantes que deben sobrevivir al cambio

Este ticket añade tablas, pero también cambia el reparto de privilegios del esquema existente (las tablas nuevas heredan los privilegios por omisión de la migración `0001` y esta migración revoca lo que corresponde). Cada invariante que podría romperse genera un criterio de regresión `[M]`.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 10 del modelo de datos | `bitacora.usuario_id` `NOT NULL` y sin `UPDATE`, `DELETE` ni `TRUNCATE` para el rol de aplicación | `CA-R1` |
| 20 del modelo de datos | `intento_acceso` solo admite `INSERT` y `SELECT` para el rol de aplicación | `CA-R2` |
| 21 del modelo de datos | El rol de solo lectura no ve `sesion` ni `usuario.password_hash` y no gana escritura en ninguna tabla nueva | `CA-R3` |
| Cadena de migraciones | `0006` cuelga de `0005`, hay una sola cabeza y las pruebas de TKT-003, TKT-007 y TKT-057 siguen en verde | `CA-R4` |
| Regla 3 de `CLAUDE.md` | Ningún módulo toca las tablas de otro; las únicas claves foráneas externas son las de `usuario` | `CA-R5` |
| Regla 1 de `CLAUDE.md` | Todo importe, precio, cantidad y rendimiento es `NUMERIC`, nunca flotante | `CA-R6` |

## Criterios de aceptación

Gherkin, en español. Como el ticket es de esquema, los rechazos los emite el motor: cada escenario de rechazo nombra el `SQLSTATE` de PostgreSQL y el nombre de la restricción (`diag.constraint_name`) y comprueba que la tabla queda intacta. Las pruebas se conectan **con el rol de aplicación** salvo donde se indica el de migración, para que ninguna quede verde por la razón equivocada. Los valores de partida del esquema que la spec no fija los define el modelo de datos.

### Estructura

### CA-1 `[M]` · Las tablas del modelo existen con su forma · `RNF-09`

```gherkin
Escenario: las migraciones crean las 19 tablas del módulo con las columnas del modelo (doce en "0006" y siete en "0007"; se verifica por mitad)
  Dado una base vacía migrada con "alembic upgrade head"
  Cuando se consulta el catálogo de PostgreSQL
  Entonces existen las tablas "empresa", "obra", "nivel", "area", "tipo_partida", "partida", "concepto", "insumo", "precio_insumo", "apu", "apu_insumo", "apu_cargo", "linea_base", "linea_base_concepto", "explosion_presupuesto", "presupuesto_control", "importacion", "importacion_error" y "rendimiento_observado"
  Y cada tabla tiene exactamente las columnas, los tipos y la nulabilidad que fija la tabla de nulabilidad del diseño, derivada del modelo de datos §4 y §11 y del borrador OpenAPI
  Y toda columna de importe, precio, cantidad, rendimiento y porcentaje es NUMERIC, nunca real ni doble precisión
  Y las fechas y horas de eventos son TIMESTAMPTZ
```

```gherkin
Escenario: una columna obligatoria no admite nulo
  Dado la tabla "obra"
  Cuando el rol de aplicación inserta una obra sin "empresa_id"
  Entonces el motor responde 23502 (not_null_violation) sobre la columna "empresa_id"
  Y la tabla no tiene filas nuevas
```

### CA-2 `[M]` · `empresa` y `obra` · `RN-25`, ADR-008

```gherkin
Escenario: los días laborales de la semana valen seis por omisión
  Dado una empresa insertada sin "dias_semana_laboral"
  Cuando se lee la fila
  Entonces "dias_semana_laboral" vale 6
  Y la columna es smallint NOT NULL

Escenario: la clave foránea a la empresa es obligatoria y se respeta
  Cuando el rol de aplicación inserta una obra con un "empresa_id" que no existe
  Entonces el motor responde 23503 (foreign_key_violation) sobre la restricción de "empresa_id"
```

### CA-3 `[M]` · Rechazo · El código de obra es único · `HDU-001 esc. 3`

```gherkin
Escenario: dos obras con el mismo código
  Dado una obra con código "AP-058-25"
  Cuando el rol de aplicación inserta otra obra con código "AP-058-25"
  Entonces el motor responde 23505 (unique_violation) sobre la restricción única de "codigo"
  Y la tabla "obra" sigue con una sola fila de ese código

Escenario: el mismo código en una obra distinta es otro código
  Dado una obra con código "AP-058-25"
  Cuando se inserta una obra con código "AP-059-25"
  Entonces la inserción se acepta
```

### Línea base y control

### CA-4 `[M]` · Rechazo · Una sola línea base congelada por obra · invariante 5, `HDU-001 esc. 19`

```gherkin
Escenario: segunda línea base congelada de la misma obra
  Dado una obra con una línea base "CONGELADA"
  Cuando el rol de aplicación inserta otra línea base "CONGELADA" para la misma obra
  Entonces el motor responde 23505 sobre el índice único parcial de líneas base congeladas
  Y la obra sigue con una sola línea base "CONGELADA"

Escenario: una congelada junto a las que no lo son
  Dado una obra con una línea base "CONGELADA", otra "SUPERSEDIDA" y otra "BORRADOR"
  Entonces el motor las acepta
  Y una línea base "CONGELADA" de otra obra también se acepta
```

### CA-5 `[M]` · Rechazo · Un control por línea base y tipo de partida · invariante 6

```gherkin
Escenario: dos controles para el mismo tipo de partida
  Dado un "presupuesto_control" de la línea base L para el tipo de partida "MUROS"
  Cuando el rol de aplicación inserta otro para L y "MUROS"
  Entonces el motor responde 23505 sobre "linea_base_id" y "tipo_partida_id"
  Y un control para L y "ENCHAPES" sí se acepta

Escenario: el tope puede ser nulo mientras no se capture
  Cuando se inserta un control sin "importe_tope", sin "capturado_por_id" y sin "capturado_en"
  Entonces el motor lo acepta
  Y "actualizado_por_id", "actualizado_en" y "motivo_ultimo_cambio" también admiten nulo
```

### CA-6 `[M]` · Rechazo · Una fila de explosión por línea base, tipo de partida e insumo · `(asumido)` · invariante 19

```gherkin
Escenario: la explosión repetida para el mismo insumo y tipo de partida
  Dado una fila de "explosion_presupuesto" de la línea base L, el tipo de partida "MUROS" y el insumo I
  Cuando el rol de aplicación inserta otra para (L, "MUROS", I)
  Entonces el motor responde 23505 sobre esa terna
  Y la terna (L, "ENCHAPES", I) sí se acepta
```

### Importación

### CA-7 `[M]` · La importación no guarda el archivo y vigila su latido · `RNF-17`

```gherkin
Escenario: la importación identifica el archivo sin clave foránea
  Dado la tabla "importacion"
  Cuando se consultan sus columnas y sus claves foráneas
  Entonces "archivo_id" existe, es uuid y no tiene clave foránea
  Y la tabla no tiene columnas de nombre ni de URL del archivo
  Y "latido" es TIMESTAMPTZ nullable y "progreso" es NUMERIC(9,6) nullable

Escenario: un identificador de archivo que no existe se acepta
  Cuando el rol de aplicación inserta una importación con un "archivo_id" que no corresponde a ninguna fila
  Entonces el motor la acepta
```

### CA-8 `[M]` · Rechazo · Los estados y los tipos de error son cerrados · `RNF-17`, `HDU-001 esc. 27`

```gherkin
Esquema del escenario: valores fuera del conjunto cerrado
  Cuando el rol de aplicación inserta <fila>
  Entonces el motor responde <sqlstate> y no queda ninguna fila nueva

  Ejemplos:
    | fila                                                         | sqlstate |
    | una importación con estado "TERMINADA"                        | el del mecanismo que elija el diseño |
    | un error de importación con tipo "OTRO"                       | el mismo |
    | una línea base con estado "ABIERTA"                           | el mismo |
    | una obra con estado "BORRADA"                                 | el mismo |
    | un insumo con tipo "EQUIPO"                                   | el mismo |
    | un cargo de APU con tipo "PROPINA"                            | el mismo |

(El diseño aprobado usa `CHECK` con nombre, así que el `SQLSTATE` es `23514` en las seis filas y la prueba afirma ese y el nombre de la restricción. TKT-011a prueba las filas de sus tablas —obra, insumo y cargo de APU— y TKT-011b prueba las seis juntas.)

Escenario: los valores admitidos se aceptan
  Entonces la importación admite "RECIBIDO", "ANALIZANDO", "VALIDADO", "CON_ERRORES", "CONFIRMADO" y "DESCARTADO"
  Y el error de importación admite "REF_ROTA", "UNIDAD_DESCONOCIDA", "SIN_APU", "RENDIMIENTO_AUSENTE", "DUPLICADO", "SIN_CONCEPTOS" y "PROCESO_INTERRUMPIDO"
  Y la línea base admite "BORRADOR", "CONGELADA" y "SUPERSEDIDA"
  Y la obra admite "PLANEACION", "ACTIVA", "SUSPENDIDA" y "CERRADA"
```

### CA-9 `[M]` · El error de hoja sin conceptos no tiene fila ni columna · `HDU-001 esc. 27`

```gherkin
Escenario: error SIN_CONCEPTOS
  Cuando el rol de aplicación inserta un error de tipo "SIN_CONCEPTOS" con "fila" y "columna" nulas
  Entonces el motor lo acepta
  Y "mensaje" sigue siendo obligatorio: un error sin "mensaje" responde 23502
```

### CA-10 `[M]` · Rendimiento observado vacío y separado · invariante 19, `RN-24`

```gherkin
Escenario: la tabla existe, no tiene escritor y no comparte filas con la explosión
  Dado una base recién migrada
  Entonces "rendimiento_observado" existe y no tiene ninguna fila
  Y no tiene clave foránea hacia "explosion_presupuesto" ni a la inversa
  Y "explosion_presupuesto.rendimiento_congelado" no es una vista ni una columna generada de "rendimiento_observado"

Escenario: ninguna escritura sobre una tabla toca la otra
  Cuando se inserta una fila en "rendimiento_observado"
  Entonces "explosion_presupuesto" no cambia
```

### Restricciones de dominio

### CA-11 `[M]` · Rechazo · Unidades fuera del catálogo · invariante 27, `HDU-001 esc. 8`

```gherkin
Esquema del escenario: unidad de concepto o de insumo
  Cuando el rol de aplicación inserta <fila>
  Entonces <resultado>

  Ejemplos:
    | fila                                  | resultado                               |
    | un concepto con unidad "M2"            | el motor lo acepta                      |
    | un concepto con unidad "M3"            | responde 23514 (check_violation) sobre la restricción de unidad |
    | un insumo con unidad "JORNAL"          | el motor lo acepta                      |
    | un insumo con unidad "LITRO"           | responde 23514 sobre la restricción de unidad |
```

Las ocho unidades admitidas son las de la entidad «Unidad de medida» del [glosario](../../../docs/glosario.md): `M2`, `ML`, `PZA`, `KG`, `CAJA`, `SACO`, `ROLLO` y `JORNAL`. Se acepta cada una de las ocho en las dos tablas `(asumido)` (ver `PA-T7`).

### CA-12 `[M]` · Rechazo · Un concepto es único por obra · invariante 13, `HDU-001 esc. 9`

```gherkin
Escenario: dos conceptos con el mismo código en la misma obra
  Dado un concepto "620001" en la obra A
  Cuando el rol de aplicación inserta otro concepto "620001" en la obra A
  Entonces el motor responde 23505 sobre "(obra_id, codigo)"

Escenario: el mismo código en otra obra
  Cuando se inserta un concepto "620001" en la obra B
  Entonces el motor lo acepta
```

### CA-13 `[M]` · Rechazo · Nada negativo · invariante 8

```gherkin
Esquema del escenario: cantidades, precios, importes y rendimientos
  Cuando el rol de aplicación inserta una fila con <columna> igual a -0.0001
  Entonces el motor responde 23514 sobre la restricción de no negatividad de esa columna
  Y con <columna> igual a 0 el motor la acepta

  Ejemplos:
    | columna |
    | concepto.cantidad |
    | concepto.precio_unitario |
    | concepto.importe |
    | precio_insumo.costo_unitario |
    | apu_insumo.costo_unitario |
    | apu_insumo.rendimiento |
    | linea_base_concepto.cantidad |
    | linea_base_concepto.precio_unitario |
    | linea_base_concepto.importe |
    | explosion_presupuesto.cantidad_presupuestada |
    | explosion_presupuesto.rendimiento_congelado |
    | explosion_presupuesto.costo_unitario |
    | explosion_presupuesto.importe_venta |
    | presupuesto_control.importe_tope |
    | rendimiento_observado.rendimiento |
```

Cada columna de importe, precio, cantidad o rendimiento de las tablas de este ticket tiene su restricción, aunque la tabla de ejemplos cite las principales: el diseño enumera la lista completa y `CA-1` la comprueba contra el catálogo.

### CA-14 `[M]` · Rechazo · Rango de los porcentajes · `PA-02`

```gherkin
Esquema del escenario: porcentajes de 0 a 1 (0.050000 es 5 %)
  Cuando el rol de aplicación inserta <fila> con valor <valor>
  Entonces <resultado>

  Ejemplos:
    | fila                                  | valor    | resultado                  |
    | obra.retencion_destajo_pct             | 0.150000 | el motor la acepta          |
    | obra.retencion_destajo_pct             | 1.500000 | responde 23514 (rango)      |
    | obra.fondo_garantia_pct                | -0.01    | responde 23514              |
    | importacion.progreso                   | 1.000000 | el motor la acepta          |
    | importacion.progreso                   | 1.000001 | responde 23514              |
    | obra.umbral_alerta_pct                 | nulo     | el motor la acepta          |
    | obra.umbral_alerta_pct                 | -0.5     | responde 23514              |
```

`obra.umbral_alerta_pct` y `apu_cargo.porcentaje` solo exigen `>= 0`: el primero es una desviación relativa que puede pasar de 1 y el segundo, un cargo porcentual `(asumido)` (ver `PA-T5`).

### Disparador del invariante 14

### CA-15 `[M]` · Rechazo · Las copias de una línea base congelada no se alteran ni se amplían · invariante 14, `RN-01`, `HDU-001 esc. 18`

```gherkin
Esquema del escenario: INSERT, UPDATE y DELETE sobre las copias de una línea base congelada
  Dado una línea base "CONGELADA" con filas en "linea_base_concepto" y en "explosion_presupuesto"
  Cuando, conectado con el rol de migración, se ejecuta <sentencia>
  Entonces el disparador la rechaza con un código y un mensaje estables que citan "RN-01"
  Y la fila queda intacta

  Ejemplos:
    | sentencia                                                     |
    | INSERT en linea_base_concepto                                  |
    | INSERT en explosion_presupuesto                                |
    | UPDATE sobre linea_base_concepto                               |
    | DELETE sobre linea_base_concepto                               |
    | UPDATE sobre explosion_presupuesto                             |
    | DELETE sobre explosion_presupuesto                             |

Escenario: lo mismo sobre una línea base SUPERSEDIDA
  Cuando se ejecuta cualquiera de las seis sentencias sobre sus copias
  Entonces el disparador también las rechaza

Escenario: una línea base en BORRADOR se puede preparar
  Dado una línea base "BORRADOR"
  Cuando se insertan, modifican o borran copias suyas
  Entonces el disparador no interviene

Escenario: el congelado ocurre en una sola transacción
  Dado una línea base "BORRADOR" con sus copias insertadas
  Cuando, en la misma transacción, pasa a "CONGELADA"
  Entonces la transición se acepta y, desde ese momento, las copias quedan protegidas
```

El `SQLSTATE` y el texto exacto del rechazo los fija el diseño y quedan documentados, porque TKT-017 los traduce al rechazo `409` `REGLA_NEGOCIO` con `RN-01` `(asumido)`. La prueba usa el rol de migración a propósito: con el de aplicación el privilegio fallaría antes y la prueba quedaría verde sin haber tocado el disparador.

### CA-16 `[M]` · Rechazo · La fila `linea_base` solo avanza · invariante 14, `RN-01`

```gherkin
Esquema del escenario: transiciones de estado de la línea base
  Dado una línea base en estado <desde>
  Cuando, conectado con el rol de migración, se ejecuta un UPDATE que la pasa a <hasta>
  Entonces <resultado>

  Ejemplos:
    | desde       | hasta       | resultado                                                    |
    | BORRADOR    | CONGELADA   | el disparador la acepta                                      |
    | CONGELADA   | SUPERSEDIDA | el disparador la acepta                                      |
    | CONGELADA   | BORRADOR    | el disparador la rechaza con el código estable que cita RN-01 |
    | SUPERSEDIDA | CONGELADA   | el disparador la rechaza                                     |
    | SUPERSEDIDA | BORRADOR    | el disparador la rechaza                                     |
    | BORRADOR    | SUPERSEDIDA | el disparador la rechaza (hay que congelar antes)            |

Escenario: una línea base congelada no cambia más que su estado
  Dado una línea base "CONGELADA"
  Cuando se intenta un UPDATE de "obra_id", "version", "motivo", "importe_venta", "congelada_en" o "congelada_por_id"
  Entonces el disparador lo rechaza y la fila queda intacta

Escenario: no se borra una línea base que no es borrador
  Cuando se ejecuta un DELETE sobre una línea base "CONGELADA" o "SUPERSEDIDA"
  Entonces el disparador lo rechaza
  Y un DELETE sobre una línea base "BORRADOR" sin copias se acepta
```

`BORRADOR` no está protegido: es el estado en el que TKT-017 prepara y reimporta (`HDU-001 esc. 13`). El `CHECK` de que una `CONGELADA` lleve `congelada_en` y `congelada_por_id` sigue fuera de este ticket (`PA-T3`).

### Permisos por rol

### CA-17 `[M]` · Rechazo · Privilegio mínimo del rol de aplicación · `RNF-09`, invariante 14

```gherkin
Escenario: la copia de conceptos solo se anexa
  Cuando se consultan los privilegios del rol de aplicación sobre "linea_base_concepto"
  Entonces tiene exactamente SELECT e INSERT
  Y un UPDATE o un DELETE real con ese rol responde 42501 (insufficient_privilege)

Escenario: el bloqueo pesimista funciona con el rol de aplicación
  Cuando el rol de aplicación ejecuta "SELECT … FOR UPDATE" sobre "explosion_presupuesto" y sobre "presupuesto_control"
  Entonces ambas sentencias funcionan
  Y el rol tiene el privilegio UPDATE sobre las dos tablas

Escenario: la aplicación puede congelar pero no vaciar
  Cuando se consultan los privilegios del rol de aplicación sobre "linea_base"
  Entonces tiene UPDATE (lo necesita TKT-017 para congelar, y el disparador de CA-16 lo acota)
  Y no tiene TRUNCATE sobre ninguna tabla del módulo (en TKT-011a, sobre las doce tablas; sobre linea_base, en TKT-011b)

Escenario: el rol de lectura no escribe
  Cuando se consultan los privilegios del rol de lectura sobre las tablas del módulo
  Entonces tiene solo SELECT
  Y un INSERT real con ese rol responde 42501
```

### Reversibilidad

### CA-18 `[M]` · Las migraciones se suben, se bajan y se vuelven a subir · `conv-sql-postgres`

```gherkin
Escenario: ciclo completo de cada migración
  Dado una base migrada a "0005"
  Cuando TKT-011a ejecuta "upgrade 0006", "downgrade 0005" y "upgrade 0006", y TKT-011b ejecuta "upgrade 0007", "downgrade 0006" y "upgrade 0007"
  Entonces el catálogo (tablas, columnas, restricciones, índices, disparadores y privilegios) es idéntico en la primera y la segunda subida
  Y tras bajar a "0005" no queda ninguna de las tablas del módulo
```

### CA-19 `[M]` · Rechazo · No se baja con una línea base congelada · invariante 14

```gherkin
Escenario: bajada con datos de negocio
  Dado una línea base "CONGELADA" o "SUPERSEDIDA" en la base
  Cuando se ejecuta "downgrade 0006" (la guarda vive en la bajada de "0007")
  Entonces la bajada se detiene con un error que nombra la línea base "CONGELADA" o "SUPERSEDIDA"
  Y las tablas y las filas siguen intactas

Escenario: bajada solo con borradores
  Dado una base en la que solo hay borradores: ninguna línea base "CONGELADA" ni "SUPERSEDIDA"
  Cuando se ejecuta "downgrade 0006"
  Entonces la bajada elimina las siete tablas de "0007" y sus dos funciones
```

La guarda se niega también con una `SUPERSEDIDA`: es un presupuesto firmado que ya estuvo vigente, y bajar la migración la borraría igual que a la vigente. Decisión de la persona dueña del 2026-11-01 (PA-T6 y PA-T8).

### Nombres y documentación

### CA-20 `[S]` · Las restricciones tienen nombre · `conv-sql-postgres`

```gherkin
Escenario: ninguna restricción ni índice sin nombre explícito
  Cuando se consultan las restricciones y los índices de las tablas del módulo
  Entonces cada nombre empieza por "pk_", "fk_", "uq_", "ck_", "ix_" o "trg_" según su tipo
```

### CA-21 `[M]` · La documentación dice lo que crea la migración · `M8`

```gherkin
Escenario: el modelo de datos, la ficha del ticket y la arquitectura coinciden
  Cuando se leen "docs/03-modelo-datos.md", la ficha de TKT-011 en "docs/05-tickets-trabajo.md" y "docs/02-arquitectura.md" §9
  Entonces las tres nombran las mismas tablas, la columna "empresa.dias_semana_laboral" y las restricciones de este ticket
  Y el diagrama de estados de la importación de la arquitectura incluye "DESCARTADO"
  Y "python tools/verificar_docs.py" no reporta ningún problema
```

### Regresión

### CA-R1 `[M]` · Invariante 10 · La bitácora sigue siendo permanente

```gherkin
Escenario: la migración nueva no toca la bitácora
  Cuando se consultan los privilegios del rol de aplicación sobre "bitacora"
  Entonces siguen siendo exactamente INSERT y SELECT
  Y "bitacora.usuario_id" sigue siendo NOT NULL
```

### CA-R2 `[M]` · Invariante 20 · `intento_acceso` sigue solo anexándose

```gherkin
Escenario: privilegios de intento_acceso
  Cuando se consultan los privilegios del rol de aplicación sobre "intento_acceso"
  Entonces son exactamente SELECT e INSERT, sin UPDATE ni DELETE
```

### CA-R3 `[M]` · Invariante 21 · Lo que ve el rol de lectura

```gherkin
Escenario: el rol de lectura no gana acceso a secretos
  Entonces sigue sin ver "sesion" ni "usuario.password_hash"
  Y no tiene ningún privilegio de escritura en ninguna tabla nueva
```

### CA-R4 `[M]` · La cadena de migraciones

```gherkin
Escenario: una sola cabeza
  Entonces "alembic heads" devuelve una sola revisión, "0006" cuelga de "0005" y "0007" cuelga de "0006"
  Y las pruebas de migración de TKT-003 y TKT-007 pasan sin cambios
  Y las de TKT-057 pasan con el único ajuste de que TC-12 y TC-13 suben a "0005" explícito en lugar de a la cabeza (aprobado en el gate del diseño, P3)
```

### CA-R5 `[M]` · Regla 3 · Fronteras entre módulos

```gherkin
Escenario: ninguna clave foránea cruza un módulo salvo hacia usuario
  Cuando se listan las claves foráneas de las tablas del módulo
  Entonces las que apuntan fuera de "presupuesto" apuntan solo a "usuario"
  Y "uv run lint-imports" mantiene sus 15 contratos
```

### CA-R6 `[M]` · Regla 1 · Dinero nunca flotante

```gherkin
Escenario: ningún tipo flotante en el esquema nuevo
  Cuando se consultan los tipos de las columnas de las tablas del módulo
  Entonces ninguna es real ni double precision
  Y "uv run python -m herramientas.verificar_float" no reporta hallazgos
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-003 (archivado), tras el corte de TKT-059. Bloquea a TKT-010, TKT-012 a TKT-018 y a todo ticket que lea o escriba presupuesto |
| **N** | Describe el qué, no impone el cómo | Sí, con reserva | Los criterios hablan de tablas, restricciones, códigos del motor y privilegios, que en un ticket de esquema son el qué. El mecanismo (disparador, función, nombres) lo elige el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con matiz | Dirección General y el Director de Proyectos obtienen una línea base que ninguna ruta de código puede alterar; el valor visible llega con TKT-017. Como en los tickets de fundación, lo que entrega hoy es capacidad de entregar valor |
| **E** | Estimable sin investigar antes | Sí | El DDL está en el modelo de datos y los patrones de prueba (`test_tkt057_migracion.py`) existen. La incertidumbre restante (mecanismo del disparador, nulabilidad) la resuelve el diseño |
| **S** | Cabe en una sesión sin romper contexto | **Reserva** | Diecinueve tablas, dos disparadores (copias y fila de la línea base), privilegios y tres tipos de pruebas por rol: talla M en el ticket, pero con probabilidad de superar las 400 líneas del tope y de pasar de 1,500 con las pruebas. El diseño debe proponer partir en dos migraciones y dos entregas (estructura y catálogos; línea base, importación, disparadores y permisos) |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada uno es una consulta al catálogo o un `INSERT` real contra PostgreSQL con testcontainers |

Una reserva de talla y una de granularidad, ningún fallo: pasa.

## Definition of Done

La de un ticket de funcionalidad (`sdd/metodologia.md` §8), corregida el 2026-11-01 tras el gate del diseño; el ticket se reparte en TKT-011a (`0006`) y TKT-011b (`0007`), con un PR cada uno, y cada uno cumple los criterios de su mitad.

- [ ] Los 20 criterios `[M]` (`CA-1` a `CA-19` y `CA-21`) y los 6 de regresión pasan; `CA-20` (`[S]`) pasa o se recorta vía `/sdd-escalar`
- [ ] Cada escenario tiene su test con el identificador en el nombre (`test_tkt011_caNN_...`)
- [ ] Cada prueba de rechazo comprueba el `SQLSTATE`, el nombre de la restricción y que la tabla queda intacta
- [ ] Las pruebas de permisos usan el rol que dice cada criterio (aplicación, migración o lectura), nunca el propietario
- [ ] `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`, `lint-imports` y `verificar_float` en verde
- [ ] `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` sin problemas
- [ ] Cada PR señala a quien aprueba: añade las migraciones `0006` (a) y `0007` (b) y reparte privilegios sobre tablas nuevas

## Preguntas abiertas y supuestos

Todo lo marcado `(asumido)` en los criterios se repite aquí.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | `rendimiento_observado` se crea vacía y sin escritor, aunque el PRD §7 pone su cálculo (`F1.8`, `RN-24`) en la v1.1. Decisión de la persona dueña el 2026-11-01 para declarar desde ya el invariante 19 y evitar una migración sobre una tabla con datos | Si debía esperar a la v1.1, hay una tabla sin dueño en la fase 1; basta con una migración que la elimine | Confirmado |
| PA-T2 | `empresa.dias_semana_laboral` (`smallint NOT NULL DEFAULT 6`, `PA-22`, nómina de la fase 2) se crea aquí, porque el módulo `personal` no puede alterar una tabla de `presupuesto` sin cruzar la frontera. TKT-049 solo la consume | Si TKT-049 esperaba crearla, habrá que quitarle el criterio | Confirmado |
| PA-T3 | Quedan **fuera** `UNIQUE (apu.concepto_id)`, `UNIQUE (linea_base.obra_id, version)`, el `CHECK` de congelado de `linea_base` y la coherencia de `concepto.obra_id` con su jerarquía, aunque el modelo de datos los describe. Decisión de la persona dueña el 2026-11-01 | La base no protege esas cuatro invariantes: un caso de uso defectuoso podría crear un APU duplicado, repetir una versión de línea base, dejar una `CONGELADA` sin autor o desalinear `obra_id` | Confirmado; ver los tickets futuros sugeridos en `_index.md` |
| PA-T4 | Solo migración y pruebas de esquema: sin modelos ORM ni repositorios. Decisión de la persona dueña el 2026-11-01 | TKT-012 tendrá que crear los modelos de `obra` y `empresa` además de su caso de uso | Confirmado |
| PA-T5 | El invariante 8 se amplía a toda cantidad, precio, importe y rendimiento de las tablas del ticket (decisión del 2026-11-01). El rango de los **porcentajes** que propone la spec es `0 <= p <= 1` en `retencion_destajo_pct`, `fondo_garantia_pct` y `progreso`, y solo `>= 0` en `umbral_alerta_pct` y `apu_cargo.porcentaje` | Un tope de 1 en un porcentaje que puede pasar de 1 (por ejemplo una desviación relativa) rechazaría datos válidos | `(asumido)`: la persona dueña confirma los límites en el gate del diseño |
| PA-T6 | El disparador del invariante 14 interviene cuando la línea base de la fila **no es** `BORRADOR` (`CONGELADA` o `SUPERSEDIDA`) y rechaza con un código y un mensaje estables que citan `RN-01`; el código exacto lo fija el diseño y TKT-017 lo traduce a `409` `REGLA_NEGOCIO` | Si se limitara a `CONGELADA`, una versión superada podría alterarse | `(asumido)` — confirmado como valor por omisión el 2026-11-01 |
| PA-T7 | `concepto.unidad` e `insumo.unidad` admiten las **ocho** unidades del catálogo (invariante 27 y el borrador `Unidad`). El modelo de datos comenta `M2\|ML\|PZA` para el concepto y `PZA\|CAJA\|SACO\|ROLLO\|KG\|JORNAL` para el insumo, pero son ejemplos del uso habitual, no un recorte | Si el concepto solo admitiera `M2`, `ML` y `PZA`, el `CHECK` debería ser distinto en cada tabla | `(asumido)` |
| PA-T8 | Las claves foráneas no se borran en cascada (`RESTRICT`); la bajada de la migración se niega si existe una línea base `CONGELADA` o `SUPERSEDIDA`; los nombres usan los prefijos de `conv-sql-postgres` | Un borrado en cascada sobre un borrador descartado sería más cómodo para TKT-017 pero abriría un camino a borrar copias | `(asumido)` — confirmado como valor por omisión el 2026-11-01 |
| PA-T9 | `UNIQUE (linea_base_id, tipo_partida_id, insumo_id)` en `explosion_presupuesto`. El ticket y el modelo (§15) lo llaman índice sin decir si es único | Si el cálculo de TKT-016 pudiera repetir un insumo dentro del tipo de partida, la unicidad lo rechazaría | `(asumido)` — confirmado como valor por omisión el 2026-11-01 |
| PA-T10 | **Nulabilidad.** Toda columna es `NOT NULL` salvo las que el modelo o el borrador OpenAPI marcan opcionales o condicionales: `umbral_alerta_pct`; `precio_insumo.obra_id` y `vigente_hasta`; `linea_base.congelada_en` y `congelada_por_id`; en `presupuesto_control`, `importe_tope`, `capturado_*` y `actualizado_*`; en `importacion`, `progreso`, `latido`, `filas_*` y `resumen`; en `importacion_error`, `hoja`, `fila`, `columna` y `valor_original`. El diseño completa la tabla | Una columna `NOT NULL` de más rechaza datos válidos; una `NULL` de más deja pasar datos incompletos | `(asumido)`: la persona dueña aprueba la tabla de nulabilidad en el gate del diseño |
| PA-T11 | Columnas de auditoría solo donde el modelo o el borrador las usan: `obra` (creación y actualización con autor), `linea_base` (autor de creación y de congelado), `presupuesto_control` (`actualizado_*` y motivo), `importacion` (`importado_por`, `creado_en`). Catálogos y copias congeladas, sin ellas. Decisión de la persona dueña el 2026-11-01 | Un caso de uso que necesite auditar otra tabla tendrá que migrarla | Confirmado |
| PA-T12 | La «zona de preparación» de las filas válidas de una importación (HDU-001 esc. 6) no es una tabla de este ticket; la define TKT-013 | Si TKT-013 la quisiera como tabla, será una migración propia | `(asumido)` — confirmado como valor por omisión el 2026-11-01 |
| PA-T13 | La arquitectura §9 no incluye `DESCARTADO` en su diagrama de estados de la importación, pero el modelo y el borrador sí. Se corrige la arquitectura (`M8`) | Si `DESCARTADO` no existiera, el enum del modelo y del borrador sobrarían | Corregida en `M8` |
| PA-T14 | La fila `linea_base` solo avanza `BORRADOR` → `CONGELADA` → `SUPERSEDIDA`, y desde `CONGELADA` solo cambia su estado hacia `SUPERSEDIDA`; todas las demás columnas quedan fijas desde que se congela. Decisión de la persona dueña el 2026-11-01 de cerrar el hueco de la fila (`M5` ampliado); la lista exacta de columnas inmutables es `(asumido)` | Si TKT-017 necesitara escribir `importe_venta` o `congelada_*` después del cambio de estado, tendría que hacerlo en la misma sentencia que congela, o el disparador lo rechazaría | `(asumido)` |
| PA-T15 | `TRUNCATE` no dispara disparadores de fila: el rol de aplicación no tiene ese privilegio (los privilegios por omisión de `0001` son `SELECT`, `INSERT`, `UPDATE` y `DELETE`) y solo el rol de migración, que es superusuario en la suite y en el despliegue, podría vaciar las copias | Un uso indebido del rol de migración vaciaría una copia congelada sin que ningún disparador lo vea; lo cubre la disciplina de acceso al rol de migración, no el esquema | `(asumido)`; se comprueba que la aplicación no tiene `TRUNCATE` (`CA-17`) |
| PA-T16 | Dependencias externas de pago, cuenta o clave: **ninguna**. Solo PostgreSQL local y testcontainers con Docker | No hay presupuesto que confirmar | Resuelto |
| PA-T17 | ¿Con qué valor nace `linea_base.importe_venta` en un `BORRADOR`, si la columna es `NOT NULL`? Lo decide TKT-017, que es quien crea el borrador | Si el caso de uso inventa un valor, un borrador con importe cero es indistinguible de un presupuesto de importe cero | **Resuelta el 2026-11-05 en TKT-017** (`PA-T17.2`): el precio unitario del concepto de partida es el del pie del análisis; el importe es cantidad × ese precio, cuantizado, e `importe_venta` es la suma de los importes |

## Pasada adversarial

Resultado de `abogado-del-diablo`, modo A (retar el qué), sobre esta spec. Sin evidencia del historial de evolución específica para este dominio más allá de las filas de `sdd/_evolucion.md` sobre ausencia de mutación y suite completa entre filas (TKT-057).

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El disparador solo cubría las copias: la fila `linea_base` seguía desprotegida. Quien tiene `UPDATE` sobre ella (el rol de aplicación lo necesita para congelar) podía poner `estado = 'BORRADOR'` en una línea base congelada y, con la condición «no es `BORRADOR`», volver a poder editar las copias. El modelo dice que «nunca vuelve a `BORRADOR`» (§14) y nada lo impone | Decisión de la persona dueña: cerrar el hueco. `M5` ampliado, nuevo `CA-16` (transiciones, columnas fijas, no se borra) y `PA-T14` |
| 2 | Alta | El invariante 14 habla de `UPDATE` y `DELETE`, pero el rol de aplicación conserva `INSERT` sobre `linea_base_concepto`: se puede añadir un concepto a una línea base ya congelada y cambiar el presupuesto firmado | `CA-15` rechaza también `INSERT` en las copias (seis sentencias) y exige que el congelado ocurra en una sola transacción |
| 3 | Media | `CA-8` aceptaba «22P02 o 23514, el que defina el diseño»: una prueba que acepta dos códigos no distingue un `ENUM` de un `CHECK` | Un único `SQLSTATE` por mecanismo, el mismo para las seis filas |
| 4 | Media | `TRUNCATE` no dispara disparadores de fila: el rol de migración (superusuario) vaciaría una copia congelada sin que nada lo vea | `PA-T15` registra el límite y `CA-17` comprueba que la aplicación no tiene `TRUNCATE` en ninguna tabla del módulo |
| 5 | Media | Un tope de 1 en todo porcentaje rechazaría datos válidos (`umbral_alerta_pct` es una desviación relativa que puede pasar de 1) y las cuatro restricciones que quedan como «Won't» (APU 1:1, versión de línea base, `CHECK` de congelado y coherencia de `concepto.obra_id`) dejan sin protección de base esas invariantes | El tope de 1 solo en `retencion_destajo_pct`, `fondo_garantia_pct` y `progreso` (`PA-T5`); los cuatro Won't son decisión de la persona dueña (`PA-T3`) y salen como tickets futuros sugeridos |

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

**Estado de partida (verificado el 2026-11-01).**

- Migraciones existentes en `backend/migraciones/versions/`: `v0001` (roles `cimenta_aplicacion` y `cimenta_lectura`, `lock_timeout`, `ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion … GRANT SELECT, INSERT, UPDATE, DELETE` a la aplicación y `SELECT` a la lectura, tablas de identidad), `v0002` (semilla de los seis roles de negocio), `v0003` (`bitacora`, con su `REVOKE` y una bajada que se niega con asientos), `v0004` (`CHECK` del correo) y `v0005` (columna `credenciales_verificadas` e índices parciales). La siguiente es `0006`.
- Arnés de pruebas en `backend/tests/conftest.py`: `migrar(base, destino, sentido)`, `base_de_prueba`, `base_vacia`, `conectar("aplicacion"|"migracion"|"lectura", base)` con una guarda que rechaza al propietario. `test_tkt057_migracion.py` es el patrón de reversibilidad, de catálogo y de privilegios con `aclexplode(relacl)`. El rol de migración es superusuario en la suite: «con el rol de migración» significa `conectar("migracion", …)`.
- `backend/cimenta/presupuesto/` existe con las cuatro capas y un `interfaz.py` vacíos. Su grafo en `pyproject.toml` permite que lo importen `compras`, `almacen`, `avance`, `personal` y `analitica`; él puede importar `identidad`, `auditoria` y `archivos`.
- `backend/tipos_base/numericos.py`: `Dinero` (escala 4), `Cantidad` (4), `Rendimiento` (6) y `Porcentaje` (6, con `0.050000` como 5 %). Las escalas de `NUMERIC` del esquema: importes `(18,4)`, precios y cantidades `(14,4)`, rendimientos `(18,6)`, porcentajes `(9,6)` (modelo de datos §2).

**Fuentes del DDL.** [Modelo de datos §4.1 a §4.3 y §11](../../../docs/03-modelo-datos.md): tablas y columnas. El borrador OpenAPI fija los conjuntos cerrados (`Unidad`, `TipoInsumo`, `EstadoObra`, `EstadoImportacion`, `TipoErrorImportacion`, `EstadoLineaBase`) y la nulabilidad de `Importacion`, `ErrorImportacion` y `PresupuestoControl`. [Invariantes del modelo de datos](../../../docs/03-modelo-datos.md): 5, 6, 8, 13, 14, 19 y 27. ADR de copia física de la línea base, ADR-004, ADR-008 y el ADR de roles de PostgreSQL.

**Escenarios de HDU-001 que apoyan en garantías de este ticket** (los implementan otros tickets): esc. 3 (código de obra único), esc. 8 (unidad fuera del catálogo, respaldo del motor), esc. 9 (concepto repetido), esc. 18 (la base rechaza alterar una línea base congelada), esc. 19 (una sola línea base congelada por obra), esc. 27 y `RNF-17` (`SIN_CONCEPTOS`, latido, `PROCESO_INTERRUMPIDO`). HDU-002 esc. 9 usa `FOR UPDATE` sobre `presupuesto_control` y `explosion_presupuesto` (ADR-004).

**Discrepancias entre el ticket y el modelo, que `M8` y el diseño resuelven.** El ticket omite `empresa.dias_semana_laboral`, `UNIQUE (obra.codigo)` y la unicidad de la explosión, que esta spec incorpora; omite además las cuatro restricciones que quedan como «Won't». El ticket y el modelo no fijan la nulabilidad de casi ninguna columna (`PA-T10`). La arquitectura §9 omite `DESCARTADO`.

**Del glosario.** «Partida» (conceptos agrupados por tipo de trabajo dentro de un área) no es lo mismo que «tipo de partida» (la unidad de control, cuatro bolsas por obra, `PA-01`). Hay dos rendimientos, el congelado (en la explosión) y el observado (en su tabla). El presupuesto de control es un tope que **captura** Dirección, no se calcula.

**Aguas abajo.** TKT-010 siembra `empresa`, `tipo_partida`, `insumo` y precios; TKT-012 (obras), TKT-013 a TKT-016 (importación, validaciones y explosión), TKT-017 (congelado, copias y control), TKT-018 (importación con su archivo), TKT-019 y siguientes (compras bloquea con `FOR UPDATE`), TKT-039 (`umbral_alerta_pct`) y, en la fase 2, TKT-042, TKT-046 y TKT-049.
