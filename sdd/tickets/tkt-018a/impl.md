# Impl · TKT-018a · Pantalla de línea base y presupuesto de control

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta](delta.md)

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
- **`SEG-1`, resuelta por la persona dueña el 2026-11-11.** Los endpoints de línea base comprueban el rol y no una asignación de la persona a la obra. Es backend de TKT-017 y no cambia en esta entrega. La persona dueña confirmó que Director de Proyectos, Dirección General y Compras ven todas las obras por diseño: no es un hallazgo y no hace falta ticket.
- **Observaciones sin acción en esta entrega.** `ARQ-2` (el texto de `ElegirObra` solo es cierto con la entrega b), `SEG-2` (codificar `obra.id` en el enlace), `OBS-1` (aviso de error con reintento duplicado, a extraer en la entrega b), `OBS-2` (ruta escrita a mano en varios sitios), `OBS-3` (`FilaCifra` pinta «null» ante un valor conocido nulo), `OBS-4` (valor por omisión que silencia un desfase en la fábrica `lineaBase()`) y `OBS-5` (docstring de una sola línea larga).

#### Hallazgos fuera de alcance de la revisión

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/scripts/eslint-reglas.test.ts` | `tkt008_ca13_esc03 · Number en src` agota sus 5000 ms cuando la máquina está cargada (la primera invocación de ESLint tardó 6244 ms junto a pytest) | Baja |
| `docs/07-especificacion-api.md`, `docs/api/openapi.yaml` | Las operaciones de importación siguen atribuidas a `TKT-018`; corresponde cambiarlas a `TKT-018b` al diseñarlo (`DOC-10`) | Baja (TKT-018b) |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | Toda clave desconocida del `detalle` se pinta cruda; un identificador nuevo del backend que no se registre en `CLAVES_OCULTAS` saldría a la vista | Baja |

**Veredicto de la entrega a: aprobada.** Queda acumulada en la rama `tkt-018a-pantalla-linea-base`, sin PR. Siguiente: `/sdd-ejecutar TKT-018a` sobre la entrega b (filas B1 a B4).

## Entrega b · presupuesto de control (filas B1 a B4)

Entrega b ejecutada el 2026-11-11 con el ciclo TDD fila por fila en la rama `tkt-018a-pantalla-linea-base`, que ya traía la entrega a. La rama se verificó en lugar de reabrirse con `git-entrega`: estaba activa y sin cambios ajenos. Docker estaba en marcha. No hay backend, migración ni cambio de contrato.

### Qué se implementó

- **B1.** `tope.formulario.ts` con el patrón y el mensaje del importe, `esquemaTopes`, `esquemaRecaptura` y sus resolutores; y la prop opcional `etiquetaCancelar` de `CapturaMotivo`.
- **B2.** `TablaPresupuestoControl.tsx`, montada en la vista `CONGELADA` de `PantallaLineaBase`: captura de los topes por fila con un `PUT` secuencial, éxito parcial con resumen, y la cola de confirmación del tope superior a la venta con `CapturaMotivo` («Confirmar con motivo» y «Corregir»).
- **B3.** `DialogoRecaptura.tsx` y el botón «Recapturar {nombre}» de la tabla, con el reenvío confirmado dentro del diálogo.
- **B4.** Documentación de `docs/08-wireframes.md` (§2, §2b, §3, §4, §4a, §4b, §12 y §13) y la regresión completa.

### Ajustes respecto al design

| Fila | Ajuste | Motivo |
|---|---|---|
| B2 | La variante «fila ya capturada» de TC-23 no mata `M-2` por sí sola; se añadió la variante «dos guardados seguidos», que sí | Una fila capturada llega sin campo, así que su valor en el formulario es `""` y el filtro por vacío ya la excluye. Tras un primer guardado, el formulario conserva lo escrito y un segundo guardado reenviaría esa fila sin el filtro por `importe_tope === null` |
| B2 | Dos pruebas más de la tabla: cargando con `aria-busy` y error 500 con referencia y «Reintentar» | El diseño declara esos estados y el plan de pruebas no los enumeraba |
| B2 | `PantallaLineaBase.test.tsx` gana la opción `control` del doble y la usan TC-07 (tres roles, fecha inválida y datos ausentes), TC-08 y `servidorQueCongela()`. No cambia ninguna aserción | Nota de ejecución «Entrega b sobre la vista de a» |
| B2 | `cuerpos.ts` gana `filaControl` y `controlSinTopes` | `errorTopeSuperior` ya existía desde la entrega a |
| B3 | `compartido/componentes/bloqueo/DetalleCifras.tsx` gana un espacio entre `<dt>` y `<dd>` | Sin él el texto accesible salía como «Venta$30,000.00» y TC-33 espera «Venta $30,000.00». No cambia el aspecto visual (contenedor `flex`) y la suite completa sigue en verde. Es un archivo más que el diseño no listaba; `auditor-arquitectura` lo revisó |
| B4 | `docs/08-wireframes.md` §3 cambia dos referencias de `TKT-018` a `TKT-018b`, y §2b añade `TKT-018a` a las historias | Siguen la misma regla de partición que §12 y §13 |
| B4 | Los marcadores `(aprobado · D-7)` del diseño quedaron escritos en el wireframe | Pendiente de decidir si el documento debe citar identificadores del diseño |

### Archivos tocados

| Archivo | Cambio |
|---|---|
| `frontend/src/modulos/presupuesto/linea-base/tope.formulario.ts` (y su prueba) | Nuevo |
| `frontend/src/modulos/presupuesto/linea-base/TablaPresupuestoControl.tsx` (y su prueba) | Nuevo |
| `frontend/src/modulos/presupuesto/linea-base/DialogoRecaptura.tsx` | Nuevo |
| `frontend/src/modulos/presupuesto/linea-base/PantallaLineaBase.tsx` y su prueba | Monta la tabla; TC-24 y el doble del control |
| `frontend/src/compartido/formularios/CapturaMotivo.tsx` y su prueba | Prop `etiquetaCancelar`; TC-21 |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | Un espacio |
| `frontend/src/pruebas/cuerpos.ts` | Dos fábricas |
| `docs/08-wireframes.md` | Ver B4 |

### Ciclo TDD por fila

| Fila | Rojo | Verde | Refactor |
|---|---|---|---|
| B1 | `tope.formulario.test.ts`: módulo ausente, nada se ejecuta; `CapturaMotivo`: 1 fallida («Unable to find an accessible element with the role "button" and name "Corregir"») y 16 en verde, entre ellas la guarda de regresión del valor por omisión | `tope.formulario` y `CapturaMotivo`: 55 de 55; suite 384 de 384 | Ninguno |
| B2 | 23 fallidas por comportamiento: TC-24 («Unable to find role "heading" and name "Presupuesto de control"»), 20 de la tabla («Se esperaba una tabla de presupuesto de control y hay 0»), cargando y error 500; 57 previas en verde | 80 de 80; suite 407 de 407 | Ninguno: el aviso de error con reintento (`OBS-1`) no es trivial de extraer |
| B3 | 10 fallidas, todas «Unable to find an accessible element with the role "button" and name "Recapturar MUROS"»; 22 previas en verde | `TablaPresupuestoControl`: 32 de 32; suite 417 de 417 | Ninguno |
| B4 | No aplica (documentación) | `verificar_docs` sin problemas; `extraer_mermaid` sin error de ejecución (30 diagramas, página `tools/mermaid-check.html`; la sintaxis la valida CI con `mermaid-cli`) | — |

Las cifras son las que devolvieron los agentes de cada fila, con el mismo texto de error. B1 tiene una reserva: el rojo de `tope.formulario.test.ts` es de módulo ausente, y sus pruebas solo se probaron por comportamiento con el verde y con el mutante `M-4`.

### Evidencia de ejecución al cerrar

Ejecutado por el orquestador desde `frontend/` tras la fila B3:

```text
npm run tipos:verificar  → Tipos al día.
git diff --stat -- src/api/generado → (vacío)
npm run lint             → eslint . (sin salida)
npm run typecheck        → tsc --noEmit (sin salida)
npm test                 → Test Files 23 passed (23) · Tests 417 passed (417)
python tools/verificar_docs.py → ✓ Sin problemas.
python tools/extraer_mermaid.py → 30 diagramas encontrados · Escrito: tools/mermaid-check.html
```

`vale docs/08-wireframes.md`: 0 errores, 0 avisos. `markdownlint-cli2` y `lychee` no están instalados en esta máquina y no se ejecutaron.

### Mutación en rutas críticas

Un mutante a la vez, con copia previa fuera del repositorio, SHA-256 del conjunto de 81 archivos `.ts` y `.tsx` de `frontend/src` antes y después (`322ff0a04de9eb526b194698a167f0b91d915978e0b2c9e0572f34c641b9b33e` en las dos), restauración verificada tras cada uno y suite completa en verde al terminar (417 de 417).

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-2` | Quita el filtro `importe_tope === null` de «Guardar topes» | TC-23, variante «dos guardados seguidos». Sin ningún filtro, o sin el filtro por vacío, caen diez pruebas (TC-23, TC-25, TC-26, TC-28 y TC-29) |
| `M-3` | La confirmación de la tabla reenvía `confirmar_superior_a_venta: false` | TC-25 (cuerpo exacto); en el diálogo de recaptura, TC-33 |
| `M-4` | `PATRON_IMPORTE_TOPE` admite `{1,5}` decimales | `tope.formulario.test.ts` (varias) y TC-28 con `1.12345` (seis pruebas) |
| `M-6` | `puedeCapturar` incluye `DIRECTOR_PROYECTOS` | TC-24 y TC-27 |
| `M-7` | Formatea con `Number` en vez de `formatearImporte` | TC-22 en la tabla; cinco pruebas en la pantalla (TC-06 y «No disponible») |
| `M-9` | `DialogoRecaptura` envía sin `motivo` | TC-30 y TC-33 |
| `M-10` | `mensajeDeRechazo` devuelve un texto fijo en `PERMISO` | Seis pruebas: `presentacion.test.ts` (dos), TC-16 (dos), TC-29 y TC-32 |

