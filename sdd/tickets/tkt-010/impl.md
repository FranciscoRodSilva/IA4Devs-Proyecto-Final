# Impl · TKT-010 · Datos semilla con catálogos

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

Este documento registra la ejecución de **TKT-010a**, la primera de las dos entregas hermanas (filas A1 y A2 del diseño). TKT-010b, con la herramienta `herramientas.semilla_local`, la documentación y el ADR-032, se ejecuta después y añade su propia sección.

## Qué se implementó

TKT-010a siembra, mediante la migración `0008` y con identificadores fijos, la empresa única «Constructora Celsius» y los cuatro tipos de partida de `PA-01`. La migración es solo de datos: usa `ON CONFLICT DO NOTHING`, de modo que una fila existente con otros valores queda intacta, y su bajada borra por identificador y la detiene la clave foránea `RESTRICT` si una obra o una partida ya usa lo sembrado.

La plantilla de pruebas se construye con `alembic upgrade head`, así que nace con esa semilla, igual que una base desplegada. Para que TKT-011 siga verificando lo mismo, la fábrica `DatosPresupuesto.tipo_partida` devuelve el tipo existente cuando la clave ya está, y tres pruebas de TKT-011 cambiaron su precondición de «tabla vacía» a «la tabla no cambió». La persona dueña aprobó esas ediciones el 2026-11-02 (P2).

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-02 | TC-A05 compara el número de empresas tomado **después** de crear la fila que referencia, no antes | La fábrica `partida()` crea su propia empresa (obra, nivel, área), así que el recuento previo daba 2 frente a 1. Defecto del test, corregido por `tester-backend`; la migración no cambió |
| 2026-11-02 | TC-A03 retoca además el nombre de `MUROS` y comprueba que sobrevive a la resiembra | Cubre `M5` también para `tipo_partida`; son pocas líneas |
| 2026-11-02 | TC-A07 usa `walk_revisions()` y una aserción propia en lugar de `get_revision("0008")` | Da un mensaje limpio en el rojo en lugar de una excepción de Alembic; afirma lo mismo |
| 2026-11-02 | TC-INV-A1 incluye los privilegios de columna (`attacl`) además de los de tabla | El bloqueo de `password_hash` al rol de lectura es por privilegio de columna |
| 2026-11-02 | TC-A06, TC-INV-A1 y TC-INV-A2 llevan la precondición «hay una empresa y cuatro tipos sembrados» | Sin ella nacían en verde de forma vacía, sin migración |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0008_semilla_empresa_y_tipos_de_partida.py` | nuevo | infraestructura |
| `backend/tests/test_tkt010_migracion.py` | nuevo | pruebas |
| `backend/tests/conftest.py` | modificado: solo `DatosPresupuesto.tipo_partida` | pruebas |
| `backend/tests/test_tkt011_estructura.py` | modificado: precondición de `ca20` y de `ca01[empresa_con_obra]` | pruebas |
| `backend/tests/test_tkt011_regresion.py` | modificado: precondición de TC-18 | pruebas |
| `docs/05-tickets-trabajo.md` | modificado: dependencia de TKT-011b y partición en dos hermanos | documentación |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-A01 | `test_tkt010_ca01_la_migracion_siembra_la_empresa_y_los_cuatro_tipos` | feliz | `CA-1` | FALLA | PASA |
| TC-A02 | `test_tkt010_ca01_una_obra_referencia_la_empresa_sembrada` | feliz | `CA-1` | FALLA | PASA |
| TC-A03 | `test_tkt010_ca02_la_siembra_no_sobrescribe_una_empresa_cambiada` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-A04 | `test_tkt010_ca02_bajar_y_subir_no_duplica` | **rechazo** | `CA-2`, `CA-R2` | FALLA | PASA |
| TC-A05 | `test_tkt010_ca03_la_bajada_se_niega_si_lo_sembrado_esta_en_uso` (2 casos) | **rechazo** | `CA-3` | FALLA | PASA |
| TC-A06 | `test_tkt010_ca10_la_migracion_no_siembra_usuarios_ni_insumos` | **rechazo** | `CA-10` | FALLA | PASA |
| TC-A07 | `test_tkt010_car2_una_sola_cabeza_y_0008_cuelga_de_0007` | regresión | `CA-R2` | FALLA | PASA |
| TC-INV-A1 | `test_tkt010_car3_los_privilegios_no_cambian` | **rechazo** y regresión | `CA-R3` | FALLA | PASA |
| TC-INV-A2 | `test_tkt010_car4_las_restricciones_no_cambian` | regresión | `CA-R4` | FALLA | PASA |
| TC-INV-A3 | Las pruebas de TKT-011 de la tabla de `A8`, con la fábrica y las tres ediciones | regresión | `CA-R1` | 12 FALLAN | PASAN |

Los criterios `CA-4` a `CA-9`, `CA-R5` (la parte de la herramienta), `CA-R6` y `CA-R7` son de TKT-010b.

### Ciclo TDD por fila

#### Fila A1 · migración `0008`, fábrica y pruebas

**Rojo** — `uv run pytest tests/test_tkt010_migracion.py -q` antes de que existiera `v0008`:

```text
10 failed in 4.89s
```

Todos fallan por aserciones o por `pytest.fail`, ninguno por importación, sintaxis o entorno. Ejemplos literales: TC-A01 `assert [] == [(UUID('c1e0a...00', True, 6)]`; TC-A03 `Failed: La migración 0008 no existe todavía: falta v0008_semilla_empresa_y_tipos_de_partida.py`; TC-A07 `AssertionError: La revisión 0008 no existe todavía`. TC-A06, TC-INV-A1 y TC-INV-A2 habrían nacido en verde de forma vacía y se les añadió la precondición.

**Experimento E-4** — con `v0008` aplicada y sin fábrica ni ediciones, las seis suites de TKT-011:

```text
12 failed, 273 passed in 32.80s
```

Los doce nodeids rojos son exactamente los de la tabla de `A8`: 7 en `test_tkt011_linea_base.py`, 2 en `test_tkt011_permisos.py`, 2 en `test_tkt011_estructura.py` (`ca20` y `ca01[empresa_con_obra]`) y 1 en `test_tkt011_regresion.py` (TC-18). Ningún caso distinto de los previstos.

**Verde** — migración sola, antes de la fábrica: `9 passed, 1 failed` (TC-A05 por el defecto del test indicado arriba, que `tester-backend` corrigió). Con las tres ediciones y sin fábrica: `9 failed, 286 passed`, los nueve de la fábrica. Con todo:

```text
uv run pytest tests/test_tkt010_migracion.py tests/test_tkt011_estructura.py tests/test_tkt011_linea_base.py tests/test_tkt011_permisos.py tests/test_tkt011_importacion.py tests/test_tkt011_regresion.py tests/test_tkt011_migracion_linea_base.py -q
295 passed in 47.41s
uv run pytest tests/test_tkt057_migracion.py tests/test_tkt006_esquema.py tests/test_tkt007_esquema.py tests/test_identidad_migracion.py tests/test_identidad_migracion_cli.py tests/test_identidad_migracion_ciclo.py tests/test_identidad_semilla.py tests/test_identidad_credenciales.py tests/test_identidad_sin_create_all.py -q
59 passed in 10.91s
```

**Refactor:** sin refactor; el único cambio posterior fue de formato (`ruff format` pidió cerrar la comillas del docstring de la migración en la misma línea del texto y partir una consulta larga en la fábrica).

**Tests devueltos al tester:** TC-A05, caso `partida_con_el_tipo_muros`. El desarrollador comprobó que la migración cumplía el diseño y que el fallo (`assert 2 == 1`) era del test: tomaba el recuento de empresas antes de que la fábrica creara la suya. El tester movió el recuento después de crear la fila que referencia y conservó el resto de aserciones.

#### Fila A2 · cierre de TKT-010a

**Mutación en rutas críticas** — cada mutante se aplicó, se vio el test en rojo y se revirtió; el SHA-256 de `v0008` y de `conftest.py` coincide con el original tras cada reversión.

| Mutante | Cambio | Test que cayó | Mensaje |
|---|---|---|---|
| MA-1 | `ON CONFLICT DO NOTHING` de `empresa` pasa a `ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre` | TC-A03 | el nombre sembrado pisó «Otra Constructora» |
| MA-2 | sin `ON CONFLICT` en `tipo_partida` | TC-A03 | `UniqueViolation … pk_tipo_partida` |
| MA-3 | la bajada borra antes las obras de la empresa | TC-A05, caso de obra | `DID NOT RAISE DBAPIError` |
| MA-4 | la fábrica vuelve a insertar siempre | los nueve de la fábrica | `UniqueViolation … uq_tipo_partida_clave`, clave `MUROS` |

**Evidencia de ejecución al cerrar**, con `docker info` respondiendo (servidor 29.9.2), desde `backend/`:

```text
uv run ruff format --check .   -> 176 files already formatted
uv run ruff check .            -> All checks passed!
uv run mypy .                  -> Success: no issues found in 176 source files
uv run lint-imports            -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float -> archivos revisados: 19; hallazgos: 0
uv run pytest                  -> 1698 passed in 293.89s (0:04:53)
```

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | por omisión del agente | por omisión del agente | — |
| A1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A1 · verde, migración | `desarrollador-sql` | `haiku` | `haiku` | — |
| A1 · TC-A05, E-4 y tres ediciones | `tester-backend` | `sonnet` | `sonnet` | Devuelto por el desarrollador; defecto del test |
| A1 · verde, fábrica | `desarrollador-sql` | `haiku` | `haiku` | — |
| A2 · mutantes y suite completa | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditoría de arquitectura | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Auditoría de SQL | `auditor-sql` | `sonnet` | `sonnet` | — |

Ningún paso subió ni bajó de modelo.

## Resultado contra los criterios de aceptación

Los de TKT-010a, con los criterios de TKT-010b marcados como pendientes de su entrega.

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-A01, TC-A02 |
| `CA-2` | `[M]` | Cumplido | TC-A03, TC-A04; MA-1, MA-2 |
| `CA-3` | `[S]` | Cumplido | TC-A05; MA-3 |
| `CA-10` | `[M]` | Parcial: el escenario de la migración (TC-A06) cumplido; el de las demás tablas sembradas por la herramienta es de TKT-010b | TC-A06 |
| `CA-R1` | `[M]` | Cumplido | TC-INV-A3, E-4, MA-4 |
| `CA-R2` | `[M]` | Cumplido | TC-A04, TC-A07 |
| `CA-R3` | `[M]` | Cumplido | TC-INV-A1 |
| `CA-R4` | `[M]` | Cumplido | TC-INV-A2 |
| `CA-R5` | `[M]` | Cumplido para el código de esta entrega (la herramienta no existe aún) | Salida de `ruff`, `mypy`, `lint-imports` y `verificar_float` |
| `CA-R6` | `[M]` | Pendiente de TKT-010b: la documentación de esta entrega no deja enlaces rotos salvo los de `impl.md`, que este archivo resuelve | `verificar_docs` |
| `CA-4` a `CA-9`, `CA-R7` | `[M]` | Pendientes: son de TKT-010b | — |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` con observaciones | Tres observaciones (F006 a F008), ninguna bloqueante; recorrió las 17 reglas y repitió la suite: 1698 en verde | 1 |
| `auditor-sql` | `APROBADO` | Cinco observaciones (F001 a F005), ninguna bloqueante | 1 |
| `auditor-codigo` | No despachado: el cambio de TKT-010a no añade código de aplicación, solo una migración de datos, una fábrica de pruebas y pruebas | — | — |
| `auditor-seguridad` | No despachado: sin endpoint, sesión, archivo, secreto ni dependencia | — | — |
| `auditor-docs` | `APROBADO` tras un ciclo de corrección | Primera pasada `REQUIERE CAMBIOS` (un Mayor y cuatro Menores, F009 a F013); reauditoría con el informe previo: los cinco `Resuelto`, ninguno `Nuevo` | 2 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | `auditor-sql` | Observación | `v0008_semilla_empresa_y_tipos_de_partida.py:1` | El docstring explica que `RESTRICT` detiene la bajada, pero el comando y el respaldo previo solo están en el diseño | Nuevo; opcional, no se aplica para no desviar el docstring del literal del diseño |
| F002 | `auditor-sql` | Observación | `v0008…py:29-30` | La bajada borra por identificador una empresa renombrada que nadie referencia | Nuevo; aceptado por la persona dueña con el supuesto `A1` |
| F003 | `auditor-sql` | Observación | `v0008…py:13-17` | En una base con otra empresa de otro identificador, la subida añade una segunda | Nuevo; es la pregunta `A9` de TKT-012 |
| F004 | `auditor-sql` | Observación | `test_tkt010_migracion.py:329-381` | TC-A05 prueba dos de las cuatro rutas `RESTRICT` hacia lo sembrado | Nuevo; misma garantía del motor, sin riesgo real |
| F005 | `auditor-sql` | Observación | `test_tkt010_migracion.py:279` y `:72-84` | TC-A03 lee `_SUBIDA` (nombre privado) y `TABLAS_SIN_FILAS` no incluye las copias de la línea base | Nuevo; sin acción |
| F006 | `auditor-arquitectura` | Observación | `test_tkt010_migracion.py:329-381` | Misma cobertura parcial de las rutas `RESTRICT` que F004; ninguna prueba fija que una línea base congelada con sus copias detenga la bajada | Persiste de F004; sin acción, anotado como fuera de alcance |
| F007 | `auditor-arquitectura` | Observación | `v0008…py:14-17` | `ON CONFLICT DO NOTHING` sin destino solo detecta el conflicto por `id`; una empresa previa con otro `id` produciría una segunda | Persiste de F003; caso teórico, lo resuelve TKT-012 (`A9`) |
| F008 | `auditor-arquitectura` | Observación | `sdd/tickets/tkt-010/_index.md` | Estado y rama del índice desactualizados | Resuelto: se actualizan al cerrar esta fase |
| F009 | `auditor-docs` | Mayor | `v0008_semilla_empresa_y_tipos_de_partida.py:1` y `design.md:75` | El docstring de la migración citaba `ADR-032`, que no existe hasta TKT-010b; `verificar_docs.py` no revisa archivos `.py` | Resuelto: ahora cita «(`M1`, `PA-01`, ADR-008)»; el docstring coincide carácter a carácter con el literal del diseño |
| F010 | `auditor-docs` | Menor | `_index.md:21` | La ficha omitía TKT-011b como dependencia | Resuelto |
| F011 | `auditor-docs` | Menor | `spec.md:315` | La fila I de la DoR hablaba de dos dependencias | Resuelto |
| F012 | `auditor-docs` | Menor | `design.md:296-297` | Las filas A1 y A2 seguían en «Pendiente» | Resuelto: ahora «Hecho»; B1 a B5 siguen «Pendiente» |
| F013 | `auditor-docs` | Menor | `spec.md:345` | La pregunta A8 seguía «Pendiente para `/sdd-disenar`» | Resuelto: «Cerrado en el diseño» |

En `/sdd-completar`, la auditoría de cierre de `auditor-docs` pidió cambios otra vez (cinco Menores y dos Observaciones, F014 a F020 en esta numeración): el docstring de la migración presentaba en presente una herramienta de TKT-010b (corregido por `corrector-revision`, con `ruff`, `verificar_docs` y las diez pruebas de la migración en verde), y cinco desajustes de redacción entre `delta.md`, `_index.md` y `_evolucion.md` (resueltos por el orquestador con el texto literal pedido, según el criterio de parada de redacción). Dos puntos no se aplicaron tal como se pedían: no se añadieron criterios a TKT-012 ni a TKT-014 en `docs/05-tickets-trabajo.md`, porque amplían el alcance de otros tickets y es decisión de la persona dueña (el hub lo dice y queda como entrada de sus `/sdd-definir`); y la Observación sobre el ADR-032 se mantiene hasta que TKT-010b lo cree.

Los identificadores F001 a F005 de los informes de `auditor-sql`, `auditor-arquitectura` y `auditor-docs` se repetían entre auditores; en esta tabla se renumeran de forma única, F001 a F013, en el orden en que se registraron.

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `backend/tests/test_tkt010_migracion.py` | Un tercer caso de TC-A05 con `presupuesto_control` cuando exista una fábrica para esa tabla | Baja |
| `docs/03-modelo-datos.md:235` | Podría mencionar que la fila única de `empresa` la fija la migración `0008` | Baja; entra en la documentación de TKT-010b |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/05-tickets-trabajo.md` | La ficha de TKT-010 depende también de TKT-011b; la línea de partición de TKT-011 y la nota del sprint 2 lo reflejan; subsección «Partición en dos tickets hermanos» de TKT-010 |

El resto de la documentación de `S1` (`CLAUDE.md`, `README.md`, `llms.txt`, `docs/arranque-local.md`, `.env.example`, criterios de TKT-010 y ADR-032) pertenece a TKT-010b.

`python tools/verificar_docs.py` → único problema antes de este archivo: enlaces rotos hacia `impl.md`, que este archivo resuelve.

## Verificación en `/sdd-revisar` (2026-11-02)

Comprobaciones ejecutadas de nuevo por el orquestador, sin fiarse de las anteriores, con `docker info` respondiendo (servidor 29.9.2):

```text
uv run ruff format --check .                    -> 176 files already formatted
uv run ruff check .                             -> All checks passed!
uv run mypy .                                   -> Success: no issues found in 176 source files
uv run lint-imports                             -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float   -> archivos revisados: 19; hallazgos: 0
uv run pytest -q                                -> 1698 passed in 318.49s (0:05:18)
python tools/verificar_docs.py                  -> ✓ Sin problemas.
python -m unittest discover -s tools/tests      -> Ran 474 tests in 19.841s — OK
```

Tras la suite completa, el corrector solo cambió un docstring y textos de documentación; `uv run pytest tests/test_tkt010_migracion.py` dio `10 passed` después de esos cambios, y `ruff` y `verificar_docs` siguieron limpios.

`auditor-arquitectura` y `auditor-sql` auditaron el diff de código en `/sdd-ejecutar`. En `/sdd-revisar` no se reauditaron porque el código no cambió desde entonces salvo el docstring de la migración, comprobado por `auditor-docs` contra el literal del diseño. Solo `auditor-docs` se despachó en esta fase.

Criterios `[M]` de TKT-010a: todos con resultado explícito y evidencia en la tabla anterior. `CA-10` queda cumplido en su escenario de la migración; el de las tablas que siembra la herramienta es de TKT-010b. `CA-R6` se verifica en el PR de TKT-010a (`/sdd-completar`) con `verificar_docs`, que hoy da «Sin problemas».

## Verificación final

- [x] Los criterios `[M]` de TKT-010a cumplidos con evidencia
- [x] Ciclo TDD completo: rojo antes de verde, ningún test editado por un desarrollador (las tres ediciones de TKT-011 las hizo `tester-backend` con aprobación de la persona dueña)
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: cuatro mutantes, cuatro tests en rojo
- [x] Todas las auditorías de esta fase `APROBADO` (`auditor-arquitectura` con observaciones y `auditor-sql`); `auditor-docs` queda para `/sdd-revisar`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada por esta entrega actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta (`tkt-010a-migracion-semilla`) y sin secretos en el diff
