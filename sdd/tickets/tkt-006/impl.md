# Impl · TKT-006 · Autenticación y autorización por rol

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (lo escribe `/sdd-completar`)

## Qué se implementó

Las dos entregas del ticket están implementadas. El cierre contra los criterios de aceptación y la verificación final quedan para las secciones de abajo.

**Entrega A (filas 1 a 9).** Se declararon `pwdlib[argon2]` y `email-validator` como dependencias directas de `backend/pyproject.toml`, fijadas en `backend/uv.lock`. Se crearon el dominio de identidad (`correo`, `vigencia`, `acceso` y `autorizacion`, sin framework ni reloj), la configuración y el reloj de `aplicacion/`, el adaptador Argon2id sobre `pwdlib` en `infraestructura/`, y los modelos y el repositorio sobre las tablas de `v0001`. Abrir, validar y cerrar sesión viven en `aplicacion/sesiones.py` y `aplicacion/contexto.py`. La API expone sus cuatro rutas de sesión, todas `def`, montadas desde `servidor/fabrica.py`. La migración `v0004` impone que el correo esté en minúsculas. La fila 9 cerró la entrega con su tabla de mutantes y la regresión TC-R1 a TC-R7.

**Entrega B (filas 10 a 12).** `api/dependencias.py` añade `exigir_rol`, que cada ruta declara con los roles de su `x-roles`. `aplicacion/denegacion.py` asienta el `DENEGAR` por la interfaz publicada de `auditoria` (`asentar_denegacion`) en una transacción propia; si el asiento falla, se registra `denegacion_no_asentada` y la petición responde igualmente `403`. `cimenta.identidad.interfaz` publica `sesion_vigente`, `exigir_rol`, `UsuarioAutenticado`, `evaluar_resolucion`, `ResultadoResolucion` y `MotivoNegacion`. La fila 11 añadió la mutación de MT-10 a MT-14 y MT-21, con un test que mata el MT-10 literal. La fila 12 escribió el ADR-023 (`docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md`), su fila del índice y la documentación afectada.

Además, la revisión de ciclo 1 corrigió la codificación del subproceso de `lint-imports` en `tests/test_tkt006_dominio.py`; ver su sección.

## Ajustes respecto al design

Las filas 3 y 7 de `design.md` están marcadas `⚠ Ajustado`, y la fila 11 se ajustó durante la ejecución. Los cambios respecto al diseño son:

- **Fila 3 (configuración y contraseñas).** `ContrasenasArgon2` no importa `ConfiguracionIdentidad`, porque la capa `infraestructura` queda por debajo de `aplicacion` en el contrato `esqueleto-capas`. Declara el protocolo `CostesArgon2`, que `ConfiguracionIdentidad` cumple de forma estructural. Además, `Argon2Hasher(**costes)` no tipaba bajo `mypy`, y se usa un `TypedDict` parcial (`_CostesDeclarados`, `total=False`), sin cambio de comportamiento.
- **Fila 7 (API y composición).** La validación del correo usa `email_validator` con `test_environment=True` y devuelve el valor tal como se escribió. Es una decisión del usuario del 2026-10-22: `pydantic.networks.validate_email` rechaza `ana@cimenta.test`, y `email-validator` se declara como dependencia directa. El rojo de la fila 7 vino de la firma de `crear_aplicacion`, que aún no admitía `motor`, `reloj` ni `entorno` (`TypeError` en las pruebas y `call-arg` en `mypy`). TC-75 de TKT-005 se reescribió, autorizado por la decisión D-2, y se añadió el caso de arranque de `fastapi dev` sin variables de base (CA-R4).
- **Fila 11 (mutación y regresión).** Se añadió `test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada` para matar el MT-10 literal (`roles_de` con `functools.cache`). Ese mutante sobrevivía porque cada petición abre su propia sesión de base y la caché nunca acierta. El test se escribe a nivel de repositorio.

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/tests/test_tkt006_configuracion.py` | nuevo (fila 1: TC-18); ampliado en la fila 3 con TC-13 a TC-17 | pruebas |
| `backend/tests/test_tkt006_dominio.py` | nuevo (fila 2: TC-01 a TC-12, sin Docker) | pruebas |
| `backend/cimenta/identidad/dominio/correo.py` | nuevo (fila 2: `normalizar_correo`) | dominio |
| `backend/cimenta/identidad/dominio/vigencia.py` | nuevo (fila 2: `Ordenable`, `EstadoSesion`, `evaluar_vigencia`) | dominio |
| `backend/cimenta/identidad/dominio/acceso.py` | nuevo (fila 2: `credenciales_aceptadas`) | dominio |
| `backend/cimenta/identidad/dominio/autorizacion.py` | nuevo (fila 2: `rol_suficiente`, `MotivoNegacion`, `ResultadoResolucion`, `evaluar_resolucion`) | dominio |
| `backend/pyproject.toml` | añade `pwdlib[argon2]>=0.3.1` a `[project].dependencies` (fila 1); añade `cimenta.identidad.*` al override estricto de `mypy` (fila 3) | dependencias y tipos |
| `backend/cimenta/identidad/aplicacion/configuracion.py` | nuevo (fila 3: `ConfiguracionIdentidad` y `desde_entorno`) | aplicación |
| `backend/cimenta/identidad/aplicacion/reloj.py` | nuevo (fila 3: `Reloj` y `reloj_del_sistema`) | aplicación |
| `backend/cimenta/identidad/aplicacion/contexto.py` | nuevo (fila 5: `Contrasenas`, `UsuarioAutenticado`, `ContextoIdentidad` y `construir_contexto`) | aplicación |
| `backend/cimenta/identidad/aplicacion/sesiones.py` | nuevo (fila 5: `abrir_sesion` y `MENSAJE_CREDENCIALES_INVALIDAS`); ampliado en la fila 6: `validar_sesion`, `cerrar_sesion_vigente` y los mensajes `MENSAJE_SIN_SESION`, `MENSAJE_SESION_CADUCADA` y `MENSAJE_SESION_REVOCADA` | aplicación |
| `backend/cimenta/identidad/infraestructura/contrasenas.py` | nuevo (fila 3: `ContrasenasArgon2` sobre `pwdlib`, con el protocolo `CostesArgon2`) | infraestructura |
| `backend/cimenta/identidad/infraestructura/modelos.py` | nuevo (fila 4: `Base` con `naming_convention` y los modelos `Usuario`, `Rol`, `UsuarioRol`, `Sesion` e `IntentoAcceso`, que mapean las tablas de `v0001`) | infraestructura |
| `backend/cimenta/identidad/infraestructura/repositorio.py` | nuevo (fila 4: `CredencialAlmacenada`, `SesionAlmacenada` y las ocho funciones del repositorio) | infraestructura |
| `backend/tests/conftest.py` | ampliado (fila 4): `ENTORNO_DE_PRUEBA`, `INICIO_DEL_RELOJ`, `RelojDePrueba`, `SembrarUsuario` y las *fixtures* `reloj_de_prueba`, `sembrar_usuario`, `registro_tecnico`, `aplicacion_identidad` y `cliente`, ninguna `autouse` | pruebas |
| `backend/tests/test_tkt006_repositorio.py` | nuevo (fila 4: TC-58 y TC-59, con Docker) | pruebas |
| `backend/tests/test_tkt006_inicio_sesion.py` | nuevo (fila 5: TC-26 y TC-27 a nivel de aplicación, `CA-2`, `CA-3`, `CA-4`, `CA-8` esc. 4 y `contexto.py`, con Docker salvo cinco casos; la fila 7 le añade los casos HTTP) | pruebas |
| `backend/tests/test_tkt006_sesion_vigente.py` | nuevo (fila 6: TC-41 y sus dos hermanos de concurrencia, más los casos de nivel de aplicación de `validar_sesion` y `cerrar_sesion_vigente` para `CA-6` a `CA-11`, con Docker; la fila 7 le añade los casos HTTP de TC-32 a TC-40) | pruebas |
| `backend/tests/test_tkt006_csrf.py` | nuevo (fila 7, tanda 1: TC-50 y TC-51 por HTTP, con Docker) | pruebas |
| `backend/tests/test_tkt006_cierre.py` | nuevo (fila 7, tanda 1: TC-43 a TC-46 por HTTP, con Docker) | pruebas |
| `backend/tests/test_tkt006_enrutador.py` | nuevo (fila 7, tanda 2: TC-47 a TC-53 y complementos, sin Docker) | pruebas |
| `backend/tests/test_tkt006_esquema.py` | nuevo (fila 8: TC-54 a TC-57; TC-55 sin Docker, el resto con Docker) | pruebas |
| `backend/migraciones/versions/v0004_identidad_correo_en_minusculas.py` | nuevo (fila 8, verde: `ck_usuario_email_minusculas`, `CHECK (email = lower(email))`, con su bajada; revisión `0004`, anterior `0003`) | migración |
| `backend/tests/test_servidor_arranque.py` | editado (fila 7, tanda 2): TC-75 de TKT-005 reescrito por D-2 y un caso nuevo de arranque de `fastapi dev` sin variables de base | pruebas |
| `backend/cimenta/identidad/api/esquemas.py` | nuevo (fila 7: `forma_de_correo`, `TokenCsrf`, `CredencialesInicio`, `VigenciaSesion`, `UsuarioActual.desde`) | api |
| `backend/cimenta/identidad/api/dependencias.py` | nuevo (fila 7: `COOKIE_SESION`, `COOKIE_CSRF`, `contexto_de`, `sesion_vigente`); ampliado en la fila 10, verde: `exigir_rol` y `MENSAJE_ROL_INSUFICIENTE` | api |
| `backend/cimenta/identidad/api/rutas.py` | nuevo (fila 7: las cuatro rutas de sesión, todas `def`) | api |
| `backend/cimenta/identidad/api/montaje.py` | nuevo (fila 7: `montar_identidad`) | api |
| `backend/servidor/fabrica.py` | editado (fila 7): `crear_aplicacion(..., motor=None, reloj=None, entorno=None)` con motor perezoso; monta solo `cimenta.identidad.api.montaje` | composición |
| `backend/pyproject.toml` | además (fila 7): declara `email-validator>=2.3.0` como dependencia directa | dependencias |
| `backend/uv.lock` | fija `pwdlib` 0.3.1, `argon2-cffi` 25.1.0, `argon2-cffi-bindings` 26.1.0, `cffi` 2.1.1 y `pycparser` 3.11; amplía los marcadores de versión de Python | dependencias |
| `backend/tests/test_tkt006_permisos_rol.py` | nuevo (fila 10, rojo: TC-60 a TC-64 y TC-67, por HTTP y a nivel de aplicación, con Docker) | pruebas |
| `backend/tests/test_tkt006_enrutador.py` | ampliado (fila 10, rojo): TC-65, TC-66 y la publicación en la interfaz, sin Docker; los 16 casos existentes no se tocaron | pruebas |
| `backend/cimenta/identidad/aplicacion/denegacion.py` | nuevo (fila 10, verde: `registrar_denegacion`, transacción propia y fallo absorbido, PA-T6) | aplicación |
| `backend/tests/test_tkt006_repositorio.py` | ampliado (fila 11): `test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada`, que mata el `MT-10` literal; `text` pasa a la cabecera | pruebas |
| `backend/cimenta/identidad/interfaz.py` | editado (fila 10, verde): publica `sesion_vigente`, `exigir_rol`, `UsuarioAutenticado`, `evaluar_resolucion`, `ResultadoResolucion` y `MotivoNegacion` en `__all__` | interfaz publicada |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-18 | `test_tkt006_ca15_sin_passlib_ni_hash_generico` | **rechazo** | `CA-15` esc. 2 | FALLA (parte de dependencias) | |
| TC-01 | `test_tkt006_ca02_correo_se_normaliza_a_minusculas` | feliz | `CA-2` esc. 2 | FALLA (`correo`) | |
| TC-02 | `test_tkt006_ca06_sesion_vigente_antes_de_ambos_limites` | feliz | `CA-6` esc. 1 | FALLA (`vigencia`) | |
| TC-03 | `test_tkt006_ca08_caduca_al_llegar_expira_en` | **rechazo** | `CA-8` esc. 1 y 3 | FALLA (`vigencia`) | |
| TC-04 | `test_tkt006_ca08_caduca_por_inactividad` | **rechazo** | `CA-8` esc. 2 | FALLA (`vigencia`) | |
| TC-05 | `test_tkt006_ca09_revocada_prevalece` | **rechazo** | `CA-9` esc. 2 | FALLA (`vigencia`) | |
| TC-06 | `test_tkt006_ca10_usuario_desactivado_es_revocada` | **rechazo** | `CA-10`, `PA-T3` | FALLA (`vigencia`) | |
| TC-07 | `test_tkt006_ca08_vigencia_con_instantes_con_zona` | feliz | `CA-8` | FALLA (`vigencia`) | |
| TC-08 | `test_tkt006_ca04_credenciales_aceptadas` | **rechazo** | `CA-3`, `CA-4` | FALLA (`acceso`) | |
| TC-09 | `test_tkt006_ca13_quien_solicito_no_resuelve` (+ complemento) | **rechazo** | `CA-13` esc. 1 | FALLA (`autorizacion`) | |
| TC-10 | `test_tkt006_ca13_otra_persona_puede_resolver` | feliz | `CA-13` esc. 2 y 3 | FALLA (`autorizacion`) | |
| TC-11 | `test_tkt006_ca06_permiso_es_la_union` | feliz y **rechazo** | `CA-6` esc. 2, `CA-11`, `CA-12` | FALLA (`autorizacion`) | |
| TC-12 | `test_tkt006_ca13_dominio_de_identidad_puro` | **rechazo** de forma | `CA-13` esc. 4, `CA-R3` | FALLA (archivos ausentes) | |
| TC-12 (lint-imports) | `test_tkt006_ca13_contrato_dominio_sin_framework_se_cumple` | **rechazo** de forma | `CA-13` esc. 4, `CA-R3` | **NACE EN VERDE** (previsto) | |
| TC-13 | `test_tkt006_ca08_configuracion_por_omision` | feliz | `CA-8` esc. 4, `PA-T2` | FALLA (`configuracion`) | |
| TC-14 | `test_tkt006_ca08_configuracion_desde_el_entorno` (+ complemento `..._una_variable_no_arrastra_a_las_otras`) | feliz | `CA-8` esc. 4 | FALLA (`configuracion`) | |
| TC-15 | `test_tkt006_ca08_configuracion_rechaza_valores_invalidos` (35 casos: 5 variables por 7 valores) | **rechazo** | `CA-8`, `PA-T8` | FALLA (`configuracion`) | |
| TC-16 | `test_tkt006_ca15_hash_argon2id_con_los_parametros_configurados` (+ complemento `..._derivar_dos_veces_da_hashes_distintos`) | feliz y **rechazo** | `CA-15` esc. 1 | FALLA (`configuracion`, antes de llegar a `contrasenas`) | |
| TC-17 | `test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros` (2 casos: costes de prueba y por omisión) | **rechazo** | `CA-3` esc. 3 | FALLA (`configuracion`, antes de llegar a `contrasenas`) | |
| TC-58 | `test_tkt006_ca02_repositorio_inserta_y_lee` (+ 9 complementos de lectura, credencial, intento, último acceso y no confirmar) | feliz | `M11`, `CA-2`, `CA-3`, `CA-4`, `CA-9`, `CA-10` | FALLA (`repositorio`) | |
| TC-59 | `test_tkt006_ca09_tocar_y_revocar_respetan_la_revocacion` (+ 3 complementos) | **rechazo** | `CA-9`, ADR-014 | FALLA (`repositorio`) | |
| TC-26 | `test_tkt006_ca03_aplicacion_verifica_un_hash_siempre` (3 casos; + `..._el_hash_de_descarte_no_es_el_de_ningun_usuario`, `test_tkt006_ca02_aplicacion_inicio_correcto_verifica_un_hash`, `..._rechazo_con_contrato_de_error_completo` ×3 y `..._los_tres_rechazos_son_indistinguibles`) | **rechazo** | `CA-3` esc. 1 a 3, `CA-4` | FALLA (`contexto` o `sesiones`) | |
| TC-27 | `test_tkt006_ca03_aplicacion_el_intento_fallido_sobrevive` (3 casos; + 2 complementos) | **rechazo** | `CA-3` esc. 4, `RNF-04` | FALLA (`contexto` o `sesiones`) | |
| fila 5 | 4 casos de `abrir_sesion` para `CA-2` y `CA-8`, 3 de `construir_contexto` y 2 de inmutabilidad | feliz y **rechazo** de forma | `CA-2`, `CA-8` esc. 4, `CA-R4` | FALLA (`contexto` o `sesiones`) | |

### Ciclo TDD por fila

#### Fila 1 · Dependencia `pwdlib[argon2]`

**Rojo** — TC-18 falla porque `pyproject.toml` no declara `pwdlib` entre sus dependencias. La aserción es de contenido, no de importación: el archivo de pruebas solo importa la biblioteca estándar.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_configuracion.py`

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 1 item

tests\test_tkt006_configuracion.py F                                     [100%]

================================== FAILURES ===================================
________________ test_tkt006_ca15_sin_passlib_ni_hash_generico ________________

    def test_tkt006_ca15_sin_passlib_ni_hash_generico() -> None:
        """TC-18 · CA-15 esc. 2 — pwdlib[argon2] está declarada y fijada; no hay passlib, bcrypt ni hashlib.
    
        Parte de dependencias (fila 1). Falla por el contenido de `pyproject.toml` y `uv.lock`,
        no por una importación.
        """
        proyecto = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
        declaradas = dict(nombre_y_extras(r) for r in proyecto["project"]["dependencies"])
    
>       assert "pwdlib" in declaradas, (
            f"pyproject.toml no declara pwdlib entre sus dependencias: {sorted(declaradas)}"
        )
E       AssertionError: pyproject.toml no declara pwdlib entre sus dependencias: ['alembic', 'fastapi', 'psycopg', 'pydantic', 'sqlalchemy', 'structlog']
E       assert 'pwdlib' in {'alembic': frozenset(), 'fastapi': frozenset({'standard-no-fastapi-cloud-cli'}), 'psycopg': frozenset({'binary'}), 'pydantic': frozenset(), ...}

tests\test_tkt006_configuracion.py:46: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca15_sin_passlib_ni_hash_generico
============================== 1 failed in 0.11s ==============================
```

**Razón del fallo.** Es la esperada: ni `pyproject.toml` ni `uv.lock` contienen `pwdlib` (una búsqueda de `pwdlib|argon2|passlib|bcrypt` en ambos archivos no encontró ninguna coincidencia). El caso comprueba, en este orden y en un solo test: que `pwdlib` esté declarada con el extra `argon2`; que `pyproject.toml` no declare `passlib` ni `bcrypt`; que `uv.lock` fije `pwdlib` y `argon2-cffi` y no fije `passlib`; y que ningún `.py` de `cimenta/identidad/` contenga las palabras `passlib`, `bcrypt` ni `hashlib`. Hoy cae en la primera aserción, así que las demás todavía no se han ejercido con `pwdlib` presente. Las funciones auxiliares y la lectura de `uv.lock` (86 paquetes, sin `passlib`) y de los seis archivos actuales de `identidad` se comprobaron aparte, sin error.

**Verde** — ver «Fila 1 · verde y refactor» más abajo.

**Refactor** — ver la misma sección.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar:** pendiente.

**Mutación en rutas críticas:** no aplica a esta fila: no hay regla de dinero, límite, línea base ni avance. La parte de dependencias se protege con la comprobación de `uv sync --locked` y `pip-audit` de la fila.

#### Fila 1 · verde y refactor

**Verde.** Desde `backend/`, `uv add "pwdlib[argon2]"`. La sintaxis `pwdlib[argon2]` es la que documenta `pwdlib` para Argon2id, y el resolutor fijó `pwdlib` 0.3.1 con `argon2-cffi` 25.1.0. Ninguna otra dependencia se añadió. `uv add` dejó la línea en orden alfabético dentro de `dependencies`:

```diff
     "psycopg[binary]>=3.3.6",
+    "pwdlib[argon2]>=0.3.1",
     "pydantic>=2.14.1",
```

Comprobaciones, con la salida real de cada una:

1. `uv sync --locked` → código 0.

```
Resolved 91 packages in 1ms
Audited 88 packages in 15ms
EXIT=0
```

2. `uv run python -c "import pwdlib, argon2, email_validator; print(argon2.DEFAULT_TIME_COST, argon2.DEFAULT_MEMORY_COST, argon2.DEFAULT_PARALLELISM)"` → código 0. Los parámetros por omisión de `argon2-cffi` son 3 iteraciones, 65536 KiB de memoria y 4 hilos, lo que corresponde al perfil recomendado por la biblioteca.

```
3 65536 4
EXIT=0
```

   `email_validator` se importa sin problema, pero **no es dependencia declarada del proyecto**: llega de forma transitiva por `fastapi[standard-no-fastapi-cloud-cli]` (`uv tree --invert --package email-validator` → `email-validator v2.3.0` ← `fastapi v0.159.1` (extra `standard-no-fastapi-cloud-cli`) ← `cimenta`). No se añadió. Se deja al orquestador la decisión de declararla o no, como indica el diseño.

3. `uv run --with pip-audit pip-audit` → sin CVE abiertos. `pip-audit` se ejecuta con `--with`, así que no entra en el bloqueo del proyecto.

```
No known vulnerabilities found
EXIT=0
```

4. Verificaciones del pipeline:

`PYTHONUTF8=1 uv run lint-imports`:

```
Analyzed 80 files, 49 dependencies.
...
Contracts: 15 kept, 0 broken.
EXIT=0
```

`PYTHONUTF8=1 uv run pytest tests/test_tkt006_configuracion.py`:

```
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
...
collected 1 item

tests\test_tkt006_configuracion.py .                                     [100%]

============================== 1 passed in 0.04s ==============================
EXIT=0
```

`uv run mypy .`:

```
Success: no issues found in 127 source files
EXIT=0
```

`uv run ruff check .`:

```
All checks passed!
EXIT=0
```

`uv run ruff format --check .`:

```
127 files already formatted
EXIT=0
```

**Notas sobre el bloqueo.** `uv.lock` está en `backend/`, no en la raíz. El cambio en `uv.lock` tiene 155 líneas añadidas y una eliminada. La eliminada es la línea `"python_full_version < '3.15'"` de `resolution-markers`, que `uv` divide en `== '3.14.*'` y `< '3.14'` al resolver las nuevas dependencias: es un efecto automático de `uv`, no una edición manual. El intérprete de `.venv` es Python 3.14.3, aunque `requires-python` sea `>=3.13`; el bloqueo cubre ambos.

**Refactor.** Ninguno. El único cambio en `pyproject.toml` es la línea de la dependencia, en el orden que impone `uv`, y no hay código que simplificar.

**Verificación de cambios.** `git diff --stat` tras la fila: solo `backend/pyproject.toml` (1 línea) y `backend/uv.lock` (155 añadidas, 1 eliminada). Fuera de esos dos archivos, este paso solo toca `sdd/tickets/tkt-006/impl.md`. No se ha hecho commit.

**Violación de prueba.** No aplica como compuerta nueva: la fila no añade ningún control de código. El rojo de la fila 1 es el de TC-18, ya registrado arriba.

#### Fila 2 · rojo

Se escribió `backend/tests/test_tkt006_dominio.py` (sin Docker) con TC-01 a TC-12: 37 casos recolectados, de los que 36 caen y 1 nace en verde. Ningún archivo de producción se creó ni se tocó: `backend/cimenta/identidad/dominio/` sigue con solo su `__init__.py`.

Los símbolos del dominio (`normalizar_correo`, `evaluar_vigencia`, `EstadoSesion`, `credenciales_aceptadas`, `rol_suficiente`, `evaluar_resolucion`, `MotivoNegacion`, `ResultadoResolucion`) se importan **dentro de cada caso**, como en `test_tkt007_dominio.py`, para que cada uno falle por su cuenta con el `ModuleNotFoundError` del archivo que le falta y la recolección no se caiga. `Ordenable` solo se importa bajo `TYPE_CHECKING`, para el tipado de la ayuda `_evaluar`.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_dominio.py --tb=line` (salida abreviada: se omiten las líneas repetidas de `ModuleNotFoundError` y la lista de los 36 nombres, que coincide con la de «Casos» más abajo).

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 37 items

tests\test_tkt006_dominio.py FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.       [100%]

================================== FAILURES ===================================
E   ModuleNotFoundError: No module named 'cimenta.identidad.dominio.correo'
tests\test_tkt006_dominio.py:77: ModuleNotFoundError: No module named 'cimenta.identidad.dominio.correo'
E   ModuleNotFoundError: No module named 'cimenta.identidad.dominio.vigencia'
tests\test_tkt006_dominio.py:88: ModuleNotFoundError: No module named 'cimenta.identidad.dominio.vigencia'
...  (15 casos en total fallan igual por `vigencia`)
E   ModuleNotFoundError: No module named 'cimenta.identidad.dominio.acceso'
tests\test_tkt006_dominio.py:234: ModuleNotFoundError: No module named 'cimenta.identidad.dominio.acceso'
...  (8 casos por `acceso`)
E   ModuleNotFoundError: No module named 'cimenta.identidad.dominio.autorizacion'
tests\test_tkt006_dominio.py:245: ModuleNotFoundError: No module named 'cimenta.identidad.dominio.autorizacion'
...  (11 casos por `autorizacion`)
E   AssertionError: Faltan archivos en cimenta/identidad/dominio/: ['__init__.py']
    assert {'__init__.py'} >= {'acceso.py',...'vigencia.py'}
      Extra items in the right set:
      'acceso.py'
      'vigencia.py'
      'correo.py'
      'autorizacion.py'
tests\test_tkt006_dominio.py:342: AssertionError: Faltan archivos en cimenta/identidad/dominio/: ['__init__.py']
=========================== short test summary info ===========================
FAILED tests/test_tkt006_dominio.py::test_tkt006_ca02_correo_se_normaliza_a_minusculas
... (36 líneas FAILED)
FAILED tests/test_tkt006_dominio.py::test_tkt006_ca13_dominio_de_identidad_puro
======================== 36 failed, 1 passed in 0.43s =========================
```

**Casos.**

| # | Test | Casos | Razón del fallo |
|---|---|---|---|
| TC-01 | `test_tkt006_ca02_correo_se_normaliza_a_minusculas` | 1 | `ModuleNotFoundError` de `cimenta.identidad.dominio.correo` |
| TC-02 | `test_tkt006_ca06_sesion_vigente_antes_de_ambos_limites` | 1 | `ModuleNotFoundError` de `...dominio.vigencia` |
| TC-03 | `test_tkt006_ca08_caduca_al_llegar_expira_en` | 3 (199, 200, 201) | ídem `vigencia` |
| TC-04 | `test_tkt006_ca08_caduca_por_inactividad` | 3 (149, 150, 151) | ídem `vigencia` |
| TC-05 | `test_tkt006_ca09_revocada_prevalece` | 4 | ídem `vigencia` |
| TC-06 | `test_tkt006_ca10_usuario_desactivado_es_revocada` | 3 | ídem `vigencia` |
| TC-07 | `test_tkt006_ca08_vigencia_con_instantes_con_zona` | 1 | ídem `vigencia` |
| TC-08 | `test_tkt006_ca04_credenciales_aceptadas` | 8 (las combinaciones) | `ModuleNotFoundError` de `...dominio.acceso` |
| TC-09 | `test_tkt006_ca13_quien_solicito_no_resuelve` y `test_tkt006_ca13_resolucion_no_recibe_roles_y_su_resultado_es_inmutable` | 2 | `ModuleNotFoundError` de `...dominio.autorizacion` |
| TC-10 | `test_tkt006_ca13_otra_persona_puede_resolver` | 1 | ídem `autorizacion` |
| TC-11 | `test_tkt006_ca06_permiso_es_la_union` | 8 | ídem `autorizacion` |
| TC-12 (AST) | `test_tkt006_ca13_dominio_de_identidad_puro` | 1 | `AssertionError`: faltan los cuatro archivos del dominio (aserción anti-verde-vacío); aún no se ejerce la lista blanca de importaciones ni la ausencia de `raise` |
| TC-12 (lint-imports) | `test_tkt006_ca13_contrato_dominio_sin_framework_se_cumple` | 1 | **Nace en verde**, previsto: con el dominio sin archivos el contrato `dominio-sin-framework` se cumple (1 kept, 0 broken) |

Todas las razones son las esperadas: un módulo que no existe o los archivos que faltan, ninguna por entorno, sintaxis o importación de terceros. Los casos de TC-09 y TC-10 que comprueban `FrozenInstanceError`, la firma de `evaluar_resolucion` y los campos del `dataclass` se ejercerán en cuanto exista `autorizacion.py`.

**Casos que nacen en verde.** Uno, previsto por el diseño: la parte de `lint-imports` de TC-12. Se separó de la parte AST (el diseño las reúne en TC-12) para que el rojo de la AST no oculte el verde del contrato y para anotar cada uno por separado. Su prueba de que depende de algo es la mutación, que no se ha ejecutado todavía: añadir al dominio de identidad una importación de `pwdlib` o de `contrato_error` debe romper el contrato (`1 broken`). Una importación de `datetime` no lo rompe, porque es biblioteca estándar (ADR-021); esa la atrapa solo la parte AST de TC-12.

**Qué afirma cada decisión de diseño que se probó más allá del literal.**

- Bordes con enteros en TC-03 y TC-04: un instante antes, el límite exacto y uno después, con el otro límite lejos, para que cada mutante de `<` por `<=` o de `or` por `and` caiga solo en el suyo.
- TC-05 y TC-06 cubren la precedencia: `REVOCADA` gana a `CADUCADA` tanto por la marca de revocación como por el usuario desactivado, en cualquier estado de caducidad.
- TC-07 añade el mismo instante escrito en otra zona (`UTC-6`): el borde no se mueve.
- TC-08 recorre las ocho combinaciones con `itertools.product` y comprueba que el resultado es el booleano exacto (`is`), no un valor «verdadero».
- TC-09 compara con otro objeto `UUID` de igual valor (mutante `is` por `==`) y comprueba que la función no recibe roles (`inspect.signature`), que sus parámetros son solo de palabra clave, que el resultado está congelado y que no tiene atributo `regla` ni `RN-` en su `repr`.
- TC-11 usa los seis valores de `Rol` de `contrato_error` como cadenas, como llegan de `usuario_rol` y de `x-roles`, y añade dos casos que el diseño no listaba: dos roles ajenos y una ruta sin roles requeridos (nadie pasa).

**Comprobación del oráculo, fuera del repositorio.** Para demostrar que los tests no exigen más ni menos que el diseño, se copió el árbol a la carpeta temporal de la sesión y se escribieron allí los cuatro archivos con los cuerpos literales de «Dominio» (ese código **no** está en el repositorio): los 36 casos pasaron. Después se aplicaron ocho mutantes a esa copia, de uno en uno, y cada uno puso en rojo al menos un caso: `<` por `<=` en `expira_en` (2 casos caen), `<` por `<=` en la inactividad (2), `or` por `and` en `revocada or not usuario_activo` (6), quitar el `not usuario_activo` (2), quitar `activo` de `credenciales_aceptadas` (1), `isdisjoint` por `issubset` (2), `==` por `is` en `evaluar_resolucion` (1) y quitar `.lower()` (1). La mutación oficial sobre el código real se hace en la fila 9.

**Ruff.** `uv run ruff check tests/test_tkt006_dominio.py` y `uv run ruff format --check tests/test_tkt006_dominio.py` pasan. `uv run mypy .` no se corrió: con los módulos ausentes dará `import-not-found` en las importaciones bajo `TYPE_CHECKING`, igual que en `test_tkt007_dominio.py` durante su rojo; queda en verde con la fila.

**Verde** — ver «Fila 2 · verde y refactor» más abajo.

**Tests devueltos al tester:** ninguno.

#### Fila 2 · verde y refactor

**Verde.** Se crearon en `backend/cimenta/identidad/dominio/` los cuatro archivos con el código literal de «Capas afectadas · Dominio» del diseño, con docstrings que citan la regla (`M11`, `PA-T10`, `RNF-01`, `ADR-014`, `PA-T3`, `M2`, `PA-T4`, `M7`, `M8`, `PA-T1`) y sin inventar ningún `RN-xx`. Solo importan `__future__`, `dataclasses`, `enum`, `typing` y `uuid`; `autorizacion.py` no contiene ningún `raise`. Ningún test se modificó.

- `correo.py`: `normalizar_correo` (`.lower()`, sin recortar).
- `vigencia.py`: `Ordenable`, `EstadoSesion`, `evaluar_vigencia` (genérica, sin `datetime`; `REVOCADA` gana a `CADUCADA`; en el límite exacto ya caducó).
- `acceso.py`: `credenciales_aceptadas`.
- `autorizacion.py`: `rol_suficiente`, `MotivoNegacion`, `ResultadoResolucion` (congelado, sin atributo `regla`) y `evaluar_resolucion` (solo palabras clave, sin roles, D-5).

Comandos desde `backend/` con `PYTHONUTF8=1`, con la salida real:

`uv run pytest tests/test_tkt006_dominio.py` (sin Docker):

```
collected 37 items