Ningún mutante sobrevive. Los mutantes `M-1`, `M-5` y `M-8` son de la entrega a y se ejecutaron entonces.

### Modelo por paso

| Despacho | Agente | Modelo | Motivo |
|---|---|---|---|
| Rojo B1, B2, B3 y mutación | `tester-frontend` | `sonnet` | Por omisión de la metodología |
| Verde B1 | `desarrollador-react` | `haiku` | Diseño |
| Verde B2 y B3 | `desarrollador-react` | `sonnet` | Disparador del diseño: la fila toca una regla de dinero o de límite (`RN-03`) |
| Documentación B4 | `desarrollador-react` | `haiku` | Diseño |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | Por omisión; sin esquema, no hubo `auditor-sql` |

Ningún paso subió ni bajó de modelo.

### Auditorías

`auditor-arquitectura`: **`APROBADO`** en el primer ciclo, con dos observaciones sin acción. Resumen de su sección «Qué verifiqué»: dinero sin `Number`, `parseFloat` ni `toFixed` en el código nuevo y formateo siempre con `formatearImporte`; el tope se envía como cadena; el cliente no compara tope y venta (`D-10`) y solo el `409` con su `codigo` abre la confirmación; los límites bloquean (confirmar sin motivo no envía, «Corregir» no reenvía); tipos solo de `components["schemas"]`; sin backend, contrato ni fase 2 (`git diff --stat -- backend docs/api frontend/src/api` vacío); sin imports cruzados; cuatro estados presentes; el espacio de `DetalleCifras` no cambia el aspecto y sus consumidores siguen en verde; prueba de rechazo para cada regla implicada.

