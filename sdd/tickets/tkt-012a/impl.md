# Impl · TKT-012a · Alta y consulta de obras

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta.md](delta.md)

## Entrega a · backend (filas A1 a A5)

### Qué se implementó

La entrega a deja completo y probado el backend de las tres rutas `crear_obra`, `listar_obras` y `obtener_obra`. El dominio gana `dominio/obra.py` con la normalización del código y la regla del rango de los porcentajes (`PA-02`, `PA-18`). La infraestructura completa el modelo Core de `obra`, añade el de `empresa` y un repositorio propio. El caso de uso `aplicacion/obras.py` abre una sola transacción, asienta la bitácora dentro de ella y traduce el `23505` de `uq_obra_codigo` a `409 CODIGO_OBRA_DUPLICADO`, sin comprobación previa. La API publica los tres endpoints tal como el borrador OpenAPI, con los `maxLength` de `D-5`, y el cliente regenera `servidor.ts`. No hay migración.

### Ajustes respecto al design

Ninguna fila quedó `⚠ Ajustado`. Hubo seis precisiones de ejecución que el diseño no preveía y que no cambian su alcance:

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-10 | La rama se llama `tkt-012a-alta-de-obras`, renombrada desde la rama local vacía `tkt-012a-alta-y-mantenimiento-de-obras`, que tenía 0 commits propios. | Decisión de la persona dueña al abrir la rama: una sola rama por ticket y el nombre que fija `_index.md`. |
| 2026-11-10 | `FilaObraCompleta` no expone `creado_por_id` ni `empresa_id`; TC-05 los comprueba con SQL sobre la tabla `obra`. | El diseño pide comprobar `creado_por_id` pero no lo incluye en la firma del repositorio. El dato queda guardado y verificado; no se amplía la firma. |
| 2026-11-10 | Tres pruebas más en `test_tkt012a_alta_obra.py` fuera del plan: rango de porcentajes en el caso de uso, `obtener_obra` con `listar_obras`, y obra inexistente. | Sin la primera, el mutante `M-4` no tenía test que lo matara; las otras cubren `CA-7` y `CA-8` desde la capa de aplicación. |
| 2026-11-10 | Dos pruebas de apoyo en `test_tkt012a_api_obras.py` (el origen se verifica antes que el rol; las rutas de obra son `def`, con sesión y origen primero). | Vigilan la regla 11 y el orden de las dependencias que declara el diseño. |
| 2026-11-10 | En `test_tkt017_api_congelado.py::test_tkt017_operation_id_de_las_rutas_de_presupuesto` (TC-B19), además de ampliar `IMPLEMENTADAS_DE_PRESUPUESTO` y `esperadas`, el filtro de `esperadas` acepta `x-tickets` con `TKT-012`. | Las tres operaciones traen `x-tickets: [TKT-012]`; sin ese filtro no entrarían en `esperadas`. Actualización declarada en la fila A4 (hallazgo 1 de Impacto); no se debilita ninguna aserción. |
| 2026-11-10 | `test_tkt057_csrf.py` gana la entrada `POST /api/v1/obras` en `CUERPOS_VALIDOS`. | Ese test exige un cuerpo válido por cada ruta que muta. No estaba en el diseño; es una ampliación mecánica y no cambia ninguna aserción. |

