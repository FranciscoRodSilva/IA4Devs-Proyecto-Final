# Impl · TKT-004 · Tipos base del dominio con decimal exacto

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

## Qué se implementó

El ticket se ejecutó en las dos entregas que fijó el gate del diseño (D-2), sobre una sola rama. La **entrega A** hizo las filas 1 a 4, la mutación de MT-1 a MT-15, MT-19 y MT-20, y la documentación con ADR-020. La **entrega B** hizo la fila 5 (lista blanca de `import-linter`, `root_packages` y contrato `tipos-base-puro`), MT-16 a MT-18 y los mutantes extra, y las filas «B» de la documentación con ADR-021. Con la B se cumple `CA-10` y el ticket pasa a `EN REVISIÓN`.

Se creó el paquete `backend/tipos_base/`, fuera de `cimenta/`, con `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje` sobre `Decimal`. Calculan con un contexto de `decimal` propio e independiente del del proceso: sumas, restas y productos son exactos, la división da un `Porcentaje` con 28 dígitos o falla con `ZeroDivisionError`, y solo `cuantizar()` redondea, con `ROUND_HALF_UP` `(asumido)`. `serializar()` produce la cadena de escala completa y rechaza lo que no se ha cuantizado. La regla 1 de `CLAUDE.md` deja de ser texto: `RUF032` marca `Decimal(0.1)` y el verificador `herramientas/verificar_float.py` marca `float` en las anotaciones de `dominio/` y de `tipos_base/`.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-19 | **Fila 1 · `⚠ Ajustado`.** `_viene_de_float` cuenta los dígitos significativos **después de quitar los ceros finales** (a mano sobre `as_tuple().digits`, sin `Decimal.normalize`, que redondea al contexto). `design.md` conserva el código original con `len(digits)` | El tester detectó que la heurística de D-1 rechazaba `Decimal("0.5000000000000000000")` y `Decimal("100000000000000.0000")`: valores legítimos con más de 18 dígitos solo por los ceros de escala. Ciclo propio: TC-05b y TC-05c en rojo, corrección en verde. Un `Decimal(float)` real no trae ceros finales, así que el rechazo de `Decimal(0.1)` y `Decimal(2**-30)` no cambia |
| 2026-10-19 | Fila 1: `tipos_base/__init__.py` no exportó `sumar` hasta la fila 2, y `numericos.py` no importó `Iterable` ni `overload` hasta entonces. `_Numero` ya llevaba `__add__` y `__sub__` | El literal del diseño importa `sumar`, que es de la fila 2: con ese import el paquete no carga en la fila 1. `TC-12b` necesita `__add__` para comprobar el `TypeError` al mezclar tipos |
| 2026-10-19 | Fila 1, TC-10: añadir un atributo nuevo a una dataclass `frozen=True, slots=True` lanza `TypeError`, no `AttributeError`, en Python 3.14.3 | Comportamiento de la plataforma, no del diseño. El test acepta ambas excepciones y exige que `valor` no cambie y que `hasattr` sea falso. CA-2 solo pide que la asignación falle |
| 2026-10-19 | Fila 2: TC-34, TC-42 y TC-43 nacieron en verde (el diseño los daba en rojo); TC-28 y TC-33 también, porque sin `__mul__` ni `__truediv__` cualquier combinación da `TypeError` | Los oráculos de `float` y `Fraction` no dependen del código; `__add__` ya existía desde la fila 1. TC-28 y TC-33 son pruebas del espacio negativo: las ejercita la mutación de la fila 6 |
| 2026-10-19 | Fila 4: `ruff format` partió en tres líneas la 87 de `verificar_float.py` (101 caracteres) | El diseño decía «literal»; el cambio es solo de formato, la lógica es idéntica |
| 2026-10-19 | Fila 4: TC-80 se parametrizó con un segundo caso, un `Any` devuelto donde se declara `int` | CA-11 esc. 2 pide «función sin anotar o un `Any`» y el diseño solo traía el primero |
| 2026-10-19 | Cierre, F002: se introdujo la constante `_MODO_REDONDEO = ROUND_HALF_UP` en `numericos.py` y se usa en los tres contextos y en `_a_escala` | El ADR-020 promete que cambiar el modo «toca una sola constante» y el código lo repetía en cuatro sitios |
| 2026-10-19 | Cierre, F003: TC-05d, TC-05e y TC-05f fijan los bordes de la heurística de D-1 | Los mutantes «umbral 18→19», «18→20» y «sin la conjunción de double exacto» sobrevivían a la suite |
| 2026-10-19 | Cierre, F001: la regla 1 de `CLAUDE.md` nombra `ROUND_HALF_UP` `(asumido)` | CA-12 esc. 2 y TC-111 piden que los tres textos digan lo mismo |
| 2026-10-19 | `.claude/agents/desarrollador-dominio.md` pasó a poder escribir en `backend/tipos_base/` | D-4, aprobado en el gate |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/tipos_base/__init__.py` | nuevo | dominio |
| `backend/tipos_base/numericos.py` | nuevo | dominio |
| `backend/herramientas/verificar_float.py` | nuevo | herramientas |
| `backend/pyproject.toml` | modificado: `RUF032` en `select`, `tipos_base.*` en el override de mypy | configuración |
| `backend/tests/test_tipos_base_construccion.py` | nuevo | pruebas |
| `backend/tests/test_tipos_base_aritmetica.py` | nuevo | pruebas |
| `backend/tests/test_tipos_base_explosion.py` | nuevo | pruebas |
| `backend/tests/test_tipos_base_redondeo.py` | nuevo | pruebas |
| `backend/tests/test_tipos_base_mypy.py` | nuevo | pruebas |
| `backend/tests/test_verificar_float.py` | nuevo | pruebas |
| `backend/tests/test_tkt004_conftest.py` | nuevo | pruebas |
| `docs/adr/20261019-tipos-numericos-base.md` | nuevo (ADR-020) | documentación |
| `docs/adr/README.md`, `CLAUDE.md`, `README.md`, `llms.txt`, `docs/arranque-local.md`, `docs/02-arquitectura.md`, `docs/06-stack-tecnologico.md` | modificados | documentación |
| `.claude/skills/conv-dominio-python/SKILL.md`, `.claude/agents/desarrollador-dominio.md` | modificados | convenciones |
| `backend/herramientas/contrato_lista_blanca.py` | nuevo (entrega B) | herramientas |
| `backend/pyproject.toml` | modificado (entrega B): `root_packages`, `contract_types`, `dominio-sin-framework` como `lista_blanca` y el contrato `tipos-base-puro` | configuración |
| `backend/tests/test_fronteras_dominio.py` | nuevo (entrega B) | pruebas |
| `docs/adr/20261019-lista-blanca-del-dominio.md` | nuevo (ADR-021) | documentación |
| `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md`, `docs/convenciones.md` | modificados (ADR-018 «el contrato `dominio-sin-framework` fue sustituido por ADR-021»; `tipos_base/` en la estructura) | documentación |

No hubo cambios en `backend/uv.lock` ni dependencias nuevas.

## Pruebas

Los nombres siguen `test_tkt004_caNN_…`, porque el ticket no tiene escenario HDU. Cada fila de la tabla agrupa los casos parametrizados.

| # | Test (resumen) | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 a TC-02 | construcción desde `str`, `int` y `Decimal`; admite signo | feliz | `CA-1` | FALLA (`ModuleNotFoundError`) | PASA |
| TC-03 a TC-09 | rechazo de `float`, `Decimal` desde `float`, `bool`, cadenas no llanas, no finitos y otros tipos | **rechazo** | `CA-1` | FALLA | PASA |
| TC-05, TC-05b a TC-05f | bordes de la heurística de D-1 | **rechazo** y borde | `CA-1`, D-1 | TC-05b FALLA; el resto PASA | PASA |
| TC-10 a TC-12b | inmutabilidad, igualdad y hash, sin `float()` ni `round()`, tipos que no se mezclan | feliz y **rechazo** | `CA-2` | FALLA | PASA |
| TC-13 | el `conftest.py` no tiene fixtures `autouse` | regresión | `CA-13` | PASA (nace en verde) | PASA |
| TC-20 a TC-27 | producto, suma, colección vacía, sin redondeo intermedio, máximos de columna, contexto del proceso | feliz | `CA-3` | FALLA | PASA |
| TC-28 | combinaciones sin sentido: `TypeError` | **rechazo** | `CA-3` | PASA (nace en verde) | PASA |
| TC-29 a TC-32 | división, 28 dígitos, divisor cero | feliz y **rechazo** | `CA-4` | FALLA | PASA |
| TC-34, TC-35 | `0.1 + 0.2` y el oráculo de `float` | feliz y **rechazo** | `CA-7` | PASA (nacen en verde) | PASA |
| TC-40 a TC-43 | 27 insumos sintéticos, orden, control en `float`, oráculo con `Fraction` | feliz y **rechazo** | `CA-8` | TC-40 y TC-41 FALLAN; TC-42 y TC-43 nacen en verde | PASA |
| TC-50 a TC-55 | cuantizar, empate, rango, nada cuantiza solo | feliz y **rechazo** | `CA-5` | FALLA | PASA |
| TC-56 a TC-61 | serializar, cero negativo, más decimales que la escala, fuera de rango | feliz y **rechazo** | `CA-6` | FALLA | PASA |
| TC-70 a TC-78 | `verificar_float` y `RUF032` | feliz y **rechazo** | `CA-9` | FALLA | PASA |
| TC-79, TC-80 | mypy estricto sobre `tipos_base` | feliz y **rechazo** | `CA-11` | TC-79 nace en verde; TC-80 FALLA | PASA |
| TC-90, TC-98 | `15 kept, 0 broken` en una copia y en el árbol real | feliz | `CA-10`, `CA-R3` | FALLAN (`14 kept`) | PASAN |
| TC-91 a TC-95 | un tercero, un framework directo o indirecto, la interfaz de otro módulo y `tipos_base` impuro rompen su contrato | **rechazo** | `CA-10`, D-5 | TC-91, TC-93, TC-94 y TC-95 FALLAN; TC-92 nace en verde | PASAN |
| TC-96 | los contratos de TKT-002 siguen vigentes (módulo extra, `fastapi`, dominio de otro módulo) | **rechazo**, regresión | `CA-R3` | PASAN (nacen en verde: la lista negra ya los rechazaba) | PASAN |
| TC-97 | un comodín sin coincidencia, un origen o un permitido inexistentes no dan verde | **rechazo** | `CA-10` | FALLAN (tipo de contrato desconocido) | PASAN |
| TC-99, TC-100 | un prefijo de un módulo permitido (`tipos_basefoo`, `cimenta.presupuestox`) no es permitido | **rechazo** | `CA-10`, F003 | PASAN (nacen en verde: el código real ya lo rechaza) | PASAN |

### Ciclo TDD por fila

#### Fila 1 · Construcción, inmutabilidad e igualdad

**Rojo.** El rojo válido es el `ModuleNotFoundError`; con un error de recolección pytest no ejecuta nada, y TC-13 solo corre con `--continue-on-collection-errors`.

```
collected 1 item / 1 error
tests\test_tipos_base_construccion.py:14: in <module>
    from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento
E   ModuleNotFoundError: No module named 'tipos_base'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!
```

**Verde.**

```
collected 29 items
tests\test_tipos_base_construccion.py ............................       [ 96%]
tests\test_tkt004_conftest.py .                                          [100%]
============================= 29 passed in 0.05s ==============================
mypy --strict tipos_base: Success: no issues found in 2 source files
ruff check .: All checks passed!    lint-imports: Contracts: 14 kept, 0 broken.
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno; TC-10 se ajustó por el tester antes del verde (ver «Ajustes»).

**Ajuste de D-1 dentro de esta fila.** Rojo: TC-05b, 8 fallos con `TypeError: … no admite un Decimal construido desde float (Decimal('100000000000000.0000'))` desde `numericos.py:71`. Verde: `103 passed in 0.11s` con `_digitos_significativos` y la segunda condición intacta.

#### Fila 2 · Aritmética, división y los 27 insumos

**Rojo.**

```
E   TypeError: unsupported operand type(s) for *: 'Cantidad' and 'Rendimiento'
E   TypeError: unsupported operand type(s) for /: 'Cantidad' and 'Cantidad'
E   ImportError: cannot import name 'sumar' from 'tipos_base'
======================== 16 failed, 19 passed in 0.19s ========================
```

El total literal del fixture, `3359291.85066580048515`, se recalculó con `fractions.Fraction` sobre el producto cartesiano 3×3×3 y con enteros (`17130615 × 3127553 × 6270037`): coincide, tiene 21 dígitos significativos, y la suma en `float` da `3359291.8506658003`.