| ID | Observación | Acción |
|---|---|---|
| `F001` | `DetalleCifras.tsx` tiene CRLF en la copia de trabajo; Git lo normaliza | Ninguna |
| `F002` | El diff de wireframes incluye cambios de la entrega a | Ninguna: el diseño los declara |

Fuera de alcance, prioridad baja: `enviarTopes` hace varios `setState` tras cada `await`; solo se nota si el componente se desmonta a mitad de la serie.

### Resultado contra los criterios de aceptación

| Criterio | Resultado | Evidencia |
|---|---|---|
| `CA-3` (última cláusula) | Cumplido | TC-24 |
| `CA-6` | Cumplido | TC-22, TC-23 |
| `CA-7` | Cumplido | TC-21, TC-25, TC-26, TC-33 |
| `CA-8` | Cumplido | TC-30, TC-33 |
| `CA-9` | Cumplido | TC-27, TC-29, TC-31, TC-32 |
| `CA-10` | Cumplido | TC-20, TC-28, TC-34 |
| `CA-11` | Cumplido | TC-23, TC-26, TC-29 |
| `CA-13` (captura) | Cumplido | TC-27 |
| `CA-R1` | Cumplido: 417 de 417, sin aserciones previas modificadas | Suite completa |
| `CA-R2` | Cumplido | `tipos:verificar` y `git diff --stat` del generado vacío |
| `CA-S1` | Pendiente · entrega c | — |

### Pendientes

- **Entrega c** (semilla local y E2E, *Should*): sin ejecutar. Su disparador de recorte fija el cierre del 2026-11-11 para la aprobación de `/sdd-revisar` de esta entrega.
- **Decisión menor.** Los marcadores `(aprobado · D-7)` que quedaron en `docs/08-wireframes.md`, solo en §2: conservarlos o quitarlos.
- **`markdownlint-cli2` y `lychee`** no se ejecutaron localmente.

Siguiente: `/sdd-revisar TKT-018a` sobre la entrega b.

### Verificación final de `/sdd-revisar` · entrega b

Revisión ejecutada el 2026-11-11 sobre el diff de la entrega b: `git diff HEAD` desde el cierre de la entrega a (`d7bccc5`) más los archivos nuevos de `frontend/src/modulos/presupuesto/linea-base/`.

#### Completitud, corrección y coherencia

- **Completitud.** Cada criterio `[M]` de la entrega tiene resultado y evidencia (tabla más abajo). Cada fila B1 a B3 tiene en la sección de la entrega b el texto de su rojo, con el motivo del fallo, y la salida de su verde. B1 tiene una reserva ya declarada: el rojo de `tope.formulario.test.ts` es de módulo ausente.
- **Corrección.** Se implementó lo de la spec y nada de más. Los archivos extra respecto al diseño son `DetalleCifras.tsx` (un espacio, declarado) y `presentacion.ts` (helpers extraídos por `COD-6`, en una carpeta que el diseño ya preveía).
- **Coherencia.** Los objetos de `impl.md` coinciden con los del diseño. `git diff HEAD --stat -- frontend/src/api backend docs/api` está vacío: sin cambio de contrato, de backend ni de tipos generados.

#### Suite ejecutada en la revisión

Docker en marcha (`docker info`: 29.9.3). El diff no toca backend ni migraciones, así que `pytest`, `ruff`, `mypy` y `lint-imports` de backend no se repitieron: la última corrida completa del backend es la de la revisión de la entrega a (2767 en verde y 26 omitidas) y el diff de esta entrega no los afecta. Ejecutado desde `frontend/` tras el último cambio:

```text
npm test                 → Test Files 23 passed (23) · Tests 438 passed (438)
npm run lint             → eslint . (sin salida)
npm run typecheck        → tsc --noEmit (sin salida)
npm run tipos:verificar  → Tipos al día.
python tools/verificar_docs.py → ✓ Sin problemas.
vale (wireframes, diseño, impl) → 0 errors, 0 warnings and 0 suggestions
```

