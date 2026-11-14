# Impl · TKT-029a · Catálogo de proveedores, sin baja

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

## Qué se implementó

Entrega **a** del ticket (filas A1 a A4): el esquema y la lógica del catálogo de proveedores, probados sin HTTP. La entrega **b** (API, montaje, contrato y tipos) se documenta en la última sección de este archivo y acumula sus cambios en la misma rama y el mismo pull request.

- **Dominio.** `proveedores/dominio/proveedor.py`: `EstadoProveedor`, los días por omisión de `RN-17`, `normalizar_rfc` (recorta solo espacios y pasa a mayúsculas, decisión D-1) y `admite_desactivacion` (solo un proveedor `ACTIVO`).
- **Esquema.** Migración `0013` con la tabla `proveedor`, sus seis restricciones nombradas y los permisos del rol de aplicación sin `DELETE` (decisión D-4).
- **Infraestructura.** Modelo Core y repositorio con inserción, lectura por identificador y por RFC (con `FOR UPDATE` opcional), listado con filtro por estado, búsqueda literal y página inalcanzable, y actualización por columnas.
- **Aplicación.** Contexto y cinco casos de uso: alta (el índice único arbitra el duplicado y la carrera), consulta, listado, cambio de datos y desactivación con bloqueo pesimista. La bitácora se asienta en la misma transacción.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-12 | La migración es `0013` (`down_revision = "0012"`), no `0012`. | TKT-059 fusionó `v0012_archivos_archivo.py` mientras se diseñaba este ticket. Es solo numeración. TKT-019 tomará `0014`. |
| 2026-11-12 | `test_tkt059_migracion.py::test_tkt059_ca01_la_bajada_se_niega_con_archivos` lee la cabeza única de `ScriptDirectory` en lugar de la cadena `"0012"`. | La migración nueva movió la cabeza. Lo que la prueba afirma no cambia, y ya no se rompe con la siguiente migración. |
| 2026-11-12 | Tres pruebas de apoyo en `test_tkt029a_casos_de_uso.py` (`obtener_proveedor`, recorte de `q` con desplazamiento, y roles y campos cambiables). | Evitar funciones del módulo de casos de uso sin ninguna prueba en la entrega a. |
| 2026-11-12 | `actualizar_proveedor` del repositorio devuelve sin ejecutar nada si recibe un mapa vacío. | Un `UPDATE` sin columnas no es válido en SQLAlchemy. El caso de uso nunca lo envía vacío. |
| 2026-11-12 | El mutante `M-5` se ejecutó como `estado is not ACTIVO` (invertido). | Cae en TC-02 y TC-19, igual que el del diseño. |
| 2026-11-12 | El orquestador ordenó los imports de `test_tkt029a_repositorio_proveedor.py` con `ruff check --fix` (regla `I001`). | Solo estilo; el desarrollador no puede tocar tests y el tester ya había terminado. |

