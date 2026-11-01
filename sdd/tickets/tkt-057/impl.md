# Impl · TKT-057 · Endurecimiento de la frontera HTTP

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

## Qué se implementó

Rama `tkt-057-endurecimiento-http`, abierta el 2026-10-30 desde `Produccion` (`a944005`), sin commit. Las 16 filas del diseño, en las entregas A (filas 1 a 10) y B (filas 11 a 16), se ejecutaron con el ciclo rojo, verde y refactor, más un ciclo de corrección tras las auditorías de cierre.

- **Límite de intentos** (`M1` a `M3`). Una regla pura en `identidad/dominio/limite_intentos.py` decide, con enteros en microsegundos, si hay un bloqueo vigente por cuenta (5 fallos) o por origen (20 fallos) en una ventana de 15 minutos que es también la duración del bloqueo. `abrir_sesion` lo orquesta en una sola transacción: toma un candado consultivo por correo normalizado, lee el reloj, evalúa el límite antes de buscar la credencial y antes de Argon2, asienta el intento (también el rechazado) en `intento_acceso` y escribe `usuario.bloqueado_hasta` como reflejo para las cuentas reales. Un correo inexistente se bloquea igual que uno real. La migración `v0005` añade `intento_acceso.credenciales_verificadas`, su `CHECK` y tres índices parciales.
- **Token CSRF** (`M4`). `verificar_origen` (la sesión primero, después el par de doble envío, comparado en bytes con `compare_digest`) protege `cerrar_sesion`, con `DENEGAR` a nombre del usuario en transacción propia; `credenciales_con_origen_verificado` protege `POST /sesion` y asienta el rechazo anónimo en `intento_acceso` y en el registro técnico. El token se rota al iniciar y al cerrar sesión.
- **Cabeceras** (`M5`). `MiddlewareCabecerasSeguridad`: HSTS, `nosniff`, `Referrer-Policy: no-referrer`, la política de contenido con el origen del almacén en `img-src`, `media-src` y `connect-src`, y `Cache-Control: no-store` bajo `/api/`; el manejador del `500` las añade él mismo.
- **Configuración** (`M6`). `servidor/ajustes.py` con `pydantic-settings`: solo `CIMENTA_DB_CONTRASENA_APLICACION` es obligatoria al arrancar el servidor; `.env.example` lleva las claves sin valor; `humo` genera las contraseñas; `frontend/scripts/tipos.ts` pasa una contraseña efímera.
- **Pruebas y documentación** (`M7`, `M8`). Nueve archivos `test_tkt057_*`, 17 mutantes de `CA-19` (16 de la tabla de la fila 16 y el M17 de `/sdd-revisar`), el borrador OpenAPI, la especificación, el stack, el modelo de datos, la guía de arranque y el ADR `20261030`.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-30 | Fila 3: `dominio/limite_intentos.py` no importa `collections.abc`; las secuencias se tipan `tuple[int, ...] \| list[int]` en lugar de `Sequence[int]` (`typing.Sequence` lo rechaza Ruff con UP035) | La lista blanca de `test_tkt006_ca13_dominio_de_identidad_puro` (TKT-006) solo admite `__future__`, `dataclasses`, `enum`, `typing` y `uuid`. El test no se toca: se ajusta el dominio nuevo, que es lo que se está escribiendo |
| 2026-10-31 | Fila 11: en `cargar_ajustes(None)`, `AjustesServidor()` lleva `# type: ignore[call-arg]` | `mypy` exige el campo obligatorio en el constructor sin argumentos, y el diseño pide que esa rama lea el entorno. La alternativa (leer `os.environ` por el camino del mapa) cambia lo que dice el diseño. Consecuencia anotada: la rama `None` no distingue mayúsculas y la del mapa sí |
| 2026-10-30 | La suite completa queda en rojo (110 fallos de TKT-006) entre las filas 2 y 5 | Consecuencia del orden del diseño: la columna `NOT NULL` sin `DEFAULT` llega en la fila 2 y el parámetro de `insertar_intento` en la fila 5. Las verificaciones de las filas 3 y 4 corrieron solo sus archivos, y por eso el fallo del dominio no se vio hasta correr la suite completa en la fila 5 |

## Ciclo TDD por fila

### Fila 1 · Experimentos `(sin ejecutar)` del diseño

Se ejecutaron el 2026-10-30 con el entorno del backend (Python 3.14.3, FastAPI 0.159.1, Pydantic 2.14.1, `pydantic-settings` 2.16.1, Starlette 1.9.0, `httpx` 0.28.1) y Docker 29.9.2, en guiones sueltos fuera del repositorio. **Los tres quedan confirmados**; el repositorio no se tocó.

**E1 · una dependencia `def` con un parámetro `BaseModel` de cuerpo no se llama si el cuerpo es inválido — CONFIRMADO.**

```text
a) cuerpo inválido -> status: 422
a) llamadas a dependencia tras inválido: 0
a) llamadas a ruta tras inválido: 0
a2) cuerpo lista -> status: 422 · llamadas a dependencia: 0
b) cuerpo válido -> status: 200 · llamadas a dependencia: 1
c) schema del requestBody: {"$ref": "#/components/schemas/CredencialesDePrueba"}
c) ES $ref AL MODELO SIN ENVOLVER: True
```

**E2 · `pydantic-settings` 2.16.1 con el diseño de `AjustesServidor` — CONFIRMADO (cinco puntos).**

```text
[1] _AjustesDesdeMapa con settings_customise_sources=(init_settings,) ignora os.environ: True
[2] env_ignore_empty=True trata la variable vacía como ausente: True (control con False: '')
[3] hide_input_in_errors=True: str(error) no contiene el valor: True
[4] errors()[0]['loc'] es el nombre del campo: ('db_contrasena_aplicacion',)
[5] repr -> SecretStr('**********'); model_dump_json -> "**********"; get_secret_value() recupera el valor: True
```

Observación para la fila 11: `hide_input_in_errors=True` oculta el valor solo en `str(error)`; `error.errors()` conserva la clave `input`. `cargar_ajustes` usa solo `loc`, y nunca debe serializar `errors()`.

**E3 · `pg_advisory_xact_lock(hashtextextended(...))` con el rol de aplicación — CONFIRMADO.** PostgreSQL real (`postgres:18.6`, imagen de `compose.yaml`), esquema por `alembic upgrade head`.

```text
E3 rol de la conexión 1: ('cimenta_aplicacion',)
E3 T1 adquirió lock de ana: True
E3 lock de otra@ mientras T1 retiene ana: tardó 0.001 s
E3 T2 (mismo correo) sigue bloqueada a los 2.5 s: True
E3 T2 se desbloqueó 0.003 s después del commit de T1
1 passed in 16.01s
```

**Verde:** los tres experimentos confirmados, sin refutación: la fila 2 puede empezar. **Refactor:** no aplica.

### Fila 2 · Migración `v0005` y columna del modelo ORM

**Rojo** (`tester-backend`, `uv run pytest tests/test_tkt057_migracion.py tests/test_identidad_esquema.py tests/test_identidad_permisos_tablas.py`): doce fallos por la razón esperada, el resto verde.

```text
FAILED tests/test_tkt057_migracion.py::test_tkt057_ca08_un_exito_sin_credenciales_verificadas_lo_rechaza_la_base   (UndefinedColumn: credenciales_verificadas)
FAILED tests/test_tkt057_migracion.py::test_tkt057_ca08_un_intento_sin_la_columna_lo_rechaza_not_null_y_no_queda_default   (DID NOT RAISE NotNullViolation)
FAILED tests/test_tkt057_migracion.py::test_tkt057_ca08_las_filas_de_la_version_anterior_quedan_verificadas   (UndefinedColumn)
FAILED tests/test_tkt057_migracion.py::test_tkt057_ca08_la_migracion_se_revierte_y_vuelve_a_subir   (falta la columna, la restricción y los índices)
FAILED tests/test_tkt057_migracion.py::test_tkt057_car1_aplicacion_solo_anexa_intentos_tambien_la_columna_nueva   (UndefinedColumn)
FAILED tests/test_identidad_esquema.py::test_tkt003_ca03_esc01_columnas_y_tipos_del_modelo
FAILED tests/test_identidad_esquema.py::test_tkt003_ca03_esc03_intento_con_correo_inexistente
FAILED tests/test_identidad_esquema.py::test_tkt003_ca03_esc07_claves_foraneas_de_auditoria_y_de_usuario[fk_intento_acceso_usuario_id]
FAILED tests/test_identidad_permisos_tablas.py::test_tkt003_ca06_esc01_aplicacion_registra_y_lee_intentos
FAILED tests/test_identidad_permisos_tablas.py::test_tkt003_ca06_esc02_aplicacion_no_modifica_intento
FAILED tests/test_identidad_permisos_tablas.py::test_tkt003_ca06_esc03_aplicacion_no_borra_intento
FAILED tests/test_identidad_permisos_tablas.py::test_tkt003_ca06_esc04_aplicacion_no_vacia_intentos
12 failed, 14 passed in 6.35s
```

**Nació en verde, a propósito:** TC-INV-2 (`test_tkt057_car3_lectura_no_ve_sesion_ni_password_hash_y_si_bloqueado_hasta`). El invariante 21 ya se cumple hoy; la prueba existe para romperse si `v0005` concede o revoca algo por error. Se demuestra con una mutación en el cierre (`GRANT SELECT ON sesion TO cimenta_lectura`).

**Verde** (`desarrollador-sql`, `sonnet`): `v0005_identidad_intento_verificado.py` con el SQL exacto del diseño y `IntentoAcceso.credenciales_verificadas` en `modelos.py`. Ningún test se tocó en esta fase.

```text
uv run pytest tests/test_tkt057_migracion.py tests/test_identidad_esquema.py tests/test_identidad_permisos_tablas.py tests/test_identidad_migracion.py -q
30 passed in 5.15s
ruff check: All checks passed · ruff format --check: 155 files already formatted · mypy: no issues in 155 source files · lint-imports: 15 kept, 0 broken
```