La suite pasó de 417 a 438 pruebas por el ciclo de corrección: quince de `COD-1` a `COD-5` (trece en rojo y dos de `COD-2`, que nacieron en verde), cuatro de `F002` y dos de `F003`. `markdownlint-cli2` y `lychee` no están instalados en esta máquina.

#### Auditorías de la revisión

| Auditor | Primera pasada | Final |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` (tres observaciones) | `APROBADO` |
| `auditor-seguridad` | `APROBADO` (`SEG-3` y `SEG-4`, Bajas) | `APROBADO`; `SEG-3` quedó resuelta por `COD-3` |
| `auditor-docs` | `REQUIERE CAMBIOS` (`DOC-1`, Menor) | Corregido por `corrector-revision`; `DOC-2` a `DOC-4` aplicados; `DOC-5` elevada a la persona dueña |
| `auditor-codigo` | `REQUIERE CAMBIOS` (tres Mayores y tres Menores) | Ciclo 1: `COD-1` a `COD-6` resueltos y `F002` nuevo. Ciclo 2: `F002` resuelto y `F003` nuevo. **`APROBADO CON MENORES RESUELTOS SIN REAUDITAR`** |

La primera pasada de `auditor-arquitectura` ya se había hecho al cerrar la ejecución; en la revisión se repitió con el diff real y dio el mismo veredicto. Los veredictos con su sección «Qué verifiqué» llegaron completos.

#### Ciclo de corrección

- **Ciclo 1.** Tres Mayores: `COD-1` (la cola de confirmaciones podía perder un tope al cancelar con la petición en vuelo; ahora `sacarDeLaCola` filtra por identificador y `CapturaMotivo` deshabilita la salida mientras envía), `COD-2` (faltaban pruebas con dos topes superiores en la cola) y `COD-3` (la confirmación de la recaptura reenviaba los valores actuales y no los que provocaron el `409`). Tres Menores: `COD-4`, `COD-5` y `COD-6`. El orden fue el del protocolo: `tester-frontend` en rojo (trece pruebas nuevas fallidas por comportamiento y dos de `COD-2` en verde, que matan `setCola([])`), después `corrector-revision` en `sonnet`, porque la fila toca `RN-03`.
- **Ciclo 2.** `F002` (Menor, nuevo): con la acción del bloqueo en vuelo, «Recapturar» seguía habilitado y un envío con otro tope lanzaba un segundo `PUT` concurrente; el rojo reprodujo la doble escritura (la fila quedó en `$60,000.00`). Corregido con el estado `enviando` y un `ref`. La reauditoría lo dio por resuelto y encontró `F003` (Menor, nuevo, de pruebas: nada probaba que `enviando` se libera tras un rechazo que deja el diálogo abierto).
- **`F003`, resuelto por el orquestador sin tercera reauditoría**, por el criterio del paso 4 (Menor de código de pruebas que no cambia el comportamiento del producto, tras el segundo ciclo). Se aplicó el texto literal del auditor: una prueba con `provocarElBloqueo()` y su variante con `422`; el mutante que quita `setEnviando(false)` del `finally` hace caer las dos y, sin él, la suite queda en 438 de 438. Se renombraron además las pruebas de `F002` a `hdu001_esc17` (`O-6`). **Se comunica a la persona dueña.**
- **Observaciones sin acción:** `O-1` (`recapturando` guarda la fila y no su identificador), `O-2` (`enviarTopes` no se cancela al desmontar), `O-3` (comentario del espacio de `DetalleCifras`), `O-5` (las acciones del bloqueo siguen habilitadas mientras envían; el segundo clic se descarta sin señal visible), `SEG-4` (el bucle de `PUT` no se corta ante un `403`), `O-2` y `O-3` de `auditor-arquitectura` (autor y fecha duplicados en dos componentes, CRLF en la copia de trabajo), y el mutante `slice(1)` de `sacarDeLaCola`, que sobrevive porque con las guardas ninguna prueba llega a esa rama (defensa en profundidad).

#### Mutación de la revisión

Repetida por los auditores sobre copias fuera del repositorio, con el árbol idéntico al terminar: `COD-1` (sin guarda de `onOpenChange` y sin `disabled`: nueve pruebas caen), `COD-2` (`setCola([])`: seis), `COD-3` (otro tope: tres), `COD-4` (una), `COD-5` (una), `F002` (sin guarda de reentrada: dos; sin marcar `enviando`: dos; solo `isSubmitting`: dos) y `F003` (sin `setEnviando(false)`: dos). Los mutantes de la ejecución (`M-2` a `M-10`) no cambiaron.

#### Resultado por criterio de la entrega b

| Criterio | Nivel | Resultado | Evidencia |
|---|---|---|---|
| `CA-3` (última cláusula) | `[M]` | Cumplido | TC-24 |
| `CA-6` | `[M]` | Cumplido | TC-22, TC-23 |
| `CA-7` | `[M]` | Cumplido | TC-21, TC-25, TC-26, TC-33 y las pruebas de la cola de `COD-1` y `COD-2` |
| `CA-8` | `[M]` | Cumplido | TC-30, TC-33 y `F002` |
| `CA-9` | `[M]` | Cumplido | TC-27, TC-29, TC-31, TC-32 |
| `CA-10` | `[M]` | Cumplido | TC-20, TC-28, TC-34 |
| `CA-11` | `[M]` | Cumplido | TC-23, TC-26, TC-29 |
| `CA-13` (captura) | `[M]` | Cumplido | TC-27 |
| `CA-R1` | `[M]` | Cumplido: 438 de 438, sin aserciones previas modificadas | Suite completa |
| `CA-R2` | `[M]` | Cumplido | `tipos:verificar` y diff del generado vacío |
| `CA-S1` | `[S]` | Pendiente · entrega c | — |

Hay prueba de rechazo para cada regla implicada (`RN-03`: tope mal formado, `422` y `403` por fila, tope superior a la venta con «Corregir», recaptura sin motivo; `RN-04`: la recaptura exige motivo) y las rutas críticas tienen mutación probada.

#### Desviaciones y pendientes para la persona dueña

- **`DOC-5`.** El diseño dice que no merece ADR, pero fija un `PUT` secuencial por fila en lugar de una ruta por lotes (`D-5`). Decidir si se escribe el ADR.
- **Marcador `(aprobado · D-7)`** en `docs/08-wireframes.md` §2: conservarlo o quitarlo.
- **Entrega c** (semilla local y E2E, *Should*): sin ejecutar. El disparador de recorte de la entrega b no se cumplió: la revisión se aprobó el 2026-11-11.
- **`markdownlint-cli2` y `lychee`** no se ejecutaron localmente; los corre CI en el PR.
- El delta del ticket debe decir que, si la entrega c se recorta, la pantalla solo se verá con línea base real a partir de TKT-018b.

**Veredicto de la entrega b: aprobada.** Queda acumulada en la rama `tkt-018a-pantalla-linea-base`, sin PR. Siguiente: `/sdd-ejecutar TKT-018a` sobre la entrega c, o recortarla con `/sdd-escalar` y pasar a `/sdd-completar`.

## Entrega c · semilla local y E2E (filas C1 y C2, *Should*)

Entrega c ejecutada el 2026-11-11 en la rama `tkt-018a-pantalla-linea-base`, que ya traía las entregas a y b (la b, en el commit `00fe418`). El disparador de recorte del diseño no se cumplió: la entrega b se aprobó el mismo día. Docker estaba en marcha. No hay cambio en `backend/cimenta`, en el contrato ni en los tipos generados.

### Qué se implementó

- **C1.** `backend/herramientas/semilla_linea_base_local.py`: `sembrar_linea_base` prepara en una transacción la obra en `PLANEACION`, el insumo de mano de obra `MO-001` y una importación `VALIDADO`, y confirma la importación con el caso de uso `materializar_importacion` de la interfaz publicada de `presupuesto`, que crea la línea base `BORRADOR` con su bitácora. `main()` niega cualquier base que no sea local antes de abrir una conexión y deja `OBRA_ID=<uuid>` en la última línea. El docstring de `backend/herramientas/soporte_tkt017.py` dice ahora que también lo usa esta semilla y que ningún módulo de `cimenta/` lo importa.
- **C2.** `frontend/e2e/preparacion-global.ts` siembra el tercer usuario de humo (`humo.direccion@cimenta.test`, Dirección General), ejecuta la semilla con una obra `E2E-LB-<8 hex>` y deja `CIMENTA_HUMO_LB_OBRA_ID`; `frontend/e2e/linea-base.spec.ts` recorre el congelado como Director de Proyectos y la captura de un tope como Dirección General.
- **Documentación.** `README.md` y `docs/arranque-local.md` explican cómo sembrar una línea base de demostración y qué siembra el E2E.

### Ajustes respecto al design

| Fila | Ajuste | Motivo |
|---|---|---|
| C1 | `insumo.creado_en_importacion` se inserta con `false` para `MO-001` | La columna es `NOT NULL` sin valor por omisión y el diseño no la mencionaba; es un insumo registrado, no uno dado de alta por la importación |
| C1 | `importacion.preparacion` se escribe con `json.dumps(preparacion_a_json(…))` y `CAST(:preparacion AS jsonb)` | Con `text()` de SQLAlchemy |
| C1 | Sin empresa activa, `SystemExit("No hay empresa activa en la base; ejecuta las migraciones. No se ha escrito nada.")` | El diseño no decía qué hacer; no es una regla de negocio nueva |
| C1 | Usuario resuelto por correo con `SELECT id FROM usuario WHERE email = :correo`; si falta, `SystemExit("Falta el usuario …; ejecuta herramientas.semilla_local.")` | Texto que el diseño ya fijaba; la consulta no filtra por `activo` |
| C1 | El reloj de `main()` es `datetime.now(UTC)` local a la herramienta | Así no se importa `cimenta.presupuesto.aplicacion.contexto`, que el diseño no listaba |
| C1 | `ContextoPresupuesto` se importa de `cimenta.presupuesto.interfaz`, que ya lo publica | El desarrollador lo había importado de `aplicacion.contexto`; el orquestador lo corrigió para respetar la lista de importaciones del diseño |
| C1 | `E-5`, `E-6` y `E-7` quedan comprobadas por TC-S1; `E-8` por TC-E1 | Eran afirmaciones sin ejecutar |
| C2 | `docs/arranque-local.md` actualiza la lista de escenarios del E2E | El texto decía «entrar y salir, credenciales incorrectas y el menú en un teléfono» |
| C2 | `frontend/test-results/.last-run.json`, que Playwright reescribe y está versionado, se restauró con `git checkout` | No es parte del cambio |

### Archivos tocados

| Archivo | Cambio |
|---|---|
| `backend/herramientas/semilla_linea_base_local.py` | Nuevo |
| `backend/tests/test_tkt018a_semilla_linea_base.py` | Nuevo (cinco pruebas) |
| `backend/herramientas/soporte_tkt017.py` | Solo el docstring |
| `frontend/e2e/preparacion-global.ts` | Tercer usuario y semilla |
| `frontend/e2e/linea-base.spec.ts` | Nuevo (TC-E1) |
| `README.md`, `docs/arranque-local.md` | Cómo sembrar la línea base de demostración |

### Ciclo TDD por fila

| Fila | Rojo | Verde | Refactor |
|---|---|---|---|
| C1 | Primer rojo: las cinco pruebas fallaron con `ModuleNotFoundError: No module named 'herramientas.semilla_linea_base_local'`; el tester no creó un esqueleto porque su rol no escribe producción. Rojo por comportamiento: el orquestador creó un esqueleto no funcional (`NotImplementedError`) y las cinco fallaron con `NotImplementedError` (`5 failed in 2.63s`) | `5 passed`; `ruff check`, `ruff format --check`, `mypy .` (287 archivos), `lint-imports` (16 contratos cumplidos), `verificar_float` (34 archivos, 0 hallazgos) y las 38 pruebas de `test_tkt010_semilla_local.py` en verde | `ruff format` sobre los dos archivos; el orquestador corrigió el import de `ContextoPresupuesto` y repitió las cinco pruebas, `ruff`, `mypy` y `lint-imports` |
| C2 | `npm run e2e`: `1 failed, 5 passed`; el spec falla con «Falta CIMENTA_HUMO_LB_OBRA_ID: la fija la preparación global (e2e/preparacion-global.ts).» y `humo.spec.ts` y `obras.spec.ts` siguen verdes | `npm run e2e`: `6 passed (13.9s)`, entre ellos `hdu001_esc14 · congelar como DP y capturar como DG` (2.0s) | Ninguno |

Ejecución con dos pasos del orquestador en C1 (el esqueleto y la corrección del import), declarados arriba; los tests no los tocó ningún desarrollador.

### Evidencia de ejecución al cerrar

```text
backend/  uv run pytest -q -x      → 2772 passed, 26 skipped in 573.32s (0:09:33)
backend/  uv run ruff check .      → All checks passed!
backend/  uv run ruff format --check . → 287 files already formatted
backend/  uv run mypy .            → Success: no issues found in 287 source files
backend/  uv run lint-imports      → Contracts: 16 kept, 0 broken.
backend/  verificar_float          → archivos revisados: 34; hallazgos: 0
frontend/ npm run e2e              → 6 passed (13.9s)
frontend/ npm test                 → Test Files 23 passed (23) · Tests 438 passed (438)
raíz      python tools/verificar_docs.py → ✓ Sin problemas.
raíz      vale README.md docs/arranque-local.md → 0 errors, 0 warnings and 0 suggestions
```

Las 26 pruebas omitidas son las de `PA-T3` (faltan los archivos reales del catálogo), las mismas que en la revisión de la entrega a. La suite de backend pasó de 2767 a 2772 pruebas: las cinco de la semilla.

### Mutación en rutas críticas

El diseño no pide mutantes para la entrega c (su tabla de mutación cubre las rutas de dinero y límite de las filas A y B). La semilla es una herramienta de preparación de datos que no decide ninguna regla. Queda anotado como decisión de alcance del diseño, no como mutación probada.

### Modelo por paso

| Despacho | Agente | Modelo | Motivo |
|---|---|---|---|
| Rojo C1 | `tester-backend` | `sonnet` | Por omisión |
| Verde C1 | `desarrollador-aplicacion` | `haiku` | Diseño |
| Rojo C2 | `tester-frontend` | `sonnet` | Por omisión |
| Verde C2 y documentación | `desarrollador-react` | `haiku` | Diseño |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | Por omisión; sin esquema, no hubo `auditor-sql` |

Ningún paso subió ni bajó de modelo.

### Efectos sobre el entorno local

El tester del E2E ejecutó `herramientas.contrasenas_roles` contra la base local (paso documentado de `docs/arranque-local.md`), que fija las contraseñas de los roles `cimenta_aplicacion` y `cimenta_lectura`. Cada corrida de `npm run e2e` añade a la base de humo las obras `E2E-` y `E2E-LB-` (riesgo declarado en el diseño). Playwright dejó modificado `frontend/test-results/.last-run.json` y se restauró.

### Auditorías

`auditor-arquitectura`: **`APROBADO`** en el primer ciclo, sin hallazgos Críticos, Mayores ni Menores y con dos observaciones sin acción. Resumen de su sección «Qué verifiqué»: ruff, mypy, `lint-imports`, `verificar_float` y las cinco pruebas en verde; sin `float`; `exigir_base_local()` antes de abrir ninguna conexión y la prueba de que no se llama a `create_engine` ante host remoto o `PGHOSTADDR`; la línea base la crea el caso de uso con su bitácora y la semilla no hace SQL sobre `linea_base` ni `bitacora`; el SQL directo se limita a `obra`, `insumo` e `importacion`; importaciones solo de la interfaz publicada, `preparacion_json` y `herramientas.*`; sin secretos en el repositorio ni en la salida; sin fase 2; `backend/cimenta` y `docs/api` sin cambios.

| ID | Observación | Acción |
|---|---|---|
| `O001` | Ninguna prueba cubre «Falta el usuario …» ni que `OBRA_ID=` sea la última línea de `main()`, de la que depende `preparacion-global.ts` | Ninguna; el E2E la ejercita de punta a punta |
| `O002` | `herramientas/` queda fuera de `import-linter` y `soporte_tkt017` llega transitivamente a `presupuesto.dominio` | Ninguna: el diseño lo declara y es el patrón de `soporte_tkt017_entorno.py` |

### Resultado contra los criterios de aceptación

| Criterio | Nivel | Resultado | Evidencia |
|---|---|---|---|
| `CA-S1` | `[S]` | Cumplido | TC-S1 a TC-S3, TC-E1 |

Hay prueba de rechazo para la regla implicada de la semilla (negarse fuera de la base local y ante un código de obra repetido): TC-S2 y TC-S3. El resto de los criterios `[M]` se cerraron en las entregas a y b.

### Pendientes

- **`/sdd-revisar TKT-018a` sobre la entrega c.** Es la última: al aprobarla el estado pasa a `LISTO PARA PR` y sigue `/sdd-completar`.
- **Decisiones para la persona dueña**, abiertas desde la entrega b: `DOC-5` (ADR de `D-5`) y el marcador `(aprobado · D-7)` de `docs/08-wireframes.md` §2.
- `markdownlint-cli2` y `lychee` no están instalados en esta máquina; los corre CI en el PR.

### Verificación final de `/sdd-revisar` · entrega c

Revisión ejecutada el 2026-11-11 sobre el diff de la entrega c: `git diff HEAD` desde el cierre de la entrega b (`00fe418`) más los archivos nuevos `backend/herramientas/semilla_linea_base_local.py`, `backend/tests/test_tkt018a_semilla_linea_base.py` y `frontend/e2e/linea-base.spec.ts`. Es la última entrega del ticket.

#### Completitud, corrección y coherencia

- **Completitud.** `CA-S1`, el único criterio de la entrega, tiene resultado y evidencia. Cada fila (C1 y C2) tiene su rojo registrado en la sección «Entrega c»; el de C1 se obtuvo en dos pasos declarados (módulo ausente y después esqueleto no funcional).
- **Corrección.** Se implementó lo de la spec y del diseño, con los ajustes declarados en la sección «Entrega c». El ciclo de corrección añadió, sin ampliar el alcance, la traducción del `ValueError` del puerto y las pruebas de `main()`.
- **Coherencia.** Los archivos de `impl.md` coinciden con los del diseño. `git diff HEAD --stat -- backend/cimenta docs/api frontend/src` está vacío: la entrega no toca la aplicación, el contrato ni los tipos generados.

#### Suite ejecutada en la revisión

Docker en marcha (`docker info`: 29.9.3). Cifras copiadas de la última corrida, posterior al ciclo de corrección:

```text
backend/  uv run pytest -q         → 2778 passed, 26 skipped in 555.28s (0:09:15)
backend/  uv run ruff check .      → All checks passed!
backend/  uv run ruff format --check . → 287 files already formatted
backend/  uv run mypy .            → Success: no issues found in 287 source files
backend/  uv run lint-imports      → Contracts: 16 kept, 0 broken.
backend/  verificar_float          → archivos revisados: 34; hallazgos: 0
frontend/ npm test                 → Test Files 23 passed (23) · Tests 438 passed (438)
frontend/ npm run lint             → eslint . (sin salida)
frontend/ npm run typecheck        → tsc --noEmit (sin salida)
frontend/ npm run tipos:verificar  → Tipos al día.
frontend/ npm run e2e              → 6 passed (13.5s)
raíz      python tools/verificar_docs.py → ✓ Sin problemas.
raíz      vale README.md docs/arranque-local.md docs/08-wireframes.md → 0 errors, 0 warnings and 0 suggestions
```

Las 26 pruebas omitidas son las de `PA-T3` (faltan los archivos reales del catálogo). La suite de backend pasó de 2772 a 2778 pruebas: las seis que el ciclo de corrección añadió a la semilla (la suite de la semilla pasó de 5 a 11). La sección «Entrega c» de arriba cita las cifras previas al ciclo (cinco pruebas y 2772); esta verificación las sustituye. `markdownlint-cli2` y `lychee` no están instalados en esta máquina; los corre CI en el PR.

#### Auditorías de la revisión

| Auditor | Primera pasada | Final |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` (`F001` a `F003`, observaciones) | `APROBADO` |
| `auditor-seguridad` | `APROBADO` (`SEG-1` a `SEG-4`, Bajas) | `APROBADO`; `SEG-4` aplicada |
| `auditor-docs` | `REQUIERE CAMBIOS` (`DOC-1` y `DOC-2` Mayores; `DOC-3` y `DOC-4` Menores) | `APROBADO` tras un ciclo |
| `auditor-codigo` | `REQUIERE CAMBIOS` (`COD-1` Mayor; `COD-2` y `COD-3` Menores) | `APROBADO` tras un ciclo |