**Verde.**

```
64 passed in 0.08s   (filas 1 y 2)
TC-26: producto de los máximos de columna = 9999999999999899990000.0000000001, exacto, sin MemoryError
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

#### Fila 3 · Cuantizar y serializar

**Rojo.**

```
      3 E   AttributeError: 'Cantidad' object has no attribute 'cuantizar'
     12 E   AttributeError: 'Dinero' object has no attribute 'cuantizar'
      5 E   AttributeError: 'Dinero' object has no attribute 'serializar'
26 failed, 1 passed in 0.05s
```

**Verde.**

```
91 passed in 0.11s   (filas 1 a 3)
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

#### Fila 4 · La regla contra `float`

**Rojo.**

```
E   ModuleNotFoundError: No module named 'herramientas.verificar_float'      (x16)
E   AssertionError: All checks passed!  /  assert (3, 'RUF032') in set()     (TC-78)
E   AssertionError: Success: no issues found in 2 source files / assert 0 != 0   (TC-80, x2)
======================== 20 failed, 1 passed in 1.82s =========================
```

La prueba de que RUF032 no es *preview* en Ruff 0.17.1 la ejecutó el orquestador al aprobar el diseño: marca `Decimal(0.1)` con `--isolated --select RUF032`.

**Verde.**

```
21 passed in 1.60s
verificar_float: archivos revisados: 12; hallazgos: 0     (código 0)
ruff check . → All checks passed!    mypy . → Success: no issues found in 91 source files
lint-imports → Contracts: 14 kept, 0 broken.
124 passed in 1.75s   (los tests de TKT-004 sin Docker)
```