**Suite completa tras la fila 2:** `110 failed, 1034 passed in 230.40s`. Los 110 fallos son todos de TKT-006 (`inicio_sesion` 40, `sesion_vigente` 40, `permisos_rol` 18, `cierre` 10, `repositorio` 2) y comparten una causa: `insertar_intento` aún no pasa `credenciales_verificadas` y la columna no tiene `DEFAULT` (`NotNullViolation`). Es la consecuencia prevista del orden del diseño, que añade la columna en la fila 2 y el parámetro en la fila 5; **la suite completa queda en rojo hasta la fila 6** y por eso las verificaciones intermedias de las filas 3 a 5 se limitan a sus propios archivos.

**Refactor:** sin refactor.

**Tests devueltos al tester:** ninguno.

### Fila 3 · `dominio/limite_intentos.py`

**Rojo** (`tester-backend`, `uv run pytest tests/test_tkt057_dominio.py`): los 13 casos fallan, todos con la misma razón esperada.

```text
E   ModuleNotFoundError: No module named 'cimenta.identidad.dominio.limite_intentos'
13 failed in 0.16s
```

El tester añadió dos casos que la tabla del diseño no numeraba y que caben sin cambiarla: **TC-08a** (`CA-3`: cinco fallos cuyo último tiene más de una ventana no bloquean) y **TC-08b** (`CA-5`: un fallo en el mismo instante del último éxito no cuenta, es decir, el filtro es `>` estricto). Más TC-08 parametrizado en cuatro valores.

**Verde** (`desarrollador-dominio`, `sonnet`): `limite_intentos.py` con `EstadoLimite`, `instante_de_disparo` y `evaluar_limite`; solo biblioteca estándar, sin `datetime` ni `float`.

```text
uv run pytest tests/test_tkt057_dominio.py -q          13 passed in 0.03s
uv run lint-imports                                    Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float          archivos revisados: 19; hallazgos: 0
uv run ruff check .                                    All checks passed!
uv run ruff format --check .                           157 files already formatted
uv run mypy .                                          Success: no issues found in 157 source files
```

**Refactor:** sin refactor; las ayudas privadas `_disparo_vigente` y `_segundos_de_espera` nacieron separadas. **Tests devueltos al tester:** ninguno. **Mutación:** pendiente para el cierre (`>` por `>=` en la vigencia debe poner en rojo TC-04; ventana inclusiva, TC-03; quitar el filtro del último éxito, TC-05 y TC-08b; división entera sin techo, TC-08).

### Fila 4 · Tres campos de límite en `ConfiguracionIdentidad` (`S2`)

**Rojo** (`tester-backend`, `uv run pytest tests/test_tkt057_configuracion.py tests/test_tkt006_configuracion.py -q`): 24 casos nuevos fallan, ninguno nació en verde, y los 49 de TKT-006 siguen en verde.

```text
TC-14/TC-15 y complemento:  AttributeError: 'ConfiguracionIdentidad' object has no attribute 'limite_fallos_cuenta' / 'limite_ventana'   (3 failed)
TC-16 (3 variables × 7 valores):  Failed: DID NOT RAISE ValueError   (21 failed; las variables CIMENTA_LIMITE_* aún no se validan)
24 failed, 49 passed in 0.48s
```

El tester añadió `"1.5"` a los valores inválidos de TC-16, como hizo TKT-006, y un caso complementario (una variable de límite no arrastra a las otras ni a las caducidades).

**Verde** (`desarrollador-aplicacion`, `haiku`): `configuracion.py` con tres constantes de nombre, tres por omisión y tres campos leídos con el `_leer_entero` existente.

```text
uv run pytest tests/test_tkt057_configuracion.py tests/test_tkt006_configuracion.py -q   73 passed in 0.35s
ruff check: All checks passed! · ruff format --check: 158 files already formatted · mypy: Success: no issues found in 158 source files · lint-imports: 15 kept, 0 broken
```

Nadie construye `ConfiguracionIdentidad(...)` directamente (solo `desde_entorno`), así que ningún test existente se rompe por los campos nuevos. **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

### Fila 5 · Repositorio del límite

**Rojo** (`tester-backend`, `uv run pytest tests/test_tkt057_limite_intentos.py tests/test_tkt006_repositorio.py -q`): 17 casos nuevos (TC-17 a TC-22) y 2 adaptados de TKT-006 fallan por la razón esperada; los 13 restantes de `test_tkt006_repositorio.py` siguen en verde.

```text
TypeError: insertar_intento() got an unexpected keyword argument 'credenciales_verificadas'   (4 + test006 ca02)
NotNullViolation: null value in column "credenciales_verificadas"   (test "exige_credenciales_verificadas")
AttributeError: module '...repositorio' has no attribute 'fallos_de_correo' (x3) · 'fallos_de_origen' (x3) · 'ultimo_exito_de_correo' (x2) · 'fijar_bloqueado_hasta' (x3)
AssertionError: La primera transacción falló: AttributeError(... 'bloquear_correo')   (x3, concurrencia)
19 failed, 13 passed in 5.94s
```

Ninguno nació en verde. El tester añadió tres casos que el diseño no listaba y que son coherentes con él: las consultas devuelven `[]` (no `None`), `fijar_bloqueado_hasta` solo toca al usuario indicado y la clave del bloqueo distingue mayúsculas (el repositorio no normaliza). Renombró `test_tkt006_ca03_...` a `..._insertar_intento_guarda_el_correo_que_se_le_pasa` (`D-4`). La sincronización de TC-22 usa `threading.Event` con tiempos máximos, sin `sleep`.

**Verde** (`desarrollador-aplicacion`, `sonnet`): `insertar_intento` con `credenciales_verificadas` obligatorio por nombre; `bloquear_correo`, `fallos_de_correo`, `fallos_de_origen`, `ultimo_exito_de_correo` y `fijar_bloqueado_hasta`. La única llamada de `abrir_sesion` pasa `credenciales_verificadas=True`, que es lo que TKT-006 hacía de hecho, para no dejar la aplicación rota hasta la fila 6.

```text
uv run pytest tests/test_tkt057_limite_intentos.py tests/test_tkt006_repositorio.py -q   32 passed in 8.05s
uv run pytest -q (suite completa)                                                        1 failed, 1197 passed in 228.64s (0:03:48)
ruff check: All checks passed! · ruff format --check: 159 files already formatted · mypy: Success: no issues found in 159 source files · lint-imports: 15 kept, 0 broken
```

De los 110 fallos tras la fila 2 queda uno: `test_tkt006_dominio.py::test_tkt006_ca13_dominio_de_identidad_puro`, porque `limite_intentos.py` (fila 3) importa `collections.abc` y ese test de TKT-006 solo admite `__future__`, `dataclasses`, `enum`, `typing` y `uuid` en el dominio de identidad. No lo había detectado la fila 3 porque solo corrió sus propios archivos. Se corrige en el dominio (sin tocar el test): ver «Ajustes respecto al design».

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

### Fila 6 · `abrir_sesion` con el límite y el correo normalizado

**Rojo** (`tester-backend`, `uv run pytest tests/test_tkt057_limite_intentos.py tests/test_tkt006_inicio_sesion.py -q`): 22 fallos por comportamiento ausente, ninguno por entorno ni sintaxis.

```text
AttributeError: module '...sesiones' has no attribute 'MENSAJE_LIMITE_INTENTOS'
TC-23/27/36:  assert None == (2026-10-21 09:04 + 900 s)         (bloqueado_hasta sin escribir)
TC-24..32, 34b:  Se esperaba LimiteIntentosExcedido (429); llegó UsuarioAutenticado / SesionInvalida
TC-33:  Salidas: [SesionInvalida(...), SesionInvalida(...)]      (los dos hilos verifican y salen 401)
TC-36/37 por HTTP:  assert 200 == 429  ·  assert 401 == 429
TKT-006 (D-4):  assert ['Ana@Cimenta.TEST'] == ['ana@cimenta.test']   (2 casos)
22 failed, 73 passed in 30.28s
```

Nacen en verde, a propósito (seis casos): **TC-23** (cuatro fallos no bloquean) y **TC-29** (diecinueve fallos de origen no bloquean) son guardas contra un `>=` en el umbral; **TC-28** (un inicio correcto reinicia el recuento) es una guarda contra el sobre-bloqueo; **TC-34** (un fallo de credenciales no escribe en la bitácora) es la regresión del invariante 10 (su variante con rechazo por bloqueo nace roja); **TC-35** (un fallo verifica exactamente un hash, para la cuenta existente y el correo inexistente) es regresión de `RNF-04`/TKT-006. El tester comprueba `reintentar_en_s` con cifras exactas (810, 780, 600, 300, 899, 896) y no con rangos, de modo que fijan el techo y la fórmula `f + M − ahora`. Añadió casos que el diseño no listaba: 19 fallos de origen no bloquean, un segundo antes del vencimiento sigue el `429`, un éxito no reinicia el origen (`D-3`), un correo inexistente y una cuenta real vencen igual, y la constante del mensaje tiene su prueba.

**Verde** (`desarrollador-aplicacion`, `sonnet`): `sesiones.py` con `MENSAJE_LIMITE_INTENTOS`, `_microsegundos`, `_estado_del_limite` y `abrir_sesion` en los cinco pasos del diseño, en una transacción que se confirma antes de lanzar.

