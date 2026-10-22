# Delta · TKT-007 · Bitácora transversal de solo-anexado

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `v0003`: el tipo `accion_bitacora` con los 22 verbos del borrador, la tabla `bitacora` (el `id` lo genera la aplicación, `ocurrido_en` sin `DEFAULT`, `datos_antes` y `datos_despues` en `JSONB`), la clave foránea `fk_bitacora_usuario_id`, la restricción `ck_bitacora_regla_negocio_formato`, los índices `ix_bitacora_obra_id_ocurrido_en` e `ix_bitacora_regla_negocio` (parcial), y la revocación de `UPDATE`, `DELETE` y `TRUNCATE` al rol de aplicación. La bajada se niega si la tabla tiene asientos | `backend/migraciones/versions/v0003_auditoria_bitacora.py` | Que exista la bitácora de `RN-04` y que su inmutabilidad (invariante 10) sea un permiso del motor y no una disciplina del código |
| Dominio de la bitácora: `AccionBitacora`, `DefectoDeCampo`, `Asiento`, `ResultadoAsiento`, `regla_bien_formada` y `revisar_asiento`, que devuelve el asiento normalizado o todos sus defectos y nunca lanza; rechaza `float` y `Decimal` dentro de `datos_*` (regla 1), los UUID los convierte en cadena y rechaza el carácter NUL en cualquier texto. En `consulta.py`, `revisar_filtros` con los límites de paginación y de rango | `backend/cimenta/auditoria/dominio/asiento.py` y `consulta.py` | Decidir la forma de un asiento y de una consulta sin base de datos y sin importar `datetime` ni `contrato_error` (ADR-021) |
| Modelo ORM `FilaBitacora` con su `Base` propia, y repositorio con `insertar_asiento`, `contar_asientos` y `leer_asientos`. El `INSERT` se ejecuta al instante, no al confirmar; la lectura devuelve filas y no entidades del ORM | `backend/cimenta/auditoria/infraestructura/modelos.py` y `repositorio.py` | Que el error de la clave foránea aparezca en la llamada a `asentar` y que un asiento leído no pueda acabar en un `UPDATE` |
| Casos de uso `asentar`, `asentar_denegacion` y `consultar_bitacora`, con `AsientoLeido` y `PaginaBitacora`. Ninguno abre ni cierra transacción: escriben o leen en la `Session` que recibe del llamador. Un asiento o un filtro mal formado lanza `ValidacionRechazada` de TKT-005 antes de emitir ninguna sentencia | `backend/cimenta/auditoria/aplicacion/asentar.py` y `consulta.py` | Que cualquier módulo asiente en la misma transacción que su cambio (regla 8) y que TKT-027 tenga la consulta lista para montarle la ruta |
| Interfaz publicada con seis nombres: `AccionBitacora`, `AsientoLeido`, `PaginaBitacora`, `asentar`, `asentar_denegacion` y `consultar_bitacora` | `backend/cimenta/auditoria/interfaz.py` | Lo único que otro módulo puede importar de `auditoria` (regla 3) |
| `url_aplicacion()` y `crear_motor_aplicacion()`, con las firmas que ya usa el diseño de TKT-006 | `backend/herramientas/conexion.py` | El motor con el rol de aplicación, que la aplicación y las pruebas de permisos necesitan |
| *Fixtures* `motor_aplicacion`, `sesion_bd` y `guarda_de_aplicacion`, ninguna `autouse` | `backend/tests/conftest.py` | Probar con el rol de aplicación y no con el propietario (convención de `conv-pruebas`) |
| Siete archivos de pruebas con 162 casos al cerrar `/sdd-ejecutar` y 16 más en el ciclo de corrección de `/sdd-revisar` (diez parámetros de NUL en texto, uno que acumula NUL en varios campos y uno de control sin NUL en `dominio`, y cuatro parámetros de NUL en `asiento`) | `backend/tests/test_tkt007_esquema.py`, `_motor.py`, `_dominio.py`, `_dominio_consulta.py`, `_asiento.py`, `_fronteras.py`, `_consulta.py` | Cada garantía se vio fallar: 28 mutantes de uno en uno, sin sobrevivientes, con el SHA-256 de cada archivo restaurado |
| Excepción a la regla de claves foráneas del modelo de datos y párrafos de `DENEGAR`, de `ocurrido_en` y de la bajada | `docs/03-modelo-datos.md` §2 y §10 | Dejar escritos el porqué de la clave foránea a `usuario`, a quién se atribuye un `403` sin recurso y cómo se comporta la bajada |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Diseño de TKT-006 (el contrato C-1, la decisión D-3, la escalera, las filas 3 y 4, TC-19, TC-62, MT-21, `PA-T7` y los riesgos) | `sdd/tickets/tkt-006/design.md`, `spec.md` y `_index.md` | Un `403` sin recurso se atribuía a la sesión y TKT-006 construía `url_aplicacion` y el motor → se atribuye al usuario (`entidad_tipo` igual a `usuario`, `entidad_id` igual a su `usuario_id`), sin correlación en `datos`, y `url_aplicacion`, `crear_motor_aplicacion` y `motor_aplicacion` los entrega TKT-007. **Es una enmienda de un diseño ya aprobado por el usuario** |
| Cómo se protege la bitácora | `.claude/skills/conv-sql-postgres/SKILL.md` §1 y `.claude/agents/desarrollador-sql.md` | «Disparador que rechaza `UPDATE` y `DELETE`» → «sin `UPDATE`, `DELETE` ni `TRUNCATE` para el rol de aplicación (invariante 10, TKT-007)». `sdd/00-propuesta-toolkit.md` conserva la frase original con la nota «histórico» |
| Cómo se asienta | `.claude/skills/conv-backend-fastapi/SKILL.md` §2 | Solo «escribe la bitácora en la misma transacción» → además nombra `asentar(sesion_bd, ...)` de la interfaz, que nunca confirma, y `asentar_denegacion` para un `403` autenticado |
| Criterios de TKT-007 y TKT-027 | `docs/05-tickets-trabajo.md` | `DENEGAR` sin dueño ni transacción dicha → servicio aparte, atribuido al usuario y en transacción que abre quien llama. La consulta, sin ruta HTTP. TKT-027 «depende de» TKT-025 → también TKT-006 y TKT-007, y convierte el `usuario_id` en `UsuarioResumen` |
| `mypy` | `backend/pyproject.toml` | Override estricto de `contrato_error.*` y `servidor.*` → también `cimenta.auditoria.*`. El override acotado de `arg-type` para `test_tkt007_fronteras` se quitó en la revisión (`F003`) |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| El `DENEGAR` atribuido a la sesión y el `correlacion_id` dentro de `datos` | Diseño de TKT-006 | Todavía no existía código de TKT-006. El identificador de la sesión es la credencial de la cookie y el rol de lectura lee la bitácora (invariante 21); la correlación va al registro técnico (especificación de la API §2.7) |
| La construcción de `url_aplicacion` y `crear_motor_aplicacion` dentro de TKT-006, y su caso TC-19 | Diseño de TKT-006 | Los entrega este ticket; el caso queda «Retirado» porque lo cubre TC-18 de TKT-007 |

