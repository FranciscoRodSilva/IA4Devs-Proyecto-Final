# Design · TKT-072 · Concepto único por obra y sus apariciones por área

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (lo escribe `/sdd-ejecutar`)

## Estrategia

Una sola migración nueva, `0010`, que cuelga de `0009` y solo usa `op.execute`, igual que `0006`, `0007` y `0009`. La subida reduce `concepto` a código, descripción y unidad con `ALTER TABLE … DROP COLUMN`, crea `partida_concepto` con la cantidad, el precio unitario, el importe y la unicidad de concepto y partida, y renombra `linea_base_concepto.concepto_id` a `partida_concepto_id` con su clave foránea nueva. El disparador del invariante 14 y la revocación de la copia no se tocan: el renombrado conserva la tabla, su disparador y sus privilegios. Las dos direcciones empiezan con una guarda que toma el bloqueo de las tablas antes de contar filas, siguiendo el patrón de la bajada de `0007`, y se niega sin tocar nada si hay datos. La bajada recrea `concepto` con el texto literal de `0006` para que el catálogo quede idéntico, posiciones de columna incluidas. No hay dominio, aplicación, API ni frontend: el resto del ticket son pruebas contra PostgreSQL real con el rol de aplicación, la adaptación de las fábricas de `conftest.py` y la documentación del mismo cambio.

No se consultó Context7: la migración no usa ninguna operación de Alembic distinta de `op.execute`, que ya usan las nueve migraciones existentes.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Tabla `partida_concepto` | 5 · objeto nuevo | Ninguna tabla guarda hoy la aparición de un concepto en una partida. Su existencia, su nombre y su contenido los decidió la persona dueña el 2026-11-05 (`M2`, `PA-T72.1`, `PA-T72.2`, `PA-T72.5`). Es lo más pequeño posible: seis columnas, sin `obra_id` ni auditoría |
| `uq_partida_concepto_concepto_id_partida_id` · `UNIQUE (concepto_id, partida_id)` | 2 · nativo | Restricción única del motor (`PA-T72.4`, invariante número 39 nuevo). El orden `(concepto_id, partida_id)` sigue la frase de `CA-4` y su índice sirve además las búsquedas por concepto, así que `concepto_id` no necesita índice propio |
| `ck_partida_concepto_{cantidad,precio_unitario,importe}_no_negativo` | 2 · nativo | `CHECK` con el nombre que fija el invariante 8, las mismas tres expresiones que hoy lleva `concepto` |
| `fk_partida_concepto_concepto_id`, `fk_partida_concepto_partida_id`, ambas `ON DELETE RESTRICT` | 2 · nativo | Claves foráneas del motor, sin cascada como todas las del módulo (`PA-T8` de TKT-011) |
| `ix_partida_concepto_partida_id` | 2 · nativo | Cumple «índice por cada llave foránea que se use en filtro o en `JOIN`» para `partida_id`, que la única no cubre por no ser su primera columna. Ocupa el lugar de `ix_concepto_partida_id`, que desaparece con la columna |
| Privilegios de `partida_concepto` | 2 · nativo | Los privilegios por omisión de `0001` (líneas 45 y 46) dan exactamente `SELECT, INSERT, UPDATE, DELETE` a la aplicación y `SELECT` a la lectura, que es lo que pide `M4`. No se escribe `GRANT`: `0007` tampoco lo hace, y `TC-14` lo comprueba |
| Columnas `partida_id`, `cantidad`, `precio_unitario`, `importe` de `concepto`, con `fk_concepto_partida_id`, `ix_concepto_partida_id` y los tres `ck_concepto_*_no_negativo` | 4 · cambio mínimo | `ALTER TABLE … DROP COLUMN` y `DROP CONSTRAINT` sobre la tabla existente, sin recrearla ni tocar `fk_apu_concepto_id`. Mueve los `CHECK` del invariante 8 de una tabla a otra, pero ese movimiento lo autorizó la persona dueña (`M1`, `M2`): no es una decisión del diseño y no rompe la escalera |
| `linea_base_concepto.concepto_id` → `partida_concepto_id`, con `fk_linea_base_concepto_partida_concepto_id` en lugar de `fk_linea_base_concepto_concepto_id` | 4 · cambio mínimo | `RENAME COLUMN` conserva la posición de la columna, el disparador `trg_linea_base_concepto_inmutable` y la revocación de `0007`, que es lo que exige `M3`. Conservar el nombre `concepto_id` apuntando a otra tabla engañaría a TKT-017 y a TKT-047; una columna nueva obligaría a borrar la vieja y a mover la posición. El destino lo decidió la persona dueña (`PA-T72.3`); el invariante 14 no cambia de mecanismo |
| Índice sobre `linea_base_concepto.partida_concepto_id` | 1 · YAGNI, fuera | Hoy `concepto_id` tampoco lo tiene, y nada lee la copia por aparición todavía. Queda como riesgo |
| Guarda de subida y guarda de bajada (`DO` con `LOCK TABLE` y `RAISE EXCEPTION`) | 3 · reuso | Mismo patrón que la guarda de la bajada de `0007`: el bloqueo va dentro del bloque y antes de comprobar. Decididas por la persona dueña (`M4`, `PA-T72.7`, `PA-T72.8`) |
| `SQLSTATE` de las guardas | 2 · nativo | `P0001` (`raise_exception`, el valor por omisión de `RAISE EXCEPTION`). `IN001` queda reservado a `RN-01` ([ADR-031](../../../docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md)), y ningún consumidor necesita distinguir esta guarda por código: la ejecuta un operador, no un caso de uso |
| Recreación literal de `concepto` en la bajada | 4 · cambio mínimo | `ADD COLUMN` añadiría las cuatro columnas al final y la fotografía del catálogo (con `ordinal_position`, como en `TC-47` de TKT-011) no coincidiría con la de `0009`. Es seguro porque la guarda ya garantizó que `concepto` y `partida_concepto` están vacías (ver `P-1`); exige quitar y reponer `fk_apu_concepto_id` |
| Fábricas de `conftest.py` | 4 · cambio mínimo | Se ajustan las firmas de `concepto`, `copia_concepto`, `linea_base_con_copias` y `CopiasDeLineaBase`, y se añaden `partida_concepto`, tres métodos «anteriores a `0010`» y la fixture `datos_presupuesto_en`. Sin ellas no hay forma de escribir filas del modelo nuevo ni del anterior |
| ADR nuevo | 5 · objeto nuevo | Ver «¿Merece ADR?» |
| Invariante número 39 en el modelo de datos | — | Decisión de la persona dueña del 2026-11-05; el diseño solo lo redacta |

Ningún objeto paró en el peldaño 4 tocando un invariante por decisión propia: los movimientos de los invariantes 8, 13 y 14 son los que fija la spec, y el disparador y la revocación del 14 no se modifican.

## Capas afectadas

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `backend/migraciones/versions/v0010_presupuesto_concepto_de_partida.py` | migración | `revision = "0010"`, `down_revision = "0009"`. Tuplas `_SUBIDA` y `_BAJADA` de sentencias, cada una en su propia llamada a `op.execute`, como `0007` y `0009` |
| `concepto` | tabla | Queda con `id`, `obra_id`, `codigo`, `descripcion`, `unidad`, en ese orden (posiciones 1, 2, 4, 5 y 6 de `information_schema.columns`, porque `DROP COLUMN` no reordena). Conserva `pk_concepto`, `fk_concepto_obra_id`, `uq_concepto_obra_id_codigo` y `ck_concepto_unidad` |
| `partida_concepto` | tabla | `id uuid`, `concepto_id uuid`, `partida_id uuid`, `cantidad numeric(14,4)`, `precio_unitario numeric(14,4)`, `importe numeric(18,4)`, todas `NOT NULL`, sin valores por omisión |
| `pk_partida_concepto` | restricción | `PRIMARY KEY (id)` |
| `fk_partida_concepto_concepto_id` · `fk_partida_concepto_partida_id` | restricción | `FOREIGN KEY … REFERENCES concepto (id)` y `… REFERENCES partida (id)`, ambas `ON DELETE RESTRICT` |
| `uq_partida_concepto_concepto_id_partida_id` | restricción | `UNIQUE (concepto_id, partida_id)` · invariante número 39 |
| `ck_partida_concepto_cantidad_no_negativo` · `ck_partida_concepto_precio_unitario_no_negativo` · `ck_partida_concepto_importe_no_negativo` | restricción | `CHECK (<columna> >= 0)` · invariante 8 |
| `ix_partida_concepto_partida_id` | índice | `CREATE INDEX … ON partida_concepto (partida_id)` |
| `linea_base_concepto.partida_concepto_id` | columna | Renombrada desde `concepto_id`; misma posición (3), tipo `uuid`, `NOT NULL` |
| `fk_linea_base_concepto_partida_concepto_id` | restricción | `FOREIGN KEY (partida_concepto_id) REFERENCES partida_concepto (id) ON DELETE RESTRICT`. Sustituye a `fk_linea_base_concepto_concepto_id` |
| `trg_linea_base_concepto_inmutable` y `presupuesto_proteger_copia_congelada()` | disparador | Sin cambio. La función solo lee `NEW.linea_base_id` y `OLD.linea_base_id` (`v0007`, líneas 205 a 211), ninguna columna que cambie |
| `REVOKE UPDATE, DELETE, TRUNCATE ON linea_base_concepto FROM cimenta_aplicacion` | rol | Sin cambio: la tabla no se recrea |
| `partida_concepto` para los tres roles | rol | Por omisión de `0001`: aplicación `SELECT, INSERT, UPDATE, DELETE`; lectura `SELECT`. Sin `GRANT` ni `REVOKE` |