**Refactor:** solo el formato de la línea 87. **Tests devueltos al tester:** ninguno.

#### Fila 5 · Fronteras: lista blanca y pureza de `tipos_base` (entrega B)

**Rojo.** Las pruebas de la copia del árbol parten de la lista negra de TKT-002:

```
$ uv run pytest tests/test_fronteras_dominio.py
11 failed, 4 passed in 7.56s
assert (14, 0) == (15, 0)                                  (TC-90, TC-98)
assert 0 == 1   # la lista negra deja pasar requests, numpy, tipos_base con sqlalchemy y la interfaz de otro módulo
tipo de contrato desconocido: lista_blanca                 (TC-97, x3)
```

Nacen en verde TC-92 y los tres casos de TC-96, como preveía el diseño.

**Verde.** El literal del diseño funcionó contra `import-linter` 2.15 y `grimp` 3.17 sin cambios de mecánica; es el único código que el diseño no pudo ejecutar, y quedó comprobado por el desarrollador y por el orquestador. Solo `ruff format` movió saltos de línea.

```
uv run lint-imports → Contracts: 15 kept, 0 broken.
uv run pytest tests/test_fronteras_dominio.py → 15 passed in 7.55s
ruff check . → All checks passed!   mypy . → Success: no issues found in 93 source files
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

**Mutación de la entrega B** (SHA-256 de `contrato_lista_blanca.py` antes y después de cada mutante: `c1dedb6c…70e5f`, idéntico). Ningún mutante dejó la suite en verde.

| Mutante | Cambio | Resultado | Tests que cayeron |
|---|---|---|---|
| MT-16 | `_es_permitido` devuelve `True` si el módulo no empieza por `cimenta` | 6 failed | TC-91, TC-92, TC-93, TC-95, TC-96 |
| MT-16b | `_es_permitido` siempre `True` | 8 failed | los anteriores, TC-94 y TC-95 |
| MT-17 | solo imports directos, sin recorrer indirectos | 1 failed | TC-93 |
| MT-18, MT-18b | sin la rama de la biblioteca estándar; la estándar como violación | 2 failed | TC-90 y TC-98 |
| MT-A | `check` siempre cumplido | 8 failed | TC-91 a TC-96 |
| MT-B, MT-C | sin cada `ValueError` contra el verde vacío | 1 y 2 failed | TC-97 |
| MT-21 (hallazgo F003) | `modulo.startswith(p)` en lugar de `modulo == p or modulo.startswith(f"{p}.")` | sobrevivía a 15 tests; con TC-99 y TC-100, 3 failed | TC-99 (2 casos) y TC-100 |

**Evidencia de ejecución al cerrar** (con Docker 29.8.2 respondiendo; al empezar el demonio no estaba en marcha, y las filas no lo necesitan):

```
uv run pytest -q
215 passed in 48.75s
```

Son 154 pruebas de TKT-004 (136 de la entrega A y 18 de la B) más 61 de identidad (TKT-003). Esta evidencia es **previa a la revisión**, que añadió pruebas: la cifra vigente, 447 con 386 de TKT-004, está en la sección «Revisión». Las de TKT-004 pasan sin Docker (`DOCKER_HOST=tcp://127.0.0.1:9`). Con la entrega B: `lint-imports` da 15 kept, 0 broken; `ruff check`, `ruff format --check` y `mypy` limpios; `uv sync --locked` sin cambio en `uv.lock`.