## Comportamiento observable nuevo

Un integrador, es decir, el desarrollador de otro módulo, puede ahora:

- **Asentar un cambio** con `asentar(sesion_bd, accion=…, entidad_tipo=…, entidad_id=…, usuario_id=…, ocurrido_en=…)` desde `cimenta.auditoria.interfaz`, dentro de la transacción de su caso de uso. Recibe el `id` del asiento. Si su transacción se deshace, el asiento se deshace con el cambio; `asentar` nunca confirma.
- **Asentar un `403`** con `asentar_denegacion`, atribuido a quien se le denegó. La transacción la abre quien llama, separada de la de la petición. Es la única escritura de la bitácora que no acompaña a un cambio.
- **Consultar la bitácora** con `consultar_bitacora`, filtrada por obra, regla, tipo y identificador de entidad, verbo, usuario y rango (`desde` inclusivo, `hasta` exclusivo), paginada y con el asiento más reciente primero, con desempate por `id`. Devuelve `usuario_id`, no el nombre.
- Un asiento o un filtro mal formado se rechaza con `422` `VALIDACION` y el campo nombrado, antes de emitir ninguna sentencia: verbo fuera de los 22, regla fuera de la forma `RN-` con dos dígitos, UUID mal formado, momento sin zona horaria, un `float` o un `Decimal` dentro de los datos, o un carácter NUL en cualquier texto o clave. Un `usuario_id` que no existe lo rechaza el motor con la clave foránea.
- **La tabla es inmutable por privilegios.** El rol de aplicación solo tiene `SELECT` e `INSERT`: un `UPDATE`, un `DELETE` o un `TRUNCATE` desde la aplicación fallan por permiso. La bajada de la migración se niega con asientos presentes.