```text
uv run pytest tests/test_tkt057_limite_intentos.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_sesion_vigente.py -q   136 passed in 35.06s
uv run pytest -q (suite completa)                                                                                        1224 passed in 240.64s (0:04:00)
TC-33 (concurrencia) 5 corridas seguidas: 5 × "1 passed" (≈4,6 s cada una), sin intermitencia
ruff check: All checks passed! · ruff format --check: 159 files already formatted · mypy: Success · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno. La suite completa vuelve a estar en verde. Mutaciones previstas para el cierre: `>` por `>=` en el umbral, rechazos que cuentan como fallos y quitar `bloquear_correo` (TC-33 debe caer).

### Fila 7 · `par_csrf_valido`, `verificar_origen` y `cerrar_sesion`

**Rojo** (`tester-api`, `uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_cierre.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_enrutador.py -q`): 25 fallos por la razón esperada.

```text
TC-38 ×4 (ambos ausentes, solo cookie, solo cabecera, distintos), la variante no ASCII y TC-41 ×3:  assert 204 == 403   (el cierre no exige token)
TC-41 con transacción propia:  ImportError: cannot import name 'verificar_origen' from 'cimenta.identidad.interfaz'
TC-47 ×15:  ImportError: cannot import name 'par_csrf_valido' from 'cimenta.identidad.api.dependencias'
test_tkt006_ca13_la_interfaz_publica_exigir_rol_y_evaluar_resolucion:  AssertionError: falta 'verificar_origen' en __all__
25 failed, 64 passed in 12.77s
```

Nacen en verde, a propósito: **TC-40** (`sin_cookie` y `sesion_inexistente`: `401 SESION` sin sesión ni token, bitácora vacía), que fija el orden «la sesión antes que el token» y se pondría en rojo con un `verificar_origen` que mirara el token primero; y **TC-39** (par válido: `204` y `revocada_en` escrito), la regresión del camino feliz, porque hoy el cierre ignora el token. Los `204` adaptados de `test_tkt006_cierre.py` y `test_tkt006_permisos_rol.py` enviaban ya el par y siguen en verde. El tester usó un ayudante `cerrar_con_token` con la cabecera `Cookie` explícita, que sobrevive a la rotación de la fila 9, y añadió un caso fuera del plan: la cabecera no ASCII por HTTP (riesgo 7 de la pasada adversarial, `compare_digest` con `str` lanzaría `TypeError` y sería un `500`). TC-41 comprueba el asiento `DENEGAR` entero: una fila a nombre de Ana, `datos_despues == {metodo, ruta, roles_requeridos: []}`, sin token, identificador de sesión ni `correlacion_id` en ninguna columna, y que persiste aunque la petición deshaga la suya.

**Verde** (`desarrollador-api`, `haiku`): `dependencias.py` con `CABECERA_CSRF`, `MENSAJE_ORIGEN_NO_VERIFICADO`, `_esquema_csrf` (`APIKeyHeader`, `auto_error=False`), `par_csrf_valido` (`compare_digest` en bytes UTF-8) y `verificar_origen` (la sesión antes que el token); `cerrar_sesion` depende de `verificar_origen`; `interfaz.py` publica `verificar_origen` (siete nombres) con la convención de las rutas futuras. Context7 confirmó que `APIKeyHeader(auto_error=False)` devuelve `None` si falta la cabecera.

```text
uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_cierre.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_enrutador.py -q   89 passed in 13.08s
uv run pytest -q (suite completa)                                                                                                         1251 passed in 240.01s (0:04:00)
ruff check: All checks passed! · ruff format --check: 160 files already formatted · mypy: Success · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno. El docstring del módulo de `rutas.py` sigue diciendo «verificarlo es de TKT-057»: es cierto mientras `iniciar_sesion` no verifique; se quita en la fila 8.

### Fila 8 · `registrar_rechazo_de_origen` y `credenciales_con_origen_verificado`

**Rojo** (`tester-api`, `uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_cierre.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_sesion_vigente.py tests/test_tkt057_limite_intentos.py -q`): siete fallos por la razón esperada y 204 en verde.

```text
TC-42 sin token, TC-43 (solo cookie / solo cabecera / distintos) y la cabecera no ASCII:  assert 200 == 403   (se abrió sesión sin par CSRF válido)
TC-42 con correo inexistente:  401 CREDENCIALES_INVALIDAS en vez de 403
TC-49 de POST /api/v1/sesion:  assert 'csrf' in set()   (la operación publicada no declara `security`)
7 failed, 204 passed in 45.32s
```

Como la aserción del código falla primero, el rojo aún no ejercita el asiento en `intento_acceso`, la línea `origen_no_verificado`, el contador de hashes ni la bitácora vacía; lo ejercitan al pasar a verde. Nacen en verde, a propósito: **TC-44** (cuerpo sin `contrasena`, sin token y con par distinto → `422 VALIDACION`, cero filas en `intento_acceso`, sin línea de rechazo, sin hash; fija el orden de `D-5` y se pondría en rojo si la dependencia rechazara por origen antes de validar el cuerpo), **CA-R8** (`POST` con par válido y credenciales correctas → `200`, fila exitosa, una sesión), **CA-R7** (par válido y contraseña errónea → `401` con su contrato completo) y las cuatro pruebas de TC-49 que ya se cumplen desde la fila 7. Casos que el tester añadió fuera del plan: TC-42 con correo inexistente (el `403` no revela si la cuenta existe) y la cabecera no ASCII en `POST /sesion`.

**Adaptaciones de pruebas existentes** (hechas por el tester; cada inicio de sesión por HTTP envía ahora una cabecera `Cookie` explícita con `cimenta_csrf=<token>` y `X-CSRF-Token` con el mismo valor): `iniciar_por_http` de `test_tkt006_inicio_sesion.py`, `iniciar` de `test_tkt006_cierre.py`, `iniciar_por_http` y el `POST` con contraseña errónea (~986) de `test_tkt006_permisos_rol.py`, `iniciar_por_http` de `test_tkt006_sesion_vigente.py` y el de `test_tkt057_limite_intentos.py` (TC-36 y TC-37, que el diseño no listaba y habrían pasado a `403`). Los dos sitios que hacían `galleta.load(respuesta.headers["set-cookie"])` leen ahora `headers.get_list("set-cookie")` por nombre. **Decisión del tester:** `test_tkt006_ca05_forma_invalida` (~1401) **no** recibe token: su cuerpo es inválido y debe dar `422` sin token por `D-5`; añadirlo le quitaría valor como regresión del orden. Solo se le añadió un comentario que lo explica. Se acepta.

**Verde** (`desarrollador-api`, `haiku`): `registrar_rechazo_de_origen` y la constante `RUTA_SESION` en `sesiones.py`, `credenciales_con_origen_verificado` en `dependencias.py` e `iniciar_sesion` dependiendo de ella; se quitó «verificarlo es de TKT-057» del docstring de `rutas.py`. Context7 confirmó que FastAPI valida el cuerpo de una dependencia antes de llamarla.

```text
uv run pytest (los seis archivos de la fila) -q    211 passed in 46.25s
uv run pytest -q (suite completa)                  1266 passed in 264.13s (0:04:24)
ruff check: All checks passed! · ruff format --check: 160 files already formatted · mypy: Success · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

**Refactor:** sin refactor, el código ya era mínimo. **Tests devueltos al tester:** ninguno.

### Fila 9 · Rotación del token (`_fijar_cookie_csrf`)

**Rojo** (`tester-api`, reanudado tras un corte por el límite semanal de la API y un reinicio de Docker Desktop; `uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_cierre.py tests/test_tkt006_csrf.py tests/test_tkt006_permisos_rol.py tests/test_tkt006_sesion_vigente.py tests/test_tkt006_enrutador.py -q`): cuatro fallos por la razón esperada.

```text
E  AssertionError: Se esperaba exactamente un Set-Cookie de cimenta_csrf; hay 0: ['cimenta_sesion=...; HttpOnly; Path=/; SameSite=lax; Secure']
FAILED test_tkt057_ca12_esc1_el_inicio_de_sesion_fija_un_token_csrf_nuevo
FAILED test_tkt057_ca12_esc1_tras_el_inicio_la_cookie_nueva_con_la_cabecera_vieja_se_rechaza
FAILED test_tkt057_ca12_esc1_tras_el_inicio_la_cookie_nueva_con_la_cabecera_nueva_cierra
FAILED test_tkt057_ca12_esc2_el_cierre_de_sesion_fija_un_token_csrf_nuevo
4 failed, 202 passed in 32.04s
```

Los tres últimos fallan al obtener el T2 que debe fijar el inicio, antes de llegar a sus aserciones propias (el `403` con cookie T2 y cabecera T1, el `204` con T2 en ambos, y T3 distinto de T2 al cerrar); se verán cuando el inicio rote, y el cierre fallaría aparte si no rotara. Ningún caso nació en verde. **Ajustes a TKT-006: ninguno**, porque los ayudantes `una_cookie` filtran por nombre y ningún test cuenta los `Set-Cookie` totales. Un primer intento del tester, sin Docker, produjo `49 passed, 157 errors` por la ausencia del daemon; esa salida no se acepta como rojo y se repitió con Docker 29.9.2 en marcha.

**Verde** (`desarrollador-api`, `haiku`): en `rutas.py`, `_fijar_cookie_csrf(response) -> str` (mismo `set_cookie` que antes: `cimenta_csrf`, `secure`, sin `httponly`, `samesite=lax`, `path=/`), usada por `obtener_token_csrf`, `iniciar_sesion` y `cerrar_sesion`.

```text
uv run pytest (las siete suites de la fila) -q    206 passed in 30.79s
uv run pytest -q (suite completa)                 1270 passed in 247.75s (0:04:07)
ruff check: All checks passed! · ruff format --check: 160 files already formatted · mypy: Success · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno. La frase «verificarlo es de TKT-057» ya se quitó en la fila 8, así que el diseño no exigía nada más en el docstring.

### Fila 10 · Prueba del enrutador (`S1`) y cierre de la entrega A

Sin código de producción, como preveía el diseño: los 17 casos nuevos (TC-48 y el de `CA-R5`) nacen en verde, porque las filas 7 y 8 ya pusieron la verificación en las dos rutas que mutan. Un test que nace en verde no prueba nada por sí solo, así que el tester demostró que prueban algo con oráculos y con mutaciones sobre producción.