Las filas A1 a A4 quedan en `✓ Hecho` en `design.md`; ninguna lleva `⚠ Ajustado` porque los cambios son de numeración y de apoyo, no de enfoque.

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/proveedores/dominio/proveedor.py` | nuevo | dominio |
| `backend/migraciones/versions/v0013_proveedores_catalogo.py` | nuevo | infraestructura (esquema) |
| `backend/cimenta/proveedores/infraestructura/tablas.py` | nuevo | infraestructura |
| `backend/cimenta/proveedores/infraestructura/repositorio_proveedor.py` | nuevo | infraestructura |
| `backend/cimenta/proveedores/aplicacion/contexto.py` | nuevo | aplicación |
| `backend/cimenta/proveedores/aplicacion/proveedores.py` | nuevo | aplicación |
| `backend/tests/test_tkt029a_dominio_proveedor.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_migracion.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_repositorio_proveedor.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_casos_de_uso.py` | nuevo | pruebas |
| `backend/tests/test_tkt010_semilla_local.py` | modificado (actualización declarada de TC-B15) | pruebas |
| `backend/tests/test_tkt059_migracion.py` | modificado (cabeza leída del guion) | pruebas |
| `docs/03-modelo-datos.md` | modificado (§9) | documentación |
| `sdd/tickets/tkt-029a/design.md` | modificado (filas y «Ajustes de la ejecución») | documentación |
| `sdd/tickets/tkt-029a/rojo/fila-A1.txt` a `fila-A4.txt` | nuevo | evidencia |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_hdu004_esc03_dominio_normaliza_el_rfc` | feliz · borde | `CA-2` | FALLA | PASA |
| TC-02 | `test_hdu004_esc12_dominio_solo_activo_admite_desactivacion` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-03 | `test_hdu004_esc02_dominio_dias_por_omision_rn17` | feliz | `CA-1` | FALLA | PASA |
| TC-04 | `test_tkt029a_car1_0013_cuelga_de_0012_y_la_cabeza_es_unica` | regresión | `CA-R1` | FALLA | PASA |
| TC-05 | `test_tkt029a_car1_sube_baja_y_vuelve_a_subir` | regresión | `CA-R1` | FALLA | PASA |
| TC-06 | `test_tkt029a_ca11_el_motor_rechaza_con_la_restriccion_nombrada` (12 parámetros) y `test_tkt029a_ca11_sin_dias_el_motor_pone_4_y_6` | **rechazo** | `CA-11` | FALLA | PASA |
| TC-07 | `test_tkt029a_ca10_el_rol_de_aplicacion_no_borra_proveedores` | **rechazo** | `CA-10` esc. 2 | FALLA | PASA |
| TC-B15 | `test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio` (actualizada) | regresión | `CA-R1` | FALLA | PASA |
| TC-08 | `test_tkt029a_repositorio_inserta_y_lee_el_proveedor` | feliz | `CA-1` | FALLA | PASA |
| TC-09 | `test_tkt029a_repositorio_inexistente_devuelve_none` | **rechazo** | `CA-7` | FALLA | PASA |
| TC-10 | `test_tkt029a_repositorio_lista_filtra_busca_ordena_y_pagina` | feliz · **rechazo** | `CA-6` | FALLA | PASA |
| TC-11 | `test_tkt029a_repositorio_actualiza_solo_las_columnas_dadas` | feliz · **rechazo** | `CA-8` | FALLA | PASA |
| TC-12 | `test_hdu004_esc02_alta_guarda_el_proveedor_y_asienta_crear` | feliz | `CA-1` | FALLA | PASA |
| TC-13 | `test_hdu004_esc02_alta_bitacora_en_la_misma_transaccion` | **rechazo** | `CA-1` | FALLA | PASA |
| TC-14 | `test_hdu004_esc03_alta_rfc_duplicado` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-15 | `test_hdu004_esc03_dos_altas_concurrentes_mismo_rfc` | **concurrencia** | `CA-3` | FALLA | PASA |
| TC-16 | `test_tkt029a_actualizar_cambia_solo_lo_enviado_y_asienta` | feliz | `CA-8` | FALLA | PASA |
| TC-17 | `test_tkt029a_actualizar_inexistente` | **rechazo** | `CA-8` | FALLA | PASA |
| TC-18 | `test_hdu004_esc12_desactivar_conserva_todo_y_asienta` | feliz | `CA-9` | FALLA | PASA |
| TC-19 | `test_hdu004_esc12_desactivar_un_desactivado_o_inexistente` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-20 | `test_hdu004_esc12_dos_desactivaciones_concurrentes` | **concurrencia** | `CA-9` | FALLA | PASA |
| apoyo | `test_tkt029a_obtener_proveedor`, `test_tkt029a_listar_recorta_q_y_calcula_el_desplazamiento`, `test_tkt029a_roles_y_campos_cambiables_del_caso_de_uso` | feliz · borde | `CA-6`, `CA-7` | FALLA | PASA |

TC-21 a TC-42 pertenecen a la entrega b.

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| A1 | `rojo/fila-A1.txt` | `tester-backend` (haiku) · `desarrollador-dominio` (haiku) | 3 passed | Sí, abajo |
| A2 | `rojo/fila-A2.txt` | `tester-backend` (sonnet) · `desarrollador-sql` (sonnet) | 167 passed en los 15 archivos de la fila; suite completa 3298 passed | Sí, abajo |
| A3 | `rojo/fila-A3.txt` | `tester-backend` (haiku) · `desarrollador-aplicacion` (haiku) | 4 passed | Sí, abajo |
| A4 | `rojo/fila-A4.txt` | `tester-backend` (sonnet) · `desarrollador-aplicacion` (sonnet) | 12 passed | Sí, abajo |