No hay ruta HTTP, pantalla ni cambio visible para un usuario final. `GET /api/v1/bitacora` la monta TKT-027.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `cimenta.auditoria.interfaz` | De solo un docstring a seis nombres publicados: `AccionBitacora`, `AsientoLeido`, `PaginaBitacora`, `asentar`, `asentar_denegacion` y `consultar_bitacora` | No: no existía ningún consumidor |
| Endpoints, DTO y `docs/api/openapi.yaml` | Ninguno. El borrador ya declara `AccionBitacora`, `AsientoBitacora` y `ListaBitacora` con `x-tickets` de TKT-007 y TKT-027, y este ticket no monta ruta. **No toca el borrador** | No |
| C-1 de TKT-006, la firma de `asentar_denegacion` | **Enmendado**: `asentar_denegacion(sesion_bd, *, usuario_id, ocurrido_en, motivo, datos) -> uuid.UUID`, sin `entidad_tipo`, `entidad_id` ni correlación. Debe señalarse a la persona que aprueba el PR | Sí, para el diseño de TKT-006, que no se había ejecutado. Su fila 10 compara la firma real con esta |
| Esquema de base de datos | Migración `v0003`: tipo, tabla, restricciones, índices y privilegios. Una sola cabeza de Alembic | No: aditiva. Un usuario con asientos ya no se puede borrar físicamente, que es lo buscado |
| `herramientas/conexion.py` | Dos funciones nuevas, `url_aplicacion` y `crear_motor_aplicacion`; `url_migracion` no cambia | No |
| Contratos de `import-linter` | Ninguno cambia: son 15 antes y después. `auditoria` no importa ningún módulo de `cimenta` | No |
| Variables de entorno | Ninguna | No |

## Decisiones (ADR)

**No se creó ADR.** Se valoró, y la razón del diseño es que no hay una decisión nueva con alternativas descartadas de peso: la inmutabilidad por privilegios la había fijado ya el modelo de datos §13 y la arquitectura §7.2; la clave foránea a `usuario` la decidió el usuario y se documenta como excepción en el modelo §2; la bajada que se niega sigue de que `RN-04` dice «permanente»; y «escribe en la transacción del llamador» es la regla 8 de `CLAUDE.md`. Un recién llegado encuentra el porqué donde lo buscaría. Si en algún momento se añade un disparador además del permiso, entonces sí merece un ADR corto.

### 2026-10-21 — D-6: inmutabilidad por privilegios, no por disparador

