# Impl · TKT-018a · Pantalla de línea base y presupuesto de control

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

El ticket se ejecuta en tres entregas sobre la rama `tkt-018a-pantalla-linea-base`. Cada entrega añade su sección a este archivo sin reescribir las anteriores.

## Entrega a · línea base y congelado (filas A1 a A5)

Ejecutada el 2026-11-10 y el 2026-11-11.

### Qué se implementó

La pantalla `/obras/:obraId/linea-base` muestra la línea base de la obra de la ruta: la congelada si existe y, si no, el borrador de mayor versión, que la interfaz oculta a Compras. Pinta estado, versión, estado de la obra, importe de venta y el desglose por tipo de partida, con sus estados de carga, vacío, obra inexistente, sin permiso y error. El Director de Proyectos congela el borrador con un motivo escrito en línea; cada rechazo del servidor se pinta con el contrato de error: el `422` junto al campo, `RN-01` en la pantalla de bloqueo, los conflictos de estado y de concurrencia en línea con su reintento, y el `403` y el `404` en una alerta con el mensaje del servidor. La lista de obras gana un enlace «Línea base» por fila para los roles con la sección, y las dos entradas del menú que eran marcadores remiten ahora a «Obras».

No hay backend, contrato ni tipos generados nuevos. El presupuesto de control (entrega b) y la semilla con su prueba de extremo a extremo (entrega c) siguen pendientes: tras congelar, la pantalla todavía no pide `presupuesto-control`.

### Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-10 | A1 · TC-01 gana el caso de dos borradores (`[v2, v3]` → v3) | El diseño pide el borrador de mayor versión sin depender del orden y ningún caso del plan lo comprobaba |
| 2026-11-10 | A1 · `obras.consultas.ts` gana la exportación `obraOptions(api, obraId)` | Caso previsto en la nota de integración: TKT-012a no la exportaba |
| 2026-11-10 | A1 · el rojo se tomó con un esqueleto de firmas que lanzan «no implementado» | El primer rojo era «módulo ausente», que el método no acepta como rojo por la razón esperada |
| 2026-11-10 | A2 · las pruebas de `ConflictoEnLinea` de TC-04 viven en `compartido/formularios/ConflictoEnLinea.test.tsx` | Ese componente ya tenía su archivo de pruebas |
| 2026-11-10 | A2 · un archivo más: `celda()` de `DetalleCifras.tsx` trata `null` como vacío | El servidor manda `concepto` y `clave_insumo` nulos en las causas `SUGERIDO_NEGATIVO` y `CARGO_AUSENTE`, y la tabla «Causas» pintaba el texto «null». Ajuste menor aprobado por la persona dueña el 2026-11-10 |
| 2026-11-10 | A2 · prueba añadida para el rótulo `estado_obra` | TC-04 no lo cubría; nació en verde y se demostró con una mutación revertida |
| 2026-11-10 | A3 · TC-06 gana dos importes de 18 dígitos (`"99999999999999.9949"` y `"12345678901234.5650"`) | El importe del plan da el mismo texto con `Number` y no mata `M-7`. TC-22 de la entrega b debe usar estos valores |
| 2026-11-10 | A3 · TC-05 gana tres casos: `403` del servidor y obra `200` con líneas base `500` o `404` | El diseño dice «error de cualquiera de las dos consultas» y el plan solo probaba las dos fallando a la vez |
| 2026-11-10 | A3 · el estado de la obra se pinta con el valor del contrato (`PLANEACION`, `ACTIVA`) | El wireframe 4a lo dibuja así; el rótulo de `PantallaObras` es una constante privada de TKT-012a |
| 2026-11-11 | A4 · un importe del servidor que no es cadena decimal plana se pinta «No disponible» | La primera versión de A3 pintaba la cadena cruda; «Entradas hostiles» del diseño pide «No disponible» |
| 2026-11-11 | A4 · TC-12 y TC-13 ganan un caso cada uno | El `422` de otro campo va a la alerta y «Cerrar» quita el bloqueo conservando lo escrito: lo describe la fila del diseño y el plan no lo probaba |
| 2026-11-11 | A3 a A5 · sin `interfaz.md` de `disenador-ui-ux` | El diseño aprobado asigna las filas a `desarrollador-react` y su tabla «Capas afectadas» ya fija jerarquía, estados y textos |
| 2026-11-11 | Documentación de `docs/08-wireframes.md` y `docs/05-tickets-trabajo.md` aplazada a la fila B4 | El diseño la ordena en B4, dentro del mismo PR del ticket |
| 2026-11-10 | Todos los despachos corrieron en Fable 5.2 con esfuerzo medio | Excepción pedida por la persona dueña para esta sesión; no cambia el modelo declarado de los agentes |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `frontend/src/modulos/presupuesto/linea-base/linea-base.consultas.ts` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/linea-base/presentacion.ts` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/linea-base/PantallaLineaBase.tsx` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/linea-base/FormularioCongelado.tsx` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/linea-base/ElegirObra.tsx` | nuevo | frontend |
| `frontend/src/modulos/presupuesto/rutas.tsx` | modificado | frontend |
| `frontend/src/modulos/presupuesto/obras/PantallaObras.tsx` | modificado | frontend |
| `frontend/src/modulos/presupuesto/obras/obras.consultas.ts` | modificado | frontend |
| `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | modificado | frontend |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | modificado | frontend |
| `frontend/src/modulos/presupuesto/linea-base/linea-base.consultas.test.ts` | nuevo | pruebas |
| `frontend/src/modulos/presupuesto/linea-base/presentacion.test.ts` | nuevo | pruebas |
| `frontend/src/modulos/presupuesto/linea-base/PantallaLineaBase.test.tsx` | nuevo | pruebas |
| `frontend/src/modulos/presupuesto/obras/PantallaObras.test.tsx` | modificado (pruebas nuevas) | pruebas |
| `frontend/src/compartido/componentes/bloqueo/PantallaBloqueo.test.tsx` | modificado (pruebas nuevas) | pruebas |
| `frontend/src/compartido/formularios/ConflictoEnLinea.test.tsx` | modificado (pruebas nuevas) | pruebas |
| `frontend/src/pruebas/cuerpos.ts` | modificado (fábricas nuevas) | pruebas |

Unas 455 líneas de producción nuevas en `linea-base/`, más 68 en archivos existentes. Ninguna aserción existente cambió: en los archivos de prueba que ya existían solo se ampliaron importaciones y se añadieron bloques.

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `tkt018a_d2 · qué línea base se muestra` (6 casos) | feliz · borde | `CA-12` | FALLA | PASA |
| TC-02 | `tkt018a_ca13 · sin ver borrador` (2 casos) | **rechazo** | `CA-13` | FALLA | PASA |
| TC-03 | `tkt018a_ca04 · mensajeDeRechazo` (6 casos) | **rechazo** | `CA-4`, `CA-9` | FALLA | PASA |
| TC-04 | `hdu001_esc19 · …`, `hdu001_esc17 · …`, `tkt018a_ca04 · …` (7 casos) | **rechazo** | `CA-4`, `CA-7` | FALLA (6) · nace en verde (1, mutada) | PASA |
| TC-05 | `tkt018a_ca12 · estados` (8 casos) | feliz · **rechazo** | `CA-12` | FALLA | PASA |
| TC-06 | `hdu001_esc14 · borrador para …` y `tkt018a_ca02 · …` (9 casos) | feliz · borde | `CA-2`, `CA-13` | FALLA | PASA |
| TC-07 | `hdu001_esc18 · congelada en solo lectura` (3 roles) | **rechazo** | `CA-5` | FALLA | PASA |
| TC-08 | `tkt018a_ca13 · COMPRAS no ve el borrador` (2 casos) | **rechazo** | `CA-13` | FALLA | PASA |
| TC-09 | `tkt018a_ca01 · la obra de la ruta` (4 casos) | feliz · **rechazo** | `CA-1` | FALLA | PASA |
| TC-10 | `hdu001_esc14 · congelar con motivo` | feliz | `CA-3` | FALLA | PASA |
| TC-11 | `hdu001_esc14 · motivo vacío o en blanco` (2 casos) | **rechazo** | `CA-4` | FALLA | PASA |
| TC-12 | `hdu001_esc14 · 422 del servidor` (2 casos) | **rechazo** | `CA-4` | FALLA | PASA |
| TC-13 | `hdu001_esc19 · segunda vigente` (2 casos) | **rechazo** | `CA-4` | FALLA | PASA |
| TC-14 | `hdu001_esc14 · 409 de estado` (2 casos) | **rechazo** | `CA-4` | FALLA | PASA |
| TC-15 | `hdu001_esc14 · concurrencia` | **rechazo** · concurrencia | `CA-4` | FALLA | PASA |
| TC-16 | `hdu001_esc14 · 403 y 404` (3 casos) | **rechazo** | `CA-4` | FALLA | PASA |
| TC-17 | `tkt018a_ca01 · enlace desde la lista` (9 casos) | feliz · **rechazo** | `CA-1` | FALLA (6) · nace en verde (3, mutadas) | PASA |
| TC-18 | `tkt018a_d7 · el menú remite a Obras` (14 casos) | feliz · **rechazo** | `CA-1` | FALLA (8) · nace en verde (6, mutadas) | PASA |

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó (agente o herramienta) | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| A1 | Fila A1 · Rojo | `tester-frontend` · `desarrollador-react` | Fila A1 · Verde | Sí (`M-5`, `M-8`, `M-10`) |
| A2 | Fila A2 · Rojo | `tester-frontend` · `desarrollador-react` | Fila A2 · Verde | Sí (rótulo `estado_obra`) |
| A3 | Fila A3 · Rojo | `tester-frontend` · `desarrollador-react` | Fila A3 · Verde | Sí (`M-7`, `M-8`) |
| A4 | Fila A4 · Rojo | `tester-frontend` · `desarrollador-react` | Fila A4 · Verde | Sí (`M-1`, `M-10`) |
| A5 | Fila A5 · Rojo | `tester-frontend` · `desarrollador-react` | Fila A5 · Verde | Sí (`M-A5a` a `M-A5c`) |

#### Fila A1 · consultas y presentación

**Rojo** — el primer rojo fue «módulo ausente» (`Failed to resolve import "./linea-base.consultas"`). El desarrollador creó el esqueleto de firmas con cuerpos `throw new Error("no implementado")` y el rojo por comportamiento quedó así:

```text
     × tkt018a_ca04 · mensajeDeRechazo: el 403 muestra el mensaje del servidor con su referencia 3ms
     × tkt018a_ca04 · mensajeDeRechazo: el 403 de origen no verificado conserva la pista de recargar 0ms
     × tkt018a_ca04 · mensajeDeRechazo: el 404 muestra el mensaje del servidor tal cual 0ms
     × tkt018a_ca04 · mensajeDeRechazo: sin red dice que no hay conexión con el servidor 0ms
     × tkt018a_ca04 · mensajeDeRechazo: el error genérico con identificador muestra la referencia 0ms
     × tkt018a_ca04 · mensajeDeRechazo: el error genérico sin identificador no inventa referencia 0ms
     × tkt018a_d2 · qué línea base se muestra: con borrador v2 y congelada v1, la congelada 3ms
     × tkt018a_d2 · qué línea base se muestra: la congelada también si la lista llega en orden inverso 0ms
     × tkt018a_d2 · qué línea base se muestra: sin congelada, el borrador v3 y nunca una supersedida 0ms
     × tkt018a_d2 · qué línea base se muestra: entre dos borradores, el de mayor versión 0ms
     × tkt018a_d2 · qué línea base se muestra: solo una supersedida, ninguna 0ms
     × tkt018a_d2 · qué línea base se muestra: la obra sin líneas base, ninguna 0ms
     × tkt018a_ca13 · sin ver borrador: con solo un borrador no se muestra ninguna 0ms
     × tkt018a_ca13 · sin ver borrador: con borrador v2 y congelada v1, la congelada 0ms
