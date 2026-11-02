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

---

## TKT-010b · Ejecución de la herramienta de siembra local

> Segunda entrega hermana (filas B1 a B5 del diseño). TKT-010a quedó fusionada en `Produccion` con el PR 33 antes de empezar.

## Qué se implementó (TKT-010b)

La herramienta `backend/herramientas/semilla_local.py`, que se ejecuta con `uv run --env-file ../.env python -m herramientas.semilla_local`, siembra en una base local seis usuarios, uno por rol de acceso, y 27 insumos sintéticos de tablaroca con su precio general. Se niega antes de conectar si el host de la base no es local o si `PGHOSTADDR` o `PGSERVICE` redirigen la conexión, exige la contraseña en `CIMENTA_SEMILLA_CONTRASENA`, deriva cada hash con `ContrasenasArgon2`, escribe en una sola transacción y nunca sobrescribe una fila existente. Se entrega con la documentación de arranque, `.env.example` y el ADR-032, que registra por qué la empresa y los tipos van en migración y los usuarios y los insumos en una herramienta local.

## Ajustes respecto al design (TKT-010b)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-02 | El ADR se llama `20261102-semilla-en-migracion-y-herramienta-local.md`, no `20261101-…` | Es la fecha real de creación; `design.md` se corrigió |
| 2026-11-02 | `create_engine(…, hide_parameters=True)` | `auditor-arquitectura` (Menor): sin ello, un fallo de sentencia vuelca los hashes Argon2id en `[parameters: …]` |
| 2026-11-02 | La cuarta subconsulta del resumen es `count(DISTINCT insumo_id)` | `auditor-sql` (Menor): contar filas daría 28 cuando TKT-014 cargue un segundo precio general |
| 2026-11-02 | Tres pruebas nuevas, TC-B04b, TC-B06b y TC-B09b, y los mutantes MB-9 y MB-10 | Cobertura pedida por los auditores; consta en `design.md` |
| 2026-11-02 | `npm run e2e` no se ejecutó contra la base local de desarrollo | La herramienta escribiría ahí, y `sdd/_evolucion.md` registra el antecedente de un agente que sembró la base de la persona usuaria. TC-B16 ejecuta el script de humo contra un contenedor y el CI corre la comprobación «Humo». Fila B5 marcada `⚠ Ajustado` |
| 2026-11-02 | El resumen de TC-B06b es `(5, 4, 26, 26)` y no `(5, 5, 26, 26)` | Error de cálculo del informe de `auditor-sql`: al borrar las asignaciones 3 y 4 quedan cuatro sembradas; `auditor-sql` lo confirmó a mano en la reauditoría |

## Archivos tocados (TKT-010b)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/herramientas/semilla_local.py` | nuevo | infraestructura (herramienta de operación) |
| `backend/tests/test_tkt010_semilla_local.py` | nuevo | pruebas |
| `docs/adr/20261102-semilla-en-migracion-y-herramienta-local.md` | nuevo | documentación |
| `docs/adr/README.md`, `CLAUDE.md`, `README.md`, `llms.txt` | modificados: fila del ADR-032, comando nuevo y conteo de ADR a 32 | documentación |
| `docs/arranque-local.md`, `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md`, `.env.example` | modificados | documentación y configuración de ejemplo |

## Ciclo TDD por fila (TKT-010b)

| Fila | Rojo | Verde |
|---|---|---|
| B1 · esqueleto, datos y guardas | `9 failed`, todos con «La herramienta herramientas.semilla_local no existe todavía» | `9 passed`; ruff, mypy, `lint-imports` y `verificar_float` limpios |
| B2 · usuarios y asignaciones | `3 failed, 9 passed`: `NotImplementedError` (TC-B04, TC-B16) y «sembrar no existe todavía» (TC-B07) | `1 failed, 11 passed`; TC-B04 solo falla en «27 insumos y 27 precios» del resumen, lo que cierra B3. E-1 confirmado: `id = ANY(:lista)` con `list[uuid.UUID]` llega como `uuid[]` |
| B3 · insumos y precios generales | `10 failed, 11 passed` por insumos y precios sin sembrar; ninguna prueba nació en verde vacía (se añadió la precondición de 27 insumos) | `21 passed` |
| B4 · documentación y ADR-032 | no aplica | `verificar_docs` sin problemas (32 ADR), 474 pruebas de `tools/` y `markdownlint` en verde |
| B5 · mutantes y suite | no aplica | diez mutantes caídos y suite completa en verde |

