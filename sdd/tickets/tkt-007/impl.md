# Impl · TKT-007 · Bitácora transversal de solo-anexado

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (lo escribe `/sdd-completar`)

## Qué se implementó

Las dos entregas del ticket, A y B, con las diez filas del diseño ejecutadas por el ciclo rojo, verde y refactor.

**Entrega A, tabla y asiento.**

- La migración `v0003_auditoria_bitacora.py` crea el tipo `accion_bitacora` con los 22 verbos, la tabla `bitacora`, sus restricciones nombradas y sus dos índices. Quita `UPDATE`, `DELETE` y `TRUNCATE` al rol de aplicación, y su bajada se niega si hay asientos.
- `url_aplicacion` y `crear_motor_aplicacion` en `herramientas/conexion.py`, más las fixtures `motor_aplicacion`, `sesion_bd` y `guarda_de_aplicacion` en `conftest.py`, ninguna `autouse`.
- El dominio `auditoria/dominio/asiento.py`, puro, que revisa la forma de un asiento y acumula defectos por campo.
- El modelo, el repositorio y `asentar` en `aplicacion/`, que nunca confirma, y `asentar_denegacion` con el contrato C-1 enmendado: el `403` se atribuye al usuario.
- La interfaz publicada de `auditoria`.
- La documentación y la enmienda del diseño de TKT-006.

**Entrega B, consulta.**

- `dominio/consulta.py` revisa los filtros.
- La consulta se publica como `consultar_bitacora`, con `AsientoLeido` y `PaginaBitacora`: filtros del borrador, orden `(ocurrido_en DESC, id DESC)` y paginación por desplazamiento.
- No hay ruta HTTP: la monta TKT-027.