Error: no implementado
 Test Files  2 failed (2)
      Tests  14 failed (14)
```

**Verde:**

```text
> vitest run linea-base presentacion
 Test Files  2 passed (2)
      Tests  14 passed (14)
   Duration  1.26s
```

**Refactor:** sin refactor; la implementación mínima ya estaba en su forma final. `npm run lint` y `npm run typecheck`, limpios.

**Tests devueltos al tester:** ninguno.

#### Fila A2 · etiquetas del bloqueo

**Rojo:**

```text
     × tkt018a_ca04 · la explosión no calculable muestra la tabla «Causas» con concepto, causa e insumo 16ms
     × tkt018a_ca04 · las causas no pintan ningún identificador interno 4ms
     × hdu001_esc17 · el tope mayor que la venta muestra «Venta» y «Tope» con las cifras del servidor 3ms
     × hdu001_esc19 · la segunda línea base vigente muestra la obra y la versión vigente, y solo «Cerrar» 8ms
     × hdu001_esc19 · el identificador de la línea base vigente no se pinta 4ms
TestingLibraryElementError: Unable to find an accessible element with the role "table" and name "Causas"
expected document not to contain element, found <dt> linea_base_id </dt> instead
TestingLibraryElementError: Unable to find an element with the text: Venta, which matches selector 'dt'.
TestingLibraryElementError: Unable to find an element with the text: Versión vigente, which matches selector 'dt'.
expected document not to contain element, found <dt> linea_base_vigente_id </dt> instead
 Test Files  2 failed (2)
      Tests  5 failed | 18 passed (23)
```

Rojo del ajuste (celda `null`):

```text
     × tkt018a_ca04 · una causa sin concepto ni insumo deja la celda vacía y no pinta «null» 17ms
AssertionError: expected [ 'null', 'SUGERIDO_NEGATIVO', 'null' ] to deeply equal [ '', 'SUGERIDO_NEGATIVO', '' ]
 Test Files  1 failed | 1 passed (2)
      Tests  1 failed | 24 passed (25)
```

**Verde:**

```text
 Test Files  2 passed (2)
      Tests  25 passed (25)
   Duration  1.61s
```

**Refactor:** sin refactor. La constante `INSUMO` existente no se reutilizó en la tabla `causas` porque apunta al campo `insumo`, no a `clave_insumo`.

**Tests devueltos al tester:** ninguno.

**Mutación:** la prueba del rótulo `estado_obra` nació en verde. Al quitar la entrada `estado_obra` de `CLAVES_DETALLE`, cae con `Unable to find an element with the text: Estado de la obra`; tras restaurar, la huella SHA-256 de `etiquetas.ts` (`c890289c…dd583c`) es idéntica a la previa.

#### Fila A3 · pantalla y ruta

**Rojo** — la ruta no existía y `main` pintaba «Página no encontrada»:

```text
 × tkt018a_ca12 · estados · TC-05 · cargando: un esqueleto con aria-busy mientras el servidor no responde
 × tkt018a_ca12 · estados · TC-05 · sin línea base: los dos textos del vacío y ningún botón
 × tkt018a_ca12 · estados · TC-05 · la obra no existe (404): «La obra no existe», sin tratamiento de error
 × tkt018a_ca12 · estados · TC-05 · el identificador de la ruta no es un UUID (422): «La obra no existe»
 × tkt018a_ca12 · estados · TC-05 · error 500: la referencia de correlación y «Reintentar», que vuelve a pedir las dos consultas
 × tkt018a_ca12 · estados · TC-05 · la obra llega y las líneas base fallan con 500: el aviso con la referencia y «Reintentar»
 × tkt018a_ca12 · estados · TC-05 · la obra llega y las líneas base responden 404: «La obra no existe»
 × tkt018a_ca12 · estados · TC-05 · 403 del servidor: el aviso de sin permiso, sin cifras y sin tratamiento de error
 × hdu001_esc14 · borrador para el Director de Proyectos · TC-06 · estado, versión, venta y desglose, sin presupuesto de control
 × hdu001_esc14 · borrador para Dirección General · TC-06 · la misma vista, sin formulario de congelado
 × tkt018a_ca02 · TC-06 · una venta de 18 dígitos (…) se pinta sin pérdida de exactitud (3 casos)
 × hdu001_esc18 · congelada en solo lectura · TC-07 · … (DIRECTOR_PROYECTOS, DIRECCION_GENERAL, COMPRAS)
 × tkt018a_ca13 · COMPRAS no ve el borrador · TC-08 · … (2 casos)
 × tkt018a_ca01 · la obra de la ruta · TC-09 · … (4 casos)
TestingLibraryElementError: Unable to find role="heading" and name "Línea base · AP-058-25 · Union Square F2"
 Test Files  1 failed (1)
      Tests  22 failed (22)
```

**Verde:**

```text
 Test Files  1 passed (1)
      Tests  22 passed (22)
   Duration  4.12s

> vitest run   (suite completa)
 Test Files  21 passed (21)
      Tests  298 passed (298)