**Mutación en rutas críticas** (entrega A). Cada mutante se aplicó con el SHA-256 del archivo anotado antes y comprobado al restaurar, y los hashes coinciden con la línea base. Ningún mutante dejó la suite en verde.

| Mutante | Cambio | Tests que cayeron |
|---|---|---|
| MT-1 | `ROUND_HALF_EVEN` en `_a_escala` | TC-50, TC-51 (3 casos) |
| MT-2, MT-3 | `+`, `-`, `*` fuera del contexto exacto; `prec=28` | TC-26, TC-27 |
| MT-4 | `cuantizar` devuelve `self` | 12 casos de `ca05`, `ca03`, `ca06` |
| MT-5 | `serializar` sin rechazar el exceso de decimales | TC-59 |
| MT-6 | `_a_decimal` acepta `float` | TC-03 (4 tipos) |
| MT-7 | sin la comprobación de `bool` | TC-06 |
| MT-8 | regex con `[+-]?` | TC-07 (`+12.10`) |
| MT-9 | `>` en lugar de `>=` en `_en_columna` | TC-53 y TC-61 (7 casos) |
| MT-10 | división entre cero devuelve `Porcentaje("0")` | TC-32 (3 casos) |
| MT-11 | `_DIVISION` con `prec=10` | TC-31, TC-27 |
| MT-12 | sin la normalización del cero negativo | TC-58 |
| MT-13 | `verificar_float` sin la rama `ast.Constant` | TC-72 (`'float'`, 2 casos) |
| MT-14 | sin la rama `ast.AnnAssign` | TC-73 |
| MT-15a, b, c | `main` devuelve 0 siempre; `RUF032` fuera de `select`; `tipos_base.*` fuera del override | 13 casos; TC-78; TC-80 (2 casos) |
| MT-19 | sin `_viene_de_float` | TC-04 y TC-05c (5 casos) |
| MT-20a, b | `autouse=True` en una fixture del `conftest.py` | TC-13; 124 errores de contenedor |
| F003 | umbral 18→19, 18→20, sin la conjunción de double exacto (y 18→17) | TC-05d (4 casos); TC-05e (4 casos); TC-05f y TC-05 |


## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | `haiku` | `haiku` | — |
| Fila 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 1 · verde | `desarrollador-dominio` | `haiku` | `haiku` | — |
| Ajuste de D-1 · rojo y verde | `tester-backend`, `desarrollador-dominio` | `sonnet`, `haiku` | `sonnet`, `haiku` | — |
| Fila 2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 2 · verde | `desarrollador-dominio` | `sonnet` | `sonnet` | Disparador «la fila toca una regla de dinero» (metodología §14) |
| Fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde | `desarrollador-dominio` | `sonnet` | `sonnet` | Mismo disparador |
| Fila 4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | Código literal del diseño; la definición del agente prevé `sonnet` por omisión |
| Fila 6 · mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 7 · documentación | `general-purpose` con `conv-documentacion` | `haiku` | `haiku` | Sustitución: no hay agente redactor (metodología §13) |
| Fila 5 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 5 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | Código literal del diseño; funcionó sin cambios de mecánica |
| Mutación B | `tester-backend` | `sonnet` | `sonnet` | — |
| Documentación B y ADR-021 | `general-purpose` con `conv-documentacion` | `haiku` | `haiku` | Sustitución: no hay agente redactor |
| Corrección F001, F002 y F004 de la B | `corrector-revision` | `haiku` | `haiku` | — |
| F003 de la B | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditoría y reauditoría (A y B) | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Corrección F001 y F002 | `corrector-revision` | `haiku` | `haiku` | — |
| F003 | `tester-backend` | `sonnet` | `sonnet` | — |