**Rojo.** Cada fila falló con `failed` y cero `errors`. Las filas A1, A3 y A4 fallaron por `ModuleNotFoundError` del módulo nuevo, que es la ausencia esperada: son módulos que no existían, sin comportamiento previo que contrastar, y los imports van dentro de cada test para que el fallo sea del test y no de la colección. La fila A2 falló por ausencia de la migración y de la tabla (17 failed, 37 passed del resto de `test_tkt010_semilla_local.py`).

```text
A1: 3 failed in 0.16s
A2: 17 failed, 37 passed in 13.36s
A3: 4 failed in 2.88s
A4: 12 failed in 4.29s
```

**Verde.** Mypy, `lint-imports`, `verificar_float`, `ruff format --check` y `ruff check` limpios al cerrar cada fila (la única salvedad fue el `I001` del test de la fila A3, ya resuelto).

**Refactor.** Ninguno en las cuatro filas: el código mínimo ya coincidía con el diseño.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar** (`docker info` respondía, servidor 29.9.3):

```text
uv run pytest -q   →   3314 passed, 26 skipped in 647.72s (0:10:47)
```

Los 26 omitidos son pruebas contra los archivos reales del catálogo (`CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` sin definir, `PA-T3`); ninguna es de este ticket.

**Mutación en rutas críticas.** Un mutante a la vez, con copia previa fuera del repositorio. Huella SHA-256 de los 333 `.py` de `backend/` antes de mutar: `774e57baed2619aa5ae20b4d06017b8cb5a41f5e0f88a8db854c6e2ca0079540`. Tras revertir cada mutante la huella volvió a ser idéntica, y `git status --short` quedó igual antes y después.

| Mutante | Cambio | Test que cae | Huella con el mutante |
|---|---|---|---|
| `M-1` | `normalizar_rfc` sin `.upper()` | TC-01 | `b24ea490…a29e` |
| `M-2` | `strip()` sin argumento | TC-01 | `ceca459c…0224` |
| `M-5` | `admite_desactivacion` invertido (`is not ACTIVO`) | TC-02, TC-19 | `30b55a23…dcdb` |
| `M-3` | sin la rama del `23505` de `uq_proveedor_rfc` | TC-14, TC-15 | `8b8c68f6…723f` |
| `M-6` | `desactivar_proveedor` lee con `para_cambio=False` | TC-20 | `d8e3f486…baae5` |
| `M-10` | `asentar` con sesión nueva tras confirmar | TC-13 | `b7942036…0db2` |
| `M-9` | sin el `REVOKE DELETE` de `0013` | TC-07 | `c6abfdc6…8b3` |
| `M-7` | `icontains` sin `autoescape=True` | TC-10 | `5825d795…c463` |

No sobrevivió ningún mutante. Quedan para la entrega b: `M-4`, `M-8`, `M-11`, `M-12`, y la parte de API de `M-1`, `M-2` y `M-7` (TC-22, TC-23, TC-28).

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A1 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| A1 · verde | `desarrollador-dominio` | `haiku` | `haiku` | — |
| A2 · rojo | `tester-backend` | `haiku` | `sonnet` | Migración con fotografía de esquema y permisos por rol: se eligió `sonnet` desde el inicio para no gastar reintentos |
| A2 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «los permisos de un rol» |
| A3 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| A3 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| A4 · rojo | `tester-backend` | `haiku` | `sonnet` | Concurrencia determinista con `pg_blocking_pids` |
| A4 · verde | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador «bloqueo pesimista o concurrencia» |
| Cierre · suite y mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditorías | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |

Ningún paso subió a `opus`; ninguno necesitó un segundo intento.

## Resultado contra los criterios de aceptación