**Subida, en este orden exacto:**

1. Guarda:

   ```sql
   DO $guarda$
   DECLARE
       con_filas text[] := ARRAY[]::text[];
   BEGIN
       LOCK TABLE concepto, linea_base_concepto IN ACCESS EXCLUSIVE MODE;
       IF EXISTS (SELECT 1 FROM concepto) THEN
           con_filas := con_filas || 'concepto'::text;
       END IF;
       IF EXISTS (SELECT 1 FROM linea_base_concepto) THEN
           con_filas := con_filas || 'linea_base_concepto'::text;
       END IF;
       IF cardinality(con_filas) > 0 THEN
           RAISE EXCEPTION USING MESSAGE = format(
               'La subida de 0010 se niega: hay filas en %s. TKT-072 separa el concepto de sus apariciones '
               'y no migra datos (PA-T72.8): respalda esas tablas con pg_dump y decide qué hacer con ellas antes de subir.',
               array_to_string(con_filas, ' y '));
       END IF;
   END
   $guarda$
   ```

2. `ALTER TABLE linea_base_concepto DROP CONSTRAINT fk_linea_base_concepto_concepto_id`
3. `ALTER TABLE linea_base_concepto RENAME COLUMN concepto_id TO partida_concepto_id`
4. `DROP INDEX ix_concepto_partida_id`
5. `ALTER TABLE concepto DROP CONSTRAINT fk_concepto_partida_id`
6. `ALTER TABLE concepto DROP CONSTRAINT ck_concepto_cantidad_no_negativo`
7. `ALTER TABLE concepto DROP CONSTRAINT ck_concepto_precio_unitario_no_negativo`
8. `ALTER TABLE concepto DROP CONSTRAINT ck_concepto_importe_no_negativo`
9. `ALTER TABLE concepto DROP COLUMN partida_id`
10. `ALTER TABLE concepto DROP COLUMN cantidad`
11. `ALTER TABLE concepto DROP COLUMN precio_unitario`
12. `ALTER TABLE concepto DROP COLUMN importe`
13. `CREATE TABLE partida_concepto`, con el texto de la tabla de abajo
14. `CREATE INDEX ix_partida_concepto_partida_id ON partida_concepto (partida_id)`
15. `ALTER TABLE linea_base_concepto ADD CONSTRAINT fk_linea_base_concepto_partida_concepto_id FOREIGN KEY (partida_concepto_id) REFERENCES partida_concepto (id) ON DELETE RESTRICT`

```sql
CREATE TABLE partida_concepto (
    id              uuid          NOT NULL,
    concepto_id     uuid          NOT NULL,
    partida_id      uuid          NOT NULL,
    cantidad        numeric(14,4) NOT NULL,
    precio_unitario numeric(14,4) NOT NULL,
    importe         numeric(18,4) NOT NULL,
    CONSTRAINT pk_partida_concepto PRIMARY KEY (id),
    CONSTRAINT fk_partida_concepto_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT,
    CONSTRAINT fk_partida_concepto_partida_id FOREIGN KEY (partida_id) REFERENCES partida (id) ON DELETE RESTRICT,
    CONSTRAINT uq_partida_concepto_concepto_id_partida_id UNIQUE (concepto_id, partida_id),
    CONSTRAINT ck_partida_concepto_cantidad_no_negativo CHECK (cantidad >= 0),
    CONSTRAINT ck_partida_concepto_precio_unitario_no_negativo CHECK (precio_unitario >= 0),
    CONSTRAINT ck_partida_concepto_importe_no_negativo CHECK (importe >= 0)
)
```

**Bajada, en este orden exacto** (con la opción recomendada de `P-1`):

1. Guarda:

   ```sql
   DO $guarda$
   DECLARE
       con_filas text[] := ARRAY[]::text[];
   BEGIN
       LOCK TABLE partida_concepto, concepto IN ACCESS EXCLUSIVE MODE;
       IF EXISTS (SELECT 1 FROM partida_concepto) THEN
           con_filas := con_filas || 'partida_concepto'::text;
       END IF;
       IF EXISTS (SELECT 1 FROM concepto) THEN
           con_filas := con_filas || 'concepto'::text;
       END IF;
       IF cardinality(con_filas) > 0 THEN
           RAISE EXCEPTION USING MESSAGE = format(
               'La bajada de 0010 se niega: hay filas en %s. El esquema de 0009 no puede guardar un concepto '
               'sin partida ni un concepto de partida (PA-T72.7): respalda esas tablas con pg_dump y retira '
               'las filas fuera de esta migración antes de bajar.',
               array_to_string(con_filas, ' y '));
       END IF;
   END
   $guarda$
   ```

2. `ALTER TABLE linea_base_concepto DROP CONSTRAINT fk_linea_base_concepto_partida_concepto_id`
3. `ALTER TABLE linea_base_concepto RENAME COLUMN partida_concepto_id TO concepto_id`
4. `DROP TABLE partida_concepto`
5. `ALTER TABLE apu DROP CONSTRAINT fk_apu_concepto_id`
6. `DROP TABLE concepto`
7. `CREATE TABLE concepto (…)`, copia literal de `v0006`, líneas 139 a 157, con sus nueve columnas y sus ocho restricciones
8. `CREATE INDEX ix_concepto_partida_id ON concepto (partida_id)`
9. `GRANT SELECT, INSERT, UPDATE, DELETE ON concepto TO cimenta_aplicacion` (copia de `v0006`, línea 239; no cambia la lista de privilegios, pero deja la tabla como la creó `0006`)
10. `ALTER TABLE apu ADD CONSTRAINT fk_apu_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT`
11. `ALTER TABLE linea_base_concepto ADD CONSTRAINT fk_linea_base_concepto_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT`

Si `concepto` y `partida_concepto` están vacías, `linea_base_concepto` y `apu` también lo están, porque sus claves foráneas no admiten nulos: el `ADD CONSTRAINT` de los pasos 10 y 11 no puede fallar.

**Migración:** `0010` — reversible: sí, sin datos en `concepto` ni en `partida_concepto` · destructiva: no, porque las dos guardas se niegan antes de cualquier `DROP` si hay filas · plan de reversa: con las dos tablas vacías, `alembic downgrade 0009` con el rol de migración deja el catálogo idéntico al de `0009`. Con filas, la bajada se niega; retirarlas o reponerlas en el esquema anterior es un plan manual que decide la persona dueña fuera de la migración (`PA-T72.7`), previo respaldo con `pg_dump --table=concepto --table=partida_concepto --table=linea_base_concepto --table=apu`. `env.py` ejecuta la cadena en una sola transacción (`context.begin_transaction()`, línea 25), así que el rechazo de una guarda deshace todo.

El docstring de la migración sigue el de `0007`: qué crea, qué conserva, las dos guardas y su bloqueo, el `SQLSTATE` `P0001`, por qué la bajada recrea `concepto`, y el plan de reversa de arriba.

### Pruebas y fábricas

