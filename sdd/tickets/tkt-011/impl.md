# Impl · TKT-011a · Esquema y migraciones del módulo presupuesto (estructura y catálogos)

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

Este documento recoge la entrega **TKT-011a** (migración `0006`, filas A0 a A7 del diseño). La entrega **TKT-011b** (migración `0007`, filas B1 a B8) se ejecuta aparte y añade su propio apartado.

## Qué se implementó

La migración `0006` crea las doce tablas de estructura y catálogos del módulo `presupuesto`: `empresa` (con `dias_semana_laboral`), `obra`, `nivel`, `area`, `tipo_partida`, `partida`, `concepto`, `insumo`, `precio_insumo`, `apu`, `apu_insumo` y `apu_cargo`. Lleva 15 claves foráneas `ON DELETE RESTRICT`, seis `CHECK` de conjunto cerrado, dos de rango, diecisiete de no negatividad, cuatro unicidades y ocho índices, todos con nombre. No hay modelos ORM, casos de uso ni datos semilla. La bajada elimina las doce tablas y las pruebas demuestran el ciclo de subir, bajar y volver a subir.

Además se ajustaron las pruebas de TKT-057 (TC-12 y TC-13) para que suban a `0005` explícito y no a la cabeza, y se generalizó la prueba de `tools/tests` que fijaba el conteo de ADR en 29, de modo que calcula el número real.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-01 | `SQLSTATE` de borrar un padre con hijos: `23001` (`restrict_violation`), no `23503`, en TC-02 y en el texto del disparador y de TC-42 | Con `ON DELETE RESTRICT` PostgreSQL emite `23001`; el `23503` es el de insertar un hijo huérfano. Lo comprobó `tester-backend` en un contenedor `postgres:18.6` en la fila A2. El diseño se corrigió en el mismo acto. TKT-017 debe traducir también `23001` |
| 2026-11-01 | TC-15 (`apu_cargo.porcentaje`) pasa de la fila A3 a la A4 | `apu_cargo` nace en A4; en A3 los dos tests no podían ponerse en verde |
| 2026-11-01 | `docs/02-arquitectura.md` §7.6: la atribución de las pruebas de `linea_base_concepto` y `explosion_presupuesto` pasa a TKT-011b, fuera de la fila A6 | Corresponde a la partición del ticket |
| 2026-11-01 | La migración añade un `GRANT SELECT, INSERT, UPDATE, DELETE` explícito a `cimenta_aplicacion` por tabla | El desarrollador lo añadió por la convención de conceder por objeto nuevo. Es redundante con los privilegios por omisión de `0001` y deja exactamente el mismo reparto (lo comprueba TC-18). Pendiente de que la persona dueña confirme si se queda o se quita (observación F001 de `auditor-sql`) |
| 2026-11-01 | El orden de `_BAJADA` pone `area` y `nivel` antes de `insumo` y `tipo_partida`, y no el literal del diseño | Ambos órdenes respetan las claves foráneas; la prueba de bajada con filas pasa. Se conserva el del código |
| 2026-11-01 | Tres cambios fuera de la lista de archivos de la fila: dos tests extra de unicidad (`uq_tipo_partida_clave`, `uq_insumo_codigo`) y las fábricas `apu()` y `apu_cargo()` | Las unicidades las crea A2 y ningún TC las afirmaba; `apu` y `apu_cargo` los necesita TC-15 |
| 2026-11-01 | Decidido para TKT-011b: el `SQLSTATE` del disparador es `IN001` | El experimento de A0 confirmó que `CM001` está en el rango que el estándar reserva; la persona dueña eligió `IN001` frente a `RN001`. `design.md` actualizado |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0006_presupuesto_estructura_y_catalogos.py` | nuevo | infraestructura |
| `backend/tests/test_tkt011_estructura.py` | nuevo | pruebas |
| `backend/tests/test_tkt011_regresion.py` | nuevo | pruebas |
| `backend/tests/conftest.py` | modificado (fábrica `DatosPresupuesto`) | pruebas |
| `backend/tests/test_tkt057_migracion.py` | modificado (tres llamadas, fila A1, P3) | pruebas |
| `tools/tests/test_definicion_revision.py` | modificado (conteo real de ADR, P9) | pruebas |
| `docs/02-arquitectura.md` | modificado (§7.6: atribución de las pruebas de `linea_base_concepto` y `explosion_presupuesto` a TKT-011b) | documentación |
| `docs/03-modelo-datos.md` | modificado | documentación |
| `docs/05-tickets-trabajo.md` | modificado | documentación |
| `docs/adr/20261101-catalogos-cerrados-por-check.md` | nuevo (ADR-030) | documentación |
| `docs/adr/README.md`, `CLAUDE.md`, `README.md`, `llms.txt` | modificados (índice y conteo 30) | documentación |
| `sdd/tickets/tkt-011/*` | nuevo | proceso |

## Experimentos previos (fila A0)

Ejecutados el 2026-11-01 por `desarrollador-sql` contra un contenedor desechable `postgres:18.6` con psycopg 3.3.6 (guion en el directorio temporal de la sesión). Los doce confirman el diseño. E-6 y E-12 no se repitieron: los cubren TC-31 y TC-32 de TKT-003 y TC-17 de TKT-007.

| Exp. | Esperado | Observado | Veredicto |
|---|---|---|---|
| E-1 | `FOR UPDATE` y `FOR SHARE` con solo `SELECT` responden `42501`; con `UPDATE` funcionan | Exactamente eso | Confirma |
| E-2 | `SELECT … FOR UPDATE` no dispara un `BEFORE UPDATE` de fila | Terminó sin error; el `UPDATE` de control sí lanzó `P0001` | Confirma |
| E-3 | `TRUNCATE` no dispara disparadores `ON DELETE` de fila | Tabla vacía sin error | Confirma |
| E-4 | `RAISE … USING ERRCODE, CONSTRAINT, TABLE` llega a psycopg con `sqlstate`, `constraint_name` y `table_name` | `DatabaseError`, con `CM001`, `RN001` e `IN001` por igual | Confirma |
| E-5 | `cimenta_migracion` es superusuario | `rolsuper = t` | Confirma |
| E-7 | `ENUM` responde `22P02` sin nombre de restricción; `CHECK`, `23514` con él | Exactamente eso, con parámetro y con literal | Confirma |
| E-8 | Índice único parcial violado: `23505` con el nombre del índice | Exactamente eso | Confirma |
| E-9 | Con `FOR SHARE`, la inserción concurrente espera (`55P03`) y luego recibe el rechazo; sin él, se cuela | Exactamente eso: 0 copias con `FOR SHARE`, 1 sin él | Confirma |
| E-10 | Un identificador de 64 caracteres se trunca a 63 con aviso `42622` | Exactamente eso | Confirma |
| E-11 | `(to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado')` es falso si solo cambia `estado` | Falso; verdadero con `numeric`, `timestamptz`, `uuid` y `text` | Confirma |

**Clase del `SQLSTATE`.** Consultado el apéndice A de PostgreSQL con Context7: el estándar SQL reserva las clases que empiezan por 0 a 4 o por una letra entre la A y la H. `CM001` empieza por `C`. PostgreSQL 18.6 solo usa las clases `P0` y `XX` entre las que empiezan por I a Z. La base acepta `CM001`, pero eso no lo hace seguro frente a una clase estándar futura. La persona dueña eligió `IN001` para TKT-011b.

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_tkt011_ca01_tablas_de_estructura_con_su_forma` (12 tablas) | feliz | `CA-1` | FALLA | PASA |
| TC-02 | `test_tkt011_ca01_claves_foraneas_sin_cascada` y `…_borrar_el_padre_con_hijos_lo_rechaza_la_clave_foranea` | **rechazo** | `CA-1`, `PA-T8` | FALLA | PASA |
| TC-03 | `test_tkt011_ca01_obra_sin_empresa_la_rechaza_not_null` | **rechazo** | `CA-1` | FALLA | PASA |
| TC-04 | `test_tkt011_ca02_dias_semana_laboral_vale_seis_por_omision` | feliz | `CA-2` | FALLA | PASA |
| TC-05 | `test_tkt011_ca02_obra_con_empresa_inexistente_la_rechaza_la_clave_foranea` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-06 y TC-07 | `test_tkt011_ca03_codigo_de_obra_repetido_lo_rechaza_la_base` y `…_otro_codigo_de_obra_se_acepta` | **rechazo** y feliz | `CA-3` | FALLA | PASA |
| TC-08 y TC-09 | `test_tkt011_ca08_valor_fuera_del_conjunto_cerrado_lo_rechaza_la_base` y `…_valores_admitidos_se_aceptan` | **rechazo** y feliz | `CA-8` | FALLA | PASA |
| TC-10 | `test_tkt011_ca11_unidad_fuera_del_catalogo_la_rechaza_la_base` y las ocho unidades | **rechazo** y feliz | `CA-11` | FALLA | PASA |
| TC-11 y TC-12 | `test_tkt011_ca12_concepto_repetido_en_la_obra_lo_rechaza_la_base` y `…_el_mismo_codigo_en_otra_obra_se_acepta` | **rechazo** y feliz | `CA-12` | FALLA | PASA |
| TC-13 | `test_tkt011_ca13_negativo_lo_rechaza_la_base` y `…_cero_es_el_borde_que_la_base_acepta` (17 columnas) | **rechazo** y borde | `CA-13` | FALLA | PASA |
| TC-14 y TC-15 | `test_tkt011_ca14_porcentaje_de_obra_fuera_de_rango` y los dos de `apu_cargo.porcentaje` | **rechazo** y borde | `CA-14` | FALLA | PASA |
| TC-16 | `test_tkt011_ca18_0006_sube_baja_y_vuelve_a_subir` | feliz | `CA-18` | nace en verde | PASA |
| TC-17 | `test_tkt011_ca20_restricciones_e_indices_con_nombre` | feliz | `CA-20` | nace en verde | PASA |
| TC-18 | `test_tkt011_ca17_privilegios_de_las_tablas_de_estructura` | **rechazo** | `CA-17` | nace en verde | PASA |
| TC-INV-1 a 6 | `test_tkt011_car1_…` a `test_tkt011_car6_…` | regresión | `CA-R1` a `CA-R6` | nacen en verde | PASAN |

Los tres criterios de la parte a de TC-16 a TC-18 y los seis de regresión nacieron en verde porque la bajada y la subida ya existían cuando se escribieron (se escribieron después de A2 a A4, como describe el diseño). Para que no fueran vacuos, `tester-backend` aplicó 19 mutantes temporales a `v0006` y vio rojo en cada uno (tabla siguiente).

### Ciclo TDD por fila

- **A0 · experimentos.** Sin código. Resultados arriba.
- **A1 · ajuste de TKT-057.** Antes: `6 passed in 3.06s`. Después de cambiar las tres llamadas `migrar(base_vacia)` por `migrar(base_vacia, REVISION_NUEVA)`: `6 passed in 2.91s`. El ajuste es necesario cuando exista `0006` (con él, TC-12 y TC-13 afirmarían `0005` sobre una base en `0006`); no se ejecutó contra una `0006` real, pero el ciclo posterior de A2 en adelante mantiene esas seis pruebas en verde.
- **A2 · empresa, obra, tipo_partida, insumo.** Rojo: `44 failed in 6.41s`, todos por tabla inexistente. Verde: `44 passed in 6.08s`; suite completa `1447 passed`.
- **A3 · nivel, area, partida, concepto.** Rojo: `25 failed, 43 passed`. Verde: `66 passed, 2 deselected` (los dos de TC-15, movidos a A4); suite completa `1469 passed`.
- **A4 · precio_insumo, apu, apu_insumo, apu_cargo.** Rojo: `47 failed, 67 passed`. Verde: `114 passed`; suite completa `1517 passed`.
- **A5 · bajada, nombres, privilegios y regresión.** Nueve pruebas nuevas, todas en verde; `55 passed` junto a las suites de migración de TKT-003, TKT-006, TKT-007 y TKT-057.
- **A6 · documentación y ADR-030.** `python -m unittest discover -s tools/tests`: `Ran 474 tests … OK`.
- **A7 · cierre.** Mutantes y suite completa (abajo).

**Tests devueltos al tester:** ninguno de producción. Un docstring de `test_tkt011_regresion.py` contenía el texto `create_all(` y la prueba de TKT-003 que vigila ese literal falló (`1 failed, 1525 passed`); se reformuló y ambas pruebas pasaron (`10 passed`). Dos docstrings de `test_tkt011_estructura.py` citaban `RN-25` donde correspondía `PA-22`/`PA-T2` y `ADR-008` (hallazgo F003 de `auditor-arquitectura`) y se corrigieron.

**Evidencia de ejecución al cerrar.** Docker 29.9.2 respondiendo.

```text
tests/test_tkt011_estructura.py + tests/test_tkt011_regresion.py: 125 passed in 14.36s (123 al cerrar A7; las dos filas nuevas del borde de fondo_garantia_pct llegaron con la corrección F001 de auditor-codigo)
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 169 files already formatted
uv run mypy .                  -> Success: no issues found in 169 source files
uv run lint-imports            -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float -> archivos revisados: 19; hallazgos: 0
python -m unittest discover -s tools/tests -> Ran 474 tests … OK
```

La salida de la suite completa del backend tras las últimas correcciones queda en la sección «Verificación final».

**Mutación en rutas críticas.** Hash de la migración (`git hash-object`) antes y después de cada mutante de A5 y A7: `614a0ba0a1f31f114679947d7b82592fa81819db`. Tras el ciclo de corrección, que solo cambió comentarios y docstring (el AST sin el docstring de módulo es idéntico), el hash vigente es `938dbb85de5f4168ae915a0d4de73235765ef658`; los mutantes de la reauditoría de código se aplicaron y revirtieron sobre esta versión.

| Mutante | Cambio | Test en rojo | Aserción |
|---|---|---|---|
| MA-1 | `ck_concepto_cantidad_no_negativo` con `> 0` | `test_tkt011_ca13_cero_es_el_borde_que_la_base_acepta[concepto.cantidad]` | `CheckViolation` con `cantidad = 0.0000` |
| MA-2 | `ck_obra_fondo_garantia_pct_rango` con `< 1` | `test_tkt011_ca14_porcentaje_de_obra_fuera_de_rango[…fondo=1.000000…]` | `CheckViolation` con fondo `1.000000` |
| MA-3 | Quitar `ck_insumo_unidad` | `test_tkt011_ca11_unidad_fuera_del_catalogo_la_rechaza_la_base[insumo_LITRO]` y `…ca20_restricciones_e_indices_con_nombre` | `DID NOT RAISE CheckViolation` |
| MA-4 | `uq_concepto_obra_id_codigo` solo sobre `(codigo)` | `test_tkt011_ca12_el_mismo_codigo_en_otra_obra_se_acepta` | `UniqueViolation` |
| MA-5 | `fk_nivel_obra_id` con `ON DELETE CASCADE` | `…ca01_borrar_el_padre_con_hijos…[obra_con_nivel]` y `…claves_foraneas_sin_cascada` | `DID NOT RAISE RestrictViolation`; `{'c','r'} == {'r'}` |
| MA-6 | `obra.umbral_alerta_pct NOT NULL` | `…ca01_tablas_de_estructura_con_su_forma[obra]` y el caso `umbral=None` de TC-14 | `('NO') != ('YES')`; `NotNullViolation` |

Ningún mutante sobrevivió. En A5 se aplicaron además 19 mutantes (MT-1 a MT-19) sobre bajada, nombres, privilegios y regresión; cada uno puso en rojo el test previsto (`GRANT TRUNCATE`, `REVOKE DELETE`, renombrar restricciones, quitar un índice, `down_revision` equivocado, columna `double precision`, entre otros).

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Diseño | `arquitecto-tecnico` | `opus` | `opus` | — |
| A0 | `desarrollador-sql` | `sonnet` | `sonnet` | — (permisos de un rol y disparador) |
| A1 | `tester-backend` | `sonnet` | `sonnet` | — |
| A2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A2 · verde | `desarrollador-sql` | `haiku` | `haiku` | — |
| A3 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `haiku` | `sonnet` / `haiku` | — |
| A4 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `haiku` | `sonnet` / `haiku` | — |
| A5 | `tester-backend` | `sonnet` | `sonnet` | La fila A5 del diseño marca `sonnet` por los permisos de un rol; no hubo paso de desarrollo porque la bajada ya existía desde A4 |
| A6 · conteo de ADR | `tester-backend` | `haiku` | `sonnet` | Edición de una prueba de otro ticket con expresiones regulares y mutantes; la fila decía `haiku` para documentación, pero esta parte es de pruebas |
| A6 · documentación | `desarrollador-sql` | `haiku` | `haiku` | — |
| A7 | `tester-backend` | `sonnet` | `sonnet` | — |
| Impacto | `revisor-impacto` | — | por omisión del agente | — |
| Auditorías | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |

## Resultado contra los criterios de aceptación

Criterios de la parte a. Los de la parte b (`CA-4` a `CA-7`, `CA-9`, `CA-10`, `CA-15`, `CA-16`, `CA-19` y la parte b de `CA-1`, `CA-8`, `CA-13`, `CA-14`, `CA-17`, `CA-18` y `CA-21`) pertenecen a TKT-011b.

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` (doce tablas) | `[M]` | Cumplido | TC-01, TC-02, TC-03 |
| `CA-2` | `[M]` | Cumplido | TC-04, TC-05 |
| `CA-3` | `[M]` | Cumplido | TC-06, TC-07 |
| `CA-8` (obra, insumo, cargo de APU) | `[M]` | Cumplido en la parte a | TC-08, TC-09 |
| `CA-11` | `[M]` | Cumplido | TC-10 |
| `CA-12` | `[M]` | Cumplido | TC-11, TC-12 |
| `CA-13` (diecisiete columnas) | `[M]` | Cumplido en la parte a | TC-13 |
| `CA-14` (obra y cargo) | `[M]` | Cumplido en la parte a | TC-14, TC-15 |
| `CA-17` (privilegios de las doce) | `[M]` | Cumplido en la parte a | TC-18 |
| `CA-18` (`0006`) | `[M]` | Cumplido | TC-16 |
| `CA-20` | `[S]` | Cumplido | TC-17 |
| `CA-21` (parte a) | `[M]` | Cumplido | `verificar_docs.py` y revisión de los tres documentos; falta la arquitectura §9, que es de 011b |
| `CA-R1` a `CA-R6` | `[M]` | Cumplido en la parte a | TC-INV-1 a TC-INV-6 |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO en la reauditoría | Primera pasada: 2 menores (F001, F002) y 2 observaciones; F001 a F003 resueltos, F004 persiste como observación | 2 |
| `auditor-sql` | APROBADO | 4 observaciones, sin hallazgos críticos, mayores ni menores | 1 |
| `auditor-codigo` | APROBADO en la reauditoría | Primera pasada: 1 mayor y 6 menores; los siete resueltos | 2 |
| `auditor-docs` | APROBADO en la tercera pasada | Primera pasada: 1 mayor y 7 menores; segunda: 3 mayores y 4 menores de la misma clase de atribución, resueltos por el orquestador con el texto literal del auditor; tercera: todo resuelto y una observación (O011, corregida) | 3 |
| `auditor-seguridad` | No aplica: no hay endpoint, entrada externa, archivo, sesión, imagen, Compose, flujo de CI ni dependencia nueva | — | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `design.md` → `impl.md` | Enlace roto para `verificar_docs.py` hasta que exista `impl.md` | Resuelto (este archivo) |
| F002 | arquitectura | Menor | ADR-030, «Evidencia del mecanismo» | La evidencia de E-7 no estaba en el repositorio | Resuelto (sección «Experimentos previos») |
| F003 | arquitectura | Observación | `test_tkt011_estructura.py:419` y `:440` | Citaba `RN-25` en lugar de `PA-22`/`PA-T2` y `ADR-008` | Resuelto |
| F004 | arquitectura | Observación | `docs/05-tickets-trabajo.md:138`, `:494`, `:1342`, `:2258` | Siguen diciendo «TKT-011» a secas donde el dueño es 011a o 011b | Resuelto: `docs/05` se corrigió en este cambio (F004 a F006 de `auditor-docs`) |
| F001 | sql | Observación | `v0006…py:233-244` | `GRANT` explícito redundante con los privilegios por omisión | Pendiente de confirmación de la persona dueña |
| F002 | sql | Observación | `v0006…py:248-261` | Orden de `_BAJADA` distinto del literal del diseño | Sin acción; ambos son válidos |
| F003 | sql | Observación | `v0006…py:128-137` y otras | Claves foráneas sin índice, YAGNI del diseño | Ticket futuro |
| F004 | sql | Observación | `v0006…py:121` | `area.tipo_unidad` sin `CHECK`, YAGNI del diseño | Ticket futuro |

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `v0006…py` | Sin índice en `partida.tipo_partida_id`, `precio_insumo.obra_id`, `apu_insumo.insumo_id`, `obra.empresa_id`, `obra.creado_por_id` y `obra.actualizado_por_id`. `partida.tipo_partida_id` es el candidato real si la fase 1 filtra partidas por tipo | Baja; ticket futuro |
| `v0006…py` | `area.tipo_unidad` admite cualquier texto | Baja; ticket futuro |
| `docs/api/openapi.yaml` | `Obra.actualizado_en` no admite `null` y la columna sí; TKT-012 debe omitir el campo | Media; TKT-012 |
| `v0006…py` | `concepto.obra_id` no está atado por restricción a la obra de su jerarquía (`PA-T3`) | Media; ticket futuro ya sugerido en `_index.md` |
| `docs/05-tickets-trabajo.md` | Fichas de TKT-014 a TKT-018 no citan TKT-011; dependen de 011b por TKT-013 | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/02-arquitectura.md` | §7.6: atribución de las pruebas de `linea_base_concepto` y `explosion_presupuesto` a TKT-011b |
| `docs/03-modelo-datos.md` | §2 «Enumeraciones» (`CHECK` con nombre); §4.1 `obra` con auditoría, `empresa.dias_semana_laboral`, `APU.concepto_id` sin `UNIQUE`, `concepto.obra_id`, unidades; §13 invariante 8 ampliado |
| `docs/05-tickets-trabajo.md` | Partición en 011a y 011b; «Depende de» reasignado; TKT-049 solo consume `dias_semana_laboral` |
| `docs/adr/20261101-catalogos-cerrados-por-check.md` | ADR-030 nuevo, con la evidencia de E-7 |
| `docs/adr/README.md`, `CLAUDE.md`, `README.md`, `llms.txt` | Índice y conteo de 29 a 30 |
| `tools/tests/test_definicion_revision.py` | El conteo se calcula de `docs/adr/` |

`python tools/verificar_docs.py` → con este archivo presente no debe reportar el enlace roto de `design.md` a `impl.md`; el resultado de la última ejecución figura en «Verificación final».

## Verificación final

- [x] Criterios `[M]` de la parte a cumplidos con evidencia
- [x] Ciclo TDD en cada fila: rojo antes de verde donde había código que escribir; las pruebas de A5 nacieron en verde y se validaron con mutantes
- [x] Suite completa en verde tras las últimas correcciones: `uv run pytest -q` → `1528 passed in 278.06s (0:04:38)`, con `docker info` respondiendo (29.9.2). `python tools/verificar_docs.py` → `✓ Sin problemas.`
- [x] Al menos un test de rechazo por garantía implicada
- [x] Mutación en rutas críticas: seis mutantes de A7 y diecinueve de A5, ninguno sobrevivió
- [x] Todas las auditorías `APROBADO`: arquitectura, sql, código y documentación
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios
- [x] Rama `tkt-011a-esquema-estructura-catalogos`, sin secretos en el diff