**Oráculos** (rutas de prueba): una ruta `POST`, `PUT`, `PATCH` o `DELETE` sin verificación aparece en la lista como «MÉTODO ruta»; la sesión o el rol solos no cuentan como verificación de origen; una ruta con `verificar_origen` (en el decorador, en un parámetro, en una sub-dependencia o como `credenciales_con_origen_verificado`) no se señala; una lectura no entra en el recorrido; una ruta que ejecuta sin par válido falla las cuatro combinaciones nombrando operación y combinación; un `403` por otro motivo (`ROL_INSUFICIENTE`) no cuenta como rechazo de origen; y una ruta que muta sin entrada en el mapa `CUERPOS_VALIDOS` falla diciéndolo.

**Mutaciones sobre producción** (revertidas; `rutas.py` quedó byte a byte igual al respaldo, `sha256 848a8611…dc81e`):

```text
M1  cerrar_sesion: Depends(verificar_origen) -> Depends(sesion_vigente)
    AssertionError: Rutas que mutan sin comprobar el origen (CA-18):  POST /api/v1/sesion/cierre
    POST /api/v1/sesion/cierre [ambos_ausentes]: respondió 204 y no el 403 ORIGEN_NO_VERIFICADO completo
    (las otras tres combinaciones dan 401 SESION_REVOCADA: la primera ya cerró la sesión)
M2  iniciar_sesion: se quita Depends(credenciales_con_origen_verificado)
    Rutas que mutan sin comprobar el origen (CA-18):  POST /api/v1/sesion
    POST /api/v1/sesion [las cuatro combinaciones]: respondió 200 y no el 403 ORIGEN_NO_VERIFICADO completo
```

En una primera pasada de M1 el caso caía en un assert auxiliar y no en el detector; el tester reordenó para que el detector corra primero y el mensaje nombre la ruta. Reutilizados sin duplicar: `test_tkt006_ca14_la_lista_cerrada_coincide_con_el_enrutador` (CA-R6) y `test_tkt006_car6_rutas_de_identidad_sincronas` (CA-R5). Límites conocidos, del lado seguro: una ruta protegida solo por `include_router(dependencies=[...])` se contaría como sin verificar (falla el test), y las rutas montadas con `Mount` sueltas no son inspeccionables (las cubre TC-47 de TKT-006).

**Cierre de la entrega A:**

```text
uv run pytest tests/test_tkt057_csrf.py tests/test_tkt006_enrutador.py -q   92 passed in 10.48s
uv run pytest -q (suite completa, dos corridas)                              1287 passed in 248.85s (0:04:08)
ruff check: All checks passed! · ruff format --check: 160 files already formatted · mypy: Success · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

### Fila 11 · `pydantic-settings` y `servidor/ajustes.py`

**Rojo** (`tester-backend`, `uv run pytest tests/test_tkt057_arranque.py -q`): los 23 casos nuevos fallan, todos con la misma razón esperada.

```text
E   ModuleNotFoundError: No module named 'servidor.ajustes'
23 failed in 0.18s
```

Cobertura: TC-50 (sin la contraseña de aplicación: `ConfiguracionInvalida` que nombra solo esa variable, con `from None` y subclase de `RuntimeError`), TC-51 (la vacía es igual que la ausente), TC-52 (los ajustes no tienen campo de migración ni de lectura; `repr`, `str` y `model_dump_json()` no contienen ninguna de las tres contraseñas), TC-53 (nueve orígenes inválidos rechazados con el mensaje sin el valor ni la contraseña, y dos válidos aceptados) y TC-54 (con un mapa explícito no se lee `os.environ`). El tester añadió casos de rechazo extra (`ftp://`, barra final, puerto de ocho dígitos, solo esquema, sin esquema y dos orígenes) y avisó de que `https://a.test:99999` pasaría con el regex del diseño, que no pide rechazar puertos fuera de rango.

**Verde** (`desarrollador-api`, `haiku`): `uv add "pydantic-settings>=2.16.1"` (la dependencia pasa de transitiva a directa; `uv.lock` cambia solo en dos líneas y la versión sigue siendo 2.16.1) y `servidor/ajustes.py` con `ConfiguracionInvalida`, `AjustesServidor`, `_AjustesDesdeMapa` y `cargar_ajustes`.

```text
uv run pytest tests/test_tkt057_arranque.py -q       23 passed in 0.06s
uv run pytest tests/test_tkt005_regresion.py -q      9 passed in 2.85s   (sin BOM ni CRLF)
uv sync --locked --python 3.14                       Audited 108 packages, EXIT=0
uv run pytest -q (suite completa)                    1310 passed in 248.57s (0:04:08)
ruff check: All checks passed! · ruff format --check: 162 files already formatted · mypy: Success (162 files) · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

**Desviación del diseño, aceptada y anotada en «Ajustes»:** en la rama `entorno is None`, `mypy` exige el campo obligatorio en `AjustesServidor()` y se añadió `# type: ignore[call-arg]` con un comentario. **Hallazgo menor, no cubierto por ninguna prueba:** esa rama lee el entorno con la búsqueda de `pydantic-settings`, que no distingue mayúsculas (`case_sensitive=False`), mientras que la rama del mapa sí las distingue; una variable en minúsculas del proceso entraría por la primera y no por la segunda. No es bloqueante; queda anotado para la revisión.

**Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

### Fila 12 · `crear_aplicacion` con los ajustes, `contrasena` en el motor y exportación de tipos

**Rojo** (`tester-backend`): tras el primer intento, `uv run pytest -q` dio `9 failed, 1313 passed`; los nueve eran los siete casos rojos de la fila y dos efectos colaterales que el propio tester corrigió (`mypy` por las llamadas con la firma nueva, que se resuelve en el verde, y siete archivos con CRLF que su `write_text` había dejado y normalizó a LF). Con los seis archivos de la fila: `7 failed, 182 passed`.

```text
procesos hijos (variable ausente / vacía):  código=0 --- stdout --- VARIABLE='' ARRANCO --- stderr ---     (la fábrica arranca sin validar)
espías (entorno={}):                         Failed: DID NOT RAISE ConfiguracionInvalida
motor:                                       assert [None] == ['secreto-aplicacion-tkt057-9f3a']
url_aplicacion / crear_motor_aplicacion:     TypeError: ... takes 0 positional arguments but 1 was given
fastapi dev sin la variable:                 assert <Response [200 OK]> is None     (el servidor arrancó y sirvió GET /openapi.json)
```

Nacen en verde, a propósito: **TC-56** (404, 200 del token y 401 sin cookie con solo la contraseña de aplicación y sin host, puerto ni nombre de base; es la reescritura de TC-75, y se pone en verde sin cambios porque el motor es perezoso; añade que el token del cuerpo es igual a la cookie), **TC-58** (`alembic upgrade head` sin la contraseña de migración falla nombrándola: `leer_variable` ya lo hace, y se documenta como regresión de la parte de `M6` que no cambia), **CA-15 esc. 2** (el servidor arranca sin las de migración y lectura), los dos casos de `url_aplicacion` sin argumento y los dos de `fastapi dev` reescritos (`test_tkt005_ca12_...` y `test_tkt006_car4_...`). Adaptaciones: `conftest.py` (`ENTORNO_DE_PRUEBA`), `test_servidor_arranque.py` (TC-75, los dos casos de `fastapi dev`, el de `aplicacion_con_secreto.py` y `aplicacion_de_la_fabrica()`), `test_contrato_error_http.py` (`:164`, `:1075`), `test_servidor_correlacion.py` (`:49`), `test_tkt006_enrutador.py` (`:98`), `test_tkt006_sesion_vigente.py` (su `ENTORNO_DE_PRUEBA` local) y `test_tkt007_consulta.py` (`:640`). **TC-57**: la mitad «sin ella no arranca» está en `test_tkt057_arranque.py` y la mitad «arranca con la variable» son los dos casos de `fastapi dev` reescritos, para no lanzar un tercer servidor.

**Verde** (`desarrollador-api`, `haiku`): `url_aplicacion` y `crear_motor_aplicacion` aceptan `contrasena`; `cargar_ajustes(entorno)` es la primera línea de `crear_aplicacion` y el proveedor perezoso del motor recibe la contraseña ya validada; `entorno` sigue alimentando `montar_identidad`; `frontend/scripts/tipos.ts` genera una contraseña efímera (`secrets.token_urlsafe(16)`) dentro de su guion Python y la pasa como `entorno`, con un comentario que explica que es desechable y por qué existe.

```text
uv run pytest (siete archivos de la fila) -q       198 passed in 26.75s
uv run pytest -q (suite completa)                  1322 passed in 250.41s (0:04:10)
ruff check: All checks passed! · ruff format --check: 162 files already formatted · mypy: Success (162 files) · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
frontend:  npm run tipos:generar -> "Tipos generados: src/api/generado/servidor.ts, src/api/generado/contrato-error.provisional.ts"
           npm run tipos:verificar -> "Tipos al día."  ·  npm run lint: sin salida de error  ·  npm run typecheck: tsc --noEmit sin errores
```

**Archivo versionado que cambia:** `frontend/src/api/generado/servidor.ts` cambia dos líneas (`@description` de `iniciar_sesion` y `cerrar_sesion`) porque salen de las docstrings de `rutas.py`, que las filas 8 y 9 reescribieron. El CI fallaría con el archivo anterior; el regenerado viaja en el mismo PR. `npm run e2e` no es parte de la fila: se corre en el cierre (fila 16). **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

### Fila 13 · Cabeceras de seguridad (`servidor/cabeceras.py`)

**Rojo** (`tester-api`, `uv run pytest tests/test_tkt057_cabeceras.py -q`): 28 fallos por la razón esperada y 1 caso en verde a propósito.

```text
TC-59/60/61 y /openapi.json (16 casos):  AssertionError: Strict-Transport-Security debe aparecer una vez en la respuesta <código> y aparece 0 ([])   (o lo mismo con Content-Security-Policy; el código HTTP esperado ya se cumplía, incluidos 500 y 429)
TC-62 (5 parámetros):  assert 'public, max-age=3600' == 'no-store' · 'default-src *' · 'max-age=0' == 'max-age=31536000' · 'sniff' == 'nosniff' · 'unsafe-url' == 'no-referrer'
módulo y ASGI (7 casos):  ModuleNotFoundError: No module named 'servidor.cabeceras'
estado de la aplicación (2 casos):  AttributeError: 'State' object has no attribute 'cabeceras_seguridad'
28 failed, 1 passed in 4.22s
```