Ningún paso subió de modelo.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1`, `CA-2` | `[M]` | Cumplido | TC-01 a TC-13 y TC-05b a TC-05f |
| `CA-3`, `CA-4` | `[M]` | Cumplido | TC-20 a TC-32 |
| `CA-5`, `CA-6` | `[M]` | Cumplido | TC-50 a TC-61 |
| `CA-7`, `CA-8` | `[M]` | Cumplido | TC-34, TC-35, TC-40 a TC-43; fixture sintético con total literal |
| `CA-9` | `[M]` | Cumplido | TC-70 a TC-78; MT-13 a MT-15 |
| `CA-10` | `[M]` | Cumplido | TC-90 a TC-100; MT-16 a MT-18 y extras |
| `CA-11` | `[M]` | Cumplido | TC-79, TC-80; MT-15c |
| `CA-12` | `[M]` | Cumplido | Marcas retiradas, ubicación y modo de redondeo documentados, regla 2 de `CLAUDE.md` y ADR-021; `verificar_docs.py` solo marca el enlace a `delta.md` |
| `CA-13` | `[S]` | Cumplido | 136 pruebas pasan con `DOCKER_HOST` apuntando a un puerto muerto; TC-13 |
| `CA-R1` a `CA-R7` | `[M]` | Cumplido | `ruff`, `mypy`, `uv sync --locked` sin cambio en `uv.lock`, 14 contratos, `verificar_docs`, y la suite completa con Docker: 197 passed |

Todos los Must `[M]` quedan cumplidos.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura`, entrega A | `APROBADO` | 3 Menores, resueltos | 1 |
| `auditor-arquitectura`, entrega B | `APROBADO` | 4 Menores resueltos y 4 observaciones; las de F005 y F007 quedan como deuda anotada | 1 |
| `auditor-sql` | No aplica | Sin esquema ni consulta | — |
| `auditor-seguridad` | No aplica | Sin endpoint, entrada externa, archivo, sesión, Dockerfile, CI ni dependencia nueva | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `CLAUDE.md:20` | La regla 1 no nombraba `ROUND_HALF_UP`, y CA-12 esc. 2 pide que los tres documentos digan lo mismo | Resuelto |
| F002 | arquitectura | Menor | `numericos.py`, ADR-020 | El modo de redondeo estaba repetido en cuatro sitios y el ADR prometía una sola constante | Resuelto con `_MODO_REDONDEO` |
| F003 | arquitectura | Menor | `test_tipos_base_construccion.py` | Los bordes de la heurística de D-1 sobrevivían a tres mutantes | Resuelto con TC-05d, TC-05e y TC-05f |
| F001 (B) | arquitectura | Menor | ADR-021 | No declaraba que el contrato solo ve imports estáticos; decía «archivo» donde el informe imprime módulo | Resuelto: límite declarado y «módulo» |
| F002 (B) | arquitectura | Menor | ADR-018 | Seguía `Aceptado` sin la ampliación de ADR-021 | Resuelto: «Aceptado · el contrato `dominio-sin-framework` fue sustituido por ADR-021» y una nota (redacción corregida en la revisión: se sustituye, no se amplía) |
| F003 (B) | arquitectura | Menor | `contrato_lista_blanca.py`, tests | El mutante `modulo.startswith(p)` sobrevivía a los 15 tests de la entrega B | Resuelto con TC-99 y TC-100 (MT-21) |
| F004 (B) | arquitectura | Menor | `docs/convenciones.md:61` | La estructura del backend omitía `tipos_base/`; omisión del diseño | Resuelto |
| F005, F006, F007 (B) | arquitectura | Observación | contrato propio, límites de `grimp`, `delta.md` de TKT-002 | Ver «Hallazgos fuera de alcance» | Anotados; F006 también en ADR-021 |

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/02-arquitectura.md` §12, `docs/06-stack-tecnologico.md` §13 | No listan ADR-018 (interfaz publicada y contrato de fronteras): es anterior a este ticket | Baja |
| `docs/06-stack-tecnologico.md:520` | El ✅ de «explosión real» enlaza ADR-020, pero este ticket verifica un fixture sintético; la reconciliación con el total real es de TKT-016 | Baja |
| `herramientas/verificar_float.py` | Un `Literal["float"]` daría falso positivo; no detecta alias, `type X = float` ni el límite de un `TypeVar` (`PA-T14`) | Baja |
| `backend/herramientas/contrato_lista_blanca.py` | F005: un dominio con `import cimenta` o `import cimenta.compras` rompe el contrato con la excepción de `grimp` «Modules have shared descendants»: falla cerrado, pero el mensaje es engañoso. Envolver `find_shortest_chain` en `try/except ValueError` | Baja |
| `backend/pyproject.toml`, contratos de TKT-002 | F007: la segunda puerta `cimenta/<m>/__init__.py` que TKT-002 asignó a «TKT-004 y TKT-009» no se cierra aquí; la lista blanca la cierra solo para `dominio/` | Media, hacia TKT-009 |
| `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` | El cuerpo del ADR-018 aún describe el contrato `forbidden` original; solo lleva el marcador de sustitución | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/adr/20261019-tipos-numericos-base.md` | ADR-020, nuevo, con ubicación, aritmética, redondeo, serialización y `float`, y las opciones descartadas |
| `docs/adr/README.md`, `CLAUDE.md`, `README.md`, `llms.txt`, `docs/02-arquitectura.md`, `docs/06-stack-tecnologico.md` | Índice y conteo de ADR (19 a 20); regla 1 sin la marca «desde TKT-004» y con `ROUND_HALF_UP`; estructura del backend; comando `verificar_float`; §7.4 con los tipos y el redondeo; fila de mypy |
| `docs/arranque-local.md` | Comando y códigos de salida de `verificar_float`; los tests de los tipos no necesitan Docker |
| `.claude/skills/conv-dominio-python/SKILL.md` | §1 y §3 alineadas con `cuantizar()` y con los tipos |
| `.claude/agents/desarrollador-dominio.md` | Puede escribir en `backend/tipos_base/` (D-4) |
| Entrega B: `docs/adr/20261019-lista-blanca-del-dominio.md` (ADR-021), `docs/adr/README.md`, ADR-018, `CLAUDE.md` (regla 2, estructura del backend, 21 decisiones), `README.md`, `llms.txt`, `docs/02-arquitectura.md` §12, `docs/06-stack-tecnologico.md` §8, §11 y §13, `docs/arranque-local.md`, `docs/convenciones.md` | La lista blanca del dominio, `tipos-base-puro`, la regla 2 literal y el conteo de 21 ADR |