```

**Refactor:** los tres campos opcionales del congelado (`congelada_en`, `congelada_por`, `motivo`) se normalizan con `?? null` para el comprobador de tipos.

**Tests devueltos al tester:** ninguno.

#### Fila A4 · formulario de congelado

**Rojo:**

```text
 ❯ src/modulos/presupuesto/linea-base/PantallaLineaBase.test.tsx (39 tests | 17 failed)
     × hdu001_esc14 · borrador para el Director de Proyectos · TC-06 · el campo «Motivo (obligatorio)» vacío, el botón «Congelar línea base» y la advertencia del congelado
     × hdu001_esc14 · congelar con motivo · TC-10 · un POST con el motivo y el token CSRF; la pantalla pasa a CONGELADA y ACTIVA, sin campo ni botón
     × hdu001_esc14 · motivo vacío o en blanco · TC-11 · … (2 casos)
     × hdu001_esc14 · 422 del servidor · TC-12 · … (2 casos)
     × hdu001_esc19 · segunda vigente · TC-13 · … (2 casos)
     × hdu001_esc14 · 409 de estado · TC-14 · … (2 casos)
     × hdu001_esc14 · concurrencia · TC-15 · «Inténtalo de nuevo» con «Reintentar» deshabilitado durante el Retry-After; al pulsarlo, segundo POST con el mismo motivo
     × hdu001_esc14 · 403 y 404 · TC-16 · … (3 casos)
     × tkt018a_ca02 · un importe mal formado del servidor se pinta «No disponible» · 1e5 / abc / Infinity
TestingLibraryElementError: Unable to find an accessible element with the role "textbox" and name "Motivo (obligatorio)"
AssertionError: expected '1e5' to be 'No disponible'
 Test Files  1 failed (1)
      Tests  17 failed | 22 passed (39)
```

**Verde:**

```text
 Test Files  1 passed (1)
      Tests  39 passed (39)
   Duration  7.23s

> vitest run   (suite completa)
 Test Files  21 passed (21)
      Tests  315 passed (315)
```

**Refactor:** el tratamiento de los rechazos se separó en `rechazar(error)` con un `switch` por `tipo`, y un único `limpiar()` sirve al envío y al cierre del bloqueo. La rama `VALIDACION` repite la de `CapturaMotivo`; no se extrajo porque D-3 pide no tocar ese componente.

**Tests devueltos al tester:** ninguno.

#### Fila A5 · `ElegirObra` y enlace desde la lista

**Rojo** — nueve pruebas de rechazo nacieron en verde, porque hoy nadie ve la columna y las rutas de los marcadores ya llevan la guarda; se demostraron con los mutantes `M-A5a` a `M-A5c`:

```text
 × tkt018a_ca01 · enlace desde la lista · TC-17 · … ve la columna «Línea base» y, en cada fila, el enlace «Línea base de {código}» … (DP, DG, COMPRAS)
TestingLibraryElementError: Unable to find an accessible element with the role "columnheader" and name "Línea base"
 × tkt018a_ca01 · enlace desde la lista · TC-17 · … pulsa el enlace de una obra: la ruta cambia y se pide la línea base de esa obra, no de otra (DP, DG, COMPRAS)
TestingLibraryElementError: Unable to find an accessible element with the role "link" and name "Línea base de AP-061-25"
 × tkt018a_d7 · el menú remite a Obras · TC-18 · … el título de la sección, el texto que remite a «Obras» y el enlace «Ir a Obras», sin el marcador (2 secciones × 3 roles)
TestingLibraryElementError: Unable to find an element with the text: /^Elige la obra en «Obras»: su línea base y su presupuesto de control están en la misma pantalla\.?$/.
 × tkt018a_d7 · el menú remite a Obras · TC-18 · …: «Ir a Obras» lleva a la lista de obras (2 secciones)
TestingLibraryElementError: Unable to find an accessible element with the role "link" and name "Ir a Obras"
 Test Files  2 failed (2)
      Tests  14 failed | 70 passed (84)
```

**Verde:**

```text
 Test Files  2 passed (2)
      Tests  84 passed (84)
   Duration  8.78s
```

**Refactor:** `rutaElegirObra(clave)` evita repetir la ruta en `rutas.tsx`, y la constante `ETIQUETA_LINEA_BASE` sirve al encabezado, al enlace y a su `aria-label` en `PantallaObras.tsx`.

**Tests devueltos al tester:** ninguno.

### Evidencia de ejecución al cerrar

Desde `frontend/`, con el árbol de la entrega a completo:

```text
> vitest run
 Test Files  21 passed (21)
      Tests  338 passed (338)
   Duration  14.06s

> eslint .                         (sin salida, exit 0)
> tsc --noEmit                     (sin salida, exit 0)
> node scripts/tipos.ts verificar
Tipos al día.                      (exit 0)