Solo los criterios que cierra la entrega a. Los demás (`CA-1` a `CA-9` por HTTP, `CA-10` esc. 1, `CA-R2`) los cierra la entrega b.

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-03, TC-08, TC-12, TC-13 |
| `CA-2` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-01, TC-14 |
| `CA-3` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-15 |
| `CA-6`, `CA-7` (repositorio) | `[M]` | Cumplido en repositorio; falta por API | TC-09, TC-10 y pruebas de apoyo |
| `CA-8` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-11, TC-16, TC-17 |
| `CA-9` (lógica) | `[M]` | Cumplido sin HTTP; falta por API | TC-02, TC-18, TC-19, TC-20 |
| `CA-10` esc. 2 | `[M]` | Cumplido | TC-07 |
| `CA-11` | `[M]` | Cumplido | TC-06 |
| `CA-R1` | `[M]` | Cumplido | TC-04, TC-05, TC-B15 y las 13 suites de la cadena |
| `CA-4`, `CA-5`, `CA-10` esc. 1, `CA-R2` | `[M]` | Pendiente: entrega b | — |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO | 3 observaciones, ningún hallazgo | 1 |
| `auditor-sql` | APROBADO | 5 observaciones, ningún hallazgo | 1 |
| `auditor-codigo` | No despachado en esta entrega | — | — |
| `auditor-seguridad` | No aplica a la entrega a (sin endpoint ni entrada externa) | — | — |
| `auditor-docs` | Se despacha en `/sdd-revisar` y `/sdd-completar` | — | — |

Ambas auditorías incluyen la sección «Qué verifiqué» ítem por ítem. Resumen de lo verificado: dinero en `NUMERIC(18,4)` y `Dinero` sin `float` (`verificar_float`: 0 hallazgos); dominio con solo `enum` y `typing`; 16 contratos de `lint-imports` mantenidos; `proveedores` solo importa `cimenta.auditoria.interfaz`; bitácora en la misma transacción con prueba específica; sin `async`; seis restricciones nombradas; ciclo `upgrade` → `downgrade -1` → `upgrade` ejecutado sobre la base local con cabeza única `0013`; `GRANT` y `REVOKE DELETE` comprobados con `aclexplode` y un `DELETE` real rechazado con `42501`; autoescape de `icontains` compilado y probado.

### Hallazgos y su resolución

Ninguno. Observaciones:

| ID | Auditor | Severidad | Ubicación | Observación | Estado |
|---|---|---|---|---|---|
| O-1 | arquitectura | Observación | `tests/test_tkt072_migracion.py:35` | `CABEZA = "0012"` obsoleta y sin uso | Fuera de alcance, anotada abajo |
| O-2 | arquitectura | Observación | `aplicacion/proveedores.py` (`listar_proveedores`) | Un `estados` vacío emitiría `IN ()`; hoy la ruta pone `[ACTIVO]` por omisión | Para la entrega b: fijarlo con una prueba |
| O-3 | ambos | Observación | `design.md` (cuerpo) | Sigue diciendo `0012` y `0011` para esta migración | Cubierto por «Ajustes de la ejecución»; `delta.md` lo cita |
| O-4 | sql | Observación | `repositorio_proveedor.py` | Sin índices para filtro, búsqueda y orden del listado | Catálogo de decenas de filas; revisar si crece |
| O-5 | sql | Observación | `repositorio_proveedor.py` | `actualizar_proveedor` cuantiza solo un `Dinero`; `count` y página son dos sentencias | Sin acción |

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `backend/tests/test_tkt072_migracion.py:35` | Constante `CABEZA = "0012"` sin uso y obsoleta | Baja |
| `sdd/tickets/tkt-029a/design.md` | El cuerpo conserva `0012`/`0011` para la migración; reescribirlo en `/sdd-completar` si se quiere | Baja |
| Base local de desarrollo | El auditor de SQL dejó la base local en `0013 (head)` tras el ciclo de migración (partía de `0011`) | Informativa |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/03-modelo-datos.md` §9 | `PROVEEDOR` añade `creado_en` y `creado_por_id`; párrafo sobre el `REVOKE DELETE` y los tres `CHECK` |
| `sdd/tickets/tkt-029a/design.md` | Filas A1 a A4 en «Hecho» y «Ajustes de la ejecución» |

El resto de la documentación listada en el diseño (`docs/api/openapi.yaml`, `servidor.ts`, `docs/05-tickets-trabajo.md`) es de la entrega b o ya estaba en el árbol de trabajo.

`python tools/verificar_docs.py` → «✓ Sin problemas» (la única nota es el aviso de finales de línea CRLF/LF de 15 archivos, que Git normaliza al commitear).

## Verificación final (entrega a)

- [x] Criterios `[M]` de la entrega a cumplidos con evidencia (los de API quedan para la b)
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: 8 de 8 mutantes aplicables muertos
- [x] Auditorías aplicables `APROBADO`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta (`tkt-029a-catalogo-proveedores`) y sin secretos en el diff; nada confirmado ni empujado (el commit local de cierre de entrega es de `git-entrega`)

---

# Entrega b · API, montaje, contrato y tipos

## Qué se implementó (entrega b)

Filas B1 y B2 del diseño: las cinco operaciones del catálogo por HTTP, su contrato publicado y los tipos del cliente.

- **API.** `proveedores/api/esquemas.py` (DTO con copias locales de `MetaPagina` y `Motivo`, RFC normalizado y validado, días `Strict`, `ProveedorCambios` con al menos una propiedad), `rutas.py` (cinco rutas `def`, con `verificar_origen` antes de `exigir_rol` en las tres mutaciones) y `montaje.py`; `servidor/fabrica.py` monta el enrutador. No existe ninguna ruta `DELETE`.
- **Contrato.** `docs/api/openapi.yaml` gana `maxLength: 200` en `nombre` y el patrón de `q`; `frontend/src/api/generado/servidor.ts` se regeneró con `npm run tipos:generar`, sin editarlo a mano.
- **Soporte de pruebas.** `borrador_comparable()` en `herramientas/soporte_tkt017_api.py` y tres entradas nuevas en `CUERPOS_VALIDOS` de `test_tkt057_csrf.py`.

## Ajustes respecto al design (entrega b)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-14 | Tres entradas nuevas en `CUERPOS_VALIDOS` de `test_tkt057_csrf.py`. | La prueba de TKT-057 exige un cuerpo válido por cada mutación protegida y falló al montar las rutas. No cambia lo que afirma. |
| 2026-11-14 | `borrador_comparable()` añadida al soporte de pruebas de contrato. | Prevista en la fila B1 como apoyo de TC-40. |
| 2026-11-14 | El docstring de `Motivo` en `presupuesto/api/esquemas.py` se iguala al de la copia de `proveedores`. | Pydantic fusiona las dos clases en el OpenAPI solo si forma y docstring coinciden (D-7; lo guardan TC-42 y `M-12`). Sin cambio de comportamiento. |
| 2026-11-14 | `docs/05-tickets-trabajo.md` indica `0013` y `0012` para la migración. | Numeración de la entrega a. |
| 2026-11-14 | `ProveedorCambios` usa `_AUSENTE: Any = cast("Any", None)` como valor por omisión. | `mypy` rechaza `Field(default=None)` en campos que no admiten `None`. |
| 2026-11-14 | El RFC se valida contra `[A-Za-zÑñ&0-9]+` antes de pasar a mayúsculas, y `actualizar_proveedor` rechaza con `ValueError` un conjunto de campos vacío o ajeno. | Hallazgos F001 y F003 de `auditor-codigo` (ver abajo). |
| 2026-11-14 | El orquestador ordenó los imports de `test_tkt029a_casos_de_uso.py` con `ruff check --fix` (`I001`). | Solo estilo; el corrector no toca tests. |

## Archivos tocados (entrega b)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/proveedores/api/esquemas.py` | nuevo | api |
| `backend/cimenta/proveedores/api/rutas.py` | nuevo | api |
| `backend/cimenta/proveedores/api/montaje.py` | nuevo | api |
| `backend/cimenta/proveedores/aplicacion/proveedores.py` | modificado (guarda de F003) | aplicación |
| `backend/servidor/fabrica.py` | modificado (monta el enrutador) | api |
| `backend/cimenta/presupuesto/api/esquemas.py` | modificado (docstring de `Motivo`) | api |
| `backend/herramientas/soporte_tkt017_api.py` | modificado (`borrador_comparable()`) | pruebas |
| `backend/tests/test_tkt029a_api_proveedores.py` | nuevo | pruebas |
| `backend/tests/test_tkt029a_casos_de_uso.py` | modificado (tests de F003, orden de imports) | pruebas |
| `backend/tests/test_tkt057_csrf.py` | modificado (tres entradas) | pruebas |
| `docs/api/openapi.yaml` | modificado | documentación |
| `frontend/src/api/generado/servidor.ts` | regenerado | cliente (generado) |
| `docs/05-tickets-trabajo.md` | modificado (numeración) | documentación |
| `sdd/tickets/tkt-029a/rojo/fila-B1.txt` y `fila-B1-correccion.txt` | nuevo | evidencia |