Nace en verde, a propósito: **TC-63** (el `500` conserva `X-Correlacion-Id` y el cuerpo de TKT-005, sin traza ni nombre de la excepción); es la regresión que debe seguir en verde cuando el manejador del `500` añada las cabeceras. Cada cabecera se comprueba con `get_list`, es decir, exactamente una vez: un `500` con cabeceras duplicadas queda en rojo. El tester fijó una decisión que el diseño dejaba abierta: `cabeceras_para_ruta` suma `no-store` solo si la ruta empieza por `/api/` (`/api/` lo lleva; `/apiario`, `/` y `/openapi.json` no).

**Verde** (`desarrollador-api`, `haiku`): `cabeceras.py` con `cabeceras_de_seguridad`, `cabeceras_para_ruta` y `MiddlewareCabecerasSeguridad` (ASGI puro, quita las cabeceras homónimas sin distinguir mayúsculas y añade las suyas); la fábrica guarda `aplicacion.state.cabeceras_seguridad` y registra el middleware antes que `MiddlewareCorrelacion`, que queda el más externo; `manejar_error_no_controlado` añade las cabeceras él mismo. Context7 confirma que el último `add_middleware` es el más externo.

```text
uv run pytest (cabeceras, correlacion, arranque, contrato_error_http) -q   123 passed in 12.60s
uv run pytest -q (suite completa)                                          1351 passed in 251.81s (0:04:11)
ruff check: All checks passed! · ruff format --check: 164 files already formatted · mypy: Success (164 files) · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
```

**Un fallo corregido en el verde:** la primera ejecución dio `1 failed` (`..._el_middleware_quita_sin_distinguir_mayusculas_y_conserva_las_ajenas`): `cabeceras_para_ruta` añadía `no-store` aunque la lista ya trajera un `Cache-Control`, y salía duplicado. Ahora lo reemplaza. **Refactor:** sin refactor más que el formato. **Tests devueltos al tester:** ninguno. **Puntos abiertos:** `/docs` deja de pintarse con la política (la `D-2` aprobada la aplica también ahí; el ticket de deuda de `/docs` lo resuelve), y una lista con `Cache-Control` para una ruta fuera de `/api/` la emitiría el middleware tal cual, cosa que la fábrica nunca hace.

### Fila 14 · `.env.example`, trabajo `humo`, `compose.yaml` y pruebas de `tools/`

**Rojo** (`tester-backend`): seis casos nuevos y dos reescritos de TKT-003 fallan por la razón esperada; en `tools/` cae un solo test (`test_tc08`), por la misma causa.

```text
FAILED tests/test_tkt057_entorno.py::test_tkt057_ca17_esc01_env_example_lista_las_tres_contrasenas_sin_valor      (CIMENTA_DB_CONTRASENA_MIGRACION lleva valor; 4 problemas)
FAILED tests/test_tkt057_entorno.py::test_tkt057_ca17_esc01_env_example_documenta_la_seccion_de_tkt057            (no documenta CIMENTA_ALMACEN_ORIGEN)
FAILED tests/test_tkt057_entorno.py::test_tkt057_ca17_esc02_humo_no_copia_el_ejemplo_tal_cual                      (assert ['cp .env.example .env'] == [])
FAILED tests/test_tkt057_entorno.py::test_tkt057_ca17_esc02_humo_genera_las_tres_contrasenas_antes_de_levantar_la_base
FAILED tests/test_tkt057_entorno.py::test_tkt057_ca17_esc02_humo_no_fija_ningun_valor_literal_para_las_contrasenas
FAILED tests/test_tkt057_entorno.py::test_tkt057_ca17_regresion_las_tres_contrasenas_de_env_example_existen_y_estan_vacias   ('solo-desarrollo-aplicacion' != '')
FAILED tests/test_identidad_credenciales.py::test_tkt003_ca10_esc03_ningun_secreto_en_el_repositorio
FAILED tests/test_identidad_credenciales.py::test_tkt003_ca11_esc01_env_example_define_lo_que_se_usa
8 failed, 6 passed in 2.22s
tools:  Ran 474 tests · FAILED (failures=1)  test_tc08_humo_construye_el_entorno_corre_el_recorrido_y_sube_el_informe_si_falla
        "'humo': falta «openssl rand -hex 24» en un run: del trabajo ... un paso copia .env.example tal cual"
```

Los seis que pasan son los cuatro de TKT-003 que no tocan `.env.example` (TC-60 a TC-63, con testcontainers) y los dos casos de control que demuestran, sobre texto sintético, que el comprobador acepta la forma correcta y cae ante cada mutante (`cp` en lugar de generar, generar después de `compose`, valor literal, `env:` del trabajo; valor, clave ausente o comentada, `solo-desarrollo-` en un comentario, límite activo y sin `ALMACEN_ORIGEN`). El tester reescribió TC-64 y TC-65 de TKT-003 (las tres contraseñas deben ser cadena vacía; ningún archivo de `compose.yaml`, `migraciones/` o `herramientas/` contiene `solo-desarrollo-`; `_leer_env_example` tolera un comentario al final de línea) y actualizó `tools/tests/test_definicion_ci.py` (`comprobar_tc08` exige `openssl rand -hex 24` en lugar de `cp .env.example .env`; `HUMO_SINTETICO` y siete mutantes sustituidos o añadidos). Un caso fuera de las filas TC-64..66: la sección de `TKT-057` del ejemplo (`CIMENTA_ALMACEN_ORIGEN` documentada y los tres `CIMENTA_LIMITE_*` comentados). El mensaje de `compose.yaml` no tiene prueba propia: el plan no la pedía; se verificó con `docker compose config`.

**Verde** (`ingeniero-devsecops`, `sonnet`): `.env.example` con las tres contraseñas activas y sin valor (con un comentario de qué usa cada una), sin ninguna cadena `solo-desarrollo-` y con la sección de TKT-057 (`# CIMENTA_ALMACEN_ORIGEN=` comentada, por ser opcional hasta TKT-059, y los tres límites comentados con sus valores por omisión); el paso de `humo` «Preparar el entorno con contraseñas de prueba generadas» con `grep -v '^CIMENTA_DB_CONTRASENA_' .env.example > .env` y el bucle de `openssl rand -hex 24`; mensajes de `compose.yaml` que dicen «define CIMENTA_DB_CONTRASENA_MIGRACION en .env».

```text
uv run pytest tests/test_tkt057_entorno.py tests/test_identidad_credenciales.py -q   14 passed in 2.23s
python -m unittest discover -s tools/tests                                           Ran 474 tests in 13.630s · OK (incluye test_tc08)
uvx zizmor@1.31.1 --offline .github/workflows                                        No findings to report. Good job! (6 suppressed)
uv run pytest -q (suite completa)                                                    1359 passed in 252.61s
prueba local del paso en un directorio temporal:  .env con 3 líneas CIMENTA_DB_CONTRASENA_[A-Z]+=[0-9a-f]{48}; grep -c solo- = 0;
   docker compose --env-file .env config -> CONFIG_OK (sin levantar nada); sin la de migración falla con
   "required variable CIMENTA_DB_CONTRASENA_MIGRACION is missing a value: define CIMENTA_DB_CONTRASENA_MIGRACION en .env"
```

**Hallazgos del verde:** el `.env` generado llega al backend de `humo` sin tocar `playwright.config.ts` (su `webServer` usa `uv run --locked --env-file ../.env fastapi run`, igual que Alembic y `contrasenas_roles`), y el `grep -v` conserva `CIMENTA_PRUEBA_CORREO` y `CIMENTA_PRUEBA_CONTRASENA` (esto último deducido del patrón, sin ejecutar: lo comprueba `npm run e2e` en el cierre). Solo `ci.yml` copiaba `.env.example` en un workflow. Quedan obsoletos `docs/arranque-local.md`, `README.md`, `conv-docker/SKILL.md`, `docs/06-stack-tecnologico.md` y `docs/convenciones.md`, que son la fila 15, y el comentario de `.env.example` sobre «valores de desarrollo evidentes» sigue valiendo para host, puerto y nombre. **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

### Fila 15 · Documentación `M8` y ADR

**Rojo** (`tester-api`): siete fallos por la razón esperada y dos controles en verde en TC-67; en `tools/`, un solo rojo.

```text
uv run pytest tests/test_tkt057_csrf.py -q -k borrador     7 failed, 2 passed, 63 deselected in 0.71s
  cerrar_sesion x-tickets sin TKT-057 · el 200 de iniciar_sesion y el 204 de cerrar_sesion apuntan a `SetCookieSesion` · el componente SetCookieSesionYCsrf no existe ·
  `SetCookieSesion` sigue referenciado · la descripción de securitySchemes.csrf no habla de rotación · DemasiadosIntentos dice solo «el bloqueo es temporal»
python -m unittest discover -s tools/tests -v              Ran 474 tests · FAILED (failures=1)
  test_tkt062_ca12_esc01_...: faltan 6 frase(s): CLAUDE.md, README.md y llms.txt no dicen «29», y siguen diciendo «27» o «28»
```

Nacen en verde dos controles: `iniciar_sesion` ya cita `TKT-057` y `SetCookieCsrf` (que TKT-057 no toca) sigue declarado y referenciado. El tester subió los conteos de ADR de 28 a 29 en `tools/tests/test_definicion_revision.py` (`DECISIONES_NUEVAS`, la muestra sintética y tres mutantes nuevos con 28); las demás apariciones de «28» son `ADR-028`, que sigue vigente.