git diff --stat -- frontend/src/api/generado   → vacío
```

La suite es de Vitest con MSW y no usa contenedores; `docker info` respondía (servidor 29.9.3) al abrir la ejecución.

### Mutación en rutas críticas

Un mutante a la vez, con copia previa fuera del repositorio, la suite completa contra cada uno y restauración desde la copia. `git status --short` quedó idéntico al de partida.

| Mutante | Cambio | Pruebas que caen |
|---|---|---|
| `M-1` | `FormularioCongelado` deja de pasar el `422` de `motivo` a `setError` | Las dos de TC-12 |
| `M-5` | `lineaBaseMostrada` prefiere el `BORRADOR` a la `CONGELADA` | Tres de TC-01 |
| `M-7` | `importe()` formatea con `Intl.NumberFormat(…).format(Number(valor))` | Dos de 18 dígitos de TC-06 y las tres de «No disponible» |
| `M-7b` | Igual, conservando «No disponible» | Las dos de 18 dígitos de TC-06 |
| `M-8` | Compras entra en los roles que ven el borrador | TC-08, «con solo un BORRADOR» |
| `M-10` | `mensajeDeRechazo` devuelve un texto fijo en `PERMISO` | Dos de TC-03 y dos de TC-16 |
| `M-10b` | Texto fijo conservando la referencia | Las mismas cuatro |
| `M-A4a` | `puedeCongelar` también para Dirección General | TC-06, variante de Dirección General |
| `M-A4b` | Un rechazo del congelado invalida `claves.obras` | Nueve: TC-12 a TC-16, por los contadores de peticiones |
| `M-A5a` | La columna «Línea base» se pinta sin condición | Tres de rechazo de TC-17 |
| `M-A5b` | `ElegirObra` sin `GuardaSeccion` | Seis de rechazo de TC-18 |
| `M-A5c` | La ruta de la pantalla sin `GuardaSeccion` | Tres de rechazo de TC-09 |
| `M-2`, `M-3`, `M-4`, `M-6`, `M-9` | — | No aplican todavía: su código es de la entrega b |

Huellas SHA-256 de los archivos mutados, iguales antes y después de todo el proceso:

```text
6304de8b85fa588915201e691c94d949ff8c77f5052d06894bd7dcebc13ed536  linea-base/FormularioCongelado.tsx
5d7d796404f0cce2b14e7a9ff4d199fc0906bcda9a8eb7d86006f015870149b0  linea-base/PantallaLineaBase.tsx
ce22ddfba57438be622eb0aa0d67d42ec54fbfac8b89cde0e1d50bdb250f7c6b  linea-base/linea-base.consultas.ts
a95f96be234fce0747b86fe5ed6b64359b9cc2396506a3a3f0bc835c232cdc02  linea-base/presentacion.ts
6dec9833a4b3ebc457a45976d8985309ef0cf5263933dcde382f3f32f1724b88  obras/PantallaObras.tsx
c71e12124b5ea49dbfb7d7cfd80f01e18ea04953b2a6a0ce4a75d5cab7358b1b  presupuesto/rutas.tsx
```

Huella conjunta de los 60 archivos de producción de `frontend/src`: `48d733d30852daf7c778165cae1be3bdd72cb668cdadeda33d96535dce70adb1`, igual antes y después de cada mutante. `M-8` y `M-A4a` caen con una sola prueba cada uno: es la defensa más delgada de la entrega.

### Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | el del agente | Fable 5.2 · medio | Excepción de sesión pedida por la persona dueña |
| A1 a A5 · rojo | `tester-frontend` | `sonnet` | Fable 5.2 · medio | La misma excepción |
| A1 a A5 · verde y refactor | `desarrollador-react` | `haiku` | Fable 5.2 · medio | La misma excepción |
| Cierre · suite y mutación | `tester-frontend` | `sonnet` | Fable 5.2 · medio | La misma excepción |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | Fable 5.2 · medio | La misma excepción |

Ningún paso necesitó un segundo intento. Dos despachos se interrumpieron por el límite de uso de la cuenta (verde de A1 y rojo de A4) y se reanudaron con su contexto, sin trabajo perdido.

### Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-09, TC-17, TC-18 |
| `CA-2` | `[M]` | Cumplido | TC-06 |
| `CA-3` | `[M]` | Cumplido salvo la última cláusula (el control aparece tras congelar), que es TC-24 de la entrega b | TC-10 |
| `CA-4` | `[M]` | Cumplido | TC-03, TC-04, TC-11 a TC-16 |
| `CA-5` | `[M]` | Cumplido | TC-07 |
| `CA-6` a `CA-11` | `[M]` | Pendiente · entrega b | — |
| `CA-12` | `[M]` | Cumplido salvo la sección del control en la vista congelada, de la entrega b | TC-01, TC-05, TC-06, TC-07 |
| `CA-13` | `[M]` | Cumplido salvo la captura, de la entrega b | TC-02, TC-06, TC-08 |
| `CA-R1` | `[M]` | Parcial: suite completa en verde sin aserciones existentes modificadas | 338 de 338 |
| `CA-R2` | `[M]` | Pendiente · entrega b (hoy `tipos:verificar` en verde y `api/generado` sin cambios) | — |
| `CA-S1` | `[S]` | Pendiente · entrega c | — |

### Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | Ningún hallazgo crítico, mayor ni menor; cuatro observaciones que no bloquean | 1 |
| `auditor-sql` | No aplica: sin esquema ni migración | | |

#### Qué verificó `auditor-arquitectura`

- **Diff real presente.** Nueve archivos modificados (450 inserciones, 9 borrados según `git diff --shortstat -- frontend` del 2026-11-11) y ocho nuevos en `frontend/src/modulos/presupuesto/linea-base/`; leyó completos los cinco de producción nuevos y todos los diffs.
- **Comprobaciones a máquina** desde `frontend/`: `npm run lint` sin salida de error, `npm run typecheck` limpio, `npm run tipos:verificar` con «Tipos al día.» y `npm test` con 21 archivos y 338 pruebas en verde. No corrió `uv run lint-imports` porque `git diff --stat -- backend` está vacío.
- **Regla 1 · dinero.** Sin `Number(`, `parseFloat`, `parseInt`, `toFixed` ni `Math.` en el directorio nuevo, `cuerpos.ts`, `modulos/presupuesto/**` y los componentes de bloqueo. Los importes pasan solo por `formatearImporte` (`PantallaLineaBase.tsx:84-86`), que opera con `decimal.js`; una cifra mal formada se pinta «No disponible». La única comparación numérica es la de versiones enteras (`linea-base.consultas.ts:79`).
- **Regla 10 · el cliente no evalúa reglas.** `FormularioCongelado.tsx` clasifica el rechazo con `switch (error.tipo)` (`:47-65`), nunca por el texto; ningún rechazo invalida consultas y solo el éxito invalida `claves.obras` (`:71-74`). No hay comparación de tope contra venta ni cálculo de disponible. `resolverMotivo` valida forma. No hay cola sin conexión.
- **Tipos generados, sin Zod espejo.** Todos los tipos salen de `components["schemas"]` y de `@/api/errores`; sin `zod`, `any`, `@ts-` ni `eslint-disable` en el directorio nuevo; `frontend/src/api/generado` sin cambios.
- **Contrato de error.** `REGLA_NEGOCIO` va a `PantallaBloqueo`; `CONFLICTO` y `CONCURRENCIA`, a `ConflictoEnLinea` (`FormularioCongelado.tsx:106-110`); el `422` de `motivo`, al campo; `403`, `404`, red y genérico, a `mensajeDeRechazo` con la referencia de correlación (`presentacion.ts:7-20`). Las claves nuevas de `etiquetas.ts` coinciden con lo que arma el backend (`aplicacion/congelado.py:111, 172-174, 184-185` y `aplicacion/presupuesto_control.py:226`).
- **Regla 14 · rechazos.** TC-11 a TC-16 comprueban regla o código, mensaje, detalle, acciones, referencia y que la pantalla sigue en `BORRADOR`; TC-08, TC-09 y TC-17 cubren los roles sin acceso.
- **Cuatro estados.** Cargando, vacío, error con «Reintentar», obra inexistente, sin permiso y el bloqueado diferenciado del error (`PantallaLineaBase.tsx:29-72, 161-169`).
- **TanStack Query.** `queryOptions` con `staleTime` explícito, identificadores en las claves y `obraOptions` colgada de `claves.obras`.
- **Regla 17 · fase 1.** Nada de nómina, destajo, captura sin conexión, evidencia ni adaptador simulado. Las reglas 11 y 15 no aplican al cambio.
- **Alcance.** Fuera del diseño solo están los dos ajustes declarados (`DetalleCifras.tsx:69` y `obraOptions`). `secciones.ts`, `SeccionMarcador.tsx` y `ruta-marcador.tsx` no cambiaron.
- **Aserciones existentes.** Las únicas líneas borradas en archivos de prueba son tres de `import`, ampliadas. `Armazon.test.tsx`, `secciones.test.ts` y `PaginaInicioSesion.test.tsx` no cambiaron.

El auditor no ejecutó los mutantes: su tabla es la del cierre de `tester-frontend`, más arriba.

#### Observaciones de la auditoría

| ID | Ubicación | Observación | Estado |
|---|---|---|---|
| O-1 | `frontend/src/pruebas/cuerpos.ts` | Cinco fábricas de prueba más que las enumeradas en el diseño (`errorNoEncontrado`, `obra`, `errorExplosionNoCalculable`, `errorLineaBaseEnOtroEstado`, `errorCongeladoBloqueoVencido`); `obra()` duplica la fábrica local de `PantallaObras.test.tsx` | Declaradas en «Ajustes de la ejecución» del diseño; unificar `obra()` queda para `/sdd-revisar` |
| O-2 | `PantallaLineaBase.test.tsx:425, 657` | `toMatch(/^activa$/i)` acepta `ACTIVA` y `Activa`, aunque el ajuste de A3 fijó el valor del contrato | Abierta: la corrige el tester en `/sdd-revisar` |
| O-3 | `docs/08-wireframes.md` §2 y §4 | La entrega a ya cambia lo que muestran las dos secciones del menú y el wireframe sigue sin tocar | Agendada en B4; el PR no se abre sin ella |
| O-4 | `PantallaLineaBase.tsx:22, 156` | Los roles que ven el borrador y que congelan se repiten en el cliente | Sin acción: es presentación (D-1) y el servidor responde `403` |

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | La columna «Causa» pinta el código crudo (`INSUMO_SIN_COSTO`); el diseño la fija como texto, sin tabla de rótulos | Baja |
| `frontend/src/modulos/presupuesto/linea-base/FormularioCongelado.tsx` | La rama `VALIDACION` repite la de `CapturaMotivo`; candidata a un ayudante compartido | Baja |
| `frontend/src/modulos/presupuesto/linea-base/linea-base.consultas.ts` | Con una `CONGELADA` y un `BORRADOR` más nuevo, nadie ve el borrador desde esta pantalla (D-2). Cuando TKT-018b permita reimportar hará falta un camino para verlo y congelarlo | Media (TKT-018b) |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | No se comprobó cómo pinta un `null` una columna de tipo `cantidad` | Baja |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `sdd/tickets/tkt-018a/design.md` | Estado de las filas A1 a A5 y la tabla «Ajustes de la ejecución» |
| `sdd/tickets/tkt-018a/_index.md` | Estado y fila del registro |
| `docs/08-wireframes.md`, `docs/05-tickets-trabajo.md` | Sin cambios en esta entrega: los hace la fila B4, en el mismo PR |

`python tools/verificar_docs.py` → `✓ Sin problemas.`

### Verificación final de la entrega a

- [x] Criterios `[M]` de la entrega cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en rutas críticas
- [x] Auditoría de arquitectura `APROBADO`
- [ ] Documentación de wireframes y tickets (fila B4)
- [x] `eslint`, `tsc` y `tipos:verificar` limpios; el backend no cambió
- [x] Rama correcta

### Verificación final de `/sdd-revisar` · entrega a

Revisada el 2026-11-11. La revisión cubre los criterios `[M]` de la entrega a, su sección de este archivo y su diff, que es el de la rama desde `Produccion` porque es la primera entrega.

#### Completitud, corrección y coherencia

- **Completitud.** Cada criterio `[M]` de la entrega (`CA-1` a `CA-5`, `CA-12`, `CA-13` y `CA-R1` parcial) tiene resultado y evidencia en la tabla «Resultado contra los criterios de aceptación». Las cláusulas que dependen del presupuesto de control siguen pendientes y declaradas para la entrega b.
- **Corrección.** No hay alcance de más: fuera del diseño solo están los ajustes declarados y aprobados (`DetalleCifras.tsx`, `obraOptions` y las fábricas de prueba).
- **Coherencia.** La tabla «Archivos tocados» coincide con `git status --short`.
- **Rastro del ciclo TDD.** Las cinco filas traen la salida literal de su rojo antes de la de verde. El rojo de A1 se tomó con un esqueleto de firmas, no con el módulo ausente.

#### Suite ejecutada en la revisión

Corrida final, tras el ciclo de corrección 1 y sin ningún otro proceso en marcha. El ciclo 2 solo tocó `impl.md` y `design.md`.

```text
> docker info --format '{{.ServerVersion}}'
29.9.3

> uv run pytest -q                     (desde backend/)
2767 passed, 26 skipped in 695.69s (0:11:35)

> uv run ruff check .
All checks passed!

> uv run mypy cimenta/
Success: no issues found in 123 source files

> uv run lint-imports
Contracts: 16 kept, 0 broken.

> npx vitest run                       (desde frontend/)
 Test Files  21 passed (21)
      Tests  344 passed (344)
   Duration  9.18s

> npm run lint                         (sin salida de error, exit 0)
> npm run typecheck                    (sin salida de error, exit 0)
> npm run tipos:verificar
Tipos al día.

> python tools/verificar_docs.py       (desde la raíz)
✓ Sin problemas.

> git diff --shortstat -- frontend
 9 files changed, 466 insertions(+), 26 deletions(-)

> git diff --stat -- backend docs frontend/src/api/generado
(vacío)
```

Las 26 pruebas omitidas del backend son las de los archivos reales de catálogo, que exigen `CIMENTA_CATALOGO_UNION` y `CIMENTA_CATALOGO_ENITI` (`PA-T3`). El backend no cambió en esta entrega; su suite se corrió igualmente.

Una primera corrida de Vitest, lanzada a la vez que pytest, dio `1 failed | 337 passed (338)`: `tkt008_ca13_esc03 · Number en src`, de `scripts/eslint-reglas.test.ts`, agotó su tiempo de espera de 5000 ms. Repetida sin carga, la suite pasó completa (338 de 338 antes de la corrección y 344 de 344 después). La prueba es de TKT-008 y está fuera del diff; queda anotada en «Hallazgos fuera de alcance de la revisión».

El diff no toca `docs/api/openapi.yaml`.

#### Auditorías de la revisión

| Auditor | Modelo | Veredicto | Pasadas | Hallazgos |
|---|---|---|---|---|
| `auditor-arquitectura` | `sonnet` | `APROBADO` | 1 | Ninguno crítico, mayor ni menor. Persisten O-3 y O-4 sin acción; O-1 y O-2 se cerraron por `COD-8` y `COD-2`; `ARQ-1` se cerró por `COD-1`; `ARQ-2` es una observación |
| `auditor-codigo` | `sonnet` | `APROBADO` tras `REQUIERE CAMBIOS` | 2 | Un Mayor (`COD-1`) y siete Menores (`COD-2` a `COD-8`), todos `Resuelto`. Observaciones `OBS-1` a `OBS-5`, sin acción |
| `auditor-seguridad` | `sonnet` | `APROBADO` | 1 | Observaciones `SEG-1` y `SEG-2` |
| `auditor-docs` | `haiku` | `APROBADO` tras `REQUIERE CAMBIOS` | 3 | Dos Mayores (`DOC-1`, `DOC-2`) y Menores, todos `Resuelto`; `DOC-7` retirado por el auditor; `DOC-10` es una observación para TKT-018b |
| `auditor-sql` | — | No aplica: sin esquema, migración ni consulta | | |

Cada veredicto trajo su sección «Qué verifiqué» ítem por ítem. `auditor-arquitectura` y `auditor-seguridad` aprobaron sobre el diff previo a la corrección; los cambios de producción del ciclo 1 (`formatearFecha`, la alerta del `422` sin errores de campo y `espera_maxima_ms` en `CLAVES_OCULTAS`) los reauditó `auditor-codigo`.

#### Ciclo de corrección

Dos ciclos de `corrector-revision` (`haiku`).

**Ciclo 1.** Aplicó `COD-1` a `COD-8` y `DOC-1` a `DOC-5`, `DOC-8`, `DOC-9` y `DOC-11` a `DOC-14`, con el texto literal de cada auditor.

| ID | Qué cambió | Dónde |
|---|---|---|
| `COD-1` | `formatearFecha` devuelve `null` ante una fecha inválida en lugar de lanzar, y `DatosCongelado` no pinta el `<time>` | `presentacion.ts`, `PantallaLineaBase.tsx` y pruebas nuevas en `presentacion.test.ts` y en TC-07 |
| `COD-2` (O-2) | Cuatro aserciones del estado de la obra pasan a `toBe("PLANEACION")` y `toBe("ACTIVA")` | `PantallaLineaBase.test.tsx` |
| `COD-3` | Un `422` sin errores de campo muestra el `mensaje` del servidor en la alerta | `FormularioCongelado.tsx` y prueba nueva en TC-12 |
| `COD-4` | `espera_maxima_ms` deja de pintarse como clave cruda | `etiquetas.ts` y aserción en TC-15 |
| `COD-5` | TC-14 afirma el código del conflicto; prueba nueva del `500` en TC-16 | `PantallaLineaBase.test.tsx` |
| `COD-6` | Prueba nueva de la congelada sin fecha, autor ni motivo | `PantallaLineaBase.test.tsx` |
| `COD-7` | Cinco aserciones de tipo evitables, retiradas | `PantallaLineaBase.test.tsx`, `ConflictoEnLinea.test.tsx` |
| `COD-8` (O-1) | La fábrica local `obra()` envuelve la compartida | `PantallaObras.test.tsx` |
| `DOC-1`, `DOC-2` | La tabla «Documentación afectada» del diseño enumera el wireframe §2b, §12 y §13, que cambia la fila B4 | `design.md` |
| `DOC-3` a `DOC-5`, `DOC-8`, `DOC-9`, `DOC-11`, `DOC-12` | Referencias, numeración y estado de TKT-012a | `design.md`, `_index.md` |
| `DOC-13`, `DOC-14` | Docstrings que citaban `RN-01` y `RN-04` donde no aplican | `linea-base.consultas.ts`, `PantallaLineaBase.tsx` |

Rojo de `COD-1`, antes de tocar producción:

```text
 ❯ |cliente| src/modulos/presupuesto/linea-base/presentacion.test.ts (8 tests | 1 failed) 7ms
   ❯ TKT-018a · formatearFecha (2)
     × tkt018a_ca02 · formatearFecha: una cadena que no es fecha devuelve null en vez de lanzar 2ms
RangeError: Invalid time value
 ❯ formatearFecha src/modulos/presupuesto/linea-base/presentacion.ts:24:24
Tests  1 failed | 7 passed (8)
```

Rojo de la prueba de pantalla de `COD-1` y de `COD-3`:

```text
 FAIL  … > hdu001_esc18 · congelada con fecha inválida · TC-07 · …
TestingLibraryElementError: Unable to find role="heading" and name "Línea base · AP-058-25 · Union Square F2"
Error handled by React Router default ErrorBoundary: RangeError: Invalid time value
 FAIL  … > hdu001_esc14 · 422 sin errores de campo · TC-12 · el mensaje del servidor va a la alerta
TestingLibraryElementError: Unable to find role="alert"
Test Files  1 failed (1)
Tests  2 failed | 4 passed | 50 skipped (56)
```

Las aserciones de `COD-4`, `COD-5` y `COD-6` nacieron en verde; `auditor-codigo` razonó en la reauditoría, mutante por mutante, que cada una cae sin su cambio, sin ejecutar los mutantes. La suite pasó de 338 a 344 pruebas.

**Ciclo 2.** Dos Menores de redacción de `auditor-docs`: `DOC-6` (las cifras de la viñeta «Diff real presente», que ahora citan el `git diff --shortstat -- frontend` previo al ciclo 1) y `DOC-9` (la nota de TC-19, que había quedado dentro de la tabla del plan de pruebas). Reauditados y `Resuelto`.

**Decisión del orquestador.** `DOC-7` pedía reescribir `> vitest run`, `> eslint .` y `> tsc --noEmit` como comandos `npm`. No se aplicó: son el eco literal que imprime npm y la salida de un comando no se reformula. El auditor retiró el hallazgo.

#### Resultado por criterio de la entrega a

| Criterio | Nivel | Resultado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-09, TC-17, TC-18 |
| `CA-2` | `[M]` | Cumplido | TC-06 |
| `CA-3` | `[M]` | Cumplido salvo la última cláusula, que es de la entrega b (TC-24) | TC-10 |
| `CA-4` | `[M]` | Cumplido | TC-03, TC-04, TC-11 a TC-16 |
| `CA-5` | `[M]` | Cumplido | TC-07 |
| `CA-12` | `[M]` | Cumplido salvo la sección del control, de la entrega b | TC-01, TC-05, TC-06, TC-07 |
| `CA-13` | `[M]` | Cumplido salvo la captura, de la entrega b | TC-02, TC-06, TC-08 |
| `CA-R1` | `[M]` | Parcial, como corresponde a la entrega: 344 de 344, sin aserciones previas modificadas | Suite completa |
| `CA-6` a `CA-11`, `CA-R2` | `[M]` | Pendientes · entrega b | — |
| `CA-S1` | `[S]` | Pendiente · entrega c | — |

Hay prueba de rechazo para cada regla implicada (`RN-01` en TC-13; los rechazos del congelado en TC-11 a TC-16; los de acceso en TC-08, TC-09 y TC-17) y la mutación de las rutas críticas está en «Mutación en rutas críticas». Los mutantes no se repitieron en la revisión.

#### Desviaciones y pendientes

- **Documentación.** Los cambios de `docs/08-wireframes.md` siguen en la fila B4, dentro del mismo PR, con la enumeración ya completa en el diseño. El PR no se abre sin ella.
- **`SEG-1`, pregunta para la persona dueña.** Los endpoints de línea base comprueban el rol y no una asignación de la persona a la obra. Es backend de TKT-017 y no cambia en esta entrega. Falta confirmar si Director de Proyectos, Dirección General y Compras ven todas las obras por decisión de producto.
- **Observaciones sin acción en esta entrega.** `ARQ-2` (el texto de `ElegirObra` solo es cierto con la entrega b), `SEG-2` (codificar `obra.id` en el enlace), `OBS-1` (aviso de error con reintento duplicado, a extraer en la entrega b), `OBS-2` (ruta escrita a mano en varios sitios), `OBS-3` (`FilaCifra` pinta «null» ante un valor conocido nulo), `OBS-4` (valor por omisión que silencia un desfase en la fábrica `lineaBase()`) y `OBS-5` (docstring de una sola línea larga).

#### Hallazgos fuera de alcance de la revisión

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/scripts/eslint-reglas.test.ts` | `tkt008_ca13_esc03 · Number en src` agota sus 5000 ms cuando la máquina está cargada (la primera invocación de ESLint tardó 6244 ms junto a pytest) | Baja |
| `docs/07-especificacion-api.md`, `docs/api/openapi.yaml` | Las operaciones de importación siguen atribuidas a `TKT-018`; corresponde cambiarlas a `TKT-018b` al diseñarlo (`DOC-10`) | Baja (TKT-018b) |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | Toda clave desconocida del `detalle` se pinta cruda; un identificador nuevo del backend que no se registre en `CLAVES_OCULTAS` saldría a la vista | Baja |

**Veredicto de la entrega a: aprobada.** Queda acumulada en la rama `tkt-018a-pantalla-linea-base`, sin PR. Siguiente: `/sdd-ejecutar TKT-018a` sobre la entrega b (filas B1 a B4).