## Pruebas (entrega b)

Todas en `backend/tests/test_tkt029a_api_proveedores.py`, salvo las de F003.

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-21 | `test_hdu004_esc02_api_alta_responde_201` | feliz | `CA-1` | FALLA | PASA |
| TC-22 | `test_hdu004_esc03_api_rfc_duplicado` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-23 | `test_hdu004_esc02_api_forma_invalida` (parametrizada, con `ß`, `ı` y `ſ` tras F001) y `test_tkt029a_api_rfc_con_enie_minuscula_se_normaliza_a_mayuscula` | **rechazo** | `CA-4` | FALLA | PASA |
| TC-24 | `test_tkt029a_api_tope_del_nombre` | **rechazo** · borde | `CA-4` | FALLA | PASA |
| TC-25 | `test_tkt029a_api_mutaciones_sin_permiso` | **rechazo** | `CA-5` | FALLA | PASA |
| TC-26 | `test_tkt029a_api_mutaciones_sin_sesion_y_sin_csrf` y `test_tkt029a_api_el_origen_se_verifica_antes_que_el_rol` | **rechazo** | `CA-5`, `CA-R2` | FALLA | PASA |
| TC-27 | `test_hdu004_esc02_api_lista_por_omision_solo_activos` | feliz | `CA-6` | FALLA | PASA |
| TC-28 | `test_hdu004_esc12_api_lista_filtro_y_busqueda` | feliz · **rechazo** | `CA-6` | FALLA | PASA |
| TC-29 | `test_tkt029a_api_lista_parametros_invalidos` | **rechazo** | `CA-6` | FALLA | PASA |
| TC-30 | `test_tkt029a_api_lista_pagina_inalcanzable` | borde | `CA-6` | FALLA | PASA |
| TC-31 | `test_tkt029a_api_obtener_proveedor` | feliz · **rechazo** | `CA-7` | FALLA | PASA |
| TC-32 | `test_tkt029a_api_actualizar_proveedor` | feliz | `CA-8` | FALLA | PASA |
| TC-33 | `test_tkt029a_api_actualizar_cuerpo_invalido` | **rechazo** | `CA-8` | FALLA | PASA |
| TC-34 | `test_tkt029a_api_actualizar_inexistente` | **rechazo** | `CA-8` | FALLA | PASA |
| TC-35 | `test_hdu004_esc12_api_desactivar` | feliz | `CA-9` | FALLA | PASA |
| TC-36 | `test_hdu004_esc12_api_desactivar_sin_motivo` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-37 | `test_hdu004_esc12_api_desactivar_un_desactivado_o_inexistente` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-38 | `test_tkt029a_ca10_no_existe_ninguna_ruta_delete_de_proveedores` y `test_tkt029a_api_las_rutas_de_proveedores_son_def_con_sesion_y_origen_primero` | **rechazo** | `CA-10` esc. 1 | FALLA | PASA |
| TC-39 | `test_tkt029a_api_alta_ignora_campos_extra` | **rechazo** | `CA-1` | FALLA | PASA |
| TC-40 | `test_tkt029a_api_forma_publicada_igual_al_borrador` y `test_tkt029a_api_operaciones_publicadas_igual_al_borrador` | contrato | `CA-1`, `CA-6` a `CA-9` | FALLA | PASA |
| TC-41 | `test_tkt017_cab08` y `test_tkt017_cab09` y el resto de `test_tkt017_api_*.py`, sin cambios | regresión | `CA-R2` | PASA | PASA |
| TC-42 | `test_tkt029a_api_las_copias_se_publican_fusionadas` | contrato | `CA-R2` | FALLA | PASA |
| F003 | `test_tkt029a_actualizar_rechaza_presentes_vacio_o_ajeno` (cuatro variantes), en `test_tkt029a_casos_de_uso.py` | **rechazo** | `CA-8` | FALLA | PASA |

### Ciclo TDD por fila (entrega b)