**Tests devueltos al tester:** ninguno en la fase de ejecución. En el ciclo de corrección, el tester añadió las pruebas antes de que el corrector tocara la herramienta.

**Mutación en rutas críticas** (cada mutante aplicado, visto en rojo y restaurado con el SHA-256 original):

| Mutante | Test que cayó |
|---|---|
| MB-1 · sentencia 1 con `DO UPDATE SET password_hash` | TC-B07 |
| MB-2 · sentencia 3 con `DO UPDATE SET unidad` | TC-B08 |
| MB-3 · sentencia 4 sin `NOT EXISTS` | TC-B09 |
| MB-4 · `if host not in HOSTS_LOCALES` pasa a `if False` | TC-B11 (dos casos) |
| MB-5 · solo `PGHOSTADDR` en `VARIABLES_QUE_REDIRIGEN` | TC-B12, caso `pgservice` |
| MB-6 · contraseña con `os.environ.get(…, "")` | TC-B10 (dos casos) |
| MB-7 · la guarda se llama después de `create_engine` | TC-B11 y TC-B12 (cuatro casos) |
| MB-8 · el `print` del resumen añade la contraseña | TC-B04 |
| MB-9 · `ON CONFLICT (id) DO NOTHING` en usuarios, asignaciones o insumos | TC-B06b (`uq_usuario_email`, `uq_usuario_rol_usuario_id_rol_id`, `uq_insumo_codigo`); en precios es equivalente |
| MB-10 · sin `hide_parameters=True` | TC-B04b |

**Evidencia de ejecución al cerrar**, con `docker info` respondiendo (servidor 29.9.2), desde `backend/`:

```text
uv run ruff format --check .                    -> 178 files already formatted
uv run ruff check .                             -> All checks passed!
uv run mypy .                                   -> Success: no issues found in 178 source files
uv run lint-imports                             -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float   -> archivos revisados: 19; hallazgos: 0
uv run pytest -q                                -> 1722 passed in 340.21s (0:05:40)
python tools/verificar_docs.py                  -> ✓ Sin problemas.
python -m unittest discover -s tools/tests      -> Ran 474 tests … OK
```

## Modelo por paso (TKT-010b)

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | por omisión | por omisión | — |
| B1, B2 y B3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| B1, B2 y B3 · verde | `desarrollador-sql` | `haiku` | `haiku` | — |
| B4 · documentación y ADR | `desarrollador-sql` | `haiku` | `haiku` | — |
| B5 · mutantes y suite | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditorías de arquitectura y SQL | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |
| Ciclo de corrección 1 · pruebas | `tester-backend` | `sonnet` | `sonnet` | — |
| Ciclo de corrección 1 · código | `corrector-revision` | `haiku` | `haiku` | — |
| Reauditoría de SQL | `auditor-sql` | `sonnet` | `sonnet` | Incluía un hallazgo Mayor |
| Reauditoría de arquitectura | `auditor-arquitectura` | `sonnet` | `haiku` | Hallazgo Menor ya corregido, acotado según la metodología |

Ningún paso de desarrollo subió de modelo.

## Resultado contra los criterios de aceptación (TKT-010b)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-4` | `[M]` | Cumplido | TC-B03, TC-B04, TC-B04b |
| `CA-5` | `[M]` | Cumplido | TC-B01, TC-B05 |
| `CA-6` | `[M]` | Cumplido | TC-B06, TC-B06b, TC-B07, TC-B08, TC-B09, TC-B09b; MB-1 a MB-3 y MB-9 |
| `CA-7` | `[M]` | Cumplido | TC-B10; MB-6 |
| `CA-8` | `[M]` | Cumplido | TC-B11, TC-B12; MB-4, MB-5 y MB-7 |
| `CA-9` | `[M]` | Cumplido | TC-B13, TC-B14 |
| `CA-10` | `[M]` | Cumplido (el escenario de la migración, en TKT-010a) | TC-B15 |
| `CA-R5` | `[M]` | Cumplido | TC-B02 y la salida de `ruff`, `mypy`, `lint-imports` y `verificar_float` |
| `CA-R6` | `[M]` | Cumplido localmente; se confirma en el PR | `verificar_docs` sin problemas |
| `CA-R7` | `[M]` | Cumplido | TC-B16 |