**Verde** (`desarrollador-api`, `haiku`): `openapi.yaml` con `components.headers.SetCookieSesionYCsrf` (usado por el `200` de `iniciar_sesion` y el `204` de `cerrar_sesion`; se eliminó el huérfano `SetCookieSesion`), `x-tickets` de `cerrar_sesion` con `TKT-057`, las descripciones del `422`/`403`/`429` y de `securitySchemes.csrf`; `07-especificacion-api.md` (§2.5, el límite de intentos con la fórmula resumida y, por coherencia con el borrador, la fila de `POST /sesion/cierre` de §4.1); `06-stack-tecnologico.md` (§6.2 sin `slowapi`, §6.3 sin semilla CSRF, §6.4 sin `solo-desarrollo-*`, §6.6 «cinco fallos y el sexto bloqueado» y la tabla); `arranque-local.md`; `03-modelo-datos.md` (§10, diagrama ER e invariante 20 sin crear invariante: siguen siendo 38); `05-tickets-trabajo.md`; `08-wireframes.md`; `convenciones.md`; `README.md`; `CLAUDE.md` y `llms.txt` (29 decisiones); `.claude/skills/conv-docker`, `conv-backend-fastapi` y `.claude/agents/desarrollador-api.md`; y el ADR `docs/adr/20261030-limite-de-intentos-sobre-intento-acceso.md` con su fila en el índice. El orquestador cambió el estado del ADR de `Propuesto` a `Aceptado`: la persona dueña aprobó `D-1` (la migración) y el resto del diseño el 2026-10-30.

```text
uv run pytest tests/test_tkt057_csrf.py -q -k borrador        9 passed, 63 deselected in 0.50s
uv run pytest tests/test_tkt057_csrf.py -q                    72 passed in 16.83s     (TC-49, el OpenAPI en vivo, sigue en verde)
python -m unittest discover -s tools/tests -v                 Ran 474 tests in 13.558s · OK
python tools/extraer_mermaid.py                               exit 0 · 30 diagramas encontrados (la sintaxis real se valida en un navegador: no validada)
markdownlint-cli2@0.24.0 sobre los 14 Markdown tocados       Summary: 0 issues in 0 files
Vale 3.25.1.0 sobre los archivos tocados                      exit 0, sin alertas
python tools/verificar_docs.py                                adrs 29 · invariantes 38 · PROBLEMAS (2): enlaces de impl.md y de _index.md hacia delta.md (aún no existe)
```

**Lo que no se pudo comprobar:** `lychee` no está instalado en esta máquina (no se añadieron enlaces externos; los relativos los comprueba `verificar_docs`), y la sintaxis del diagrama ER cambiado (`INTENTO_ACCESO`) solo se valida con un navegador. **Los dos enlaces rotos a `delta.md`** son los artefactos propios del ticket y desaparecen cuando `/sdd-completar` escribe `delta.md`, antes del PR. **Asunciones del texto:** `/docs` queda sin pintarse bajo la política de contenido (`D-2`, aprobada). **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

### Fila 16 · Mutación de `CA-19`, suite completa y cierre

`tester-backend` aplicó 16 mutantes (los 14 de la tabla del diseño de entonces, más la división sin techo y el `GRANT` sobre `sesion` en la migración; en `/sdd-revisar` se añadió el mutante 17 y la tabla del diseño tiene hoy 15 filas). Antes de cada uno guardó una copia con su `sha256` en el directorio temporal, ejecutó 427 pruebas (los ocho archivos `tkt057`, los de identidad y los de `tkt006` de cierre, inicio y enrutador, el contrato de error y el servidor), y al revertir comprobó con `cmp` y `sha256` que el archivo quedaba idéntico. La comparación final de `git status` y de los hashes de `git diff` y de cada archivo sin seguimiento, antes y después, fue idéntica: no queda ningún cambio de producción de las mutaciones. Todos los archivos de producción de `backend/` tienen finales de línea CRLF y el guion de mutación los conservó.

| Id | Mutante | Pruebas que cayeron |
|---|---|---|
| M01 | `evaluar_limite` siempre con `reintentar_en_s=0` | 27: TC-04, TC-06, TC-07, TC-08 y los de aplicación y API de `CA-1`, `CA-2`, `CA-3`, `CA-4`, `CA-5`, `CA-6`, `CA-7`, `CA-8`, la concurrencia, `CA-R2`, los `429` y `cabeceras::ca13[429_bloqueo]` |
| M02 | `f - ventana < g` por `<=` | TC-03 (`assert 0 is None`) |
| M03 | `d + ventana > 0` por `>= 0` | TC-04 |
| M04 | `evaluar_limite` sin el filtro del último éxito | TC-05, TC-08b y dos de `CA-5` en aplicación |
| M05 | división entera sin techo | TC-04, dos de TC-08, el sexto intento y el `429` completo |
| M06 | `fallos_de_correo` sin `credenciales_verificadas IS true` | el de repositorio, `ca03` ×3 (`assert 600 == 300`), `ca04` ×2 |
| M07 | `fallos_de_origen` sin el mismo filtro | el de repositorio, `ca03`, `ca04`, `ca07` (caduca solo) y `ca06` (los rechazos no cuentan) |
| M08 | `abrir_sesion` sin `bloquear_correo` | solo TC-33 (`[SesionInvalida, SesionInvalida]`) |
| M09 | `verificar_origen` devuelve el usuario sin comparar | 11: `ca09` ×5, `ca11_esc2` ×4, `ca12_esc1` y `ca18` |
| M10 | `par_csrf_valido` verdadero con dos `None` | 8: `m4` ausentes, `ca09`, `ca11_esc2` ×2, `ca11_esc3` ×2, `ca18` y `cabeceras::ca13[403_sin_token]` |
| M11 | `iniciar_sesion` sin rotar | 4: `ca12_esc1` ×3 y `ca12_esc2` (`hay 0`) |
| M12 | el token se evalúa antes que la sesión | 24: `ca11_esc1` ×2 (esperaban `401` y llegó `403`), `ca11_esc2` ×4, `tkt006_cierre` ×5, `tkt006_enrutador::ca14_*` ×13 |
| M13 | `db_contrasena_aplicacion` con valor por omisión | 9: `ca15_esc1` ×5, `ca16` ×2, espías, `fastapi dev` (`DID NOT RAISE ConfiguracionInvalida`) |
| M14 | `env_ignore_empty=False` | 2: `ca15_sin_mapa...` y `ca16_proceso_con_la_contrasena_vacia...` (`código=0`) |
| M15 | `manejar_error_no_controlado` sin las cabeceras | `cabeceras::ca13[500_...]` (`Strict-Transport-Security ... aparece 0`) |
| M16 | migración con `GRANT SELECT ON sesion TO cimenta_lectura` | TC-INV-2 y `test_tkt003_ca05_esc03_privilegios_exactos_en_identidad` |

Todos cayeron donde el diseño lo promete; no hay hallazgo de prueba faltante. **M12** se aplicó como equivalente: FastAPI evalúa las dependencias antes del cuerpo, así que reordenar parámetros no cambia nada; el tester renombró la función, quitó `Depends(sesion_vigente)` y escribió una que comprueba el par primero. **M16** se aplicó sobre el archivo real, con respaldo, porque `alembic` no lee una copia. Los mutantes que mata un único test son M02, M03, M08 y M15: son los más frágiles si alguien lo toca.

**Cierre** (desde `backend/`, `frontend/` y la raíz):

```text
uv run pytest -q                       1 failed, 1367 passed in 252.73s (0:04:12)
    el fallo: tests/test_tkt005_regresion.py::test_tkt005_car2_calidad_estatica_sin_hallazgos[ruff_format]
    causa: backend/tests/test_tkt057_csrf.py sin formatear (tres sitios: re.compile ~1624, una firma ~1679, un assert largo ~1704)
```

**Corrección del orquestador, sin cambiar comportamiento:** el tester no aplicó el formato porque se le pidió no tocar pruebas. El orquestador ejecutó `uv run ruff format tests/test_tkt057_csrf.py` (solo formato; ningún desarrollador tocó la prueba) y repitió la comprobación:

```text
ruff format tests/test_tkt057_csrf.py   1 file reformatted
ruff format --check .                   165 files already formatted
ruff check .                            All checks passed!
uv run pytest tests/test_tkt005_regresion.py tests/test_tkt057_csrf.py -q   81 passed in 12.02s
mypy .: Success (165 files) · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
python -m unittest discover -s tools/tests   Ran 474 tests in 13.909s · OK
frontend:  npm test -> Test Files 17 passed (17) · Tests 214 passed (214) · npm run lint: sin hallazgos · npm run typecheck: sin errores · npm run tipos:verificar -> "Tipos al día."
           npm run e2e -> 3 passed (7.3s)   (entrar y salir con la rotación del token, credenciales incorrectas y el teléfono: CA-R8)
```