| Fila | Rojo | Ejecutó | Verde | Mutación |
|---|---|---|---|---|
| B1 | `rojo/fila-B1.txt` | `tester-api` (sonnet) · `desarrollador-api` (sonnet) | `test_tkt029a_api_proveedores.py`: 100 passed antes de la corrección de F001 | Sí, abajo |
| B2 | Sin test propio: la regeneración de `servidor.ts` y el borrador se verifican con `npm run tipos:verificar` y TC-40 | `desarrollador-api` | `npm run tipos:verificar` sin diferencias | No aplica: no hay lógica |
| Corrección F001 y F003 | `rojo/fila-B1-correccion.txt` | `tester-api` (sonnet) · `corrector-revision` (sonnet) | 120 passed en `test_tkt029a_api_proveedores.py` y `test_tkt029a_casos_de_uso.py` | La salida en rojo hace de mutación: sin la corrección, los siete tests nuevos caen |

**Rojo.** La fila B1 falló por `404` `NO_ENCONTRADO` en `/api/v1/proveedores`, la ausencia esperada de las rutas. El rojo de la corrección dio `7 failed, 113 passed`: tres RFC con `ß`, `ı` y `ſ` que devolvían `201` y se guardaban como `SSAX…`, `IAX…` y `SAX…`, y cuatro variantes de `presentes` que no lanzaban `ValueError` (una con `DID NOT RAISE`, tres con `AttributeError`).

**Refactor.** Ninguno.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar** (`docker info` respondía, servidor 29.9.3):

```text
uv run pytest -q   →   3422 passed, 26 skipped in 727.17s (0:12:07)
```

`ruff format`, `ruff check`, `mypy` (337 archivos), `lint-imports` (16 contratos mantenidos) y `verificar_float` (0 hallazgos) limpios. Una corrida anterior a la corrección, con la entrega b completa, dio `3414 passed, 26 skipped`.