tests\test_tkt006_dominio.py .....................................       [100%]

============================= 37 passed in 0.42s ==============================
EXIT=0
```

`uv run mypy .`: `Success: no issues found in 132 source files`. `uv run ruff check .`: `All checks passed!`. `uv run python -m herramientas.verificar_float`: `verificar_float: archivos revisados: 18; hallazgos: 0`. `uv run lint-imports`: `Contracts: 15 kept, 0 broken.`

Regresión: `tests/test_tkt006_configuracion.py` (TC-18, que escanea la carpeta en busca de `passlib`, `bcrypt` y `hashlib`) sigue en verde con `1 passed`, y `tests/test_tkt007_dominio.py` con `54 passed`.

**Refactor.** Solo formato: `ruff format --check` marcó la firma de `evaluar_resolucion`, que superaba el ancho de línea, y `uv run ruff format cimenta/identidad/dominio` la partió en tres líneas sin cambiar comportamiento. Tras el cambio: `132 files already formatted`, `ruff check` y `mypy` limpios y los 37 casos en verde.

**Supuestos y desviaciones.** Ninguna respecto al diseño. `Ordenable` lleva un docstring corto que el diseño no traía, y `Self` se importa de `typing` (lista blanca). No se ejecutó la mutación sobre el código real: es de la fila 9.

**Tests devueltos al tester:** ninguno.

#### Fila 3 · rojo

Se añadieron a `backend/tests/test_tkt006_configuracion.py` los casos de TC-13 a TC-17, sin tocar TC-18. El archivo pasó de 1 a 43 casos recolectados: 42 caen y 1 pasa, que es TC-18 (ya estaba en verde desde la fila 1; no es un test que nazca en verde). **Ningún caso nuevo nace en verde.** No se creó ni se tocó ningún archivo de producción ni `pyproject.toml`: `backend/cimenta/identidad/aplicacion/` e `infraestructura/` siguen con solo su `__init__.py`. Sin Docker.

Los símbolos de producción (`ConfiguracionIdentidad`, `ContrasenasArgon2`) se importan **dentro de cada caso**, como en las filas anteriores. `ENTORNO_DE_PRUEBA` se declara como constante del propio archivo, porque la fila 4 es la que lo lleva a `conftest.py`; ningún caso pide una *fixture*. Además de los casos del diseño se añadieron tres complementos, cada uno con su motivo: `..._una_variable_no_arrastra_a_las_otras` (un entorno con una sola variable deja las demás por omisión, lo que no cubre TC-13 ni TC-14), `..._derivar_dos_veces_da_hashes_distintos` (cada hash lleva su sal; un mutante que fije la sal pasaría TC-16) y, en TC-17, la comprobación de que el hash real y el de descarte traen el segmento de parámetros antes de compararlos, para que la igualdad nunca sea entre dos `None`.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_configuracion.py --tb=line` (salida abreviada: las 84 líneas de traza repiten el mismo error y se omiten; los 35 identificadores de TC-15 se condensan).

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 43 items

tests\test_tkt006_configuracion.py .FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF [ 86%]
FFFFFF                                                                   [100%]

================================== FAILURES ===================================
E   ModuleNotFoundError: No module named 'cimenta.identidad.aplicacion.configuracion'
tests\test_tkt006_configuracion.py:91: ModuleNotFoundError: No module named 'cimenta.identidad.aplicacion.configuracion'
...  (42 casos fallan igual, todos con ese mismo error)
=========================== short test summary info ===========================
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca08_configuracion_por_omision
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca08_configuracion_desde_el_entorno
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca08_configuracion_una_variable_no_arrastra_a_las_otras
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca08_configuracion_rechaza_valores_invalidos[CIMENTA_SESION_CADUCIDAD_MINUTOS-0]
...  (34 casos más de TC-15, de las cinco variables por los siete valores)
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca15_hash_argon2id_con_los_parametros_configurados
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca15_derivar_dos_veces_da_hashes_distintos
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros[costes_de_prueba]
FAILED tests/test_tkt006_configuracion.py::test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros[costes_por_omision]
======================== 42 failed, 1 passed in 0.09s =========================
```

**Casos.**

| # | Test | Casos | Razón del fallo |
|---|---|---|---|
| TC-13 | `test_tkt006_ca08_configuracion_por_omision` | 1 | `ModuleNotFoundError` de `cimenta.identidad.aplicacion.configuracion` |
| TC-14 | `test_tkt006_ca08_configuracion_desde_el_entorno` y `..._una_variable_no_arrastra_a_las_otras` | 2 | ídem `configuracion` |
| TC-15 | `test_tkt006_ca08_configuracion_rechaza_valores_invalidos` | 35 | ídem `configuracion` |
| TC-16 | `test_tkt006_ca15_hash_argon2id_con_los_parametros_configurados` y `..._derivar_dos_veces_da_hashes_distintos` | 2 | ídem `configuracion`: es la primera importación del caso, así que `infraestructura.contrasenas` aún no se ejerce |
| TC-17 | `test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros` | 2 | ídem `configuracion`, por el mismo motivo |
| TC-18 | `test_tkt006_ca15_sin_passlib_ni_hash_generico` | 1 | **Pasa**: no se alteró y sigue en verde desde la fila 1 |

Todas las razones son las esperadas: un módulo que no existe, ninguna por entorno, sintaxis o importación de terceros. Los archivos `aplicacion/reloj.py` e `infraestructura/contrasenas.py` quedan sin un `ModuleNotFoundError` propio, porque cada caso importa primero `configuracion`; el rojo por `contrasenas` aparecerá en cuanto exista `configuracion` y falte solo `contrasenas`. Esto no pierde cobertura: ambos módulos los ejerce el verde de la fila.

**Casos que nacen en verde.** Ninguno entre los nuevos.

**Comprobación del oráculo, fuera del repositorio.** Para demostrar que los tests exigen lo que el diseño dice y no más, se copió `cimenta/` y el archivo de pruebas a la carpeta temporal de la sesión y se escribieron allí `configuracion.py` y `contrasenas.py` según el diseño (ese código **no** está en el repositorio): los 43 casos pasaron. Después se aplicaron tres mutantes a esa copia, de uno en uno: hash de descarte con `PasswordHash.recommended()` en lugar de los costes configurados (cae `test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros[costes_de_prueba]`, que es el caso para el que sirve `ENTORNO_DE_PRUEBA`); validación `[0-9]+` sin el primer dígito distinto de cero ni el tope de nueve dígitos (caen 5 casos de TC-15, uno por variable, el del valor `"0"`); y validación `\d+`, que en Python acepta dígitos de ancho completo (caen 10 casos de TC-15: el valor `"0"` y `"１２"` en cada una de las cinco variables). Un primer intento de este último mutante, mal escrito con `sed`, produjo la expresión literal `d+`; se descartó y se repitió con Python.

**Ruff.** `uv run ruff check tests/test_tkt006_configuracion.py` y `uv run ruff format --check tests/test_tkt006_configuracion.py` pasan (se aplicó `ruff format` una vez al añadir los casos). `uv run mypy .` no se corrió: con los módulos ausentes daría `import-not-found` en las importaciones de los casos, igual que durante los rojos anteriores; queda en verde con la fila.

**Verde** — pendiente: `aplicacion/configuracion.py`, `aplicacion/reloj.py`, `infraestructura/contrasenas.py` y `"cimenta.identidad.*"` en el *override* de `mypy`.

**Tests devueltos al tester:** ninguno.

#### Fila 3 · verde y refactor

**Verde.** Se escribieron tres archivos de producción, con el código del diseño («Capas afectadas») y sin tocar ningún test:

- `backend/cimenta/identidad/aplicacion/reloj.py`: `type Reloj = Callable[[], datetime]` y `reloj_del_sistema()`, que devuelve `datetime.now(UTC)`. Es el único archivo de `identidad` que importa `datetime`.
- `backend/cimenta/identidad/aplicacion/configuracion.py`: `ConfiguracionIdentidad`, `dataclass` congelada con `slots`, y `desde_entorno(entorno: Mapping[str, str])`. Los valores por omisión son 720 minutos de caducidad absoluta y 30 de inactividad (PA-T2); los costes de Argon2 quedan en `None` si no vienen. Cada valor presente pasa por `re.fullmatch(r"[1-9][0-9]{0,8}", valor)` y, si falla, lanza `ValueError(f"{nombre} debe ser un entero positivo; se recibió {valor!r}")`.
- `backend/cimenta/identidad/infraestructura/contrasenas.py`: `ContrasenasArgon2`, que construye `PasswordHash((Argon2Hasher(...),))` pasando solo los costes que no son `None`. El hash de descarte se deriva con ese mismo `PasswordHash` y `secrets.token_urlsafe(32)` al construir el adaptador, no en la primera petición.

Dos decisiones de forma que el diseño no fija de forma explícita:

1. **`ContrasenasArgon2` no importa `ConfiguracionIdentidad`.** La capa `infraestructura` queda por debajo de `aplicacion` en el contrato `esqueleto-capas`, así que importarla rompería el contrato. El adaptador declara el protocolo `CostesArgon2`, con tres propiedades de solo lectura, y `ConfiguracionIdentidad` lo cumple de forma estructural. La prueba de TC-16 y TC-17 sigue pasando la configuración tal cual.
2. **`Argon2Hasher(**costes)` no tipaba bajo `mypy --strict`.** Un `dict[str, int]` expandido cubre también el parámetro `type` de la biblioteca, y `mypy` lo rechazó con `arg-type`. La corrección es un `TypedDict` parcial (`_CostesDeclarados`, `total=False`) que solo declara `time_cost`, `memory_cost` y `parallelism`. No cambia el comportamiento ni usa `Any`.

**Desviación respecto a la instrucción de la orden de trabajo.** La orden pedía validar con `[0-9]+`. Ese patrón acepta `"0"`, y TC-15 exige rechazarlo porque los costes y los minutos son positivos. Se conserva `[1-9][0-9]{0,8}`, que es el patrón literal del diseño: sigue siendo solo ASCII (sin `\d`), rechaza el cero y pone un tope de nueve dígitos. TC-15 pasa con él.

`pwdlib` 0.3.1 trae `py.typed` (comprobado en `backend/.venv/Lib/site-packages/pwdlib/py.typed`), así que **no** se añadió el override `ignore_missing_imports` para `pwdlib.*`.

Comprobaciones, desde `backend/` con `PYTHONUTF8=1`, con la salida real:

1. `uv run pytest tests/test_tkt006_configuracion.py tests/test_tkt006_dominio.py` → verde.

```
collected 80 items

tests\test_tkt006_configuracion.py ..................................... [ 46%]
......                                                                   [ 53%]
tests\test_tkt006_dominio.py .....................................       [100%]

============================= 80 passed in 0.68s ==============================
```

   Los 80 casos son los 43 de `test_tkt006_configuracion.py` (TC-13 a TC-18 con sus complementos) y los 37 de `test_tkt006_dominio.py` (TC-01 a TC-12). Ninguno nace en verde y ningún test se editó.

2. `uv run mypy .`: en la primera pasada falló con el error de la decisión 2 (`Argon2Hasher ... expected "Type"`). Tras el `TypedDict`:

```
Success: no issues found in 135 source files
```

3. `uv run ruff check .` → `All checks passed!`

4. `uv run ruff format --check .` → `135 files already formatted`

5. `uv run python -m herramientas.verificar_float` → `verificar_float: archivos revisados: 18; hallazgos: 0` (código 0).

6. `uv run lint-imports` → `Contracts: 15 kept, 0 broken.` (código 0).

7. Regresión: `uv run pytest tests/test_tkt007_dominio.py tests/test_servidor_arranque.py -q` → `62 passed in 5.81s`.

**Refactor.** Ninguno más allá de la corrección de tipos de la decisión 2. El código sigue el diseño literal y `ruff format` no cambió nada. No se añadieron comentarios ni abstracciones que el diseño no pida.

**Mutación.** No se ejecutó en esta fila. Las mutaciones de configuración y del hash de descarte que este ticket exige se comprobaron antes, en la fila 3 de rojo, sobre una copia fuera del repositorio. Lo que corresponde ahora es que el tester las repita sobre el código real al cerrar.

**Tests devueltos al tester:** ninguno.

#### Fila 4 · rojo

Se añadieron a `backend/tests/conftest.py` las *fixtures* que el diseño asigna a este ticket y se escribió `backend/tests/test_tkt006_repositorio.py` (con Docker) con TC-58 y TC-59: 14 casos recolectados, **los 14 caen y ninguno nace en verde**. No se creó ni se tocó ningún archivo de producción: `backend/cimenta/identidad/infraestructura/` sigue con `contrasenas.py` (fila 3) y su `__init__.py`; ni `modelos.py` ni `repositorio.py` existen.

**Fixtures de `conftest.py`** (ninguna `autouse`; `test_tkt004_conftest.py` lo comprueba):

| Pieza | Qué es |
|---|---|
| `ENTORNO_DE_PRUEBA`, `INICIO_DEL_RELOJ` | Constantes: costes baratos de Argon2 (`t=1`, `m=8192`, `p=1`) y `2026-10-21 09:00 UTC` |
| `RelojDePrueba` y `reloj_de_prueba` | Clase con `ahora`, `__call__` y `avanzar(delta)` y su *fixture* |
| `sembrar_usuario(motor_aplicacion)` | Fábrica `(correo, contrasena, roles=(), activo=True, nombre="Ana Torres") -> UUID`. Deriva el hash con `ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))` e inserta `usuario` y `usuario_rol` con el rol de aplicación, buscando cada rol por `clave`; una clave que la semilla no tiene falla con nombre |
| `registro_tecnico` | `io.StringIO` |
| `aplicacion_identidad` | `crear_aplicacion(destino_registro=..., motor=motor_aplicacion, reloj=reloj_de_prueba, entorno=ENTORNO_DE_PRUEBA)` |
| `cliente` | `TestClient(aplicacion_identidad, base_url="https://testserver", raise_server_exceptions=False)`, cerrado al terminar |

`sembrar_usuario` ya funciona hoy (usa símbolos de la fila 3), y los 14 casos llegan a su cuerpo con el usuario sembrado. `aplicacion_identidad` y `cliente` importan `servidor.fabrica.crear_aplicacion` **dentro** del cuerpo y fallarán solo cuando alguien los use (fila 7): `crear_aplicacion` aún no admite `motor`, `reloj` ni `entorno`. Por eso `uv run mypy tests/conftest.py` reporta hoy tres `call-arg` en esa llamada; se resuelven con el verde de la fila 7. `FastAPI` y `TestClient` se importan arriba: ya son dependencias del proyecto.

Los símbolos de producción de los casos se importan con `import cimenta.identidad.infraestructura.repositorio as repositorio` **dentro** de cada caso, no con `from ... import repositorio`: la primera forma lanza `ModuleNotFoundError` del archivo que falta (la segunda lanza un `ImportError` menos preciso, que fue lo que se vio en el primer intento y se corrigió). Las sesiones de TC-59 se siembran con SQL directo, para que su rojo y su verde no dependan de `insertar_sesion`.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_repositorio.py --tb=line` (salida abreviada: las 14 líneas de traza repiten el mismo error).

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 14 items

tests\test_tkt006_repositorio.py FFFFFFFFFFFFFF                          [100%]

================================== FAILURES ===================================
E   ModuleNotFoundError: No module named 'cimenta.identidad.infraestructura.repositorio'
...  (14 casos fallan igual, todos con ese mismo error)
=========================== short test summary info ===========================
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca02_repositorio_inserta_y_lee
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca02_leer_sesion_inexistente_es_none
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca10_leer_sesion_trae_el_estado_del_usuario
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca09_leer_sesion_trae_la_revocacion
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca02_roles_de_devuelve_las_claves_sembradas
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca02_buscar_credencial_con_el_correo_exacto
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca04_buscar_credencial_devuelve_al_desactivado
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca03_insertar_intento_conserva_el_correo_tal_como_se_escribio
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca02_marcar_ultimo_acceso_no_toca_actualizado_en
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca02_el_repositorio_no_confirma
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca06_tocar_sesion_vigente_desliza_la_actividad
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca09_tocar_y_revocar_respetan_la_revocacion
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca09_revocar_no_toca_la_actividad_ni_borra_la_fila
FAILED tests/test_tkt006_repositorio.py::test_tkt006_ca09_tocar_y_revocar_una_sesion_inexistente_devuelven_false
============================= 14 failed in 3.48s ==============================
```

**Casos.** Todos fallan con el `ModuleNotFoundError` de `cimenta.identidad.infraestructura.repositorio`, la razón esperada: ninguno por Docker, entorno, sintaxis ni importación de terceros.

| # | Test | Qué afirma |
|---|---|---|
| TC-58 | `test_tkt006_ca02_repositorio_inserta_y_lee` | `insertar_sesion` escribe `creada_en = ultima_actividad = ahora`, `revocada_en` nulo, `origen_ip` y `agente_usuario` (comprobado con una conexión nueva) y `leer_sesion` devuelve `usuario_id`, `nombre`, `email`, `expira_en`, `ultima_actividad`, `revocada_en` y `usuario_activo` |
| TC-58 | `..._leer_sesion_inexistente_es_none` | Una sesión que no existe se lee como `None` |
| TC-58 | `..._leer_sesion_trae_el_estado_del_usuario` | `usuario_activo` es `False` para un usuario desactivado (el dominio decide, `CA-10`) |
| TC-58 | `..._leer_sesion_trae_la_revocacion` | `revocada_en` viaja en la lectura |
| TC-58 | `..._roles_de_devuelve_las_claves_sembradas` | `frozenset` con las claves del usuario pedido, sin mezclar a otros; vacío para un usuario sin roles o inexistente |
| TC-58 | `..._buscar_credencial_con_el_correo_exacto` | Devuelve `id`, `nombre`, `email`, `activo` y un `password_hash` que empieza por `$argon2id$`; con otro correo, `None`; con el mismo en mayúsculas, `None` (normalizar es del dominio) |
| TC-58 | `..._buscar_credencial_devuelve_al_desactivado` | Un desactivado se devuelve con `activo` en `False` |
| TC-58 | `..._insertar_intento_conserva_el_correo_tal_como_se_escribio` | Dos filas: el correo con mayúsculas y sin usuario, y el de un usuario real con `exitoso` verdadero y sin IP |
| TC-58 | `..._marcar_ultimo_acceso_no_toca_actualizado_en` | `ultimo_acceso` pasa de nulo a la hora dada y `actualizado_en` no cambia `(asumido)` |
| TC-58 | `..._el_repositorio_no_confirma` | Lo escrito se ve dentro de la transacción de quien llama, no desde otra conexión, y desaparece con `rollback` |
| TC-59 | `..._tocar_sesion_vigente_desliza_la_actividad` | `tocar_sesion` devuelve `True` y mueve solo `ultima_actividad` |
| TC-59 | `test_tkt006_ca09_tocar_y_revocar_respetan_la_revocacion` | Tras revocar, `tocar_sesion` devuelve `False` y `ultima_actividad` conserva el valor anterior; un segundo `revocar_sesion` devuelve `False` y `revocada_en` conserva el primer valor |
| TC-59 | `..._revocar_no_toca_la_actividad_ni_borra_la_fila` | `revocar_sesion` escribe `revocada_en`, deja `ultima_actividad` y la fila (`CA-9` esc. 4: nunca se borra) |
| TC-59 | `..._tocar_y_revocar_una_sesion_inexistente_devuelven_false` | Sin fila, ambas devuelven `False` y no se crea ninguna |

**Nombres que el diseño no fija y los tests dan por sentados.** Los campos de `CredencialAlmacenada` son `id`, `nombre`, `email`, `password_hash` y `activo`; los de `SesionAlmacenada`, `usuario_id`, `nombre`, `email`, `expira_en`, `ultima_actividad`, `revocada_en` y `usuario_activo`. Salen de las columnas del `SELECT` y de los usos de `abrir_sesion` y `validar_sesion` en el diseño. Las funciones se llaman con los nombres y las palabras clave literales de la tabla del repositorio.

**Casos que nacen en verde.** Ninguno.

**Comprobación del oráculo, fuera del repositorio.** Se copió el árbol a la carpeta temporal de la sesión y se escribió allí un `repositorio.py` con las sentencias de la tabla del diseño (ese código **no** está en el repositorio): los 14 casos pasaron, con Docker y el rol de aplicación. Después se aplicaron seis mutantes a esa copia, de uno en uno, y cada uno puso en rojo exactamente un caso: quitar `AND revocada_en IS NULL` de `tocar_sesion` (cae `..._tocar_y_revocar_respetan_la_revocacion`; es MT-9), quitarlo de `revocar_sesion` (cae el mismo caso), que `marcar_ultimo_acceso` toque también `actualizado_en` (cae `..._marcar_ultimo_acceso_no_toca_actualizado_en`), comparar el correo con `lower()` en `buscar_credencial` (cae `..._buscar_credencial_con_el_correo_exacto`), guardar el correo del intento en minúsculas (cae `..._insertar_intento_conserva_el_correo_tal_como_se_escribio`) y quitar el filtro por usuario de `roles_de` (cae `..._roles_de_devuelve_las_claves_sembradas`). La mutación oficial sobre el código real se hace en la fila 9.

**Regresión.** Con las *fixtures* nuevas en `conftest.py`, `uv run pytest tests/test_tkt004_conftest.py tests/test_identidad_sin_create_all.py tests/test_tkt007_motor.py tests/test_tkt006_dominio.py tests/test_tkt006_configuracion.py` da `87 passed in 134.39s (0:02:14)`, sin ningún fallo: ninguna *fixture* es `autouse` y no rompen nada. `uv run ruff check tests` y `uv run ruff format --check tests` pasan.

**Tests devueltos al tester:** ninguno.

#### Fila 4 · verde y refactor

**Verde, de uno en uno.** Se escribieron `modelos.py` y `repositorio.py` siguiendo la tabla de infraestructura de `design.md` («Capas afectadas · Infraestructura»). La prueba de la fila pasó en el primer intento: las catorce pruebas en verde, sin cambiar ningún test ni `conftest.py`. Como no hubo ciclo de corrección, no hay rojos intermedios que registrar.

Decisiones de implementación, todas dentro del diseño:

- `Base(DeclarativeBase)` con `MetaData(naming_convention=...)`, las mismas convenciones que `auditoria`. Los modelos usan `Mapped[...]` y `mapped_column`, con `Uuid`, `Text`, `Boolean` y `DateTime(timezone=True)`. Ningún modelo tiene `relationship`, `@validates` ni `event.listen`.
- Las claves foráneas de `usuario`, `usuario_rol` e `intento_acceso` se declaran con `ForeignKey` para que el mapa sea fiel a `v0001`. Las uniones de `leer_sesion`, `roles_de` y `buscar_credencial` llevan su `ON` explícito y no dependen de la clave declarada.
- `origen_ip` y `agente_usuario` son `Text`, como pide la fila.
- `insertar_sesion` e `insertar_intento` usan `insert(...).values(...)` ejecutado con `bd.execute`, sin pasar por `add` ni por `flush`, para que la escritura ocurra en la transacción de quien llama.
- Los tres `UPDATE` (`marcar_ultimo_acceso`, `tocar_sesion`, `revocar_sesion`) llevan `synchronize_session=False` en la sentencia. `tocar_sesion` y `revocar_sesion` usan `RETURNING` y devuelven `True` solo si hubo fila. La guarda `revocada_en IS NULL` va dentro del `WHERE` del `UPDATE`, no en una lectura previa.
- El parámetro de la `Session` se llama `bd` en vez de `s` del diseño. Es un nombre, no cambia el contrato.
- Ninguna función llama a `commit`, `rollback`, `begin` ni `flush`.

**Refactor.** Con la suite en verde, `ruff check --fix` corrigió el bloque de imports de `repositorio.py` (regla I001, bloque sin ordenar o sin formatear: la importación de `modelos` quedó partida en varias líneas), y `ruff format` lo dejó en forma. No se cambió comportamiento. Después de ese cambio se repitieron todas las comprobaciones sobre el estado final; las salidas pegadas abajo son de esa repetición.

Comprobaciones en `identidad` sin palabras prohibidas: `Grep` de `passlib|hashlib|float` sobre `backend/cimenta/identidad` no devuelve coincidencias.

**Salida real, desde `backend/`:**

```
$ PYTHONUTF8=1 uv run pytest tests/test_tkt006_repositorio.py -q
..............                                                           [100%]
14 passed in 3.99s
```

Los catorce casos de TC-58 y TC-59 pasan. Antes del código fallaban con `ModuleNotFoundError: No module named 'cimenta.identidad.infraestructura.repositorio'`.

```
$ PYTHONUTF8=1 uv run pytest tests/test_tkt004_conftest.py tests/test_identidad_sin_create_all.py -q
..                                                                       [100%]
2 passed in 0.03s
```

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
138 files already formatted

$ PYTHONUTF8=1 uv run python -m herramientas.verificar_float
verificar_float: archivos revisados: 18; hallazgos: 0

$ uv run lint-imports
Contracts: 15 kept, 0 broken.
```

```
$ uv run mypy .
tests\conftest.py:494: error: Unexpected keyword argument "motor" for "crear_aplicacion"  [call-arg]
tests\conftest.py:494: note: "crear_aplicacion" defined in "servidor.fabrica"
tests\conftest.py:494: error: Unexpected keyword argument "reloj" for "crear_aplicacion"  [call-arg]
tests\conftest.py:494: error: Unexpected keyword argument "entorno" for "crear_aplicacion"  [call-arg]
Found 3 errors in 1 file (checked 138 source files)
```

Los tres `call-arg` son el rojo previsto de la fila 7 (`crear_aplicacion` aún no admite `motor`, `reloj` ni `entorno`). No se han tocado.

**Suite completa**, con todas las *fixtures* ya presentes, desde `backend/`:

```
$ PYTHONUTF8=1 uv run pytest -q
1 failed, 963 passed in 194.81s (0:03:14)
FAILED tests/test_tkt005_regresion.py::test_tkt005_car2_calidad_estatica_sin_hallazgos[mypy]
```

El único fallo es `test_tkt005_car2_calidad_estatica_sin_hallazgos[mypy]`, que ejecuta `mypy .` y recibe los mismos tres `call-arg` de `tests/conftest.py:494`. No es un fallo nuevo de esta fila: viene del rojo de la fila 7 que ya estaba en `conftest.py` antes de empezar. Las demás 963 pruebas pasan.

**Migración.** Esta fila no añade DDL: no hay `downgrade` que probar ni `GRANT` nuevo. Las tablas y los permisos ya existen desde `v0001`, y el rol de aplicación ya tiene `SELECT, INSERT, UPDATE, DELETE` por omisión sobre ellas, con el `REVOKE` de `intento_acceso`.

**Tests devueltos al tester:** ninguno. No se ha tocado ningún test.

#### Fila 5 · rojo

Se escribió `backend/tests/test_tkt006_inicio_sesion.py` con los casos de **nivel de aplicación** de TC-26 y TC-27, más los de `abrir_sesion` que cubren `CA-2` a `CA-4` y `CA-8` esc. 4, y los de `contexto.py` que el diseño fija y ningún TC nombra: 25 casos recolectados, **los 25 caen y ninguno nace en verde**. No se creó ni se tocó ningún archivo de producción ni `conftest.py`: `backend/cimenta/identidad/aplicacion/` sigue con `configuracion.py`, `reloj.py` y su `__init__.py`; ni `contexto.py` ni `sesiones.py` existen. `git status` solo añade el archivo de pruebas y este `impl.md`.

Todos los casos llaman a `abrir_sesion` con un `ContextoIdentidad` construido a mano sobre `motor_aplicacion` (rol de aplicación, `NullPool`), con `reloj_de_prueba` y con `ContrasenasArgon2` de costes baratos; lo que ocurrió en la base se lee con una conexión **nueva** del rol de aplicación. Los usuarios los siembra `sembrar_usuario`. No se usa la *fixture* `sesion_bd`: ningún caso necesita una `Session` abierta por la prueba, y `abrir_sesion` abre la suya.

Los símbolos de producción (`abrir_sesion`, `ContextoIdentidad`, `UsuarioAutenticado`, `construir_contexto`, `MENSAJE_CREDENCIALES_INVALIDAS`) se importan **dentro del cuerpo** de cada caso o de las ayudas que este llama (`crear_contexto`, `rechazar`, `exigir_contrato_de_credenciales_invalidas`), nunca en una *fixture*: un fallo de importación en una *fixture* se reporta como `ERROR`, no como `FAILED`. Por eso los 25 casos caen como `FAILED` con `ModuleNotFoundError`.

**Preparado para la fila 7.** El archivo se abre con un docstring que lo dice: la fila 7 añade debajo los casos HTTP de TC-20 a TC-31 y la parte HTTP de TC-27, con `cliente` y `aplicacion_identidad`. El filtro del comando de la fila es `-k "aplicacion"`: todos los casos de esta fila llevan la palabra `aplicacion` en su nombre y **ningún caso HTTP la debe llevar**, o el filtro de esta fila lo recogería. El contador de contraseñas (`ContadorDeContrasenas`) y `con_contador` se dejaron como ayudas del propio archivo para que la fila 7 los reutilice en TC-28 y TC-29 con `dataclasses.replace(aplicacion.state.identidad, ...)`. El filtro no selecciona nada de otros archivos.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_inicio_sesion.py -k "aplicacion" --tb=line` (salida abreviada: se omiten las 25 líneas de traza con ruta absoluta, que repiten el mismo error, y se condensa la lista de los 25 nombres).

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 25 items

tests\test_tkt006_inicio_sesion.py FFFFFFFFFFFFFFFFFFFFFFFFF             [100%]

================================== FAILURES ===================================
E   ModuleNotFoundError: No module named 'cimenta.identidad.aplicacion.contexto'
...  (18 casos fallan así)
E   ModuleNotFoundError: No module named 'cimenta.identidad.aplicacion.sesiones'
...  (7 casos fallan así)
=========================== short test summary info ===========================
FAILED tests/test_tkt006_inicio_sesion.py::test_tkt006_ca03_aplicacion_verifica_un_hash_siempre[correo_inexistente]
FAILED tests/test_tkt006_inicio_sesion.py::test_tkt006_ca03_aplicacion_verifica_un_hash_siempre[contrasena_erronea]
FAILED tests/test_tkt006_inicio_sesion.py::test_tkt006_ca03_aplicacion_verifica_un_hash_siempre[usuario_desactivado]
...  (22 líneas FAILED más; la lista completa está en «Casos»)
============================= 25 failed in 5.04s ==============================
```