No hubo `auditor-sql`: no hay esquema ni migración.

#### Ciclo de corrección

Un ciclo, con las pruebas antes del código:

- **`COD-1` (Mayor).** En `preparacion-global.ts`, `sembrarLineaBaseDeHumo` hacía `split` sobre `stdout` antes de mirar el fallo; con `uv` fuera del `PATH`, `stdout` y `status` son `null` y salía un `TypeError` que tapaba el mensaje guiado. Ahora se comprueba el fallo antes de parsear. La reauditoría lo comprobó con un `spawnSync` real de un ejecutable inexistente: sale el mensaje guiado con `spawnSync uv ENOENT`. No tiene prueba automatizada (el fallo del proceso hijo de la preparación global no se prueba con Vitest ni con Playwright); queda como observación del auditor (`OBS-8`).
- **`COD-2` (Menor).** Los helpers `ejecutarEnBackend` y `detalleDelFallo` sustituyen la duplicación entre los dos `spawnSync`.
- **`COD-3` (Menor) y `SEG-4` (Baja).** Seis pruebas nuevas: `main()` imprime `OBRA_ID=<uuid>` en la última línea y coincide con una fila de `obra`; las variables vacías caen a los valores por omisión; un correo inexistente sale con «Falta el usuario» sin escribir nada; el caso `PGSERVICE` de TC-S2; y el puerto no numérico. La del puerto nació en rojo por comportamiento (`ValueError`) y `main()` ahora lo traduce a `SystemExit` como `semilla_local.main()`. Las demás nacieron en verde (cobertura que faltaba) y seis mutantes las matan: línea extra tras `OBRA_ID=`, `OBRA=` en lugar de `OBRA_ID=`, el mensaje de «Falta el usuario», la omisión de las dos variables vacías y quitar `PGSERVICE` de la guarda. La huella SHA-256 de los `.py` de `backend/` fue idéntica antes y después de cada mutante.
- **`DOC-1` a `DOC-4`.** Aplicados con el texto literal del auditor en `README.md` y `docs/arranque-local.md`.
- **`SEG-2`** (`hide_parameters` en `sembrar_usuario_humo.py`) no se aplicó: el archivo es anterior a esta entrega y está fuera de su diff. `SEG-1` (la guarda no considera el puerto) y `SEG-3` (el trazado de Playwright registra las contraseñas aleatorias de cada corrida) son observaciones previas a la entrega y quedan para la persona dueña.

