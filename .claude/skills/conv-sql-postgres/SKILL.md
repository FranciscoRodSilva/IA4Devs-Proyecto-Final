---
name: conv-sql-postgres
description: Convenciones de esquema PostgreSQL y migraciones Alembic en CIMENTA — NUMERIC para dinero, snake_case singular, restricciones nombradas, disparadores de inmutabilidad, tres roles, migraciones reversibles. Cárgala antes de escribir o auditar esquema, migraciones o consultas.
---

# Convenciones · PostgreSQL y Alembic

## 1 · El esquema sostiene los invariantes

Treinta y ocho invariantes del [modelo de datos](../../../docs/03-modelo-datos.md) viven en garantías de PostgreSQL. **Lo que la base puede sostener, lo sostiene la base.** Una regla implementada solo en Python se salta con un `psql`, con un script de carga o con el siguiente servicio que alguien conecte.

| Invariante | Mecanismo |
|---|---|
| La línea base congelada es inmutable | disparador que rechaza `UPDATE` y `DELETE` |
| La bitácora no admite modificación | sin `UPDATE`, `DELETE` ni `TRUNCATE` para el rol de aplicación (invariante 10, TKT-007) |
| El inventario es solo-anexado | sin columna de existencia; correcciones como movimiento `AJUSTE` |
| Rangos y dominios cerrados | `CHECK` con nombre |
| Unicidad condicional | único parcial con `WHERE` |

**Los disparadores protegen estructura, nunca implementan reglas de negocio.** Nada de procedimientos almacenados con lógica: las reglas viven en `dominio/`, donde `import-linter` y los tests de dominio las alcanzan.

## 2 · Tipos

- **Dinero: `NUMERIC` con precisión y escala declaradas.** `DOUBLE PRECISION` y `REAL` prohibidos para cualquier importe, cantidad monetaria o porcentaje que entre en un cálculo de dinero. Las escalas por concepto están en [modelo de datos §2](../../../docs/03-modelo-datos.md): `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje` no comparten escala.
- **Claves primarias `UUID`** en toda tabla y **columnas de auditoría** en toda tabla transaccional, según el modelo de datos §2: en identidad, solo `usuario` y `usuario_rol`.
- **`TIMESTAMPTZ`** para todo lo que registre un instante. `DATE` solo para fechas de calendario del negocio.
- `TEXT` antes que `VARCHAR(n)` salvo que el límite sea una regla real.

## 3 · Nombres

- **`snake_case` singular** para tablas y columnas: `requisicion`, no `requisiciones`. Contradice la recomendación más común de internet; aquí manda la convención del proyecto.
- Español, el del [glosario](../../../docs/glosario.md).
- **Toda restricción con nombre explícito.** Una restricción anónima no se puede eliminar limpiamente en una migración futura. El `naming_convention` del `MetaData` lo resuelve para lo que genera SQLAlchemy; lo que se escriba a mano lleva su nombre escrito.
- Prefijos: `pk_`, `fk_`, `uq_`, `ck_`, `ix_`, `trg_`.

## 4 · Migraciones Alembic

- **Revisadas a mano, siempre.** `--autogenerate` es un punto de partida: **no detecta renombrados** y los emite como `drop` + `add`, que en producción es pérdida de datos. Comprobar cada diff antes de aceptarlo.
- **Reversibles.** Toda migración tiene su `downgrade` real. Si una no se puede revertir, se declara explícitamente y se escribe el plan de reversa en `design.md`.
- Una migración de esquema por ticket, más la de semilla si la hay, con el identificador en el mensaje y `--rev-id` correlativo.
- Los datos semilla van en su propia migración o en un script aparte, nunca mezclados con DDL de esquema.
- Nada de `create_all()`. El esquema se construye solo con `alembic upgrade head`, también en los tests.

## 5 · Tres roles

| Rol | Puede |
|---|---|
| **migración** | DDL. Es el propietario de los objetos |
| **aplicación** | DML sobre lo que le corresponde. **Sin DDL** |
| **solo lectura** | `SELECT` |

**La migración crea los roles de aplicación y de solo lectura; el de migración lo crea el entorno**, y nada se crea a mano en el servidor (`RNF-09`). Cada tabla nace con los permisos por omisión que fija la migración inicial con `ALTER DEFAULT PRIVILEGES`, y cada migración de módulo **revoca** lo que su tabla no admite, con su prueba.

**Los tests se conectan con el rol de aplicación.** Con el propietario, las pruebas de permisos quedan verdes sin verificar nada — se anularían tres invariantes de golpe, porque los números 10, 20 y 21 *son* permisos.

### La trampa del privilegio mínimo mal aplicado

El reflejo de «quitar todo lo que se pueda» rompe el bloqueo pesimista, y falla **en tiempo de ejecución**, no en la migración:

- En PostgreSQL, **`SELECT … FOR UPDATE` exige privilegio `UPDATE`** sobre la tabla. El rol de aplicación **sí** necesita `UPDATE` sobre `explosion_presupuesto` y `presupuesto_control`, o el bloqueo de [ADR-004](../../../docs/adr/20260918-bloqueo-pesimista-presupuesto.md) falla por permisos.
- La inmutabilidad de la línea base **la garantiza el disparador** del invariante 14, **no** la ausencia de privilegio. No intentes sustituir uno por el otro.
- Donde el invariante sí es un permiso, se aplica: el rol de aplicación **no** tiene `UPDATE` ni `DELETE` sobre `intento_acceso` (invariante 20), y el rol de solo lectura no tiene más que `SELECT` (invariante 21).
- **`lock_timeout` y `statement_timeout` se fijan en el rol de aplicación** (`RNF-16`), no en cada conexión: así aplican aunque una ruta nueva no los pida.

## 6 · Índices y consultas

- Índice por cada llave foránea que se use en filtro o en `JOIN`.
- Índice compuesto por `(obra_id, tipo_partida_id)` donde el control presupuestal filtra. El control es **por obra y tipo de partida**, no por ubicación.
- La consulta del semáforo está definida una sola vez en [modelo de datos §15](../../../docs/03-modelo-datos.md) y la comparten la regla y el tablero. Si se reescribe en dos sitios, el tablero y el bloqueo dejan de coincidir — y el usuario ve un disponible que el sistema no respeta.
- `EXPLAIN` antes de dar por buena una consulta sobre una tabla que crece: la bitácora y el libro mayor de inventario crecen sin parar por diseño.

## 7 · Todo gasto lleva `obra_id`

Y toda requisición además `tipo_partida_id`. No es opcional, no es nullable, y no se deduce: se exige. Es la columna sobre la que se apoya la autorización, así que una fila sin ella es a la vez un dato huérfano y un agujero de seguridad.

## 8 · Al auditar una migración

- [ ] `downgrade` escrito y probado (`upgrade head` → `downgrade -1` → `upgrade head`)
- [ ] Ninguna columna de dinero en punto flotante
- [ ] Toda restricción con nombre
- [ ] Revocación y prueba de lo que la tabla no admite
- [ ] Índice para cada llave foránea que se filtre
- [ ] Disparadores de inmutabilidad donde el invariante lo exige
- [ ] Ninguna operación destructiva sin plan de reversa documentado
- [ ] Ningún `DROP` o `ALTER ... TYPE` sobre una tabla con datos sin estrategia declarada
- [ ] Ninguna lógica de negocio en el esquema