**Casos.** Dieciocho caen en la primera importación de `cimenta.identidad.aplicacion.contexto` (la de `crear_contexto` o `construir_contexto`) y siete en la de `cimenta.identidad.aplicacion.sesiones`, porque importan `abrir_sesion` antes de construir el contexto. Las dos razones son las esperadas: un módulo que no existe; ninguna por Docker, entorno, sintaxis o importación de terceros.

| # | Test | Casos | Qué afirma | Cae por |
|---|---|---|---|---|
| TC-26 | `test_tkt006_ca03_aplicacion_verifica_un_hash_siempre` | 3 (`correo_inexistente`, `contrasena_erronea`, `usuario_desactivado`) | Con el contador sobre `ContrasenasArgon2` y `dataclasses.replace`, una sola verificación por intento: `[(contrasena, hash)]` con el `hash_de_descarte` si el correo no existe y con el hash guardado del usuario si existe (también desactivado y con su contraseña correcta); el hash empieza por `$argon2id$` y `abrir_sesion` no deriva ninguno | `contexto` |
| TC-26 | `..._aplicacion_el_hash_de_descarte_no_es_el_de_ningun_usuario` | 1 | Con dos cuentas reales, el correo inexistente verifica contra el de descarte y no contra el hash de ninguna cuenta (un mutante que verifique siempre contra la primera pasaría «un hash») | `contexto` |
| TC-26 | `test_tkt006_ca02_aplicacion_inicio_correcto_verifica_un_hash` | 1 | Un inicio correcto también verifica una sola vez, contra el hash del usuario | `sesiones` |
| TC-26 | `test_tkt006_ca03_aplicacion_rechazo_con_contrato_de_error_completo` | 3 (los mismos escenarios) | `SesionInvalida`: `tipo` `SESION`, `estado_http` `401`, `motivo` `CREDENCIALES_INVALIDAS`, `mensaje` igual al literal «El correo o la contraseña no son correctos.» y a `MENSAJE_CREDENCIALES_INVALIDAS`; `cuerpo(frozenset(), correlacion)` con las claves exactas `tipo`, `mensaje`, `motivo` y `correlacion_id` (el que se le pasa), sin `detail` ni `acciones`; sin fila en `sesion`, `bitacora` sin filas y `ultimo_acceso` nulo | `contexto` |
| TC-26 | `..._aplicacion_los_tres_rechazos_son_indistinguibles` | 1 | Correo inexistente, contraseña errónea y desactivado con su contraseña correcta dan el mismo cuerpo (`CA-3` esc. 2, `CA-4`) | `contexto` |
| TC-27 | `test_tkt006_ca03_aplicacion_el_intento_fallido_sobrevive` | 3 | Tras capturar la `SesionInvalida`, una conexión nueva ve **una** fila de `intento_acceso`: `email` tal como se escribió, `usuario_id` (nulo si no existe), `exitoso` falso, `ocurrido_en` del reloj y `origen_ip` | `contexto` |
| TC-27 | `..._aplicacion_cada_intento_fallido_deja_su_fila` | 1 | Tres fallos de una cuenta y uno de un correo inexistente dejan cuatro filas (3 y 1): el conteo de `RNF-04` depende de ello | `contexto` |
| TC-27 | `..._aplicacion_el_fallo_no_borra_el_intento_de_un_inicio_correcto_previo` | 1 | Un fallo posterior conserva el intento exitoso: el historial solo se anexa | `sesiones` |
| `CA-2` | `test_tkt006_ca02_aplicacion_inicio_correcto_devuelve_al_usuario_autenticado` | 1 | Con el reloj adelantado 7 minutos: `UsuarioAutenticado` con `usuario_id`, `nombre`, `email`, `roles` (`frozenset`), `sesion_id` UUID versión 4, `expira_en` = ahora + 12 h y `expira_por_inactividad_en` = ahora + 30 min | `contexto` |
| `CA-2` | `..._aplicacion_inicio_correcto_escribe_la_sesion` | 1 | Una sola fila en `sesion` con el id devuelto, `creada_en` = `ultima_actividad` = ahora, `expira_en`, `revocada_en` nulo, `origen_ip` y `agente_usuario` | `sesiones` |
| `CA-2` | `..._aplicacion_inicio_correcto_asienta_el_intento_y_el_ultimo_acceso` | 1 | `intento_acceso` con `exitoso` verdadero, el usuario, el correo y la hora; `usuario.ultimo_acceso` pasa de nulo a ahora | `sesiones` |
| `CA-2` | `..._aplicacion_correo_sin_distinguir_mayusculas` | 1 | «Ana@Cimenta.TEST» abre la sesión del mismo usuario; el intento conserva el correo tal como se escribió; el origen y el agente nulos se guardan nulos | `sesiones` |
| `CA-8` | `test_tkt006_ca08_aplicacion_las_caducidades_salen_de_la_configuracion` | 1 | Con 90 y 10 minutos configurados, `expira_en` y la inactividad los respetan, en el resultado y en la fila | `sesiones` |
| `CA-2` | `..._aplicacion_dos_inicios_abren_dos_sesiones_distintas` | 1 | Cada inicio genera su propio identificador: dos filas con ids distintos | `sesiones` |
| `CA-R4` | `test_tkt006_car4_aplicacion_construir_contexto_no_pide_el_motor_hasta_usarlo` (sin Docker) | 1 | El proveedor de motor no se llama al construir; se llama una vez al usar la fábrica, y la misma fábrica se devuelve siempre (`functools.cache`) con el motor como `bind` | `contexto` |
| `CA-8` | `..._aplicacion_construir_contexto_toma_configuracion_reloj_y_contrasenas` (sin Docker) | 1 | El contexto lleva la configuración del entorno, el reloj dado y un hash de descarte ya calculado con los costes del entorno (`$argon2id$v=19$m=8192,t=1,p=1$`) | `contexto` |
| `CA-8` | `..._aplicacion_construir_contexto_sin_reloj_usa_el_del_sistema` (sin Docker) | 1 | Con `reloj=None` el contexto usa `reloj_del_sistema`, que devuelve la hora con zona | `contexto` |
| `CA-R4` | `test_tkt006_car4_aplicacion_usuario_autenticado_es_inmutable` y `..._contexto_de_identidad_es_inmutable` (sin Docker) | 2 | Los dos son `dataclass(frozen=True, slots=True)` con los campos del diseño en su orden | `contexto` |

**Casos que nacen en verde.** Ninguno.

**Casos añadidos más allá de la tabla del diseño, con su motivo.** `..._el_hash_de_descarte_no_es_el_de_ningun_usuario` (el diseño solo dice «contra `hash_de_descarte`»; con una sola cuenta, un mutante que verifique siempre contra un hash fijo pasaría), `..._los_tres_rechazos_son_indistinguibles` (`CA-3` esc. 2 y `CA-4` piden «indistinguible»), `..._cada_intento_fallido_deja_su_fila` y `..._el_fallo_no_borra_el_intento_de_un_inicio_correcto_previo` (`RNF-04` cuenta filas; con un solo fallo en una base limpia, un `DELETE` previo o un `ON CONFLICT` pasarían), los tres casos de `construir_contexto` y los dos de inmutabilidad (el diseño fija el literal de `contexto.py`, y TC-75 de la fila 7 solo lo ejerce por HTTP).

**Comprobación del oráculo, fuera del repositorio.** Se copió el árbol a la carpeta temporal de la sesión y se escribieron allí `contexto.py` y `sesiones.py` (solo `abrir_sesion` y los cuatro mensajes) con el código literal del diseño (ese código **no** está en el repositorio): los 25 casos pasaron, con Docker y el rol de aplicación. Después se aplicaron veintidós mutantes a esa copia, de uno en uno, y cada uno puso en rojo al menos un caso:

| Mutante (sobre la copia) | Cae |
|---|---|
| MT-5: sin credencial no se verifica (`coincide = False`) | `..._verifica_un_hash_siempre[correo_inexistente]` y `..._el_hash_de_descarte_no_es_el_de_ningun_usuario` |
| MT-7: `raise` dentro del bloque `begin()` | los 3 de `..._el_intento_fallido_sobrevive`, `..._cada_intento_fallido_deja_su_fila` y `..._el_fallo_no_borra_el_intento...` (5) |
| verifica dos veces cuando hay credencial | `..._verifica_un_hash_siempre[contrasena_erronea]`, `[usuario_desactivado]` e `..._inicio_correcto_verifica_un_hash` (3) |
| verifica siempre contra el hash de descarte | 10 casos, entre ellos los de TC-26 y todos los de inicio correcto |
| deriva un hash en cada intento | los 3 de `..._verifica_un_hash_siempre` e `..._inicio_correcto_verifica_un_hash` (4) |
| ignora `activo` | `[usuario_desactivado]` de TC-26, de contrato y de supervivencia, e `..._indistinguibles` (4) |
| sin `marcar_ultimo_acceso` | `..._inicio_correcto_asienta_el_intento_y_el_ultimo_acceso` |
| `intento_acceso.email` en minúsculas | `..._correo_sin_distinguir_mayusculas` |
| sin `normalizar_correo` | `..._correo_sin_distinguir_mayusculas` |
| `expira_en` con la caducidad por inactividad | `..._devuelve_al_usuario_autenticado`, `..._escribe_la_sesion` y `..._las_caducidades_salen_de_la_configuracion` |
| la inactividad con la caducidad absoluta | `..._devuelve_al_usuario_autenticado` y `..._las_caducidades_salen_de_la_configuracion` |
| `usuario_id` nulo en el intento | 4 (`[contrasena_erronea]` y `[usuario_desactivado]` de TC-27, `..._cada_intento_fallido_deja_su_fila`, `..._asienta_el_intento...`) |
| mensaje distinto cuando no hay cuenta | `..._rechazo_con_contrato...[correo_inexistente]` e `..._indistinguibles` |
| motivo `SIN_SESION` en vez de `CREDENCIALES_INVALIDAS` | los 3 de contrato e `..._indistinguibles` (4) |
| la hora de `datetime.now` en lugar de `contexto.reloj()` | 7 |
| `roles` vacíos en el resultado | `..._devuelve_al_usuario_autenticado` |
| `fabrica` sin `functools.cache` | `..._construir_contexto_no_pide_el_motor_hasta_usarlo` |
| `construir_contexto` pide el motor al construir | el mismo |
| `ContrasenasArgon2` sin la configuración del entorno | `..._construir_contexto_toma_configuracion_reloj_y_contrasenas` |
| el reloj dado se ignora | el mismo |
| `ContextoIdentidad` sin `frozen=True` | `..._contexto_de_identidad_es_inmutable` (la primera versión del test no lo detectaba; ver la nota de debajo) |
| `UsuarioAutenticado` sin `frozen=True` | `..._usuario_autenticado_es_inmutable` |

Un primer intento de la prueba de inmutabilidad de `ContextoIdentidad` solo comparaba los campos y dejaba pasar el mutante sin `frozen`: se dividió en dos casos y el del contexto ahora construye uno real y comprueba la asignación. La mutación oficial sobre el código real se hace en la fila 9.

**Ruff y mypy.** `uv run ruff check` y `uv run ruff format --check` sobre el archivo pasan. `uv run mypy tests/test_tkt006_inicio_sesion.py` da solo dos `import-not-found`, uno por cada módulo ausente (`cimenta.identidad.aplicacion.contexto` y `cimenta.identidad.aplicacion.sesiones`), que desaparecen con el verde de la fila. `mypy` informa de cada módulo ausente una sola vez aunque se importe en varios cuerpos. No hay ningún otro error.

**Nombres que el diseño fija y los tests dan por sentados.** `abrir_sesion(contexto, *, correo_escrito, contrasena, origen_ip, agente_usuario)`; `UsuarioAutenticado` con los siete campos del diseño, en ese orden (el caso de inmutabilidad lo comprueba); `ContextoIdentidad` con `fabrica_sesiones`, `configuracion`, `contrasenas` y `reloj`, en ese orden; `construir_contexto(*, proveedor_motor, reloj, entorno)`; `MENSAJE_CREDENCIALES_INVALIDAS`. Que `contexto.fabrica_sesiones()` devuelva un `sessionmaker` cuyo `kw["bind"]` es el motor es lo que el diseño escribe literalmente (`sessionmaker(bind=proveedor_motor(), ...)`).

**Verde** — ver «Fila 5 · verde y refactor» más abajo.

**Tests devueltos al tester:** ninguno.

#### Fila 5 · verde y refactor

**Verde.** Se escribieron dos archivos de producción con el código literal de «Capas afectadas · Aplicación» del diseño, sin tocar `test_tkt006_inicio_sesion.py` ni `conftest.py`:

- `backend/cimenta/identidad/aplicacion/contexto.py`: el protocolo `Contrasenas`, `UsuarioAutenticado` (`dataclass(frozen=True, slots=True)` con sus siete campos, en orden), `ContextoIdentidad` (la misma forma, con `fabrica_sesiones`, `configuracion`, `contrasenas` y `reloj`) y `construir_contexto`. La fábrica es perezosa: un `functools.cache` llama a `proveedor_motor()` solo en el primer uso. El hash de descarte lo calcula `ContrasenasArgon2` al construirse, no en el primer intento.
- `backend/cimenta/identidad/aplicacion/sesiones.py`: solo `abrir_sesion` y `MENSAJE_CREDENCIALES_INVALIDAS`. `validar_sesion` y `cerrar_sesion_vigente` no están (fila 6). La función verifica exactamente un hash: el del usuario, o `hash_de_descarte` si el correo normalizado no existe, y también cuando el usuario está desactivado. El resultado se calcula dentro de `fabrica_sesiones().begin()`: se busca la credencial con `normalizar_correo`, se decide con `credenciales_aceptadas`, se inserta `intento_acceso` con el correo tal como se escribió, y en el éxito se insertan la fila de `sesion` y `ultimo_acceso`. El `SesionInvalida(motivo="CREDENCIALES_INVALIDAS", ...)` se lanza **fuera** del bloque, para que el intento se confirme antes del rechazo (TC-27).

**Desviaciones respecto al diseño.** Son solo de forma:

1. `if credencial else` del diseño pasa a `if credencial is not None else` en el hash a verificar. Es equivalente: `Credencial` no define truthiness, así que siempre es verdadera cuando existe. Se hizo por claridad y por coherencia con el resto de la función.
2. `ruff check --fix` reordenó el bloque de importaciones de `sesiones.py` (`contrato_error` pasa después de `cimenta.*`, orden de isort). `ruff format` partió dos líneas largas (la del hash a verificar y la del `raise`). No cambia comportamiento.

**Ajustes de forma que el diseño no fija.** Ninguno más. No hay `TODO`, ni `print`, ni `passlib`/`hashlib` en los módulos nuevos, ni `float` en las firmas.

Comandos desde `backend/` con `PYTHONUTF8=1`, con la salida real:

`uv run pytest tests/test_tkt006_inicio_sesion.py -k "aplicacion"` (con Docker):

```
.........................                                                [100%]
25 passed in 5.03s
```

`uv run pytest tests/test_tkt006_configuracion.py tests/test_tkt006_dominio.py tests/test_tkt006_repositorio.py` (con Docker en el repositorio):

```
......................                                                   [100%]
94 passed in 4.63s
```

`uv run mypy .`: `Found 3 errors in 1 file (checked 141 source files)`. Los tres son los `call-arg` de `tests/conftest.py:494` (`Unexpected keyword argument` para `motor`, `reloj` y `entorno` en `crear_aplicacion`). Son el rojo esperado de la fila 7. No hay ningún error en los archivos de `cimenta/identidad/`.

`uv run ruff check .`: en la primera pasada marcó un `I001` (orden de importaciones) en `sesiones.py`; se corrigió con `ruff check --fix` sobre ese archivo. Después: `All checks passed!`.

`uv run ruff format --check .`: en la primera pasada `1 file would be reformatted` (`sesiones.py`); se aplicó `ruff format` a los dos archivos nuevos. Después: `141 files already formatted`.

`uv run python -m herramientas.verificar_float`: `verificar_float: archivos revisados: 18; hallazgos: 0`.

`uv run lint-imports`: `Contracts: 15 kept, 0 broken.` Se repitió tras los ajustes de formato.

**Refactor.** Solo los cambios de forma listados arriba. El código sigue el diseño y no se añadieron abstracciones.

**Mutación.** No se ejecutó sobre el código real en esta fila. Los 22 mutantes de la fila 5 de rojo se aplicaron sobre una copia fuera del repositorio. La mutación oficial sobre el código real corresponde a la fila 9.

**Tests devueltos al tester:** ninguno. Ningún test se consideró equivocado.

**Evidencia de ejecución al cerrar:** pendiente de la revisión de la fila 6 y de la fila 7 (HTTP). Los 25 casos de `-k "aplicacion"` están en verde, como exige la fila.

#### Fila 6 · rojo

Se escribió `backend/tests/test_tkt006_sesion_vigente.py` (con Docker) con TC-41 y los casos de **nivel de aplicación** de `validar_sesion` y `cerrar_sesion_vigente` que cubren `CA-6` a `CA-11`: 24 casos recolectados, **los 24 caen y ninguno nace en verde**. No se creó ni se tocó ningún archivo de producción ni `conftest.py`: `backend/cimenta/identidad/aplicacion/sesiones.py` sigue con solo `abrir_sesion` y `MENSAJE_CREDENCIALES_INVALIDAS`. El diseño asigna el cierre por HTTP (TC-43 a TC-46) a `test_tkt006_cierre.py`, que es de la fila 7 y no se escribió; el cierre a nivel de aplicación no tiene TC propio, así que vive en este archivo por indicación de la orden de trabajo. Los casos HTTP de TC-32 a TC-40 también son de la fila 7 y no se escribieron.

**Convención de nombres, para que cada fila seleccione lo suyo.** Los casos de nivel de aplicación llevan `aplicacion` en el nombre. La palabra `concurrencia` aparece **solo** en los tres casos con dos transacciones, porque `-k "concurrencia"` es la verificación de la fila 6 (tres ejecuciones seguidas). Ningún caso HTTP de la fila 7 debe llevar ninguna de las dos palabras. El archivo se abre con un docstring que lo dice.

**Contrato de error comprobado completo.** Cada rechazo pasa por `exigir_contrato_de_sesion`: la excepción es `SesionInvalida` con `tipo` `SESION` y `estado_http` `401`; su `motivo` es el esperado; su `mensaje` es el literal del diseño y es igual a la constante (`MENSAJE_SIN_SESION`, `MENSAJE_SESION_CADUCADA` o `MENSAJE_SESION_REVOCADA`); y `cuerpo(frozenset(), correlacion)` tiene exactamente las claves `tipo`, `mensaje`, `motivo` y `correlacion_id`, sin `detail` ni `acciones`. Lo que se verifica en la base se lee con una conexión **nueva** del rol de aplicación.

**Importaciones.** `validar_sesion` y `cerrar_sesion_vigente` (y las tres constantes de mensaje, que se leen con `getattr` sobre el módulo) se importan **dentro** de las ayudas `validar`, `cerrar` y `exigir_contrato_de_sesion` y de los tres casos de concurrencia, nunca arriba ni en una *fixture*. Cada caso falla por sí solo con el `ImportError` y la recolección no se cae. En los tres de concurrencia el `import` es la primera línea del cuerpo, antes de tomar ningún bloqueo.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_sesion_vigente.py --tb=line` (salida abreviada: se omiten las 24 líneas de traza con ruta absoluta, que repiten el mismo error, y la cabecera de plataforma).

```
============================= test session starts =============================
collected 24 items

tests\test_tkt006_sesion_vigente.py FFFFFFFFFFFFFFFFFFFFFFFF             [100%]

================================== FAILURES ===================================
E   ImportError: cannot import name 'validar_sesion' from 'cimenta.identidad.aplicacion.sesiones' (...\backend\cimenta\identidad\aplicacion\sesiones.py)
...  (16 casos fallan así: 15 por la ayuda `validar` en la línea 124 y TC-41 por su propio `import` en la 790)
E   ImportError: cannot import name 'cerrar_sesion_vigente' from 'cimenta.identidad.aplicacion.sesiones' (...\backend\cimenta\identidad\aplicacion\sesiones.py)
...  (8 casos fallan así: 6 por la ayuda `cerrar` en la línea 130 y los otros dos de concurrencia por su propio `import`, en la 840 y la 888)
=========================== short test summary info ===========================
FAILED tests/test_tkt006_sesion_vigente.py::test_tkt006_ca06_aplicacion_validar_devuelve_usuario_y_roles_actuales
... (21 líneas FAILED más; la lista completa está en «Casos»)
FAILED tests/test_tkt006_sesion_vigente.py::test_tkt006_ca06_concurrencia_cierre_y_peticion_simultanea
FAILED tests/test_tkt006_sesion_vigente.py::test_tkt006_ca09_concurrencia_dos_cierres_no_pisan_revocada_en
FAILED tests/test_tkt006_sesion_vigente.py::test_tkt006_ca09_concurrencia_el_cierre_no_pisa_la_actividad_de_una_peticion_en_curso
============================= 24 failed in 15.19s =============================
```

**Razón de cada fallo.** Todos son el `ImportError` esperado de `cimenta.identidad.aplicacion.sesiones`: la primera vez que un caso necesita `validar_sesion` o `cerrar_sesion_vigente`, que todavía no existen. Antes de ese punto cada caso **sí** ejecuta código real: siembra al usuario con `sembrar_usuario`, construye el `ContextoIdentidad` y abre la sesión con `abrir_sesion` (verde desde la fila 5), así que el rojo no viene del entorno, de Docker, de las *fixtures* ni de la sintaxis. Los tres de concurrencia caen en el `import` previo a cualquier bloqueo, así que ni dejan una transacción abierta ni esperan el plazo de 10 s. Un `mypy` del archivo da solo cinco `attr-defined` (los símbolos que faltan, uno por cada importación) y desaparecen con el verde.

**Casos.**

| Test | Casos | Qué afirma | Criterio | Cae por |
|---|---|---|---|---|
| `test_tkt006_ca06_aplicacion_validar_devuelve_usuario_y_roles_actuales` | 1 | Cinco minutos después de abrir: `UsuarioAutenticado` con el mismo usuario y sesión, nombre, correo, los dos roles como `frozenset`, `expira_en` sin cambio y `expira_por_inactividad_en` = ahora + 30 min | `CA-6` esc. 1 (TC-32 en HTTP) | `validar_sesion` |
| `..._ca06_aplicacion_validar_desliza_solo_la_ultima_actividad` | 1 | Con una conexión nueva: `ultima_actividad` = ahora; `creada_en`, `expira_en`, `revocada_en`, origen, agente y `usuario.ultimo_acceso` intactos; una sola fila | `CA-6` esc. 1, ADR-014 | `validar_sesion` |
| `..._ca06_aplicacion_validar_toca_solo_su_sesion` | 1 | Validar la sesión de Ana no mueve la de Luis ni otra sesión de Ana | `CA-6` esc. 1 | `validar_sesion` |
| `..._ca06_aplicacion_validar_usuario_sin_roles_devuelve_conjunto_vacio` | 1 | Un usuario sin roles tiene sesión vigente y `roles == frozenset()` | `CA-6`, M7 | `validar_sesion` |
| `..._ca07_aplicacion_validar_sesion_inexistente_es_sin_sesion` | 1 | UUID inexistente → `SIN_SESION` con el contrato completo; sin asientos en `bitacora`, sin filas nuevas en `intento_acceso`, la sesión real conserva su actividad | `CA-7` esc. 1 y 2 | `validar_sesion` |
| `..._ca08_aplicacion_validar_caduca_al_llegar_expira_en` | 1 | Con caducidad de 60 min e inactividad de 1,000 min (para aislar la absoluta): a `expira_en` − 1 s vigente; a `expira_en` exacto `SESION_CADUCADA`; la fila no se borra, `revocada_en` nulo, `ultima_actividad` no se desliza | `CA-8` esc. 1 (TC-36) | `validar_sesion` |
| `..._ca08_aplicacion_validar_caduca_por_inactividad` | 3 (30 min, 31 min, 3 h) | `SESION_CADUCADA` con `expira_en` lejos; la fila no se borra; `ultima_actividad` intacta | `CA-8` esc. 2 (TC-37) | `validar_sesion` |
| `..._ca08_aplicacion_validar_un_segundo_antes_del_limite_de_inactividad_sigue_vigente` | 1 | A 29 min 59 s sigue vigente y la inactividad se renueva a ahora + 30 min | `CA-8` esc. 2 (borde) | `validar_sesion` |
| `..._ca08_aplicacion_la_actividad_desliza_la_inactividad_y_no_la_absoluta` | 1 | Peticiones cada 25 min, al menos 28, todas vigentes con la misma `expira_en`; al llegar `expira_en` caduca aunque la última petición fuera 20 min antes; `ultima_actividad` es la de la última petición vigente | `CA-8` esc. 3 (TC-38) | `validar_sesion` |
| `..._ca08_aplicacion_validar_usa_la_inactividad_de_la_configuracion` | 1 | Con 10 min configurados, a 9:59 vigente y a 10:00 caducada | `CA-8` esc. 4, `PA-T2` | `validar_sesion` |
| `..._ca09_aplicacion_cerrar_revoca_sin_borrar` | 1 | `revocada_en` = hora del reloj; toda la fila restante intacta; una sola fila | `CA-9` esc. 1 y 4 (TC-43) | `cerrar_sesion_vigente` |
| `..._ca09_aplicacion_la_sesion_cerrada_ya_no_sirve` | 1 | Tras cerrar, `SESION_REVOCADA` con el contrato completo; `revocada_en` no se pisa y la actividad no se desliza | `CA-9` esc. 2 (TC-44) | `cerrar_sesion_vigente` |
| `..._ca09_aplicacion_cerrar_dos_veces_no_pisa_revocada_en` | 1 | El segundo cierre no lanza y deja la hora del primero | `CA-9`, ADR-014 | `cerrar_sesion_vigente` |
| `..._ca09_aplicacion_cerrar_una_sesion_inexistente_no_hace_nada` | 1 | No lanza, no crea filas y la sesión real queda idéntica | `CA-9` esc. 3 | `cerrar_sesion_vigente` |
| `..._ca09_aplicacion_cerrar_toca_solo_su_sesion` | 1 | Las otras sesiones (de Ana y de Luis) siguen sin revocar y vigentes | `CA-9` | `cerrar_sesion_vigente` |
| `..._ca09_aplicacion_revocada_prevalece_sobre_caducada` | 1 | Revocada y caducada → `SESION_REVOCADA` | `CA-9` esc. 2 | `cerrar_sesion_vigente` |
| `..._ca10_aplicacion_desactivar_surte_efecto_en_la_peticion_siguiente` | 1 | Con `usuario.activo` en falso → `SESION_REVOCADA` en la siguiente; la fila no se borra, no se desliza la actividad y `revocada_en` sigue nulo | `CA-10` (TC-40) | `validar_sesion` |
| `..._ca10_aplicacion_desactivado_y_caducada_es_revocada` | 1 | Desactivado y caducada → `SESION_REVOCADA` (gana la desactivación) | `CA-10`, `PA-T3` | `validar_sesion` |
| `..._ca11_aplicacion_validar_lee_los_roles_en_cada_peticion` | 1 | Con el mismo contexto y la misma sesión: dos roles; retirado `COMPRAS`, uno; concedido `ALMACEN`, dos | `CA-11`, M6, MT-10 | `validar_sesion` |
| `test_tkt006_ca06_concurrencia_cierre_y_peticion_simultanea` | 1 | **TC-41.** Ver abajo | `CA-6`, `CA-9`, objeción 5 de la spec | `validar_sesion` |
| `..._ca09_concurrencia_dos_cierres_no_pisan_revocada_en` | 1 | Dos cierres simultáneos: el segundo espera, no lanza y conserva la hora del primero | `CA-9`, ADR-014 | `cerrar_sesion_vigente` |
| `..._ca09_concurrencia_el_cierre_no_pisa_la_actividad_de_una_peticion_en_curso` | 1 | Un cierre y un deslizamiento de actividad simultáneos tocan columnas distintas: quedan las dos escrituras | `CA-6`, `CA-9`, ADR-014 | `cerrar_sesion_vigente` |

**TC-41 y sus dos hermanos, con dos transacciones reales.** La conexión A es de `psycopg`, del rol de aplicación y sin `autocommit`; un hilo (`ThreadPoolExecutor` de un trabajador) llama al caso de uso con el contexto de la base de prueba. Un observador, tercera conexión del mismo rol, sondea `pg_stat_activity` filtrando por la base (`current_database()`), `wait_event_type = 'Lock'` y excluyendo los dos procesos propios; cada vuelta consulta y espera 20 ms con `threading.Event().wait`, **sin pausa fija** y con plazo de 10 s medido con `time.monotonic()`. Si el hilo termina antes de bloquearse, el caso falla con lo que devolvió o lanzó; si el plazo se agota, falla con un mensaje que lo dice. Todo termina en un `finally` que hace `rollback` de A y espera al hilo: un fallo no deja un bloqueo colgado. En el primero, A revoca con `revocada_en` = inicio + 2 min, sin confirmar; el hilo llama a `validar_sesion` con el reloj en inicio + 5 min; cuando el sondeo ve la espera, A confirma; el hilo debe terminar con `SesionInvalida` `SESION_REVOCADA` (contrato completo), la fila con `revocada_en` = la hora de A y `ultima_actividad` = la de inicio. En el segundo, el hilo es `cerrar_sesion_vigente` con otra hora de reloj y debe terminar sin excepción dejando la hora de A. En el tercero, A desliza `ultima_actividad` y el hilo cierra: quedan `revocada_en` = hora del cierre y `ultima_actividad` = la de A.

**Comprobación del oráculo, fuera del repositorio.** Se copió `backend/` a la carpeta temporal de la sesión (sin `.venv`) y se escribieron allí `validar_sesion`, `cerrar_sesion_vigente` y los tres mensajes con el código literal del diseño (ese código **no** está en el repositorio; `git status` solo añade el archivo de pruebas): los 24 casos pasaron, con Docker y el rol de aplicación (`24 passed in 6.82s`). `-k "concurrencia"` pasó **tres veces seguidas** (`3 passed, 21 deselected` en 2.76 s, 2.73 s y 2.82 s). Después se aplicaron 22 mutantes a esa copia, de uno en uno, con restauración del archivo tras cada uno, y cada uno puso en rojo al menos un caso:

| Mutante (sobre la copia) | Cae |
|---|---|
| MT-9: `tocar_sesion` sin `AND revocada_en IS NULL` | `..._concurrencia_cierre_y_peticion_simultanea` (el único; es TC-41) |
| `revocar_sesion` sin `AND revocada_en IS NULL` | `..._cerrar_dos_veces_no_pisa_revocada_en` y `..._concurrencia_dos_cierres_no_pisan_revocada_en` |
| `validar_sesion` ignora lo que devuelve `tocar_sesion` | `..._concurrencia_cierre_y_peticion_simultanea` (el único) |
| `validar_sesion` no desliza la actividad | 6, entre ellos TC-41 y `..._desliza_solo_la_ultima_actividad` |
| `validar_sesion` desliza aunque haya caducado | 6: los tres de inactividad, el de `expira_en`, el de sesión deslizante y el de desactivado |
| `roles_de` con caché | `..._ca11_aplicacion_validar_lee_los_roles_en_cada_peticion` (MT-10) |
| MT-1: el borde de `expira_en` deja de caducar | `..._validar_caduca_al_llegar_expira_en` y `..._la_actividad_desliza_...` |
| el borde de inactividad deja de caducar | `..._caduca_por_inactividad[paso0]` y `..._usa_la_inactividad_de_la_configuracion` |
| MT-2: sin comprobación de inactividad | 4 (los tres de inactividad y el de configuración) |
| MT-3: `evaluar_vigencia` sin `revocada` | `..._revocada_prevalece_sobre_caducada` |
| MT-4: `evaluar_vigencia` ignora `usuario_activo` | `..._desactivar_surte_efecto...` y `..._desactivado_y_caducada_es_revocada` |
| la inactividad usa la caducidad absoluta | 7 |
| `expira_por_inactividad_en` usa la absoluta | 4 |
| `cerrar_sesion_vigente` usa la hora del sistema en vez del reloj | 5 |
| `cerrar_sesion_vigente` no revoca | 7 |
| `revocar_sesion` sin filtrar por `id` | `..._cerrar_una_sesion_inexistente_no_hace_nada` y `..._cerrar_toca_solo_su_sesion` |
| `tocar_sesion` sin filtrar por `id` | 3 |
| sesión inexistente responde `SESION_REVOCADA` | `..._ca07_..._es_sin_sesion` |
| mensaje de caducada cambiado | 6 |
| la caducada se reporta como `SESION_REVOCADA` | 6 |
| `validar_sesion` devuelve roles vacíos | 2 |
| `validar_sesion` escribe `revocada_en` al rechazar al desactivado | `..._desactivar_surte_efecto...` |

Dos mutantes —MT-9 y el que ignora lo que devuelve `tocar_sesion`— caen **solo** en TC-41, como el diseño pretende: sin concurrencia real nadie los ve, porque en secuencia la guarda `revocada_en IS NULL` nunca se activa. La mutación oficial sobre el código real se hace en la fila 9.

**Casos que nacen en verde.** Ninguno.

**Ruff y mypy.** `uv run ruff check` y `uv run ruff format --check` sobre el archivo pasan. `uv run mypy tests/test_tkt006_sesion_vigente.py` da solo los cinco `attr-defined` de arriba.

**Nombres que el diseño fija y los tests dan por sentados.** `validar_sesion(contexto, sesion_id) -> UsuarioAutenticado`; `cerrar_sesion_vigente(contexto, sesion_id) -> None`; las constantes `MENSAJE_SIN_SESION`, `MENSAJE_SESION_CADUCADA` y `MENSAJE_SESION_REVOCADA` con los textos del diseño. El `SesionInvalida` se lanza **fuera** del bloque de la transacción. Un cierre sobre un identificador inexistente **no lanza** (la dependencia de la ruta es quien responde `SIN_SESION`), y rechazar a un usuario desactivado **no escribe** `revocada_en`: son lecturas literales del diseño, y la segunda está marcada `(asumido)` en `CA-10`.

**Verde** — ver «Fila 6 · verde y refactor» más abajo.

**Tests devueltos al tester:** ninguno.

#### Fila 6 · verde y refactor

**Verde.** Se añadieron a `backend/cimenta/identidad/aplicacion/sesiones.py` `validar_sesion` y `cerrar_sesion_vigente`, con el código literal de «Capas afectadas · Aplicación» del diseño, y las constantes `MENSAJE_SIN_SESION`, `MENSAJE_SESION_CADUCADA` y `MENSAJE_SESION_REVOCADA` con los textos exactos. `abrir_sesion` no se tocó. Cada petición lee de la base la sesión, el usuario y sus roles, sin caché, y evalúa con `evaluar_vigencia` del dominio. Si la sesión está vigente la desliza con `tocar_sesion`; si esa escritura no toca fila (cierre simultáneo), responde `SESION_REVOCADA` sin pisar nada. Un usuario desactivado da `SESION_REVOCADA` sin escribir `revocada_en`. `cerrar_sesion_vigente` revoca con `revocar_sesion`, no borra, no pisa un `revocada_en` previo y no lanza si el identificador no existe. Todos los rechazos son `SesionInvalida` de `contrato_error`, lanzados fuera del bloque de la transacción. Ningún test ni `conftest.py` se editó. Se añadió la importación de `EstadoSesion` y `evaluar_vigencia`.

Comandos desde `backend/` con `PYTHONUTF8=1`, con la salida real:

`uv run pytest tests/test_tkt006_sesion_vigente.py` (con Docker):

```
collected 24 items