`python tools/verificar_docs.py` → sin problemas, una vez escrito `delta.md` en `/sdd-completar`. `python tools/extraer_mermaid.py` → código 0. `markdownlint-cli2`, `Vale` y `lychee` no están disponibles en esta sesión y **no se ejecutaron**; los corre el pipeline de TKT-009.

## Revisión (`/sdd-revisar`)

La revisión reejecutó la suite y lanzó tres auditorías independientes desde cero: `auditor-arquitectura`, un auditor de código y un auditor de documentación. Los dos últimos se hicieron por sustitución, porque no existen los agentes `auditor-codigo` ni `auditor-docs` ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)). Las tres dieron `REQUIERE CAMBIOS`; se cerraron en dos ciclos de corrección con TDD (tests en rojo antes del código).

**Hallazgo Mayor, resuelto.** `M-01`: un `Decimal` con exponente enorme (`Decimal('1E+999999999')`) entraba al constructor y bloqueaba el proceso durante segundos en `cuantizar`, `serializar` y `sumar`, con mensajes de error de hasta 1 GB. Es un vector de consumo de memoria y tiempo en el tipo que usarán todos los módulos. Por decisión del usuario, los tipos rechazan al construir un valor con más de 40 decimales o con una magnitud de 10^41 o más `(asumido)`, y las cadenas de más de 100 caracteres y los enteros de más de 140 bits se rechazan antes de convertirlos. Todos los mensajes truncan el valor. Los 9 mutantes del límite mueren.

**Ajustes de la revisión respecto al diseño.** Todos dejan rastro de rojo antes de verde:

| Hallazgo | Cambio |
|---|---|
| `M-01`, N-01 | `_a_decimal` con `_comprobar_exponente`, `_resumen` acotado (un `int` se resume por sus bits), mensajes que distinguen «la magnitud debe ser menor que 10^41» de «admite como máximo 40 decimales». Tests TC-07c a TC-07l |
| m-02, F-01 | Tests de orden dentro de cada tipo (TC-11b, TC-11c) y de `Dinero / Cantidad` (TC-33b): el mutante `order=False` y el que admite esa división sobrevivían |
| F-02, m-03 | Cuantizar y serializar bajo un contexto hostil (TC-27b, TC-27c); un resultado de más de 56 dígitos (TC-26b) |
| F-09 | La regex rechaza dígitos Unicode y saltos de línea (TC-07b) |
| m-05, N-05 | `verificar_float` lee con `utf-8-sig`; un error de sintaxis, un archivo ilegible o un directorio `x.py` son un hallazgo `ruta:línea` con código 1, sin traceback (TC-81, TC-81b, TC-81c, TC-82, TC-83) |
| N-02 | Ids de test sin duplicados dentro de TKT-004 (comprobado con `grep`) |
| `M2` (docs) | `PA-23` en el PRD, decidido por el usuario: el modo `ROUND_HALF_UP` consta como pregunta abierta, 22 a 23 |
| F-03, F-04, F-06, N1, N2, N8 y otros | ADR-020 y ADR-021 declaran los límites reales (imports estáticos, E/S y reloj en la biblioteca estándar, límites del verificador, falso positivo de D-1, límites de entrada); ADR-021 *sustituye* y no amplía el contrato de ADR-018 |

Los textos de `design.md` que decían «ampliado por ADR-021» se corrigieron a «sustituido». El código literal de `design.md` no se actualizó (`_viene_de_float`, los límites de entrada y `verificar_float` evolucionaron): la fuente es `backend/`.

**Decisiones del orquestador sobre hallazgos no aplicados.** `TC-35` y `TC-42` se mantienen como controles negativos documentados de `CA-7` y `CA-8`: no detectarían por sí solos una implementación en `float`, y quien la detecta es `TC-34`. `Literal["float"]` y `Annotated[int, "float"]` dan un falso positivo del verificador, y `type X = float` o `TypeVar(bound=float)` pasan: quedan declarados como límites conocidos (`PA-T14`).

**Suite reejecutada por el revisor, con Docker 29.8.2:**

```
uv run pytest -q                       → 447 passed in 40.37s   (386 de TKT-004 y 61 de identidad)
uv run ruff check .                    → All checks passed!
uv run ruff format --check .           → 94 files already formatted
uv run mypy .                          → Success: no issues found in 94 source files
uv run lint-imports                    → Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 12; hallazgos: 0
uv sync --locked                       → sin cambio en uv.lock
python tools/verificar_docs.py         → solo el enlace roto a delta.md
```

**Veredictos finales:** `auditor-arquitectura` `APROBADO` (ciclo 2); auditor de código `APROBADO` (ciclo 1, sus tres Menores cerrados en el ciclo 2); auditor de documentación, sin hallazgos abiertos tras el ciclo 2 (sus dos Menores finales —un comentario y mis artefactos de `sdd/`— los cerró el orquestador y consta aquí). La última pasada fue una verificación del orquestador con `grep` y la suite completa, no una reauditoría separada.

**Deuda anotada, sin cambio de código** (para `delta.md`): `__bool__` que lance `TypeError`, porque `if consumido:` con `Dinero("0")` sería verdadero (F-07); el mensaje de un `int` de 41 a 42 dígitos se resume como `Decimal`; `import cimenta` en un `dominio/` falla cerrado con un mensaje engañoso de `grimp` (F005); la segunda puerta `cimenta/<m>/__init__.py` va a TKT-009 (F007). Al hacer el commit hay que **separar las entregas A y B en dos PR** (D-2): el árbol las mezcla (F-12).

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en las filas 1 a 5: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba (447 passed con Docker tras la revisión; 215 antes de ella)
- [x] Al menos un test de rechazo por cada criterio con regla
- [x] Mutación en rutas críticas, entregas A y B
- [x] Arquitectura `APROBADO` en las dos entregas; seguridad y SQL no aplican
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación actualizada en este mismo cambio, con los dos ADR
- [x] `ruff`, `mypy` y `lint-imports` limpios (15 contratos)
- [x] Rama `tkt-004-tipos-base-decimal`, sin secretos; sin commit todavía