#### Mutación de la revisión

El diseño no pide mutantes para la entrega c y la semilla no decide ninguna regla; los mutantes arriba son los de las pruebas añadidas. La mutación de las rutas críticas del ticket se probó en las entregas a y b.

#### Resultado por criterio de la entrega c

| Criterio | Nivel | Resultado | Evidencia |
|---|---|---|---|
| `CA-S1` | `[S]` | Cumplido | TC-S1 a TC-S3, las pruebas de `main()` y TC-E1 |

Hay prueba de rechazo para la regla implicada de la semilla: negarse fuera de la base local (host remoto, `PGHOSTADDR`, `PGSERVICE`, host ausente y puerto no numérico) y ante un código de obra repetido o un usuario inexistente.

#### Resultado del ticket

Con esta entrega queda cumplido el ticket completo: `CA-1` a `CA-13`, `CA-R1` y `CA-R2` (`[M]`, entregas a y b) y `CA-S1` (`[S]`, entrega c). La suite de Vitest es de 438 pruebas, la de backend de 2778 y el E2E de 6. Los criterios que solo se verifican con el pipeline de un PR real (los trabajos de `ci.yml`) se verifican en `/sdd-completar`, que no fusiona sin esa evidencia.

#### Desviaciones y pendientes para la persona dueña