tests\test_tkt006_sesion_vigente.py ........................             [100%]

============================= 24 passed in 8.30s ==============================
```

`uv run pytest tests/test_tkt006_sesion_vigente.py -k "concurrencia"`, tres veces seguidas:

```
== concurrencia 1
====================== 3 passed, 21 deselected in 2.79s =======================
== concurrencia 2
====================== 3 passed, 21 deselected in 2.73s =======================
== concurrencia 3
====================== 3 passed, 21 deselected in 2.82s =======================
```

Regresión: `uv run pytest tests/test_tkt006_inicio_sesion.py -k aplicacion` → `25 passed, 14 deselected in 5.13s` (el `-k` se aplicó también al filtrar el archivo de repositorio en la misma orden, así que este se corrió aparte) y `uv run pytest tests/test_tkt006_repositorio.py` → `14 passed in 4.06s`.

`uv run mypy .`: `Found 3 errors in 1 file (checked 142 source files)`. Son los tres `call-arg` de `tests/conftest.py:494` (`motor`, `reloj` y `entorno` en `crear_aplicacion`), el rojo esperado de la fila 7. No hay errores en `cimenta/identidad/`.

`uv run ruff check .`: `All checks passed!`. `uv run ruff format --check .`: `142 files already formatted`. `uv run python -m herramientas.verificar_float`: `verificar_float: archivos revisados: 18; hallazgos: 0`. `uv run lint-imports`: `Contracts: 15 kept, 0 broken.`

**Refactor.** Solo formato (`ruff format` partió la condición de `tocar_sesion` y las construcciones largas) y el docstring de cabecera del módulo, que ya no dice «fila 5». Sin cambio de comportamiento.

**Desviaciones respecto al diseño.** Solo de forma. Ningún test se consideró equivocado. La mutación sobre el código real queda para la fila 9.

**Tests devueltos al tester:** ninguno.

#### Fila 7 · rojo (tanda 1)

La tanda 1 escribe los casos HTTP de `csrf`, `inicio de sesión`, `sesión vigente` y `cierre`. La tanda 2 queda para el enrutador y la lista cerrada (TC-47 a TC-53) y la reescritura de TC-75 de TKT-005 (D-2). Ningún archivo de producción se creó ni se tocó: `backend/cimenta/identidad/api/` sigue con solo su `__init__.py` y `servidor/fabrica.py` conserva su firma anterior.

**Comprobación previa de la fila** (pedida por el diseño, ejecutada por el orquestador y repetida al abrir esta tanda), desde `backend/`:

```
$ uv run python -c "from fastapi.dependencies.models import Dependant; f = Dependant.__dataclass_fields__; print('dependencies' in f, 'call' in f)"
True True
```

Con FastAPI 0.159.1, `Dependant` expone `dependencies` y `call`: la fila no se detiene y la tanda 2 puede recorrer las dependencias de cada `APIRoute`.

**Archivos de pruebas de la tanda.**

| Archivo | Qué | Casos nuevos |
|---|---|---|
| `backend/tests/test_tkt006_csrf.py` (nuevo) | TC-50 y TC-51: emisión del token sin sesión, cookie sin `HttpOnly`, cuerpo igual a la cookie, tokens distintos, sin escritura en la base | 5 |
| `backend/tests/test_tkt006_cierre.py` (nuevo) | TC-43 a TC-46: 204 y fila no borrada, cookie expirada, sesión cerrada, cierre repetido, otras sesiones intactas, cierre sin sesión o con cookie inexistente o mal formada, sin `DELETE` sobre `sesion` | 10 (con 3 parametrizados) |
| `backend/tests/test_tkt006_inicio_sesion.py` (se añade al final; los 25 casos de aplicación no se tocaron) | TC-20 a TC-25, TC-27 (HTTP), TC-28 a TC-31 | 21 (con 3 y 7 parametrizados) |
| `backend/tests/test_tkt006_sesion_vigente.py` (se añade al final; los 24 casos existentes no se tocaron) | TC-32 a TC-40, el `SESION_REVOCADA` por revocación en la base y el rol retirado o concedido, por HTTP | 17 |

Los nombres de los casos HTTP no contienen `aplicacion` ni `concurrencia`: `-k "aplicacion"` sigue seleccionando exactamente los 25 casos de la fila 5 (`25/46 collected`) y `-k "concurrencia"`, los 3 de la fila 6. En los archivos de inicio y de sesión vigente solo se añadieron importaciones de arriba y un bloque nuevo al final; `ruff check --fix` reordenó además las importaciones locales de dos funciones existentes de `test_tkt006_inicio_sesion.py` (`crear_contexto` y `..._sin_reloj_usa_el_del_sistema`), sin cambiar su comportamiento.

**Cómo se afirma cada rechazo.** Todo `401` de sesión comprueba, a la vez, el código, `tipo` `SESION`, el `motivo`, el `mensaje` literal del diseño, el conjunto exacto de claves (`tipo`, `motivo`, `mensaje`, `correlacion_id`), la ausencia de `detail`, que `correlacion_id` sea igual a la cabecera `X-Correlacion-Id` y la validez contra `ErrorSesion` del borrador con la ayuda `validar_contra` de TKT-005 (copiada al archivo). El `422` hace lo mismo con `ErrorValidacion` y comprueba el campo y el `codigo` de cada error. Las cookies se interpretan con `http.cookies.SimpleCookie` y se exige exactamente un `Set-Cookie` por nombre. La base se lee con una conexión nueva del rol de aplicación. Una cookie que ya no está en el almacén del cliente se envía con la cabecera `Cookie`. Las rutas de prueba (`/api/v1/prueba/roles`) se añaden a la aplicación dentro del caso, con `Depends(sesion_vigente)` importado de `cimenta.identidad.api.dependencias` (la interfaz publicada llega en la fila 10). No se exige ningún token CSRF en `iniciar_sesion` ni en `cerrar_sesion`: es de TKT-057.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_csrf.py tests/test_tkt006_cierre.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_sesion_vigente.py --tb=line -q` (salida abreviada: las 51 líneas `ERROR at setup` repiten el mismo error y se condensan).

```
ERROR at setup of test_tkt006_ca01_token_csrf_sin_sesion
E   TypeError: crear_aplicacion() got an unexpected keyword argument 'motor'
...  (51 casos, todos con ese mismo error)
================================== FAILURES ===================================
test_tkt006_ca08_caducidad_absoluta
E   TypeError: crear_aplicacion() got an unexpected keyword argument 'motor'
tests\test_tkt006_sesion_vigente.py:1060: TypeError: crear_aplicacion() got an unexpected keyword argument 'motor'
test_tkt006_ca08_valores_de_la_configuracion
E   TypeError: crear_aplicacion() got an unexpected keyword argument 'motor'
=========================== short test summary info ===========================
ERROR tests/test_tkt006_csrf.py::test_tkt006_ca01_token_csrf_sin_sesion - TypeError ...
...  (5 de csrf, 10 de cierre, 21 de inicio_sesion y 15 de sesion_vigente)
FAILED tests/test_tkt006_sesion_vigente.py::test_tkt006_ca08_caducidad_absoluta
FAILED tests/test_tkt006_sesion_vigente.py::test_tkt006_ca08_valores_de_la_configuracion
2 failed, 49 passed, 51 errors in 14.04s
```

**Razón de cada fallo.** Es la prevista por la orden de trabajo: `crear_aplicacion` aún no acepta `motor`, `reloj` ni `entorno`. 51 casos caen con `ERROR at setup` porque la *fixture* `aplicacion_identidad` (y con ella `cliente`) lanza `TypeError: crear_aplicacion() got an unexpected keyword argument 'motor'`; los dos que usan la fábrica local `crear_cliente` (`ca08_caducidad_absoluta` y `ca08_valores_de_la_configuracion`, que necesitan otra configuración) llegan al cuerpo y caen con el mismo `TypeError` en `FAILED`. Es rojo por la firma pedida, no por sintaxis ni por entorno: todo se importa dentro de cada caso y la recolección no se cae. Los 49 que pasan son los 25 de aplicación de `inicio_sesion` y los 24 de `sesion_vigente` de las filas 5 y 6, sin cambios. Como `crear_aplicacion` ni siquiera arranca, este rojo todavía no ejerce las rutas; lo que sí demuestra el oráculo de abajo es que, con la firma y las rutas del diseño, los 53 casos nuevos pasan y los mutantes los ponen en rojo.

**Casos nuevos y criterio que cubre cada uno.**

| TC | Test | Tipo | Criterio |
|---|---|---|---|
| TC-50 | `test_tkt006_ca01_token_csrf_sin_sesion` y `..._el_token_lleva_correlacion_y_no_abre_sesion` | feliz | `CA-1` esc. 1 |
| (CA-1) | `test_tkt006_ca01_emitir_el_token_no_escribe_en_la_base` | **rechazo** de forma | `CA-1`, `M1` |
| TC-51 | `test_tkt006_ca01_dos_emisiones_consecutivas_dan_tokens_distintos` y `..._cien_emisiones_no_repiten_ningun_token` | **rechazo** | `CA-1` esc. 2 |
| TC-20 | `test_tkt006_ca02_inicio_correcto`, `..._escribe_sesion_intento_y_ultimo_acceso` y `..._la_respuesta_no_lleva_contrasena_ni_hash` | feliz y **rechazo** de forma | `CA-2` esc. 1, `RNF-03` |
| TC-21 | `test_tkt006_ca02_atributos_de_la_cookie_de_sesion` | feliz | `CA-2` esc. 1, `RNF-02` |
| TC-22 | `test_tkt006_ca02_correo_sin_distinguir_mayusculas` | feliz | `CA-2` esc. 2 |
| TC-23 | `test_tkt006_ca02_la_cookie_es_opaca` | **rechazo** de forma | `CA-2` esc. 3, regla 9 |
| TC-24 | `test_tkt006_ca03_contrasena_equivocada` | **rechazo** | `CA-3` esc. 1, `CA-R5` |
| TC-25 | `test_tkt006_ca03_correo_inexistente_indistinguible` | **rechazo** | `CA-3` esc. 2 |
| TC-27 (HTTP) | `test_tkt006_ca03_el_intento_fallido_sobrevive_al_401` (3 escenarios) | **rechazo** | `CA-3` esc. 4, `RNF-04` |
| TC-28 | `test_tkt006_ca04_usuario_desactivado_no_inicia` | **rechazo** | `CA-4`, `PA-T4` |
| TC-29 | `test_tkt006_ca05_forma_invalida` (7 casos) | **rechazo** | `CA-5`, `PA-T5` |
| TC-30 | `test_tkt006_ca15_la_contrasena_no_viaja` | **rechazo** | `CA-15` esc. 3 |
| TC-31 | `test_tkt006_ca12_denegaciones_anonimas_fuera_de_la_bitacora` | **rechazo** | `CA-12` esc. 3, `RNF-13` |
| TC-32 | `test_tkt006_ca06_sesion_vigente_devuelve_usuario_y_roles`, `..._la_peticion_desliza_ultima_actividad_y_nada_mas` y `..._sesion_vigente_de_un_usuario_sin_roles` | feliz | `CA-6` esc. 1 |
| TC-33 | `test_tkt006_ca06_roles_de_quien_llama` y `test_tkt006_ca07_la_ruta_con_sesion_vigente_no_se_ejecuta_sin_cookie` | feliz y **rechazo** | `CA-6` esc. 1, `M7` |
| TC-34 | `test_tkt006_ca07_peticion_sin_cookie` | **rechazo** | `CA-7` esc. 1, `CA-R5` |
| TC-35 | `test_tkt006_ca07_cookie_inexistente_o_mal_formada` | **rechazo** | `CA-7` esc. 2 y 3 |
| TC-36 | `test_tkt006_ca08_caducidad_absoluta` | **rechazo** | `CA-8` esc. 1 |
| TC-37 | `test_tkt006_ca08_caducidad_por_inactividad` y `..._un_segundo_antes_del_limite_de_inactividad_sigue_vigente` | **rechazo** | `CA-8` esc. 2 |
| TC-38 | `test_tkt006_ca08_la_actividad_desliza_la_inactividad_y_no_la_absoluta` | **rechazo** | `CA-8` esc. 3 |
| TC-39 | `test_tkt006_ca08_valores_de_la_configuracion` | feliz | `CA-8` esc. 4 |
| TC-40 | `test_tkt006_ca10_desactivar_surte_efecto_en_la_peticion_siguiente` y `..._desactivado_y_caducada_es_revocada` | **rechazo** | `CA-10`, `M6` |
| (CA-9) | `test_tkt006_ca09_una_sesion_revocada_en_la_base_responde_revocada` y `..._revocada_prevalece_sobre_caducada_por_http` | **rechazo** | `CA-9` esc. 2 |
| (CA-11) | `test_tkt006_ca11_retirar_un_rol_se_ve_en_la_peticion_siguiente` | **rechazo** | `CA-11`, `M6`, `M7` |
| TC-43 | `test_tkt006_ca09_cerrar_revoca_sin_borrar`, `..._cerrar_expira_la_cookie_de_sesion` y `..._cerrar_una_sesion_no_revoca_las_demas` | feliz | `CA-9` esc. 1, `M4` |
| TC-44 | `test_tkt006_ca09_la_sesion_cerrada_ya_no_sirve` y `..._cerrar_dos_veces_la_segunda_es_revocada` | **rechazo** | `CA-9` esc. 2 |
| TC-45 | `test_tkt006_ca09_cerrar_sin_sesion` y `..._cerrar_con_una_cookie_que_no_corresponde_a_nada` (3 casos) | **rechazo** | `CA-9` esc. 3, `CA-7` esc. 2 |
| TC-46 | `test_tkt006_ca09_sin_delete_sobre_sesion` | **rechazo** | `CA-9` esc. 4, `CA-R1` |

**Casos que nacen en verde.** Ninguno entre los nuevos.

**Comprobación del oráculo, fuera del repositorio.** Se copió `backend/` (sin `.venv`), `docs/api/openapi.yaml` y `compose.yaml` a la carpeta temporal de la sesión y se escribieron allí `api/esquemas.py`, `api/dependencias.py`, `api/rutas.py`, `api/montaje.py` y el cambio de `servidor/fabrica.py` con el código literal del diseño (ese código **no** está en el repositorio). Con Docker y el rol de aplicación, los 102 casos de los cuatro archivos pasaron (`102 passed in 19.99s`) **después de un cambio**, descrito en la ambigüedad 1. Sobre esa copia se aplicaron 12 mutantes, de uno en uno y con restauración; cada uno puso en rojo al menos un caso HTTP: cookie de sesión con `httponly=False` (cae `ca02_atributos_de_la_cookie_de_sesion`), cookie CSRF con `HttpOnly` (`ca01_token_csrf_sin_sesion`), token CSRF de 11 caracteres (el mismo), cookie CSRF sin `Secure` (el mismo), cierre sin `delete_cookie` (`ca09_cerrar_expira_la_cookie_de_sesion`), `delete_cookie` sin `HttpOnly` (el mismo), MT-22 sin fijar `roles_de_quien_llama` (`ca06_roles_de_quien_llama`), MT-20 con un UUID mal formado que responde `SESION_REVOCADA` (`ca09_cerrar_sin_sesion`), roles sin ordenar (`ca06_sesion_vigente_devuelve_usuario_y_roles`), MT-1 con el borde de `expira_en` invertido (`ca08_caducidad_absoluta`, que por eso usa la inactividad configurada a 1,000 minutos), sin registrar el agente de usuario (`ca02_inicio_correcto_escribe_sesion_intento_y_ultimo_acceso`) y guardar el correo normalizado en `intento_acceso` (`ca02_correo_sin_distinguir_mayusculas`). La mutación oficial sobre el código real se hace en la fila 9.

**Ruff y mypy.** `uv run ruff check .` y `uv run ruff format --check .` pasan (`All checks passed!`; `144 files already formatted`). `uv run mypy` sobre los cuatro archivos solo reporta lo que falta de producción: la importación de `cimenta.identidad.api.dependencias` y los tres `call-arg` de `crear_aplicacion` (`motor`, `reloj`, `entorno`), que se resuelven con el verde de la fila.

**Ambigüedades y decisiones que el diseño no cubre.**

1. **`forma_de_correo` del diseño rechaza `ana@cimenta.test`.** `pydantic.networks.validate_email` delega en `email_validator`, que trata `.test` como dominio de uso especial y lanza «The part after the @-sign is a special-use or reserved name». Con la función literal del diseño, el correo de la spec (`CA-2`, `ana@cimenta.test`) saldría `422 FORMATO` y los 40 casos que inician sesión por HTTP caerían. Se comprobó con `validate_email("ana@cimenta.test")` (error) frente a `ana@cimenta.com` y `ana@cimenta.example` (válidos). Los tests **no se cambian**: la spec y los 25 casos de aplicación usan `ana@cimenta.test`. Para el oráculo se sustituyó la llamada por `email_validator.validate_email(valor, check_deliverability=False, test_environment=True)`, con lo que pasan los 102. Corresponde al orquestador decidir cómo se resuelve en el verde (`email_validator` es solo dependencia transitiva de `fastapi[standard-no-fastapi-cloud-cli]`) o si se cambia el dominio de los correos de prueba y de la spec.
2. **`agente_usuario` y `origen_ip` por HTTP.** Los casos esperan `origen_ip == "testclient"` (el host que `TestClient` pone en `request.client`) y `agente_usuario` igual a la cabecera `User-Agent` enviada (`Prueba/1.0`), como dice el diseño (`request.client.host` y `request.headers.get("user-agent")`).
3. **Atributos de la cookie de sesión.** No se afirma la ausencia de `Max-Age` ni de `expires` en el inicio (el diseño la marca `(asumido)`) ni la ausencia de `Domain`; solo `HttpOnly`, `Secure`, `SameSite=Lax` y `Path=/`.
4. **Rutas de prueba.** `/api/v1/prueba/roles` se registra con `aplicacion.include_router(...)` sobre la aplicación ya construida y declara la dependencia en el decorador (`dependencies=[Depends(sesion_vigente)]`), para no anotar el parámetro con un tipo que aún no existe; es del código de la prueba, no de producción.
5. **Finales de línea.** Los archivos de prueba de la tanda están, como los de las filas anteriores, con CRLF en el árbol de trabajo (Windows, `core.autocrlf=true`); `.gitattributes` (`* text=auto eol=lf`) los normaliza al confirmar. `test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf` solo recorre los archivos de TKT-005.

**Verde** — ver «Fila 7 · verde y refactor» más abajo.

**Tests devueltos al tester:** ninguno.

#### Fila 7 · rojo (tanda 2)

La tanda 2 escribe el test del enrutador y de la lista cerrada (TC-47 a TC-53), reescribe TC-75 de TKT-005 según la decisión D-2 y añade el caso de arranque de `fastapi dev` sin variables de base. Ningún archivo de producción se creó ni se tocó: `backend/cimenta/identidad/api/` sigue con solo su `__init__.py` y `servidor/fabrica.py` conserva su firma anterior. Todo corre sin Docker.

**Archivos de pruebas de la tanda.**

| Archivo | Qué | Casos |
|---|---|---|
| `backend/tests/test_tkt006_enrutador.py` (nuevo) | TC-47 a TC-53 con sus complementos: recorrido de la aplicación real, lista cerrada, token CSRF sin base, contrato de seguridad y rutas síncronas | 16 recolectados |
| `backend/tests/test_servidor_arranque.py` (editado) | TC-75 reescrito (D-2) y `test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad` (nuevo) | 2 afectados de 9 |

**Ayudas del archivo del enrutador** (las del diseño, más una). `rutas_de` y `corrutinas_registradas` son las de `test_servidor_arranque.py`, copiadas como hace `test_tkt007_consulta.py`. `llamadas(dependant)` recorre `dependant.dependencies` de forma recursiva y devuelve cada `.call`. `rutas_sin_sesion(aplicacion)` devuelve el «MÉTODO ruta» de cada `APIRoute` cuya cadena de llamadas no contiene `sesion_vigente`; compara por identidad (`is`) con la función real de `cimenta.identidad.api.dependencias`, no por nombre. `violaciones(aplicacion, lista_cerrada)` devuelve `sin proteger: …`, `en la lista pero protegida o inexistente: …` y, añadida por la tanda, `no inspeccionable: …`. La aplicación es `crear_aplicacion(destino_registro=io.StringIO(), entorno={})`, sin motor, y cada caso borra del entorno las variables `CIMENTA_DB_*` con `monkeypatch.delenv` antes de construirla: si una ruta ejercida intentara crear el motor, `leer_variable` lanzaría y la respuesta sería `500`.

**Comprobación previa de la fila**, repetida al abrir esta tanda y con la aplicación del oráculo montada (ver más abajo): `Dependant` expone `dependencies` y `call`, y cada `APIRoute` que `rutas_de` encuentra bajo `original_router` expone `dependant.dependencies[i].call`. La ruta `GET /api/v1/sesion` muestra la cadena `sesion_vigente` y el `APIKeyCookie` del esquema; `GET /api/v1/sesion/csrf` y `POST /api/v1/sesion`, una cadena vacía. La fila no se detiene.

**Salida real del rojo**, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_enrutador.py tests/test_servidor_arranque.py --tb=line -q -rf` (salida abreviada: las 16 trazas del enrutador repiten uno de dos errores y se condensan; los siete casos de `test_servidor_arranque.py` que no cambian y pasan no se listan).

```
E   ModuleNotFoundError: No module named 'cimenta.identidad.api.dependencias'
tests\test_tkt006_enrutador.py:149: ModuleNotFoundError: ...   (3 casos)
E   TypeError: crear_aplicacion() got an unexpected keyword argument 'entorno'
tests\test_tkt006_enrutador.py:98: TypeError: ...              (13 casos)
E   AssertionError: assert {'no_existe':...'sesion': 404} == {'no_existe':...'sesion': 401}
      Differing items:
      {'csrf': 404} != {'csrf': 200}
      {'sesion': 404} != {'sesion': 401}
tests\test_servidor_arranque.py:161: AssertionError
E   AssertionError: assert set() >= {'GET /api/v1...esion/cierre'}
      Extra items in the right set:
      'GET /api/v1/sesion/csrf'
      'GET /api/v1/sesion'
      'POST /api/v1/sesion/cierre'
      'POST /api/v1/sesion'
tests\test_servidor_arranque.py:379: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_la_lista_cerrada_coincide_con_el_enrutador
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_nueva_sin_proteger_falla
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_con_otra_dependencia_no_cuenta_como_protegida
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_que_no_es_apiroute_se_reporta
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_con_sesion_vigente_cuenta_como_protegida[en_el_decorador]
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_con_sesion_vigente_cuenta_como_protegida[en_un_parametro]
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_con_sesion_vigente_cuenta_como_protegida[en_una_sub_dependencia]
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_de_la_lista_pierde_su_excepcion
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_entrada_inventada_en_la_lista_se_reporta
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_protegida_en_la_lista_se_reporta
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca01_token_csrf_sin_sesion
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca01_los_tokens_no_se_repiten
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca07_el_contrato_publica_la_seguridad_de_sesion
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca07_los_operation_id_coinciden_con_el_borrador
FAILED tests/test_tkt006_enrutador.py::test_tkt006_car6_rutas_de_identidad_sincronas
FAILED tests/test_tkt006_enrutador.py::test_tkt006_car6_el_recorrido_detecta_una_corrutina_y_una_dependencia_asincrona
FAILED tests/test_servidor_arranque.py::test_tkt005_ca11_el_camino_del_error_no_toca_la_base
FAILED tests/test_servidor_arranque.py::test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad
18 failed, 7 passed in 6.42s
```

**Razón de cada fallo.**

| Caso | Razón |
|---|---|
| Los tres casos de `..._cuenta_como_protegida[...]` | `ModuleNotFoundError` de `cimenta.identidad.api.dependencias`: importan `sesion_vigente` antes de construir la aplicación, porque la comparación de `llamadas` es por identidad con esa función. Falta la ruta de importación que crea la fila |
| Los otros 13 casos del enrutador (TC-47 a TC-53 y sus complementos) | `TypeError: crear_aplicacion() got an unexpected keyword argument 'entorno'`. Es el rojo por la firma pedida por el diseño (`entorno={}`), el mismo de la tanda 1 con `motor`: la aplicación aún no monta `identidad`, así que la lista de rutas sin sesión ni siquiera llega a calcularse. Se probó que con la firma y sin las rutas las aserciones caerían por comportamiento (véase el oráculo) |
| TC-75 reescrito | Comportamiento: `GET /api/v1/sesion/csrf` y `GET /api/v1/sesion` responden `404 NO_ENCONTRADO` porque `identidad` no está montada. `no_existe` ya da `404`, como se espera |
| `fastapi dev` sin variables de base | Comportamiento: el servidor arranca y publica `/openapi.json` con `200`, pero sin ninguna de las cuatro rutas (`paths` vacío) |

Ninguno cae por sintaxis, entorno ni importación de terceros. Los siete casos de `test_servidor_arranque.py` que no cambian siguen en verde, TC-104 incluido (`test_tkt005_car4_pruebas_sin_base`): ni el caso nuevo ni el reescrito piden una *fixture* de base.

**Casos y criterio que cubre cada uno.**

| TC | Test | Tipo | Criterio |
|---|---|---|---|
| TC-47 | `test_tkt006_ca14_la_lista_cerrada_coincide_con_el_enrutador` (anti-verde vacío: las cuatro rutas y las cuatro funciones de identidad están en el recorrido) | feliz | `CA-14` esc. 1 |
| TC-48 | `test_tkt006_ca14_una_ruta_nueva_sin_proteger_falla` (la violación es exactamente `sin proteger: GET /api/v1/prueba/sin-sesion`) | **rechazo** | `CA-14` esc. 2 |
| (CA-14) | `test_tkt006_ca14_una_ruta_con_otra_dependencia_no_cuenta_como_protegida` (la cookie leída con `Cookie()`, como MT-15) | **rechazo** | `CA-14` esc. 2 |
| (CA-14) | `test_tkt006_ca14_una_ruta_que_no_es_apiroute_se_reporta` (`Mount /estatico` se nombra, no se calla) | **rechazo** de forma | `CA-14` |
| (CA-14) | `test_tkt006_ca14_una_ruta_con_sesion_vigente_cuenta_como_protegida` (3 formas: decorador, parámetro y sub-dependencia, la forma de `exigir_rol`) | feliz (anti falso positivo) | `CA-14` |
| TC-49 | `test_tkt006_ca14_una_ruta_de_la_lista_pierde_su_excepcion` y `..._una_entrada_inventada_en_la_lista_se_reporta` | **rechazo** | `CA-14` esc. 3 |
| (CA-14) | `test_tkt006_ca14_una_ruta_protegida_en_la_lista_se_reporta` (`GET /api/v1/sesion` listada) | **rechazo** | `CA-14` esc. 3 |
| TC-50 | `test_tkt006_ca01_token_csrf_sin_sesion` (sin Docker y sin variables de base; atributos de la cookie y `X-Correlacion-Id`) | feliz | `CA-1` esc. 1 |
| TC-51 | `test_tkt006_ca01_los_tokens_no_se_repiten` (dos y cien emisiones) | **rechazo** | `CA-1` esc. 2 |
| TC-52 | `test_tkt006_ca07_el_contrato_publica_la_seguridad_de_sesion` | feliz | `CA-7`, `M7` |
| (M7) | `test_tkt006_ca07_los_operation_id_coinciden_con_el_borrador` | **rechazo** de forma | `M7`, contrato |
| TC-53 | `test_tkt006_car6_rutas_de_identidad_sincronas` (rutas, manejadores y dependencias propias) | **rechazo** de forma | `CA-R6` |
| (CA-R6) | `test_tkt006_car6_el_recorrido_detecta_una_corrutina_y_una_dependencia_asincrona` (oráculo de TC-53) | **rechazo** de forma | `CA-R6` |
| TC-75 | `test_tkt005_ca11_el_camino_del_error_no_toca_la_base`, reescrito | **rechazo** | `CA-R4`, D-2 |
| (CA-R4) | `test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad` | feliz | `CA-R4`, D-2 |

**Casos que nacen en verde.** Ninguno.

**Edición autorizada de un test de TKT-005 (TC-75, decisión D-2).** El test `test_tkt005_ca11_el_camino_del_error_no_toca_la_base` de `backend/tests/test_servidor_arranque.py` afirmaba que construir la aplicación y responder un `404` no cargaba SQLAlchemy. Al montar `identidad` esa afirmación deja de ser cierta: se comprobó sobre el oráculo, donde la versión anterior falla con `assert ['sqlalchemy'] == []`. La versión nueva afirma lo que el test protegía, que el camino del error no toca la base, sin mirar qué módulos se cargaron. El nombre del test no cambia. La edición toca solo la constante `PROGRAMA_SIN_BASE`, el entorno del subproceso y el cuerpo del test; el resto del archivo no se tocó, y se añadió una constante `ENTORNO_SIN_BASE` y un caso nuevo (más abajo).

*Antes:*

```python
# El proceso limpio construye la aplicación, atiende una petición a una ruta que no existe y mira
# lo que se cargó: el camino del error no toca la base (CA-11 esc. 3, D-3).
PROGRAMA_SIN_BASE = """
import io
import json
import sys

from servidor.fabrica import crear_aplicacion
from fastapi.testclient import TestClient

aplicacion = crear_aplicacion(destino_registro=io.StringIO())
respuesta = TestClient(aplicacion, raise_server_exceptions=False).get("/api/v1/no-existe")

raices = {nombre.partition(".")[0] for nombre in sys.modules}
print(json.dumps({
    "estado": respuesta.status_code,
    "fastapi_cargado": "fastapi" in raices,
    "con_base": sorted(raices & {"sqlalchemy", "psycopg", "psycopg2", "asyncpg", "alembic"}),
}))
"""