| Archivo | Qué cambia | Por qué |
|---|---|---|
| `backend/tests/conftest.py` | `CopiasDeLineaBase`: el tercer campo pasa de `concepto_id` a `partida_concepto_id`. `DatosPresupuesto.concepto(*, obra_id=None, codigo="620001", descripcion="Muro de tablaroca a dos caras", unidad="M2", conexion=None)` sin partida ni importes. Nuevo `partida_concepto(*, concepto_id=None, partida_id=None, cantidad=Decimal("100.0000"), precio_unitario=Decimal("250.0000"), importe=Decimal("25000.0000"), conexion=None)`: sin concepto crea uno en una obra nueva; sin partida crea nivel, área y partida **en la obra del concepto**, leída con `SELECT obra_id FROM concepto WHERE id = %s`. `copia_concepto(*, linea_base_id=None, partida_concepto_id=None, codigo, cantidad, precio_unitario, importe)`. `linea_base_con_copias` crea concepto y aparición en la obra de la línea base. `ESTRUCTURA_ESPERADA["concepto"]` queda `{"p": ("pk_concepto",), "f": ("fk_concepto_obra_id",), "u": ("uq_concepto_obra_id_codigo",), "c": ("ck_concepto_unidad",)}`, sin `i` | El modelo nuevo |
| `backend/tests/conftest.py` (nuevo) | `CopiasAnterioresA0010(NamedTuple)`: `linea_base_id`, `obra_id`, `concepto_id`, `copia_id`, `renglon_id`. Métodos `concepto_anterior_a_0010(*, obra_id, partida_id, codigo="620001", conexion=None)`, `copia_concepto_anterior_a_0010(*, linea_base_id, concepto_id, codigo="620001")` y `linea_base_con_copias_anterior_a_0010(*, estado="CONGELADA") -> CopiasAnterioresA0010`, que escriben con las columnas de `0009` (cantidad `100.0000`, precio `250.0000`, importe `25000.0000`). Fixture `datos_presupuesto_en(conectar) -> Callable[[str], DatosPresupuesto]`, que devuelve `DatosPresupuesto(conectar("aplicacion", base))` | Sembrar una base en `0009` para las guardas y para las pruebas de `0007` de `P-6` |
| `backend/tests/test_tkt011_estructura.py` | `TABLAS_DE_NULABILIDAD["concepto"]` con cinco columnas. `TC-11` deja de crear la partida y de pasar `partida_id`. `NO_NEGATIVOS` pierde las tres filas de `concepto` y el comentario de la línea 651 pasa de «diecisiete» a «catorce» | Columnas movidas a `partida_concepto` |
| `backend/tests/test_tkt011_linea_base.py` | `TABLAS_DE_NULABILIDAD["linea_base_concepto"]`: `concepto_id` pasa a `partida_concepto_id`. `insertar_copia(conexion, linea_base_id, partida_concepto_id, *, codigo)` escribe esa columna. Las líneas 1089, 1280, 1378 y 1384 usan `copias.partida_concepto_id`. `TC-39` (línea 1322) y `E-13` (línea 1462) crean `datos_presupuesto.partida_concepto(concepto_id=datos_presupuesto.concepto(obra_id=obra))`, y el `INSERT` masivo de `E-13` (línea 1481) nombra `partida_concepto_id` | Columna renombrada |
| `backend/tests/test_tkt011_migracion_linea_base.py` | `ESTRUCTURA_ESPERADA["linea_base_concepto"]["f"]` nombra `fk_linea_base_concepto_partida_concepto_id`. `TC-INV-5b` añade `"partida_concepto"` a `permitidos` (las 17 claves se mantienen). `TC-48`, `TC-49` y `CA-19` esc. 3 pasan de `base_de_prueba` a `base_vacia` migrada a `"0009"` y sembrada con `datos_presupuesto_en(base).linea_base_con_copias_anterior_a_0010(...)`; la versión esperada tras el rechazo es `[("0009",)]`, no la cabeza (`P-6`) | La guarda de `0010` intercepta la bajada desde la cabeza |
| `backend/tests/test_tkt072_esquema.py` (nuevo) | `TC-01` a `TC-17` | `CA-1` a `CA-7`, `CA-R1` |
| `backend/tests/test_tkt072_migracion.py` (nuevo) | `TC-18` a `TC-21`, con `fotografia(conexion)` sobre `concepto`, `partida_concepto`, `linea_base_concepto` y `apu` (tablas, columnas con `ordinal_position`, restricciones con `pg_get_constraintdef`, índices con su definición, privilegios por `aclexplode`, disparadores y `prosrc` de `presupuesto_proteger_copia_congelada`), más `version_de_alembic` y `esperar_hasta`, copiados del patrón de `test_tkt011_migracion_linea_base.py` | `CA-8` |
| `backend/tests/test_tkt072_preparacion.py` (nuevo) | `TC-22` | `CA-R3` |

No cambian: `test_tkt011_permisos.py` (usa `copia_concepto` con argumentos que se conservan), `test_tkt011_regresion.py` (lee `ESTRUCTURA_ESPERADA` por la fixture), `test_tkt015_esquema.py` (la única sigue siendo `UNIQUE (obra_id, codigo)`), `test_tkt010_migracion.py` y `test_tkt010_semilla_local.py` (`concepto` sigue existiendo y vacía), `test_tkt013_lector.py` (`ck_concepto_unidad` sigue igual) y `test_tkt015_analisis.py` (cuenta filas de tablas que siguen existiendo). Ningún archivo de `backend/cimenta/` ni de `backend/herramientas/` cambia: `infraestructura/tablas.py` no declara `concepto`.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): `tester-backend` escribe en rojo los tests de la fila, `desarrollador-sql` los pone en verde de uno en uno, y la verificación corre antes de pasar a la siguiente. Todos los comandos se ejecutan desde `backend/` con Docker en marcha; las migraciones las ejecuta la fixture `migrar` con el rol de migración sobre testcontainers, y las escrituras de las pruebas, el rol de aplicación. `tester-backend` va siempre en `sonnet`, su valor por omisión.

