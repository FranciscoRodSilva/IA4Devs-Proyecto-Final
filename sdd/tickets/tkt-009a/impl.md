# Impl · TKT-009a · Pipeline de pruebas y fronteras

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

El flujo `.github/workflows/ci.yml` corre en cada pull request ocho trabajos con permisos de solo lectura y sin secretos: `backend` (formato, lint, tipos, regla de `float`, y pruebas con cobertura contra PostgreSQL), `fronteras` (`lint-imports`), `contrato-api` (trabajo reservado para TKT-061), `frontend` (lint, tipos, pruebas y tipos generados), `humo` (Playwright contra una base migrada), `herramientas` (la suite de `tools/` con guarda contra pruebas saltadas), `workflows` (`zizmor` 1.31.1) y `documentacion` (`verificar_docs.py`). Todas las acciones están fijadas por SHA.

La definición del flujo se prueba con `tools/tests/test_definicion_ci.py`: casos que leen el texto del workflow, ignoran comentarios y buscan dentro del bloque de cada trabajo, más mutantes sintéticos que demuestran que cada caso se pone en rojo cuando una compuerta se comenta, se mueve de trabajo o se desactiva. Se añadió `pytest-cov` al grupo `dev`, las entradas de `.gitignore` de los artefactos de cobertura, y se retiraron las marcas «desde TKT-009» de las reglas 1 a 3 y de las skills afectadas.