def test_tkt005_ca11_el_camino_del_error_no_toca_la_base() -> None:
    """TC-75 · CA-11 esc. 3 (asumido) — construir la aplicación y un 404 no cargan SQLAlchemy ni psycopg."""
    proceso = subprocess.run(
        [sys.executable, "-c", PROGRAMA_SIN_BASE],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )

    assert proceso.returncode == 0, proceso.stderr
    resultado = json.loads(proceso.stdout.strip().splitlines()[-1])
    assert resultado["estado"] == 404
    assert resultado["fastapi_cargado"] is True  # anti-verde vacío: la aplicación sí se construyó
    assert resultado["con_base"] == []
```

*Después:*

```python
# El proceso limpio no tiene ninguna variable `CIMENTA_DB_*`. Construye la aplicación con identidad
# montada y atiende tres peticiones cuyo camino no necesita la base: una ruta que no existe, el
# token CSRF y una consulta de sesión sin cookie. Si cualquiera intentara crear el motor,
# `leer_variable` lanzaría y la respuesta sería 500 (CA-11 esc. 3 de TKT-005, reescrito por D-2 de TKT-006).
PROGRAMA_SIN_BASE = """
import io
import json
import os

from fastapi.testclient import TestClient

from servidor.fabrica import crear_aplicacion

aplicacion = crear_aplicacion(destino_registro=io.StringIO())
cliente = TestClient(aplicacion, base_url="https://testserver", raise_server_exceptions=False)
respuestas = {
    "no_existe": cliente.get("/api/v1/no-existe"),
    "csrf": cliente.get("/api/v1/sesion/csrf"),
    "sesion": cliente.get("/api/v1/sesion"),
}
print(json.dumps({
    "variables_de_base": sorted(n for n in os.environ if n.startswith("CIMENTA_DB_")),
    "estados": {nombre: r.status_code for nombre, r in respuestas.items()},
    "cuerpos": {nombre: r.json() for nombre, r in respuestas.items()},
}))
"""

# El entorno de los procesos que no deben ver la base: el del test sin ninguna `CIMENTA_DB_*`.
ENTORNO_SIN_BASE = {
    nombre: valor for nombre, valor in ENTORNO.items() if not nombre.startswith("CIMENTA_DB_")
}

def test_tkt005_ca11_el_camino_del_error_no_toca_la_base() -> None:
    """TC-75 · CA-11 esc. 3 (asumido) · TKT-006 D-2 — sin `CIMENTA_DB_*`, el 404, el token CSRF y el 401 sin cookie no tocan la base.
    ...(docstring ampliado)
    """
    proceso = subprocess.run(
        [sys.executable, "-c", PROGRAMA_SIN_BASE],
        cwd=BACKEND,
        env=ENTORNO_SIN_BASE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )

    assert proceso.returncode == 0, proceso.stderr
    resultado = json.loads(proceso.stdout.strip().splitlines()[-1])
    assert resultado["variables_de_base"] == []  # anti-verde vacío: el proceso no ve la base
    assert resultado["estados"] == {"no_existe": 404, "csrf": 200, "sesion": 401}
    cuerpos = resultado["cuerpos"]
    assert cuerpos["no_existe"]["tipo"] == "NO_ENCONTRADO"
    assert set(cuerpos["csrf"]) == {"token"}
    assert cuerpos["sesion"]["tipo"] == "SESION"
    assert cuerpos["sesion"]["motivo"] == "SIN_SESION"
    assert "detail" not in cuerpos["sesion"]
```

**Caso nuevo de arranque.** `test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad`, en el mismo archivo: lanza el comando real `python -m fastapi dev --no-reload --port <libre>` desde `backend/`, con el entorno sin ninguna `CIMENTA_DB_*`, espera `GET /openapi.json` con `200` y comprueba que `paths` contiene las cuatro operaciones de identidad y que `components.securitySchemes.sesion` es `apiKey` en `cookie` llamada `cimenta_sesion`. Usa los puertos libres y las ayudas de TC-79, no el `8765` literal del diseño: un puerto fijo choca si otra ejecución lo ocupa. El comando manual del diseño (`uv run fastapi dev --no-reload --port 8765`) sigue siendo parte de la verificación de la fila en el verde.

**Comprobación del oráculo, fuera del repositorio.** Se copió `backend/` del oráculo de la tanda 1 (con `api/esquemas.py`, `api/dependencias.py`, `api/rutas.py`, `api/montaje.py` y `servidor/fabrica.py` con el código literal del diseño; ese código **no** está en el repositorio) a la carpeta temporal de la sesión, y se copiaron allí los dos archivos de prueba. Con la aplicación montada, los 25 casos pasan (`25 passed in 7.77s`: 16 del enrutador y 9 de `test_servidor_arranque.py`, con TC-79, TC-104 y el caso de `uvicorn` incluidos). La versión anterior de TC-75, ejecutada sobre ese mismo oráculo, falla con `assert ['sqlalchemy'] == []`, que confirma D-2. Después se aplicaron 13 mutantes a esa copia, de uno en uno y con restauración comprobada por SHA-256 (el archivo vuelve al mismo valor cada vez), y cada uno puso en rojo al menos un caso:

| Mutante | Qué cae |
|---|---|
| MT-15: `cerrar_sesion` lee la cookie con `Cookie()` en lugar de `Depends(sesion_vigente)` | Los diez de `CA-14` (la aplicación real deja de coincidir con la lista cerrada, y TC-47 lo nombra) y `ca07_el_contrato_publica_la_seguridad_de_sesion` (`cierre` pierde `security`) |
| Ruta nueva `GET /api/v1/sesion/oculta` sin `sesion_vigente` | Los diez de `CA-14`. TC-47 falla con `Rutas fuera de la lista cerrada de CA-14:` y `sin proteger: GET /api/v1/sesion/oculta`, sin buscar en una lista de conjuntos |
| `obtener_sesion_actual` sin `sesion_vigente` | Los diez de `CA-14`, el contrato de seguridad y TC-75 (el `401` pasa a `200`) |
| `iniciar_sesion` declarada `async def` | TC-53 y su oráculo, y TC-77 y TC-78 de TKT-005 |
| Token CSRF de 8 bytes | TC-50, TC-51 y TC-75 |
| Token CSRF constante | TC-51 (y solo TC-51) |
| Cookie CSRF con `HttpOnly` | TC-50 |
| Esquema de seguridad con otro nombre | TC-52 y el arranque de `fastapi dev` |
| `operation_id` de `cerrar_sesion` distinto del borrador | `ca07_los_operation_id_coinciden_con_el_borrador` |
| El motor se crea al construir la aplicación (sin `functools.cache` perezoso) | 24 de los 25 casos: la aplicación no se construye sin variables de base. TC-75 y el arranque, entre ellos |
| `sesion_vigente` abre la base antes de mirar la cookie | TC-75 (el `401` sin cookie pasa a `500`), y solo ese |
| `sesion_vigente` declarada `async def` | TC-53 y su oráculo |
| Ayuda de la prueba: `llamadas` no baja por las sub-dependencias | `..._cuenta_como_protegida[en_una_sub_dependencia]` |
| Ayuda de la prueba: `rutas_de` no baja por `original_router` | Doce casos: los diez de `CA-14` y los dos de TC-53 |

La mutación oficial sobre el código real se hace en las filas 9 y 11; esta tabla demuestra que los tests no dependen de la forma exacta del código del diseño y que el recorrido distingue una ruta abierta de una protegida.

**Ruff y mypy.** `uv run ruff check` y `uv run ruff format --check` sobre los dos archivos pasan. `uv run mypy` sobre ellos solo reporta lo que falta de producción: el `call-arg` de `entorno` y la importación de `cimenta.identidad.api.dependencias`, que se resuelven con el verde de la fila.

**Ambigüedades y decisiones que el diseño no cubre.**

1. **TC-50 y TC-51 existen dos veces.** La tanda 1 los escribió en `test_tkt006_csrf.py`, con Docker y la *fixture* `cliente`; el diseño los asigna también a `test_tkt006_enrutador.py`, sin Docker, y la orden de esta tanda pidió TC-47 a TC-53 en ese archivo. Los dos archivos comparten nombre de función y comprueban cosas distintas: los de `csrf` comprueban que no se escribe en `sesion`, `intento_acceso` ni `bitacora`; los del enrutador, que la ruta funciona sin motor ni variables de base. Se dejaron ambos. Si el orquestador prefiere una sola versión, se puede retirar la del enrutador sin perder cobertura de comportamiento; la de `csrf` pide Docker.
2. **Rojo por firma en 13 de 16 casos.** El diseño fija `crear_aplicacion(destino_registro=..., entorno={})`; el rojo es `TypeError` por `entorno`, no «lista de rutas sin sesión vacía». Para que la comparación sea por identidad con la función real, los tres casos `..._cuenta_como_protegida` importan `sesion_vigente` primero y caen por `ModuleNotFoundError`. Ambos son errores del código que falta, no de entorno ni de sintaxis. La caída por comportamiento queda demostrada con el oráculo y los mutantes de arriba.
3. **Límite del recorrido (`rutas_de`).** Lee `original_router.routes` y no el contexto de la inclusión (`_IncludedRouter.include_context`). Una ruta montada con `include_router(enrutador, prefix="/x")` se nombra sin ese prefijo, y una protegida solo con `include_router(..., dependencies=[Depends(sesion_vigente)])` se cuenta como sin proteger. Los dos errores caen del lado seguro (la prueba falla), no dejan pasar una ruta abierta; la convención del diseño (el prefijo y las dependencias en la ruta, no en la inclusión) los evita. Queda anotado en el docstring del archivo.
4. **Complementos que el diseño no listaba**, todos en `test_tkt006_enrutador.py`: reportar lo que no es `APIRoute` (un `Mount` abriría una ruta sin sesión que el recorrido no vería), `Cookie()` leída a mano como mutante de MT-15, las tres formas de proteger con `sesion_vigente` (la tercera es la de `exigir_rol`, fila 10, que el recorrido debe aceptar), una ruta protegida metida en la lista, los `operationId` contra el borrador, y las dependencias propias `async def`. Ninguno cambia lo que el diseño pide.
5. **TC-52 no afirma `csrf`.** El borrador declara `security: sesion + csrf` en `cerrar_sesion`, pero la verificación del token es de TKT-057; el caso solo afirma `sesion` y que las dos rutas de la lista cerrada no la declaran.
6. **Finales de línea.** Los dos archivos están con CRLF en el árbol de trabajo, como los de las tandas anteriores; `.gitattributes` los normaliza al confirmar.

**Verde** — ver «Fila 7 · verde y refactor» más abajo.

**Tests devueltos al tester:** ninguno.

#### Fila 7 · verde y refactor

**Comprobación previa.** `uv run python -c "from fastapi.dependencies.models import Dependant; f = Dependant.__dataclass_fields__; print('dependencies' in f, 'call' in f)"` imprime `True True` con FastAPI 0.159.1. El recorrido de dependencias de los tests es válido y el diseño no choca con la versión.

**Verde.** Se escribieron `api/esquemas.py`, `api/dependencias.py` (`sesion_vigente` con `APIKeyCookie(name="cimenta_sesion", scheme_name="sesion", auto_error=False)`; sin `exigir_rol`), `api/rutas.py`, `api/montaje.py` y se cambió `servidor/fabrica.py`, con el código del diseño. Ningún test ni `conftest.py` se tocó. Las cuatro rutas son `def`; los errores salen solo de `SesionInvalida`; la cookie de sesión lleva el identificador opaco de la fila `sesion` con `HttpOnly`, `Secure`, `SameSite=Lax` y `Path=/`; la cookie `cimenta_csrf` no lleva `HttpOnly` y su valor es el del cuerpo (solo se emite: verificarlo es de TKT-057). `sesion_vigente` está en la cadena de `GET /api/v1/sesion` y `POST /api/v1/sesion/cierre`; solo `GET /api/v1/sesion/csrf` y `POST /api/v1/sesion` quedan sin ella. El motor es perezoso: construir la aplicación no exige variables de base ni abre conexión. El docstring de `fabrica.py` anota que solo monta `cimenta.identidad.api.montaje`.

**Decisión del usuario sobre el correo.** `pydantic.networks.validate_email` rechaza `ana@cimenta.test` (dominio reservado) y la spec usa ese correo. `forma_de_correo` valida con `email_validator.validate_email(valor, check_deliverability=False, test_environment=True)` y devuelve el valor original tal como se escribió, no la forma normalizada ni `EmailStr`, que cambiaría el dominio. Se mantienen los rechazos previos de espacios en los extremos y de `<` o `>`. `email-validator` se declaró como dependencia directa con `uv add email-validator` (`email-validator>=2.3.0`; antes llegaba solo de forma transitiva por `fastapi[standard-no-fastapi-cloud-cli]`). Tras el cambio de `pyproject.toml` y `uv.lock`, TC-18 sigue en verde (`tests/test_tkt006_configuracion.py`: `43 passed in 0.27s`) y `uv sync --locked` termina sin cambios.

Comandos desde `backend/` con `PYTHONUTF8=1`, con la salida real:

`uv run pytest tests/test_tkt006_*.py tests/test_servidor_arranque.py tests/test_contrato_error_http.py -q` (con Docker):

```
301 passed in 38.90s
```

- `uv run mypy .` → `Success: no issues found in 149 source files`.
- `uv run ruff check .` → `All checks passed!`; `uv run ruff format --check .` → `149 files already formatted`.
- `uv run python -m herramientas.verificar_float` → `verificar_float: archivos revisados: 18; hallazgos: 0`.
- `uv run lint-imports` → `Contracts: 15 kept, 0 broken.` La raíz `servidor/` solo importa `cimenta.identidad.api.montaje`.
- `uv run --with pip-audit pip-audit` → `No known vulnerabilities found`.
- `uv run fastapi dev --no-reload --port 8765`, en segundo plano y sin ninguna variable `CIMENTA_DB_*` en el entorno: `GET http://127.0.0.1:8765/openapi.json` responde `200` con `GET /api/v1/sesion/csrf`, `GET /api/v1/sesion`, `POST /api/v1/sesion` y `POST /api/v1/sesion/cierre`, y `components.securitySchemes` es `{'sesion': {'type': 'apiKey', 'in': 'cookie', 'name': 'cimenta_sesion'}}`. El proceso se terminó después y el puerto quedó libre.

**Refactor.** Ninguno: `ruff format` no cambió nada y no hay duplicación que simplificar.

**Desviaciones respecto al design.** Dos, ambas menores. (1) `forma_de_correo` usa `email_validator` y no `pydantic.networks.validate_email`, por la decisión del usuario descrita arriba. (2) `forma_de_correo` captura `EmailNotValidError` y lanza `ValueError`, porque Pydantic solo convierte un `ValueError` en `422 FORMATO`; un `EmailNotValidError` también es `ValueError`, pero se relanza con mensaje propio para no filtrar el texto de la biblioteca. `dependencias.py` añade `COOKIE_CSRF` y `rutas.py` pasa `scheme_name="sesion"` por el borrador, como indica el diseño. Sin mutación en esta fila: la hace el tester en la fila 9.

**Tests devueltos al tester:** ninguno.

#### Fila 8 · rojo

La fila 8 escribe las pruebas de la restricción `ck_usuario_email_minusculas` (S2, `CA-17`) y de la comparación entre la semilla de `rol` y el enum `Rol` (`CA-16`). Ningún archivo de producción se creó ni se tocó: la migración `v0004` no existe todavía y ningún test existente se modificó.

**Comprobación previa.** La cabeza de migraciones antes de la fila, desde `backend/`:

```
$ uv run --env-file ../.env alembic heads
0003 (head)
```

Hay una sola cabeza, `0003` (TKT-007, tabla `bitacora`). La migración de este ticket es, por tanto, la `0004` con `down_revision = "0003"`. Los tests de TKT-003 y TKT-007 que fijan `0002` y `0003` como revisión anterior siguen siendo válidos.

**Archivo de pruebas.** `backend/tests/test_tkt006_esquema.py` (nuevo, con Docker, salvo TC-55). Reutiliza `base_de_prueba`, `base_vacia`, `migrar` y `conectar` de `conftest.py`; sus ayudas son `diferencias_de_roles`, `claves_de_rol`, `restriccion_de_correo`, `insertar_usuario` y `contar_usuarios`.

| # | Test | Casos | Resultado | Razón |
|---|---|---|---|---|
| TC-54 | `test_tkt006_ca16_semilla_igual_al_enum` | 1 | **Nace en verde** (previsto) | La semilla de `v0002` ya trae las seis claves del enum `Rol`. Depende de algo real: lee `SELECT clave FROM rol` con el rol de aplicación y compara contra `{r.value for r in Rol}`; si una de las dos listas cambiara, cae |
| TC-55 | `test_tkt006_ca16_la_diferencia_nombra_la_clave` | 1 | **Nace en verde** (previsto) | Es el oráculo de TC-54 y no toca la base: con el enum más `GERENTE` el texto nombra `GERENTE` y habla del enum; sin `ALMACEN` nombra `ALMACEN` y habla de la semilla; iguales devuelve `[]` |
| TC-56 | `test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas` | 3 (`Ana@Cimenta.test`, `ANA@CIMENTA.TEST`, `ana@Cimenta.test`) | **FALLA** | `Failed: DID NOT RAISE CheckViolation`: el `INSERT` con mayúsculas pasa porque la restricción no existe. Es una aserción de comportamiento, no un error de importación ni de entorno |
| TC-57 | `test_tkt006_ca17_la_migracion_se_revierte` | 1 | **FALLA** | `AssertionError: Tras upgrade head debe existir ck_usuario_email_minusculas: falta la migración v0004 (TKT-006)`: `pg_constraint` no devuelve la restricción tras subir a `head` |

TC-56 afirma, por cada correo, el `sqlstate` `23514`, `diag.constraint_name == "ck_usuario_email_minusculas"`, `diag.table_name == "usuario"`, que la tabla siga sin filas tras el rechazo, que el mismo correo en minúsculas se inserte y que quede exactamente una fila con ese valor. TC-57 sube a `head` sobre `base_vacia`, exige la restricción con la definición `CHECK ((email = lower(email)))`, baja a `0003`, exige que la restricción no esté, que `alembic_version` sea `0003` y que `usuario` siga existiendo, vuelve a subir y exige la misma restricción. La primera aserción de TC-57 es la que cae hoy, así que el resto del ciclo no corre sobre un esquema equivocado.

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_esquema.py -p no:cacheprovider`, con Docker en marcha (`docker info` responde la versión 29.8.2). Extracto de la salida real:

```
E           Failed: DID NOT RAISE CheckViolation
tests\test_tkt006_esquema.py:134: Failed
E       AssertionError: Tras `upgrade head` debe existir ck_usuario_email_minusculas: falta la migración v0004 (TKT-006).
E       assert [] == [('ck_usuario...er(email)))')]
tests\test_tkt006_esquema.py:156: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_tkt006_esquema.py::test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas[mayuscula-inicial]
FAILED tests/test_tkt006_esquema.py::test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas[todo-en-mayusculas]
FAILED tests/test_tkt006_esquema.py::test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas[mayuscula-en-el-dominio]
FAILED tests/test_tkt006_esquema.py::test_tkt006_ca17_la_migracion_se_revierte
========================= 4 failed, 2 passed in 4.10s =========================
```

`ruff check`, `ruff format` y `mypy` sobre el archivo nuevo pasan.

**Desviaciones respecto al design.** (1) TC-56 se parametriza con tres correos con mayúsculas en lugar de uno, y el caso en minúsculas pasa dentro del mismo test para no crear un test que nazca en verde. (2) TC-57 baja con `downgrade 0003` y no con `downgrade -1`: si una migración posterior a la `0004` se añade, `-1` ya no tocaría esta restricción, y bajar a la revisión propia del paso la mantiene probada. (3) `diferencias_de_roles` devuelve una lista de textos (vacía si no hay diferencia), igual que `diferencias_de_verbos` de TKT-007, y no un único texto.

**Qué debe producir el verde.** La migración `v0004` con `down_revision = "0003"`, una sola cabeza, que ejecute `ALTER TABLE usuario ADD CONSTRAINT ck_usuario_email_minusculas CHECK (email = lower(email))` y, en la bajada, `ALTER TABLE usuario DROP CONSTRAINT ck_usuario_email_minusculas`. Sin reescribir correos existentes: si la subida los encontrara, falla y se escala.

**Tests devueltos al tester:** ninguno.

#### Fila 8 · verde y refactor

**Verde.** Se escribió `backend/migraciones/versions/v0004_identidad_correo_en_minusculas.py`, con `revision = "0004"` y `down_revision = "0003"`, siguiendo el patrón de `v0001` y `v0003`: tuplas `_SUBIDA` y `_BAJADA` con una sentencia por `op.execute`. La subida es `ALTER TABLE usuario ADD CONSTRAINT ck_usuario_email_minusculas CHECK (email = lower(email))` y la bajada es `ALTER TABLE usuario DROP CONSTRAINT ck_usuario_email_minusculas`, tal como fija la fila `v000N_identidad_correo_en_minusculas` de la tabla de objetos de `design.md` y la migración de S2. La migración no normaliza filas existentes: si hubiera correos con mayúsculas, PostgreSQL rechaza la subida y la migración falla, y el caso se escala. Ningún test se tocó, ni `ARCHIVOS_QUE_LA_REVISION_DEBE_INCLUIR` de TKT-003. No se añade ningún objeto nuevo que necesite `GRANT`: la restricción es de `usuario`, que ya tiene sus permisos de `v0001`.

Comandos desde `backend/` con `PYTHONUTF8=1`, con la salida real:

- `uv run --env-file ../.env alembic heads` → `0004 (head)`. Una sola cabeza.
- `uv run pytest tests/test_tkt006_esquema.py tests/test_identidad_*.py tests/test_tkt007_esquema.py -q` (con Docker, tras el verde):

```
91 passed in 32.14s
```

Tras el refactor, la misma selección vuelve a dar `91 passed in 32.31s`. Los cuatro tests de la fila pasan por separado: `test_tkt006_ca16_semilla_igual_al_enum`, `test_tkt006_ca16_la_diferencia_nombra_la_clave`, los tres casos de `test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas` (rechazo con `CheckViolation`, `sqlstate` `23514` y `constraint_name` `ck_usuario_email_minusculas`) y `test_tkt006_ca17_la_migracion_se_revierte` (subida a `head`, bajada a `0003`, nueva subida, misma definición `CHECK ((email = lower(email)))`).

- `uv run mypy .` → `Success: no issues found in 151 source files`.
- `uv run ruff check .` → `All checks passed!`.
- `uv run ruff format --check .` → antes del refactor, `unformatted: File would be reformatted` sobre el archivo nuevo; tras `ruff format` sobre ese único archivo, `151 files already formatted`.

**Base local no comprobada.** `docker compose ps` no lista contenedores y el ciclo `upgrade head` → `downgrade -1` → `upgrade head` sobre la base local no terminó en 120 s (las tres órdenes acabaron con código de salida 124, sin salida de Alembic). No hay base local en marcha, así que no se ejecutó la comprobación manual. El ciclo sí está probado sobre PostgreSQL real con testcontainers: `test_tkt006_ca17_la_migracion_se_revierte` (TC-57) lo recorre y pasa.

**Refactor.** `ruff format` dejó la tupla de `_BAJADA` en una sola línea. Ningún otro cambio: la migración son dos tuplas con una sentencia cada una y dos funciones que las recorren.

**Desviaciones respecto al design.** (1) `design.md` da las sentencias de subida y bajada en prosa, no como bloque de código; se copiaron literales, sin reescribirlas. (2) Ningún test de TKT-003 ni de TKT-007 se rompió al añadir `0004`: TC-15 y TC-17 de TKT-007 usan `cabeza_de_las_migraciones()` o bajan explícitamente a `0002`, y TC-16 de TKT-007 sigue encontrando `0003` en la cadena. (3) No hay desviación en el nombre del archivo: sigue el patrón de `v0001` a `v0003`.

**Tests devueltos al tester:** ninguno.

## Fila 9 · mutación y regresión (entrega A)

Fila sin código de producción: solo se mutó, se comprobó y se restauró. Ningún archivo de producción ni de prueba quedó alterado y no se añadió ningún test, porque ningún mutante sobrevivió.

**Método.** Un arnés en Python, fuera del repositorio (reutiliza el de la entrega A de TKT-007: `aplicar`, `correr` y `sha`), calcula el SHA-256 del archivo, comprueba que cada fragmento a sustituir aparece exactamente una vez, escribe el archivo mutado, ejecuta los nueve archivos `tests/test_tkt006_*.py` completos (218 casos, con Docker y `PYTHONUTF8=1`), restaura los bytes originales dentro de un `finally` y calcula de nuevo el SHA-256. Se corre la suite entera del ticket y no solo el caso del diseño para que la tabla muestre también los casos que caen de más. Los archivos de producción de `identidad` tienen finales de línea LF, así que los fragmentos se sustituyen tal cual. La línea base, antes de empezar, era `218 passed in 23.95s`. Los mutantes `MT-10` a `MT-14` y `MT-21` son de la entrega B y no se ejecutaron.

**SHA-256 de cada archivo antes de mutar** (idéntico después de cada restauración y al terminar la fila, comprobado de nuevo con los ocho archivos al final):

| Archivo | SHA-256 |
|---|---|
| `backend/cimenta/identidad/dominio/vigencia.py` | `2b446051b29936897e79b59ddbedc78e4e42500e863519677dad27dc5dcac334` |
| `backend/cimenta/identidad/dominio/acceso.py` | `84ff4cd7f2c226b009c7127cd3260b1092a9345ce90876effff7e767c4ba66b1` |
| `backend/cimenta/identidad/dominio/correo.py` | `1b96c94e4d16546fe8d0c53127e22222cd35f5ceb225bb4a3a3b4331c79686dc` |
| `backend/cimenta/identidad/aplicacion/sesiones.py` | `032d751564aaba60248d9c870dd3393ab6ecc92defb78a6bb454fac73908053f` |
| `backend/cimenta/identidad/infraestructura/contrasenas.py` | `a06216037f450beb8a8aea003adca17b5b48283a4b8c0814ae8999310a9f74cb` |
| `backend/cimenta/identidad/infraestructura/repositorio.py` | `dfaccc56f822c8e70456163dab1c20119ee41385d7818e3c5d817d564874a5eb` |
| `backend/cimenta/identidad/api/rutas.py` | `a1d370cb84cfaa3cb69bdac40e83bca2ca00f97bca944f3ff75dc06b7d2a3658` |
| `backend/cimenta/identidad/api/dependencias.py` | `86a93cb67b784d2cb8f098665ac36cc6c1453ba5a30d57b0e10ba02a27dce89f` |

### Tabla de mutantes

SHA mutado: los primeros 12 caracteres; el SHA «antes» y el «después» son los de la tabla anterior y coincidieron en los 16 casos. «Debe caer» es la columna del diseño; «Cae» son los casos que se pusieron rojos de verdad (cada nombre es `test_tkt006_<...>` abreviado), con la línea de resumen de `pytest` del mutante.

| Mutante | Archivo | Mutación | SHA mutado | Debe caer | Cae (salida resumida) | Restaurado |
|---|---|---|---|---|---|---|
| MT-1 | `vigencia.py` | `not ahora < expira_en` pasa a `expira_en < ahora` | `4e7946a2c1c8` | TC-03, TC-36 | `ca08_caduca_al_llegar_expira_en[en-el-limite]` (TC-03), `ca08_caducidad_absoluta` (TC-36), `ca08_vigencia_con_instantes_con_zona`, `ca08_aplicacion_validar_caduca_al_llegar_expira_en`, y dos casos de «la actividad desliza la inactividad y no la absoluta» · `6 failed, 212 passed` | sí |
| MT-2 | `vigencia.py` | sin la comprobación de inactividad | `fa8e5be00084` | TC-04, TC-37 | `ca08_caduca_por_inactividad[en-el-limite]` y `[despues-del-limite]` (TC-04), `ca08_caducidad_por_inactividad` (TC-37), `ca08_vigencia_con_instantes_con_zona`, tres pasos de `aplicacion_validar_caduca_por_inactividad` y `aplicacion_validar_usa_la_inactividad_de_la_configuracion` · `8 failed, 210 passed` | sí |
| MT-3 | `vigencia.py` | sin `revocada` | `14cc0e9c790e` | TC-05, TC-44 | los cuatro casos de `ca09_revocada_prevalece` (TC-05), `ca09_revocada_prevalece_sobre_caducada_por_http` (TC-44) y `ca09_aplicacion_revocada_prevalece_sobre_caducada` · `6 failed, 212 passed` | sí |
| MT-4 | `vigencia.py` | ignora `usuario_activo` | `a6647dc16a0b` | TC-06, TC-40 | `ca10_usuario_desactivado_es_revocada[vigente]` y `[ya-caducada]` (TC-06), `ca10_desactivar_surte_efecto_en_la_peticion_siguiente` y `ca10_desactivado_y_caducada_es_revocada` (TC-40), más sus dos hermanos de aplicación · `6 failed, 212 passed` | sí |
| MT-5 | `sesiones.py` | `abrir_sesion`: sin credencial no verifica y rechaza directamente | `50cc110ca956` | TC-26 | `ca03_aplicacion_verifica_un_hash_siempre[correo_inexistente]` y `ca03_aplicacion_el_hash_de_descarte_no_es_el_de_ningun_usuario` · `2 failed, 216 passed` | sí |
| MT-6 | `contrasenas.py` | hash de descarte con `PasswordHash.recommended()` | `a8ba7734d69a` | TC-17 | `ca03_hash_de_descarte_con_los_mismos_parametros[costes_de_prueba]` y `ca08_aplicacion_construir_contexto_toma_configuracion_reloj_y_contrasenas` · `2 failed, 216 passed` | sí |
| MT-7 | `sesiones.py` | `abrir_sesion`: el `raise` dentro del bloque `begin()` | `ae3c0b2e380b` | TC-27 | `ca03_aplicacion_el_intento_fallido_sobrevive` (3 casos), `ca03_aplicacion_cada_intento_fallido_deja_su_fila`, `ca03_aplicacion_el_fallo_no_borra_el_intento_de_un_inicio_correcto_previo`, `ca03_el_intento_fallido_sobrevive_al_401` (3 casos por HTTP), `ca03_contrasena_equivocada`, `ca03_correo_inexistente_indistinguible`, `ca04_usuario_desactivado_no_inicia` y `ca12_denegaciones_anonimas_fuera_de_la_bitacora` · `12 failed, 206 passed` | sí |
| MT-8 | `acceso.py` | `credenciales_aceptadas` sin `activo` | `37872f96450a` | TC-08, TC-28 | `ca04_credenciales_aceptadas[existe-no-activo-coincide]` (TC-08), `ca04_usuario_desactivado_no_inicia` (TC-28) y cinco casos de `usuario_desactivado` de `ca03_*` · `7 failed, 211 passed` | sí |
| MT-9 | `repositorio.py` | `tocar_sesion` sin `AND revocada_en IS NULL` | `06f4773c3b80` | TC-41, TC-59 | `ca06_concurrencia_cierre_y_peticion_simultanea` (TC-41) y `ca09_tocar_y_revocar_respetan_la_revocacion` (TC-59). Ningún caso secuencial de aplicación ni de HTTP lo detecta, como esperaba la orden: la guarda solo se prueba con el cierre simultáneo (TC-41) y con el repositorio (TC-59) · `2 failed, 216 passed` | sí |
| MT-15 | `rutas.py` | `cerrar_sesion` lee la cookie con `Cookie()` en lugar de `Depends(sesion_vigente)` | `5981251b6d68` | TC-47 | `ca14_la_lista_cerrada_coincide_con_el_enrutador` (TC-47) y otros nueve casos de `test_tkt006_enrutador.py` que usan el recorrido de rutas; por HTTP, `ca09_cerrar_sin_sesion`, `ca09_cerrar_dos_veces_la_segunda_es_revocada`, `ca09_cerrar_con_una_cookie_que_no_corresponde_a_nada` (3 casos) y `ca07_el_contrato_publica_la_seguridad_de_sesion` · `16 failed, 202 passed` | sí |
| MT-16 | `rutas.py` | `set_cookie` de la sesión con `httponly=False` | `db46cc4a0ffb` | TC-21 | `ca02_atributos_de_la_cookie_de_sesion` · `1 failed, 217 passed` | sí |
| MT-17 | `correo.py` | `normalizar_correo` devuelve el valor sin cambiar | `df51b377e306` | TC-01, TC-22 | `ca02_correo_se_normaliza_a_minusculas` (TC-01), `ca02_correo_sin_distinguir_mayusculas` (TC-22) y `ca02_aplicacion_correo_sin_distinguir_mayusculas` · `3 failed, 215 passed` | sí |
| MT-18 | `sesiones.py` | `insertar_intento` recibe el correo normalizado | `76f8183ffd92` | TC-22 | `ca02_correo_sin_distinguir_mayusculas` y `ca02_aplicacion_correo_sin_distinguir_mayusculas`: el intento debe guardar lo escrito · `2 failed, 216 passed` | sí |
| MT-19 | `repositorio.py` | `revocar_sesion` hace `DELETE` | `ff9119c43589` | TC-43, TC-46 | `ca09_cerrar_revoca_sin_borrar` (TC-43), `ca09_sin_delete_sobre_sesion` (TC-46), `ca09_la_sesion_cerrada_ya_no_sirve`, `ca09_cerrar_dos_veces_la_segunda_es_revocada`, `ca09_cerrar_una_sesion_no_revoca_las_demas`, dos casos del repositorio, cinco de aplicación y la concurrencia del cierre · `13 failed, 205 passed` | sí |
| MT-20 | `sesiones.py` | `sesion_vigente` (vía `validar_sesion`) responde `SESION_REVOCADA` a un UUID inexistente | `93bfe4b0539b` | TC-35 | `ca07_cookie_inexistente_o_mal_formada` (TC-35), `ca07_aplicacion_validar_sesion_inexistente_es_sin_sesion` y `ca09_cerrar_con_una_cookie_que_no_corresponde_a_nada[uuid_inexistente]` · `3 failed, 215 passed` | sí |
| MT-22 | `dependencias.py` | `sesion_vigente` no fija `request.state.roles_de_quien_llama` con los roles | `f351959cbae7` | TC-33 | `ca06_roles_de_quien_llama` (TC-33) y `ca11_retirar_un_rol_se_ve_en_la_peticion_siguiente` · `2 failed, 216 passed` | sí |

**Sobrevivientes: ninguno.** Los 16 mutantes de la entrega A dejaron en rojo al menos los casos que el diseño indica. No hace falta añadir ningún test.

**Observaciones.**

- **Dominio.** `MT-1`, `MT-2`, `MT-3`, `MT-4`, `MT-8` y `MT-17` no añaden ninguna importación, así que `test_tkt006_ca13_dominio_de_identidad_puro` (el AST de TC-12) y `test_tkt006_ca13_contrato_dominio_sin_framework_se_cumple` (`lint-imports`) siguieron en verde en las seis ejecuciones: los mutantes son válidos y respetan la pureza, y cae solo lo que prueba el comportamiento.
- **`MT-9`.** Cae solo con los dos casos que ejercen la guarda de verdad: TC-41, con dos transacciones reales, y TC-59, contra el repositorio. Ningún caso secuencial de `validar_sesion` ni de HTTP se pone rojo, porque en secuencia la lectura previa ya descarta la sesión revocada. Es la razón por la que TC-41 no se puede reducir a una versión sin concurrencia.
- **`MT-7`.** Cae tanto a nivel de aplicación como por HTTP: el intento fallido que se deshace con el `raise` dentro de `begin()` lo detectan los dos niveles, además de `ca04_usuario_desactivado_no_inicia` y `ca12_denegaciones_anonimas_fuera_de_la_bitacora`, que también dependen de que la fila del intento sobreviva al `401`.
- **`MT-15`.** El arnés lo mutó con una firma `Cookie()` y `uuid.UUID(...)`: los casos del enrutador (TC-47 y complementos) caen porque `cerrar_sesion` deja de depender de `sesion_vigente`, que es lo que el diseño pide demostrar sobre su riesgo 7 (el test del enrutador depende de atributos internos de FastAPI).
- Los casos que nacieron en verde en las filas anteriores (TC-12 en su parte de `lint-imports`, TC-54 y TC-55) no tienen mutante asignado entre los de esta fila; su prueba de que dependen de algo es la del diseño (la parte AST de TC-12 y las seis ejecuciones de dominio de arriba). `MT-10` a `MT-14` y `MT-21` quedan para la fila 11.

### Regresión (TC-R1 a TC-R7)

Desde `backend/`, con `PYTHONUTF8=1` y Docker en marcha, con los ocho archivos restaurados y comprobados por SHA-256.

```text
TC-R1  uv run pytest tests/test_identidad_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_lectura_sin_secretos.py tests/test_tkt006_cierre.py
       26 passed in 5.87s          (TC-46 va en test_tkt006_cierre.py; el oyente de TC-62 es de la entrega B)