Dos decisiones de implementación que el desarrollador de la API documentó: `tipo_contrato` lleva el respaldo `json_schema_extra={"enum": [...]}` porque Pydantic publica el `Literal` de un solo valor como `const` (E-3 confirmada); y `actualizado_en` se omite de la respuesta cuando no tiene valor (`response_model_exclude_unset`), porque el borrador lo declara cadena no nula y no obligatoria. `umbral_alerta_pct` y `linea_base_vigente_id` siguen saliendo como `null`, que el borrador sí admite. `TextoObra` se sustituyó por tres alias explícitos (`CodigoObra`, `NombreObra`, `DomicilioObra`) porque una fábrica de alias no pasa `mypy --strict`.

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/obra.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/aplicacion/obras.py` | nuevo | aplicación |
| `backend/cimenta/presupuesto/infraestructura/repositorio_obra.py` | nuevo | infraestructura |
| `backend/cimenta/presupuesto/infraestructura/tablas.py` | modificado | infraestructura |
| `backend/cimenta/presupuesto/api/rutas_obras.py` | nuevo | api |
| `backend/cimenta/presupuesto/api/esquemas.py` | modificado | api |
| `backend/cimenta/presupuesto/api/montaje.py` | modificado | api |
| `docs/api/openapi.yaml` | modificado (`maxLength` de `nombre` y `domicilio`, `D-5`) | api |
| `frontend/src/api/generado/servidor.ts` | regenerado | frontend |
| `backend/tests/test_tkt012a_dominio_obra.py` | nuevo | pruebas |
| `backend/tests/test_tkt012a_repositorio_obra.py` | nuevo | pruebas |
| `backend/tests/test_tkt012a_alta_obra.py` | nuevo | pruebas |
| `backend/tests/test_tkt012a_api_obras.py` | nuevo | pruebas |
| `backend/tests/test_tkt017_api_congelado.py` | modificado (TC-B19, declarado) | pruebas |
| `backend/tests/test_tkt057_csrf.py` | modificado (`CUERPOS_VALIDOS`) | pruebas |

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 a TC-04 | `test_hdu001_esc02_dominio_*` (8 casos) | feliz · borde · **rechazo** | `CA-1`, `CA-5` | FALLA | PASA |
| TC-05 a TC-08 | `test_tkt012a_repositorio_*` | feliz · borde | `CA-1`, `CA-7`, `CA-8` | FALLA | PASA |
| TC-09, TC-10 | `test_hdu001_esc02_alta_guarda_la_obra_y_asienta_crear`, `..._bitacora_en_la_misma_transaccion` | feliz · **rechazo** | `CA-1` | FALLA | PASA |
| TC-11 | `test_hdu001_esc03_alta_codigo_duplicado` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-12 | `test_hdu001_esc03_dos_altas_concurrentes_mismo_codigo` | **concurrencia** | `CA-3` | FALLA | PASA |
| TC-13 | `test_tkt012a_alta_sin_una_unica_empresa_activa` | **rechazo** | `CA-1` (A9) | FALLA | PASA |
| TC-14 a TC-18 | `test_hdu001_esc02_api_*` | feliz · **rechazo** · borde | `CA-1`, `CA-4`, `CA-5` | FALLA | PASA |
| TC-19, TC-20 | `test_tkt012a_api_alta_sin_permiso`, `..._sin_sesion_y_sin_csrf` | **rechazo** | `CA-6` | FALLA | PASA |
| TC-21 a TC-29 | `test_tkt012a_api_*` | feliz · **rechazo** · borde | `CA-4`, `CA-7`, `CA-8` | FALLA | PASA |
| TC-30 | `test_tkt012a_api_forma_publicada_igual_al_borrador` | contrato | `CA-1`, `CA-7`, `CA-8` | FALLA | PASA |
| TC-31 | `test_hdu001_esc14_obra_creada_por_api_se_congela_y_pasa_a_activa` | regresión | `CA-R1` | FALLA | PASA |
| TC-R2 | `test_tkt011_estructura.py` sin cambios | regresión | `CA-R2` | PASA | PASA |

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| A1 | `rojo/fila-A1.txt`: 8 failed, 0 errors (`ModuleNotFoundError`) | `tester-backend` · `desarrollador-dominio` | 8 passed | Sí, ver abajo |
| A2 | `rojo/fila-A2.txt`: 4 failed, 0 errors (`ModuleNotFoundError`; los fixtures corrieron contra la base migrada) | `tester-backend` · `desarrollador-aplicacion` | 241 passed (nuevos más TKT-017 y TKT-011) | No aplica (repositorio sin regla propia) |
| A3 | `rojo/fila-A3.txt`: 8 failed, 0 errors (`ModuleNotFoundError`, `ImportError` del módulo ausente) | `tester-backend` · `desarrollador-aplicacion` | 8 passed, TC-12 incluido | Sí, ver abajo |
| A4 | `rojo/fila-A4.txt`: 69 failed, 0 errors (ruta ausente `404`, componentes no publicados, TC-B19 por tres operaciones sin publicar) | `tester-api` · `desarrollador-api` | Suite completa 2763 passed y 2 failed por defectos de test; devueltos y corregidos: 210 passed en las cuatro suites afectadas | Sí, ver abajo |
| A5 | `rojo/fila-A5.txt`: `npm run tipos:verificar` falla con «Difiere: src/api/generado/servidor.ts» | orquestador (herramienta de generación, sin código escrito a mano) | `tipos:generar`, `tipos:verificar` («Tipos al día»), `typecheck` y `verificar_docs.py` en verde | No aplica (artefacto generado) |

**Tests devueltos al tester.** En A4 el desarrollador de la API reportó dos fallos que eran defectos de las pruebas, y los corrigió `tester-api`: TC-27 intentaba pasar una línea base de `BORRADOR` a `SUPERSEDIDA`, lo que el disparador de `RN-01` rechaza con razón (ahora la versión anterior pasa por `CONGELADA`); y `test_tkt057_csrf.py` exigía una entrada de `POST /api/v1/obras` en `CUERPOS_VALIDOS`. Ningún desarrollador editó un test.

**Refactor.** A1: solo se completaron los docstrings con el escenario. A2: dos funciones auxiliares que devolvían `Any` pasaron a constantes de módulo. A3: se tipó `ahora` como `datetime` y se quitaron dos `# type: ignore`. A4: tres alias explícitos en lugar de la fábrica de alias; `ruff` reordenó un import.

**Evidencia de ejecución al cerrar** (`docker info` responde, Server 29.9.3):

```text
================ 2765 passed, 26 skipped in 569.45s (0:09:29) =================
(corrida del 2026-11-10, al cerrar la entrega a)
```

Los 26 omitidos son pruebas de TKT-013 a TKT-016 con `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` sin definir (`PA-T3`); no tienen relación con este ticket.