## Auditorías (TKT-010b)

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-sql` | `APROBADO` | Primera pasada con un Mayor y dos Menores; los tres `Resuelto` en la reauditoría, sin hallazgos nuevos | 2 |
| `auditor-arquitectura` | `REQUIERE CAMBIOS` en la reauditoría por un Menor de documentación, resuelto por el orquestador | El Menor de código quedó `Resuelto`; el Menor de documentación (literales del diseño) lo resolvió el orquestador según el criterio de parada de redacción, y la Observación de trazabilidad se atendió al añadir las tres pruebas nuevas a `design.md` | 2 |
| `auditor-codigo`, `auditor-seguridad`, `auditor-docs` | Ver «Verificación en `/sdd-revisar` (TKT-010b)» al final de este documento | | |

### Hallazgos y su resolución (TKT-010b)

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F021 | `auditor-arquitectura` | Menor | `semilla_local.py:295` | El docstring prometía no imprimir hashes, pero un fallo de sentencia los volcaba en `[parameters: …]` | Resuelto: `hide_parameters=True` y TC-B04b |
| F022 | `auditor-sql` | Mayor | `test_tkt010_semilla_local.py:729-848` | Ninguna prueba cubría una fila ajena con la misma única y otro `id` | Resuelto: TC-B06b ata el mutante MB-9 |
| F023 | `auditor-sql` | Menor | `semilla_local.py:223` | El resumen contaba filas de precio general, no insumos | Resuelto: `count(DISTINCT insumo_id)` y TC-B09b |
| F024 | `auditor-sql` | Menor | `test_tkt010_semilla_local.py:973-976` | La consulta con `%%simulad%%` iba sin parámetros y sin control positivo | Resuelto |
| F025 | `auditor-arquitectura` | Menor | `design.md:154` y `:189` | Los literales del diseño no reflejaban el cambio | Resuelto por el orquestador |
| F026 | `auditor-arquitectura` | Observación | `test_tkt010_semilla_local.py:494`, `:905`, `:1018` | TC-B04b, TC-B06b y TC-B09b no estaban en el plan del diseño | Resuelto: añadidos a `design.md` |

Observaciones que no bloquean y que se anotan fuera de alcance: la siembra no asienta en la bitácora (decidido, `A7`); la guarda por host no cubre un túnel hacia una base remota; la herramienta escribe con el rol de migración, igual que `contrasenas_roles`; si una fila ajena choca, el resumen muestra una cifra menor y devuelve 0 sin avisar; `NOT EXISTS` no mira `vigente_hasta`; y falta una fila MB-11 para `count(*)` en el diseño.

## Hallazgos fuera de alcance (TKT-010b)

| Archivo | Observación | Prioridad |
|---|---|---|
| `backend/herramientas/semilla_local.py` y `frontend/e2e/sembrar_usuario_humo.py` | La guarda por host está duplicada, porque el script de humo no es importable | Baja, ya registrada en el ADR-032 |
| `backend/herramientas/semilla_local.py` | Devolver un código distinto de 0 o avisar cuando el resumen sea menor que 6, 6, 27 y 27 | Baja |
| `README.md` | La cifra de ADR de «Lo entregado, en cifras» ya estaba desactualizada antes de este ticket | Baja |
| Vale | No está instalado en local: la prosa se revisó a mano y la comprobación de CI lo ejecuta | Baja |

## Documentación actualizada (TKT-010b)

`CLAUDE.md` (comando nuevo y conteo de ADR), `README.md`, `llms.txt`, `docs/arranque-local.md`, `.env.example`, `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md` (título, «Qué hace» y criterios de TKT-010) y el ADR-032 con su fila en `docs/adr/README.md`. `python tools/verificar_docs.py` → `✓ Sin problemas.`

## Verificación final (TKT-010b)

- [x] Todos los criterios `[M]` de TKT-010b cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: diez mutantes, diez con su test en rojo (en MB-9, la sentencia de precios es equivalente y se excluye de ese recuento)
- [x] `auditor-sql` `APROBADO`; `auditor-arquitectura` sin hallazgos de código pendientes
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta (`tkt-010b-herramienta-semilla-local`) y sin secretos en el diff

## Verificación en `/sdd-revisar` (TKT-010b, 2026-11-02)

**Auditorías.** `auditor-arquitectura` y `auditor-sql` auditaron el código en `/sdd-ejecutar` y se reauditaron allí; en esta fase se despacharon `auditor-codigo`, `auditor-seguridad` y `auditor-docs`.

| Auditor | Primera pasada | Reauditorías | Veredicto final |
|---|---|---|---|
| `auditor-codigo` | `REQUIERE CAMBIOS`: ocho Menores | Ciclo 2: seis resueltos, dos parciales y dos Menores nuevos. Ciclo 3: queda un Menor (N001) más dos Observaciones | `APROBADO` condicionado a N001, que se aplicó después (ver abajo) |
| `auditor-seguridad` | `APROBADO` con dos Bajas | Ciclo 2: las dos `Resuelto`, sin hallazgos nuevos; los siete mutantes de la guarda y del volcado cayeron | `APROBADO` |
| `auditor-docs` | `REQUIERE CAMBIOS`: dos Mayores y cuatro Menores | Ciclo 2: los siete aplicados `Resuelto`, un Menor nuevo (el diseño no recogía el comportamiento nuevo de `main()`) | `APROBADO`: el Menor lo resolvió el orquestador con el texto literal pedido, según el criterio de parada de redacción |

Ciclos de corrección: tres, en el máximo. Quedaron Menores de pruebas y Observaciones, sin Críticos ni Mayores vivos.

### Hallazgos y su resolución (`/sdd-revisar`)

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F027 | `auditor-codigo` | Menor | `semilla_local.py:294-296` | `url_migracion()` se evaluaba fuera del `try`: un entorno de conexión incompleto salía con traza | Resuelto: la URL va dentro del `try`, con `except ValueError` para el puerto; TC-B10b |
| F028 | `auditor-seguridad` | Baja | `semilla_local.py:296-301` | `hide_parameters=True` no oculta el `DETAIL: Failing row contains (...)` de PostgreSQL, que lleva el hash | Resuelto: `except SQLAlchemyError` con `SystemExit` sin detalle y `from None`; TC-B04c |
| F029 | `auditor-codigo` | Menor | `semilla_local.py:164-169` | El docstring de `exigir_base_local` decía «Lanza `SystemExit`» aunque con el host ausente deja pasar un `RuntimeError` | Resuelto |
| F030 | `auditor-codigo` y `auditor-seguridad` | Menor y Baja | `test_tkt010_semilla_local.py` (TC-B11) | Solo se probaban dos hosts remotos; el mensaje no decía «exactamente» | Resuelto: nueve casos y mutantes `split(",")`, `lower()`, `startswith` y `strip` caídos |
| F031 | `auditor-codigo` | Menor | `test_tkt010_semilla_local.py` | Andamiaje de la fase roja muerto, `Any` sin justificar, duplicación y un docstring en fase roja | Resuelto: import al inicio, `psycopg.Connection[tuple[Any, ...]]`, `COSTES_BARATOS`, `functools.partial` y docstring |
| F032 | `auditor-codigo` | Menor | `semilla_local.py:44-46` | Comentario en línea que obligaba a envolver la anotación de `costo_unitario` | Resuelto: docstring de clase |
| F033 | `auditor-codigo` | Menor | `test_tkt010_semilla_local.py` (TC-B04b y TC-B04c) | Bloque de captura de fallos duplicado, y falta de prueba con `CIMENTA_DB_HOST` ausente o vacío | Resuelto: helpers `secretos_filtrados` y `capturar_fallo`, y los casos `host_ausente` y `host_vacio` de TC-B10b |
| F034 | `auditor-docs` | Mayor | `README.md` (tabla de cifras) | Decía 21 ADR cuando el resto del repositorio dice 32 | Resuelto |
| F035 | `auditor-docs` | Mayor | `impl.md` | Dos encabezados de primer nivel (MD025) | Resuelto |
| F036 | `auditor-docs` | Menor | `README.md`, `design.md` e `impl.md` | La frase sobre qué cifras comprueba `verificar_docs.py`; la fila B5 del diseño (MB-1 a MB-10, sin `npm run e2e` local, `⚠ Ajustado`); «ocho» en lugar de «diez» mutantes; recuento ambiguo | Resuelto |
| F037 | `auditor-docs` | Observación | ADR-032 y `README.md` | `PA-T13` sin su ticket | Resuelto: «de TKT-006» |
| F038 | `auditor-docs` | Menor | `design.md` (`main()` y plan de pruebas) | El diseño no recogía el comportamiento nuevo de `main()` ni TC-B10b y TC-B04c | Resuelto por el orquestador |
| F039 | `auditor-seguridad` | Observación | `semilla_local.py:7-8` y ADR-032 línea 34 | El docstring prometía «cualquier variable de libpq» y el ADR decía que un destino remoto «no recibe ninguna escritura» sin matizar el túnel | Resuelto: se nombran `PGHOSTADDR` y `PGSERVICE` y el túnel consta entre los costes aceptados |

**Observaciones aceptadas, sin acción:** `CLAUDE.md:63` (documentar la excepción de `herramientas/`) queda a decisión de la persona dueña; el `except ValueError` cubre todo el `try`, pero hoy solo `int()` lo lanza; `ContrasenasArgon2` se construye fuera del `try` (solo mostraría una traza sin secretos); líneas de más de 100 caracteres; `sembrar` larga con SQL incrustado; la importación de `CaptureResult` desde `_pytest.capture` solo para anotar; Vale y lychee no se ejecutan en local.

**Último ajuste, sin una cuarta reauditoría.** Al tercer ciclo quedaba un Menor de pruebas (N001, el bloque de captura repetido en dos pruebas), que el propio auditor dejaba en `APROBADO` si se corregía con el texto literal. Se aplicó (helper `capturar_fallo`) y lo verifiqué yo: las 36 pruebas de la herramienta pasan, y `ruff`, `mypy` y los escáneres de credenciales siguen en verde. Ese último cambio no lo reauditó un auditor.

### Suite y verificadores reejecutados por el orquestador

```text
uv run pytest -q                                -> 1734 passed in 355.17s (0:05:55)
uv run pytest tests/test_tkt010_semilla_local.py tests/test_identidad_credenciales.py tests/test_identidad_sin_create_all.py -q
                                                -> 43 passed in 15.11s   (tras el último ajuste de pruebas)