**Contexto:** `conv-sql-postgres` y `desarrollador-sql` decían que la bitácora se protege con un disparador que rechaza `UPDATE` y `DELETE`; el modelo de datos §13 y la arquitectura §7.2 dicen que con permisos, y el criterio de TKT-007 pide permisos.
**Opciones consideradas:** solo permisos; permisos más un disparador `trg_bitacora_inmutable` que rechace también al propietario; solo disparador.
**Decisión:** solo permisos para el rol de aplicación, y se corrige la convención hacia lo que ya decidían el modelo y la arquitectura. Es el mismo patrón que `intento_acceso` en `v0001`. El propietario, `cimenta_migracion`, sí puede modificar la tabla: el invariante 10 es un permiso del rol de aplicación.
**Evidencia:** TC-07 a TC-11 de `test_tkt007_esquema.py` (con el rol de aplicación, `UPDATE`, `DELETE` y `TRUNCATE` fallan, y la igualdad exacta de privilegios hace que un cambio sea deliberado) y los mutantes que quitan la revocación.
**Consecuencias:** quien conecte con el propietario puede alterar la bitácora; si se quiere cerrar también esa puerta, hace falta el disparador, con su ADR. El `TRUNCATE` aparece en la revocación aunque hoy ningún privilegio por omisión lo concede (D-7): deja escrita la intención y sobrevive a un cambio de `v0001`.