TC-R2  uv run pytest tests/test_identidad_migracion_ciclo.py tests/test_identidad_semilla.py tests/test_identidad_migracion_cli.py tests/test_tkt006_esquema.py
       18 passed in 5.96s          (TC-57 va en test_tkt006_esquema.py)
TC-R3  uv run lint-imports                       -> Contracts: 15 kept, 0 broken.   (código 0; eran 15 antes del ticket)
       uv run pytest tests/test_fronteras_dominio.py tests/test_tkt005_fronteras.py
       24 passed in 11.29s
       grep -c ignore_imports pyproject.toml     -> 0
TC-R4  uv run ruff check .                       -> All checks passed!                              (código 0)
       uv run ruff format --check .              -> 151 files already formatted                     (código 0)
       uv run mypy .                             -> Success: no issues found in 151 source files    (código 0)
       uv run python -m herramientas.verificar_float -> archivos revisados: 18; hallazgos: 0        (código 0)
TC-R5  TC-24, TC-34 y TC-45 afirman `"detail" not in cuerpo` (test_tkt006_inicio_sesion.py, test_tkt006_sesion_vigente.py
       y test_tkt006_cierre.py), y pasan en la suite completa. TC-61 es de la entrega B.
TC-R6  uv run pytest tests/test_contrato_error_http.py tests/test_servidor_arranque.py
       89 passed in 9.32s          (TC-53 y TC-77 de TKT-005, con la identidad montada)
```

Suite completa, `uv run pytest -p no:cacheprovider` con Docker:

```text
tests\test_tkt006_cierre.py ..........                                   [ 62%]
tests\test_tkt006_configuracion.py ..................................... [ 65%]
......                                                                   [ 66%]
tests\test_tkt006_csrf.py .....                                          [ 66%]
tests\test_tkt006_dominio.py .....................................       [ 70%]
tests\test_tkt006_enrutador.py ................                          [ 71%]
tests\test_tkt006_esquema.py ......                                      [ 72%]
tests\test_tkt006_inicio_sesion.py ..................................... [ 75%]
.........                                                                [ 76%]
tests\test_tkt006_repositorio.py ..............                          [ 77%]
tests\test_tkt006_sesion_vigente.py .................................... [ 81%]
.....                                                                    [ 81%]
tests\test_tkt007_asiento.py ...................                         [ 83%]
tests\test_tkt007_consulta.py ...............................            [ 86%]
tests\test_tkt007_dominio.py ........................................... [ 90%]
...........                                                              [ 91%]
tests\test_tkt007_dominio_consulta.py .................................. [ 94%]
...                                                                      [ 94%]
tests\test_tkt007_esquema.py ........................                    [ 96%]
tests\test_tkt007_fronteras.py ........                                  [ 97%]
tests\test_tkt007_motor.py .....                                         [ 97%]
tests\test_verificar_float.py .......................                    [100%]