Las rondas de ensayo en GitHub demostraron cada compuerta en rojo, y el PR #2 corrió el pipeline completo en verde sobre el árbol sano.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-28 | Los SHA de las acciones se obtuvieron con `git ls-remote --tags`, no con `gh api` (regla común 2). El SHA es el mismo | `gh` no estaba autenticado en ese momento. Las cuatro etiquetas son ligeras, así que el SHA es el del commit. El auditor de seguridad lo verificó |
| 2026-10-28 | El paso de la suite de `tools/` en `herramientas` no usa `-v` | En modo detallado `unittest` imprime la primera línea del docstring de cada prueba, y tres docstrings contenían la cadena `skipped=`: la guarda daba rojo permanente con todo en verde. TC-23 no exige `-v` |
| 2026-10-28 | `upload-artifact` de `backend` lleva `if-no-files-found: error` | Un informe ausente es un fallo, no un aviso. El diseño no fijaba valor |
| 2026-10-28 | A3 `⚠ Ajustado`: el recorrido de Playwright no se pudo ejecutar en local | `frontend/node_modules` estaba bloqueado por un proceso (EPERM) y el servidor de Vite del puerto 5173 usaba ese árbol roto. La verificación real fue el trabajo `humo` en GitHub, en verde |
| 2026-10-28 | Ronda 1 de ensayo: la violación de la ruta de inicio de sesión lleva un `as` de TypeScript | Sin él, `openapi-fetch` rompía el tipado y caía también `frontend`. Aun así cayó `frontend`, por una prueba de componente que simula esa ruta |
| 2026-10-29 | Ronda 2 de ensayo añade un `summary` nuevo a `GET /api/v1/sesion` en lugar de cambiar uno existente | Ninguna ruta de `identidad` declaraba `summary=` |
| 2026-10-29 | Se corrigió una prueba de TKT-008b, `Armazon.test.tsx` | Ver «Hallazgos fuera de alcance». El pipeline la mostró rota en Linux |
| 2026-10-29 | Tras la auditoría de código se añadieron las comprobaciones de las reglas comunes 6 y 7 y del comando completo de pytest | Hallazgo F001 (Mayor), ver «Auditorías» |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `.github/workflows/ci.yml` | nuevo | entrega continua |
| `tools/tests/test_definicion_ci.py` | nuevo | pruebas |
| `tools/tests/test_sembrar_usuario_humo.py`, `tools/tests/test_verificar_codificacion.py` | modificado (solo docstrings) | pruebas |
| `backend/pyproject.toml`, `backend/uv.lock` | modificado (`pytest-cov`, `coverage`) | dependencias de desarrollo |
| `.gitignore` | modificado | configuración |
| `CLAUDE.md`, `.claude/skills/conv-docker/SKILL.md`, `.claude/skills/conv-dominio-python/SKILL.md` | modificado | documentación |
| `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `docs/arranque-local.md`, `tools/README.md` | modificado | documentación |
| `sdd/tickets/tkt-009/design.md` | modificado (estados y ajustes) | documentación |
| `frontend/src/app/armazon/Armazon.test.tsx` | modificado (fuera de alcance, ver abajo) | pruebas |

No se tocó `backend/cimenta/` ni `frontend/src/` fuera de ese test.

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01, TC-05, TC-06, TC-12, TC-13, TC-R1a | `test_tc01_…` a `test_tcr1a_…` en `test_definicion_ci.py` | estático, con rechazo | `CA-1`, `CA-3`, `CA-4`, `CA-9`, `CA-R1` | FALLA (7 de 23, falta `ci.yml`) | PASA |
| TC-08 | `test_tc08_humo_…` | estático | `CA-5` | FALLA (28 pruebas, 1 fallo) | PASA |
| TC-21, TC-22, TC-23, TC-R4b y trabajos `workflows` y `documentacion` | `test_tc21_…`, `test_tc22_…`, `test_tc23_…`, `test_tcr4b_…`, `test_a4_…` | estático, con rechazo | `CA-12`, `CA-R4` | FALLA (4 de 52) | PASA |
| Reglas comunes 6 y 7, pytest completo | `test_compuertas_…` | rechazo | `CA-9`, `CA-12` | FALLA (66 comprobaciones de mutantes en verde cuando debían caer) | PASA |
| TC-R1b | mutante local: `motor_aplicacion` como propietario | **rechazo** | `CA-R1` | — | 16 errores por la guarda `_exigir_motor_de_aplicacion` |
| TC-R2b | mutante local: un contrato de `import-linter` borrado | **rechazo** | `CA-R2` | — | cae `test_tkt004_ca10_arbol_real` con `(14, 0)` |
| TC-02, 03, 04, 07, 09, 10, 24 | rondas 1 y 2 de ensayo en GitHub | **rechazo** | `CA-2` a `CA-5`, `CA-12` | — | rojo en el trabajo esperado |

### Ciclo TDD por fila

#### Fila A0 · registro de la partición

Ya estaba hecha cuando empezó la ejecución: `docs/05-tickets-trabajo.md` traía la subsección de partición. Se comprobó con `verificar_docs.py`.

#### Fila A1 · `pytest-cov` y `.gitignore`

**Rojo:**

```
ERROR: usage: pytest [options] [file_or_dir] [file_or_dir] [...]
pytest: error: unrecognized arguments: --cov=cimenta
pytest exit=4
```

**Verde:**

```
Coverage XML written to file cobertura.xml
1138 passed in 238.54s (0:03:58)
pytest exit=0
```

`git status` no lista `.coverage`, `cobertura.xml` ni `pytest.xml`. El diff de `pyproject.toml` solo añade `pytest-cov>=7.1.0`.

#### Fila A2 · `ci.yml`: backend, fronteras, contrato-api y frontend

**Rojo:** `Ran 23 tests … FAILED (failures=7)`, todos con «No existe .github\workflows\ci.yml». Los otros 16 (extractores y mutantes sintéticos) pasaban.

**Verde:** `Ran 23 tests … OK`. En local: `ruff format --check` (153 archivos), `ruff check`, `mypy` (153 archivos), `verificar_float` (0 hallazgos), `lint-imports` (15 contratos intactos) y, sobre un espejo, `npm ci`, lint, tipos, 214 pruebas del cliente y `tipos:verificar`.

**Mutantes locales:** comentar `lint-imports` pone en rojo `test_tc05_…`; mover `mypy` a otro trabajo pone en rojo `test_tc01_…`.

**Refactor:** el desarrollador había fijado la versión de `uv` (`0.10.7`) en `setup-uv`. El diseño no lo pedía y se quitó.

#### Fila A3 · trabajo `humo`

**Rojo:** `Ran 28 tests … FAILED (failures=1)` por `no existe el trabajo 'humo'`.

**Verde:** `Ran 28 tests … OK`. La parte local del recorrido (`npm run e2e`) no se pudo ejecutar (ver ajustes). La verificación real es el trabajo `humo` de GitHub en verde.

#### Fila A4 · `herramientas`, `workflows` y `documentacion`

**Rojo:** `Ran 52 tests … FAILED (failures=4)`, todos por trabajos inexistentes.

**Verde:** `Ran 52 tests … OK`; la suite completa de `tools/` dio 64 pruebas en `OK`, sin `skipped=`.

**Rojo de TC-20** (workflow sin `permissions` y con `pull_request_target`, en el directorio de pruebas del espacio temporal):

```
error[dangerous-triggers]: use of fundamentally insecure workflow trigger
warning[excessive-permissions]: overly broad permissions
exit caso pedido=14
```

Solo sin `permissions`: `warning[excessive-permissions] … default permissions used due to no permissions: block`, `exit=13`. Sobre el árbol real: `No findings to report. Good job! (1 suppressed)`, `exit=0`.

**Rojo de TC-R4b:** con `uv` fuera del `PATH`, `unittest` termina con `OK (skipped=2)` y la guarda `! grep -q "skipped="` devuelve 1.

#### Fila A5 · mutantes de regresión

**TC-R1b:** con `motor_aplicacion` conectado como `cimenta_migracion`, `13 passed, 16 errors`; los errores caen en la guarda: «El motor de pruebas no es el del rol de aplicación (cimenta_aplicacion): es cimenta_migracion». Al revertir: `29 passed`.

**TC-R2b:** con el contrato `grafo-analitica` borrado, `Contracts: 14 kept, 0 broken.` y `assert (14, 0) == (15, 0)` en `test_tkt004_ca10_arbol_real`. Al revertir: `Contracts: 15 kept, 0 broken.` y `32 passed`.

**TC-R2a:** el diff de `pyproject.toml` no toca `[tool.importlinter]`.

El nombre del plan decía que las pruebas de permisos usan `motor_aplicacion`. No es exacto: `test_identidad_permisos*` usan `conectar("aplicacion")`, con su propia guarda. La guarda del motor la ejercen las fixtures que dependen de `motor_aplicacion` (por ejemplo `test_tkt006_repositorio.py`).

#### Fila A6 · ensayo en el pipeline

Las ejecuciones están en el repositorio `FranciscoRodSilva/IA4Devs-Proyecto-Final`.

| Ronda | Ejecución | Trabajo | Resultado y mensaje |
|---|---|---|---|
| 1 | `actions/runs/40791191850` | `backend` | Rojo. `RUF032`; `verificar_float`: «float prohibido en el parámetro valor de calcular_ensayo (regla 1 de CLAUDE.md)»; falla `test_ensayo_roto` |
| 1 | mismo | `fronteras` | Rojo. «Contracts: 14 kept, 1 broken» |
| 1 | mismo | `humo` | Rojo; artefacto `humo-playwright` subido |
| 1 | mismo | `workflows` | Rojo en `zizmor` |
| 1 | mismo | `herramientas` | Rojo (no previsto): TC-22 detecta `pull_request_target` en `ensayo.yml`, segunda compuerta sobre la misma violación |
| 1 | mismo | `frontend` | Rojo (no previsto): una prueba de componente simula la ruta de inicio de sesión que se cambió |
| 2 | `actions/runs/40791201877` | `frontend` | Rojo en «Tipos generados al día»: «Difiere: src/api/generado/servidor.ts. Ejecuta npm run tipos:generar y versiona el resultado.» |
| 3 | `actions/runs/40790629052` (PR #2, árbol sano) | los ocho | Verde |

Los PR de ensayo #3 y #4 se cerraron sin fusionar y sus ramas se borraron.

#### Fila A7 · documentación y marcas

`python tools/verificar_docs.py` → «Sin problemas». `grep "desde TKT-009"` solo encuentra `CLAUDE.md:78`, que es de TKT-009c; `desde TKT-059` sigue presente.

#### Fila A8 · cierre de la parte

Recuentos antes y después: la suite de `tools/` pasó de 12 a 77 pruebas; el backend dio 1138 pruebas en verde con la dependencia nueva (no se midió un recuento previo, pero el ticket no toca `backend/tests/`); el cliente tiene 214 pruebas. El recuento de `tools/` antes del ticket (12) se midió en una copia limpia de `HEAD`, donde 3 pruebas fallaron por falta del entorno local. El diff no añade `skip`, `xfail` ni `.only`.

**Tests devueltos al tester:** ninguno. Ningún desarrollador editó un test. La única edición de un test archivado, `Armazon.test.tsx`, la hizo `tester-frontend`.

**Evidencia de ejecución al cerrar:** la suite local de `tools/` (`Ran 77 tests … OK`, sin `skipped=`) y el pipeline completo en verde del PR #2 (`actions/runs/40790629052`, con Docker en el corredor). El pipeline no se volvió a ejecutar tras el último commit, `199f37f`, que solo toca `test_definicion_ci.py`.

**Mutación en rutas críticas:** el ticket no toca dinero, límites ni congelado. Los mutantes son los de las compuertas: los de la tabla de mutación del diseño viven en `test_definicion_ci.py`, y A5 ejecutó los dos de regresión. La auditoría de código aplicó además 29 mutantes sobre el `ci.yml` real.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| A1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| A2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A2 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | El primer despacho se detuvo por `gh` sin sesión; se repitió con los SHA resueltos |
| A3 · rojo y verde | `tester-backend`, `ingeniero-devsecops` | `sonnet`, `haiku` | `sonnet`, `haiku` | — |
| A4 · rojo y verde | `tester-backend`, `ingeniero-devsecops` | `sonnet`, `haiku` | `sonnet`, `haiku` | — |
| A5 | `tester-backend` | `sonnet` | `sonnet` | — |
| A6 | `git-entrega` | `haiku` | `haiku` | — |
| A7 | `ingeniero-devsecops`, `tester-backend` | `haiku`, `sonnet` | `haiku`, `sonnet` | — |
| Arreglo de `Armazon.test.tsx` | `tester-frontend` | `sonnet` | `sonnet` | Fuera de alcance, autorizado por el usuario |
| Auditorías | cuatro auditores | `sonnet` | `sonnet` | — |
| Corrección del ciclo 1 | `tester-backend` | `haiku` | `sonnet` | La corrección escribe lógica de pruebas y añade comprobaciones nuevas, no aplica un cambio mecánico |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` backend | `[M]` | Cumplido | TC-01; `backend` en verde en el PR #2 con 1138 pruebas |
| `CA-2` test roto, `float`, `Decimal(0.1)` | `[M]` | Cumplido | Ronda 1: `test_ensayo_roto`, `verificar_float`, `RUF032` |
| `CA-3` fronteras | `[M]` | Cumplido | TC-05; ronda 1: «14 kept, 1 broken» |
| `CA-4` frontend y tipos | `[M]` | Cumplido | TC-06; ronda 2: «Difiere: src/api/generado/servidor.ts» |
| `CA-5` humo | `[M]` | Cumplido | TC-08; ronda 1 con artefacto `humo-playwright`; `humo` en verde en el PR #2 |
| `CA-9` trabajo reservado e independencia de TKT-062 | `[M]` | Cumplido | TC-12, TC-13 |
| `CA-12` permisos y secretos | `[M]` | Cumplido | TC-21, TC-22, TC-20; `zizmor` en 0 |
| `CA-R1`, `CA-R2` | `[M]` | Cumplido | TC-R1a, TC-R1b, TC-R2a, TC-R2b |
| `CA-R4` | `[M]` | Cumplido | TC-23, TC-R4a, TC-R4b |
| `CA-15` su parte | `[M]` | Cumplido | TC-70a: marcas retiradas salvo `CLAUDE.md:78` |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO | 3 observaciones | 1 |
| `auditor-sql` | No aplica | No hay esquema ni migración | — |
| `auditor-codigo` | REQUIERE CAMBIOS, luego APROBADO | 1 Mayor, 4 Menores; reauditoría sin hallazgos | 2 |
| `auditor-seguridad` | APROBADO | 3 observaciones bajas | 1 |
| `auditor-docs` | APROBADO | 3 observaciones | 1 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | código | Mayor | `test_definicion_ci.py` | Nueve formas de desactivar una compuerta (`continue-on-error`, `\|\| true`, `if: false`, `pytest -k`) pasaban en verde: faltaban las comprobaciones de las reglas comunes 6 y 7 | Resuelto |
| F002 | código | Menor | `test_definicion_ci.py` | Ayudantes y constantes duplicados | Resuelto |
| F003 | código | Menor | `test_definicion_ci.py` | Los mutantes no exigían el motivo del rojo; sustituciones de texto sin verificar | Resuelto |
| F004 | código | Menor | `test_definicion_ci.py:1-24` | Docstring del módulo obsoleto | Resuelto (no se renombraron clases ni se partió el archivo) |
| F005 | código | Menor | `test_definicion_ci.py` | Afirmaciones tautológicas sobre la guarda de saltos | Resuelto |
| O001 de arquitectura | arquitectura | Observación | `test_definicion_ci.py` | El archivo (~2,100 líneas tras la corrección) supera con creces las ~265 líneas de la estimación | Persiste: se anota en `delta.md` |
| F001 a F003 de seguridad | seguridad | Baja | `ci.yml` | Falta `concurrency:`; `zizmor` sin lockfile para sus transitivas; cachés por omisión | Persiste: observaciones |
| O001 de docs | docs | Observación | `docs/06-stack-tecnologico.md` | La guarda es un paso aparte, no parte del paso de la suite | Persiste: observación |

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/src/app/armazon/Armazon.tsx` (`salir()`) | Tras el cierre de sesión, `Armazon` sigue montado un instante, vuelve a renderizar tras `queryClient.clear()` y lanza un segundo `GET /sesion`. Es inocuo con un servidor real (responde 401), pero es una petición espuria. Se evitaría vaciando la caché tras el desmontaje | Baja |
| `Armazon.test.tsx` | La prueba de TKT-008b cayó en Linux con CPU escasa porque el doble de sesión respondía siempre 200. Se corrigió aquí (commit `968519b`) con `dobleSesionQueTermina`. Con 0.4 CPU en Docker fallaba 3 de 4 veces y ahora pasa 8 de 8. Queda como ajuste fuera de alcance | Hecho |
| `ci.yml` | Falta `concurrency:` para cancelar ejecuciones anteriores de la misma rama | Baja |
| `ci.yml` | La guarda `! grep -q` debe ser la última orden de su paso, y el `uv sync` previo de `herramientas` calienta el entorno de `backend`; ninguno de los dos lleva comentario en el archivo | Baja |
| `test_definicion_ci.py` | La lista blanca de opciones de pytest rechaza opciones legítimas futuras (`--cov-fail-under`, `-n`); y `PYTEST_ADDOPTS: -k nada` en `env:` pasaría | Baja |
| `tools/` | `ruff` no corre sobre `tools/` en el pipeline | Baja |
| `docs/04-historias-usuario.md` (diseño, TC-58) | El plan de pruebas dice «26 `FALTA`» y la fila C5 y la ronda de ensayo dicen 27 (HDU-001). Se corrige en TKT-009c | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `CLAUDE.md` | Reglas 1 a 3 sin la marca «desde TKT-009», con el trabajo que las ejecuta; una línea en Comandos que remite a `ci.yml` |
| `.claude/skills/conv-dominio-python/SKILL.md`, `.claude/skills/conv-docker/SKILL.md` | Las marcas en presente |
| `docs/05-tickets-trabajo.md` | TKT-009: la desviación de MinIO. TKT-059: criterio nuevo de MinIO en el trabajo `backend` |
| `docs/06-stack-tecnologico.md` §10 | Los trabajos reales, la cobertura sin umbral y la desviación de MinIO |
| `docs/arranque-local.md` | Sección «Integración continua» con la reproducción local de cada trabajo |
| `tools/README.md` | Las pruebas de `tools/` las corre el trabajo `herramientas`; `test_definicion_ci.py` |
| `sdd/tickets/tkt-009/design.md` | Estados de las filas y bloque de ajustes registrados |

`python tools/verificar_docs.py` → «✓ Sin problemas».

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde: 77 pruebas de `tools/` en local, 1138 de backend, 214 del cliente y el pipeline completo en el PR #2
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: mutantes de las compuertas y los dos de regresión
- [x] Todas las auditorías `APROBADO`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios (en el trabajo `backend` y `fronteras`)
- [x] Rama correcta y sin secretos en el diff

**Pendiente de comprobar tras el último commit:** el pipeline completo no se volvió a ejecutar sobre `199f37f`; el siguiente empuje del PR #2 lo hará. Quedan además dos acciones locales tuyas: restaurar `frontend/node_modules` (`npm ci`, tras cerrar el proceso que lo bloquea) y las contraseñas de roles de tu base de desarrollo, que `contrasenas_roles` reescribió con los valores de tu `.env`.