**Mutación en rutas críticas.** Se hizo copia previa de los tres archivos mutados fuera del repositorio, un mutante a la vez. La huella SHA-256 de todos los `.py` de `backend/` fue `edbc39ab69958cd650c663e405417131e77f2af33ec28e542f860c32161b777a` antes del primer mutante, tras cada restauración y al final. `git status` y `git diff --stat` quedaron idénticos (8 archivos, 441 inserciones, 4 borrados). Huellas finales de los archivos mutados: `dominio/obra.py` `096da8de…2a6a`, `aplicacion/obras.py` `972ac9ae…77de`, `api/rutas_obras.py` `8c74c932…25ac`.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-1` | `valor <= 1` pasa a `<` | `test_hdu001_esc02_dominio_porcentajes_en_rango_y_bordes` |
| `M-2a` | `0 <= valor` pasa a `0 < valor` | el mismo test de bordes |
| `M-2b` | umbral `< 0` pasa a `<= 0` (el código no usa `>=`; se aplicó el equivalente) | el mismo test de bordes |
| `M-3` | se quita la rama del `23505` de `uq_obra_codigo` | `test_hdu001_esc03_alta_codigo_duplicado`, `test_hdu001_esc03_dos_altas_concurrentes_mismo_codigo` y `test_hdu001_esc03_api_codigo_duplicado` |
| `M-4` | `crear_obra` no valida el rango | `test_hdu001_esc02_alta_porcentaje_fuera_de_rango` y las cinco filas de `test_hdu001_esc02_api_porcentaje_fuera_de_rango` |
| `M-5` | `crear_obra` declara `exigir_rol(*ROLES_LECTURA_OBRA)` | `test_tkt012a_api_alta_sin_permiso` (RESIDENTE, COMPRAS, ALMACEN, ADMINISTRACION) |
| `M-6` | `asentar` en una sesión nueva tras confirmar | `test_hdu001_esc02_alta_bitacora_en_la_misma_transaccion` |
| `M-7a` | `normalizar_codigo_obra` sin `.upper()` | `test_hdu001_esc02_dominio_normaliza_el_codigo` |
| `M-7b` | el mismo cambio, contra el caso de uso y la API | `test_hdu001_esc03_alta_codigo_duplicado` y `test_hdu001_esc03_api_codigo_duplicado` |

### Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A1 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| A1 · verde | `desarrollador-dominio` | `haiku` | `haiku` | — |
| A2 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| A2 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| A3 · rojo | `tester-backend` | `haiku` | `sonnet` | El tester no baja del modelo del desarrollador cuyo trabajo verifica (A3 va en `sonnet`) |
| A3 · verde | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador «concurrencia» (§14.2) |
| A4 · rojo y corrección de tests | `tester-api` | `haiku` | `sonnet` | Mismo criterio: el desarrollador de A4 va en `sonnet` |
| A4 · verde | `desarrollador-api` | `sonnet` | `sonnet` | Disparador «los permisos de un rol» (§14.2) |
| A5 | orquestador | `haiku` | sin agente | Fila mecánica: solo ejecutar la generación de tipos y verificarla |
| Cierre · suite y mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Cierre · auditoría | `auditor-arquitectura` | `sonnet` | `sonnet` | — |

El orquestador no subió ningún paso a `opus`. Un primer intento del tester de A4 se cortó por el límite de uso de la cuenta, no por un fallo del paso, y se reanudó con el mismo agente.

### Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` a `CA-3` | `[M]` | Cumplido | TC-05, TC-09 a TC-15, TC-24 |
| `CA-4`, `CA-5` | `[M]` | Cumplido | TC-02 a TC-04, TC-16 a TC-18, TC-21 |
| `CA-6` | `[M]` | Cumplido | TC-19, TC-20 |
| `CA-7`, `CA-8` | `[M]` | Cumplido | TC-06, TC-07, TC-22 a TC-30 |
| `CA-R1`, `CA-R2` | `[M]` | Cumplido | TC-31; `test_tkt011_estructura.py` sin cambios en verde |
| `CA-9` a `CA-13`, `CA-R3` | `[M]` | Pendiente | Entrega b |

### Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 0 críticos, 0 mayores, 0 menores; 2 observaciones | 1 |
| `auditor-sql` | No aplica | No hay migración ni DDL; solo metadatos Core en `tablas.py` | — |