La suite completa de `backend` se vuelve a ejecutar tras las correcciones de la auditoría de cierre. El `e2e` usó el `.env` local ya existente (ignorado por git, `.gitignore:25`, con las contraseñas antiguas `solo-desarrollo-*` que coinciden con el volumen local `cimenta_pg_datos`), levantó la base con `docker compose up -d --wait db`, migró el volumen a `0005 (head)` y fijó las contraseñas de los roles; al terminar se hizo `docker compose stop db`. No se probó con un `.env` recién generado como en CI. `git status --short` quedó igual antes y después, y no hay secretos en el diff: los valores de contraseña del `.env` local solo aparecen en las líneas eliminadas de `.env.example`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | — | `haiku` | — |
| Fila 1 | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 2 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador del diseño: permisos de un rol |
| Fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde | `desarrollador-dominio` | `sonnet` | `sonnet` | Disparador del diseño: regla de límite |
| Fila 4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| Fila 5 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 5 · verde | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador del diseño: bloqueo y concurrencia |
| Fila 6 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 6 · verde | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador del diseño: regla de límite y concurrencia (TC-33) |
| Fila 7 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| Fila 7 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 8 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| Fila 8 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 9 · rojo | `tester-api` | `sonnet` | `sonnet` | — (reanudado tras el límite de la API) |
| Fila 9 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 10 | `tester-api` | `sonnet` | `sonnet` | Disparador del diseño: oráculo de la prueba estructural |
| Fila 11 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 11 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 12 · rojo | `tester-backend` | `haiku` por omisión | `sonnet` | Los desarrolladores van en `haiku`; el tester no baja de lo que verifica ni de `sonnet` |
| Fila 12 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 13 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| Fila 13 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 14 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 14 · verde | `ingeniero-devsecops` | `sonnet` | `sonnet` | Disparador del diseño: valor por omisión del agente (compuerta del pipeline) |
| Fila 15 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| Fila 15 · verde | `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 16 | `tester-backend` | `sonnet` | `sonnet` | Disparador del diseño: valor por omisión del agente |
| Auditoría de arquitectura y de SQL | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |
| Ciclo de corrección 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Ciclo de corrección 1 · verde | `corrector-revision` | `haiku` | `haiku` | Todos los hallazgos eran Menores y ninguno tocaba un disparador del paso 3 |
| Reauditoría de arquitectura y de SQL | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |
| Fila 3 · ajuste | `desarrollador-dominio` | `haiku` | `haiku` | Mecánico, verificable por comando |

No hubo despachos en `opus` en la ejecución. Ningún paso en `haiku` necesitó subir a `sonnet`.

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/identidad/dominio/limite_intentos.py` | nuevo | dominio |
| `backend/cimenta/identidad/aplicacion/sesiones.py`, `configuracion.py` | modificado | aplicación |
| `backend/cimenta/identidad/api/dependencias.py`, `rutas.py`, `esquemas.py`, `interfaz.py` | modificado | api |
| `backend/cimenta/identidad/infraestructura/modelos.py`, `repositorio.py` | modificado | infraestructura |
| `backend/migraciones/versions/v0005_identidad_intento_verificado.py` | nuevo | infraestructura (esquema) |
| `backend/servidor/ajustes.py`, `cabeceras.py` | nuevo | servidor |
| `backend/servidor/fabrica.py`, `manejadores.py`, `backend/herramientas/conexion.py` | modificado | servidor |
| `backend/pyproject.toml`, `backend/uv.lock` | modificado (`pydantic-settings` pasa a dependencia directa) | dependencias |
| `.env.example`, `.github/workflows/ci.yml`, `compose.yaml` | modificado | entorno y pipeline |
| `frontend/scripts/tipos.ts`, `frontend/src/api/generado/servidor.ts` | modificado | frontend (solo el guion de exportación y el archivo regenerado) |
| `backend/tests/test_tkt057_*.py` (nueve archivos) | nuevo | pruebas |
| `backend/tests/` (`conftest.py`, `test_contrato_error_http.py`, `test_identidad_credenciales.py`, `test_identidad_esquema.py`, `test_identidad_permisos_tablas.py`, `test_servidor_arranque.py`, `test_servidor_correlacion.py`, `test_tkt006_*.py`, `test_tkt007_consulta.py`) y `tools/tests/test_definicion_ci.py`, `test_definicion_revision.py` | modificado | pruebas |
| `docs/api/openapi.yaml`, `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `docs/07-especificacion-api.md`, `docs/08-wireframes.md`, `docs/arranque-local.md`, `docs/convenciones.md`, `docs/adr/README.md`, `README.md`, `CLAUDE.md`, `llms.txt`, `.claude/agents/desarrollador-api.md`, `.claude/skills/conv-backend-fastapi/SKILL.md`, `.claude/skills/conv-docker/SKILL.md` | modificado | documentación |
| `docs/adr/20261030-limite-de-intentos-sobre-intento-acceso.md` | nuevo | documentación |

## Pruebas

Nueve archivos nuevos: `test_tkt057_dominio.py` (TC-01 a TC-08b), `test_tkt057_migracion.py` (TC-10 a TC-13, TC-INV-1, TC-INV-2), `test_tkt057_configuracion.py` (TC-14 a TC-16), `test_tkt057_limite_intentos.py` (TC-17 a TC-37 y los dos del ciclo de corrección más la prueba de plan), `test_tkt057_csrf.py` (TC-38 a TC-49, TC-67), `test_tkt057_arranque.py` (TC-50 a TC-58), `test_tkt057_cabeceras.py` (TC-59 a TC-63), `test_tkt057_entorno.py` (TC-64 a TC-66) y `test_tkt057_origen.py` (`origen_de`, `CA-6` y `CA-7`, añadido en `/sdd-revisar`). Cada defensa tiene su prueba de rechazo con el contrato completo, hay concurrencia real (TC-22, TC-33) y 16 mutantes. Todos nacieron en rojo por la razón esperada salvo los casos de regresión listados fila por fila (TC-23, TC-28, TC-29, TC-34, TC-35, TC-39, TC-40, TC-44, TC-56, TC-58, TC-63, TC-INV-2 y las comprobaciones de control).

## Ciclo de corrección 1

Las auditorías de cierre dieron `REQUIERE CAMBIOS` con hallazgos Menores. El tester escribió antes el rojo de los dos que lo admitían (6 fallos) y `corrector-revision` aplicó los arreglos.

```text
uv run pytest tests/test_tkt057_migracion.py tests/test_tkt057_limite_intentos.py -q   (rojo)   6 failed, 48 passed in 19.83s
   TC-13: el catálogo tiene los dos índices completos y no los tres parciales
   "El reloj se leyó antes de tomar el candado del correo: ['reloj', 'bloquear_correo']"
   carrera sin hilos: el 6.º intento no ve el 5.º fallo, verifica la contraseña correcta y abre sesión (llegó UsuarioAutenticado)
   plan: se esperaba el índice parcial ...; el plan usó ['ix_intento_acceso_email_ocurrido_en'] (Bitmap Heap Scan que filtra los rechazos) ×3
(verde)   54 passed in 20.15s  ·  uv run pytest -q: 1373 passed in 251.07s (0:04:11)
ruff check: All checks passed! · ruff format --check: 165 files already formatted · mypy: Success (165 files) · lint-imports: 15 kept, 0 broken · verificar_float: hallazgos: 0
python -m unittest discover -s tools/tests: Ran 474 tests · OK
```

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` a `CA-5` (límite por cuenta) | `[M]` | Cumplido | TC-23 a TC-28, TC-33, TC-36, TC-37 y las pruebas de dominio TC-01 a TC-08b |
| `CA-6`, `CA-7` (límite por origen) | `[M]` | Cumplido | TC-29, TC-30, TC-32 |
| `CA-8` (cada intento asentado) | `[M]` | Cumplido | TC-31, TC-17, TC-INV-1 y las de migración |
| `CA-9`, `CA-10`, `CA-11` (CSRF) | `[M]` | Cumplido | TC-38 a TC-44, TC-47, TC-49 |
| `CA-12` (rotación) | `[M]` | Cumplido | TC-45, TC-46 |
| `CA-13`, `CA-14` (cabeceras y política de contenido) | `[M]` | Cumplido | TC-59 a TC-63 |
| `CA-15`, `CA-16`, `CA-17` (configuración y secretos) | `[M]` | Cumplido | TC-50 a TC-58, TC-64 a TC-66 |
| `CA-18` (el enrutador) | `[S]` | Cumplido | TC-48 y sus oráculos |
| `CA-19` (el pipeline falla ante la violación) | `[M]` | Cumplido | las 16 mutaciones de la fila 16 y el mutante 17 de `/sdd-revisar` |
| `CA-R1` a `CA-R8` (regresión) | `[M]` | Cumplido | TC-INV-1, TC-INV-2, TC-34, el recorrido del enrutador, TC-36, TC-56 y `npm run e2e` (3 de 3) |
| `M8` (documentación) | `[M]` | Cumplido | fila 15; `verificar_docs`: solo los enlaces a `delta.md` |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | F001 a F003 Menores resueltos; F004 a F007 Observaciones; F008 de redacción de `design.md`, corregida por el orquestador | 1 corrección y 1 reauditoría |
| `auditor-sql` | `APROBADO` | F001 Menor resuelto; F002 a F004 Observaciones | 1 corrección y 1 reauditoría |
| `auditor-codigo` | `APROBADO` | `/sdd-revisar`: F001 a F005 (Menores) y 4 observaciones nuevas; F002 a F004 resueltos en el ciclo 1, F001 y F005 en el ciclo 2 | 2 correcciones y 2 reauditorías |
| `auditor-seguridad` | `APROBADO` | `/sdd-revisar`: F001 a F003 Medias (F003 resuelto; F001 y F002 aceptados por la persona dueña) y F004 a F007 Bajas (F005 resuelto; F004, F006 y F007 observaciones) | 1 corrección y 1 reauditoría |
| `auditor-docs` | `REQUIERE CAMBIOS` (solo `N001`) | `/sdd-revisar`: F001 a F005 Menores resueltos; N002 y N003 corregidos por el orquestador; `N001` (Mayor por regla): `verificar_docs` en rojo por los enlaces a `delta.md`, que escribe `/sdd-completar` | 1 corrección y 1 reauditoría |

`/sdd-ejecutar` solo exige arquitectura y SQL en el cierre de la fase; `auditor-seguridad` (hay endpoint, sesión, CSRF y cabeceras), `auditor-codigo` y `auditor-docs` corresponden a `/sdd-revisar`.

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `sesiones.py:79,85` | El reloj se leía antes del candado | Resuelto (el reloj se lee tras `bloquear_correo`; dos pruebas nuevas) |
| F002 | arquitectura | Menor | `repositorio.py:154-161` | `ultimo_exito_de_correo` sin cota inferior | Resuelto por otra vía (índices parciales; prueba de plan) |
| F003 | arquitectura | Menor | `esquemas.py:22` | Docstring obsoleta (correo «tal como se escribió») | Resuelto |
| F004 a F007 | arquitectura | Observación | `ajustes.py:80`; tiempo residual; contraseña en `partial`; proceso | `type: ignore` y mayúsculas, señal de tiempo residual, Sentry futuro, estado del hub | Persisten (no bloquean) |
| F008 | arquitectura | Observación | `design.md:332,495,501` | «dos índices» en vez de «tres» | Resuelto por el orquestador |
| F001 | sql | Menor | `v0005:33-34` | Índices completos que recorren los rechazos por bloqueo (33 ms con 300 000 filas) | Resuelto (tres parciales: 0,02 a 0,04 ms) |
| F002 | sql | Observación | `v0005:29-34` | Bloqueo de tabla de unos 6,7 s con 3 M de filas | Persiste (sin acción obligatoria; ticket futuro si la tabla crece) |
| F003 | sql | Observación | `docs/03-modelo-datos.md` | Faltaba matizar las filas anteriores a TKT-057 | Resuelto |
| F004 | sql | Observación | `v0005` | Permisos sin cambios | Resuelto (correcto) |