====================== 1089 passed in 218.05s (0:03:38) =======================
```

**TC-R7 (documentación, desde la raíz).**

- `python tools/extraer_mermaid.py` → código 0 (escribe `tools/mermaid-check.html`, que está en `.gitignore`).
- `python -m unittest discover -s tools/tests -v` → `Ran 6 tests ... OK`, código 0.
- `python tools/verificar_docs.py` → **código 1, un problema**: `Enlace roto · sdd\tickets\tkt-006\impl.md → delta.md`. Es el enlace «Siguiente: delta →» de la cabecera de este mismo archivo, que apunta a un `delta.md` que no existe hasta `/sdd-completar` (fila 12 y cierre del ticket). No lo introdujo esta fila ni lo causa ningún cambio de código; los conteos (22 ADR, 38 invariantes, 162 escenarios) y la codificación (111 archivos) están bien. Debe estar en verde cuando exista `delta.md`; hasta entonces TC-R7 queda a medias en este punto.
- **BOM y CRLF de los archivos nuevos del ticket.** Se revisaron los 31 archivos modificados o nuevos que muestra `git status`: ninguno empieza con BOM. Dos archivos nuevos de prueba tienen finales de línea CRLF en el árbol de trabajo: `backend/tests/test_tkt006_dominio.py` y `backend/tests/test_tkt006_inicio_sesion.py`. El resto, incluidos todos los de `cimenta/identidad/`, la migración `v0004` y este `impl.md`, está en LF. `.gitattributes` fija `* text=auto eol=lf`, así que `git` los normaliza a LF al confirmar y el repositorio queda limpio; no se tocaron.
- **Lo que cubre `test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf`.** Está en verde, pero solo recorre `contrato_error/*.py`, `servidor/*.py`, `tests/test_contrato_error_*.py`, `tests/test_servidor_*.py`, `tests/test_tkt005_*.py` y `sdd/tickets/tkt-005/*.md` (comprobado leyendo `archivos_nuevos_del_ticket`). Cubre `servidor/fabrica.py` y `test_servidor_arranque.py`, que este ticket edita, y no cubre ningún archivo nuevo de TKT-006. Los dos CRLF de arriba quedan fuera de su alcance. Se deja la decisión al orquestador: normalizarlos a LF antes de confirmar, o ampliar ese verificador al glob `test_tkt006_*` en la fila 11 (TKT-005 es de otro ticket, así que no se tocó aquí).

**Verificación de que no queda ningún archivo mutado.** `git status --short` lista los mismos 5 archivos modificados y los mismos 26 sin seguimiento (`impl.md` incluido) que antes de la fila; `git diff --stat` solo muestra `pyproject.toml`, `servidor/fabrica.py`, `tests/conftest.py`, `tests/test_servidor_arranque.py` y `uv.lock` (404 inserciones, 21 eliminaciones), todos de filas anteriores. Como los archivos de `cimenta/identidad/` no están aún en el índice, `git diff` no los vería: la garantía es el SHA-256 de los ocho archivos, que coincide con la tabla inicial tras cada restauración y al final, y la suite completa, `ruff`, `mypy` y `lint-imports` en verde sobre el árbol restaurado.

**Tests devueltos al tester:** ninguno. **Tests añadidos o modificados en esta fila:** ninguno.

## Fila 10 · rojo

Entrega B, fila 10: rol por ruta, asiento `DENEGAR` e interfaz publicada. Solo pruebas: no se creó ni se tocó ningún archivo de producción. `backend/cimenta/identidad/interfaz.py` sigue siendo el esqueleto de TKT-002 (solo docstring), y `backend/cimenta/identidad/aplicacion/` no tiene `denegacion.py`. Docker en marcha (`docker info` responde, servidor 29.8.2).

### Comprobación previa · `asentar_denegacion` de TKT-007 contra el contrato C-1 enmendado

Comando, desde `backend/`: `PYTHONUTF8=1 uv run python -c "import inspect; from cimenta.auditoria import interfaz; print(inspect.signature(interfaz.asentar_denegacion)); print('asentar_denegacion' in interfaz.__all__)"`

```
(sesion_bd: sqlalchemy.orm.session.Session, *, usuario_id: uuid.UUID, ocurrido_en: datetime.datetime, motivo: str, datos: collections.abc.Mapping[str, object]) -> uuid.UUID
True
```

Comparación con el contrato C-1 enmendado del diseño (`asentar_denegacion(sesion_bd, *, usuario_id, ocurrido_en, motivo, datos) -> uuid.UUID`):

| Punto del contrato | Firma real y código de TKT-007 | ¿Coincide? |
|---|---|---|
| Nombre y exportación | `cimenta.auditoria.interfaz.asentar_denegacion`, dentro de `__all__` | Sí |
| Parámetros | `sesion_bd` posicional; `usuario_id`, `ocurrido_en`, `motivo` y `datos` solo por palabra clave, en ese orden | Sí |
| Retorno | `uuid.UUID` (el id del asiento) | Sí |
| Escribe en la sesión recibida, sin confirmar | Delega en `asentar(...)`, cuyo docstring dice «Nunca confirma ni abre otra transacción»; el de `asentar_denegacion` lo repite: «aquí no se confirma» | Sí |
| `entidad_tipo` y `entidad_id` | `entidad_tipo="usuario"`, `entidad_id=usuario_id` | Sí |
| Sin correlación ni sesión web | No recibe ninguno de los dos; el docstring explica por qué (credencial de la cookie e invariante 21) | Sí |
| `regla_negocio`, `obra_id` y `datos_antes` | No se pasan: quedan nulos; `datos` va a `datos_despues` | Sí |

La semántica coincide: ninguna diferencia, así que la fila 10 sigue. La «transacción propia» no es cosa de `auditoria`: la abre quien llama (`registrar_denegacion`, con `fabrica_sesiones().begin()`), que es lo que prueba TC-63.

### Qué se escribió

`backend/tests/test_tkt006_permisos_rol.py` (con Docker, rol de aplicación, `alembic upgrade head` por el arnés de `conftest.py`, ninguna *fixture* `autouse`) y cinco bloques nuevos al final de `backend/tests/test_tkt006_enrutador.py` (sin Docker), debajo de los 16 casos existentes, que no se modificaron. Los símbolos de producción (`exigir_rol`, `sesion_vigente`, `evaluar_resolucion` y `registrar_denegacion`) se importan **dentro de cada caso o de cada ayuda**, desde `cimenta.identidad.interfaz` salvo `registrar_denegacion`, que vive en `cimenta.identidad.aplicacion.denegacion`: mientras no existan, cada caso falla por su cuenta y la recolección no se cae.

Las rutas de prueba son de la suite (`agregar_rutas_de_prueba`): `GET /api/v1/prueba/compras`, `.../almacen`, `.../direccion` (y su `POST`), `.../compras-o-direccion` con `exigir_rol("COMPRAS", "DIRECCION_GENERAL")` y `GET /api/v1/prueba/roles` con `sesion_vigente`. Cada cuerpo anota «MÉTODO ruta» en una lista: un `401` o un `403` la deja vacía y demuestra que la dependencia cortó antes de llegar a él.

Qué comprueba cada `403`: código, `tipo`, `motivo`, `mensaje` literal «Tu rol no permite esta operación.» (y que sea el `MENSAJE_ROL_INSUFICIENTE` de `cimenta.identidad.api.dependencias`), conjunto exacto de claves `{tipo, motivo, mensaje, roles_requeridos, correlacion_id}`, ausencia de `detail` y de `detalle`, `roles_requeridos` en el orden declarado, `correlacion_id` igual a la cabecera `X-Correlacion-Id` y validez contra `ErrorPermiso` del borrador. Cada `401`, igual, contra `ErrorSesion`.

| # | Test | Archivo | Tipo | Criterio |
|---|---|---|---|---|
| TC-60 | `test_tkt006_ca06_el_permiso_es_la_union_de_los_roles` (+ 3 complementos: `..._tener_un_rol_no_da_los_de_otras_rutas`, `..._un_solo_rol_no_alcanza_para_la_ruta_de_otro` y `..._una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos`) | `permisos_rol` | feliz y **rechazo** | `CA-6` esc. 2 |
| TC-61 | `test_tkt006_ca11_retirar_un_rol_surte_efecto` | `permisos_rol` | **rechazo** | `CA-11`, `M6` |
| TC-62 | `test_tkt006_ca12_rol_insuficiente_asentado_como_denegar` (+ 5 complementos: datos del asiento, sin correlación ni credencial de la cookie, solo `INSERT` sobre `bitacora`, método y ruta de la petición, y atribución con dos usuarios; y una comprobación de la llamada a `asentar_denegacion`) | `permisos_rol` | **rechazo** | `CA-12` esc. 1, `CA-13` esc. 3, `RN-04`, `CA-R1` |
| TC-63 | `test_tkt006_ca12_denegar_en_transaccion_propia` (a nivel de aplicación) y `test_tkt006_ca12_denegar_persiste_aunque_la_peticion_deshaga_la_suya` (por HTTP) | `permisos_rol` | **rechazo** | `CA-12` esc. 2 |
| TC-64 | `test_tkt006_ca12_si_la_bitacora_falla_sigue_en_403` (+ `..._el_fallo_de_la_bitacora_se_registra_sin_el_texto_de_la_excepcion` y `..._registrar_denegacion_no_propaga_el_fallo_de_la_bitacora`) | `permisos_rol` | **rechazo** | `CA-12` esc. 4, `PA-T6` |
| TC-65 | `test_tkt006_ca14_una_ruta_con_exigir_rol_cuenta_como_protegida` (2 formas; + `..._exigir_rol_no_abre_una_ruta_sin_sesion`) | `enrutador` (sin Docker) | feliz y **rechazo** | `CA-14` |
| TC-66 | `test_tkt006_ca07_exigir_rol_mal_declarado_falla_al_declarar` (+ 6 nombres inválidos y `..._acepta_los_seis_roles_del_contrato`) | `enrutador` (sin Docker) | **rechazo** | `M7` |
| TC-67 | `test_tkt006_ca12_sin_sesion_en_ruta_con_rol_es_401_sin_bitacora` (3 formas de cookie; + sesión caducada y revocada, y credenciales erróneas con petición sin cookie) | `permisos_rol` | **rechazo** | `CA-12` esc. 3 |
| CA-13 · M12 | `test_tkt006_ca13_la_interfaz_publica_exigir_rol_y_evaluar_resolucion` y `..._la_interfaz_se_importa_con_asterisco_y_se_documenta` | `enrutador` (sin Docker) | feliz | `CA-13`, `M12` |

Decisiones de las pruebas que el diseño no fija de forma literal:

- **TC-65 y TC-66 viven en `test_tkt006_enrutador.py`**, no en `test_tkt006_permisos_rol.py`: el diseño las marca «sin Docker» y el título de su sección asigna ese archivo a los casos sin Docker. La publicación en la interfaz (`__all__` y atributos) va también ahí, por la misma razón.
- **El asiento se comprueba con SQL, no con el ORM**: `datos_antes IS NULL` como expresión de SQL, para distinguir el `NULL` de SQL de un `null` de JSONB, que `psycopg` devolvería igual como `None`.
- **TC-62 comprueba también lo que no debe estar**: ni la correlación ni el identificador de la sesión (la credencial de la cookie, invariante 21) en ninguna columna del asiento; nada de la cadena de consulta (`?token=…`) en `ruta`; solo `INSERT` sobre `bitacora` (el oyente de sentencias de TC-R1, y el `INSERT` sí aparece).
- **TC-63 tiene dos versiones**: la del diseño (una `Session` exterior que inserta un usuario y hace `rollback`; el asiento ya es visible desde otra conexión **antes** del `rollback`) y una por HTTP, donde una dependencia de la ruta abre una transacción, escribe y la deshace al terminar, y `exigir_rol` lanza el `403` después.
- **TC-64 fija el contenido de la línea del registro técnico**: evento `denegacion_no_asentada`, nivel `error`, `correlacion_id` de la respuesta y `usuario_id` (como cadena, tal como lo escribe el diseño), y que la línea lleve el tipo de la excepción (`RuntimeError`) y **no** su mensaje (conv-seguridad §6; el procesador del registro resume por tipo y marcos).
- **TC-67 espía `asentar_denegacion`**: además de que la bitácora quede vacía, la función no se llama; así el caso no se pone verde por un fallo silencioso de la bitácora. El `401` va antes que el `403` también con la sesión caducada o cerrada.
- **TC-60 y TC-67 comprueban que lo permitido no asienta**: una petición con `200` deja la bitácora en cero.

### Rojo

Comando, desde `backend/`: `PYTHONUTF8=1 uv run pytest tests/test_tkt006_permisos_rol.py tests/test_tkt006_enrutador.py -p no:cacheprovider --tb=line -q` (salida abreviada: se omiten las líneas repetidas de traza y los nombres de los 16 casos que pasan).

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Documentos\LIDR\Proyecto Final\backend
...
tests\test_tkt006_permisos_rol.py:218: ImportError: cannot import name 'exigir_rol' from 'cimenta.identidad.interfaz' (D:\Documentos\LIDR\Proyecto Final\backend\cimenta\identidad\interfaz.py)
...  (21 casos de permisos_rol fallan igual; uno de ellos en tests\test_tkt006_permisos_rol.py:261, la ruta con transacción propia)
tests\test_tkt006_permisos_rol.py:329: ModuleNotFoundError: No module named 'cimenta.identidad.aplicacion.denegacion'
...  (2 casos de permisos_rol, los que llaman a registrar_denegacion sin HTTP)
tests\test_tkt006_enrutador.py:595: ImportError: cannot import name 'exigir_rol' from 'cimenta.identidad.interfaz' ...
...  (11 casos de enrutador fallan igual)
tests\test_tkt006_enrutador.py:734: ImportError: cannot import name 'evaluar_resolucion' from 'cimenta.identidad.interfaz' ...
...  (1 caso: el que importa los dos nombres falla por el primero que no encuentra)
=========================== short test summary info ===========================
FAILED tests/test_tkt006_permisos_rol.py::test_tkt006_ca06_el_permiso_es_la_union_de_los_roles
FAILED tests/test_tkt006_permisos_rol.py::test_tkt006_ca06_tener_un_rol_no_da_los_de_otras_rutas
FAILED tests/test_tkt006_permisos_rol.py::test_tkt006_ca06_un_solo_rol_no_alcanza_para_la_ruta_de_otro
FAILED tests/test_tkt006_permisos_rol.py::test_tkt006_ca06_una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos
FAILED tests/test_tkt006_permisos_rol.py::test_tkt006_ca11_retirar_un_rol_surte_efecto
FAILED tests/test_tkt006_permisos_rol.py::test_tkt006_ca12_rol_insuficiente_asentado_como_denegar
...  (17 líneas FAILED más de permisos_rol: TC-62 complementos, TC-63, TC-64 y TC-67)
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_con_exigir_rol_cuenta_como_protegida[en_el_decorador]
FAILED tests/test_tkt006_enrutador.py::test_tkt006_ca14_una_ruta_con_exigir_rol_cuenta_como_protegida[en_un_parametro]
...  (11 líneas FAILED más de enrutador: TC-65, TC-66 y la interfaz)
======================== 36 failed, 16 passed in 5.69s =========================
```

Por archivo, con el mismo comando: `test_tkt006_permisos_rol.py` → `23 failed in 17.45s`; `test_tkt006_enrutador.py` → `13 failed, 16 passed in 1.42s`. Los 16 que pasan son los casos existentes de la fila 7 (TC-47 a TC-53 y complementos), sin cambios.

### Razón de cada fallo

| Casos | Razón | ¿Esperada? |
|---|---|---|
| 21 casos HTTP y de aplicación de `permisos_rol` (TC-60, TC-61, TC-62 y sus complementos, TC-63 por HTTP, TC-64 por HTTP y TC-67) | `ImportError: cannot import name 'exigir_rol' from 'cimenta.identidad.interfaz'`, lanzado dentro de `agregar_rutas_de_prueba` (o de `agregar_ruta_con_transaccion_propia`), después de que el arnés levantó PostgreSQL, migró y conectó con el rol de aplicación. `interfaz.py` existe, pero solo con su docstring | Sí: es el rojo que el diseño anuncia |
| 2 casos de `permisos_rol` que llaman a `registrar_denegacion` sin HTTP (TC-63 y TC-64 a nivel de aplicación) | `ModuleNotFoundError: No module named 'cimenta.identidad.aplicacion.denegacion'`. Fallan más tarde que los HTTP: antes ya sembraron el usuario y, en TC-63, abrieron la transacción exterior | Sí: el módulo de la fila no existe |
| 11 casos de `enrutador` (TC-65 ×3 y TC-66 ×8, el de los seis roles incluido) | `ImportError: cannot import name 'exigir_rol' from 'cimenta.identidad.interfaz'` | Sí |
| 2 casos de `enrutador` de la publicación en la interfaz | `ImportError` de `evaluar_resolucion` o de `exigir_rol`: el `from ... import` los pide antes de mirar `__all__` | Sí. El rojo es por importación y no por `AttributeError` de `__all__`, a propósito |

Ningún fallo es de entorno, de sintaxis, de Docker ni de otra importación: el arnés de `testcontainers` funcionó en los 23 casos de `permisos_rol`. **Ningún caso nace en verde**: los 16 que pasan en `enrutador` son los preexistentes. Los errores de `mypy` sobre los dos archivos son todos `attr-defined` sobre `cimenta.identidad.interfaz` o `import-not-found` sobre `denegacion`, los mismos del rojo de las filas anteriores, y desaparecen con el verde; `uv run ruff check` y `uv run ruff format --check` pasan sobre los dos archivos.

### Comprobación del oráculo, fuera del repositorio

Para demostrar que los tests exigen lo que el diseño dice y no más, se copió el árbol a la carpeta temporal de la sesión y se escribieron allí `exigir_rol`, `MENSAJE_ROL_INSUFICIENTE`, `aplicacion/denegacion.py` e `interfaz.py` con los cuerpos literales de «Capas afectadas» del diseño (ese código **no** está en el repositorio). Resultado sobre la copia: los dos archivos, **52 passed** (36 casos de la fila y 16 preexistentes).

Una primera pasada sobre la copia dejó un caso rojo, `test_tkt006_ca12_el_asiento_lleva_el_metodo_y_la_ruta_de_la_peticion`: dos asientos con el mismo `ocurrido_en` salían en orden libre al ordenar por `ocurrido_en, id`. Era un defecto de la prueba, no del diseño; se corrigió avanzando el reloj un minuto entre las dos peticiones y se repitió la pasada completa.

Mutantes aplicados a la copia, de uno en uno, y lo que cayó (los de la tabla del diseño se ejecutarán sobre el código real en la fila 11):

| Mutante sobre la copia | Casos que caen |
|---|---|
| MT-11 `rol_suficiente` con `issubset` | `ca06_el_permiso_es_la_union_de_los_roles`, `ca11_retirar_un_rol_surte_efecto` |
| MT-13 `exigir_rol` sin llamar a `registrar_denegacion` | 11 casos, entre ellos `ca12_rol_insuficiente_asentado_como_denegar`, `ca12_denegar_persiste_aunque_la_peticion_deshaga_la_suya` y `ca12_si_la_bitacora_falla_sigue_en_403` |
| MT-14 `registrar_denegacion` vuelve a lanzar | `ca12_si_la_bitacora_falla_sigue_en_403` y `ca12_registrar_denegacion_no_propaga_el_fallo_de_la_bitacora` |
| MT-21 `datos` con `correlacion_id` | `ca12_los_datos_del_asiento_denegar`, `ca12_el_asiento_no_lleva_correlacion_ni_la_credencial_de_la_cookie` y la comprobación de la llamada a la bitácora |
| `metodo` fijo en `"GET"` | `ca12_el_asiento_lleva_el_metodo_y_la_ruta_de_la_peticion` |
| `ruta` con la cadena de consulta (`str(request.url)`) | `ca12_los_datos_del_asiento_denegar`, `ca12_el_asiento_lleva_el_metodo_y_la_ruta_de_la_peticion` y la llamada a la bitácora |
| `ocurrido_en` un segundo antes del reloj | `ca12_rol_insuficiente_asentado_como_denegar` y la llamada a la bitácora |
| siempre `403` | `ca06_el_permiso_es_la_union_de_los_roles`, `ca06_un_solo_rol_no_alcanza_para_la_ruta_de_otro`, `ca06_una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos` y `ca11_retirar_un_rol_surte_efecto` |
| nunca `403` | 14 casos |
| mensaje distinto del literal | 8 casos |
| `comprobar_rol` apoyado en una copia de `sesion_vigente` en vez de `sesion_vigente` | los tres casos de TC-65 de `enrutador` |

Ningún mutante sobrevivió. Los mutantes de `ocurrido_en`, `metodo` y `ruta` no los pide el diseño: se añadieron porque ninguno de MT-10 a MT-14 ni MT-21 los cubre. MT-10 (`roles_de` con caché) no se ejecutó sobre la copia: el diseño lo asigna a TC-61 y se aplica sobre el código real en la fila 11.

**Tests devueltos al tester:** ninguno. **Verde** — pendiente: `exigir_rol` y `MENSAJE_ROL_INSUFICIENTE` en `api/dependencias.py`, `aplicacion/denegacion.py` e `interfaz.py` con el `__all__` de seis nombres.

## Fila 10 · verde y refactor

Se escribió el código literal del diseño («Capas afectadas · API» y «Aplicación»), sin tocar ningún test ni `conftest.py`.

- `exigir_rol(*roles)` y `MENSAJE_ROL_INSUFICIENTE` en `backend/cimenta/identidad/api/dependencias.py`. Se apoya en `sesion_vigente`, así que sin sesión responde `401` antes que `403`. Los roles se validan contra `contrato_error.Rol` al declarar la dependencia: sin roles o con un rol desconocido lanza `ValueError`. Si la unión de roles de quien llama no cumple `rol_suficiente`, llama a `registrar_denegacion` y lanza `PermisoDenegado` con motivo `ROL_INSUFICIENTE`. `Request`, `UsuarioAutenticado` y `sesion_vigente` son importaciones reales del módulo, porque con `from __future__ import annotations` FastAPI resuelve las anotaciones en tiempo de ejecución.
- `backend/cimenta/identidad/aplicacion/denegacion.py`: `registrar_denegacion` abre su propia transacción con `sessionmaker.begin()` y llama a `auditoria.asentar_denegacion` como atributo del módulo `cimenta.auditoria.interfaz`. Los datos son `{metodo, ruta, roles_requeridos}`, sin `correlacion_id`. Si falla, registra `denegacion_no_asentada` con nivel `error`, la correlación, el usuario como cadena y la traza resumida por tipo, y la petición sigue en `403` (PA-T6).
- `backend/cimenta/identidad/interfaz.py`: `__all__` con los seis nombres y un docstring que nombra `exigir_rol`, `evaluar_resolucion` y `AUTO_RESOLUCION`.

Refactor: ninguno; el código del diseño ya era el mínimo.

### Salida real

`uv run pytest tests/test_tkt006_permisos_rol.py tests/test_tkt006_enrutador.py -q`, con Docker:

```text
....................................................                     [100%]
52 passed in 9.20s
```

`uv run pytest tests/test_tkt006_*.py tests/test_servidor_arranque.py tests/test_contrato_error_http.py -q`:

```text
343 passed in 37.65s
```

Nada de la entrega A se rompió, y TC-47 sigue viendo `sesion_vigente` en la cadena de las rutas con `exigir_rol`.

| Comprobación | Resultado |
|---|---|
| `uv run mypy .` | `Success: no issues found in 153 source files` |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check .` | `153 files already formatted` |
| `uv run python -m herramientas.verificar_float` | `archivos revisados: 18; hallazgos: 0` |
| `uv run lint-imports` | `Contracts: 15 kept, 0 broken.` |

**Desviaciones:** ninguna. `interfaz.py` ya existía con un docstring de dos líneas, que se sustituyó. **Tests devueltos al tester:** ninguno. Pendiente de la fila 11: mutación de MT-10 a MT-14 y MT-21 sobre el código real.

## Fila 11 · mutación y regresión (entrega B)

Fila sin código de producción. Se aplicaron los mutantes `MT-10` a `MT-14` y `MT-21` de la entrega B, más seis propios de esta fila sobre `exigir_rol` y `registrar_denegacion` y dos variantes de `MT-10` y `MT-11`. Un mutante, el `MT-10` literal del diseño, dejó la suite en verde: se investigó, resultó equivalente en la forma que pedía el diseño y se añadió el test que lo mata (ver «Sobreviviente»). Los archivos de producción quedaron byte a byte como estaban.

**Método.** El mismo arnés de la fila 9 (`aplicar`, `correr` y `sha`, fuera del repositorio), con una variante que tolera finales de línea CRLF en el archivo a mutar: calcula el SHA-256, comprueba que cada fragmento a sustituir aparece exactamente una vez, escribe el archivo mutado, ejecuta los diez archivos `tests/test_tkt006_*.py` completos con Docker y `PYTHONUTF8=1`, restaura los bytes originales dentro de un `finally` y calcula de nuevo el SHA-256. La orden hablaba de once archivos; el ticket tiene **diez** (`cierre`, `configuracion`, `csrf`, `dominio`, `enrutador`, `esquema`, `inicio_sesion`, `permisos_rol`, `repositorio` y `sesion_vigente`). La línea base, antes de empezar, era `254 passed in 29.14s`. Los cuatro archivos de producción de la fila tienen finales de línea LF.

**SHA-256 de cada archivo antes de mutar** (idéntico después de cada restauración y al terminar la fila, comprobado de nuevo con `sha256sum`):

| Archivo | SHA-256 |
|---|---|
| `backend/cimenta/identidad/infraestructura/repositorio.py` | `dfaccc56f822c8e70456163dab1c20119ee41385d7818e3c5d817d564874a5eb` |
| `backend/cimenta/identidad/dominio/autorizacion.py` | `9aaf1ccc1b3fc8b5b18158f7ae5d433b36f5e50beecf8961c62245f7b657aa0f` |
| `backend/cimenta/identidad/aplicacion/denegacion.py` | `ff0299b95363ffc8a88721020565925bcfcd0c00e1b337c3bfd4d894a77b9e9b` |
| `backend/cimenta/identidad/api/dependencias.py` | `872d8411b7fb7e8a949be7f18d378f66727ed8ce49120c97a252e2719d21834c` |

### Tabla de mutantes

SHA mutado: los primeros 12 caracteres. El SHA «antes» y el «después» son los de la tabla anterior y coincidieron en los 15 casos (14 mutantes más la repetición de `MT-10`). Los nombres de «Cae» son `test_tkt006_<...>` abreviados.

| Mutante | Archivo | Mutación | SHA mutado | Debe caer | Cae (salida resumida) | Restaurado |
|---|---|---|---|---|---|---|
| MT-10 (1.ª vez) | `repositorio.py` | `roles_de` envuelto en `functools.cache`, tal como dice el diseño | `0530aab0ed67` | TC-61 | **Nada: `254 passed`. Sobrevive.** La clave de la caché es `(Session, usuario_id)` y cada petición abre su propia `Session`, así que nunca hay un acierto de caché: el mutante es equivalente a nivel de petición. Ver «Sobreviviente» | sí |
| MT-10 (2.ª vez, con el test nuevo) | `repositorio.py` | el mismo | `0530aab0ed67` | TC-61 | `ca11_roles_de_lee_la_base_en_cada_llamada` (test nuevo, nivel de repositorio) · `1 failed, 254 passed` | sí |
| MT-10b | `repositorio.py` | `roles_de` con caché por `usuario_id` que no depende de la `Session` (la forma que sí tendría efecto entre peticiones) | `b040b94c566e` | TC-61 | `ca11_retirar_un_rol_surte_efecto` (TC-61), `ca11_retirar_un_rol_se_ve_en_la_peticion_siguiente` y `ca11_aplicacion_validar_lee_los_roles_en_cada_peticion` · `3 failed, 251 passed` | sí |
| MT-11 | `autorizacion.py` | `rol_suficiente` con `roles_requeridos.issubset(roles_de_quien_llama)` | `a6153d3cb43b` | TC-11, TC-60 | `ca06_permiso_es_la_union[basta-uno-de-los-requeridos]` y `[ruta-sin-roles-requeridos]` (TC-11), `ca06_una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos` (TC-60) · `3 failed, 251 passed` | sí |
| MT-11b | `autorizacion.py` | `rol_suficiente` con `roles_de_quien_llama.issubset(roles_requeridos)` (la otra dirección) | `31dabcdfaf03` | TC-11, TC-60 | `ca06_permiso_es_la_union[basta-el-primero]`, `[basta-el-segundo]` y `[sin-ningun-rol]` (TC-11), `ca06_el_permiso_es_la_union_de_los_roles` (TC-60) y `ca11_retirar_un_rol_surte_efecto` (TC-61) · `5 failed, 249 passed` | sí |
| MT-12 | `autorizacion.py` | `evaluar_resolucion` con `!=` en lugar de `==` | `485bd346a034` | TC-09, TC-10 | `ca13_quien_solicito_no_resuelve` (TC-09) y `ca13_otra_persona_puede_resolver` (TC-10) · `2 failed, 252 passed` | sí |
| MT-13 | `dependencias.py` | `exigir_rol` sin llamar a `registrar_denegacion` | `aa6d6533b113` | TC-62 | `ca12_rol_insuficiente_asentado_como_denegar` (TC-62), `ca12_los_datos_del_asiento_denegar`, `ca12_el_asiento_no_lleva_correlacion_ni_la_credencial_de_la_cookie`, `ca12_denegar_solo_inserta_en_la_bitacora`, `ca12_el_asiento_lleva_el_metodo_y_la_ruta_de_la_peticion`, `ca12_cada_denegacion_deja_su_asiento_y_a_nombre_de_quien_se_denego`, `ca12_una_denegacion_llama_una_vez_a_la_bitacora_con_los_argumentos_del_contrato`, `ca12_denegar_persiste_aunque_la_peticion_deshaga_la_suya`, `ca12_si_la_bitacora_falla_sigue_en_403` (TC-64), `ca12_el_fallo_de_la_bitacora_se_registra_sin_el_texto_de_la_excepcion` y `ca06_una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos` · `11 failed, 243 passed` | sí |
| MT-14 | `denegacion.py` | `registrar_denegacion` vuelve a lanzar la excepción | `44523de91d8d` | TC-64 | `ca12_si_la_bitacora_falla_sigue_en_403` (TC-64) y `ca12_registrar_denegacion_no_propaga_el_fallo_de_la_bitacora` · `2 failed, 252 passed` | sí |
| MT-21 | `denegacion.py` | `registrar_denegacion` añade `correlacion_id` a `datos` | `27e0668a252d` | TC-62 | `ca12_los_datos_del_asiento_denegar` y `ca12_el_asiento_no_lleva_correlacion_ni_la_credencial_de_la_cookie` (claves exactas de TC-62) y `ca12_una_denegacion_llama_una_vez_a_la_bitacora_con_los_argumentos_del_contrato` · `3 failed, 251 passed`. El caso que lleva el nombre `ca12_rol_insuficiente_asentado_como_denegar` no cae; las claves exactas de `datos_despues` las afirman los otros dos | sí |
| MT-F1 | `dependencias.py` | `exigir_rol` comprueba `usuario.roles.issubset(conjunto)` en lugar de la intersección | `42167d8b5dd2` | propio | `ca06_el_permiso_es_la_union_de_los_roles` (TC-60, quien tiene `COMPRAS` y `ALMACEN` deja de entrar) y `ca11_retirar_un_rol_surte_efecto` (TC-61) · `2 failed, 252 passed` | sí |
| MT-F1b | `dependencias.py` | `exigir_rol` comprueba `conjunto.issubset(usuario.roles)` (exige todos los roles de la ruta) | `433505056eec` | propio | `ca06_una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos` (TC-60, la ruta de `COMPRAS` o `DIRECCION_GENERAL` rechaza a quien solo tiene `DIRECCION_GENERAL`) · `1 failed, 253 passed`. Con una ruta de un solo rol es indistinguible de la correcta: solo esa ruta de dos roles lo detecta | sí |
| MT-F2 | `dependencias.py` | `exigir_rol` ignora el 401: depende de una versión de `sesion_vigente` que atrapa `SesionInvalida`, devuelve `None` y deja pasar | `ca4e20488e0e` | propio (TC-67) | `ca12_sin_sesion_en_ruta_con_rol_es_401_sin_bitacora[sin_cookie]`, `[uuid_inexistente]` y `[mal_formada]` (TC-67), `ca12_sesion_caducada_o_revocada_en_ruta_con_rol_es_401_sin_bitacora[caducada]` y `[revocada]`, `ca12_credenciales_erroneas_y_ruta_con_rol_sin_cookie_no_asientan`, `ca14_exigir_rol_no_abre_una_ruta_sin_sesion` y `ca14_una_ruta_con_exigir_rol_cuenta_como_protegida[en_el_decorador]` y `[en_un_parametro]` (TC-65, sin Docker) · `9 failed, 245 passed` | sí |
| MT-F3 | `denegacion.py` | `registrar_denegacion` no asienta nada (`return` al entrar): el 403 sin asentar, a nivel de aplicación | `3715dd12121b` | propio (TC-62, TC-63) | Los mismos nueve casos que `MT-13` más `ca12_denegar_en_transaccion_propia` (TC-63) y `ca12_registrar_denegacion_no_propaga_el_fallo_de_la_bitacora` · `13 failed, 241 passed` | sí |
| MT-F4 | `dependencias.py` | `exigir_rol` no valida los roles contra `Rol` (`tuple(roles)`) | `ee3c7b5f7c46` | propio (TC-66) | `ca07_exigir_rol_mal_declarado_falla_al_declarar` (TC-66) y los seis casos de `ca07_exigir_rol_rechaza_cualquier_nombre_que_no_sea_un_rol_exacto` · `7 failed, 247 passed` | sí |
| MT-F5 | `dependencias.py` | `exigir_rol` acepta cero roles (sin el `ValueError`) | `b2ab4fa4daac` | propio (TC-66) | `ca07_exigir_rol_mal_declarado_falla_al_declarar` (TC-66) · `1 failed, 253 passed` | sí |

### Sobreviviente: `MT-10` literal

El diseño dice «`roles_de` envuelto en `functools.cache`» y espera que caiga TC-61. Aplicado tal cual, **la suite quedó en verde** (`254 passed in 28.65s`). La causa no es un test débil de HTTP sino que el mutante, así escrito, no cambia el comportamiento de ninguna petición: `functools.cache` incluye todos los argumentos en la clave, y el primero es la `Session` (`bd`). Cada petición abre la suya con `fabrica_sesiones().begin()`, de modo que la clave nunca se repite y la caché nunca acierta. TC-61 y sus dos hermanos están bien planteados: cuando el mutante sí tiene efecto entre peticiones (`MT-10b`, caché por `usuario_id`), caen los tres.

Aun así, la regla «los roles se leen en cada petición» (`CA-11`, regla 9) la sostiene en el repositorio una función sin ninguna prueba que la fije a ese nivel: bastaba que alguien reutilizara una `Session` entre llamadas para que la caché literal fuera real y ningún test lo notara. Se añadió **un test** a `backend/tests/test_tkt006_repositorio.py`, `test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada`: con la misma `Session`, llama a `roles_de`, borra el rol `COMPRAS` en esa misma transacción y llama de nuevo; la segunda llamada debe devolver solo `RESIDENTE`. Es un test de infraestructura que no toca producción y nace en verde porque el repositorio ya cumple; su prueba de que depende de algo es el propio `MT-10` literal, que ahora cae con `1 failed, 254 passed`. Se movió la importación de `text` a la cabecera del archivo para que `ruff` quede en cero. Con el test añadido, la suite de este ticket pasa de 254 a 255 casos. `MT-10b` se ejecutó con la suite de 254; con el test nuevo cae además este caso.

**Sobrevivientes al cerrar la fila: ninguno.**

**Observaciones.**

- **`MT-13` y `MT-F3` miden lo mismo desde dos capas.** `MT-13` quita la llamada en `exigir_rol` y `MT-F3` la deja pero vacía su cuerpo. Los casos que caen en los dos son los de asiento (TC-62 y sus complementos); solo `MT-F3` rompe TC-63 (transacción propia) y el caso de que `registrar_denegacion` no propague el fallo, que `MT-13` no ejerce porque la función nunca se llama.
- **`MT-21` y TC-62.** El diseño dice que cae TC-62. El caso con ese nombre no cae: afirma la fila de bitácora por sus columnas y por `datos_despues`, pero las claves exactas `{metodo, ruta, roles_requeridos}` las comprueban `los_datos_del_asiento_denegar` y `el_asiento_no_lleva_correlacion_ni_la_credencial_de_la_cookie`, que forman parte de TC-62 y sus complementos. El mutante cae donde el diseño quería, y no hace falta tocar ningún test.
- **`MT-F2`.** Lo mutado deja `sesion_vigente` intacta y cambia la dependencia de `exigir_rol` por una versión laxa; por eso TC-65 (sin Docker) también cae, y TC-47 de la fila 9 no se ve afectado.
- **Pureza del dominio.** `MT-11`, `MT-11b` y `MT-12` no añaden importaciones: `ca13_dominio_de_identidad_puro` y `ca13_contrato_dominio_sin_framework_se_cumple` siguieron en verde.

### Regresión (TC-R1 a TC-R7)

Desde `backend/`, con `PYTHONUTF8=1`, Docker en marcha (servidor 29.8.2) y los cuatro archivos restaurados y comprobados por SHA-256. La suite del ticket tiene ya 255 casos por el test añadido.

```text
TC-R1  uv run pytest tests/test_identidad_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_lectura_sin_secretos.py tests/test_tkt006_cierre.py tests/test_tkt006_permisos_rol.py
       49 passed in 10.22s         (TC-46 en test_tkt006_cierre.py; en test_tkt006_permisos_rol.py, ca12_denegar_solo_inserta_en_la_bitacora:
                                    el oyente de sentencias de TC-62 no ve UPDATE ni DELETE sobre bitacora)
TC-R2  uv run pytest tests/test_identidad_migracion_ciclo.py tests/test_identidad_semilla.py tests/test_identidad_migracion_cli.py tests/test_tkt006_esquema.py
       18 passed in 6.00s          (TC-57 en test_tkt006_esquema.py)
TC-R3  uv run lint-imports                       -> Contracts: 15 kept, 0 broken.   (código 0; eran 15 antes del ticket)
       uv run pytest tests/test_fronteras_dominio.py tests/test_tkt005_fronteras.py
       24 passed in 11.92s
       grep -c ignore_imports pyproject.toml     -> 0
TC-R4  uv run ruff check .                       -> All checks passed!                              (código 0)
       uv run ruff format --check .              -> 153 files already formatted                     (código 0)
       uv run mypy .                             -> Success: no issues found in 153 source files    (código 0)
       uv run python -m herramientas.verificar_float -> archivos revisados: 18; hallazgos: 0        (código 0)
TC-R5  TC-24, TC-34, TC-45 y TC-61 afirman `"detail" not in cuerpo` (test_tkt006_inicio_sesion.py, test_tkt006_sesion_vigente.py,
       test_tkt006_cierre.py y test_tkt006_permisos_rol.py, líneas 896/1279, 972, 98 y 138/153), y pasan en la suite completa.
TC-R6  uv run pytest tests/test_contrato_error_http.py tests/test_servidor_arranque.py
       89 passed in 9.45s          (TC-53 y TC-77 de TKT-005, con la identidad montada)
```

Suite completa, `uv run pytest -p no:cacheprovider` con Docker, código de salida 0:

```text
tests\test_tkt007_dominio_consulta.py .................................. [ 94%]
...
tests\test_tkt007_esquema.py ........................                    [ 96%]
tests\test_tkt007_fronteras.py ........                                  [ 97%]
tests\test_tkt007_motor.py .....                                         [ 97%]
tests\test_verificar_float.py .......................                    [100%]

====================== 1126 passed in 224.86s (0:03:44) =======================
```

Son 37 casos más que los 1089 de la fila 9: los de `test_tkt006_permisos_rol.py` y `test_tkt006_enrutador.py` de la fila 10 y el test añadido en esta fila. `test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf` (en `tests/test_tkt005_regresion.py`) pasa dentro de la suite completa.

**TC-R7 (documentación, desde la raíz).**

- `python tools/extraer_mermaid.py` → código 0: 30 diagramas, escribe `tools/mermaid-check.html` (ignorado por `.gitignore`).
- `python -m unittest discover -s tools/tests -v` → `Ran 6 tests ... OK`, código 0.
- `python tools/verificar_docs.py` → **código 1, un problema, el conocido**: `Enlace roto · sdd\tickets\tkt-006\impl.md → delta.md`, el enlace «Siguiente: delta →» de la cabecera, que apunta a un `delta.md` que no existe hasta el cierre del ticket. Se corrige en la fila 12 y en `/sdd-completar`. Conteos: 22 ADR, 38 invariantes, 162 escenarios, 111 archivos de codificación, sin otros problemas.

**Verificación de que no queda ningún archivo mutado.** `sha256sum` de los cuatro archivos tras la última restauración coincide con la tabla inicial. `git status --short` lista los mismos 6 archivos modificados y los mismos 28 sin seguimiento de antes de la fila, y `git diff --stat` solo muestra `interfaz.py`, `pyproject.toml`, `servidor/fabrica.py`, `tests/conftest.py`, `tests/test_servidor_arranque.py` y `uv.lock`, todos de filas anteriores. Los archivos de `identidad/` no están en el índice, así que `git diff` no los ve: la garantía es el SHA-256, más la suite completa, `ruff`, `mypy` y `lint-imports` en verde sobre el árbol restaurado.

**Tests devueltos al tester:** ninguno. **Tests añadidos en esta fila:** uno, `test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada`, en `backend/tests/test_tkt006_repositorio.py`. **Tests modificados:** ninguno.

## Fila 12 · documentación y ADR (entrega B)

Los textos de «Documentación afectada» y «¿Merece ADR?» del diseño se aplicaron tal cual, por sustitución del orquestador con `conv-documentacion`: primero el ADR y su fila del índice, después el resto. No se tocó código de producción, ni tests, ni `docs/api/openapi.yaml`. Antes de editar cada documento se comprobó que su texto no estaba aplicado: ninguna fila de la tabla A había entrado aún, así que no hubo nada que no duplicar.

### Qué se cambió

| Archivo | Cambio |
|---|---|
| `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md` | Nuevo. ADR-023 en MADR, `Aceptado`, con las opciones descartadas del diseño y sus consecuencias |
| `docs/adr/README.md` | Fila del índice (2026-10-21, `Todo el backend`). El índice pasa a 23 entradas |
| `CLAUDE.md`, `README.md`, `llms.txt` | 22 → 23 decisiones o ADR |
| `docs/05-tickets-trabajo.md` | TKT-006: depende de TKT-007, criterio del token CSRF emitido y non-goal reescrito. TKT-026: la regla de no-auto-autorización la implementa TKT-006 como `evaluar_resolucion` |
| `docs/07-especificacion-api.md` §4.1 | `GET /sesion/csrf` pasa a `TKT-006, TKT-057`; una frase al final del párrafo de la cookie |
| `docs/02-arquitectura.md` §7.1 y §12 | Párrafo «Cómo se aplica» con la referencia a ADR-023, y su fila en la tabla de decisiones |
| `docs/03-modelo-datos.md` §10 | `usuario.email` en minúsculas, con `ck_usuario_email_minusculas` (TKT-006) |
| `.env.example` | Línea nueva en la cabecera y bloque «Sesión y contraseñas · TKT-006» con las cinco variables comentadas |
| `docs/arranque-local.md` | `uv run --env-file ../.env fastapi dev` con la frase sobre el `500` sin entorno; nota de que no hay alta de usuarios (`PA-T13`) |
| `.claude/skills/conv-backend-fastapi/SKILL.md` | §9 «Cómo se protege una ruta» |
| `.claude/skills/conv-seguridad/SKILL.md` §2 | Frase sobre `sesion_vigente` y la lectura de roles en cada petición |
| `sdd/tickets/tkt-006/design.md` | «Orden de implementación»: `✓ Hecho` en las filas 1, 2, 4, 5, 6, 8, 9, 10, 11 y 12; `⚠ Ajustado` en las filas 3 y 7. Fila nueva en «Decisiones sobre las preguntas abiertas» con la decisión del usuario del 2026-10-22 sobre la validación del correo |
| `sdd/tickets/tkt-006/impl.md` | Cabecera: «Siguiente» pasa a texto plano `delta.md`, que escribe `/sdd-completar`, igual que en TKT-007 |

`docs/api/openapi.yaml` y el glosario no cambian, como indica el diseño.

### Salida de los verificadores

`python tools/verificar_docs.py`, desde la raíz con `PYTHONUTF8=1`:

```text
Documentos analizados: 111

  enlaces relativos    996
  anclas internas      462
  reglas                25
  requisitos no funcionales    19
  preguntas             23
  funcionalidades       52
  historias              9
  tickets               69
  adrs                  23
  invariantes           38
  story points          79
  escenarios           162
  codificación         112

✓ Sin problemas.
```

Código de salida 0. El problema conocido de la fila 11 (el enlace «Siguiente: delta →») desaparece con el cambio de la cabecera.

`python tools/extraer_mermaid.py`: `30 diagramas encontrados`, `Escrito: tools/mermaid-check.html`. Código de salida 0.

`python -m unittest discover -s tools/tests -v`: `Ran 6 tests in 0.014s`, `OK`. Código de salida 0.

### Lo que no se aplicó

Nada de la lista del diseño quedó sin aplicar. Dos cosas que este cambio no toca y conviene revisar: el «Ajustes respecto al design» de la cabecera de este `impl.md` sigue diciendo «Ninguno» y «Qué se implementó» sigue «En curso» (son de la fila 1 y no se han actualizado), y `CLAUDE.md`, línea 106, sigue mostrando `uv run fastapi dev` sin `--env-file ../.env`, a diferencia de `docs/arranque-local.md`.

## Revisión · ciclo 1 · fragilidad de codificación en un test

**Hallazgo** (auditor de seguridad, confirmado por el orquestador): `tests/test_tkt006_dominio.py::test_tkt006_ca13_contrato_dominio_sin_framework_se_cumple` falla en Windows cuando no está fijado `PYTHONUTF8=1`. El subproceso que ejecuta `lint-imports` escribe en la página de códigos de la consola (cp1252) y el test lo decodifica como UTF-8.

**Causa.** Los demás archivos que lanzan `lint-imports` (`test_tkt007_dominio.py`, `test_tkt007_fronteras.py`, `test_tkt005_fronteras.py`, `test_fronteras_dominio.py`) definen `ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}` y lo pasan como `env=ENTORNO`, de modo que el subproceso escribe en UTF-8 y la decodificación `encoding="utf-8"` coincide. El test de TKT-006 copió el `encoding="utf-8"` pero no el `env`.

**Rojo (reproducción, sin `PYTHONUTF8` ni `PYTHONIOENCODING`).** `uv run pytest tests/test_tkt006_dominio.py -q -k contrato_dominio_sin_framework`:

```text
>       salida = proceso.stdout + proceso.stderr
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'

tests\test_tkt006_dominio.py:369: TypeError
  ...
  PytestUnhandledThreadExceptionWarning: Exception in thread Thread-1 (_readerthread)
    File "<frozen codecs>", line 325, in decode
  UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe1 in position 203: invalid continuation byte
FAILED tests/test_tkt006_dominio.py::test_tkt006_ca13_contrato_dominio_sin_framework_se_cumple
1 failed, 36 deselected, 1 warning in 0.55s
```

El hilo lector de `subprocess` muere con `UnicodeDecodeError` y `proceso.stdout` queda en `None`; el `TypeError` es el síntoma visible.

**Arreglo (solo en el test).** `import os`, la constante `ENTORNO` con el mismo valor que en los otros cuatro archivos y `env=ENTORNO` en la llamada a `subprocess.run`. No se tocó código de producción ni otro test.

**Verde.**

| Comando | Entorno | Resultado |
|---|---|---|
| `uv run pytest tests/test_tkt006_dominio.py -q -k contrato_dominio_sin_framework` | sin `PYTHONUTF8` | `1 passed, 36 deselected in 0.41s` |
| `uv run pytest tests/test_tkt006_dominio.py tests/test_tkt006_enrutador.py tests/test_tkt006_configuracion.py -q` | sin `PYTHONUTF8` | `109 passed in 2.21s` |
| El mismo comando | `PYTHONUTF8=1` | `109 passed in 2.27s` |
| `uv run pytest tests/test_tkt007_dominio.py tests/test_tkt007_fronteras.py tests/test_tkt005_fronteras.py tests/test_fronteras_dominio.py -q` | sin `PYTHONUTF8` | `86 passed in 15.84s` |
| `uv run ruff check .` | — | `All checks passed!` |
| `uv run ruff format --check .` | — | `153 files already formatted` |

**Otros subprocesos de `tests/test_tkt006_*.py`.** Se revisaron los diez archivos del ticket: solo `test_tkt006_dominio.py` importa `subprocess` y lanza uno. No hay otro con la misma fragilidad.

## Revisión · ciclo 1 · F001 a F004 de arquitectura

Corrección de los cuatro hallazgos Menores de `auditor-arquitectura`. Son ediciones de texto en `impl.md`, `CLAUDE.md`, el ADR-023 y `docs/05-tickets-trabajo.md`: no se tocó código de `cimenta/` ni ningún test.

| Hallazgo | Qué cambió | Archivo | Estado |
|---|---|---|---|
| F001 · «Qué se implementó» decía «En curso» y «Ajustes» decía «Ninguno» | Ambas secciones reescritas con el estado de las entregas A y B y con los ajustes de las filas 3, 7 y 11 que constan en este `impl.md` y en `design.md`. «Resultado» y «Verificación final» no se tocaron | `sdd/tickets/tkt-006/impl.md` | Corregido |
| F002 · `uv run fastapi dev` sin `--env-file` en CLAUDE.md | La línea pasa a `uv run --env-file ../.env fastapi dev`, como en `docs/arranque-local.md`; el comentario no cambia | `CLAUDE.md` | Corregido |
| F003 · ADR-023 con dos afirmaciones inexactas | (a) `validar_sesion` abre su propia transacción y conexión antes que cualquier otra de la petición. (b) La prueba de mutación ejecutó solo MT-9 (guarda `revocada_en IS NULL`); TC-32 y TC-38 cubren el deslizamiento de `ultima_actividad`, sin mutante propio | `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md` | Corregido |
| F004 · TKT-026 atribuía la falta de rol a la función pura del criterio técnico 1 | El criterio 1 dice que la falta de rol es `ROL_INSUFICIENTE` y la decide `api/` con `exigir_rol`; `evaluar_resolucion` cubre solo `AUTO_RESOLUCION` y no recibe roles. El criterio 2 se ajusta para ser coherente con él | `docs/05-tickets-trabajo.md` | Corregido |

**Verificación:** `python tools/verificar_docs.py` → `✓ Sin problemas.` (111 documentos, 23 ADR, 38 invariantes, 162 escenarios). `python tools/extraer_mermaid.py` → 30 diagramas, código 0. `python -m unittest discover -s tools/tests -v` → `Ran 6 tests`, `OK`, código 0.

## Revisión · ciclo 2 · F003, F004 y fila 11

Corrección de tres hallazgos Menores de la reauditoría de arquitectura. Son ediciones de texto en el ADR-023, en `docs/05-tickets-trabajo.md` (TKT-026) y en `design.md`: no se tocó código de `cimenta/` ni ningún test.

| Hallazgo | Qué cambió | Archivo | Estado |
|---|---|---|---|
| F003 · «La prueba de mutación ejecutó solo MT-9» no era cierta | La frase se reescribe con la tabla de mutación oficial: MT-9 es el único mutante sobre la guarda `revocada_en IS NULL`, ninguno quita la escritura de `ultima_actividad`, y TC-32 y TC-38 cubren el deslizamiento sin mutante propio. La parte (a) no se tocó | `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md` | Corregido |
| F004 · TKT-026 atribuía a `dominio/` la comprobación del rol | «Qué hace» escribe en `dominio/` solo la prohibición de resolver lo propio; el rol lo comprueba `api/` con `exigir_rol` (TKT-006). En el criterio 1 se quita el `rol_autorizador` y se fija la firma real `evaluar_resolucion(*, solicitante_id, resolutor_id)`, sin roles. En la cita final se dice «este ticket escribe solo la segunda». La frase de justificación del bloque se ajusta a lo mismo: lo que sobrevive a una ruta sin dependencia es la prohibición de resolver lo propio, no el rol. Sin cambios en los demás criterios ni en el resto del ticket | `docs/05-tickets-trabajo.md` | Corregido |
| F001-N1 · fila 11 de «Orden de implementación» marcada `✓ Hecho` | Estado cambiado a `⚠ Ajustado`: se añadió el test `test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada` para el MT-10 literal (ver «Fila 11 · mutación y regresión (entrega B)») | `sdd/tickets/tkt-006/design.md` | Corregido |

**Verificación:** `python tools/verificar_docs.py` → `✓ Sin problemas.` (111 documentos, 23 ADR, 38 invariantes, 162 escenarios). `python tools/extraer_mermaid.py` → 30 diagramas, código 0. `python -m unittest discover -s tools/tests -v` → `Ran 6 tests`, `OK`, código 0.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 1 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 2 · verde | `desarrollador-dominio` | `sonnet` | `sonnet` | Disparador del diseño: los permisos de un rol |
| Fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde | `desarrollador-aplicacion` (sustituido por agente de propósito general) | `haiku` | `haiku` | — |
| Fila 4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · verde | desarrollador de esquema y migraciones (`haiku`, claude-haiku-5-5) | `haiku` | `haiku` | — |
| Fila 5 · rojo | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 5 · verde | `desarrollador-aplicacion` (sustituido por agente de propósito general) | `haiku` | `haiku` (claude-haiku-5-5) | — |
| Fila 6 · rojo | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 6 · verde | `desarrollador-aplicacion` (sustituido por agente de propósito general) | `haiku` | `sonnet` (claude-sonnet-5-5) | Disparador del diseño: concurrencia |
| Fila 7 · rojo (tanda 1) | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 7 · rojo (tanda 2) | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 7 · verde | `desarrollador-api` (sustituido por agente de propósito general) | `sonnet` | `sonnet` (claude-sonnet-5-5) | Disparador del diseño: los permisos de un rol |
| Fila 8 · rojo | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 8 · verde y refactor | desarrollador de esquema y migraciones (`haiku`, claude-haiku-5-5) | `haiku` | `haiku` (claude-haiku-5-5) | — |
| Fila 9 · mutación y regresión (entrega A) | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 10 · rojo | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 10 · verde y refactor | `desarrollador-api` (sustituido por agente de propósito general) | `sonnet` | `sonnet` (claude-sonnet-5-5) | Disparador del diseño: los permisos de un rol |
| Fila 11 · mutación y regresión (entrega B) | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Fila 12 · documentación y ADR (entrega B) | Orquestador con `conv-documentacion`, por sustitución | `haiku` | `haiku` (claude-haiku-5-5) | — |
| Revisión · ciclo 1 · fragilidad de codificación en un test | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Revisión · ciclo 1 · F001 a F004 de arquitectura | `corrector-revision` | `haiku` | `haiku` (claude-haiku-5-5) | — |
| Revisión · ciclo 2 · F003, F004 y fila 11 | `corrector-revision` | `haiku` | `haiku` (claude-haiku-5-5) | — |
| Revisión · ciclo 3 · F004 y precisiones | `corrector-revision` | `haiku` | `haiku` (claude-haiku-5-5) | — |
| Revisión · ciclo 1 · rojo de F3 (hash no válido) | `tester-backend` | `sonnet` | `sonnet` (claude-sonnet-5-5) | — |
| Revisión · ciclo 1 · verde de F3 y documentación de F1 y F2 | `corrector-revision` | `haiku` | `sonnet` (claude-sonnet-5-5) | Lo despachó el orquestador con ese modelo |

## Revisión · ciclo 3 · F004 y precisiones

Corrección del hallazgo F004 de `auditor-arquitectura`, que persistió tras el ciclo 2, y de las precisiones N2 a N7 y N9 de la reauditoría. Son ediciones de texto en `docs/05-tickets-trabajo.md`, en el ADR-023 y en este `impl.md`: no se tocó código de `cimenta/`, ningún test ni el borrador `docs/api/openapi.yaml`.

| Hallazgo | Qué cambió | Archivo | Estado |
|---|---|---|---|
| F004 (persiste) · «Qué hace» de TKT-026 decía que el ticket escribe en `dominio/` | Pasa a decir que usa en `dominio/` la prohibición de resolver lo propio que implementa TKT-006 (`evaluar_resolucion`); el rol lo comprueba `api/` con `exigir_rol` | `docs/05-tickets-trabajo.md` | Corregido |
| F004 (persiste) · criterio 1 de TKT-026 decía «es propia» | Se quita «es propia»: la función devuelve el resultado de la auto-resolución, `AUTO_RESOLUCION`, y no recibe roles | `docs/05-tickets-trabajo.md` | Corregido |
| F004 (persiste) · cita final de TKT-026 decía «este ticket escribe solo la segunda» | Pasa a «este ticket usa solo la segunda», coherente con el criterio 3: la implementa TKT-006 y este ticket la usa y no la reescribe | `docs/05-tickets-trabajo.md` | Corregido |
| N2 · cierre de `impl.md` remitía al log de `_index.md` | Se quita la frase sobre el log. Queda que hubo ciclos de corrección 1 y 2 y una reauditoría, descritos en este archivo. El log de `/sdd-revisar` lo escribirá el orquestador después | `sdd/tickets/tkt-006/impl.md` | Corregido |
| N3 · la ejecución de `uv run pytest` no indicaba a qué fila correspondía | Se identifica la fila 11 y se registran en «Verificación final» las salidas reales de las reejecuciones del orquestador y del auditor | `sdd/tickets/tkt-006/impl.md` | Corregido |
| N4 · «15 en la B» contaba casos como mutantes | Pasa a 14 mutantes distintos en la B (15 casos, porque MT-10 aparece dos veces: literal y con el test añadido) | `sdd/tickets/tkt-006/impl.md` | Corregido |
| N5 · la fila CA-3 no citaba el caso del hash de descarte | Se añade `test_tkt006_configuracion.py` a los archivos de CA-3 | `sdd/tickets/tkt-006/impl.md` | Corregido |
| N6 · mensaje de `SESION_REVOCADA` distinto entre código y borrador | Se describen las dos diferencias: un `.` en el código frente a un `;` en el ejemplo, y «Inicia» frente a «inicia». El borrador lo declara en un `example:`; decide el usuario cuál manda al tocar el borrador. Ni código ni borrador se cambiaron | `sdd/tickets/tkt-006/impl.md` | Documentado; **decisión pendiente del usuario** |
| N7 · ADR-023 hablaba de «la guarda» `revocada_en IS NULL` | Se precisa: MT-9 es el único mutante sobre la cláusula SQL `revocada_en IS NULL` | `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md` | Corregido |
| N9 · no quedaba claro dónde constaban los hallazgos del informe de `auditor-seguridad` | Se aclara que el informe no se archiva en el repositorio. Sus tres Menores constan en «Verificación final» y la lista de lo que corresponde a TKT-057 consta en «Fuera de alcance, anotado» | `sdd/tickets/tkt-006/impl.md` | Corregido |

**Verificación:** `python tools/verificar_docs.py` → `✓ Sin problemas.` (111 documentos, 23 ADR, 38 invariantes, 162 escenarios). `python tools/extraer_mermaid.py` → 30 diagramas, código 0. `python -m unittest discover -s tools/tests -v` → `Ran 6 tests`, `OK`, código 0.

## Revisión · ciclo 1 · rojo de F3 (hash no válido)

**Hallazgo F3** (Menor, reproducido por el auditor de arquitectura y por el de seguridad; es el `F001` de seguridad anotado antes como deuda). `ContrasenasArgon2.verificar`, en `backend/cimenta/identidad/infraestructura/contrasenas.py`, no captura `pwdlib.exceptions.UnknownHashError`. Si una fila de `usuario` trae un `password_hash` que no es Argon2, `POST /api/v1/sesion` responde `500` para esa cuenta y `401` para las demás, de modo que el inicio de sesión enumera cuentas y rompe la indistinguibilidad de `CA-3`. Además la excepción sale dentro de `begin()` de `abrir_sesion`, así que la fila de `intento_acceso` se deshace. **Decisión del usuario:** `verificar` devuelve `False` ante ese error, con el rojo primero. Esta fase solo escribe las pruebas: no se tocó código de producción.

### Reproducción previa, antes de escribir las pruebas

Adaptador, sin Docker (`PYTHONUTF8=1 uv run python -c ...`, con los costes baratos del entorno de prueba y la contraseña `x`):

```text
'sin-hash' LANZA pwdlib.exceptions.UnknownHashError
'' LANZA pwdlib.exceptions.UnknownHashError
'$2b$12$aaaaaaaaaaaaaaaaaaaaaaa' LANZA pwdlib.exceptions.UnknownHashError
'$pbkdf2-sha256$29000$abc$def' LANZA pwdlib.exceptions.UnknownHashError
'$argon2id$v=19$m=8192' LANZA pwdlib.exceptions.UnknownHashError
```

Por HTTP, con una prueba desechable (ya borrada) que siembra una cuenta con `password_hash = 'sin-hash'` y otra normal, y lee con una conexión nueva del rol de aplicación:

```text
DANADA 500 {"mensaje":"Ocurrió un error inesperado. Cita el identificador de correlación si pides ayuda.","correlacion_id":"ef501ee4-..."}
ANA 401 {"tipo":"SESION","mensaje":"El correo o la contraseña no son correctos.","motivo":"CREDENCIALES_INVALIDAS","correlacion_id":"231f8b67-..."}
INTENTOS [{'email': 'ana@cimenta.test', ..., 'exitoso': False, ...}]      <- solo la fila de la cuenta normal
registro técnico: {"estado": 500, "event": "peticion_fallida", "excepciones": [{"tipo": "pwdlib.exceptions.UnknownHashError", "marcos": [... "sesiones.py:44 abrir_sesion", "contrasenas.py:58 verificar", "pwdlib\\_hash.py:94 verify"]}]}
```

Tres hechos quedan demostrados: el `500` es `UnknownHashError` sin capturar; su cuerpo ni siquiera es del contrato (no tiene `tipo`), distinto del `401` de las demás cuentas; y la fila de `intento_acceso` de la cuenta dañada no existe porque la transacción se deshizo.

### Qué se escribió

Ningún archivo de producción. Tres casos nuevos y una *fixture*, todos en archivos de prueba existentes.

| Archivo | Caso | Casos | Qué afirma |
|---|---|---|---|
| `backend/tests/test_tkt006_configuracion.py` | `test_tkt006_ca03_verificar_un_hash_que_no_es_argon2_devuelve_falso` | 5 (`texto_libre`, `vacio`, `forma_de_bcrypt`, `forma_de_pbkdf2`, `argon2_truncado`) | Nivel de adaptador, sin Docker. `verificar("cualquiera", hash)` devuelve `False` y no lanza |
| `backend/tests/test_tkt006_configuracion.py` | `test_tkt006_ca03_verificar_un_hash_argon2_correcto_sigue_distinguiendo` | 1 | Salvaguarda contra una corrección excesiva: un hash Argon2 real sigue dando `True` con la contraseña correcta y `False` con la errónea |
| `backend/tests/test_tkt006_inicio_sesion.py` | `test_tkt006_ca03_aplicacion_hash_guardado_no_valido_es_credenciales_invalidas` | 3 (`texto_libre`, `vacio`, `forma_de_bcrypt`) | Nivel de aplicación, con Docker. `abrir_sesion` lanza `SesionInvalida` `CREDENCIALES_INVALIDAS` con el contrato completo (`tipo`, `401`, `motivo`, `mensaje` literal, cuatro claves exactas); su cuerpo y su mensaje son iguales a los de una contraseña errónea y de un correo inexistente; se verifica exactamente una vez, contra el hash guardado y con la contraseña escrita; sin fila en `sesion`, bitácora vacía, `ultimo_acceso` nulo; la fila de `intento_acceso` persiste con `exitoso` falso, el usuario, el correo tal como se escribió, la hora del reloj y el origen |
| `backend/tests/test_tkt006_inicio_sesion.py` | `test_tkt006_ca03_hash_guardado_no_valido_es_indistinguible_por_http` | 3 (los mismos) | Nivel HTTP, con Docker, sin las palabras `aplicacion` ni `concurrencia` en el nombre. `POST /api/v1/sesion` responde `401` `SESION` `CREDENCIALES_INVALIDAS`, validado contra `ErrorSesion`, sin `detail` ni `Set-Cookie`; cuerpo igual salvo `correlacion_id` al de una contraseña errónea y al de un correo inexistente, con las mismas cabeceras, `content-length` y `content-type`; sin fila en `sesion` y bitácora vacía; `intento_acceso` tiene tres filas, una por cuenta, la de la cuenta dañada con su usuario |
| `backend/tests/test_tkt006_inicio_sesion.py` | *fixture* `sembrar_con_hash_guardado` y las constantes `HASHES_GUARDADOS_QUE_NO_SON_ARGON2` y `CORREO_DE_CUENTA_DANADA` | — | Inserta un usuario activo con el `password_hash` exacto que se pida, con el rol de aplicación; no es `autouse` |

El hash de forma de bcrypt es `"$2b$12$" + "a" * 53` y el de pbkdf2 es `"$pbkdf2-sha256$29000$c2FsdA$aGFzaA"`: tienen la forma de otro algoritmo, y `pwdlib` con solo Argon2 habilitado no los identifica. El `argon2_truncado` (`"$argon2id$v=19$m=8192"`) no cumple la forma de un hash codificado y lanza lo mismo. En cambio un hash con forma Argon2 completa pero contenido corrupto ya devuelve `False` en `pwdlib` y no entra en estas pruebas. No se probó con `bytes`: la columna es texto.

### Rojo

`PYTHONUTF8=1 uv run pytest tests/test_tkt006_configuracion.py tests/test_tkt006_inicio_sesion.py -q -k "hash_guardado or no_es_argon2 or argon2_correcto_sigue"`:

```text
FFFFF.FFFFFF                                                             [100%]
_ test_tkt006_ca03_verificar_un_hash_que_no_es_argon2_devuelve_falso[texto_libre] _
tests\test_tkt006_configuracion.py:248: in test_tkt006_ca03_verificar_un_hash_que_no_es_argon2_devuelve_falso
    assert contrasenas.verificar("cualquiera", hash_guardado) is False
cimenta\identidad\infraestructura\contrasenas.py:58: in verificar
    return self._hash.verify(contrasena, hash_guardado)
.venv\Lib\site-packages\pwdlib\_hash.py:94: in verify
    raise exceptions.UnknownHashError(hash)
E   pwdlib.exceptions.UnknownHashError: This hash can't be identified. Make sure it's valid and that its corresponding hasher is enabled.
  ... (igual para vacio, forma_de_bcrypt, forma_de_pbkdf2 y argon2_truncado)
_ test_tkt006_ca03_aplicacion_hash_guardado_no_valido_es_credenciales_invalidas[texto_libre] _
tests\test_tkt006_inicio_sesion.py:456: in test_tkt006_ca03_aplicacion_hash_guardado_no_valido_es_credenciales_invalidas
    error = rechazar(contexto, Intento(CORREO_DE_CUENTA_DANADA, CONTRASENA_DE_ANA, danada))
tests\test_tkt006_inicio_sesion.py:171: in rechazar
    abrir_sesion(
cimenta\identidad\aplicacion\sesiones.py:44: in abrir_sesion
    coincide = contexto.contrasenas.verificar(contrasena, hash_a_verificar)
tests\test_tkt006_inicio_sesion.py:111: in verificar
    return self._interior.verificar(contrasena, hash_guardado)
cimenta\identidad\infraestructura\contrasenas.py:58: in verificar
    return self._hash.verify(contrasena, hash_guardado)
.venv\Lib\site-packages\pwdlib\_hash.py:94: in verify
    raise exceptions.UnknownHashError(hash)
E   pwdlib.exceptions.UnknownHashError: This hash can't be identified. ...
  ... (igual para vacio y forma_de_bcrypt)
_ test_tkt006_ca03_hash_guardado_no_valido_es_indistinguible_por_http[texto_libre] _
tests\test_tkt006_inicio_sesion.py:1251: in test_tkt006_ca03_hash_guardado_no_valido_es_indistinguible_por_http
    exigir_credenciales_invalidas(de_danada)
tests\test_tkt006_inicio_sesion.py:976: in exigir_credenciales_invalidas
    assert respuesta.status_code == 401
E   assert 500 == 401
  ... (igual para vacio y forma_de_bcrypt)
11 failed, 1 passed, 89 deselected in 5.20s
```

Los archivos completos: `uv run pytest tests/test_tkt006_configuracion.py tests/test_tkt006_inicio_sesion.py -q` → `11 failed, 90 passed in 10.46s`. Los 90 que pasan incluyen los 89 existentes sin tocar y la salvaguarda.

### Razón de cada fallo

| Casos | Razón del fallo | ¿Esperada? |
|---|---|---|
| 5 de adaptador | `UnknownHashError` sin capturar en `contrasenas.py:58` | Sí: es el defecto descrito |
| 3 de aplicación | La misma excepción sale de `abrir_sesion` (`sesiones.py:44`) y `pytest.raises(SesionInvalida)` no la captura; en producción deshace la fila de `intento_acceso` | Sí |
| 3 de HTTP | `assert 500 == 401`: la excepción llega al manejador genérico, con cuerpo sin `tipo` | Sí |
| `..._argon2_correcto_sigue_distinguiendo` | **Nace en verde, a propósito.** Es una salvaguarda de que la corrección no convierta `verificar` en un «siempre falso» y no describe el defecto: lo cubre ya `TC-16`, pero un mutante `return False` en `verificar` lo pondría en rojo | Investigado: el comportamiento ya existía |

Ningún fallo es de importación, de sintaxis ni de entorno. Los casos de aplicación y HTTP **no** pueden pasar con el código actual porque la excepción es de la biblioteca, no de `contrato_error`.

### Verificadores

| Comando | Resultado |
|---|---|
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check .` | `153 files already formatted` |
| `uv run mypy tests/test_tkt006_inicio_sesion.py tests/test_tkt006_configuracion.py` | `Success: no issues found in 2 source files` |

### Qué debe hacer el verde

`ContrasenasArgon2.verificar` captura `pwdlib.exceptions.UnknownHashError` y devuelve `False`. Nada más: `abrir_sesion` ya trata `coincide = False` como rechazo, confirma el intento y lanza `SesionInvalida` fuera del `begin()`. `verificar` sigue verificando una sola vez, así que `TC-26` no cambia.

## Revisión · ciclo 1 · verde de F3 y documentación de F1 y F2

| Hallazgo | Qué cambió | Archivo | Estado |
|---|---|---|---|
| F3 · hash guardado que no es Argon2 | `ContrasenasArgon2.verificar` captura `pwdlib.exceptions.UnknownHashError` y devuelve `False`; no registra ni el hash ni la contraseña, y no cambia la firma | `backend/cimenta/identidad/infraestructura/contrasenas.py` | Corregido |
| F1 · alcance del asiento `DENEGAR` automático | Se precisa que `exigir_rol` cubre solo `ROL_INSUFICIENTE` y que `registrar_denegacion` no está publicada; TKT-021, TKT-026 y TKT-027 reciben el criterio de asentar sus `403` de caso de uso por la interfaz de auditoría | `docs/02-arquitectura.md`, `.claude/skills/conv-backend-fastapi/SKILL.md`, `docs/05-tickets-trabajo.md` | Corregido |
| F2 · TC-47 no ve `include_router(..., dependencies=[...])` | Se documenta el límite de `rutas_de` y la salida: declarar `exigir_rol` en el decorador de la ruta o ampliar `rutas_de`, en TKT-027; el borrador OpenAPI no cambia | `docs/05-tickets-trabajo.md`, `docs/adr/20261021-sesion-y-autorizacion-por-dependencia.md`, `sdd/tickets/tkt-006/design.md` | Corregido |

TKT-021, TKT-026 y TKT-027 tenían un lugar natural: TKT-021 en el criterio del caso de uso (`NO_ES_SOLICITANTE`), TKT-026 junto a `evaluar_resolucion` (`AUTO_RESOLUCION`) y TKT-027 junto a los escenarios 7 y 8 de HDU-003. TKT-020 no se tocó porque es una función pura de dominio sin `403`.

### Verificación

| Comando | Resultado |
|---|---|
| `uv run pytest tests/test_tkt006_configuracion.py tests/test_tkt006_inicio_sesion.py` | `101 passed in 10.70s` (los 11 casos del rojo en verde y los previos intactos) |
| `uv run mypy .` | `Success: no issues found in 153 source files` |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check .` | `153 files already formatted` |
| `uv run python -m herramientas.verificar_float` | `archivos revisados: 18; hallazgos: 0` |
| `uv run lint-imports` | `Contracts: 15 kept, 0 broken.` |
| `python tools/verificar_docs.py` | `Sin problemas.` |
| `python tools/extraer_mermaid.py` | código 0 |
| `python -m unittest discover -s tools/tests -v` | `Ran 6 tests ... OK` |

## Resultado contra los criterios de aceptación

Las pruebas se nombran por su archivo y por su número de caso (`TC-NN`) en la sección de cada fila; aquí se cruzan con el criterio de la spec.

| Criterio | Resultado | Archivos de prueba |
|---|---|---|
| `CA-1` token CSRF emitido sin sesión | Cumplido | `test_tkt006_csrf.py`, `test_tkt006_enrutador.py` |
| `CA-2` inicio de sesión correcto | Cumplido | `test_tkt006_inicio_sesion.py` (aplicación y HTTP) |
| `CA-3` credenciales erróneas sin revelar cuentas | Cumplido | `test_tkt006_inicio_sesion.py`, `test_tkt006_configuracion.py` (el caso del hash de descarte) |
| `CA-4` usuario desactivado no inicia sesión | Cumplido | `test_tkt006_inicio_sesion.py`, `test_tkt006_dominio.py` |
| `CA-5` forma inválida del inicio de sesión | Cumplido | `test_tkt006_inicio_sesion.py` |
| `CA-6` sesión vigente con roles actuales | Cumplido | `test_tkt006_sesion_vigente.py`, `test_tkt006_permisos_rol.py` (unión de roles) |
| `CA-7` sin sesión o cookie que no corresponde | Cumplido | `test_tkt006_sesion_vigente.py` |
| `CA-8` caducidad absoluta y por inactividad | Cumplido | `test_tkt006_sesion_vigente.py`, `test_tkt006_dominio.py`, `test_tkt006_configuracion.py` |
| `CA-9` cerrar sesión revoca sin borrar | Cumplido | `test_tkt006_cierre.py`, `test_tkt006_sesion_vigente.py`, `test_tkt006_repositorio.py` |
| `CA-10` desactivar un usuario surte efecto | Cumplido | `test_tkt006_sesion_vigente.py` |
| `CA-11` retirar un rol surte efecto | Cumplido | `test_tkt006_sesion_vigente.py`, `test_tkt006_permisos_rol.py`, `test_tkt006_repositorio.py` |
| `CA-12` falta de permiso asentada como `DENEGAR` | Cumplido | `test_tkt006_permisos_rol.py` |
| `CA-13` nadie autoriza lo suyo, sin HTTP | Cumplido | `test_tkt006_dominio.py`, `test_tkt006_enrutador.py` (publicación en la interfaz) |
| `CA-14` solo dos rutas sin sesión | Cumplido | `test_tkt006_enrutador.py` |
| `CA-15` Argon2id con parámetros en configuración | Cumplido | `test_tkt006_configuracion.py` |
| `CA-16` semilla de roles igual al enum `Rol` (`S1`) | Cumplido | `test_tkt006_esquema.py` |
| `CA-17` correo en minúsculas en la base (`S2`) | Cumplido | `test_tkt006_esquema.py` |
| `CA-R1` a `CA-R7` | Cumplidos | Regresión de las filas 9 y 11 |

## Verificación final

- `uv run pytest` completo con Docker: `1126 passed`. Salidas registradas: en la fila 11, `1126 passed in 224.86s (0:03:44)`; reejecución del orquestador el 2026-10-22, sin `PYTHONUTF8`, tras el ciclo 1 de corrección y antes del ciclo 2, `1126 passed in 237.49s (0:03:57)` con `ruff`, `format`, `mypy` (153 archivos), `lint-imports` (15 kept, 0 broken), `verificar_float`, `alembic heads` (`0004`) y `verificar_docs` en verde; y reejecución del auditor de arquitectura en su reauditoría final, con `PYTHONIOENCODING=utf-8` y sin `PYTHONUTF8`, `1126 passed in 262.09s (0:04:22)`. Los ciclos 2 y 3 solo tocaron texto.
- `ruff check`, `ruff format --check`, `mypy` (153 archivos) y `verificar_float` (18 archivos, 0 hallazgos) en verde.
- `uv run lint-imports`: 15 contratos cumplidos, 0 rotos, sin `ignore_imports`.
- `alembic heads`: una sola cabeza, `0004`.
- `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y los tests de `tools/` con código 0.
- Mutación: 16 mutantes en la entrega A y 14 mutantes distintos en la B (15 casos, porque MT-10 aparece dos veces: literal y con el test añadido); el único superviviente, el `MT-10` literal (`functools.cache` sobre `roles_de` nunca acierta porque cada petición abre su `Session`), se cubrió con un test nuevo. Ninguno sobrevive y todos los archivos se restauraron con su SHA-256.
- Seguridad: `auditor-seguridad` dio `APROBADO` con tres Menores opcionales (`F001` `UnknownHashError` sin capturar, `F002` sin suelo para los costes de Argon2 ni re-derivación, `F003` cookie sin prefijo `__Host-`), anotados como deuda. El informe de `auditor-seguridad` no se archiva en el repositorio: sus tres Menores constan en esta sección, y su lista de lo que corresponde a TKT-057 consta en «Fuera de alcance, anotado». `F002` (sin suelo para los costes de Argon2 ni re-derivación) y `F003` (prefijo `__Host-`) no tienen ticket asignado: `F002` encaja en la configuración de TKT-057 y `F003` en un cambio futuro del borrador; `F001` se anotó en `PA-T13`.
- Arquitectura: `auditor-arquitectura` dio `REQUIERE CAMBIOS` con cuatro Menores documentales; hubo ciclos de corrección 1 a 3 y tres reauditorías, descritos en sus secciones de este archivo. Una fragilidad de codificación de un test (dependía de `PYTHONUTF8` en Windows) se corrigió con el rojo documentado.
- `auditor-sql`, `auditor-codigo`, `auditor-docs`, `revisor-impacto`, `desarrollador-aplicacion` y `desarrollador-api` no existen: los sustituyeron `auditor-arquitectura`, `auditor-seguridad`, los verificadores, el arquitecto y agentes generales.

## Fuera de alcance, anotado

- Verificación del doble envío CSRF, límite de intentos, `bloqueado_hasta`, cabeceras de seguridad y tope de cuerpo y de longitud de contraseña: TKT-057.
- Alta de usuarios y primer usuario: sin ella nadie inicia sesión en producción (`PA-T13`); al diseñarla, que siempre derive el hash con `ContrasenasArgon2` (`F001` de seguridad).
- `lower()` de Python y de PostgreSQL pueden diferir con caracteres no ASCII según la base: revisarlo con el alta de usuarios.
- Una ruta que conserve `sesion_vigente` y olvide `exigir_rol` queda abierta a cualquier usuario autenticado: TC-47 solo vigila la sesión. Lo cubre la revisión de cada ticket; TKT-061 puede automatizarlo.
- `abrir_sesion` verifica el hash dentro de una transacción abierta y retiene una conexión del pool durante la derivación: el límite de intentos de TKT-057 lo mitiga.
- El mensaje de `SESION_REVOCADA` difiere en dos cosas entre el código (`backend/cimenta/identidad/aplicacion/sesiones.py`, línea 20: «La sesión ya no es válida. Inicia sesión de nuevo.») y el ejemplo de `docs/api/openapi.yaml`, línea 3422, que dice «La sesión ya no es válida; inicia sesión de nuevo.»: un `.` frente a un `;`, y «Inicia» frente a «inicia». El borrador lo declara en un `example:`, así que decide el usuario cuál manda al tocar el borrador. Ni el código ni el borrador se cambiaron en esta corrección.
- `ocurrido_en` y el reloj de cada consumidor siguen siendo disciplina del llamador (heredado de TKT-007).

## Verificación final · `/sdd-revisar`

Resultado de la revisión del 2026-10-22, hecha por el orquestador sin fiarse de lo anterior.

- **Suite.** `uv run pytest` completo con Docker, sin `PYTHONUTF8`: `1126 passed in 237.45s` antes del ciclo de corrección y `1138 passed in 234.80s` después (los 12 casos nuevos de `F3`: 11 que nacieron en rojo y uno de salvaguarda). `ruff check`, `ruff format --check`, `mypy` (153 archivos), `verificar_float` (18 archivos, 0 hallazgos), `lint-imports` (15 contratos cumplidos, 0 rotos), `alembic heads` (`0004`) y `verificar_docs` en verde. El diff solo toca `pyproject.toml` y `uv.lock` por las dependencias previstas; ni `.env` ni artefactos temporales.
- **Criterios.** Los 15 `[M]`, los 2 `[S]` y los 7 de regresión cumplidos, con rechazo en cada regla y con el contrato de error completo.
- **Auditoría independiente de arquitectura.** Primera pasada: `REQUIERE CAMBIOS` con tres Menores. `F3` (un `password_hash` que no es Argon2 daba `500`, reproducido por el auditor y antes por seguridad, y rompía la indistinguibilidad de `CA-3`) se corrigió en código con el rojo primero (11 casos fallan por `UnknownHashError` o `assert 500 == 401`, luego en verde); `F1` (el `DENEGAR` automático solo cubre `ROL_INSUFICIENTE`) y `F2` (el montaje de `consultar_bitacora` con `include_router(..., dependencies=...)` protege en ejecución pero TC-47 lo reportaría como sin proteger) se resolvieron como documentación, por decisión del usuario, sin publicar ningún ayudante nuevo. Reauditoría: `APROBADO`, sin hallazgos nuevos; una mutación propia del auditor (quitar el `except`) hace caer 11 casos.
- **Seguridad.** `APROBADO` en `/sdd-ejecutar`, con tres Menores opcionales; `F001` de seguridad es el mismo defecto que `F3` y quedó corregido. No se repitió la auditoría de seguridad: la única diferencia de código desde entonces es esa captura de una excepción, que revisó la reauditoría de arquitectura.
- **Observaciones que no bloquean y quedan anotadas.** Desactivar un usuario no persiste `revocada_en`: si se reactiva dentro de la ventana de inactividad la cookie vuelve a servir (el ticket de desactivación debe revocar sus sesiones en la misma transacción). `expira_por_inactividad_en` puede mostrar un instante posterior a la caducidad absoluta (TKT-008 debe mostrar el mínimo). Cerrar una sesión ya caducada no expira la cookie. Un usuario autenticado sin permiso puede generar `DENEGAR` sin límite (TKT-057). `_como_uuid` acepta formas no canónicas de UUID. Ningún test fija que el `except` de `verificar` sea estrecho: un `except Exception` mantendría la suite en verde.
- **Deuda para otros tickets.** `NO_ES_SOLICITANTE` y `AUTO_RESOLUCION` no se asientan solos: TKT-021, TKT-026 y TKT-027 lo llevan como criterio. TKT-027 debe declarar `exigir_rol` en el decorador de la ruta o ampliar `rutas_de`. TKT-057: verificación CSRF y rotación, límite de intentos y `bloqueado_hasta`, topes de cuerpo y de contraseña, suelo de los costes de Argon2, `Cache-Control` y `pydantic-settings`. TKT-008: la cookie `Secure` en desarrollo local y un usuario con `roles: []`.
- **Fuera del ticket.** `servidor/correlacion.py` tiene un `async def __call__` (ASGI puro, anterior a este ticket).