Qué verificó `auditor-arquitectura`, ítem por ítem: reglas 1 y 2 (sin `float`; `dominio/obra.py` solo importa `enum` y `tipos_base`, con `lint-imports` en 16 contratos y `verificar_float` sin hallazgos); regla 3 (solo `cimenta.auditoria.interfaz` e `identidad.interfaz`, ninguna consulta toca tablas de otro módulo); regla 4 (solo un `LEFT OUTER JOIN` de lectura contra `linea_base`, y TC-31 prueba que la obra de la API se congela); reglas 5 y 6 (el ticket no toca el consumido y el asiento lleva `obra_id`); regla 8 (`asentar` en la misma sesión del `begin()`, sin `after_commit`; TC-10 lo comprueba); regla 9 (sesión por la interfaz de identidad); regla 11 (las tres rutas son `def`, vigilado por una prueba); regla 14 (cada regla con su rechazo); regla 17 (sin nómina, destajo, captura sin conexión ni evidencia). Reglas 7, 10, 12, 13, 15 y 16 no aplican a este diff. `tablas.py` no emite DDL y no hay `create_all`. El contrato de error usa un `codigo` del catálogo cerrado.

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| O-001 | `auditor-arquitectura` | Observación | `esquemas.py`, `test_tkt017_api_congelado.py` | La copia de trabajo tiene finales de línea CRLF y Git los normaliza a LF al confirmar | Persiste; sin acción, `verificar_docs.py` ya lo avisa para 18 archivos |
| O-002 | `auditor-arquitectura` | Observación | `aplicacion/obras.py:181-182` | Con cero o varias empresas activas el alta responde `500` | Persiste; es lo que declara el diseño (`A9`, TC-13) |

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/05-tickets-trabajo.md`, `sdd/tickets/tkt-018a/`, `sdd/tickets/tkt-029a/` | El árbol de trabajo trae artefactos de otros tickets sin commitear. El commit de este ticket no debe arrastrarlos | Baja |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/api/openapi.yaml` | `maxLength` 200 y 500 en `nombre` y `domicilio` de `ObraNueva` (`D-5`) |
| `frontend/src/api/generado/servidor.ts` | Regenerado |

`python tools/verificar_docs.py` → «Sin problemas». El boceto de `docs/08-wireframes.md` y los apuntes de `README.md` y `docs/arranque-local.md` corresponden a la entrega b.

### Verificación final de la entrega a

- [x] Criterios `[M]` de la entrega (`CA-1` a `CA-8`, `CA-R1`, `CA-R2`) cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite completa en verde, con la salida pegada arriba
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en rutas críticas, con tabla y huellas
- [x] `auditor-arquitectura` `APROBADO`; `auditor-sql` no aplica
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada por esta entrega actualizada
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta (`tkt-012a-alta-de-obras`) y sin secretos en el diff

## Entrega b · frontend y extremo a extremo (filas B1 a B5)

### Qué se implementó

La entrega b lleva la alta y la consulta de obras a la interfaz. `compartido/dinero/dinero.ts` gana `porcentajeAFraccion`, que convierte el porcentaje que escribe la persona (15) en la fracción que espera el servidor (`"0.150000"`) con `decimal.js`. `etiquetas.ts` rotula la acción `VER_OBRA` como «Ver la obra» y pinta el detalle `obra_existente`. `FormularioCatalogo` admite casilla y desplegable nativos. El armazón gana la sección «Obras» (`/obras`) para los seis roles, al final de la tabla. La pantalla `PantallaObras` muestra los cuatro estados, un botón `+` solo para Director de Proyectos y Dirección General, el formulario de alta y el conflicto de código duplicado en línea. El sembrador de humo se parametriza con `CIMENTA_HUMO_ROL` y `CIMENTA_HUMO_NOMBRE`, y la preparación global siembra también al Director de Proyectos para `obras.spec.ts`.

### Ajustes respecto al design

Ninguna fila quedó `⚠ Ajustado`. Precisiones de la ejecución que el diseño no preveía:

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-10 | `FormularioCatalogo.test.tsx`, test `tkt008_ca11_esc05 · duplicado en línea (TC-86)`: las dos aserciones pasan de `name: "VER_OBRA"` a `name: "Ver la obra"`, con un comentario que cita la fila B1. **Cambio declarado de una prueba de TKT-008c.** | La fila B1 rotula la acción `VER_OBRA` (`CA-11`, `D-7`) y TC-86 buscaba la etiqueta cruda. El diseño afirmaba «las 19 de TKT-008c sin modificar» (`CA-R3`) y no previó este choque. La persona dueña decidió el 2026-11-10, en la sesión, actualizar esas dos aserciones, y `CA-R3` se lee desde entonces como «ningún comportamiento de los campos de texto, correo y fecha cambia». El resto del archivo (21 pruebas de TKT-008c, no 19) queda sin modificar y en verde |
| 2026-11-10 | `secciones.test.ts` y `Armazon.test.tsx` se actualizan como declara la fila B3 (`D-3`): «Obras» al final de cada lista, diez títulos en lugar de nueve (`TITULOS_DE_LAS_NUEVE` se renombra `TITULOS_DE_LAS_DIEZ`, cambio mecánico no listado en el diseño) y «Obras» primera en el menú de ALMACEN. `tkt008_ca06_esc01` no cambia | La tabla del wireframe §2 cambia por `D-3`; solo se amplía lo esperado |
| 2026-11-10 | La ruta de «Obras» nace en B3 con el marcador `rutaMarcador("OBRAS")` y B4 lo sustituye por `PantallaObras` | El helper ya existía y evita escribir el JSX a mano |
| 2026-11-10 | El desplegable y la casilla usan `Label` y elementos nativos; `CLASE_DESPLEGABLE` copia a mano las clases del `Input` de shadcn | Escalera del diseño (peldaño 2); shadcn no tiene `select` ni `checkbox` instalados |
| 2026-11-10 | `obraOptions`, listada en el diseño, no se entrega | Sin ficha de obra (`D-7`) no tiene consumidor; `auditor-codigo` la marcó como código muerto (F001) y se borró |
| 2026-11-10 | En el sembrador de humo, el `ON CONFLICT` también actualiza `nombre`; el usuario sembrado para el Director se llama «Humo Director de Proyectos» | Decisión del desarrollador, no está en el diseño. Sin ella, volver a sembrar con otro `CIMENTA_HUMO_NOMBRE` conservaría el nombre viejo. El comportamiento por omisión (COMPRAS) no cambia |
| 2026-11-10 | `playwright.config.ts` no se tocó. El E2E corrió tras detener un servidor de Vite de otro repositorio (`C:\GitHub\NESGoWeb`, proceso 10980) que ocupaba el puerto 5173 | La persona dueña autorizó detenerlo en la sesión |