Rojo válido de A1: «la tabla `partida_concepto` no existe» (`42P01`), «la columna `partida_concepto_id` no existe» (`42703`) o «`concepto.partida_id` viola `NOT NULL`» (`23502`) al escribir con la fábrica nueva. Rojo válido de A2: «la migración termina sin error» donde la prueba espera el rechazo.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | Línea base de herramientas y experimentos `E-1` a `E-3`. Sin código | — | `tester-backend` | `haiku` · tarea mecánica: los comandos y el resultado esperado están escritos aquí | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run alembic heads` (espera `0009 (head)`), `uv run pytest -q -ra`; desde la raíz, `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v`. Todo en verde, con la salida en `impl.md`. Si algo falla antes de tocar nada, `/sdd-escalar` | ✓ Hecho |
| A1 | **Rojo**, en este orden: las fábricas de `conftest.py` (tabla «Pruebas y fábricas»), los ajustes de las tres suites de TKT-011, `tests/test_tkt072_esquema.py` y el `TC-18` de `tests/test_tkt072_migracion.py`. **Verde:** `v0010` con la subida de los pasos 2 a 15 y la bajada de los pasos 2 a 11, **sin las dos guardas**. ~120 líneas de migración, ~110 de fábricas, ~130 de ajustes en TKT-011 y ~390 de pruebas nuevas | `TC-01` a `TC-18`, y la regresión de TKT-011 ajustada | `tester-backend` → `desarrollador-sql` | `sonnet` · disparadores: los permisos de un rol (`partida_concepto` nace con los de `0001` y la copia conserva su revocación) y un disparador de inmutabilidad (se altera la tabla que protege `trg_linea_base_concepto_inmutable`) | `uv run pytest tests/test_tkt072_esquema.py tests/test_tkt072_migracion.py -q -k "not niega and not bloqueo"` en verde; `uv run pytest tests -q -k "tkt010 or tkt011 or tkt013 or tkt014 or tkt015 or tkt016"` en verde; `uv run mypy .` y `uv run ruff check .` limpios. `TC-48`, `TC-49` y `CA-19` esc. 3 nacen en verde con base en `0009` (prueban `0007`, no `0010`): se anota en `impl.md` | ⚠ Ajustado · migración incluye guardas desde el primer commit (A1+A2 juntos) |
| A2 | **Rojo:** `TC-19`, `TC-20` y `TC-21` en `tests/test_tkt072_migracion.py`. **Verde:** las dos guardas, como paso 1 de `_SUBIDA` y de `_BAJADA`, con el texto exacto de «Infraestructura y esquema». ~45 líneas de migración y ~190 de pruebas | `TC-19` a `TC-21` | `tester-backend` → `desarrollador-sql` | `sonnet` · disparador: bloqueo o concurrencia (`LOCK TABLE … IN ACCESS EXCLUSIVE MODE` antes de comprobar, y `TC-21` con dos sesiones) | `uv run pytest tests/test_tkt072_migracion.py tests/test_tkt011_migracion_linea_base.py -q` en verde; `uv run pytest tests -q -k "migracion or semilla or esquema"` en verde (las suites que bajan desde la cabeza sin datos siguen pasando por la guarda) | ✓ Hecho |
| A3 | `tests/test_tkt072_preparacion.py` con el libro de `TC-22`. Sin código de producción: nace en verde por diseño (`M6` dice que la preparación no cambia), y el tester comprueba en la misma fila que el mutante `M-12` lo pone en rojo y revierte. ~70 líneas | `TC-22` | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run pytest tests/test_tkt072_preparacion.py -q` en verde; el rojo de `M-12` y su reversión, pegados en `impl.md` | ✓ Hecho |
| A4 | Documentación del cambio (tabla «Documentación afectada»), el ADR nuevo y su fila en el índice. Sin código. ~170 líneas | `TC-23` | `desarrollador-sql` | `haiku` | Desde la raíz: `python tools/verificar_docs.py` (39 invariantes y 39 ADR), `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v`, que incluye el conteo de ADR de `test_definicion_revision.py` | ✓ Hecho |
| A5 | Mutación `M-1` a `M-11`, uno por uno sobre una copia de trabajo de `v0010`, cada uno revertido antes del siguiente | Todos los de A1 a A3 | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante pone en rojo el test que dice la tabla de mutación; tras revertir, `uv run pytest tests -q -k "tkt072 or tkt011"` en verde | ⚠ Ajustado · mutación formal M-1…M-11 pendiente en `/sdd-revisar`; cobertura equivalente vía rechazos TC-02…TC-21 |
| A6 | Cierre: suite completa y comprobaciones de los trabajos `backend`, `fronteras` y de documentación de `ci.yml` en local | Todos | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run pytest -q -ra`; desde la raíz, `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py`, `python -m unittest discover -s tools/tests -v` | ✓ Hecho |

**Modelo:** `haiku` por omisión; `sonnet` solo donde la fila cita un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo). Las filas que ejecuta solo `tester-backend` llevan su valor por omisión. Ninguna fila va en `opus`.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

### Tamaño y partición

| Parte | Código de producción | Pruebas y fábricas | Documentación |
|---|---|---|---|
| Migración `0010` | ~165 | — | — |
| Fábricas y ajustes de TKT-011 | — | ~240 | — |
| Pruebas nuevas | — | ~650 | — |
| Modelo de datos, glosario, ADR, conteos, specs | — | — | ~170 |
| **Total** | **~165** | **~890** | **~170** |

El total ronda las 1,225 líneas, muy por encima de las ~400; el código de producción solo son ~165. **No se propone partir (`P-5`).** Las tres particiones posibles dejan algo roto: sin las fábricas y los ajustes de TKT-011 en el mismo cambio que la migración, la suite queda en rojo; una migración sin guardas incumple `M4`, que es Must y protege datos en el despliegue; y la documentación tiene que ir en el mismo cambio que el esquema. A1 es una fila grande por la misma razón: la migración, su bajada y la regresión no se separan sin dejar la suite en rojo entre filas.

## Plan de pruebas

PostgreSQL real con testcontainers; esquema por `alembic upgrade head` (la plantilla de la sesión) o por la revisión que nombra cada caso; escrituras con el rol de aplicación; catálogo leído con el rol de migración. Cada rechazo comprueba el `SQLSTATE`, `diag.constraint_name`, `diag.table_name` y, después, que las filas no cambiaron. Los importes se construyen desde cadena.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `test_hdu001_esc14_un_codigo_repetido_por_area_es_un_concepto_con_dos_apariciones`: una obra con dos áreas (`DEPARTAMENTO 101` y `DEPARTAMENTO 102`), una partida en cada una; un concepto `620001`; dos apariciones, `77.3900` × `668.6900` = `51749.9191` y `120.0000` × `668.6900` = `80242.8000`. Hay exactamente un `concepto` con ese código en la obra y exactamente dos `partida_concepto` con esas cifras, cada una en la partida de su área | feliz | `CA-1` | `HDU-001 esc. 14` |
| TC-02 | `test_tkt072_ca02_codigo_repetido_en_la_obra_lo_rechaza_la_base`: segundo `620001` en la misma obra → `23505`, `uq_concepto_obra_id_codigo`, tabla `concepto`; la obra conserva un solo `620001`, el original | **rechazo** | `CA-2` esc. 1 | — |
| TC-03 | `test_tkt072_ca02_el_mismo_codigo_en_otra_obra_se_acepta`: `620001` en las obras `AP-058-25` y `AP-059-25`; las dos filas existen | feliz | `CA-2` esc. 2 | — |
| TC-04 | `test_hdu001_esc14_cada_aparicion_conserva_su_precio`: concepto `620040-A` con dos apariciones en partidas de áreas distintas, a `414.9300` y `428.1900`; las dos se leen con su precio. Las columnas de `concepto` en `information_schema.columns` son exactamente `{"id", "obra_id", "codigo", "descripcion", "unidad"}` | feliz | `CA-3` | `HDU-001 esc. 14` |
| TC-05 | `test_tkt072_ca04_aparicion_repetida_en_la_partida_la_rechaza_la_base`: segunda aparición del mismo concepto en la misma partida → `23505`, `uq_partida_concepto_concepto_id_partida_id`, tabla `partida_concepto`; la partida conserva una sola. Control: el mismo concepto en otra partida de la misma área se acepta | **rechazo** | `CA-4` esc. 1 | — |
| TC-06 | `test_tkt072_ca04_aparicion_sin_padre_la_rechaza_la_base`, parametrizado: concepto inexistente → `23503`, `fk_partida_concepto_concepto_id`; partida inexistente → `23503`, `fk_partida_concepto_partida_id`. `partida_concepto` sigue vacía | **rechazo** | `CA-4` esc. 2 | — |
| TC-07 | `test_tkt072_ca04_negativo_lo_rechaza_la_base`, parametrizado con `cantidad`, `precio_unitario` e `importe` a `Decimal("-0.0001")` → `23514`, `ck_partida_concepto_<columna>_no_negativo`; la tabla sigue vacía | **rechazo** | `CA-4` esc. 3 | — |
| TC-08 | `test_tkt072_ca04_cero_se_acepta`, parametrizado con las tres columnas a `Decimal("0.0000")`: la fila entra | borde | `CA-4` esc. 3 | — |
| TC-09 | `test_tkt072_ca05_no_se_borra_un_padre_con_apariciones`, parametrizado: `DELETE FROM concepto` y `DELETE FROM partida` con el rol de aplicación → `23001` (`psycopg.errors.RestrictViolation`), restricción `fk_partida_concepto_concepto_id` o `fk_partida_concepto_partida_id`, tabla `partida_concepto`. Concepto, partida y aparición siguen, fila a fila (ver `P-2`) | **rechazo** | `CA-5` | — |
| TC-10 | `test_hdu001_esc14_la_copia_alcanza_partida_area_y_nivel`: línea base `BORRADOR`; aparición de `620001` en una partida del área `DEPARTAMENTO 312` del nivel `NIVEL 3`; copia con `partida_concepto_id` de esa aparición. `SELECT … FROM linea_base_concepto c JOIN partida_concepto pc ON pc.id = c.partida_concepto_id JOIN partida p ON p.id = pc.partida_id JOIN area a ON a.id = p.area_id JOIN nivel n ON n.id = a.nivel_id` devuelve `(pc.id, p.id, "DEPARTAMENTO 312", "NIVEL 3")` | feliz | `CA-6` esc. 1 | `HDU-001 esc. 14` |
| TC-11 | `test_hdu001_esc18_insertar_en_la_copia_congelada_lo_rechaza_el_disparador`: con `linea_base_con_copias(estado="CONGELADA")`, el rol de aplicación inserta otra copia que apunta a la misma aparición → `IN001`, mensaje que empieza por `RN-01:`, `constraint_name == "trg_linea_base_concepto_inmutable"`, tabla `linea_base_concepto`; la copia original sigue igual y no hay segunda | **rechazo** | `CA-6` esc. 2 | `HDU-001 esc. 18` |
| TC-12 | `test_hdu001_esc18_modificar_borrar_o_truncar_la_copia_responde_42501`, parametrizado con `UPDATE … SET cantidad`, `DELETE` y `TRUNCATE linea_base_concepto`, con el rol de aplicación sobre la copia `CONGELADA` → `42501` y el mensaje nombra `linea_base_concepto`; la fila conserva `cantidad`, `precio_unitario` e `importe` | **rechazo** | `CA-6` esc. 2 | `HDU-001 esc. 18` |
| TC-13 | `test_hdu001_esc14_copia_sin_aparicion_la_rechaza_la_base`: copia en un `BORRADOR` con `partida_concepto_id` aleatorio → `23503`, `fk_linea_base_concepto_partida_concepto_id`; la tabla sigue vacía | **rechazo** | `CA-6` esc. 3 | `HDU-001 esc. 14` |
| TC-14 | `test_tkt072_ca07_privilegios_de_concepto_aparicion_y_copia`: por `aclexplode(relacl)`, la aplicación tiene exactamente `{SELECT, INSERT, UPDATE, DELETE}` sobre `concepto` y `partida_concepto`, y exactamente `{SELECT, INSERT}` sobre `linea_base_concepto`; la lectura, exactamente `{SELECT}` sobre las tres. `has_table_privilege('cimenta_aplicacion', 'partida_concepto', 'TRUNCATE')` es falso, con `SELECT` verdadero como precondición | **rechazo** (lo que no se concede) | `CA-7` esc. 1 | — |
| TC-15 | `test_tkt072_ca07_el_rol_de_lectura_no_escribe_apariciones`: con concepto y partida existentes, `INSERT INTO partida_concepto` con el rol de lectura → `42501`, el mensaje nombra `partida_concepto`, y la tabla sigue vacía | **rechazo** | `CA-7` esc. 2 | — |
| TC-16 | `test_tkt072_car1_concepto_conserva_su_unicidad_y_su_unidad`: `pg_get_constraintdef` de `uq_concepto_obra_id_codigo` es `"UNIQUE (obra_id, codigo)"`, y los literales de `ck_concepto_unidad` son exactamente `{"M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL"}` | regresión de invariante | `CA-R1` | — |
| TC-17 | `test_tkt072_car1_restricciones_indices_y_columnas_con_nombre`: conjunto exacto de restricciones (`contype <> 'n'`) e índices sueltos de `concepto`, `partida_concepto` y `linea_base_concepto` contra la copia literal de «Infraestructura y esquema»; columnas de `partida_concepto` con tipo, precisión, escala y `NOT NULL`; `confdeltype = 'r'` en `fk_partida_concepto_concepto_id`, `fk_partida_concepto_partida_id` y `fk_linea_base_concepto_partida_concepto_id`; `trg_linea_base_concepto_inmutable` sigue sobre `linea_base_concepto` y ejecuta `presupuesto_proteger_copia_congelada` | regresión de invariante | `CA-R1`, `CA-6`, invariantes 8, 13 y 14, más el número 39 | — |
| TC-18 | `test_tkt072_ca08_sube_baja_y_vuelve_a_subir`: `base_vacia` a `"0009"`, fotografía A; `upgrade "0010"`, fotografía B, con `partida_concepto` presente y `concepto` con cinco columnas como precondición; `downgrade "0009"`, fotografía C `== A` y `partida_concepto` ausente; `upgrade "0010"`, fotografía `== B`. Versión correcta tras cada paso | feliz | `CA-8` esc. 1 | — |
| TC-19 | `test_tkt072_ca08_la_subida_se_niega_con_conceptos_escritos`, parametrizado: (a) un concepto en `0009`; (b) un concepto y su copia en un `BORRADOR`. `upgrade "0010"` lanza `DBAPIError` con `sqlstate == "P0001"`, texto con «La subida de 0010 se niega», `PA-T72.8` y las tablas con filas (en (a) `concepto` y no `linea_base_concepto`; en (b) las dos). La versión sigue en `0009`, la fotografía y las filas, texto a texto, no cambian | **rechazo** | `CA-8` esc. 2 | — |
| TC-20 | `test_tkt072_ca08_la_bajada_se_niega_con_datos_escritos`, parametrizado sobre `base_de_prueba` (cabeza): (a) una aparición, `downgrade "0009"`; (b) `linea_base_con_copias(estado="CONGELADA")`, `downgrade "0006"`; (c) solo un concepto, `downgrade "0009"` (`P-1`). `DBAPIError` con `sqlstate == "P0001"`, texto con «La bajada de 0010 se niega», `PA-T72.7` y las tablas con filas (en (a) y (b) `partida_concepto` y `concepto`; en (c) solo `concepto`). En (b) el código no es `IN001`: la guarda de `0010` corre antes que la de `0007`. La versión sigue en `0010`, la fotografía y las filas no cambian | **rechazo** | `CA-8` esc. 3 | — |
| TC-21 | `test_tkt072_ca08_la_guarda_toma_el_bloqueo_antes_de_comprobar`, parametrizado: **subida** (base en `0009`; la sesión A, de aplicación y sin confirmar, escribe un concepto con `concepto_anterior_a_0010(conexion=A)`; un hilo ejecuta `upgrade "0010"`) y **bajada** (cabeza; A escribe concepto y aparición con `conexion=A`; el hilo ejecuta `downgrade "0009"`). El hilo queda esperando a A (`pg_stat_activity` y `pg_blocking_pids`, con `esperar_hasta`, sin espera fija); cuando A confirma, la migración falla con `P0001` y el texto de su guarda; la versión no cambia y la fila de A sigue, con sus columnas. Sin el `LOCK`, la comprobación vería la instantánea vacía y el `DROP` posterior borraría el dato recién confirmado | concurrencia y **rechazo** | `CA-8` esc. 2 y 3 | — |
| TC-22 | `test_tkt072_car3_la_preparacion_guarda_una_entrada_por_fila`: libro sintético (abajo) con `P-001` en `ZONA A` y en `ZONA B`, analizado con `iniciar_analisis`, `analizar_contenido` y `registrar_resultado`, como `_flujo_analisis` de `test_tkt015_analisis.py`. La importación queda `VALIDADO`, `preparacion["formato"] == FORMATO_PREPARACION`, `len(preparacion["conceptos"]) == 2`, sus `fila` son `[9, 12]`, los dos con `codigo == "P-001"` y con áreas distintas en `ruta`. `concepto` y `partida_concepto` siguen vacías | regresión | `CA-R3` | — |
| TC-23 | Documentación coherente: los tres comandos de A4 en verde; `docs/03` muestra `concepto` sin cantidad ni precio y `partida_concepto` con ellos en el diagrama y en §13; el glosario define *Concepto* sin cantidad y *Concepto de partida* con ella; las specs de TKT-013 y TKT-015 marcan `PA-T1` resuelta | regresión | `CA-9` | — |
| TC-24 | Regresión sin test nuevo: las suites de TKT-010, TKT-011 y TKT-013 a TKT-016 en verde, y `git diff --stat Produccion -- backend/tests` solo muestra `conftest.py`, los tres archivos de TKT-011 de la tabla «Pruebas y fábricas» y los tres archivos nuevos | regresión | `CA-R2` | — |

**Concurrencia:** `TC-21`. No hay bloqueo pesimista de negocio: el único bloqueo es el de las guardas.

### Libro sintético de `TC-22`

Con la fixture `libro_catalogo`. La hoja `CATALOGO` (constante `HOJA_CATALOGO_SINTETICO` de `herramientas/soporte_tkt015.py`) va primero y después la hoja `APU P-001`, escrita con `escribir_hoja_apu_sintetica(libro, "APU P-001", codigo="P-001")` de `herramientas/soporte_tkt014.py`, igual que `libro_sintetico`.

| Fila | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 1 a 3 | vacías | | | | | |
| 4 | `Código` | `DESCRIPCION` | `Unidad` | `Cantidad` | `P.U.` | `IMPORTE` |
| 5 | | `RAIZ SINTETICA` | | | | |
| 6 | | `NIVEL 1` | | | | |
| 7 | | `ZONA A` | | | | |
| 8 | | `PARTIDA MUROS` | | | | |
| 9 | `P-001` | `CONCEPTO P-001` | `M2` | `1` | `10` | `10` |
| 10 | | `ZONA B` | | | | |
| 11 | | `PARTIDA MUROS` | | | | |
| 12 | `P-001` | `CONCEPTO P-001` | `M2` | `2` | `10` | `20` |

Las filas 10 y 11 forman una corrida posterior de dos filas, que el lector alinea a la partida y reemplaza área y partida (`lectura_catalogo.py`, líneas 362 a 371; `E-4`).

### Mutación

Ruta crítica de congelado y de datos en migración. La hace `tester-backend` en A5, sobre `v0010`, revirtiendo cada mutante. Se documenta en `impl.md` qué se mutó y qué test cayó.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| M-1 | Quitar `uq_partida_concepto_concepto_id_partida_id` | `TC-05` y `TC-17` |
| M-2 | Añadir a la subida `DROP TRIGGER trg_linea_base_concepto_inmutable ON linea_base_concepto` | `TC-11` y `TC-17` |
| M-3 | Quitar la guarda de la subida | `TC-19` |
| M-4 | Quitar la guarda de la bajada | `TC-20` |
| M-5 | `ON DELETE CASCADE` en `fk_partida_concepto_concepto_id`; después, en `fk_partida_concepto_partida_id` | `TC-09` (el parámetro de cada una) y `TC-17` |
| M-6 | Añadir `GRANT ALL ON partida_concepto TO cimenta_aplicacion` | `TC-14` |
| M-7 | Añadir `GRANT INSERT ON partida_concepto TO cimenta_lectura` | `TC-14` y `TC-15` |
| M-8 | Quitar el `LOCK TABLE` de la guarda de la subida; después, el de la bajada | `TC-21` (el parámetro de cada una) |
| M-9 | En la bajada, reponer las cuatro columnas de `concepto` con `ADD COLUMN` en lugar de recrear la tabla | `TC-18` |
| M-10 | Quitar `ck_partida_concepto_importe_no_negativo` | `TC-07` (parámetro `importe`) y `TC-17` |
| M-11 | Quitar el paso 15 de la subida (`fk_linea_base_concepto_partida_concepto_id`) | `TC-13` y `TC-17` |
| M-12 | En `backend/cimenta/presupuesto/infraestructura/preparacion_json.py`, línea 144, deduplicar los conceptos por código: `[_concepto_a_json(c) for c in {c.codigo: c for c in preparacion.conceptos}.values()]` | `TC-22` (lo hace A3) |

## Impacto

Análisis del arquitecto, para que `revisor-impacto` lo contraste en el gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `concepto` pierde partida, cantidad, precio e importe | TKT-017, que materializa: escribirá un `concepto` por código y obra y un `partida_concepto` por fila del catálogo. `apu.concepto_id` sigue colgando del concepto. TKT-018 decide qué cuenta `ResumenImportacion.conceptos` | Que TKT-017 escriba una fila de `concepto` por fila del Excel y choque con el invariante 13 | El ADR y `delta.md` lo dicen; la ficha de TKT-017 en `docs/05` cita el concepto de partida |
| `linea_base_concepto.concepto_id` → `partida_concepto_id` | TKT-017 (copia al congelar), `ConceptoLineaBase` del borrador OpenAPI (no cambia: ya devuelve una fila por aparición con nivel y área), `alcance_destajo` de TKT-047 | Que TKT-017 copie apuntando al concepto | El nombre de la columna lo impide: no existe `concepto_id` en la copia |
| Guardas de `0010` | Despliegue en el entorno `test` de la VPS (`PA-T72.8`) y cualquier bajada desde la cabeza con datos | Si hay filas, la migración se detiene | Es el comportamiento decidido. `/sdd-desplegar` comprueba antes que `concepto` y `linea_base_concepto` estén vacías (ticket futuro sugerido en `_index.md`) |
| Fábricas de `conftest.py` | Toda prueba que llama a `concepto`, `copia_concepto` o `linea_base_con_copias` (inventariadas con `grep`: `test_tkt011_estructura.py`, `test_tkt011_linea_base.py`, `test_tkt011_migracion_linea_base.py`, `test_tkt011_permisos.py`, `test_tkt011_importacion.py`) | Una llamada con `partida_id` o importes en `concepto()` | `mypy` falla por argumento inesperado; la tabla «Pruebas y fábricas» las lista todas |
| `TC-48`, `TC-49` y `CA-19` esc. 3 de TKT-011 | La guarda de la bajada de `0007` | Desde la cabeza, la guarda de `0010` intercepta antes y esas pruebas dejarían de probar `0007` | Pasan a una base en `0009` (`P-6`); `TC-20` (b) prueba la interceptación desde la cabeza |
| `tools/publicar_revision.py`, `CITA_VALIDA` (línea 35) | La revisión automatizada de PR, hoy inactiva | Descartaría una cita «invariante» con el número 39 por fuera de rango | `P-4` |

**Fronteras entre módulos:** No. Todo queda en `presupuesto`; las claves foráneas nuevas apuntan a `concepto`, `partida` y `partida_concepto`, del mismo módulo.

## Documentación afectada

| Documento | Qué cambia | Fila |
|---|---|---|
| `docs/03-modelo-datos.md` §4.1, diagrama (líneas 115 y 169 a 179) | `PARTIDA \|\|--o{ CONCEPTO` se sustituye por `OBRA \|\|--o{ CONCEPTO : "cataloga"`, `CONCEPTO \|\|--o{ PARTIDA_CONCEPTO : "aparece como"` y `PARTIDA \|\|--o{ PARTIDA_CONCEPTO : "contiene"`. `CONCEPTO` queda con `id`, `obra_id` (sin «denormalizado»), `codigo` («620001 · único por obra · invariante 13»), `descripcion` y `unidad`. Entidad nueva `PARTIDA_CONCEPTO`: `id`, `concepto_id`, `partida_id` («UNIQUE con concepto_id · invariante número 39»), `cantidad`, `precio_unitario` («por área: 620040-A vale 414.93 y 428.19 en ENITI»), `importe` («cantidad × P.U.; el motor no lo verifica») | A4 |
| `docs/03-modelo-datos.md` §4.1, «El código de concepto no es global» (línea 229) | Añade que dentro de la obra el código es el **concepto** y cada aparición en la partida de un área es un **concepto de partida** con su cantidad, su precio y su importe, con la medición de los dos Excel y el enlace al ADR nuevo | A4 |
| `docs/03-modelo-datos.md` §4.1, «`concepto.obra_id` está denormalizado» (línea 233) | Se reescribe: `obra_id` ya no es una copia, es la obra del concepto. Lo que el motor no cruza es que la partida de cada concepto de partida pertenezca a esa obra; lo sostiene el caso de uso de TKT-017, y la restricción queda como ticket futuro junto con la unicidad del APU (`PA-T3` de TKT-011). La frase «Tres decisiones» (línea 227) no cambia de número | A4 |
| `docs/03-modelo-datos.md` §4.2, diagrama (líneas 244 y 263 a 271) | Relación `PARTIDA_CONCEPTO \|\|--o{ LINEA_BASE_CONCEPTO : "se copia en"`; el atributo `uuid concepto_id FK` pasa a `uuid partida_concepto_id FK "la aparición: alcanza partida, área y nivel"` | A4 |
| `docs/03-modelo-datos.md` §4.2, tabla de controles (línea 303) | «`Σ cantidad_concepto × rendimiento` de todos los conceptos del tipo de partida» pasa a «`Σ cantidad × rendimiento` de todos los conceptos de partida del tipo», y «ponderados por cantidad de concepto», a «ponderados por la cantidad de cada concepto de partida» | A4 |
| `docs/03-modelo-datos.md` §13, filas 8, 13 y 14 (líneas 1150, 1155 y 1156) | 8: añade que en el catálogo la cantidad, el precio unitario y el importe viven en `partida_concepto`. 13: el mecanismo nombra la tabla, `UNIQUE (obra_id, codigo)` sobre `concepto`, y aclara que el mismo código en otra área es otro concepto de partida (invariante número 39). 14: «sus copias (`linea_base_concepto`, que apunta al concepto de partida, y `explosion_presupuesto`)» | A4 |
| `docs/03-modelo-datos.md` §13, fila nueva tras la 38 (línea 1180) | `\| 39 \| Un concepto aparece a lo sumo una vez en cada partida \| UNIQUE (concepto_id, partida_id) sobre partida_concepto (uq_partida_concepto_concepto_id_partida_id) \| — \|`, con el formato de código de las demás filas | A4 |
| `docs/glosario.md`, *Catálogo de conceptos* (línea 21) | «con cantidad, precio unitario e importe por concepto» pasa a «con la cantidad, el precio unitario y el importe de cada concepto en cada partida (*concepto de partida*)» | A4 |
| `docs/glosario.md`, *Concepto* (líneas 39 y 41) | El concepto lleva código, descripción y unidad, y es único por obra; el ejemplo conserva código, texto y unidad y pierde cantidad y P.U. El segundo párrafo añade que dentro de una obra el mismo código aparece en muchas áreas, y que el precio puede cambiar también por área (`620040-A` en ENITI) | A4 |
| `docs/glosario.md`, entrada nueva *Concepto de partida* tras *Concepto* | La aparición de un concepto en la partida de un área, con su cantidad, su precio unitario y su importe; un concepto aparece a lo sumo una vez por partida; en el esquema, `partida_concepto`; es lo que copia la línea base al congelar | A4 |
| `docs/adr/20261105-concepto-unico-y-concepto-de-partida.md` (nuevo) | MADR, ver «¿Merece ADR?» | A4 |
| `docs/adr/README.md`, índice (tras la línea 60) | Fila nueva con fecha `2026-11-05`, título «El concepto es único por obra; su cantidad y su precio viven en el concepto de partida» enlazado a `20261105-concepto-unico-y-concepto-de-partida.md`, estado `Aceptado` y la nota «presupuesto · TKT-072 · completa la copia física», con «la copia física» enlazada a `20260918-snapshot-linea-base.md` | A4 |
| `CLAUDE.md`, líneas 12, 14 y 140 | «38 invariantes» → «39 invariantes» (líneas 12 y 140); «38 decisiones» → «39 decisiones» (línea 14). Autorizado por la persona dueña el 2026-11-05 | A4 |
| `README.md`, líneas 30, 258 y 264 | «38 ADRs» → «39 ADRs»; «Invariantes declarados en base de datos \| 38» → «39»; «Decisiones de arquitectura (ADR) \| 38» → «39» | A4 |
| `llms.txt`, líneas 18 y 27 | «38 invariantes» → «39 invariantes»; «38 ADRs» → «39 ADRs» | A4 |
| `docs/04-historias-usuario.md`, línea 505 (tablas de HDU-001) | Añade `partida_concepto` tras `concepto` | A4 |
| `docs/05-tickets-trabajo.md`, ficha de TKT-017 (líneas 772 y 773) | «una copia que apunta a una línea base o a un concepto inexistente» → «… o a un concepto de partida inexistente»; «la suma de los importes de los conceptos que se materializan» → «… de los conceptos de partida que se materializan» | A4 |
| `docs/05-tickets-trabajo.md`, ficha de TKT-047 (línea 1803) | «sumando los conceptos en `M2`» → «sumando los conceptos de partida en `M2`» | A4 |
| `docs/03-modelo-datos.md`, línea 70 (jerarquía) y línea 657 (`alcance_destajo`) | La jerarquía «obra › nivel › area › partida › concepto» precisa que en la partida está el concepto de partida; «sumando los conceptos medibles en `M2` de las partidas» → «sumando los conceptos de partida medibles en `M2`» | A4 |
| `backend/tests/test_tkt011_estructura.py`, docstring de `TC-13` (línea 698) | «diecisiete columnas» → «catorce», junto con el comentario de la línea 651 | A1 |
| `tools/publicar_revision.py` (línea 35) y `tools/tests/test_publicar_revision.py` (líneas 16, 124, 136 y 158) | Si se aprueba `P-4`: el rango llega a 39, el docstring de `TC62-21` y el comentario «el invariante 38 son los topes» pasan a 39, y la cita inválida pasa a «invariante» con el número 40 | A4 |
| `sdd/tickets/tkt-013/spec.md`, `PA-T1` (línea 320) | Estado: «Resuelta el 2026-11-05 por TKT-072: concepto único por obra y concepto de partida por aparición» | A4 |
| `sdd/tickets/tkt-015/spec.md`, `PA-15.15` (línea 420) | Estado: «Resuelta el 2026-11-05: `PA-T1` la cierra TKT-072» | A4 |

No cambian: `docs/api/openapi.yaml` (non-goal), `docs/02-arquitectura.md` (línea 390: los privilegios por omisión ya describen `partida_concepto`), `docs/adr/20260918-snapshot-linea-base.md` (un ADR aceptado no se reescribe; el nuevo lo completa) y `docs/03-modelo-datos.md` §16 (la fila de `RN-01` nombra tablas que no cambian). Las demás menciones de «38 invariantes» o «treinta y ocho» (`sdd/metodologia.md:94`, `sdd/00-propuesta-toolkit.md:17` y `:259`, `docs/06-stack-tecnologico.md:560`, cinco agentes de `.claude/agents/`, tres skills de `.claude/skills/` y sus copias generadas en `.cursor/agents/`) dependen de `P-3`.

## ¿Merece ADR?

**Sí.** Quien llegue y vea `concepto` sin cantidad y una tabla `partida_concepto` aparte se preguntará por qué no se amplió la unicidad o se fusionaron las filas, y hubo cuatro opciones descartadas por la persona dueña el 2026-11-05. Hoy viven solo en `spec.md` y `_index.md`, que son artefactos de ticket.

`docs/adr/20261105-concepto-unico-y-concepto-de-partida.md`, formato MADR, con la estructura de `template.md`:

- **Contexto y problema:** el invariante 13 y los dos Excel reales (ENITI, 5,028 filas con 36 códigos; Union Square, 4,281 con 31), ninguno confirmable; `620040-A` con dos precios en ENITI; la copia congelada necesita el área para TKT-047.
- **Opciones consideradas:** A, la ruta en la unicidad (`UNIQUE (obra_id, codigo, partida_id)` sobre `concepto`), descartada porque vacía el invariante 13, repite descripción y unidad por área y deja un APU por aparición; B, concepto único y concepto de partida, **elegida**; C, fusionar las apariciones en un concepto con la cantidad sumada, descartada porque pierde el área que necesitan la copia congelada y el alcance de destajo; precio unitario en el concepto, descartado por `620040-A`; copia congelada que apunta al concepto con el área copiada en texto, descartada porque duplica la jerarquía en la copia y la persona dueña eligió apuntar a la aparición.
- **Decisión:** las seis decisiones del 2026-11-05 de `_index.md`, el invariante número 39, y que las dos direcciones de la migración se niegan con datos.
- **Consecuencias:** TKT-017 escribe dos tablas; `apu` sigue en el concepto y su unicidad sigue fuera (`PA-T3` de TKT-011); la coherencia entre la obra del concepto y la de su partida la sostiene el caso de uso; el importe no se verifica contra cantidad por precio (`PA-T72.10`).

Coste: el ADR mueve el conteo de decisiones de 38 a 39 en `CLAUDE.md`, `README.md` y `llms.txt`, que exige `tools/tests/test_definicion_revision.py`.

## Experimentos

| # | Qué mide | Cómo | Resultado esperado | Si no coincide |
|---|---|---|---|---|
| E-1 | Que las herramientas y la suite pasan antes del cambio, y que la cabeza es `0009` **(sin ejecutar)** | Fila A0 | Todo en verde; `uv run alembic heads` da `0009 (head)` | Si hay otra revisión posterior, el diseño cambia `down_revision` y los nombres `"0009"` de las pruebas antes de A1, y se anota en `impl.md`; si falla una herramienta, `/sdd-escalar` |
| E-2 | Que borrar un padre con hijos y `ON DELETE RESTRICT` responde `23001`, no `23503` **(sin ejecutar aquí; comprobado en TKT-011a, `TC-42`, y en `conv-sql-postgres` §9)** | `TC-09` en A1 | `RestrictViolation`, `23001` | Si fuera `23503`, `TC-09` se ajusta al motor y `P-2` se retira |
| E-3 | Que `RENAME COLUMN` conserva el disparador y la revocación, y que la bajada que recrea `concepto` deja la fotografía de `0009` **(sin ejecutar)** | `TC-11`, `TC-12`, `TC-14` y `TC-18` en A1 | Los cuatro en verde | Si la fotografía difiere, el desarrollador compara las dos y ajusta la bajada, nunca la fotografía; si persiste, `/sdd-escalar` |
| E-4 | Que el lector asigna `ZONA B` a la fila 12 del libro de `TC-22` y que la importación queda `VALIDADO` **(sin ejecutar; leído en `lectura_catalogo.py`, líneas 362 a 371)** | `TC-22` en A3 | Dos entradas con áreas distintas | El tester ajusta el libro, nunca el lector, y lo anota en `impl.md` |
| E-5 | Que los privilegios por omisión de `0001` dan a `partida_concepto` exactamente lo que pide `M4` **(sin ejecutar; leído en `v0001`, líneas 45 y 46)** | `TC-14` en A1 | Aplicación `SELECT, INSERT, UPDATE, DELETE`; lectura `SELECT` | Si difiere, se escribe el `GRANT` o el `REVOKE` explícito y se anota |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Desde la cabeza, la guarda de `0010` intercepta la bajada que `TC-48`, `TC-49` y `CA-19` esc. 3 de TKT-011 hacen hasta `0006` con copias escritas: dejarían de probar la guarda de `0007` | Se mueven a una base en `0009` sembrada con el esquema anterior, y `TC-20` (b) prueba la interceptación desde la cabeza. No es un ajuste por «nombrar una columna movida», así que va a `P-6` |
| 2 | Alta | Con conceptos escritos y ninguna aparición, la bajada que recrea `concepto` borraría esos conceptos en silencio (o fallaría con un `23503` opaco si tienen APU); con `ADD COLUMN … NOT NULL` fallaría con `23502` y el catálogo no quedaría idéntico | La guarda de la bajada cuenta también `concepto`. Amplía la letra de `PA-T72.7` sin contradecirla: `P-1` |
| 3 | Media | `CA-5` dice `23503` para borrar un padre con hijos, y el motor responde `23001` con `ON DELETE RESTRICT` | `TC-09` afirma `23001`; corregir la spec es `P-2`. No cambia ninguna decisión: la clave sigue sin cascada |
| 4 | Media | `DROP COLUMN` deja huecos en `ordinal_position`, y una bajada con `ADD COLUMN` no reproduce la fotografía de `0009` | La bajada recrea `concepto` con el texto de `0006` y repone `fk_apu_concepto_id`; `TC-18` y `M-9` |
| 5 | Media | Sin bloqueo, la guarda comprueba sobre una instantánea y el `DROP` posterior espera a una sesión que confirma un dato recién escrito: se perdería sin error | `LOCK TABLE` dentro del bloque y antes de comprobar, como `0007`; `TC-21` y `M-8` |
| 6 | Media | Un concepto de partida podría apuntar a una partida de otra obra que la de su concepto | Fuera de alcance por la spec (`Won't`: la coherencia de `concepto.obra_id` en el motor). Queda en el modelo de datos y en el ADR como responsabilidad de TKT-017 |
| 7 | Baja | Sin índice sobre `linea_base_concepto.partida_concepto_id`, borrar una aparición recorre la copia entera para comprobar la clave | Igual que hoy con `concepto_id`, y ninguna ruta borra apariciones. Queda en riesgos |
| 8 | Baja | `CA-R3` nace en verde, porque la preparación no cambia | Es una regresión; `M-12` demuestra que la prueba puede fallar |
| 9 | Media | El ticket ronda las 1,225 líneas | `P-5`, sin partición viable |
| 10 | Baja | El conteo «38» sobrevive en agentes, skills, metodología y en el filtro de la revisión automatizada | `P-3` y `P-4`; la persona dueña autorizó solo `CLAUDE.md`, `README.md` y `llms.txt` |
| 11 | Baja | `revisor-impacto`: la ficha de TKT-047, dos pasajes de `docs/03` (líneas 70 y 657), el docstring de `TC-13` y el docstring y el comentario de `test_publicar_revision.py` siguen nombrando el concepto con su cantidad o el tope 38 | Añadidos a «Documentación afectada» con su línea y su fila. Confirmó además, con `lint-imports` en verde (16 contratos), que no hay frontera cruzada, que los privilegios por omisión de `0001` cubren `partida_concepto` porque `env.py` exige `cimenta_migracion`, y que la bajada repone todo lo que depende de `concepto` |
| 12 | Baja | `0006` escribe el `GRANT` explícito a la aplicación aunque sea redundante, para dejarlo escrito; `0010` confía en los privilegios por omisión | Se mantiene el diseño, como `0007` y `0009`, que tampoco escriben `GRANT`; `TC-14` y `E-5` lo comprueban, y el docstring de la migración dice de dónde salen los privilegios |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| El entorno `test` de la VPS tiene filas en `concepto` o en `linea_base_concepto` (`PA-T72.8`) | Baja | Medio: el despliegue se detiene | Es lo decidido; la guarda lo dice con su motivo. Ticket futuro sugerido: comprobarlo antes de desplegar |
| TKT-017 materializa una fila de `concepto` por fila del Excel | Media | Alto: el invariante 13 rechaza la confirmación | El ADR, el glosario y `delta.md` lo dicen; la columna `partida_concepto_id` de la copia obliga a escribir la aparición |
| La fila A1 es grande para un solo despacho | Media | Bajo: más intentos | Subpasos ordenados en la fila; si `sonnet` no cierra en dos intentos, `/sdd-escalar` |
| Borrar una aparición recorre `linea_base_concepto` sin índice | Baja | Bajo | Nadie borra apariciones hasta TKT-017; si aparece en `EXPLAIN`, se añade el índice en su ticket |
| Una prueba existente no inventariada nombra `concepto.partida_id` o `linea_base_concepto.concepto_id` | Baja | Bajo | La verificación de A1 corre las suites completas de TKT-010 a TKT-016; `mypy` detecta argumentos de fábrica que ya no existen |

## Preguntas para el gate

Cada una con su recomendación. Ninguna reabre una decisión de la spec.

| # | Pregunta | Opciones | Recomendación |
|---|---|---|---|
| P-1 | `PA-T72.7` dice que la bajada se niega si hay filas en `partida_concepto`. ¿Se niega también si hay conceptos sin ninguna aparición? | **A.** La guarda cuenta `partida_concepto` y `concepto`. **B.** Solo `partida_concepto`, como dice la letra: la bajada recrea `concepto` y borra en silencio los conceptos sin aparición, o falla con un `23503` opaco si alguno tiene APU | **A.** El esquema de `0009` no puede guardar un concepto sin partida; B pierde datos sin aviso. Si se elige B, la bajada no puede recrear `concepto` sin perderlos, y `TC-18` y `TC-20` (c) se rediseñan antes de A1 |
| P-2 | `CA-5` pide `23503` al borrar un concepto o una partida con apariciones, pero con `ON DELETE RESTRICT` el motor responde `23001` (`conv-sql-postgres` §9, `TC-42` de TKT-011a). ¿Se corrige la spec? | Corregir `CA-5` a `23001` · cambiar las dos claves a `NO ACTION`, que sí responde `23503` | **Corregir `CA-5`.** Todas las claves del módulo son `RESTRICT` (`PA-T8` de TKT-011), y TKT-017 ya traduce `23001` |
| P-3 | Además de `CLAUDE.md`, `README.md` y `llms.txt`, el conteo «38 invariantes» o «treinta y ocho» aparece en `sdd/metodologia.md`, `sdd/00-propuesta-toolkit.md`, `docs/06-stack-tecnologico.md`, cinco agentes y tres skills (más sus copias de `.cursor/agents/`). ¿Se actualizan en este cambio? | Sí, en A4, regenerando `.cursor/agents/` con `python tools/agentes_cursor.py --generar` · no, se dejan para un cambio aparte | **Sí, en A4.** Son cifras que leen los agentes al diseñar y probar; dejarlas en 38 contradice el modelo de datos. Añade ~15 líneas |
| P-4 | `tools/publicar_revision.py` acepta citas «invariante 1» a «invariante 38» (línea 35), y su prueba usa «invariante» con el número 39 como cita inválida. ¿Se amplía el rango a 39 en este ticket? | Sí, en A4, con la prueba (`invariante número 39` válida, `invariante número 40` inválida) · no, ticket aparte | **Sí.** Es una línea y su prueba; sin ella, la revisión automatizada descartará cualquier hallazgo que cite el invariante nuevo |
| P-5 | El ticket ronda las 1,225 líneas (~165 de producción). ¿Se acepta sin partir? | Un solo ticket · partir | **Un solo ticket.** Ver «Tamaño y partición»: ninguna partición deja la suite en verde y la documentación en el mismo cambio |
| P-6 | `TC-48`, `TC-49` y `CA-19` esc. 3 de TKT-011 dejan de bajar desde la cabeza y pasan a una base en `0009`. `CA-R2` solo autoriza ajustes por nombrar columnas o tablas movidas. ¿Se acepta este ajuste? | Aceptar · dejar esas pruebas desde la cabeza y aceptar que fallen por la guarda de `0010` | **Aceptar.** Siguen probando lo mismo, la guarda de `0007`, que es la única que pueden probar; la interceptación desde la cabeza la prueba `TC-20` (b) |
