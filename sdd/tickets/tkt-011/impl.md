# Impl · TKT-011a · Esquema y migraciones del módulo presupuesto (estructura y catálogos)

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

Este documento recoge la entrega **TKT-011a** (migración `0006`, filas A0 a A7 del diseño). La entrega **TKT-011b** (migración `0007`, filas B1 a B8) tiene su propio apartado al final de este documento.

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

---

## Entrega TKT-011b · línea base, importación, disparadores y permisos (migración `0007`)

Este apartado recoge la entrega **TKT-011b** (filas B1 a B8 del diseño), ejecutada después de fusionar TKT-011a (PR 31, merge `f334b97`). Todo lo anterior de este documento es de TKT-011a.

### Qué se implementó (TKT-011b)

La migración `0007` crea las siete tablas restantes del módulo `presupuesto`: `linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, `importacion`, `importacion_error` y `rendimiento_observado`. Añade el índice único parcial de una sola línea base `CONGELADA` por obra, las dos funciones de disparador y los tres disparadores que imponen el invariante 14 con el `SQLSTATE` propio `IN001`, un único `REVOKE` (`UPDATE`, `DELETE` y `TRUNCATE` sobre `linea_base_concepto` para el rol de aplicación) y una bajada con guarda. La guarda se niega con cualquier línea base que no sea `BORRADOR` y toma un bloqueo exclusivo de `linea_base` antes de comprobar. No hay modelos ORM, casos de uso ni datos semilla.

### Ajustes respecto al design (TKT-011b)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-01 | El `SQLSTATE` del disparador es `IN001` y no `CM001` | El experimento E-4 de la fila A0 confirmó que la clase `CM` está en el rango que el estándar SQL reserva; la persona dueña eligió `IN001` frente a `RN001` |
| 2026-11-01 | La medición E-13 pasa de la fila B8 a la B2 | Objeción 11 de la pasada independiente: medirla al final obligaba a rehacer el disparador si fallaba. Resultado: `5000 copias en 0.056 s, 300 renglones en 0.006 s, congelado en 0.008 s; total 0.070 s`, frente al límite de 15 s |
| 2026-11-01 | Las filas B3 y B5 se ejecutaron agrupadas en un solo ciclo TDD | Crean tablas independientes, sin disparadores ni dependencia entre sí; el orden de ejecución fue B1, B2, B3 y B5, B4, B6, B7 y B8 |
| 2026-11-01 | La guarda de la bajada añade `LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE` antes de comprobar | Lo propuso el desarrollador; sin él, otra sesión puede congelar una línea base entre la comprobación y el `DROP`. Una prueba de concurrencia nueva lo ata (`test_tkt011_ca19_la_guarda_toma_el_bloqueo_antes_de_comprobar`) y el mutante «sin bloqueo» la pone en rojo |
| 2026-11-01 | La guarda se niega con una línea base `CONGELADA` **o** `SUPERSEDIDA` (CA-19 ampliado) | Decisión de la persona dueña tras la auditoría de arquitectura: una `SUPERSEDIDA` es un presupuesto firmado que ya estuvo vigente y la bajada la borraría en silencio. Se cambian la spec, el diseño, el ADR-031, TC-48 y TC-49 |
| 2026-11-01 | La guarda de la bajada también usa `IN001` | Coherencia con los disparadores; no llega a la API, así que TKT-017 no la traduce |
| 2026-11-01 | Sin `GRANT` explícito en `0007`, a diferencia de `0006` | El diseño lo prescribe: las tablas heredan los privilegios por omisión de `0001` y solo se revoca lo que no corresponde. La asimetría con `0006` sigue pendiente de la decisión de la persona dueña sobre sus `GRANT` |
| 2026-11-01 | TC-42 con copias se prueba con una tabla de copias a la vez | Con las dos, PostgreSQL informa la primera clave violada y el caso de explosión no se podría afirmar |
| 2026-11-01 | TC-41 se amplía a `SUPERSEDIDA` y a las ocho columnas en la misma sentencia que supera | Con solo `importe_venta` el mutante «sin la comparación de columnas» quedaba tapado por la regla de transición |
| 2026-11-01 | Los textos «`UPDATE` y `DELETE`» se alinean en `CLAUDE.md`, `docs/02-arquitectura.md`, el ADR de snapshot, el skill `conv-sql-postgres` y los agentes `desarrollador-sql` y `auditor-sql` | Decisión de la persona dueña (P10). Queda sin alinear `.claude/agents/auditor-arquitectura.md`, línea ~36, que no estaba en la aprobación |

### Archivos tocados (TKT-011b)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0007_presupuesto_linea_base_e_importacion.py` | nuevo | infraestructura |
| `backend/tests/test_tkt011_linea_base.py` | nuevo | pruebas |
| `backend/tests/test_tkt011_importacion.py` | nuevo | pruebas |
| `backend/tests/test_tkt011_permisos.py` | nuevo | pruebas |
| `backend/tests/test_tkt011_migracion_linea_base.py` | nuevo | pruebas |
| `backend/tests/conftest.py` | modificado (la fábrica `DatosPresupuesto` gana `linea_base`, copias, renglones, control, importación, error y rendimiento observado) | pruebas |
| `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` | nuevo (ADR-031) | documentación |
| `docs/adr/README.md`, `docs/adr/20260918-snapshot-linea-base.md` | modificados | documentación |
| `docs/02-arquitectura.md`, `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md` | modificados | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt` | modificados (regla 4 y conteo 31) | documentación |
| `.claude/skills/conv-sql-postgres/SKILL.md`, `.claude/agents/desarrollador-sql.md`, `.claude/agents/auditor-sql.md` | modificados | proceso |
| `sdd/tickets/tkt-011/*` | modificado | proceso |

### Pruebas (TKT-011b)

Las 56 funciones de prueba de TKT-011b suman 160 casos con la parametrización: 31 funciones y 130 casos en `test_tkt011_linea_base.py`, 6 y 6 en `test_tkt011_permisos.py`, 8 y 9 en `test_tkt011_migracion_linea_base.py` y 11 y 15 en `test_tkt011_importacion.py`.

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-20 | `test_tkt011_ca01_tablas_de_linea_base_e_importacion_con_su_forma` y `…marcas_de_tiempo_con_zona_horaria` | feliz | `CA-1` | FALLA | PASA |
| TC-21 y TC-22 | `test_tkt011_ca04_segunda_linea_base_congelada_la_rechaza_la_base` y `…congelada_junto_a_supersedida_y_borrador` | **rechazo** y feliz | `CA-4` | FALLA | PASA |
| TC-23 a TC-25 | `test_tkt011_ca05_…` y `test_tkt011_ca06_…` | **rechazo** y feliz | `CA-5`, `CA-6` | FALLA | PASA |
| TC-26 y TC-27 | `test_tkt011_ca07_…` | feliz | `CA-7` | FALLA | PASA |
| TC-28 y TC-29 | `test_tkt011_ca08_los_siete_conjuntos_cerrados_responden_23514` y `…estados_y_tipos_admitidos_se_aceptan` | **rechazo** y feliz | `CA-8` | FALLA | PASA |
| TC-30 | `test_tkt011_ca09_…` | **rechazo** y feliz | `CA-9` | FALLA | PASA |
| TC-31 y TC-32 | `test_tkt011_ca10_…` | feliz | `CA-10` | FALLA | PASA |
| TC-33 y TC-34 | `test_tkt011_ca13_…` y `test_tkt011_ca14_…` | **rechazo** y borde | `CA-13`, `CA-14` | FALLA | PASA |
| TC-35 a TC-39 y TC-C2 | `test_tkt011_ca15_…` (seis sentencias en `CONGELADA` y en `SUPERSEDIDA`, mover entre líneas base, borrador, congelado en una transacción, concurrencia) | **rechazo**, feliz y concurrencia | `CA-15` | FALLA | PASA |
| TC-40 a TC-42 | `test_tkt011_ca16_…` | **rechazo** y feliz | `CA-16` | FALLA | PASA |
| TC-43, TC-45, TC-46 | `test_tkt011_ca17_…` | **rechazo** | `CA-17` | TC-43 FALLA; TC-45 y TC-46 nacen en verde | PASA |
| TC-44 y TC-C1 | `test_tkt011_ca17_el_bloqueo_pesimista_…` | feliz y concurrencia | `CA-17` | nacen en verde | PASA |
| TC-47 | `test_tkt011_ca18_0007_sube_baja_y_vuelve_a_subir` | feliz | `CA-18` | nace en verde | PASA |
| TC-48 | `test_tkt011_ca19_no_se_baja_con_una_linea_base_congelada` (`CONGELADA` y `SUPERSEDIDA`) | **rechazo** | `CA-19` | FALLA | PASA |
| TC-49 | `test_tkt011_ca19_solo_con_borradores_la_bajada_elimina_las_tablas` | feliz | `CA-19` | nace en verde | PASA |
| Nuevo | `test_tkt011_ca19_la_guarda_toma_el_bloqueo_antes_de_comprobar` | concurrencia | `CA-19` | nace en verde | PASA |
| TC-50 | `test_tkt011_ca20_restricciones_indices_y_disparadores_con_nombre` | feliz | `CA-20` | nace en verde | PASA |
| TC-INV | `test_tkt011_car3_lectura_sin_escritura_en_las_tablas_nuevas`, `…car4_0007_cuelga_de_0006`, `…car5_…`, `…car6_…` | regresión | `CA-R3` a `CA-R6` | nacen en verde | PASAN |

#### Ciclo TDD por fila (TKT-011b)

- **B1 · `linea_base` y su disparador.** Rojo: `46 failed in 6.60s`, todos por `linea_base` inexistente. Verde: `46 passed in 7.23s`.
- **B2 · copias, explosión y disparador de copias.** Rojo: `41 failed, 46 passed`. Verde: `87 passed`, con la concurrencia TC-C2 y la medición E-13.
- **B3 y B5 · control, importación, error y rendimiento observado (agrupadas).** Rojo: `54 failed, 91 passed`. Verde: `145 passed in 17.74s`.
- **B4 · `REVOKE` sobre `linea_base_concepto`.** Rojo: `1 failed, 5 passed` (solo TC-43 en rojo; los otros cinco nacen en verde y diecisiete mutantes demostraron que no son vacuos). Verde: `19 passed` junto a las pruebas de privilegios de TKT-003.
- **B6 · bajada con guarda.** Rojo: `1 failed, 6 passed` (TC-48). Verde: `7 passed`; luego, tras ampliar la guarda a `SUPERSEDIDA` y añadir la prueba de concurrencia del bloqueo, `9 passed`.
- **B7 · documentación y ADR-031.** `python -m unittest discover -s tools/tests`: `Ran 474 tests … OK`.
- **B8 · cierre.** Mutantes y suite completa (abajo).

**Tests devueltos al tester:** ninguno. TC-48 y TC-49 se reescribieron en el ciclo de corrección por la decisión de ampliar la guarda, antes de tocar el código.

#### Mutación en rutas críticas (TKT-011b)

Hash de la migración (`git hash-object`) antes y después de cada mutante de B8: `5da792d9713da8819565e96004dcf5b34bb19d15` (antes de la corrección; el vigente es `f9bfbc9fb9bbdabd2ee95d1bc1d60fd07be8d021`, medido con `git hash-object`). Los quince mutantes murieron:

| Mutante | Tests en rojo | Aserción |
|---|---|---|
| MB-1 `= 'CONGELADA'` en vez de `<> 'BORRADOR'` | TC-36, 6 de 6 | `DID NOT RAISE Error` |
| MB-2 disparadores de copias sin `INSERT` | TC-35 (dos `INSERT`) y TC-39 | `DID NOT RAISE Error` |
| MB-3 en `UPDATE` solo `NEW.linea_base_id` | TC-37 `congelada_a_borrador` en las dos tablas | `DID NOT RAISE Error` |
| MB-4 sin `FOR SHARE` | TC-C2 | `DID NOT RAISE LockNotAvailable` |
| MB-5 `CONGELADA` → `BORRADOR` admitida | TC-40 | `DID NOT RAISE Error` |
| MB-6 sin la comparación de columnas | TC-41 «al superseder», 8 de 8 | `DID NOT RAISE Error` |
| MB-7 `DELETE` admitido en cualquier estado | TC-42 | `DID NOT RAISE Error` |
| MB-8 sin `ERRCODE` | TC-40 y TC-35 | `'P0001' == 'IN001'` |
| MB-9 sin el `REVOKE` | TC-43 | sobran `UPDATE` y `DELETE` |
| MB-10 `REVOKE UPDATE ON explosion_presupuesto` | TC-44 y TC-C1 | `InsufficientPrivilege` (`42501`) |
| MB-11 bajada sin guarda | TC-48 | `DID NOT RAISE DBAPIError` |
| MB-12 índice único sin `WHERE` | TC-22 | `UniqueViolation` |
| MB-13 `GRANT TRUNCATE` | TC-45 | `{'linea_base_concepto': True} != {…: False}` |
| MB-14 sin el disparador de `explosion_presupuesto` | TC-35 y TC-36, tres casos de explosión | `DID NOT RAISE Error` |
| MB-15 `OLD.linea_base_id` en `INSERT` | TC-35 (dos `INSERT`) | `DID NOT RAISE Error` |

En el ciclo de corrección se añadieron estos mutantes de la guarda: «sin `LOCK`» (la prueba de concurrencia termina con `None` en lugar de `IN001` y la bajada borra una `CONGELADA` recién congelada), guarda `= 'CONGELADA'`, guarda `= 'SUPERSEDIDA'`, `EXISTS` sin filtro, `ERRCODE` distinto y `LOCK … ACCESS SHARE MODE`; todos cayeron.

**Evidencia de ejecución al cerrar.**

```text
docker info                         -> Server Version 29.9.2
uv run pytest -q                    -> 1688 passed in 300.81s (0:05:00)
uv run ruff check .                 -> All checks passed!
uv run ruff format --check .        -> 174 files already formatted
uv run mypy .                       -> Success: no issues found in 174 source files
uv run lint-imports                 -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float -> verificar_float: archivos revisados: 19; hallazgos: 0
python tools/verificar_docs.py      -> ✓ Sin problemas.
python -m unittest discover -s tools/tests -> Ran 474 tests … OK
lychee --config lychee.toml …       -> 1539 Total · 1538 OK · 0 Errors · 1 Excluded · 11 Redirects
```

La suite completa pasó de 1686 (cierre de B8) a 1688 con el ciclo de corrección: dos casos nuevos en `test_tkt011_migracion_linea_base.py` (TC-48 parametrizado por `CONGELADA` y `SUPERSEDIDA`, y la prueba de concurrencia del bloqueo). Hash de la migración tras la corrección (`git hash-object`): `f9bfbc9fb9bbdabd2ee95d1bc1d60fd07be8d021`.

### Modelo por paso (TKT-011b)

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| B1 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `sonnet` (disparador de inmutabilidad) | `sonnet` / `sonnet` | — |
| B2 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `sonnet` (inmutabilidad y concurrencia) | `sonnet` / `sonnet` | — |
| B3 y B5 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `haiku` | `sonnet` / `haiku` | — |
| B4 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `sonnet` (permisos y bloqueo pesimista) | `sonnet` / `sonnet` | — |
| B6 · rojo / verde | `tester-backend` / `desarrollador-sql` | `sonnet` / `haiku` | `sonnet` / `haiku` | — |
| B7 | `desarrollador-sql` | `haiku` | `haiku` | — |
| B8 | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditorías | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |
| Corrección | `tester-backend`, `desarrollador-sql`, `corrector-revision` | `sonnet`, `haiku`, `haiku` | `sonnet`, `haiku`, `haiku` | — |

### Resultado contra los criterios de aceptación (TKT-011b)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` (siete tablas) | `[M]` | Cumplido | TC-20 |
| `CA-4` | `[M]` | Cumplido | TC-21, TC-22 |
| `CA-5` | `[M]` | Cumplido | TC-23, TC-24 |
| `CA-6` | `[M]` | Cumplido | TC-25 |
| `CA-7` | `[M]` | Cumplido | TC-26, TC-27 |
| `CA-8` (las seis filas juntas) | `[M]` | Cumplido | TC-28, TC-29 |
| `CA-9` | `[M]` | Cumplido | TC-30 |
| `CA-10` | `[M]` | Cumplido | TC-31, TC-32 |
| `CA-13` y `CA-14` (parte b) | `[M]` | Cumplido | TC-33, TC-34 |
| `CA-15` | `[M]` | Cumplido | TC-35 a TC-39, TC-C2 |
| `CA-16` | `[M]` | Cumplido | TC-40 a TC-42 |
| `CA-17` | `[M]` | Cumplido | TC-43 a TC-46, TC-C1 |
| `CA-18` (`0007`) | `[M]` | Cumplido | TC-47 |
| `CA-19` (ampliado a `SUPERSEDIDA`) | `[M]` | Cumplido | TC-48, TC-49 y la prueba del bloqueo |
| `CA-20` | `[S]` | Cumplido | TC-50 |
| `CA-21` | `[M]` | Cumplido | `verificar_docs.py`; arquitectura §9 con `DESCARTADO`; modelo de datos y ficha de TKT-011 alineados |
| `CA-R3` a `CA-R6` (parte b) | `[M]` | Cumplido | TC-INV-3 parte b, TC-INV-4b, 5b y 6b; `CA-R1` y `CA-R2` (bitácora e `intento_acceso`) siguen solo en la parte a |

### Auditorías (TKT-011b)

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | REQUIERE CAMBIOS en la primera pasada; APROBADO en la reauditoría | Cuatro Menores (F001 a F004), resueltos, y cuatro observaciones (O1 a O4), con su estado en la tabla de abajo | 2 |
| `auditor-sql` | REQUIERE CAMBIOS en la primera pasada; APROBADO en la reauditoría | Dos Menores (F001 y F002), resueltos, y cinco observaciones (O1 a O5), con su estado en la tabla de abajo | 2 |
| `auditor-codigo` | REQUIERE CAMBIOS en la primera pasada; APROBADO en la reauditoría | Ocho Menores (F001 a F008), resueltos salvo la parte de F007 que se decidió no aplicar (no se borró ninguna prueba), y dos observaciones no pedidas (F009 y F010) | 2 |
| `auditor-docs` | REQUIERE CAMBIOS en la primera pasada, en la reauditoría y en la pasada de cierre | Primera pasada: cuatro Menores y seis observaciones; reauditoría: dos Menores de redacción (N001 y N002); pasada de cierre de `/sdd-completar`: dos Mayores (títulos de primer nivel repetidos en `delta.md` e `impl.md`, y afirmaciones de cierre sin respaldo en la tabla) y cinco Menores, resueltos por el orquestador con el texto literal del auditor y comprobados con `markdownlint-cli2` y `verificar_docs.py` | 3 |

#### Hallazgos y su resolución (TKT-011b)

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `v0007…py` (`LOCK TABLE`, `ERRCODE`) y `test_tkt011_migracion_linea_base.py` | Ninguna prueba mordía el bloqueo ni el `SQLSTATE` de la guarda | Resuelto: TC-48 afirma `IN001`, y hay una prueba de concurrencia del bloqueo con su mutante |
| F002 | arquitectura | Menor | `impl.md`, `design.md`, ADR-031 | Desviaciones sin registrar | Resuelto: este apartado, los estados de las filas y el ADR |
| F003 | arquitectura | Menor | `.claude/agents/auditor-sql.md:44` | Redacción contradictoria para la bitácora | Resuelto con el texto literal del auditor |
| F004 | arquitectura | Menor | `docs/02-arquitectura.md:393` y `_index.md:22` | Atribución desfasada | Resuelto |
| O1 | arquitectura | Observación | `v0007…py` | La guarda dejaba pasar las `SUPERSEDIDA` | Resuelto: decisión de la persona dueña, CA-19 ampliado |
| O2 | arquitectura | Observación | `backend/tests/test_tkt011_linea_base.py:922` y `:1274` | Docstrings que dicen «reimporta» | Resuelto: docstrings corregidos en la ronda de código |
| O3 | arquitectura | Observación | `sdd/tickets/tkt-011/spec.md`, CA-4 | `INSERT` directo de líneas base `CONGELADA` y `SUPERSEDIDA` | Aceptada: decisión declarada en CA-4 |
| O4 | arquitectura | Observación | `v0007…py` (`importe_venta` es `NOT NULL`) | `importe_venta` en un `BORRADOR` sin valor definido | Trasladada a TKT-017: pregunta abierta (ver la tabla de fuera de alcance) |
| F001 | sql | Menor | `v0007…py` (plan de reversa) | Un paso sin definir y una promesa en el mensaje | Resuelto: el procedimiento queda declarado como no definido, decidido fuera de la migración |
| F002 | sql | Menor | `v0007…py` (docstring) | Descripción a mitad de camino | Resuelto con el texto literal del auditor |
| O1 | sql | Observación | `v0007…py` | La guarda dejaba pasar las `SUPERSEDIDA` | Resuelto: decisión de la persona dueña, CA-19 ampliado |
| O2 | sql | Observación | `v0007…py` (`LOCK TABLE`) | Sin `lock_timeout` antes del `LOCK` | Opcional (ver la tabla de fuera de alcance) |
| O3 | sql | Observación | `v0007…py` frente a `v0006…py` | Sin `GRANT` explícito por tabla en `0007`, asimétrico con `0006` | Pendiente de la persona dueña (ver la tabla de fuera de alcance) |
| O4 | sql | Observación | `sdd/tickets/tkt-011/spec.md`, CA-4 | `INSERT` directo de líneas base `CONGELADA` y `SUPERSEDIDA` | Aceptada: decisión declarada en CA-4 |
| O5 | sql | Observación | `v0007…py` (`REVOKE` sobre `linea_base_concepto`) | Sin `DELETE` de la aplicación sobre `linea_base_concepto` | Trasladada a TKT-017 (ver la tabla de fuera de alcance) |

### Hallazgos fuera de alcance (TKT-011b)

| Archivo | Observación | Prioridad |
|---|---|---|
| `.claude/agents/auditor-arquitectura.md` (~36) | Sigue diciendo «sin disparador que rechace UPDATE y DELETE»; la aprobación P10 no lo nombraba | Baja |
| TKT-017 | Definir con qué valor nace `importe_venta` en un `BORRADOR` (`PA-T17`), cerrar el flujo de reimportación (la aplicación no tiene `DELETE` sobre `linea_base_concepto`) y traducir `IN001`, `23505`, `23503` y `23001` | Media |
| `backend/migraciones/versions/v0007_…py` | Procedimiento para retirar una línea base `CONGELADA` o `SUPERSEDIDA` antes de bajar la migración; el mensaje de la guarda lo declara sin definir | Decisión de la persona dueña |
| `backend/tests/` (varios) | Helpers repetidos (`afirmar_rechazo`, `contar`, `fotografia`) y `copia_concepto` sin padres que crea un concepto de otra obra (observaciones F009 y F010 de `auditor-codigo`, no pedidas) | Baja; ticket futuro de limpieza de pruebas |
| `v0007…py` | Sin índice en `presupuesto_control.tipo_partida_id` ni en `rendimiento_observado.obra_id`; hay que confirmarlo con la consulta del semáforo (modelo de datos §15) antes de TKT-017 | Baja |
| `v0007…py` | Sin `lock_timeout` en el rol de migración: una sesión de aplicación colgada hace esperar la bajada sin límite. Opcional: `SET LOCAL lock_timeout` antes del `LOCK` | Baja |
| `v0006…py` | `GRANT` explícito por tabla, asimétrico con `0007`; pendiente de la persona dueña | Baja |

### Documentación actualizada (TKT-011b)

| Documento | Qué cambió |
|---|---|
| ADR-031 y su fila en `docs/adr/README.md` | Nuevo; nota en el ADR de snapshot de la línea base |
| `docs/03-modelo-datos.md` | §4.2, §11, §13 (invariante 14), §14, §15 y la frase sobre la versión anterior |
| `docs/02-arquitectura.md` | §7.6 y §9 (estado `DESCARTADO`) |
| `docs/05-tickets-trabajo.md` | Criterio del disparador y restricciones para TKT-017 |
| `CLAUDE.md`, `README.md`, `llms.txt` | Regla 4 y conteo de decisiones a 31 |
| `.claude/skills/conv-sql-postgres/SKILL.md`, `.claude/agents/desarrollador-sql.md`, `.claude/agents/auditor-sql.md` | Textos del disparador y comportamientos del motor que sorprenden |

### Verificación final (TKT-011b)

- [x] Criterios `[M]` de la parte b cumplidos con evidencia
- [x] Ciclo TDD en cada fila: rojo antes de verde donde había código que escribir; las pruebas de B4 y B6 que nacieron en verde se validaron con mutantes
- [x] Suite completa en verde: `1688 passed in 300.81s (0:05:00)`, con `docker info` respondiendo (29.9.2)
- [x] Al menos un test de rechazo por garantía implicada
- [x] Mutación en rutas críticas: quince mutantes de B8 y los de la guarda en el ciclo de corrección, ninguno sobrevivió
- [x] Auditorías en `APROBADO` en su última pasada (arquitectura, SQL y código); la de documentación se resolvió con el texto literal del auditor y se comprobó con `markdownlint-cli2` y `verificar_docs.py`, conforme al criterio de parada para la redacción
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios
- [x] Rama `tkt-011b-linea-base-importacion-permisos`, sin secretos en el diff (se comprueba al cerrar)