**Huecos que el desarrollador reportó y el diseño no resuelve** (no se decidieron por cuenta propia; quedan para la persona dueña):

1. Si el alta devolviera un `409` de regla de negocio o de concurrencia (el borrador no los declara para `crear_obra`), `FormularioCatalogo` los manda a `alBloqueo`, que es obligatorio: el formulario se cierra, el bloqueo se pinta encima de la tabla y se pierde lo capturado. El conflicto de código duplicado, que es el esperado, sí queda en línea dentro del formulario.
2. El botón `+` aparece en todos los estados, no solo en el vacío, para no tener dos botones con el mismo nombre.
3. Los textos del estado vacío, los rótulos «Retención de destajo (%)», «Fondo de garantía (%)» y «Umbral de alerta (%)», la opción «Precio alzado máximo garantizado» y los nombres de estado los redactó el desarrollador `(asumido)`; el diseño no los fija.
4. `porcentajeAFraccion` rechaza en el cliente un umbral de `-5` o `1000` como «Escribe un porcentaje, como 15» (así lo aprobó TC-F01); el servidor lo habría rechazado con `FUERA_DE_RANGO`. Hoy el cliente decide una parte de `PA-18` (observación O1 de `auditor-arquitectura`).

Supuestos de los tests de B4 y B5, todos de presentación y marcados `(asumido)`: etiquetas de campo, nombre del botón «Guardar», estado legible en la tabla, `<table>` real, mensaje «Ya existe una obra con el código …», el código `E2E-` en mayúsculas porque el servidor normaliza, y que TC-E2 compruebe la tabla tras pulsar «Ver la obra» porque el diálogo modal oculta la tabla.

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `frontend/src/compartido/dinero/dinero.ts` | modificado (`porcentajeAFraccion`) | frontend |
| `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | modificado | frontend |
| `frontend/src/compartido/formularios/FormularioCatalogo.tsx` | modificado (casilla, desplegable, `CampoFormulario`) | frontend |
| `frontend/src/app/navegacion/secciones.ts` | modificado | frontend |
| `frontend/src/modulos/presupuesto/rutas.tsx` | modificado | frontend |
| `frontend/src/modulos/presupuesto/obras/obras.consultas.ts` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/obras/obras.formulario.ts` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/obras/PantallaObras.tsx` | nuevo | frontend |
| `frontend/e2e/sembrar_usuario_humo.py` | modificado | frontend (herramienta de humo) |
| `frontend/e2e/preparacion-global.ts` | modificado | frontend (herramienta de humo) |
| `frontend/src/compartido/dinero/dinero.test.ts` | modificado (TC-F01) | pruebas |
| `frontend/src/compartido/formularios/ConflictoEnLinea.test.tsx` | modificado (TC-F02) | pruebas |
| `frontend/src/compartido/formularios/FormularioCatalogo.test.tsx` | modificado (TC-F03, TC-F04 y TC-86, declarado) | pruebas |
| `frontend/src/app/navegacion/secciones.test.ts`, `frontend/src/app/armazon/Armazon.test.tsx` | modificados (TC-F05, declarado) | pruebas |
| `frontend/src/modulos/presupuesto/obras/PantallaObras.test.tsx` | nuevo (TC-F06 a TC-F11) | pruebas |
| `frontend/e2e/obras.spec.ts` | nuevo (TC-E1, TC-E2) | pruebas |
| `frontend/e2e/humo.spec.ts` | modificado («Obras» en tercer lugar) | pruebas |
| `backend/tests/test_tkt010_semilla_local.py` | modificado (dos pruebas del sembrador) | pruebas |
| `docs/08-wireframes.md`, `README.md`, `docs/arranque-local.md` | modificados | documentación |

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-F01 | `hdu001_esc02 · TC-F01 · …` (11 casos) | feliz · **rechazo** | `CA-10` | FALLA | PASA |
| TC-F02 | `hdu001_esc03 · TC-F02 · …` | **rechazo** | `CA-11` | FALLA | PASA |
| TC-F03, TC-F04 | `hdu001_esc02 · CA-10 / CA-11 (TC-F03 / TC-F04)` (5 casos) | feliz · **rechazo** | `CA-10`, `CA-11`, `CA-R3` | FALLA | PASA |
| TC-F05 | `TKT-012a · CA-9 · TC-F05 · …` (dos pruebas) | feliz | `CA-9` | FALLA (una; la guarda de `primeraSeccion` nace en verde a propósito) | PASA |
| TC-F06 a TC-F11 | `PantallaObras.test.tsx` (22 casos) | feliz · **rechazo** | `CA-9` a `CA-12` | FALLA | PASA |
| TC-E1, TC-E2 | `e2e/obras.spec.ts` | feliz · **rechazo** | `CA-13` | FALLA | PASA |
| — | `test_tkt012a_b5_*` (2 pruebas del sembrador) | feliz | `CA-13` (apoyo) | FALLA | PASA |
| `CA-R3` | las 21 pruebas de TKT-008c de `FormularioCatalogo.test.tsx` | regresión | `CA-R3` | PASA | PASA (con TC-86 actualizado, declarado) |

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| B1 | `rojo/fila-B1.txt`: 12 failed, 0 errors (`porcentajeAFraccion is not a function`; etiquetas ausentes). El mismo archivo guarda el rojo de TC-86 actualizado: 1 failed, 20 passed | `tester-frontend` · `desarrollador-react` | `Tests 49 passed (49)` en los tres archivos; `npm test` 226 passed | No aplica (conversión de formato y etiquetas, sin regla propia) |
| B2 | `rojo/fila-B2.txt`: 5 failed, 21 passed, 0 errors | `tester-frontend` · `desarrollador-react` | `FormularioCatalogo` 26 passed; `npm test` 231 passed | No aplica (componente de presentación) |
| B3 | `rojo/fila-B3.txt`: 5 failed, 31 passed, 0 errors | `tester-frontend` · `desarrollador-react` | `secciones` y `Armazon` 36 passed; `npm test` 233 passed | No aplica |
| B4 | `rojo/fila-B4.txt`: 22 failed, 0 errors | `tester-frontend` (`sonnet`) · `desarrollador-react` | `PantallaObras` 22 passed; `npm test` 255 passed | No aplica (el rango lo decide el servidor, ya mutado en la entrega a) |
| B5 | `rojo/fila-B5.txt`: 2 failed en el sembrador y 2 en `obras.spec.ts`, 0 errors | `tester-frontend` (`sonnet`) · `desarrollador-react` | Sembrador: 38 passed; `npm run e2e` 5 passed (`verde-e2e-B5.txt`) | No aplica |

**Evidencia de ejecución al cerrar** (`docker info` responde, Server 29.9.3):

```text
npm test        → Test Files  18 passed (18) · Tests  255 passed (255)
npm run e2e     → 5 passed (9.5s)   [humo.spec.ts ×3, obras.spec.ts ×2]
```

La suite de backend se volvió a correr al final de la entrega b, porque los hallazgos de `auditor-codigo` tocaron `esquemas.py` y `obras.py` tras la primera corrida; su resultado está en `suite-final-backend.txt` de este directorio.

**Mutación en rutas críticas:** la entrega b no añade reglas de negocio; las rutas críticas (rango, unicidad, permiso, bitácora) se mutaron en la entrega a. En B5, el rojo del sembrador exige que `CIMENTA_HUMO_ROL` se lea de verdad.

### Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| B1 · rojo | `tester-frontend` | `haiku` | `haiku` | — |
| B1 · TC-86 | `tester-frontend` | `haiku` | `haiku` | — |
| B1 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| B2 · rojo y verde | `tester-frontend`, `desarrollador-react` | `haiku` | `haiku` | — |
| B3 · rojo y verde | `tester-frontend`, `desarrollador-react` | `haiku` | `haiku` | — |
| B4 · rojo | `tester-frontend` | `haiku` | `sonnet` | La pantalla trae MSW y varios flujos; un rojo flojo habría dejado pruebas que no discriminan |
| B4 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| B5 · rojo | `tester-frontend` | `haiku` | `sonnet` | Mezcla Playwright, base real y sembrador |
| B5 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| Documentación | agente de propósito general | — | `sonnet` | Prosa de documentación en español |
| Auditorías | `auditor-arquitectura`, `auditor-seguridad`, `auditor-codigo` | `sonnet` | `sonnet` | — |
| Correcciones | `corrector-revision` | `haiku` | `haiku` | — |

El orquestador no subió ningún paso a `opus`.

### Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-9` | `[M]` | Cumplido | TC-F05, TC-F07, TC-F08 |
| `CA-10` | `[M]` | Cumplido | TC-F01, TC-F03, TC-F09 |
| `CA-11` | `[M]` | Cumplido | TC-F02, TC-F04, TC-F10, TC-F11 (con el texto del servidor en el `403`, `D-6`) |
| `CA-12` | `[M]` | Cumplido | TC-F06 |
| `CA-13` | `[M]` | Cumplido | TC-E1, TC-E2 |
| `CA-R3` | `[M]` | Cumplido con la actualización declarada de TC-86 | 21 pruebas de TKT-008c; ver «Ajustes respecto al design» |