No se escribió ADR del repositorio.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| PostgreSQL rechaza el carácter NUL en un texto y en un `JSONB`, y lo hace con un error del motor, no con un `422`. Hay que rechazarlo en el dominio, también dentro de claves y de cadenas anidadas. La clave con NUL nombra la ruta del objeto que la contiene, para que el NUL no viaje en el campo del contrato de error. Se busca con `"\x00" in valor` y no con `strip()`, que no lo quita. No se rechaza todo carácter de control: saltos de línea y tabuladores son legítimos | `F001` de la revisión; `test_tkt007_ca05_nul_en_texto_rechazado` (diez parámetros) y su control `test_tkt007_ca05_texto_sin_nul_pasa_aunque_lleve_otros_controles` | Todo texto libre que llegue a una columna `text` o `jsonb`: motivos, notas y descripciones de los tickets que asientan |
| El `id` y el `ocurrido_en` los pone el llamador, no la base: las pruebas controlan el tiempo, el asiento y el cambio comparten el instante de su caso de uso, y una inserción sin momento falla en lugar de tomar otro reloj en silencio. El momento debe llevar zona horaria; uno sin zona se guardaría en la zona de la sesión de PostgreSQL | Decisión D-3; TC-37 y TC-53 | Todo servicio que escriba una marca de tiempo desde un caso de uso |
| Un `403` sin recurso se atribuye al usuario, no a la sesión ni a la correlación. El identificador de la sesión es la credencial de la cookie y el rol de lectura lee la bitácora (invariante 21); exponerlo la dejaría al alcance de quien solo debía leer. La correlación va al registro técnico | Decisión del usuario del 2026-10-21; TC-38 a TC-42 | TKT-006 (`registrar_denegacion`) y cualquier asiento de un rechazo |
| `JSONB` de SQLAlchemy guarda `None` de Python como el JSON `null`, no como `NULL` de SQL, salvo con `none_as_null=True`. Sin la bandera, `datos_antes` de un `DENEGAR` saldría `'null'::jsonb` | Context7; TC-38 comprueba `IS NULL` y el mutante MT-15 quita la bandera | Toda columna `JSONB` anulable |
| Un servicio que escribe sin confirmar se prueba mirando la tabla después de un `rollback`, y se vigila por el árbol sintáctico: ningún `commit`, `rollback`, `begin` ni `flush`. El `INSERT` se ejecuta al instante para que el error de la clave foránea aparezca en la llamada y no al confirmar | TC-33 a TC-35, TC-39 y MT-11 | Todo servicio de escritura que viva dentro de la transacción de otro |
| Un caso que el diseño da por verde o por rojo puede nacer al revés. TC-16 nace en rojo porque exige `0003` en la cadena que baja desde la cabeza y esa cabeza era `0002`; TC-56 nace en verde porque consulta a mano los índices que ya creó la fila 1, y el tester añadió un complemento que repite como `EXPLAIN` la sentencia real y ese sí nació en rojo | `impl.md`, «Ajustes respecto al design» | El diseño debe marcar qué casos nacen en verde y por qué; el ejecutor lo anota en cuanto lo ve |
| Un `ignore` de línea o un `cast` se borra con el test que lo necesita; un override de `mypy` por módulo sobrevive a ese test y deja el módulo entero sin la comprobación. Se aceptó el override al ejecutar y la revisión lo sustituyó | `F003`; `impl.md`, «Fila 4 · verde y refactor» | Todo test que pase argumentos inválidos a propósito bajo `mypy` estricto |
| `datos_antes` y `datos_despues` de un asiento leído son `Mapping`, no `dict`: `dict` es invariante y el test construye el objeto con un `dict[str, str]` | Fila 8, `⚠ Ajustado` | Todo objeto de valor de lectura con campos JSON |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto. Se añadieron a [`_evolucion.md`](../../_evolucion.md) en `/sdd-completar`; esta tabla las resume.

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Siguen faltando `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `auditor-sql`, `meta-sdd` y `desarrollador-aplicacion`. Séptima vez: ya hay doce filas previas con el tema `agente`, ocho sobre agentes ausentes | Alta |
| `comando` | Un ticket posterior enmendó el diseño aprobado de otro (TKT-006). La dependencia oculta la destapó la spec de TKT-006 | Alta |
| `contexto` | El primer intento del arquitecto murió por límite de uso sin escribir nada | Media |
| `comando` | El orden sumó unas 2,180 líneas, más de cinco veces el tope, en dos entregas sobre una sola rama. Cuarta vez | Media |
| `herramienta` | Los finales de línea CRLF y LF siguen siendo fricción: cuarta vez | Media |
| `herramienta` | `verificar_docs.py` marcó como regla inexistente un ejemplo de una regla mal formada y obligó a reescribirlo en prosa | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `pagina` sin tope superior (`F002` de la revisión): un valor gigante llega al motor como `bigint out of range` | El tope es una decisión de contrato del borrador, no del ticket que lo implementa. La decidió el usuario | TKT-027, al montar la ruta |
| Los filtros por `usuario_id`, `entidad_id`, `entidad_tipo` y `accion` no tienen índice; solo los cubren `obra_id` más fecha y `regla_negocio` | Ningún Must lo pide (YAGNI); hay que medir con `EXPLAIN` sobre datos reales | TKT-027 |
| Retención, purga y crecimiento de la bitácora (`PA-T9`): `RN-04` dice «permanente» y la tabla crece sin límite | Es una decisión de negocio que el PRD no tiene | Ticket futuro de retención |
| Asiento del intento rechazado por el motor (`PA-T10`, `HDU-001` esc. 18): necesita un mecanismo fuera de la transacción que se deshace y un verbo que el enum no tiene | Cambia el enum y la política de transacciones | Ticket futuro; el verbo nuevo exige `ALTER TYPE … ADD VALUE` |
| Esquema por acción de `datos_antes` y `datos_despues`, con escala de importes (`PA-T5`) | Hoy los importes viajan como cadena sin cuantizar en este módulo | Ticket futuro, cuando haya consumidores |
| `datos_*` del `JSONB` sin esquema por acción; el rol de lectura conserva `SELECT` sobre toda la tabla (`PA-T4`) | TC-10 lo fija para que un cambio sea deliberado | Revisarlo con TKT-027 |
| El modelo de datos §10 y su invariante 10 aún no mencionan `TRUNCATE` ni `ck_bitacora_regla_negocio_formato` | Fuera de la lista literal del diseño | Primer ticket que toque el modelo de datos |
| `spec.md` de TKT-006 sigue listando en `M11` la URL y el motor como alcance propio, aunque los entrega TKT-007 | La enmienda corrigió `PA-T7` y la tabla de partida, no el `M11` | Corregirlo al abrir `/sdd-ejecutar` de TKT-006 |
| Un `403` con recurso (la auto-resolución de `HDU-003`) quedaría atribuido al usuario con `asentar_denegacion`; no se decidió si se liga a la solicitud con el `asentar` genérico | Lo deciden quienes consumen el servicio | TKT-026 y TKT-027 (el verbo `DENEGAR` con recurso) |
| Un asiento mal formado de un consumidor llega al cliente como `422` sobre un campo que no envió (D-2), y `ocurrido_en` lo pone el llamador sin cota (D-3) | Decisiones aprobadas, con su coste anotado | Los consumidores prueban su propio asiento; sin ticket |
| `MENSAJE_NUL` nombra a PostgreSQL dentro de `dominio/`: es solo texto, pero acopla el mensaje al motor | Bajo | Sin ticket; al tocar el mensaje |
| `count` y página son dos sentencias bajo `READ COMMITTED` y pueden no coincidir si entra un asiento entre ambas (`PA-T7`) | Aceptado; un consumidor que lo necesite abre su transacción en `REPEATABLE READ` | Sin ticket |
| Las entregas A y B viven en una sola rama y un solo commit | Los hunks de `pyproject.toml`, `conftest.py` y la documentación mezclan las dos | Si se quieren dos PR, separarlos al abrirlos |
| `markdownlint-cli2`, `Vale` y `lychee` no se ejecutaron | No están instalados | TKT-009 |

## Pull request

**Título:** `TKT-007 · bitácora transversal de solo-anexado`
**Origen:** `agent`
**Cuerpo:**

Qué: añade la bitácora de `RN-04`. La migración `v0003` crea el tipo `accion_bitacora`, la tabla `bitacora` con su clave foránea a `usuario`, la restricción del formato de la regla y dos índices, y quita `UPDATE`, `DELETE` y `TRUNCATE` al rol de aplicación; su bajada se niega con asientos presentes. `cimenta.auditoria.interfaz` publica `asentar`, `asentar_denegacion`, `consultar_bitacora`, `AccionBitacora`, `AsientoLeido` y `PaginaBitacora`. Los servicios escriben en la transacción del llamador y nunca confirman. Añade `url_aplicacion` y `crear_motor_aplicacion` y tres *fixtures* sin `autouse`.

Por qué: la regla 8 exige que la bitácora se escriba en la misma transacción que el cambio, y TKT-006 y todos los tickets que cambian algo necesitan un servicio para asentar. Sin él, cada ticket inventaría su asiento.

Criterios cubiertos: `CA-1` a `CA-10`, los dos `[S]` (`CA-11` y `CA-12`) y `CA-R1` a `CA-R5` de `sdd/tickets/tkt-007/spec.md`. Suite completa con Docker: 870 pruebas en verde (854 al ejecutar y 16 más tras la revisión), 15 contratos de `import-linter`, `ruff`, `mypy` y `verificar_float` limpios, una sola cabeza de Alembic. 28 mutantes de uno en uno, ninguno sobrevive. Una auditoría de arquitectura con un ciclo de corrección y una pasada independiente con otro; ambas reauditorías `APROBADO`.

**Para quien aprueba, con atención:**
- **Este PR no toca `docs/api/openapi.yaml`, pero enmienda el diseño de TKT-006** (el contrato C-1, la decisión D-3, `PA-T7` y las filas 3 y 4). Un `403` sin recurso se atribuye al usuario y no a la sesión. Lo decidió el usuario el 2026-10-21 y consta en `sdd/tickets/tkt-007/_index.md`.
- La inmutabilidad es un permiso del rol de aplicación, no un disparador (D-6): el propietario puede modificar la tabla. La convención `conv-sql-postgres` se corrigió en este cambio.
- La clave foránea de `bitacora.usuario_id` cruza de módulo; el modelo de datos §2 lo recoge como excepción.
- `auditor-sql`, `revisor-impacto`, `desarrollador-aplicacion`, `auditor-codigo` y `auditor-docs` no existen en este entorno y se sustituyeron.

Cómo verificarlo, con `uv` y Docker instalados:

```bash
cd backend && uv sync --locked
uv run pytest tests/test_tkt007_dominio.py tests/test_tkt007_dominio_consulta.py tests/test_tkt007_fronteras.py   # sin Docker
uv run pytest && uv run ruff check . && uv run mypy . && uv run lint-imports
uv run python -m herramientas.verificar_float
uv run --env-file ../.env alembic heads   # una sola cabeza
cd .. && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en `sdd/tickets/tkt-007/delta.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