**Cierre.** La auditoría de arquitectura y esquema dio `REQUIERE CAMBIOS` con tres hallazgos Menores documentales. Un ciclo de corrección resolvió dos, aceptó el tercero con nota, y la reauditoría dio `APROBADO`.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-21 | TC-16 nace en **rojo**, no en verde como preveía la fila 1 | El caso exige que `"0003"` esté en la cadena que baja desde la cabeza, y entonces la cabeza era `0002` |
| 2026-10-21 | Los casos de esquema que escriben llevan la ayuda `exigir_bitacora` | Convierte la ausencia de la tabla en un fallo con nombre y no en un `UndefinedTable` sin contexto |
| 2026-10-21 | Fila 4 `⚠ Ajustado`: override acotado de `mypy` para `test_tkt007_fronteras` en `pyproject.toml` | Al entrar `cimenta.auditoria.*` al bloque estricto, TC-42 pasa cadenas a propósito en un `monkeypatch` y `mypy` marcaba `arg-type`. Ningún test se editó. Queda como deuda: al reabrir TC-42, sustituir el override por un `cast` o un `ignore` de línea (`F003`) |
| 2026-10-21 | Fila 8 `⚠ Ajustado`: `AsientoLeido.datos_antes` y `datos_despues` son `Mapping[str, object]` o nulo, no `dict` | `dict` es invariante y el test construye el objeto con un `dict[str, str]`. Solo cambia la anotación |
| 2026-10-21 | TC-56 nace en verde en la fila 8, no como `ImportError` | Consulta a mano los índices que ya creó la fila 1. El tester añadió un complemento que repite como `EXPLAIN` la sentencia real de `consultar_bitacora`, y ese sí nació en rojo. `enable_seqscan = off` no hizo falta |
| 2026-10-21 | Agente general en lugar de `desarrollador-aplicacion` en las filas 2, 4 y 8, y orquestador en las filas 6 y 10 | Agentes ausentes, decisión D-8 |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0003_auditoria_bitacora.py` | nuevo | esquema |
| `backend/herramientas/conexion.py` | modificado (dos funciones) | infraestructura |
| `backend/cimenta/auditoria/dominio/asiento.py`, `consulta.py` | nuevos | dominio |
| `backend/cimenta/auditoria/aplicacion/asentar.py`, `consulta.py` | nuevos | aplicación |
| `backend/cimenta/auditoria/infraestructura/modelos.py`, `repositorio.py` | nuevos | infraestructura |
| `backend/cimenta/auditoria/interfaz.py` | modificado | interfaz publicada |
| `backend/pyproject.toml` | modificado (`mypy`) | configuración |
| `backend/tests/conftest.py` | modificado (tres fixtures) | pruebas |
| `backend/tests/test_tkt007_esquema.py`, `motor.py`, `dominio.py`, `dominio_consulta.py`, `asiento.py`, `fronteras.py`, `consulta.py` | nuevos | pruebas |
| `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md` | modificados | documentación |
| `.claude/skills/conv-backend-fastapi/SKILL.md`, `conv-sql-postgres/SKILL.md`, `.claude/agents/desarrollador-sql.md`, `sdd/00-propuesta-toolkit.md` | modificados | convenciones |
| `sdd/tickets/tkt-006/design.md`, `spec.md`, `_index.md` | modificados (enmienda M9) | documentación |
| `sdd/tickets/tkt-007/design.md`, `impl.md` | modificado / nuevo | documentación |

## Pruebas

La suite completa pasa con Docker: **854 pruebas en verde**. Los siete archivos `test_tkt007_*.py` suman 162 casos. Cada caso del diseño, de TC-01 a TC-57 y de TC-R1 a TC-R5, tiene su prueba nombrada por el criterio, y los mutantes cayeron. El detalle de cada fila está más abajo. Casos que nacieron en verde, todos previstos o anotados: TC-04, TC-13, TC-20 a TC-22, TC-44, TC-45, TC-55 y TC-56.

### Ciclo TDD por fila

#### Fila 1 · Migración (A)

**Rojo** — de 24 casos recogidos (TC-14 son ocho), fallan 22 y pasan 2 (`pytest tests/test_tkt007_esquema.py --tb=no -v`, desde `backend/`, con `docker info` respondiendo `29.8.2`):

```text
tests/test_tkt007_esquema.py::test_tkt007_ca01_columnas_y_nulabilidad FAILED [  4%]
tests/test_tkt007_esquema.py::test_tkt007_ca01_clave_foranea_solo_hacia_usuario FAILED [  8%]
tests/test_tkt007_esquema.py::test_tkt007_ca01_enum_igual_al_borrador FAILED [ 12%]
tests/test_tkt007_esquema.py::test_tkt007_ca01_la_diferencia_nombra_el_verbo PASSED [ 16%]
tests/test_tkt007_esquema.py::test_tkt007_ca01_verbo_fuera_del_enum FAILED [ 20%]
tests/test_tkt007_esquema.py::test_tkt007_ca01_sin_usuario_autenticado FAILED [ 25%]
tests/test_tkt007_esquema.py::test_tkt007_ca03_aplicacion_inserta_y_lee FAILED [ 29%]
tests/test_tkt007_esquema.py::test_tkt007_ca03_update_rechazado FAILED   [ 33%]
tests/test_tkt007_esquema.py::test_tkt007_ca03_delete_y_truncate_rechazados FAILED [ 37%]
tests/test_tkt007_esquema.py::test_tkt007_ca03_privilegios_exactos FAILED [ 41%]
tests/test_tkt007_esquema.py::test_tkt007_ca03_lectura_lee_y_no_escribe FAILED [ 45%]
tests/test_tkt007_esquema.py::test_tkt007_ca07_indices_con_su_definicion FAILED [ 50%]
tests/test_tkt007_esquema.py::test_tkt007_ca07_indice_ausente_se_nombra PASSED [ 54%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[minusculas] FAILED [ 58%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[un-digito] FAILED [ 62%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[tres-digitos] FAILED [ 66%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[prefijo-ajeno] FAILED [ 70%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[espacio-final] FAILED [ 75%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[digitos-de-ancho-completo] FAILED [ 79%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[bien-formada] FAILED [ 83%]
tests/test_tkt007_esquema.py::test_tkt007_ca12_formato_de_regla_en_la_base[nula] FAILED [ 87%]
tests/test_tkt007_esquema.py::test_tkt007_ca10_subir_bajar_subir FAILED  [ 91%]
tests/test_tkt007_esquema.py::test_tkt007_ca10_una_sola_cabeza FAILED    [ 95%]
tests/test_tkt007_esquema.py::test_tkt007_ca10_la_bajada_no_borra_asientos FAILED [100%]
======================== 22 failed, 2 passed in 4.32s =========================
```

La razón de cada fallo, con el mensaje real de la aserción:

| Casos | Razón del fallo |
|---|---|
| TC-01 | `assert [] == [('id', 'uuid', 'NO'), ...]` · `Right contains 11 more items`: `information_schema.columns` no devuelve ninguna columna de `bitacora` |
| TC-02 | `assert set() == {('fk_bitacora_usuario_id', 'FOREIGN KEY (usuario_id) REFERENCES usuario(id)')}`: no hay restricción `f` sobre `bitacora` |
| TC-03 | `assert ['El borrador tiene CREAR y la base no.', ...] == []` · `Left contains 22 more items`: `pg_enum` no tiene ningún verbo porque `to_regtype('accion_bitacora')` es nulo |
| TC-05 a TC-11, TC-14 (ocho casos), TC-17 | `AssertionError: La tabla bitacora no existe: falta la migración v0003 (TKT-007)` · `assert (False,) == (True,)`, lanzada por `exigir_bitacora` (`to_regclass('bitacora')` nulo) antes de escribir nada |
| TC-12 | Sin la tabla, `pg_indexes` no devuelve índices: `indices_ausentes(ESPERADOS, {})` nombra los dos |
| TC-15 | Tras `upgrade head`, `exigir_bitacora` falla con el mismo mensaje: la cabeza sigue siendo `0002` |
| TC-16 | `assert '0003' in ['0002', '0001']`: hay una sola cabeza, pero la cadena no tiene `0003` |

Ninguno falla por error de importación, de sintaxis o de entorno: `ruff check` y `mypy` limpios sobre el archivo, y las ayudas, el fichero del borrador y el arnés funcionan, como prueban TC-04 y TC-13 en verde.

**Tests que nacieron en verde y por qué:**

- **TC-04 y TC-13** son oráculos de las ayudas `diferencias_de_verbos` e `indices_ausentes`, definidas en el propio archivo y sin base de datos: prueban que TC-03 y TC-12 nombran el verbo o el índice que difiere. Nacen en verde por construcción y lo que los respalda son los mutantes de la fila 5 (invertir la comparación de la ayuda). TC-04 lee además el `AccionBitacora` real del borrador y exige 22 verbos, así que no es vacío.
- **TC-16 nace en rojo, no en verde.** La fila 1 lo preveía verde («hoy hay una cabeza»), pero el caso de diseño exige también que `"0003"` esté en la cadena que baja desde la cabeza, y eso solo ocurre cuando exista `v0003`. Se dejó la aserción del diseño: es la que detecta una migración mal encadenada. Si el orquestador prefiere partirlo en dos, la mitad de «una sola cabeza» sería verde.
- TC-09 (`TRUNCATE`) ya sería rechazado hoy por el motor si la tabla existiera, porque `v0001` no concede `TRUNCATE` a la aplicación. Su `DELETE` sí distingue la revocación; el `TRUNCATE` queda como el diseño D-7 lo describe, una intención escrita. TC-10 fija además que `relacl` no lo concede.

**Verde:** pendiente (`desarrollador-sql`, `v0003_auditoria_bitacora.py`, literal del diseño).

**Refactor:** pendiente.

**Tests devueltos al tester:** ninguno.

## Fila 1 · verde y refactor

Se creó `backend/migraciones/versions/v0003_auditoria_bitacora.py` con el SQL literal del diseño: el tipo `accion_bitacora` con los 22 verbos en el orden del borrador, la tabla `bitacora` con `pk_bitacora`, `fk_bitacora_usuario_id` y `ck_bitacora_regla_negocio_formato`, los índices `ix_bitacora_obra_id_ocurrido_en` e `ix_bitacora_regla_negocio` (parcial), y `REVOKE UPDATE, DELETE, TRUNCATE ON bitacora FROM cimenta_aplicacion`. La bajada se niega con `RAISE EXCEPTION` si hay asientos y, si no, borra tabla y tipo. Sigue el patrón de v0001 y v0002: tuplas `_SUBIDA` y `_BAJADA`, un `op.execute` por sentencia. No se tocó ningún test.

Comprobación previa: v0001 no concede `TRUNCATE` (`grep -c TRUNCATE` sobre v0001 da `0`; solo concede `SELECT, INSERT, UPDATE, DELETE` por omisión). El `TRUNCATE` del `REVOKE` queda como intención escrita (D-7).

```text
$ uv run --env-file ../.env alembic heads
0003 (head)

$ uv run pytest tests/test_tkt007_esquema.py tests/test_identidad_*.py -q
85 passed in 34.04s

$ uv run ruff check .            -> All checks passed!
$ uv run ruff format --check .   -> 114 files already formatted
$ uv run mypy .                  -> Success: no issues found in 114 source files
$ uv run pytest -q               -> 716 passed in 58.02s
```

TC-15 (subir, bajar a 0002, subir, con fotografía del catálogo), TC-16 y TC-17 (la bajada se niega con asientos) pasan sobre PostgreSQL real con testcontainers. No se corrió el ciclo manual `upgrade head`, `downgrade 0002`, `upgrade head` contra una base local de desarrollo: no había ningún contenedor de base en marcha (`docker ps` vacío); lo cubre TC-15.

**Refactor:** ninguno necesario; el archivo es literal del diseño y pasa Ruff y mypy. **Desviaciones del diseño:** ninguna; `down_revision` es `0002`, la cabeza vigente. **Tests devueltos al tester:** ninguno.

## Fila 2 · rojo

El tester escribió las tres *fixtures* en `backend/tests/conftest.py` (`guarda_de_aplicacion`, `motor_aplicacion` y `sesion_bd`, con el código literal del diseño, más la ayuda privada `_exigir_motor_de_aplicacion`; ninguna `autouse`; las *fixtures* existentes no se tocaron, solo se añadieron los imports `Callable`, `text`, `Engine` y `Session`) y `backend/tests/test_tkt007_motor.py` con TC-18 a TC-22. No se escribió ni se editó `herramientas/conexion.py`. Los símbolos `url_aplicacion` y `crear_motor_aplicacion` se importan **dentro** de cada caso, no al principio del módulo: así TC-18 y TC-19 fallan con el `ImportError` del símbolo pedido (la razón esperada) y la recolección no se cae, lo que habría ocultado TC-20 a TC-22.

Docker en marcha (`docker info` responde `29.8.2`). Salida real de `uv run pytest tests/test_tkt007_motor.py --tb=no -v`, desde `backend/`:

```text
tests/test_tkt007_motor.py::test_tkt007_ca09_url_del_rol_de_aplicacion FAILED [ 20%]
tests/test_tkt007_motor.py::test_tkt007_ca09_crear_el_motor_no_conecta FAILED [ 40%]
tests/test_tkt007_motor.py::test_tkt007_ca09_sesion_del_rol_de_aplicacion PASSED [ 60%]
tests/test_tkt007_motor.py::test_tkt007_ca09_la_guarda_rechaza_al_propietario PASSED [ 80%]
tests/test_tkt007_motor.py::test_tkt007_ca09_fixtures_nuevas_sin_autouse PASSED [100%]

FAILED tests/test_tkt007_motor.py::test_tkt007_ca09_url_del_rol_de_aplicacion
FAILED tests/test_tkt007_motor.py::test_tkt007_ca09_crear_el_motor_no_conecta
========================= 2 failed, 3 passed in 2.28s =========================
```

| Caso | Resultado | Razón |
|---|---|---|
| TC-18 | FALLA | `ImportError: cannot import name 'url_aplicacion' from 'herramientas.conexion'`. Es la razón esperada: el símbolo pedido no existe |
| TC-19 | FALLA | `ImportError: cannot import name 'crear_motor_aplicacion' from 'herramientas.conexion'`. Razón esperada |
| TC-20 | PASA (prevista) | Prueba la *fixture* `sesion_bd` que escribe el tester: sobre `base_de_prueba` devuelve `current_user = cimenta_aplicacion` y la base de la prueba. No depende de ninguna función de `conexion.py`, porque la *fixture* construye su propia URL con `URL.create`, como dicta el diseño |
| TC-21 | PASA (prevista) | Prueba `guarda_de_aplicacion`: un motor del rol de migración lanza `pytest.fail.Exception` cuyo texto contiene `cimenta_aplicacion` y `cimenta_migracion`. El caso entra por la guarda y no por `motor_aplicacion`, así que no se ve afectado por que falte código de producción |
| TC-22 | PASA (prevista) | Revisión por AST de `conftest.py`: las tres *fixtures* existen y ninguna lleva `autouse` |

Ninguna *fixture* importa una función que aún no existe, así que TC-20 a TC-22 no caen por esa causa (el diseño lo admitía como posibilidad): no hay ningún rojo por error de entorno. TC-18 y TC-19 son los dos únicos rojos y los dos por la razón prevista.

**Tests que nacieron en verde y por qué:** TC-20 a TC-22 prueban código que el propio tester escribió en esta fila; no dependen de producción y, como dice el diseño, lo que demuestra que no son huecos son los mutantes: MT-18 (construir `motor_aplicacion` con el rol de migración) debe hacer caer TC-20 por el mensaje de la guarda. TC-21 y TC-22 son oráculos de forma del arnés. Comprobaciones adicionales: `ruff check` y `ruff format --check` limpios sobre `tests/`; `uv run pytest tests/test_tkt004_conftest.py tests/test_tkt007_esquema.py` sigue en verde (25 pasan), es decir, `test_tkt004_conftest` confirma que las nuevas *fixtures* no son `autouse` y las pruebas de la fila 1 no se alteraron. `mypy` sobre los dos archivos solo marca los dos `attr-defined` de `url_aplicacion` y `crear_motor_aplicacion`, que desaparecen cuando el desarrollador escriba las funciones (es el mismo rojo, visto por el verificador de tipos).

**Verde:** pendiente (agente general por sustitución de `desarrollador-aplicacion`, modelo `haiku`; las dos funciones de `herramientas/conexion.py`, literales del diseño).

**Refactor:** pendiente.

**Tests devueltos al tester:** ninguno.

## Fila 2 · verde y refactor

Se añadieron a `backend/herramientas/conexion.py` las dos funciones del diseño, literales: `url_aplicacion() -> URL`, que devuelve `URL.create("postgresql+psycopg", ...)` con el rol `cimenta_aplicacion`, la contraseña de `CIMENTA_DB_CONTRASENA_APLICACION` leída con `leer_variable` (si falta o está vacía, `RuntimeError` que nombra la variable) y host, puerto y base de sus variables; y `crear_motor_aplicacion() -> Engine`, que devuelve `create_engine(url_aplicacion(), pool_pre_ping=True)`. `create_engine` no abre conexión: la primera se abre con la primera consulta. No se tocó `url_migracion` ni las constantes, ni ningún test, ni `backend/tests/conftest.py`. Único cambio fuera del bloque literal: el import de `sqlalchemy` pasó de `URL` a `URL, Engine, create_engine`, necesario para las dos funciones nuevas.

Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_motor.py tests/test_tkt004_conftest.py tests/test_identidad_sin_create_all.py`, desde `backend/`, con Docker en marcha:

```text
collected 7 items

tests\test_tkt007_motor.py .....                                         [ 71%]
tests\test_tkt004_conftest.py .                                          [ 85%]
tests\test_identidad_sin_create_all.py .                                 [100%]

======================== 7 passed in 132.29s (0:02:12) ========================
```

Las cinco de `test_tkt007_motor.py` son TC-18 a TC-22. TC-18 y TC-19, que estaban en rojo, pasan ahora por la razón prevista; TC-20 a TC-22 siguen en verde.

```text
uv run mypy .                  -> Success: no issues found in 115 source files
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 115 files already formatted
```

El `# type: ignore[attr-defined]` de TC-19 (`motor.pool.checkedout()`) no es innecesario: `pyproject.toml` fija `warn_unused_ignores = true` y mypy no lo marca como sobrante, así que sigue ahí sin tocarlo. Sin `pytest` completo: esta fila solo tocó `herramientas/`, y la suite completa la corre `/sdd-revisar`.

**Refactor:** ninguno. Las dos funciones son literales del diseño y el archivo pasa Ruff y mypy; no hay código que simplificar sin cambiar comportamiento. **Desviaciones del diseño:** solo el import ampliado descrito arriba, que el diseño no lista. **Tests devueltos al tester:** ninguno.

## Fila 3 · rojo

El tester escribió `backend/tests/test_tkt007_dominio.py` con TC-23 a TC-32, sin Docker. No se creó ni se tocó ningún archivo de producción: `backend/cimenta/auditoria/dominio/` sigue con su `__init__.py` vacío y sin `asiento.py`.

**Cómo se importan los símbolos.** Los símbolos de `cimenta.auditoria.dominio.asiento` se importan **dentro** de cada caso (o de la ayuda `_revisar`), nunca al principio del módulo, y los `MENSAJE_*` se piden por nombre con `getattr` desde la ayuda `_mensaje`. Así cada caso falla por sí solo con el `ModuleNotFoundError` del módulo pedido, la recolección no se cae, y la parametrización no depende del módulo que aún no existe. El único import de producción a nivel de módulo es el de `ResultadoAsiento` bajo `TYPE_CHECKING`, que no se ejecuta.

Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_dominio.py --tb=no -q -p no:cacheprovider`, desde `backend/`:

```text
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF                               [100%]
=========================== short test summary info ===========================
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_asiento_bien_formado
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[minusculas]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[prefijo-ajeno]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[un-digito]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[tres-digitos]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[espacio-final]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[salto-de-linea-final]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[digitos-de-ancho-completo]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_mal_formada[no-es-texto]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_bien_formada_o_ausente_pasa[RN-03]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_bien_formada_o_ausente_pasa[RN-25]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_regla_bien_formada_o_ausente_pasa[nula]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_float_y_decimal_rechazados[float]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_float_y_decimal_rechazados[float-anidado-en-lista]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_float_y_decimal_rechazados[decimal]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_float_y_decimal_rechazados[nan-en-antes]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_verbo_inexistente['BORRAR']
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_verbo_inexistente['autorizar']
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_verbo_inexistente['']
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_verbo_inexistente[None]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_verbo_inexistente[5]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_denegar_es_un_verbo_valido[miembro]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_denegar_es_un_verbo_valido[cadena]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca04_sin_usuario
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[tipo-vacio]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[tipo-en-blanco]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[tipo-nulo]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[tipo-no-es-texto]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[entidad-nula]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[entidad-no-es-uuid]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[motivo-en-blanco]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[motivo-no-es-texto]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[obra-no-es-uuid]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[datos-no-es-objeto]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_forma_de_entidad_motivo_y_datos[clave-no-es-cadena]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_clave_no_cadena_anidada_lleva_su_ruta
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_campos_opcionales_ausentes_pasan
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_los_defectos_se_acumulan_en_orden
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_todos_los_campos_mal_siguen_el_orden_del_diseno
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca01_enum_del_dominio_igual_al_borrador
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_codigos_del_catalogo
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca08_dominio_de_auditoria_puro
42 failed in 0.08s
```

**La razón de cada fallo.**

| Casos | Razón del fallo |
|---|---|
| TC-23 a TC-31 (41 de los 42 casos recogidos) | `ModuleNotFoundError: No module named 'cimenta.auditoria.dominio.asiento'`, lanzado por el import del símbolo pedido dentro del caso (`_revisar` o el propio caso). Es la razón esperada: el módulo que crea la fila 3 no existe. TC-31 falla por la misma causa al llamar a `_revisar`, después de importar `contrato_error`, que sí existe |
| TC-32 | `AssertionError: Falta cimenta/auditoria/dominio/asiento.py: ['__init__.py']`. No es `ModuleNotFoundError` sino la aserción de existencia del módulo (ver abajo). No llega a ejecutar `lint-imports` |

Ninguno falla por error de sintaxis, de entorno o de importación de otra cosa: `ruff check` y `ruff format --check` limpios sobre el archivo, y `mypy` sobre él solo marca `import-not-found` de `cimenta.auditoria.dominio.asiento`, que es el mismo rojo visto por el verificador de tipos y desaparece con el módulo.

**Tests que nacieron en verde:** ninguno. Una previsión del diseño no se cumple en el sentido contrario: la fila 3 admitía que TC-32 naciera en verde con la carpeta `dominio/` vacía. Se decidió que **no** lo haga: TC-32 exige primero que `asiento.py` exista en esa carpeta. Con la carpeta vacía el recorrido del AST y la ejecución de `lint-imports` sobre `dominio-sin-framework` pasarían sin examinar nada, y un test que no puede fallar no es un test. El resto de TC-32 (lista blanca por AST y `Contracts: 1 kept, 0 broken` con código 0) es literal del diseño y corre en cuanto el archivo exista.

**Casos añadidos al diseño** (cada uno nombra el TC del que es complemento y no cambia lo que el diseño pide):

| Caso | Complementa | Qué añade |
|---|---|---|
| `test_tkt007_ca05_regla_bien_formada_o_ausente_pasa` | TC-24 | `RN-03`, `RN-25` y ninguna regla no producen defecto: sin él, una regla que rechaza todo pasaría TC-24 |
| `test_tkt007_ca05_denegar_es_un_verbo_valido` | TC-26 | `DENEGAR` como miembro del enum y como cadena pasa, y el `Asiento` lleva `AccionBitacora.DENEGAR` |
| `test_tkt007_ca05_clave_no_cadena_anidada_lleva_su_ruta` | TC-28 | Una clave que no es cadena dentro de un objeto anidado nombra `datos_antes.lineas` |
| `test_tkt007_ca05_campos_opcionales_ausentes_pasan` | TC-28 | Motivo, obra, regla y datos ausentes: el asiento se forma |
| `test_tkt007_ca05_todos_los_campos_mal_siguen_el_orden_del_diseno` | TC-29 | Con los nueve campos mal, el orden de los defectos es el de la firma de `revisar_asiento` |

Y dos casos de la lista de TC-24 que el diseño no nombra: `"RN-03\n"` (un `$` los dejaría pasar, `fullmatch` no) y `3` (no es texto), más el de dígitos de ancho completo tras «RN-», que solo cae si la expresión usa `[0-9]` y no `\d`.

**Comprobación de los tests contra un oráculo (fuera del repositorio).** Para no entregar un rojo que fuera rojo por un error del propio test, se copió el árbol al directorio temporal de la sesión y allí se escribió, literal del diseño, `asiento.py`: los 42 casos pasan (`42 passed in 0.66s`, incluida la ejecución de `lint-imports`). Con esa copia se aplicaron once mutantes de uno en uno; ninguno dejó la suite en verde:

| Mutante (sobre la copia, no sobre el repositorio) | Casos que caen |
|---|---|
| `_a_json` admite `float` (MT-12) | `float_y_decimal_rechazados` (los dos casos de `float`), `los_defectos_se_acumulan_en_orden`, `todos_los_campos_mal…` |
| `_a_json` admite `Decimal` (MT-13) | `float_y_decimal_rechazados[decimal]`, `todos_los_campos_mal…` |
| `regla_bien_formada` con `match` en lugar de `fullmatch` (MT-14) | `regla_mal_formada` (espacio final, salto de línea final) |
| `[0-9]` por `\d` (MT-14) | `regla_mal_formada[digitos-de-ancho-completo]` |
| `if not valor.strip()` por `if not valor` | `forma_de_entidad_motivo_y_datos` (`tipo-en-blanco`, `motivo-en-blanco`), `todos_los_campos_mal…` |
| UUID de `datos_*` sin convertir a cadena | `asiento_bien_formado` |
| `datos_antes` y `datos_despues` revisados en orden inverso | `todos_los_campos_mal_siguen_el_orden_del_diseno` |
| `AccionBitacora` con un `BORRAR` de más (MT-8) | `enum_del_dominio_igual_al_borrador`, `codigos_del_catalogo`, `verbo_inexistente`, `los_defectos_se_acumulan_en_orden`, `todos_los_campos_mal…` |
| verbo comparado sin distinguir mayúsculas | `verbo_inexistente['autorizar']` |
| `motivo` nulo tratado como obligatorio | `campos_opcionales_ausentes_pasan` |
| `obra_id` obligatorio | `campos_opcionales_ausentes_pasan` |

Estos once son una comprobación del tester sobre el literal del diseño; los mutantes oficiales del dominio (MT-8, MT-12 a MT-14) los repite la fila 5 sobre el código real, con el SHA-256 anotado.

**Verde:** pendiente (`desarrollador-dominio`, `haiku`; `dominio/asiento.py`, literal del diseño, con `texto_obligatorio` sin guion bajo).

**Refactor:** pendiente.

**Tests devueltos al tester:** ninguno.

## Fila 3 · verde y refactor

Se creó `backend/cimenta/auditoria/dominio/asiento.py` a partir del bloque literal de `design.md` («Capas afectadas», `dominio/asiento.py`): `AccionBitacora` con los 22 verbos en el orden del borrador y `name == value`; `DefectoDeCampo`; `Asiento` y `ResultadoAsiento`, objetos de valor `frozen` y `slots`; `regla_bien_formada`, con `_REGLA.fullmatch` sobre `RN-[0-9]{2}`; `texto_obligatorio`, sin guion bajo, como pide la fila; `_uuid`, `_a_json`, `_datos` y `revisar_asiento`, que devuelve el asiento normalizado o todos sus defectos en el orden de los campos y nunca lanza. Los mensajes `MENSAJE_*` son los del diseño, literales. No se tocó ningún test ni ningún otro archivo.

Desviaciones respecto al literal, todas de forma o de imports, sin cambio de comportamiento:

- El literal no trae imports. Se añadieron `re`, `uuid`, `collections.abc.Mapping`, `dataclasses.dataclass`, `enum.StrEnum` y `typing.cast`, solo de la lista blanca de ADR-021.
- Se extrajo `_verbo(valor, defectos)` de `revisar_asiento` para que la función de revisión tenga un nivel de abstracción por paso. La comprobación es la del literal: `isinstance(valor, str)` y pertenencia a `AccionBitacora.__members__.values()`.
- `MENSAJE_VALOR_NO_JSON` se parte en dos cadenas contiguas con el mismo valor, para respetar el largo de línea que deja `ruff format`. El texto resultante es idéntico al del diseño.
- La firma de `_uuid` y la de `revisar_asiento` se partieron en varias líneas, como las deja `ruff format`.
- `regla_bien_formada` lleva `RN-04` en el docstring, porque la regla de formato es parte de RN-04.

Rojo previo, antes de crear el módulo (`PYTHONUTF8=1 uv run pytest tests/test_tkt007_dominio.py -q`, con el archivo apartado de forma temporal):

```text
E       AssertionError: Falta cimenta/auditoria/dominio/asiento.py: ['__init__.py']
E       ModuleNotFoundError: No module named 'cimenta.auditoria.dominio.asiento'  (x41)
42 failed in 0.34s
```

Verde, en la primera ejecución con el módulo en su sitio:

```text
$ PYTHONUTF8=1 uv run pytest tests/test_tkt007_dominio.py -q
..........................................                               [100%]
42 passed in 0.65s
```

Los 42 son TC-23 a TC-32 con sus parametrizaciones y complementos. Lo que no se hizo es el ciclo de uno en uno que pide la fila: el literal se escribió entero y los 42 pasaron a la primera. Eso no prueba más que el ciclo normal, así que la cobertura de los mutantes la confirma la fila 5 sobre el código real.

Gates, desde `backend/`:

```text
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 117 files already formatted
uv run mypy .                  -> Success: no issues found in 117 source files
uv run python -m herramientas.verificar_float -> archivos revisados: 13; hallazgos: 0 (exit 0)
uv run lint-imports            -> Contracts: 15 kept, 0 broken.
```

`dominio-sin-framework` queda `KEPT`, y el mismo contrato lo comprueba `test_tkt007_ca08_dominio_de_auditoria_puro` en TC-32.

Suite previa, sin los archivos que necesitan Docker (los que usan `testcontainers`), desde `backend/` con `PYTHONUTF8=1`:

```text
755 passed in 62.56s (0:01:02)
```

Los archivos con `testcontainers` (`test_tkt007_esquema.py` y `test_tkt007_motor.py`) no se ejecutaron en esta pasada, porque esta fila no toca PostgreSQL; la suite completa la corre `/sdd-revisar`.

**Refactor:** la extracción de `_verbo` se hizo al escribir el módulo, no en un paso posterior con la suite en verde. La suite pasó a la primera, así que no hubo que deshacer nada. **Tests devueltos al tester:** ninguno. Ningún test de la fila parece equivocado.

## Fila 4 · rojo

El tester escribió `backend/tests/test_tkt007_asiento.py` (con Docker) y `backend/tests/test_tkt007_fronteras.py` (sin Docker), con TC-33 a TC-45. No se creó ni se tocó ningún archivo de producción: `cimenta/auditoria/interfaz.py` sigue con su docstring, y `aplicacion/` e `infraestructura/` de `auditoria` solo tienen su `__init__.py`.

**Reparto entre los dos archivos.** `test_tkt007_asiento.py` lleva lo que escribe en la base: TC-33 a TC-40, con `sesion_bd`, el rol de aplicación y conexiones nuevas (`lector`) para mirar lo que quedó. `test_tkt007_fronteras.py` lleva lo que el diseño marca «sin Docker»: TC-41 a TC-45 y la parte de AST de TC-35. Ningún caso de `fronteras` pide una *fixture* de base.

**Cómo se importan los símbolos.** `asentar` y `asentar_denegacion` se importan **dentro** de cada caso desde `cimenta.auditoria.interfaz`, de modo que cada caso falla por sí solo con el `ImportError` del símbolo pedido y la recolección no se cae. Los `MENSAJE_*` del dominio se piden por nombre al módulo de la fila 3, que ya existe. El mensaje de la zona horaria (`El momento lleva zona horaria.`), que vivirá en `aplicacion/asentar.py`, se escribe literal en el test: es el oráculo del texto del diseño.

**Ayudas y *fixtures* del archivo.** `sembrar_usuario(conexion, correo) -> uuid.UUID` (con el `INSERT INTO usuario (id, nombre, email, password_hash)` del diseño), `sembrar_sesion`, `validar_contra` (copia de la ayuda de TKT-005, contra el borrador con `Draft202012Validator`), `afirmar_validacion_rechazada` (lista exacta de `como_dict()`, `tipo == "VALIDACION"` y cuerpo válido contra `ErrorValidacion` con `exc.cuerpo(frozenset(), CID)`), `afirmar_clave_foranea_del_actor` (`ForeignKeyViolation`, `sqlstate` `23503` y `diag.constraint_name == "fk_bitacora_usuario_id"`), y las *fixtures* `ana`, `lector` y `sentencias`. `sentencias` es el oyente `before_cursor_execute` sobre `motor_aplicacion` que prueba que un rechazo de forma no toca la base; ninguna *fixture* nueva está en `conftest.py` ni es `autouse`.

Docker en marcha (`docker info` responde `29.8.2`). Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_asiento.py tests/test_tkt007_fronteras.py --tb=no -v -p no:cacheprovider`, desde `backend/`:

```text
tests/test_tkt007_asiento.py::test_tkt007_ca02_cambio_y_asiento_se_confirman_juntos FAILED [  4%]
tests/test_tkt007_asiento.py::test_tkt007_ca02_asiento_fallido_deshace_el_cambio FAILED [  8%]
tests/test_tkt007_asiento.py::test_tkt007_ca02_el_servicio_no_confirma FAILED [ 13%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_asiento_con_regla_y_obra FAILED [ 17%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[regla-en-minusculas] FAILED [ 21%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[importe-float] FAILED [ 26%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[importe-decimal] FAILED [ 30%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[verbo-inexistente] FAILED [ 34%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[momento-sin-zona] FAILED [ 39%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[momento-nulo] FAILED [ 43%]
tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[forma-y-momento-juntos-en-orden] FAILED [ 47%]
tests/test_tkt007_asiento.py::test_tkt007_ca04_denegar_atribuido_al_usuario FAILED [ 52%]
tests/test_tkt007_asiento.py::test_tkt007_ca04_denegar_no_confirma FAILED [ 56%]
tests/test_tkt007_asiento.py::test_tkt007_ca04_nunca_anonimo FAILED      [ 60%]
tests/test_tkt007_asiento.py::test_tkt007_ca04_nunca_anonimo_usuario_inexistente FAILED [ 65%]
tests/test_tkt007_fronteras.py::test_tkt007_ca02_ningun_servicio_llama_a_commit FAILED [ 69%]
tests/test_tkt007_fronteras.py::test_tkt007_ca04_firma_sin_sesion_ni_correlacion FAILED [ 73%]
tests/test_tkt007_fronteras.py::test_tkt007_ca08_firma_de_asentar FAILED [ 78%]
tests/test_tkt007_fronteras.py::test_tkt007_ca04_sustituible_con_monkeypatch FAILED [ 82%]
tests/test_tkt007_fronteras.py::test_tkt007_ca08_funciones_desde_la_interfaz FAILED [ 86%]
tests/test_tkt007_fronteras.py::test_tkt007_ca08_auditoria_no_importa_modulos PASSED [ 91%]
tests/test_tkt007_fronteras.py::test_tkt007_ca08_ningun_archivo_de_auditoria_importa_otro_modulo PASSED [ 95%]
tests/test_tkt007_fronteras.py::test_tkt007_ca08_otro_modulo_no_importa_sus_repositorios PASSED [100%]
======================== 20 failed, 3 passed in 4.96s =========================
```

De 23 casos recogidos (TC-37 son siete), fallan 20 y pasan 3.

**La razón de cada fallo.**

| Casos | Razón del fallo |
|---|---|
| TC-33 a TC-37 (once casos recogidos) y TC-35 en su parte de base | `ImportError: cannot import name 'asentar' from 'cimenta.auditoria.interfaz'`. Es la razón esperada: el símbolo pedido no existe. La *fixture* `sesion_bd` y la siembra de `ana` ya corrieron antes, así que el contenedor, `alembic upgrade head` y el rol de aplicación funcionan: no es un rojo de entorno |
| TC-38 a TC-40 (cuatro casos recogidos) | `ImportError: cannot import name 'asentar_denegacion' from 'cimenta.auditoria.interfaz'`. Razón esperada |
| TC-35 (AST) | `AssertionError: ['__init__.py']` sobre `{'asentar.py', 'repositorio.py', 'modelos.py'} <= {'__init__.py'}`. Es la aserción anti verde vacío: hoy `aplicacion/` e `infraestructura/` no tienen ninguno de los tres archivos del diseño, y sin ella el recorrido del AST pasaría sin examinar nada |
| TC-41, TC-42 | `ImportError` de `asentar_denegacion` desde la interfaz |
| TC-43 (complemento de firma de `asentar`) | `ImportError` de `asentar` desde la interfaz |
| TC-43 | `ImportError: cannot import name 'AccionBitacora' from 'cimenta.auditoria.interfaz'` |

Ninguno falla por error de sintaxis, de entorno o de importación de otra cosa: `ruff check` y `ruff format --check` limpios sobre los dos archivos, y `mypy` sobre ellos solo marca 17 `attr-defined` de `asentar`, `asentar_denegacion`, `AccionBitacora` y `__all__` en `cimenta.auditoria.interfaz`, que es el mismo rojo visto por el verificador de tipos y desaparece con la interfaz publicada.

**Tests que nacieron en verde y por qué:**

- **TC-44** (`test_tkt007_ca08_auditoria_no_importa_modulos` y `test_tkt007_ca08_ningun_archivo_de_auditoria_importa_otro_modulo`) y **TC-45** (`test_tkt007_ca08_otro_modulo_no_importa_sus_repositorios`) son contratos que ya existen, como prevé el diseño: `grafo-identidad` ya impide que `auditoria` importe a `identidad`, `solo-por-interfaz` ya prohíbe importar `infraestructura` de otro módulo (el módulo de destino, `repositorio`, no necesita existir porque el contrato también rompe sobre el paquete `cimenta.auditoria.infraestructura`), y hoy ningún archivo de `auditoria/` importa otro módulo de `cimenta`. La comprobación del árbol real no es vacía: exige que `dominio/asiento.py` esté entre los archivos revisados. Lo que demuestra que dependen de algo son dos mutantes de la fila 5 sobre `pyproject.toml`: quitar `cimenta.auditoria` de `protected_modules` de `grafo-identidad` o añadir `cimenta.auditoria` a sus `allowed_importers` (rompe TC-44), y quitar `cimenta.*.infraestructura` de `forbidden_modules` de `solo-por-interfaz` (rompe TC-45).

**Casos añadidos al diseño** (cada uno nombra el TC del que es complemento y no cambia lo que el diseño pide):

| Caso | Complementa | Qué añade |
|---|---|---|
| `test_tkt007_ca02_ningun_servicio_llama_a_commit` | TC-35 | La parte de AST de TC-35 se separó del caso de base para que un caso diga una cosa; vive en `fronteras` porque no necesita Docker |
| `test_tkt007_ca04_nunca_anonimo_usuario_inexistente` | TC-40 | La mitad de TC-40 que el motor rechaza (UUID inexistente → `ForeignKeyViolation`, sin asiento tras `rollback`) se separó de la mitad que rechaza el dominio (`usuario_id=None`) |
| `test_tkt007_ca08_firma_de_asentar` | TC-43 | Nombres, orden, tipo de cada parámetro (el primero posicional, los demás solo por nombre) y cuáles llevan valor por omisión `None` en `asentar`: las «firmas exactas» del diseño |
| TC-37 `importe-decimal`, `momento-nulo` y `forma-y-momento-juntos-en-orden` | TC-37 | `Decimal` en `datos_antes`; `ocurrido_en=None` (`OBLIGATORIO`); y un asiento con la regla mal escrita y el instante sin zona, que fija el orden `(*defectos del dominio, *defectos del momento)` del diseño |

Además, TC-35 y TC-39 comprueban primero que, **dentro** de la transacción de quien llama, `SELECT count(*) FROM bitacora` da 1: sin eso, «0 asientos tras `rollback`» también lo cumpliría un `asentar` que no escribe nada.

**Comprobación de los tests contra un oráculo (fuera del repositorio).** Para no entregar un rojo que fuera rojo por un error del propio test, se copió el árbol al directorio temporal de la sesión y allí se escribieron, literales del diseño, `modelos.py`, `insertar_asiento`, `asentar.py` y `interfaz.py`: los 23 casos pasan (`23 passed in 5.94s`, con Docker y `lint-imports` sobre la copia). Con esa copia se aplicaron cinco mutantes de uno en uno; ninguno dejó la suite en verde:

| Mutante (sobre la copia, no sobre el repositorio) | Casos que caen |
|---|---|
| `asentar` llama a `sesion_bd.commit()` tras insertar (MT-11) | `el_servicio_no_confirma`, `denegar_no_confirma`, `ningun_servicio_llama_a_commit` |
| `JSONB()` sin `none_as_null=True` (MT-15) | `cambio_y_asiento_se_confirman_juntos`, `denegar_atribuido_al_usuario` |
| `asentar_denegacion` con un `entidad_id` que no es el usuario | `denegar_atribuido_al_usuario`, `nunca_anonimo` |
| `asentar` sin `defectos_de_momento` (MT-19) | `momento-sin-zona`, `momento-nulo`, `forma-y-momento-juntos-en-orden` |
| orden de los defectos invertido | `forma-y-momento-juntos-en-orden` |

Los mutantes oficiales (MT-9, MT-11, MT-15, MT-16, MT-19) los repite la fila 5 sobre el código real, con el SHA-256 anotado.

**Verde:** pendiente (agente general por sustitución de `desarrollador-aplicacion`, `haiku`: `infraestructura/modelos.py`, `insertar_asiento` en `infraestructura/repositorio.py`, `aplicacion/asentar.py`, `interfaz.py` con `__all__ = ["AccionBitacora", "asentar", "asentar_denegacion"]` y `"cimenta.auditoria.*"` en el *override* de `mypy`).

**Refactor:** pendiente.

**Tests devueltos al tester:** ninguno.

## Fila 4 · verde y refactor

Se escribieron, copiando el literal de `design.md` («Capas afectadas» y la fila 4 del orden de implementación), los cinco archivos de producción de la fila: `backend/cimenta/auditoria/infraestructura/modelos.py` (`Base` propia con `MetaData(naming_convention=CONVENCION_NOMBRES)` y `FilaBitacora` sobre la tabla `bitacora`, con `postgresql.ENUM(AccionBitacora, name="accion_bitacora", create_type=False, values_callable=...)` y `postgresql.JSONB(none_as_null=True)` en `datos_antes` y `datos_despues`, sin `ForeignKey` declarada), `backend/cimenta/auditoria/infraestructura/repositorio.py` (`insertar_asiento`, una sola sentencia `INSERT` sobre la `Session` recibida), `backend/cimenta/auditoria/aplicacion/asentar.py` (`MENSAJE_SIN_ZONA`, `defectos_de_momento`, `rechazar_si_hay_defectos`, `asentar` y `asentar_denegacion`; genera el `id` con `uuid.uuid4()`, convierte los defectos en `ValidacionRechazada` de `contrato_error` antes de tocar la base y nunca llama a `commit`, `rollback`, `begin` ni `flush`) y `backend/cimenta/auditoria/interfaz.py` (reexporta `AccionBitacora`, `asentar` y `asentar_denegacion` con `__all__ = ["AccionBitacora", "asentar", "asentar_denegacion"]`). La firma de `asentar_denegacion` es la enmendada de C-1: `sesion_bd` posicional y el resto solo por nombre.

Se añadió `"cimenta.auditoria.*"` al override estricto de `mypy` en `backend/pyproject.toml`, como pide el diseño. **Desviación 1 (mypy, no prevista por el diseño):** al entrar `auditoria` en el override estricto, `mypy .` marcó tres `arg-type` en `backend/tests/test_tkt007_fronteras.py:209`, dentro de TC-42 (`test_tkt007_ca04_sustituible_con_monkeypatch`). Ese test llama a `auditoria.asentar_denegacion("sesion", usuario_id="ana", ocurrido_en="T0", ...)` con cadenas a propósito: es un monkeypatch que comprueba el paso de argumentos, no el tipo. No se tocó el test, como pide la fila. Para que `mypy` quede en verde se añadió un override de módulo acotado, con el comentario de la desviación: `module = ["test_tkt007_fronteras"]` y `disable_error_code = ["arg-type"]`. Solo afecta a ese archivo y solo a ese código de error; el resto del archivo sigue comprobado. Si el tester prefiere otra forma (por ejemplo, un `cast` en el test), es decisión suya y no cambia el comportamiento.

**Desviación 2 (formato):** `ruff format --check` marcó una línea de `rechazar_si_hay_defectos` en `asentar.py` que el literal dejaba de más de 100 caracteres. Se reformateó con `ruff format` sobre ese único archivo. El contenido no cambia.

Ningún otro ajuste respecto al literal. `dominio/` no cambió, y `auditoria` no importa ningún otro módulo de `cimenta` (TC-44 lo comprueba). `herramientas/conexion.py` y `tests/conftest.py` no se tocaron en esta fila.

Verde, primera ejecución con los archivos en su sitio, desde `backend/` con `PYTHONUTF8=1` y Docker en marcha:

```text
$ uv run pytest tests/test_tkt007_asiento.py tests/test_tkt007_fronteras.py -q -p no:cacheprovider
.......................                                                  [100%]
23 passed in 7.11s
```

Los 23 son TC-33 a TC-45 con sus parametrizaciones y complementos: los 15 casos de `test_tkt007_asiento.py` (TC-33 a TC-40, con los siete de TC-37) y los 8 de `test_tkt007_fronteras.py` (TC-35 en su parte de AST, TC-41 a TC-45, y los complementos de firma y de la interfaz). Ninguno falla. El rojo previo se documentó en «Fila 4 · rojo» con 20 fallos y 3 pasos. El ciclo de uno en uno no se repitió: el literal se escribió entero y pasó a la primera. La cobertura de los mutantes la confirma la fila 5 sobre el código real.

Gates, desde `backend/`:

```text
uv run mypy .                  -> Success: no issues found in 122 source files
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 122 files already formatted
uv run lint-imports            -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float -> archivos revisados: 13; hallazgos: 0
```

**Refactor:** la única limpieza fue el formateo de la desviación 2. No hubo cambio de comportamiento ni de estructura respecto al literal, así que la suite no necesitó una segunda pasada. **Tests devueltos al tester:** TC-42 por el `arg-type` de la desviación 1. No se edita el test; se anota para que el tester decida si lo quiere tipar de otra forma. **Pendiente de la fila 5:** los mutantes MT-9, MT-11, MT-15, MT-16 y MT-19 sobre el código real, con el SHA-256 de cada archivo.

## Fila 5 · mutación y regresión (entrega A)

Fila sin código de producción: solo se mutó, se comprobó y se restauró. Ningún archivo de producción ni de prueba quedó alterado; las pruebas no se tocaron.

**Método.** Un arnés en Python, fuera del repositorio, aplica un mutante cada vez sobre el archivo indicado, comprueba que el fragmento a sustituir existe exactamente el número de veces previsto, escribe el archivo mutado, ejecuta `uv run pytest` (con `PYTHONUTF8=1`, Docker en marcha, contenedor y plantilla recreados por la propia sesión) sobre los archivos de prueba de este ticket que ejercen ese código, restaura los bytes originales dentro de un `finally` y calcula de nuevo el SHA-256. Los archivos del repositorio tienen finales de línea CRLF; el arnés convierte los fragmentos a CRLF antes de sustituir. Antes de empezar, la línea base de los cinco archivos del ticket era `94 passed in 139.27s`.

**SHA-256 de cada archivo antes de mutar** (idéntico después de cada restauración y al terminar la fila):

| Archivo | SHA-256 |
|---|---|
| `backend/migraciones/versions/v0003_auditoria_bitacora.py` | `37e7e2bea03ce8c1a254f057d61b28b28cd978f468ed95fb0747e5af3a9d3def` |
| `backend/cimenta/auditoria/dominio/asiento.py` | `55ad61d166b4981522bbb234a54501079af7e06cfefdc2df0a9a6256a36a2b4d` |
| `backend/cimenta/auditoria/aplicacion/asentar.py` | `454770e042955d65b3c29633767c9af6ea55018a140408c7bc31c63f6fcb33c0` |
| `backend/cimenta/auditoria/infraestructura/modelos.py` | `8bc4610c64aaa50811ae5783ad58845ab9fa52b781045b4183757bdaad26f9d1` |
| `backend/herramientas/conexion.py` | `94005288345e86632257eb125ca746f89e2ebbc15679e20b3652eb6f510d609f` |
| `backend/tests/conftest.py` | `b76a89a1dbcc5dc8d72824a8456ea4227ccf04bc79cc27619cdfa68d845d0893` |

**Archivos de prueba ejecutados por grupo.** Migración (`v0003`): `test_tkt007_esquema.py` y `test_tkt007_asiento.py`. Dominio y aplicación: `test_tkt007_dominio.py`, `test_tkt007_asiento.py` y `test_tkt007_fronteras.py`. `modelos.py` y `asentar_denegacion`: `test_tkt007_asiento.py`. `conexion.py`: `test_tkt007_motor.py`. `conftest.py`: `test_tkt007_motor.py` y `test_tkt007_asiento.py`.

### Tabla de mutantes

SHA mutado: los primeros 12 caracteres; el SHA «antes» y el «después» son los de la tabla anterior y coincidieron en los 22 casos. «Debe caer» es la columna del diseño; «Cae» son los casos que se pusieron rojos de verdad (cada nombre es `test_tkt007_<...>` abreviado).

| Mutante | Archivo | Mutación | SHA mutado | Debe caer | Cae (salida resumida) | Restaurado |
|---|---|---|---|---|---|---|
| MT-1 | `v0003` | `REVOKE DELETE, TRUNCATE` (sin `UPDATE`) | `a10f44640804` | TC-08, TC-10 | `ca03_update_rechazado`, `ca03_privilegios_exactos` · `2 failed, 37 passed` | sí |
| MT-2 | `v0003` | `REVOKE UPDATE, TRUNCATE` (sin `DELETE`) | `677c32860002` | TC-09, TC-10 | `ca03_delete_y_truncate_rechazados`, `ca03_privilegios_exactos` · `2 failed, 37 passed` | sí |
| MT-3 | `v0003` | `GRANT TRUNCATE ON bitacora TO cimenta_aplicacion` tras el `REVOKE` | `77bfe697a730` | TC-09, TC-10 | `ca03_delete_y_truncate_rechazados`, `ca03_privilegios_exactos` · `2 failed, 37 passed` | sí |
| MT-4 | `v0003` | sin `ix_bitacora_obra_id_ocurrido_en` | `925a03b95abe` | TC-12 | `ca07_indices_con_su_definicion` · `1 failed, 38 passed` | sí |
| MT-5 | `v0003` | `ix_bitacora_regla_negocio` sin `WHERE` | `3cd122430635` | TC-12 | `ca07_indices_con_su_definicion` · `1 failed, 38 passed` | sí |
| MT-6 | `v0003` | sin `ck_bitacora_regla_negocio_formato` | `18ee68047567` | TC-14 | los seis casos de rechazo de `ca12_formato_de_regla_en_la_base` (`minusculas`, `un-digito`, `tres-digitos`, `prefijo-ajeno`, `espacio-final`, `digitos-de-ancho-completo`) · `6 failed, 33 passed` | sí |
| MT-7a | `v0003` | enum sin `DENEGAR` | `a4f4010d6175` | TC-03, TC-38 | `ca01_enum_igual_al_borrador`, `ca10_subir_bajar_subir`, `ca04_denegar_atribuido_al_usuario`, `ca04_denegar_no_confirma`, `ca04_nunca_anonimo_usuario_inexistente` · `5 failed, 34 passed` | sí |
| MT-7b | `v0003` | `AJUSTAR` y `EMITIR` permutados | `9bbc4ecd9a22` | TC-03 | `ca01_enum_igual_al_borrador` · `1 failed, 38 passed` | sí |
| MT-8 | `asiento.py` | `AccionBitacora` con `BORRAR` de más | `923fba948d41` | TC-30 | `ca01_enum_del_dominio_igual_al_borrador`, `ca05_verbo_inexistente['BORRAR']`, `ca05_codigos_del_catalogo`, `ca05_los_defectos_se_acumulan_en_orden`, `ca05_todos_los_campos_mal…`, `ca05_rechazos_de_forma_antes_de_escribir[verbo-inexistente]`, `ca08_funciones_desde_la_interfaz` · `7 failed, 58 passed` | sí |
| MT-9 | `v0003` | sin `fk_bitacora_usuario_id` | `c764ffd4ef36` | TC-02, TC-06, TC-34, TC-40 | `ca01_clave_foranea_solo_hacia_usuario`, `ca01_sin_usuario_autenticado`, `ca02_asiento_fallido_deshace_el_cambio`, `ca04_nunca_anonimo_usuario_inexistente` · `4 failed, 35 passed` | sí |
| MT-10 | `v0003` | bajada sin el bloque `DO` | `84301d943026` | TC-17 | `ca10_la_bajada_no_borra_asientos` · `1 failed, 38 passed` | sí |
| MT-11 | `asentar.py` | `sesion_bd.commit()` tras insertar | `960535247fae` | TC-35, TC-39 | `ca02_el_servicio_no_confirma`, `ca04_denegar_no_confirma`, y por AST `ca02_ningun_servicio_llama_a_commit` · `3 failed, 62 passed` | sí |
| MT-12 | `asiento.py` | `_a_json` admite `float` | `095903b529a9` | TC-25, TC-37 | `ca05_float_y_decimal_rechazados[float]`, `[float-anidado-en-lista]`, `[nan-en-antes]`, `ca05_los_defectos_se_acumulan_en_orden`, `ca05_todos_los_campos_mal…`, `ca05_rechazos_de_forma_antes_de_escribir[importe-float]` · `6 failed, 59 passed` | sí |
| MT-13 | `asiento.py` | `_a_json` admite `Decimal` | `5af986632cd7` | TC-25 | `ca05_float_y_decimal_rechazados[decimal]`, `ca05_todos_los_campos_mal…`, `ca05_rechazos_de_forma_antes_de_escribir[importe-decimal]` · `3 failed, 62 passed` | sí |
| MT-14 | `asiento.py` | `re.match` y `\d` en lugar de `fullmatch` y `[0-9]` | `219556e90059` | TC-24 | `ca05_regla_mal_formada[tres-digitos]`, `[espacio-final]`, `[salto-de-linea-final]`, `[digitos-de-ancho-completo]` · `4 failed, 61 passed` | sí |
| MT-14a | `asiento.py` | solo `match` en lugar de `fullmatch` (sub-mutante) | `11e168e46f0c` | TC-24 | `[tres-digitos]`, `[espacio-final]`, `[salto-de-linea-final]` · `3 failed, 62 passed` | sí |
| MT-14b | `asiento.py` | solo `\d` en lugar de `[0-9]` (sub-mutante) | `2fd956519223` | TC-24 | `[digitos-de-ancho-completo]` · `1 failed, 64 passed` | sí |
| MT-15 | `modelos.py` | `JSONB()` sin `none_as_null=True` (las dos columnas) | `260902cbc8fd` | TC-38 | `ca04_denegar_atribuido_al_usuario`, y además `ca02_cambio_y_asiento_se_confirman_juntos` · `2 failed, 13 passed` | sí |
| MT-16 | `asentar.py` | `asentar_denegacion` con `entidad_tipo="sesion"` | `6234a01e664a` | TC-38 | `ca04_denegar_atribuido_al_usuario` · `1 failed, 14 passed` | sí |
| MT-17 | `conexion.py` | `crear_motor_aplicacion` abre y cierra una conexión antes de devolver el motor | `62a8b37a7f69` | TC-19 | `ca09_crear_el_motor_no_conecta` (`OperationalError`, `ConnectionTimeout`, hacia el puerto 1) · `1 failed, 4 passed in 133.75s` | sí |
| MT-18 | `conftest.py` | `motor_aplicacion` con el rol de migración y su contraseña | `23d82f3e3a88` | TC-20 | Ningún `FAILED`: `16 errors` en la preparación de las pruebas que piden `motor_aplicacion` o `sesion_bd` (entre ellas `ca09_sesion_del_rol_de_aplicacion`), todos con `Failed: El motor de pruebas no es el del rol de aplicación (cimenta_aplicacion): es cimenta_migracion…` · `4 passed, 16 errors` | sí |
| MT-19 | `asentar.py` | `asentar` sin `defectos_de_momento` | `3c3634fa2c6e` | TC-37 | `ca05_rechazos_de_forma_antes_de_escribir[momento-sin-zona]`, `[momento-nulo]`, `[forma-y-momento-juntos-en-orden]` · `3 failed, 12 passed` | sí |

**Sobrevivientes: ninguno.** Los 19 mutantes del diseño y los dos sub-mutantes de `MT-14` dejaron al menos los casos indicados en rojo. No hace falta añadir ningún test.

**Observaciones.**

- `MT-18` no produce `FAILED` sino `ERROR`: la guarda de la *fixture* falla durante la preparación, antes de que el cuerpo de la prueba corra. Es exactamente lo que prevé el diseño («la *fixture* falla con el mensaje de la guarda»), y demuestra que la guarda cumple su cometido: con el propietario, ninguna prueba de permisos llega a ejecutarse.
- `MT-17` tarda 134 s porque el mutante intenta conectar de verdad al puerto 1 y espera el tiempo máximo de conexión; la prueba sin mutar no conecta y termina en milisegundos.
- `MT-7a` además tumba `ca10_subir_bajar_subir`, que compara la fotografía del catálogo entre dos subidas y detecta la diferencia de etiquetas del enum.
- `MT-15` además tumba `ca02_cambio_y_asiento_se_confirman_juntos`, porque su asiento lleva `datos_antes` nulo.
- Los casos que nacieron en verde en las filas 1 a 4 sin mutante asignado en `MT-1` a `MT-19` (TC-04, TC-13, TC-16, TC-21, TC-22, TC-44, TC-45 y TC-55) no se cubren con estos mutantes; el diseño no les asigna ninguno. `MT-20` a `MT-27` son de la entrega B y no se ejecutaron.

### Regresión (TC-R1 a TC-R4)

Desde `backend/`, con `PYTHONUTF8=1` y Docker en marcha. Con los seis archivos restaurados y comprobados por SHA-256.

```text
TC-R1  uv run pytest tests/test_identidad_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_lectura_sin_secretos.py tests/test_identidad_privilegios_por_omision.py
       21 passed in 4.05s
TC-R2  uv run pytest tests/test_identidad_migracion_ciclo.py tests/test_identidad_semilla.py tests/test_identidad_migracion_cli.py tests/test_tkt007_esquema.py::test_tkt007_ca10_subir_bajar_subir
       13 passed in 5.96s
TC-R3  uv run lint-imports                       -> Contracts: 15 kept, 0 broken.   (código 0)
       uv run pytest tests/test_fronteras_dominio.py tests/test_tkt005_fronteras.py
       24 passed in 10.64s
       grep -c ignore_imports pyproject.toml     -> 0
TC-R4  uv run ruff check .                       -> All checks passed!                              (código 0)
       uv run ruff format --check .              -> 122 files already formatted                     (código 0)
       uv run mypy .                             -> Success: no issues found in 122 source files    (código 0)
       uv run python -m herramientas.verificar_float -> archivos revisados: 13; hallazgos: 0        (código 0)
```

Suite completa, `uv run pytest -p no:cacheprovider` con Docker:

```text
tests\test_tkt007_asiento.py ...............                             [ 87%]
tests\test_tkt007_dominio.py ..........................................  [ 92%]
tests\test_tkt007_esquema.py ........................                    [ 95%]
tests\test_tkt007_fronteras.py ........                                  [ 96%]
tests\test_tkt007_motor.py .....                                         [ 97%]
tests\test_verificar_float.py .......................                    [100%]

======================= 786 passed in 188.75s (0:03:08) =======================
```

`git status` y `git diff --stat` al terminar coinciden con los del inicio: cuatro archivos modificados (`interfaz.py`, `conexion.py`, `pyproject.toml`, `conftest.py`) y los archivos nuevos del ticket, y el SHA-256 de los seis archivos mutados es el original. TC-R5 (documentación) no se ejecuta aquí: lo cubre la fila 6.

## Fila 6 · documentación (entrega A)

Se aplicaron, literales de `design.md` («Documentación afectada» y «Enmienda del diseño de TKT-006»), solo las filas marcadas **A**:

- `sdd/tickets/tkt-006/design.md`: los siete cambios de la enmienda (escalera de `url_aplicacion` y `crear_motor_aplicacion`, llamada de `denegacion.py`, contrato C-1, infraestructura, reglas comunes, filas 3 y 4, TC-19, TC-62 y MT-21, `PA-T7` y D-3, documentación afectada y riesgos).
- `sdd/tickets/tkt-006/_index.md`: línea nueva en «Decisiones registradas».
- `docs/03-modelo-datos.md` §2 (fila «Claves foráneas») y §10 (el añadido al párrafo de `DENEGAR` y el párrafo nuevo tras «La tabla se protege…»).
- `.claude/skills/conv-backend-fastapi/SKILL.md` §2 y `.claude/skills/conv-sql-postgres/SKILL.md` §1 (D-6 aprobada).
- `docs/05-tickets-trabajo.md`, TKT-007: el criterio del `DENEGAR` y el «ni `TRUNCATE`» del rol de aplicación. La parte B (consulta, non-goals y TKT-027) no se tocó.

No se editaron `docs/api/openapi.yaml`, `docs/02-arquitectura.md` ni los ADR.

Desviaciones respecto al texto literal, todas de forma:

- Enlace de `docs/03` §10: el texto de la enmienda trae la ruta relativa desde `sdd/tickets/tkt-006/`. En `docs/03` se escribió `07-especificacion-api.md#27-correlación`, con la ruta relativa al documento que lo contiene.
- Fila D-3 del gate: la enmienda la pasa a «Superada por la enmienda de TKT-007…». Se sustituyó la celda de recomendación («**Sí**») y se conservaron las demás celdas.
- Fila 3 de `tkt-006/design.md`: la enmienda cambia la columna de tests a «TC-13 a TC-18». Además, la frase «Rojo: TC-13 a TC-17 y TC-19 fallan» pasó a «Rojo: TC-13 a TC-17 fallan», para no citar TC-19 una vez retirado. TC-19 queda en la tabla de pruebas como «Retirado: lo cubre TC-18 de TKT-007».
- Firma de `asentar_denegacion` en el contrato C-1: se copió la firma del diseño de TKT-007 con `-> uuid.UUID`. El docstring original se conservó.
- `conv-backend-fastapi` §2: la frase nueva se colocó justo después de la frase en negrita «Escribe la bitácora…», como indica «tras» en la enmienda.
- Fuera de la lista, para que `verificar_docs.py` pasara: en este `impl.md` había dos problemas previos. El enlace «Siguiente» a `delta.md` apuntaba a un archivo que crea `/sdd-completar`, y se cambió a texto plano. Una regla escrita con dígitos de ancho completo se reescribió en prosa («tras «RN-»»), como pide la convención.

Verificación, desde la raíz (`PYTHONUTF8=1`):

```text
$ python tools/verificar_docs.py
Documentos analizados: 108
  enlaces relativos 979 · anclas internas 460 · reglas 25 · requisitos no funcionales 19
  preguntas 23 · funcionalidades 52 · historias 9 · tickets 69 · adrs 22
  invariantes 38 · story points 79 · escenarios 162 · codificación 109
✓ Sin problemas.                                  -> exit 0

$ python tools/extraer_mermaid.py
30 diagramas encontrados. Escrito: tools/mermaid-check.html   -> exit 0

$ python -m unittest discover -s tools/tests -v
Ran 6 tests in 0.026s
OK                                                 -> exit 0
```

## Fila 7 · rojo

El tester escribió `backend/tests/test_tkt007_dominio_consulta.py` con TC-46 a TC-48, sin Docker. No se creó ni se tocó ningún archivo de producción: `backend/cimenta/auditoria/dominio/` sigue con `__init__.py` y `asiento.py`, y sin `consulta.py`. Tampoco se tocó `test_tkt007_dominio.py`: su TC-32 recorre `dominio/*.py` con la lista blanca y, cuando exista `consulta.py`, lo examinará sin cambios (importa `collections.abc`, `typing` y `cimenta.auditoria.dominio.asiento`, todos admitidos).

**Cómo se importan los símbolos.** Igual que en la fila 3: `revisar_filtros`, `PAGINA_POR_OMISION`, `TAMANO_PAGINA_POR_OMISION` y `TAMANO_PAGINA_MAXIMO` se importan **dentro** de cada caso (o de la ayuda `_filtros`), y `MENSAJE_PAGINA`, `MENSAJE_TAMANO`, `MENSAJE_ENTERO` y `MENSAJE_RANGO` se piden por nombre con `getattr` desde la ayuda `_mensaje`. Los mensajes que `consulta.py` reutiliza de `asiento.py` (`MENSAJE_REGLA`, `MENSAJE_ACCION`, `MENSAJE_OBLIGATORIO`, `MENSAJE_TEXTO`) se piden a `asiento.py`, que ya existe: el literal tiene una sola fuente. Así cada caso falla por sí solo con el `ModuleNotFoundError` de `cimenta.auditoria.dominio.consulta` y la recolección no se cae. El único import de producción a nivel de módulo es `DefectoDeCampo` bajo `TYPE_CHECKING`, que no se ejecuta.

Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_dominio_consulta.py --tb=no -q -p no:cacheprovider`, desde `backend/`:

```text
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF                                    [100%]
=========================== short test summary info ===========================
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_constantes_de_paginacion
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[todo-nulo]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[por-omision]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[pagina-alta]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[tamano-minimo]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[tamano-maximo]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[regla]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[entidad]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[acciones]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[accion-denegar]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[rango-ordenado]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[rango-vacio-desde-igual-hasta]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[solo-desde]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[solo-hasta]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos[rango-de-instantes]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_filtros_validos_con_todo_a_la_vez
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_la_accion_se_acepta_como_miembro_del_enum
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_paginacion_invalida[pagina-cero]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_paginacion_invalida[pagina-negativa]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_paginacion_invalida[pagina-booleano]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_paginacion_invalida[pagina-cadena]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_paginacion_invalida[pagina-float]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_paginacion_invalida[pagina-nula]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_tamano_de_pagina_invalido[tamano-cero]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_tamano_de_pagina_invalido[tamano-negativo]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_tamano_de_pagina_invalido[tamano-sobre-el-maximo]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_tamano_de_pagina_invalido[tamano-booleano]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_tamano_de_pagina_invalido[tamano-cadena]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_tamano_de_pagina_invalido[tamano-float]
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_regla_mal_formada
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_rango_invertido
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_rango_invertido_de_instantes
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_accion_inexistente
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_varias_acciones_inexistentes_dan_un_solo_defecto
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_entidad_tipo_vacia
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_los_defectos_se_acumulan_en_orden
FAILED tests/test_tkt007_dominio_consulta.py::test_tkt007_ca06_codigos_del_catalogo
37 failed in 0.06s
```

**La razón de cada fallo.**

| Casos | Razón del fallo |
|---|---|
| Los 37 casos recogidos (TC-46 a TC-48) | `ModuleNotFoundError: No module named 'cimenta.auditoria.dominio.consulta'`, lanzado por el import del símbolo pedido dentro del caso (`_filtros` o el propio caso). Se comprobó con `--tb=line`: los 37 fallos llevan exactamente ese mensaje y ninguno otro. Es la razón esperada: el módulo que crea la fila 7 no existe |

Ninguno falla por error de sintaxis, de entorno o de importación de otra cosa: `ruff check` y `ruff format --check` limpios sobre el archivo, y `mypy` sobre él solo marca `import-not-found` de `cimenta.auditoria.dominio.consulta`, que es el mismo rojo visto por el verificador de tipos y desaparece con el módulo.

**Tests que nacieron en verde:** ninguno.

**Casos por escenario.**

| TC | Casos | Qué afirma |
|---|---|---|
| TC-46 | `constantes_de_paginacion`, `filtros_validos` (14 parámetros), `filtros_validos_con_todo_a_la_vez`, `la_accion_se_acepta_como_miembro_del_enum` | `PAGINA_POR_OMISION == 1`, `TAMANO_PAGINA_POR_OMISION == 50`, `TAMANO_PAGINA_MAXIMO == 200`; los bordes `tamano_pagina` 1 y 200, `desde == hasta`, un solo extremo del rango, instantes con zona y un miembro del enum devuelven `()` |
| TC-47 | `paginacion_invalida` (6), `tamano_de_pagina_invalido` (6) | `0` y `-1` en `pagina` y `0`, `-5`, `201` en `tamano_pagina` son `FUERA_DE_RANGO` con `MENSAJE_PAGINA` o `MENSAJE_TAMANO`; booleano, cadena, `float` y nulo son `FORMATO` con `MENSAJE_ENTERO`. Cada caso afirma la tupla completa (campo, código y mensaje), no solo el código |
| TC-48 | `regla_mal_formada`, `rango_invertido`, `rango_invertido_de_instantes`, `accion_inexistente`, `varias_acciones_inexistentes_dan_un_solo_defecto`, `entidad_tipo_vacia`, `los_defectos_se_acumulan_en_orden`, `codigos_del_catalogo` | Una regla fuera de `RN-NN` (incluidos salto de línea final y dígitos de ancho completo), `hasta < desde` (en enteros y en instantes), un verbo inexistente (solo o mezclado con uno válido, y con otra mayúscula), `entidad_tipo` vacía, en blanco o no texto, el orden de los defectos según la firma, y que los cuatro códigos emitidos existan en `CodigoValidacion` |

**Mutantes que estos casos deben atrapar en la fila de mutación** (para que el tester los ejecute sobre la copia): `desde`/`hasta` con `<=` en lugar de `<` (`filtros_validos[rango-vacio-desde-igual-hasta]`), `TAMANO_PAGINA_MAXIMO = 201` (MT-25: `tamano_de_pagina_invalido[tamano-sobre-el-maximo]` y `constantes_de_paginacion`), `minimo` 0 en `pagina` (`paginacion_invalida[pagina-cero]`), `isinstance(valor, bool)` retirado (`paginacion_invalida[pagina-booleano]` y `tamano_de_pagina_invalido[tamano-booleano]`), `any` por `all` en las acciones (`accion_inexistente` con `["AUTORIZAR", "BORRAR"]`).

## Fila 7 · verde y refactor

Se creó `backend/cimenta/auditoria/dominio/consulta.py` copiando el literal de `design.md` («Capas afectadas», `consulta.py`) con sus docstrings, sin cambios de comportamiento. El módulo importa de `cimenta.auditoria.dominio.asiento` `MENSAJE_ACCION`, `MENSAJE_REGLA`, `AccionBitacora`, `DefectoDeCampo`, `regla_bien_formada` y `texto_obligatorio`; de `collections.abc` solo `Sequence`; y de `typing` `Final`, `Protocol` y `Self`. No importa `datetime`, `contrato_error`, `tipos_base` ni ningún otro paquete, y no contiene ningún `float`.

Los 37 casos de TC-46 a TC-48 pasaron a la primera, sin ciclo de uno en uno: el literal del diseño ya fija cada regla y no quedó ningún caso que exigiera código extra. Los tests no se tocaron.

**Refactor.** No se aplicó ninguno. El literal ya es el mínimo que la fila exige y no duplica nada dentro de `consulta.py`. Queda una duplicación entre módulos: la comprobación «es un verbo de `AccionBitacora`» (`isinstance(a, str) and a in AccionBitacora.__members__.values()`) aparece aquí y en `_verbo` de `asiento.py`. Extraerla exigiría tocar `asiento.py`, que ya cierra TC-23 a TC-32, y se deja como candidata para una fila posterior.

Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_dominio_consulta.py tests/test_tkt007_dominio.py`, desde `backend/`, sin Docker:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 79 items

tests\test_tkt007_dominio_consulta.py .................................. [ 43%]
...                                                                      [ 46%]
tests\test_tkt007_dominio.py ..........................................  [100%]

============================= 79 passed in 0.69s ==============================
```

Los 79 son los 37 de TC-46 a TC-48 y los 42 de `test_tkt007_dominio.py`. Entre estos últimos está TC-32, que recorre `dominio/*.py` con la lista blanca y acepta `consulta.py` sin cambios.

Resto de verificaciones, desde `backend/` con `PYTHONUTF8=1`:

```text
== mypy
Success: no issues found in 124 source files

== ruff check
All checks passed!

== ruff format --check
124 files already formatted

== verificar_float
verificar_float: archivos revisados: 14; hallazgos: 0

== lint-imports
Analyzed 79 files, 37 dependencies.
...
Contracts: 15 kept, 0 broken.
```

El `# type: ignore[arg-type]` de `_filtros` en `test_tkt007_dominio_consulta.py` no lo marca `mypy`. Hay dos razones: la configuración de `warn_unused_ignores` solo cubre `cimenta.*.dominio.*` y `cimenta.auditoria.*`, no `tests/`, y además `mypy .` no lo reporta. No se tocó.

## Fila 8 · rojo

El tester escribió `backend/tests/test_tkt007_consulta.py` con TC-49 a TC-57. No se creó ni se tocó ningún archivo de producción: `cimenta/auditoria/interfaz.py` sigue publicando solo `AccionBitacora`, `asentar` y `asentar_denegacion`; `aplicacion/consulta.py` no existe y `repositorio.py` no tiene `CriteriosBitacora`, `contar_asientos` ni `leer_asientos`.

**Cómo se importan los símbolos.** `consultar_bitacora`, `AsientoLeido` y `PaginaBitacora` se importan **dentro** de cada caso desde `cimenta.auditoria.interfaz`, de modo que cada caso falla por sí solo con el `ImportError` del símbolo pedido y la recolección no se cae. Los `MENSAJE_*` se piden por nombre a `cimenta.auditoria.dominio.consulta` y `cimenta.auditoria.dominio.asiento`, que ya existen (filas 3 y 7); el de la zona horaria, que vivirá en `aplicacion/asentar.py`, se escribe literal.

**Ayudas y *fixtures* del archivo** (copiadas de `test_tkt007_asiento.py` y de TKT-005, sin imports entre tests): `validar_contra`, `afirmar_validacion_rechazada`, `sembrar_usuario`, `rutas_de` y las *fixtures* `ana`, `beto` y `sentencias`. Nuevas del archivo, ninguna en `conftest.py` ni `autouse`: `sembrar_asientos` (escribe una lista de `Semilla` con `asentar` en `sesion_bd`, confirma y devuelve los `id` en el mismo orden), `emitidas` (el oyente con los parámetros de cada sentencia) y `muchos_asientos` (los 5,000 asientos de TC-56).

Docker en marcha (`docker info` responde `29.8.2`). Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_consulta.py --tb=no -v -p no:cacheprovider`, desde `backend/`:

```text
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_obra_y_fechas FAILED [  3%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[solo-regla-03] FAILED [  6%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[solo-regla-07] FAILED [  9%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[solo-tipo-de-entidad] FAILED [ 12%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[solo-entidad-id] FAILED [ 16%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[tipo-y-entidad-que-no-coinciden-dan-la-interseccion-vacia] FAILED [ 19%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[dos-acciones] FAILED [ 22%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[una-accion] FAILED [ 25%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[solo-usuario] FAILED [ 29%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[tres-filtros-combinados-son-la-interseccion] FAILED [ 32%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[regla-y-usuario] FAILED [ 35%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[sin-filtros-devuelve-todo] FAILED [ 38%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_orden_con_desempate_estable FAILED [ 41%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_paginacion_por_desplazamiento FAILED [ 45%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[pagina-cero] FAILED [ 48%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[tamano-cero] FAILED [ 51%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[tamano-sobre-el-maximo] FAILED [ 54%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[regla-en-minusculas] FAILED [ 58%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[rango-invertido] FAILED [ 61%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[verbo-inexistente] FAILED [ 64%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[desde-sin-zona] FAILED [ 67%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[hasta-sin-zona] FAILED [ 70%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[los-dos-sin-zona-se-nombran-en-orden] FAILED [ 74%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[desde-sin-zona-sale-solo-aunque-haya-otro-campo-mal] FAILED [ 77%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[hasta-sin-zona-con-desde-con-zona-no-compara-instantes] FAILED [ 80%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[varios-defectos-a-la-vez-en-orden] FAILED [ 83%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_asiento_leido_completo FAILED [ 87%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_la_consulta_no_es_una_ruta PASSED [ 90%]
tests/test_tkt007_consulta.py::test_tkt007_ca11_los_indices_se_usan PASSED [ 93%]
tests/test_tkt007_consulta.py::test_tkt007_ca11_la_consulta_publicada_usa_los_indices FAILED [ 96%]
tests/test_tkt007_consulta.py::test_tkt007_ca08_interfaz_completa FAILED [100%]

======================== 29 failed, 2 passed in 15.72s ========================
```

De 31 casos recogidos (TC-50 son once y TC-53 doce), fallan 29 y pasan 2.

**La razón de cada fallo.** Con `--tb=line`, los 29 llevan un `ImportError` del símbolo pedido y ninguno otro:

| Casos | Razón del fallo |
|---|---|
| TC-49, TC-50 (11), TC-51, TC-53 (12) y el complemento de TC-56 (26 casos) | `ImportError: cannot import name 'consultar_bitacora' from 'cimenta.auditoria.interfaz'`. Es la razón esperada: el símbolo pedido no existe |
| TC-52 | `ImportError: cannot import name 'PaginaBitacora' from 'cimenta.auditoria.interfaz'` (el primero de los dos que pide, por orden alfabético) |
| TC-54, TC-57 | `ImportError: cannot import name 'AsientoLeido' from 'cimenta.auditoria.interfaz'` |

Antes del `ImportError`, cada caso ya levantó `sesion_bd` y, según el caso, sembró `ana`, `beto` o los 5,000 asientos con el rol de aplicación: el contenedor, `alembic upgrade head` y el rol de aplicación funcionan, así que no hay ningún rojo de entorno. `ruff check` y `ruff format --check` están limpios sobre el archivo, y `mypy` sobre él solo marca 15 `attr-defined` de `consultar_bitacora`, `AsientoLeido` y `PaginaBitacora` en `cimenta.auditoria.interfaz`, que es el mismo rojo visto por el verificador de tipos y desaparece con la interfaz publicada.

**Tests que nacieron en verde y por qué:**

- **TC-55** (`test_tkt007_ca06_la_consulta_no_es_una_ruta`) es un contrato que ya se cumple, como prevé el diseño: ninguna ruta de la aplicación contiene `bitacora` y `cimenta/auditoria/api/` solo tiene `__init__.py`. No es vacío: exige que la aplicación tenga alguna ruta (las de documentación), de modo que «ninguna contiene `bitacora`» no se cumpla por una aplicación sin rutas. Lo que lo respalda es el mutante de la fila 9: añadir un `APIRouter` con `/bitacora` a `servidor/fabrica.py` o un archivo a `auditoria/api/`.
- **TC-56** (`test_tkt007_ca11_los_indices_se_usan`) **nace en verde, y es una desviación de la previsión del diseño**, que lo listaba entre los que fallan con `ImportError` de `consultar_bitacora`. La descripción literal de TC-56 es SQL a mano contra los índices que crea la fila 1, sin llamar a `consultar_bitacora`; por eso no puede fallar por esa causa. No es un test vacío: se comprobó con una copia temporal, ya borrada, que cambia los nombres de los índices esperados y falla con el plan completo en el mensaje. El plan real de la consulta por obra es `Limit` → `Incremental Sort` → `Index Scan` sobre `ix_bitacora_obra_id_ocurrido_en`. La regla del diseño (`SET LOCAL enable_seqscan = off`) **no hizo falta**: el planificador usa los dos índices por sí solo con 20 filas de 5,000, así que la fila no queda `⚠ Ajustado` por ese motivo. Para que el caso de la consulta publicada sí nazca en rojo se añadió un complemento, descrito abajo.

**Casos añadidos al diseño** (cada uno nombra el TC del que es complemento y no cambia lo que el diseño pide):

| Caso | Complementa | Qué añade |
|---|---|---|
| `test_tkt007_ca11_la_consulta_publicada_usa_los_indices` | TC-56 | Llama a `consultar_bitacora` por obra y fechas y por regla, captura la sentencia de lectura de la página que SQLAlchemy envía (con sus parámetros) y la repite como `EXPLAIN (FORMAT JSON)` con enlace del lado del cliente: exige `ix_bitacora_obra_id_ocurrido_en` e `ix_bitacora_regla_negocio`. Sin él, el índice se probaría con una consulta escrita a mano y no con la que el caso de uso emite |
| TC-50, once casos parametrizados | TC-50 | Cada filtro solo (regla `RN-03` y `RN-07`, tipo de entidad, `entidad_id`, una y dos acciones, usuario), la intersección vacía de un tipo y un `entidad_id` que no coinciden, tres filtros combinados, regla y usuario, y sin filtros. La matriz son seis asientos que difieren en regla, usuario, tipo, entidad y acción. Cada caso afirma el conjunto de `id` y el `total` |
| TC-51 con seis asientos en el mismo instante, no tres | TC-51 | Con tres empatados, un orden sin desempate coincidiría con el esperado una de cada seis veces; con seis, una de cada 720. Además: siete páginas de uno, cada una con un elemento, y la octava vacía |
| TC-53, doce casos | TC-53 | Además de los seis del diseño: `hasta` sin zona, los dos sin zona (el error de cada uno, en orden), `desde` sin zona junto a una página mala (sale solo el error de zona), `hasta` sin zona con `desde` con zona (sin comparar instantes) y tres defectos a la vez en el orden de la firma |
| TC-52, TC-54 | — | TC-52 comprueba también `pagina` y `tamano_pagina` devueltos y los `id` exactos de cada página; TC-54 compara los `AsientoLeido` completos por igualdad y exige que `accion` sea miembro de `AccionBitacora` (un `StrEnum` también es igual a la cadena) y que `ocurrido_en` lleve zona |

**Mutantes de la fila 9 que estos casos deben atrapar**, para que el tester los ejecute sobre el código real: MT-20 cae en TC-51; MT-21 y MT-22 en TC-49 (el de `desde` entra y el de `hasta` no); MT-23 y MT-24 en TC-52 (la página 2 con el desplazamiento equivocado y `total` igual al largo de la página); MT-25 en TC-47; MT-26 en TC-53 (el oyente de sentencias no queda vacío); MT-27 en TC-50 (`dos-acciones` y `una-accion`); MT-4 (sin `ix_bitacora_obra_id_ocurrido_en`) en TC-56 y en su complemento.

**Verde:** pendiente (agente general por sustitución de `desarrollador-aplicacion`, `haiku`: `CriteriosBitacora`, `_condiciones`, `contar_asientos` y `leer_asientos` en `infraestructura/repositorio.py`; `aplicacion/consulta.py`; `interfaz.py` con `AsientoLeido`, `PaginaBitacora` y `consultar_bitacora` en `__all__`).

**Refactor:** pendiente.

**Tests devueltos al tester:** ninguno.

## Fila 8 · verde y refactor

Se copió el literal de `design.md` («Capas afectadas» y fila 8) en tres archivos, sin cambios de comportamiento:

- `backend/cimenta/auditoria/infraestructura/repositorio.py`: se añaden `CriteriosBitacora` (dataclase de valor, con `acciones` como tupla de `AccionBitacora`), `_condiciones`, `contar_asientos` y `leer_asientos`. `insertar_asiento` queda intacta. Las funciones reciben la `Session` y no confirman.
- `backend/cimenta/auditoria/aplicacion/consulta.py` (nuevo): `AsientoLeido` con once campos, `PaginaBitacora` y `consultar_bitacora`. Valida con `defectos_de_momento` y `rechazar_si_hay_defectos` de `asentar.py` y con `revisar_filtros` del dominio, todo antes de emitir ninguna sentencia. Después cuenta y lee la página con `(pagina - 1) * tamano_pagina` de desplazamiento.
- `backend/cimenta/auditoria/interfaz.py`: publica `AsientoLeido`, `PaginaBitacora` y `consultar_bitacora`. `__all__` queda con exactamente los seis nombres del diseño.

El módulo `consulta.py` no importa ningún otro módulo de `cimenta`. Tampoco se creó nada en `auditoria/api/`, y los tests (`tests/test_tkt007_consulta.py`) no se tocaron.

**Desviaciones respecto al literal del diseño** (todas de tipo o de forma; ninguna cambia lo que la consulta devuelve):

1. `AsientoLeido.datos_antes` y `datos_despues` se tipan como `Mapping[str, object] | None` en lugar de `dict[str, object] | None`. `mypy .` marcaba `tests/test_tkt007_consulta.py:609`: el test construye un `AsientoLeido` con un `dict[str, str]`, y `dict` es invariante en su valor. `Mapping` es covariante, así que el test cumple sin editarlo. No se toca el test.
2. En los tres archivos nuevos o tocados, `datetime` se importa como `dt` (`import datetime as dt`), igual que en el `repositorio.py` previo, y las anotaciones van como `dt.datetime`. Es solo un cambio de nombre.
3. `ColumnElement` se importa de `sqlalchemy.sql.expression` (el literal no fijaba la ruta).
4. `ruff format` reparte en varias líneas las sentencias de una línea que el literal escribía compactas (`if c.x is not None: condiciones.append(...)`). El contenido es el mismo.

**Refactor.** No se aplicó ninguno. Las desviaciones 2 a 4 son formato o nombres, no lógica.

**Verde.** Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_consulta.py --tb=short -v -p no:cacheprovider`, desde `backend/`, con Docker en marcha. Es la ejecución de la primera pasada, antes de la desviación 1; la segunda pasada, tras ella, se reproduce al final:

```text
collected 31 items

tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_obra_y_fechas PASSED [  3%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_filtro_por_regla_y_demas[solo-regla-03] PASSED [  6%]
... (las 11 variantes de TC-50 PASSED)
tests/test_tkt007_consulta.py::test_tkt007_ca06_orden_con_desempate_estable PASSED [ 41%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_paginacion_por_desplazamiento PASSED [ 45%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_rechazos_sin_tocar_la_base[pagina-cero] PASSED [ 48%]
... (las 12 variantes de TC-53 PASSED)
tests/test_tkt007_consulta.py::test_tkt007_ca06_asiento_leido_completo PASSED [ 87%]
tests/test_tkt007_consulta.py::test_tkt007_ca06_la_consulta_no_es_una_ruta PASSED [ 90%]
tests/test_tkt007_consulta.py::test_tkt007_ca11_los_indices_se_usan PASSED [ 93%]
tests/test_tkt007_consulta.py::test_tkt007_ca11_la_consulta_publicada_usa_los_indices PASSED [ 96%]
tests/test_tkt007_consulta.py::test_tkt007_ca08_interfaz_completa PASSED [100%]

============================= 31 passed in 7.88s ==============================
```

Con esto pasan los 29 que estaban en rojo (TC-49 a TC-54, y los complementos de TC-50, TC-53 y TC-56) y los dos que nacieron en verde (TC-55 y TC-56 de índices). TC-56 pasa, con su complemento sobre la sentencia que emite `consultar_bitacora`.

**Verificación tras la desviación 1.** Salida real, desde `backend/` con `PYTHONUTF8=1`:

```text
== pytest consulta
...............................                                          [100%]
31 passed in 6.35s

== mypy
Success: no issues found in 126 source files

== ruff check
All checks passed!

== ruff format
126 files already formatted

== lint-imports
Contracts: 15 kept, 0 broken.
```

Antes de la desviación 1, `mypy .` daba un único error (`tests/test_tkt007_consulta.py:609`, `arg-type`); el resto ya estaba limpio.

**Tests devueltos al tester:** ninguno. El caso de `mypy` del punto 1 es un tipo que el test no puede satisfacer con `dict` invariante. Si el tester prefiere que el test anote `dict[str, object]`, la desviación 1 se revierte y el test se edita en su fila.

**Verificación pendiente.** `verificar_float` y la suite completa de `backend/` no se corrieron en esta fila; solo los tests de `consulta`, `mypy`, `ruff` y `lint-imports`.

## Fila 9 · mutación y regresión (entrega B)

Fila sin código de producción nuevo: solo se mutó, se comprobó y se restauró. No se añadió ni se editó ningún test, porque ningún mutante sobrevivió.

**Método.** El mismo arnés de la fila 5, fuera del repositorio. Para cada mutante comprueba que el fragmento a sustituir existe exactamente una vez, escribe el archivo mutado, ejecuta `uv run pytest` con `PYTHONUTF8=1` y Docker en marcha (PostgreSQL real por testcontainers, plantilla recreada por la propia sesión) sobre `tests/test_tkt007_consulta.py` y `tests/test_tkt007_dominio_consulta.py`, restaura los bytes originales dentro de un `finally` y calcula de nuevo el SHA-256. Línea base de esos dos archivos antes de mutar: `68 passed in 6.46s`.

**SHA-256 de cada archivo antes de mutar** (idéntico después de cada restauración y al terminar la fila):

| Archivo | SHA-256 |
|---|---|
| `backend/cimenta/auditoria/infraestructura/repositorio.py` | `ec1d3eca6cb8508b4407638fcb1afc3d409dba4f2e6a542d48ac00fe16cf7dab` |
| `backend/cimenta/auditoria/aplicacion/consulta.py` | `6776c825f3e512f9b5f8871e08a4a9e97d32a43bfcab9bc21405fc0aa801b58a` |
| `backend/cimenta/auditoria/dominio/consulta.py` | `88bc830960a350b0a53d7bda88403367c119c314eac5e105e1002cb1527b8540` |
| `backend/migraciones/versions/v0003_auditoria_bitacora.py` | `37e7e2bea03ce8c1a254f057d61b28b28cd978f468ed95fb0747e5af3a9d3def` |
| `backend/servidor/fabrica.py` | `33d291e90cb50e91a7b9b72fb7c4d36c41e20c1bf86b87e418767a4e190ce5e0` |

### Tabla de mutantes

SHA mutado: los primeros 12 caracteres. El SHA «antes» y el «después» son los de la tabla anterior y coincidieron en los 11 casos. «Debe caer» es la columna del diseño; «Cae» son los casos que se pusieron rojos de verdad (cada nombre es `test_tkt007_ca06_<...>` abreviado, salvo donde se indica).

| Mutante | Archivo | Mutación | SHA mutado | Debe caer | Cae (salida resumida) | Restaurado |
|---|---|---|---|---|---|---|
| MT-20 | `repositorio.py` | `leer_asientos` ordena solo por `ocurrido_en DESC` (sin `id DESC`) | `e4510d5e9378` | TC-51 | `orden_con_desempate_estable` · `1 failed, 67 passed` | sí |
| MT-21 | `repositorio.py` | `hasta` inclusivo (`<=`) | `b8ba43cc9f43` | TC-49 | `filtro_por_obra_y_fechas` · `1 failed, 67 passed` | sí |
| MT-22 | `repositorio.py` | `desde` exclusivo (`>`) | `397319fcc82f` | TC-49 | `filtro_por_obra_y_fechas` · `1 failed, 67 passed` | sí |
| MT-23 | `aplicacion/consulta.py` | desplazamiento `pagina * tamano_pagina` | `cc1c78122ded` | TC-52 | `paginacion_por_desplazamiento`, además `filtro_por_obra_y_fechas`, `orden_con_desempate_estable`, `asiento_leido_completo` y las diez variantes de `filtro_por_regla_y_demas` (la primera página ya salta una página entera) · `14 failed, 54 passed` | sí |
| MT-24 | `aplicacion/consulta.py` | `total = len(elementos)` (largo de la página) | `770480198362` | TC-52 | `paginacion_por_desplazamiento` · `1 failed, 67 passed` | sí |
| MT-25 | `dominio/consulta.py` | `TAMANO_PAGINA_MAXIMO = 201` | `7db72969c8df` | TC-47 | `dominio_consulta::tamano_de_pagina_invalido[tamano-sobre-el-maximo]`, `dominio_consulta::constantes_de_paginacion`, `dominio_consulta::los_defectos_se_acumulan_en_orden`, `consulta::rechazos_sin_tocar_la_base[tamano-sobre-el-maximo]` · `4 failed, 64 passed` | sí |
| MT-26 | `aplicacion/consulta.py` | `consultar_bitacora` cuenta antes de validar | `b4657539cc23` | TC-53 | las 12 variantes de `rechazos_sin_tocar_la_base` (el oyente de sentencias ya no queda vacío) · `12 failed, 56 passed` | sí |
| MT-27 | `repositorio.py` | `_condiciones` ignora `acciones` | `e54bb7662faf` | TC-50 | `filtro_por_regla_y_demas[dos-acciones]`, `[una-accion]` · `2 failed, 66 passed` | sí |
| MT-4b | `v0003` | sin `ix_bitacora_obra_id_ocurrido_en`, ejecutado sobre `test_tkt007_consulta.py` | `925a03b95abe` | TC-56 y su complemento | `ca11_los_indices_se_usan`, `ca11_la_consulta_publicada_usa_los_indices` · `2 failed, 29 passed` | sí |
| MT-28a | `servidor/fabrica.py` | ruta `GET /api/v1/bitacora` añadida a la aplicación (el mutante que la fila 7 anota para TC-55) | `457ca870732c` | TC-55 | `ca06_la_consulta_no_es_una_ruta` · `1 failed` | sí |
| MT-28b | `cimenta/auditoria/api/rutas.py` (archivo nuevo, borrado después) | un segundo archivo en `auditoria/api/` | — | TC-55 | `ca06_la_consulta_no_es_una_ruta` · `1 failed` | sí (archivo borrado) |

**Sobrevivientes: ninguno.** Los ocho mutantes del diseño (`MT-20` a `MT-27`), `MT-4b` (el complemento de `MT-4` que la fila 5 no podía ejecutar) y los dos mutantes de TC-55 que anotó la fila 7 dejaron en rojo, como mínimo, los casos indicados. No hace falta añadir ningún test.

**Observaciones.**

- `MT-26` se aplicó insertando, antes de la primera validación, una llamada a `repositorio.contar_asientos` con criterios vacíos. Es la forma mínima de «contar antes de validar» sin que `AccionBitacora(a)` lance antes por un verbo inexistente.
- `MT-28b` no tiene SHA mutado: crea un archivo que no existía. Se comprobó que `rutas.py` ya no existe y que `git status` no lo lista.
- `MT-4b` no sustituye a `MT-4` de la fila 5: lo repite sobre el archivo de la consulta, que es donde TC-56 y su complemento lo atrapan, como pedía el diseño.
- Con `MT-23` caen más tests que el de TC-52 porque con ese desplazamiento la primera página ya omite una página entera: es el comportamiento esperado y la mejor señal de que el desplazamiento está bien fijado.

### Regresión (TC-R1 a TC-R5)

Desde `backend/`, con `PYTHONUTF8=1`, Docker en marcha y los cinco archivos mutados restaurados y comprobados por SHA-256.

```text
TC-R1  uv run pytest tests/test_identidad_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_lectura_sin_secretos.py tests/test_identidad_privilegios_por_omision.py
       21 passed in 4.02s
TC-R2  uv run pytest tests/test_identidad_migracion_ciclo.py tests/test_identidad_semilla.py tests/test_identidad_migracion_cli.py tests/test_tkt007_esquema.py::test_tkt007_ca10_subir_bajar_subir
       13 passed in 5.74s
TC-R3  uv run lint-imports                       -> Contracts: 15 kept, 0 broken.   (código 0)
       uv run pytest tests/test_fronteras_dominio.py tests/test_tkt005_fronteras.py
       24 passed in 10.86s
       grep -c ignore_imports pyproject.toml     -> 0
TC-R4  uv run ruff check .                       -> All checks passed!                              (código 0)
       uv run ruff format --check .              -> 126 files already formatted                     (código 0)
       uv run mypy .                             -> Success: no issues found in 126 source files    (código 0)
       uv run python -m herramientas.verificar_float -> archivos revisados: 14; hallazgos: 0        (código 0)
```

Suite completa, `uv run pytest -p no:cacheprovider` con Docker (código de salida 0):

```text
tests\test_tkt005_regresion.py .........                                 [ 78%]
tests\test_tkt007_asiento.py ...............                             [ 80%]
tests\test_tkt007_consulta.py ...............................            [ 83%]
tests\test_tkt007_dominio.py ..........................................  [ 88%]
tests\test_tkt007_dominio_consulta.py .................................. [ 92%]
...                                                                      [ 92%]
tests\test_tkt007_esquema.py ........................                    [ 95%]
tests\test_tkt007_fronteras.py ........                                  [ 96%]
tests\test_tkt007_motor.py .....                                         [ 97%]
tests\test_verificar_float.py .......................                    [100%]

======================= 854 passed in 192.63s (0:03:12) =======================
```

TC-R5, desde la raíz:

```text
python tools/verificar_docs.py                       -> Sin problemas. (código 0; invariantes 38, escenarios 162)
python tools/extraer_mermaid.py                      -> Escrito: tools\mermaid-check.html (código 0; el archivo está en .gitignore)
python -m unittest discover -s tools/tests -v        -> Ran 6 tests ... OK (código 0)
```

Los 21 archivos nuevos del ticket (`.py` y `.md`, incluidos los de `sdd/tickets/tkt-006` y `tkt-007`) se leyeron como bytes: ninguno lleva BOM y ninguno contiene `CRLF`. Este mismo `impl.md` se comprobó después de la edición. La sección «Verificación final» sigue pendiente y no la rellena esta fila.

**Estado del árbol.** `git status` y `git diff --stat` coinciden con los del inicio: ocho archivos modificados (los de la entrega A más los dos `SKILL.md`, `03-modelo-datos.md` y `05-tickets-trabajo.md`, que no son de esta fila) y los archivos nuevos del ticket. El SHA-256 de los cinco archivos mutados es el original y `auditoria/api/` solo tiene `__init__.py`. Ningún archivo de producción ni de prueba quedó alterado.

## Fila 10 · documentación (entrega B)

Se aplicaron, literales de `design.md` («Documentación afectada»), solo las filas marcadas **B**:

- `docs/05-tickets-trabajo.md`, TKT-007: el criterio de la consulta pasa a «como caso de uso `consultar_bitacora` publicado en `cimenta.auditoria.interfaz`. **Sin ruta HTTP**: `GET /api/v1/bitacora` la monta TKT-027», y los non-goals a «No monta la ruta `GET /api/v1/bitacora` ni implementa interfaz de consulta: la ruta la monta TKT-027 con `exigir_rol`, y completa el nombre del usuario.».
- `docs/05-tickets-trabajo.md`, TKT-027: «**Depende de** TKT-025, TKT-006, TKT-007», y el criterio de `GET /api/v1/bitacora` añade al final la frase sobre la ruta montada desde la raíz de composición con `exigir_rol("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS")` y la conversión del `usuario_id` en `UsuarioResumen` por la interfaz de `identidad`.

No se editaron `docs/api/openapi.yaml`, `docs/02-arquitectura.md`, el glosario ni los ADR. No hubo desviaciones del texto literal.

En `design.md`, columna «Estado» de «Orden de implementación»: filas 1, 2, 3, 5, 6, 7, 9 y 10 a `✓ Hecho`; filas 4 y 8 a `⚠ Ajustado`. La fila 4 lleva el override acotado de `mypy` en `backend/pyproject.toml` para TC-42 (`impl.md`, «Fila 4 · verde y refactor»). La fila 8 lleva `Mapping` en lugar de `dict` en `AsientoLeido`, y TC-56 nace en verde con el complemento que usa la consulta publicada («Fila 8 · rojo» y «verde y refactor»).

Verificación, desde la raíz (`PYTHONUTF8=1`):

```text
$ python tools/verificar_docs.py
Documentos analizados: 108
  enlaces relativos 979 · anclas internas 460 · reglas 25 · requisitos no funcionales 19
  preguntas 23 · funcionalidades 52 · historias 9 · tickets 69 · adrs 22
  invariantes 38 · story points 79 · escenarios 162 · codificación 109
✓ Sin problemas.                                  -> exit 0

$ python tools/extraer_mermaid.py
30 diagramas encontrados. Escrito: tools/mermaid-check.html   -> exit 0

$ python -m unittest discover -s tools/tests -v
Ran 6 tests in 0.013s
OK                                                 -> exit 0
```

## Ciclo de corrección 1

Corrección de los hallazgos de la auditoría de arquitectura. Son ediciones de texto: no cambia código ni comportamiento, y no se añadió ningún test.

| ID | Severidad | Estado | Qué línea cambió |
|---|---|---|---|
| F001 | Menor | Resuelto | `.claude/agents/desarrollador-sql.md`, línea 33 (fila «Bitácora sin modificación»): pasa de «disparador que rechaza `UPDATE` y `DELETE`» a «sin `UPDATE`, `DELETE` ni `TRUNCATE` para el rol de aplicación (invariante 10, TKT-007)», alineada con `.claude/skills/conv-sql-postgres/SKILL.md` y con la decisión D-6. `sdd/00-propuesta-toolkit.md`, línea 186: se conserva la frase original y se añade la nota «histórico: TKT-007 (D-6) lo sustituyó por privilegios para la bitácora», porque es un documento de propuesta. |
| F002 | Menor | Resuelto | (a) `sdd/tickets/tkt-006/design.md`, línea 571 (fila 3): el rojo esperado pasa a «`ModuleNotFoundError`», sin «`AttributeError` (`url_aplicacion`)», porque `url_aplicacion` ya existe; el título pasa a «Configuración y contraseñas (A)», sin «y URL». (b) `sdd/tickets/tkt-006/spec.md`, línea 505 (`PA-T7`): pasa a «Resuelta por TKT-007: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`». (c) `sdd/tickets/tkt-006/spec.md`, línea 25 (tabla de estado de partida): la fila de URL y motor indica que `url_aplicacion` y `crear_motor_aplicacion` los entrega TKT-007; los modelos ORM y la normalización del correo siguen sin existir, y se mantiene la referencia a `PA-T10`. |
| F003 | — | Aceptado sin cambio | Sin cambio en código. Nota del auditor: cuando el tester reabra TC-42, el override de `pyproject.toml` (`module = ["test_tkt007_fronteras"]`, `disable_error_code = ["arg-type"]`, «Fila 4 · verde y refactor») debe sustituirse por un `cast` o por un *ignore* de línea en el propio test. Esa decisión queda para el tester, según lo anotado en «Fila 4 · verde y refactor». |

## Revisión · ciclo 1 · rojo de F001 y arreglo de F003

Estos dos hallazgos son los de la auditoría de `/sdd-revisar` (los de «Ciclo de corrección 1», más arriba, son los de la auditoría de arquitectura y llevan otra numeración). El tester abre la fase roja de `F001` y arregla `F003`. No se creó ni se tocó ningún archivo de producción: `cimenta/auditoria/dominio/asiento.py` sigue como estaba.

### F003 · el override de mypy sale

`backend/pyproject.toml` ya no tiene el bloque `[[tool.mypy.overrides]]` con `module = ["test_tkt007_fronteras"]` y `disable_error_code = ["arg-type"]`. En su lugar, TC-42 (`test_tkt007_ca04_sustituible_con_monkeypatch`, en `backend/tests/test_tkt007_fronteras.py`) lleva `# type: ignore[arg-type]` en las tres líneas del argumento que pasan una cadena a propósito (`"sesion"`, `usuario_id="ana"` y `ocurrido_en="T0"`). Un solo ignore no basta: mypy informa cada argumento en su propia línea cuando la llamada ocupa varias. Sin los ignores, y con el override ya retirado, mypy marcaba exactamente esos tres errores:

```text
tests\test_tkt007_fronteras.py:209: error: Argument 1 to "asentar_denegacion" has incompatible type "str"; expected "Session"  [arg-type]
tests\test_tkt007_fronteras.py:209: error: Argument "usuario_id" to "asentar_denegacion" has incompatible type "str"; expected "UUID"  [arg-type]
tests\test_tkt007_fronteras.py:209: error: Argument "ocurrido_en" to "asentar_denegacion" has incompatible type "str"; expected "datetime"  [arg-type]
Found 3 errors in 1 file (checked 126 source files)
```

Con los ignores de línea, desde `backend/`:

```text
$ PYTHONUTF8=1 uv run mypy .
Success: no issues found in 126 source files
$ PYTHONUTF8=1 uv run mypy --warn-unused-ignores tests/test_tkt007_fronteras.py tests/test_tkt007_asiento.py
Success: no issues found in 2 source files
$ uv run ruff check .          -> All checks passed!
$ uv run ruff format --check . -> 126 files already formatted
```

La segunda orden fuerza `warn_unused_ignores`, que el proyecto solo activa en las capas estrictas y no en los tests: demuestra que ninguno de los tres ignores es sobrante.

### F001 · rojo

Se añadieron 16 casos que exigen que un `U+0000` se rechace en el dominio como `FORMATO`. Docker en marcha (`docker info` responde `29.8.2`).

- `backend/tests/test_tkt007_dominio.py`, sin Docker, **TC-58**:
  - `test_tkt007_ca05_nul_en_texto_rechazado`, diez parámetros: `motivo` con NUL, `motivo` que es solo NUL, `entidad_tipo`, cadena de `datos_despues`, cadena de `datos_antes`, clave de `datos_despues`, clave dentro de un mapa anidado, cadena en un mapa dentro de una lista (`datos_despues.renglones[0].nota`), cadena directa en una lista (`datos_despues.etiquetas[1]`) y cadena en tres mapas anidados (`datos_antes.a.b.c`). Cada uno exige el defecto único `DefectoDeCampo(ruta, "FORMATO", MENSAJE_NUL)`.
  - `test_tkt007_ca05_nul_en_varios_campos_se_acumula_en_orden`: NUL en `entidad_tipo`, `motivo`, `datos_antes` y `datos_despues` a la vez da cuatro defectos, en el orden de los campos.
  - `test_tkt007_ca05_texto_sin_nul_pasa_aunque_lleve_otros_controles`: saltos de línea, tabulador, `\x01`, acentos y una clave con tabulador siguen formando el asiento, intactos. Nace en verde a propósito: es la guarda contra el exceso de celo del arreglo (rechazar todo carácter de control), no un rojo.
- `backend/tests/test_tkt007_asiento.py`, con Docker, **TC-59**: cuatro parámetros nuevos en `FORMAS_RECHAZADAS` (`nul-en-motivo`, `nul-en-entidad-tipo`, `nul-en-cadena-de-datos`, `nul-en-clave-de-datos`), que pasan por `test_tkt007_ca05_rechazos_de_forma_antes_de_escribir`. Ese caso comprueba la `ValidacionRechazada`, la lista exacta de errores, el cuerpo válido contra `ErrorValidacion`, el oyente de sentencias vacío y que no hay ningún asiento en la base.

**Nombre que debe producir el dominio.** Los casos piden por nombre `MENSAJE_NUL` en `cimenta.auditoria.dominio.asiento` (con `getattr`, como el resto de los mensajes). Ningún mensaje existente encajaba: `MENSAJE_TEXTO` dice «El valor es un texto.» y `MENSAJE_VALOR_NO_JSON` habla de importes. El literal lo escoge el desarrollador; los tests no lo fijan, solo exigen que el defecto lleve ese `MENSAJE_NUL`. El código es `FORMATO`.

**Campo del defecto (la ruta).** `motivo` y `entidad_tipo` nombran su campo. Una cadena en `datos_*` nombra la ruta del valor, con la misma convención de `_a_json` (`datos_despues.nota`, `datos_despues.renglones[0].nota`, `datos_despues.etiquetas[1]`). **Una clave con NUL nombra la ruta del objeto que la contiene** (`datos_despues` o `datos_despues.lineas`), nunca la ruta con la clave dentro: la misma convención que `MENSAJE_CLAVE_NO_CADENA`, y evita que el propio NUL viaje en el campo del contrato de error. Con una clave con NUL el defecto es uno solo; no se exige un segundo defecto por el valor.

El NUL se busca con `"\x00" in valor`, no con `strip()`: `"\x00".strip()` no queda vacío, por eso el caso `motivo-solo-nul` espera `FORMATO` y no `OBLIGATORIO`. `regla_negocio` y `accion` ya rechazan el NUL por su forma (`fullmatch` y el enum), y no se probaron aparte.

Salida real de `PYTHONUTF8=1 uv run pytest tests/test_tkt007_dominio.py tests/test_tkt007_asiento.py --tb=line -q -p no:cacheprovider`, desde `backend/`:

```text
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[motivo]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[motivo-solo-nul]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[entidad-tipo]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[cadena-de-datos-despues]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[cadena-de-datos-antes]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[clave-de-datos-despues]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[clave-anidada-en-mapa]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[cadena-en-mapa-dentro-de-lista]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[cadena-directa-en-lista]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_texto_rechazado[cadena-en-mapas-anidados]
FAILED tests/test_tkt007_dominio.py::test_tkt007_ca05_nul_en_varios_campos_se_acumula_en_orden
FAILED tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[nul-en-motivo]
FAILED tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[nul-en-entidad-tipo]
FAILED tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[nul-en-cadena-de-datos]
FAILED tests/test_tkt007_asiento.py::test_tkt007_ca05_rechazos_de_forma_antes_de_escribir[nul-en-clave-de-datos]
15 failed, 58 passed in 11.16s
```

**Razón de cada fallo.** Los 11 de `test_tkt007_dominio.py` fallan en `assert resultado.asiento is None`: el dominio acepta el NUL y devuelve un `Asiento` con `motivo='Excede\x00 el presupuesto'`, `entidad_tipo='requisicion\x00'` o los datos con el NUL dentro. La aserción del asiento va antes de pedir `MENSAJE_NUL`, así que no caen por un `AttributeError` del nombre ausente. Los 4 de `test_tkt007_asiento.py` fallan porque el asiento llega a la base y el motor lo rechaza, que es exactamente el síntoma de `F001`:

```text
sqlalchemy.exc.DataError: (psycopg.DataError) PostgreSQL text fields cannot contain NUL (0x00) bytes      (motivo, entidad_tipo)
sqlalchemy.exc.DataError: (psycopg.errors.UntranslatableCharacter) unsupported Unicode escape sequence
    DETAIL:  \u0000 cannot be converted to text.                                                          (cadena y clave de datos)
```

Ningún fallo es de importación, de sintaxis ni de entorno. El caso en verde de TC-58 se investigó: pasa porque el dominio de hoy no rechaza ningún carácter de control, y debe seguir pasando tras el arreglo.

**Suite completa en este punto** (`PYTHONUTF8=1 uv run pytest --tb=no -q -p no:cacheprovider`): `15 failed, 855 passed in 192.14s (0:03:12)`. Los 15 fallos son los de arriba y no hay ningún otro: el resto de la suite sigue en verde (854 anteriores más el caso de control). `uv run lint-imports`: 15 contratos cumplidos, 0 rotos.

**Para el desarrollador.** Rechazar `\x00` en `texto_obligatorio` (después de la comprobación de vacío, para que `"  "` siga siendo `OBLIGATORIO`) y en `_a_json`, para las cadenas y para las claves, con `FORMATO` y `MENSAJE_NUL`; la ruta de una clave es la del objeto que la contiene. `asentar_denegacion` pasa por el mismo `revisar_asiento`, de modo que el arreglo también lo cubre, aunque este ciclo no añadió un caso aparte para él.

## Revisión · ciclo 1 · verde de F001

Fase verde del hallazgo F001 de la auditoría de `/sdd-revisar`: el dominio rechaza un `U+0000` como `FORMATO` antes de llegar al motor, en lugar de dejar que PostgreSQL lance `DataError`. La decisión de rechazarlo en el dominio es del usuario. Lo implementa `corrector-revision` sobre el rojo de la sección anterior; los tests no se tocaron.

### Cambios

Único archivo tocado: `backend/cimenta/auditoria/dominio/asiento.py`.

- Constante nueva `MENSAJE_NUL`, con el literal del mensaje de FORMATO.
- `texto_obligatorio`: después del chequeo de vacío, un texto con `\x00` produce `DefectoDeCampo(campo, "FORMATO", MENSAJE_NUL)`. El chequeo de vacío va primero, así que `"  "` sigue siendo `OBLIGATORIO` y `"\x00"` (que no queda vacío tras `strip()`) da `FORMATO`.
- `_a_json`: una cadena con `\x00` produce `FORMATO`/`MENSAJE_NUL` en la ruta del valor (`datos_despues.renglones[0].nota`, por ejemplo).
- `_a_json`: una clave con `\x00` produce un único defecto en la ruta del objeto que la contiene, igual que `MENSAJE_CLAVE_NO_CADENA`, y se salta su valor, de modo que no aparece un segundo defecto por el valor.
- Un texto sin `\x00` no cambia: los saltos de línea, tabuladores, `\x01` y los acentos siguen pasando. Lo comprueba TC-58 complemento, que ya estaba en verde.

No se añadió `# noqa`, `# type: ignore`, ni excepción alguna al contrato de `import-linter`. Solo biblioteca estándar; sin `float` ni `datetime`.

### Verificación

Desde `backend/`, con `PYTHONUTF8=1`.

```text
$ uv run pytest tests/test_tkt007_dominio.py tests/test_tkt007_asiento.py --tb=short -q -p no:cacheprovider
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 5.21s

$ uv run mypy .
Success: no issues found in 126 source files

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
126 files already formatted

$ uv run python -m herramientas.verificar_float
verificar_float: archivos revisados: 14; hallazgos: 0

$ uv run lint-imports
Analyzed 80 files, 49 dependencies.
Contracts: 15 kept, 0 broken.
```

Los 15 casos nuevos (TC-58, diez parámetros, más el de varios campos, y TC-59, cuatro parámetros) pasaron de rojo a verde. El caso de control de TC-58 sigue en verde, como exige el diseño.

Una primera pasada de `ruff format --check` marcó la constante `MENSAJE_NUL` por partir en tres líneas. Se aplicó `ruff format` solo a `asiento.py`; el cambio es de forma y no altera el contenido.

**Suite completa.** Este ciclo no la ejecutó: el encargo pedía los dos archivos de test y los linters. Queda pendiente para la reauditoría.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 1 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | — |
| Fila 2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 2 · verde y refactor | agente general por sustitución de `desarrollador-aplicacion` (ausente, D-8) | `haiku` | `haiku` | — |
| Fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde y refactor | `desarrollador-dominio` | `haiku` | `haiku` | — |
| Fila 4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · verde y refactor | agente general por sustitución de `desarrollador-aplicacion` (ausente, D-8) | `haiku` | `haiku` | — |
| Fila 5 · mutación y regresión (A) | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 6 · documentación (A) | orquestador con `conv-documentacion`, por sustitución | `haiku` | `haiku` | — |
| Fila 7 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 7 · verde y refactor | `desarrollador-dominio` | `haiku` | `haiku` | — |
| Fila 8 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 8 · verde y refactor | agente general por sustitución de `desarrollador-aplicacion` (ausente, D-8) | `haiku` | `haiku` | — |
| Fila 9 · mutación y regresión (B) | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 10 · documentación (B) | orquestador con `conv-documentacion`, por sustitución | `haiku` | `haiku` | — |
| Ciclo de corrección 1 · F001 y F002 (ediciones de texto) | `corrector-revision` | `haiku` | `haiku` | — |
| Revisión · ciclo 1 · rojo de F001 y arreglo de F003 | `tester-backend` | `sonnet` | `sonnet` | — |
| Revisión · ciclo 1 · verde de F001 | `corrector-revision` | `haiku` | `haiku` | — |

## Resultado contra los criterios de aceptación

| Criterio | Resultado | Pruebas |
|---|---|---|
| `CA-1` tabla y enum | Cumplido | TC-01 a TC-06, TC-30 |
| `CA-2` asiento en la misma transacción | Cumplido | TC-33 a TC-35 |
| `CA-3` inmutabilidad a nivel de motor | Cumplido | TC-07 a TC-11 |
| `CA-4` `DENEGAR` atribuido al usuario | Cumplido | TC-38 a TC-42 |
| `CA-5` forma del asiento | Cumplido | TC-23 a TC-29, TC-31, TC-36, TC-37 |
| `CA-6` consulta | Cumplido | TC-46 a TC-55 |
| `CA-7` índices | Cumplido | TC-12, TC-13 |
| `CA-8` interfaz y fronteras | Cumplido | TC-32, TC-43 a TC-45, TC-57 |
| `CA-9` motor y sesión | Cumplido | TC-18 a TC-22 |
| `CA-10` migración | Cumplido | TC-15 a TC-17 |
| `CA-11` índices usados (`S1`) | Cumplido | TC-56 y su complemento |
| `CA-12` formato de la regla en la base (`S2`) | Cumplido | TC-14 |
| `CA-R1` a `CA-R5` | Cumplidos | TC-R1 a TC-R5 |

## Verificación final

- `uv run pytest` completo con Docker: `854 passed` al cerrar `/sdd-ejecutar` y `870 passed` tras el ciclo de corrección de `/sdd-revisar` (15 casos nuevos de `\x00` y uno de control).
- `ruff check`, `ruff format --check`, `mypy` (126 archivos) y `verificar_float` (14 archivos, 0 hallazgos) en verde.
- `uv run lint-imports`: 15 contratos cumplidos, 0 rotos, sin `ignore_imports`.
- `alembic heads`: una sola cabeza, `0003`.
- `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y los tests de `tools/` con código 0.
- Mutación: los mutantes de las dos entregas cayeron, ninguno sobrevivió y todos los archivos se restauraron con su SHA-256.
- Auditoría de arquitectura y esquema: `REQUIERE CAMBIOS` con `F001` a `F003` (Menores); ciclo de corrección 1; reauditoría `APROBADO`. En `/sdd-revisar`, una pasada independiente dio `REQUIERE CAMBIOS` con otros tres Menores (`F001` NUL en textos, `F002` `pagina` sin tope, `F003` override de `mypy`); el usuario decidió corregir `F001` y `F003` y dejar `F002` como deuda; la reauditoría dio `APROBADO`. `auditor-sql` y `revisor-impacto` no existen: los cubrió `auditor-arquitectura` y el arquitecto. No se despachó `auditor-seguridad`: el ticket no tiene endpoint, entrada externa ni dependencia nueva.

## Fuera de alcance, anotado

- Los filtros por `usuario_id`, `entidad_id`, `entidad_tipo` y `accion` no tienen índice. Revisarlo con `EXPLAIN` cuando exista la ruta (TKT-027).
- El modelo de datos §10 y su invariante 10 aún no mencionan `TRUNCATE` ni `ck_bitacora_regla_negocio_formato`.
- Un `403` con recurso (la auto-resolución de `HDU-003`) quedaría atribuido al usuario con `asentar_denegacion`; TKT-026 y TKT-027 deben decidir si lo ligan a la solicitud con el `asentar` genérico.
- `spec.md` de TKT-006 sigue listando en `M11` la URL y el motor como alcance propio, aunque los entrega TKT-007.
- Un asiento mal formado llega al cliente como `422` sobre un campo que no envió (D-2), y `ocurrido_en` lo pone el llamador sin cota (D-3).
- **`pagina` sin tope superior** (`F002` de la revisión): `revisar_filtros` no fija un máximo y un valor gigante llegaría al motor como `bigint out of range`. El tope es decisión de contrato del borrador, así que lo decide TKT-027 al montar la ruta. Decidió el usuario.
- `MENSAJE_NUL` nombra a PostgreSQL dentro de `dominio/`: es solo texto, pero acopla el mensaje al motor.