**Mutación en rutas críticas.** Un mutante a la vez, desde una copia fuera del repositorio, ejecutando los 100 tests de `test_tkt029a_api_proveedores.py`. Huella SHA-256 de los 337 `.py` de `backend/` antes y tras cada reversión: `4a0c3771e1b127a21dd4dac6a9ef9f1b431657bdfba576674b6c7e44f4e92f94`. Con cada mutante la huella era distinta; las nueve reversiones devolvieron la huella inicial, y `git status` quedó idéntico.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-4` | `crear_proveedor` declara `exigir_rol(*ROLES_LECTURA)` | TC-25: los cinco roles sin permiso de gestión (5 failed) |
| `M-8a` | `ESTADOS_POR_OMISION = list(EstadoProveedor)` en la ruta | TC-27, TC-28, TC-35 y TC-40 (4 failed) |
| `M-8b` | la ruta pide todos los estados cuando recibe el de omisión | TC-27, TC-28 y TC-35 (3 failed) |
| `M-8c` | el caso de uso no filtra cuando recibe `{ACTIVO}` | TC-27, TC-28 y TC-35 (3 failed) |
| `M-11` | `ProveedorCambios` sin el `model_validator` | TC-33, cuerpo vacío y solo campos desconocidos (2 failed) |
| `M-12` | docstring de `Motivo` en `proveedores` distinta de la de `presupuesto` | TC-40 `[Motivo]` y TC-42 (2 failed) |
| `M-1` (API) | `normalizar_rfc` sin `.upper()` | TC-22, variante en minúsculas (1 failed) |
| `M-2` (API) | `strip()` sin argumento | TC-23 `[rfc_salto_de_linea_final]` (1 failed) |
| `M-7` (API) | `icontains` sin `autoescape` | TC-28, `%` y `_` literales (1 failed) |

No sobrevivió ningún mutante. El diseño asigna `M-12` también a TC-41, que no tiene un test propio en este archivo.

## Modelo por paso (entrega b)

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| B1 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| B1 · verde | `desarrollador-api` | `sonnet` | `sonnet` | — |
| B2 · tipos y borrador | `desarrollador-api` | `haiku` | `sonnet` | Se hizo junto con B1, porque el borrador y las rutas se verifican entre sí |
| Cierre · mutación | `tester-api` | `sonnet` | `sonnet` | — |
| Auditorías | `auditor-arquitectura`, `auditor-seguridad`, `auditor-codigo` | `sonnet` | `sonnet` | — |
| Corrección F001 y F003 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| Corrección F001 y F003 · verde | `corrector-revision` | `sonnet` | `sonnet` | — |
| Reauditoría | `auditor-codigo` | `sonnet` | `sonnet` | — |

Ningún paso subió a `opus`. Las tres primeras auditorías de la entrega fallaron una vez por el límite de uso del servicio y se relanzaron sin cambios.

## Resultado contra los criterios de aceptación (entrega b)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-21, TC-39, TC-40 |
| `CA-2` | `[M]` | Cumplido | TC-22 |
| `CA-3` | `[M]` | Cumplido (concurrencia en los casos de uso) | TC-15 |
| `CA-4` | `[M]` | Cumplido | TC-23, TC-24 |
| `CA-5` | `[M]` | Cumplido | TC-25, TC-26 |
| `CA-6` | `[M]` | Cumplido | TC-27 a TC-30 |
| `CA-7` | `[M]` | Cumplido | TC-31 |
| `CA-8` | `[M]` | Cumplido | TC-32 a TC-34 y las cuatro variantes de F003 |
| `CA-9` | `[M]` | Cumplido | TC-35 a TC-37 |
| `CA-10` | `[M]` | Cumplido | TC-38 (esc. 1) y TC-07 (esc. 2) |
| `CA-11` | `[M]` | Cumplido | TC-06 |
| `CA-R1` | `[M]` | Cumplido | Suite completa, 3422 passed |
| `CA-R2` | `[M]` | Cumplido | TC-26, TC-41, TC-42 |

## Auditorías (entrega b)

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO | 1 observación (O-1) | 1 |
| `auditor-seguridad` | APROBADO | 4 observaciones bajas; la de la normalización Unicode del RFC es la misma que F001 y quedó resuelta | 1 |
| `auditor-codigo` | APROBADO tras la reauditoría | F001 y F003 resueltos; 7 observaciones menores | 2 |
| `auditor-sql` | No despachado: la entrega b no toca esquema ni migración | — | — |
| `auditor-docs` | Se despacha en `/sdd-revisar` y `/sdd-completar` | — | — |

### Hallazgos y su resolución (entrega b)

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | código y seguridad | Mayor | `proveedores/api/esquemas.py` (`_rfc`) | `str.upper()` convierte `ß`, `ı` y `ſ` en letras ASCII: el RFC se aceptaba y se guardaba reescrito | Resuelto: se rechaza todo carácter fuera de `[A-Za-zÑñ&0-9]` antes de normalizar; reauditado |
| F003 | código | Menor | `proveedores/aplicacion/proveedores.py` (`actualizar_proveedor`) | Aceptaba un conjunto de campos vacío o ajeno | Resuelto: `ValueError` antes de abrir la transacción; reauditado |
| F002 | código | Menor | `proveedores/api/esquemas.py` (`sin_nul`) | El mensaje dice «motivo» aunque también valida `nombre` | Aceptado: es copia idéntica de la de `presupuesto` por D-7 y no llega al cliente como texto propio |
| F004 a F009 | código | Menor | tests y esquemas | Observaciones de tipado y estilo | Aceptadas como observaciones, sin cambio |
| O-1 | arquitectura | Observación | `tests/test_tkt072_migracion.py:35` | `CABEZA = "0012"` obsoleta | Ya anotada en «Hallazgos fuera de alcance» |
| — | código (reauditoría) | Observación | `aplicacion/proveedores.py` | El docstring de `actualizar_proveedor` no menciona el `ValueError` nuevo | Sin acción; no bloquea |

La observación O-2 de la entrega a (un `estados` vacío emitiría `IN ()`) queda cubierta por `M-8c` y TC-27: la ruta siempre pasa `[ACTIVO]` por omisión.

## Documentación actualizada (entrega b)

| Documento | Qué cambió |
|---|---|
| `docs/api/openapi.yaml` | `maxLength: 200` en `nombre` y patrón de `q`, las cinco operaciones del catálogo |
| `frontend/src/api/generado/servidor.ts` | Regenerado con `npm run tipos:generar` |
| `docs/05-tickets-trabajo.md` | Migración `0013` sobre `0012` |
| `sdd/tickets/tkt-029a/design.md` | Filas B1 y B2 en «Hecho» y cinco ajustes más |

## Verificación final (entrega b)

- [x] Criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde: 3422 passed, 26 skipped
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: 9 de 9 mutantes muertos
- [x] Auditorías aplicables `APROBADO`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios
- [x] Rama correcta (`tkt-029a-catalogo-proveedores`)