uv run ruff format --check .                    -> 178 files already formatted
uv run ruff check .                             -> All checks passed!
uv run mypy .                                   -> Success: no issues found in 178 source files
uv run lint-imports                             -> Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float   -> archivos revisados: 19; hallazgos: 0
python tools/verificar_docs.py                  -> ✓ Sin problemas.
npx --no-install markdownlint-cli2 (11 archivos tocados) -> Summary: 0 issues in 0 files
python -m unittest discover -s tools/tests      -> OK (474 pruebas)
```

La suite completa (1734) se ejecutó antes del último ajuste de pruebas y los 36 casos de la herramienta se volvieron a ejecutar después. Lo que solo se puede verificar con el pipeline de un PR real —las diez comprobaciones requeridas, entre ellas «Humo» y «Documentación» con Vale y lychee— se verifica en `/sdd-completar`.

### Resultado final por criterio

Los diez criterios `[M]` de TKT-010b (`CA-4` a `CA-10`, `CA-R5`, `CA-R6` y `CA-R7`) quedan cumplidos con la evidencia de las secciones anteriores. `CA-R6` se confirma además en el PR.

### Deuda y desviaciones

- La fila B5 del diseño está `⚠ Ajustado`: no se ejecutó `npm run e2e` contra la base local de desarrollo.
- Credenciales de prueba con valor en el repositorio público, anteriores a este ticket: `auditor-seguridad` las marca como fuera de alcance y pide una decisión de la persona dueña (`CIMENTA_PRUEBA_CONTRASENA` en `.env.example`, contraseñas de desarrollo de los roles en el diseño de TKT-003 y un literal en una prueba de `tools/`). No se tocaron.
- Sigue pendiente decidir si el estado `PARCIAL` y la regla de partición llegan a la metodología (propuestas de `meta-sdd`).