### Auditorías de la entrega b

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `REQUIERE CAMBIOS` → resueltos | 2 Menores (F001 declarar TC-86, hecho arriba; F002 frase del boceto, corregida); 4 observaciones | 1 |
| `auditor-seguridad` | `APROBADO` | 3 observaciones BAJA (F001 futuro permiso por obra; F002 mensaje NUL «El motivo»; F003 filtro `estado` sin tope, acotado a 4) | 1 |
| `auditor-codigo` | `REQUIERE CAMBIOS` (ciclo 2) | Ciclo 1: 7 Menores. Resueltos: F001, F003, F004, F005, F006, F008, F009. **Persisten por decisión pendiente: F002, F007** | 2 |

Qué verificó `auditor-arquitectura` en la entrega b, ítem por ítem: regla 1 (sin `Number`, `parseFloat` ni `parseInt` sobre porcentajes; `decimal.js`; cuerpo como cadena; `"15"` da `"0.150000"`); regla 9 (sin `localStorage`, `sessionStorage`, `document.cookie` ni JWT; el botón `+` es cortesía de navegación y el control real es el `403`); regla 10 (el cliente valida la forma, no el rango; el duplicado y la acción `VER_OBRA` vienen del servidor); regla 17 (sin nómina, destajo operativo, cola, evidencia ni adaptador simulado); tipos generados del OpenAPI y no a mano; ningún Zod espeja una respuesta; `components/ui/` sin componentes nuevos y `package.json` sin cambios; los cuatro estados y su prueba; TanStack con `queryOptions`, clave jerárquica y `staleTime`; sin `any`, `!` ni `eslint-disable`; accesibilidad del botón `+` y de los campos; filas B3 y B5.