- **`DOC-5`** (de la entrega b): el diseño dice que no merece ADR, pero fija un `PUT` secuencial por fila en lugar de una ruta por lotes (`D-5`). Decidir si se escribe el ADR.
- **Marcador `(aprobado · D-7)`** en `docs/08-wireframes.md` §2: conservarlo o quitarlo.
- **`F001` de `auditor-arquitectura`.** La semilla crea la obra y la importación con `INSERT` directo porque `crear_obra` no está en la interfaz publicada de `presupuesto`, y la obra nace sin asiento de bitácora; solo afecta a una base local. Si TKT-018b o un ticket posterior publica `crear_obra`, migrar la semilla a ella. Debe constar en el delta.
- **`SEG-1`** (la guarda de base local no considera el puerto, como un túnel `ssh -L`), previa a esta entrega y presente en las tres siembras.
- **Delta:** debe decir que la pantalla solo se ve con línea base real mediante la semilla local hasta TKT-018b.
- **Base local de desarrollo:** la reauditoría dejó un usuario `x@y.z` (rol `COMPRAS`) y el E2E añade en cada corrida obras `E2E-` y `E2E-LB-`.

**Veredicto de la entrega c: aprobada. Último paso del ticket: `LISTO PARA PR`.** No se commitea aquí: el commit, el push y el PR único los hace `/sdd-completar`. Siguiente: `/sdd-completar TKT-018a`.