## Revisión (`/sdd-revisar`, 2026-10-31)

El orquestador ejecutó la suite de verdad y despachó cuatro auditorías independientes en paralelo (`auditor-arquitectura`, `auditor-codigo`, `auditor-seguridad` y `auditor-docs`). `auditor-sql` no se repitió, porque aprobó este mismo código en el cierre de `/sdd-ejecutar` y la migración no ha cambiado desde entonces.

**Primera pasada: `REQUIERE CAMBIOS` en las cuatro.**

- Arquitectura (F001, Menor bloqueante): ninguna prueba fijaba la mirada hacia atrás de `2 × ventana`. Con `desde = ahora - ventana` el mutante sobrevivía a toda la suite y permitía abrir sesión con el bloqueo vigente tras fallos repartidos en 12 minutos.
- Código (F001 a F004, Menores): el caso borde `origen_ip=None`, el literal `RUTA_SESION` y `"POST"` en `aplicacion/`, el `SELECT` duplicado de `fallos_de_correo` y `fallos_de_origen`, y `abrir_sesion` demasiado larga.
- Seguridad (F001 a F003, Medias): cookies sin prefijo `__Host-`, filas de `intento_acceso` sin tope y origen sin agrupar IPv6 por /64 ni tratar la ausencia de cliente.
- Documentación (F001 a F005, Menores): redacciones obsoletas.

**Decisiones de la persona dueña (2026-10-31).**

- `F001` de seguridad: riesgo aceptado y ticket futuro ligado a TKT-058.
- `F002`: mantener las filas y exigir la retención de `intento_acceso` como condición de salida a producción.
- `F003`: corregirlo en este ticket (IPv6 por /64, `::ffff:` desenvuelta y cubeta fija `desconocido` sin cliente).

**Ciclo 1.** El tester escribió antes 17 pruebas en rojo (`origen_de` con 10 casos, tres rechazos de `http://` ajeno a `localhost` en el origen del almacén, tres casos HTTP del /64 y de la cubeta fija, y el de `metodo` y `ruta` de `registrar_rechazo_de_origen`) y la del mutante 17, que nace en verde a propósito:

```text
uv run pytest tests/test_tkt057_origen.py tests/test_tkt057_arranque.py tests/test_tkt057_limite_intentos.py tests/test_tkt057_csrf.py -q   17 failed, 160 passed in 43.02s
   origen_de:  ImportError: cannot import name 'origen_de' from 'cimenta.identidad.api.dependencias'  (10 casos)
   TC-53:      DID NOT RAISE ConfiguracionInvalida  (http://almacen.cimenta.test · http://203.0.113.9:9000 · http://localhost.evil.test)
   HTTP:       el intento 21 desde el mismo /64 responde 200 y no 429 · un /64 bloqueado no da 429 · sin cliente el límite se omite
   registrar_rechazo_de_origen:  TypeError: ... unexpected keyword argument 'metodo'
mutante 17 (desde = ahora - ventana, aplicado a una copia de sesiones.py y revertido con cmp y sha256 11cf2b79c4c41ebb...):  1 failed, 49 passed
   cae test_tkt057_ca03_aplicacion_el_bloqueo_con_fallos_repartidos_sigue_vigente_a_los_veinte_minutos: devuelve UsuarioAutenticado donde se esperaba el 429
```

`corrector-revision` (`sonnet`, por tocar el refactor de `abrir_sesion`) aplicó los arreglos. Resultado: `1395 passed in 253.12s`, `ruff`, `mypy` y `lint-imports` limpios y `tools` con 474 en verde.

**Ciclo 2.** La reauditoría de código dejó F001 reformulado (`origen_ip: str | None` con una guarda que ya no hacía falta) y apareció F005 (el nombre `_registrar_fallo_y_bloquear` no decía lo que hacía). El tester adaptó las pruebas: `test_tkt006_inicio_sesion.py` usa `ORIGEN_IP`, los ayudantes tipan `str` y hay seis casos de borde de `origen_de`, que nacen en verde a propósito porque el cambio es de tipo y de nombre. El corrector tipó `origen_ip: str`, quitó la guarda y renombró la ayuda a `_bloquear_si_el_fallo_dispara_el_limite`. Resultado: `1403 passed in 253.68s`.

**Reauditorías, con el informe previo literal.**

- `auditor-arquitectura`: `APROBADO` (F001 resuelto; O1 resuelto en el código).
- `auditor-seguridad`: `APROBADO` (F003 y F005 resueltos; F001 y F002 persisten como riesgos aceptados y registrados).
- `auditor-codigo`: `APROBADO` (F001 a F005 resueltos).
- `auditor-docs`: cinco Menores resueltos y un único bloqueo, `N001`.

**`N001` (Mayor por regla, pendiente de decisión de la persona dueña).** `python tools/verificar_docs.py` falla únicamente por los enlaces de `impl.md` y de `_index.md` hacia `delta.md`, que escribe `/sdd-completar` antes de abrir el PR (TKT-006 pasó por lo mismo). No hay otro problema en los 181 documentos.

**Hallazgos de redacción resueltos por el orquestador con la salida real** (criterio de parada de la metodología): `N002` (el mutante se numera M17 en `design.md`), `N003` (la fila 16 del diseño ya no dice «las tres mutaciones»), `N004` (las cifras de este archivo: 17 mutantes y 1403 pruebas de `backend`) y el estado de `PA-T4` y `PA-T11` en la spec.

### Verificación real al cierre (árbol final, sin commit)

```text
uv run pytest -q                       1403 passed in 253.56s (0:04:13)
uv run ruff check .                    All checks passed!
uv run ruff format --check .           166 files already formatted
uv run mypy .                          Success: no issues found in 166 source files
uv run lint-imports                    Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float   archivos revisados: 19; hallazgos: 0
python -m unittest discover -s tools/tests      Ran 474 tests in 13.482s · OK
python tools/verificar_docs.py         PROBLEMAS (2): impl.md -> delta.md · _index.md -> delta.md   (los enlaces de N001)
frontend:  npm test -> Tests 214 passed (214) · npm run lint: sin hallazgos · npm run typecheck: sin errores · npm run tipos:verificar -> "Tipos al día."
           npm run e2e -> 3 passed (5.8s)
```

El `e2e` falló en una primera pasada en la preparación global porque la base local estaba parada (la detuve tras el `e2e` anterior). Se levantó con `docker compose up -d --wait db`, se migró a `head`, se repitió el `e2e` y se paró la base al terminar.

**Observaciones que quedan registradas (no bloquean).**

- Arquitectura: O2 a O6, y O7: `origen_ip` guarda la cubeta (`2001:db8::/64` o `desconocido`) y no la dirección real, cosa que conviene registrar en el ADR.
- Código: O-ABRIR, O-ANY, O-DISPARO, O-FRASE, O-LITERAL, O-FILA, O-PUERTO, O-EOL, O-ORIGEN-1 a 3 y O-C2-1 a O-C2-4 (sobre todo la mutación manual de `origen_de`, que sigue pendiente).
- Seguridad: F004 (HSTS sin `includeSubDomains`), F006 (`::add-mask::`), F007 (el secreto en un `partial`) y tres Bajas dependientes del despliegue (cubeta `desconocido` compartida, quien posee un /48 o un /32, hosts no parseables con proxy), todas ligadas a TKT-058.
- Documentación: O001 a O006.

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí**.

| Archivo | Observación | Prioridad |
|---|---|---|
| `CredencialesInicio.contrasena` (`esquemas.py`) | Sin tope de longitud: Argon2 sobre una cadena enorme es un vector de carga (ya en «Tickets futuros») | Media |
| `intento_acceso` | Crece sin purga, también con rechazos anónimos que un atacante provoca sin coste (invariante 20) | Media |
| `abrir_sesion`, `request.client.host` | Detrás de un proxy todos los clientes comparten origen (`PA-T5`, TKT-058) | Alta con el despliegue |
| `/docs` | La política de contenido deja de pintar Swagger (`D-2`) | Baja |
| `v0005` | Para una tabla con millones de filas: `SET LOCAL lock_timeout` y `CREATE INDEX CONCURRENTLY` (F002 de SQL); el rol de migración no tiene `lock_timeout` | Baja |
| `conexion.py`, `fabrica.py` | La contraseña viaja en un `partial` y en un parámetro `contrasena` (no está entre los nombres que Sentry oculta por omisión) cuando se conecte Sentry (F006) | Baja |
| `test_tkt057_migracion.py:8` | Una línea de docstring de más de 100 caracteres | Baja |

## Documentación actualizada

Ver «Archivos tocados». `python tools/verificar_docs.py` → `adrs 29`, `invariantes 38` y únicamente dos problemas, los enlaces de `impl.md` y de `_index.md` a `delta.md`, que `/sdd-completar` resuelve al escribirlo. `markdownlint-cli2` y Vale, sin alertas; `lychee` no estaba instalado.

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador (el formato de un archivo de pruebas lo aplicó el orquestador con `ruff format`)
- [x] Suite en verde, con la salida pegada arriba (1403 en `backend`, 474 en `tools`, 214 en `frontend`, 3 de `e2e`)
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas (17 mutantes)
- [x] Auditorías de cierre de fase `APROBADO` (arquitectura y SQL); las demás son de `/sdd-revisar`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta (`tkt-057-endurecimiento-http`) y sin secretos en el diff