`auditor-seguridad` cubrió también la entrega a: autorización por rol (el MVP no tiene permiso por obra), asignación masiva, secretos, hashing, guarda de destino del sembrador, inyección SQL, validación de entrada, CSRF, sesión, bitácora, XSS, `pip-audit` sin vulnerabilidades.

#### Hallazgos abiertos

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F002 | `auditor-codigo` | Menor | `aplicacion/obras.py` y `aplicacion/traduccion_motor.py` | La extracción de `sqlstate` y `constraint_name` está duplicada. Quitarla exige tocar `traduccion_motor.py` de TKT-017, que el diseño aprobado dice que no se toca | Persiste · decisión de la persona dueña |
| F007 | `auditor-codigo` | Menor | `test_tkt012a_repositorio_obra.py`, `test_tkt012a_api_obras.py`, `test_tkt012a_alta_obra.py` | `Any` sin justificar en auxiliares de prueba | Persiste · decisión de la persona dueña (ningún desarrollador edita tests) |
| F002 (seguridad) | `auditor-seguridad` | Baja | `api/esquemas.py:40-43` | `_sin_nul` se reutiliza en `codigo`, `nombre` y `domicilio`, pero su mensaje dice «El motivo no admite el carácter NUL». Es compartido con TKT-017 | Persiste · observación |
| O1 | `auditor-arquitectura` | Observación | `dinero.ts`, `obras.formulario.ts` | El cliente rechaza un umbral negativo por formato; ver hueco 4 arriba | Persiste · observación |

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/05-tickets-trabajo.md`, `sdd/tickets/tkt-018a/`, `sdd/tickets/tkt-029a/` | El árbol de trabajo trae artefactos de otros tickets sin commitear; el commit de este ticket no debe arrastrarlos | Baja |
| `FormularioCatalogo.tsx` | El foco inicial solo se asigna si el primer campo es de texto; si un formulario futuro empieza por una casilla o un desplegable, se pierde sin error | Baja |
| `sembrar_usuario_humo.py` | Conserva el respaldo `CIMENTA_PRUEBA_CORREO` y `CIMENTA_PRUEBA_CONTRASENA`, ya decidido como excepción declarada | Baja, ya decidido |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/08-wireframes.md` | Boceto de la pantalla «Obras» (§2b), fila «Obras» en la tabla de secciones del §2 y reconciliación del estado vacío y del selector de obra |
| `README.md`, `docs/arranque-local.md` | `CIMENTA_HUMO_ROL`, `CIMENTA_HUMO_NOMBRE` y el segundo usuario sembrado |

`python tools/verificar_docs.py` → «Sin problemas». Vale: 0 errores, 0 avisos en los tres archivos.

### Verificación final de la entrega b

- [x] Criterios `[M]` de la entrega (`CA-9` a `CA-13`, `CA-R3`) cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador (TC-86 lo actualizó el tester con decisión de la persona dueña)
- [x] Suite de frontend y E2E en verde, con la salida pegada arriba
- [x] Suite de backend: `2767 passed, 26 skipped in 591.37s (0:09:51)` (2026-11-10, corrida de `/sdd-revisar`, salida en `suite-revision-backend.txt`; la corrida anterior, tras los hallazgos de código, dio `2767 passed, 26 skipped in 560.56s` en `suite-final-backend.txt`)
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación: no aplica en la entrega b, con motivo
- [ ] Todas las auditorías `APROBADO`: `auditor-codigo` mantiene F002 y F007 por decisión pendiente
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada
- [x] `ruff`, `mypy`, `lint-imports`, `eslint` y `tsc` limpios
- [x] Rama correcta y sin secretos en el diff

## Revisión (`/sdd-revisar`, 2026-11-10)

Revisión del ticket completo, con las entregas a y b juntas, porque se ejecutaron seguidas sobre la misma rama.

### Verificación final

Comandos ejecutados de nuevo en la revisión, no copiados de las entregas:

```text
docker info                          → Server Version: 29.9.3
uv run pytest (backend)              → 2767 passed, 26 skipped in 591.37s (0:09:51)
uv run ruff check .                  → All checks passed!
uv run ruff format --check .         → 285 files already formatted
uv run mypy cimenta/                 → Success: no issues found in 123 source files
uv run lint-imports                  → Contracts: 16 kept, 0 broken.
verificar_float                      → archivos revisados: 34; hallazgos: 0
python tools/verificar_docs.py       → ✓ Sin problemas. (41 ADR)
npm test (frontend)                  → Test Files  18 passed (18) · Tests  255 passed (255)
npm run lint · typecheck · tipos:verificar → sin errores · sin errores · Tipos al día.
npm run e2e                          → 5 passed (entrega b; ver verde-e2e-B5.txt)
python -m unittest discover -s tools/tests → Ran 516 tests · OK
```

| Criterio | Estado |
|---|---|
| `CA-1` a `CA-8`, `CA-R1`, `CA-R2` (entrega a) | Cumplidos, con las pruebas de las tablas de la entrega a |
| `CA-9` a `CA-13`, `CA-R3` (entrega b) | Cumplidos; `CA-R3` con la actualización declarada de TC-86 |

`docs/api/openapi.yaml` cambia solo en `maxLength` de `nombre` y `domicilio` de `ObraNueva` (`D-5`, aprobado): **señalado a quien aprueba el PR** (convenciones §12).

### Auditorías

| Auditor | Veredicto final | Ciclos |
|---|---|---|
| `auditor-arquitectura` (entrega a) | `APROBADO` | 1 |
| `auditor-arquitectura` (entrega b) | Menores resueltos; N001 (declarar la actualización de TC-86 en `spec.md` y `design.md`) corregido en `/sdd-revisar` | 2 |
| `auditor-seguridad` | `APROBADO` | 1 |
| `auditor-codigo` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: F008 y F009 resueltos por el orquestador con el texto literal del auditor; F002 y F007 aceptados por la persona dueña como deuda | 2 |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: tras tres ciclos quedan N002 y F011 comunicados, sin acción en este PR; N006 y N007 resueltos por el orquestador con el texto literal del auditor | 3 |
| `auditor-sql` | No aplica (sin migración ni DDL) | — |

Decisiones de la persona dueña durante la revisión: escribir el ADR [la unicidad del código de obra](../../../docs/adr/20261110-unicidad-del-codigo-de-obra.md) (cierra el Mayor N001 de `auditor-docs`, la desviación respecto a ADR-031 y deja el recuento en 41); y dejar F002 y F007 de `auditor-codigo` como deuda documentada.

Rechazado con evidencia: el hallazgo F001 de `auditor-docs` afirmaba que ADR-031 no existía; existe (`20261101-inmutabilidad-de-la-linea-base-en-el-motor.md`). En la reauditoría se admitió su otra parte, que no cubre `uq_obra_codigo`, y se corrigió el texto del diseño.

**Menores abiertos y comunicados a la persona dueña** (no cambian el comportamiento del producto):

| ID | Qué | Por qué queda abierto |
|---|---|---|
| F002 · `auditor-codigo` | Duplicación de la lectura de `sqlstate` y `constraint_name` entre `aplicacion/obras.py` y `traduccion_motor.py` | Exige tocar un archivo de TKT-017; aceptado como deuda, recogido en el ADR nuevo |
| F007 · `auditor-codigo` | `Any` en auxiliares de tests | Ningún desarrollador edita tests; aceptado como deuda |
| N002 · `auditor-docs` | `docs/07` sigue con `TKT-012` en las filas de `/tipos-partida` e `/insumos` | Pertenecen a otro ticket (TKT-018 o el de la captura de requisición); fuera de alcance |
| F011 · `auditor-docs` | `test_tkt012a_api_alta_sin_permiso` no lleva escenario HDU en el nombre | `CA-6` no tiene escenario HDU y HDU-001 no tiene escenario de permiso; falta decidir si debe tenerlo |
| N008 · `auditor-docs` | `sdd/tickets/tkt-029a/design.md` reserva «ADR-041» y el ADR nuevo ocupa ese ordinal | Aviso para TKT-029a: usar el siguiente número libre |

Hallazgos de las entregas que siguen para la persona dueña: los cuatro huecos de la pantalla (bloqueo inesperado en el alta, botón `+` en todos los estados, textos redactados por el desarrollador y umbral negativo rechazado por formato en el cliente), descritos en «Entrega b · Ajustes respecto al design».

`CIMENTA_HUMO_*` en `README.md`: la fila 264 del README también se actualizó a 41 ADR.

Se verifica en `/sdd-completar`: los trabajos de `ci.yml` del PR real y las comprobaciones requeridas.
