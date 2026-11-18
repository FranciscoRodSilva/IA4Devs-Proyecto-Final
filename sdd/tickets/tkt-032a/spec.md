# Spec · TKT-032a · Pantalla del catálogo de proveedores

> [← index](_index.md) | Siguiente: design (se enlaza en `/sdd-disenar`)

## Contexto y problema

El backend del catálogo de proveedores está completo y fusionado: TKT-029a (alta, lista, consulta, cambio y desactivación) y TKT-029b (baja protegida por las órdenes pendientes). Las seis rutas de `/api/v1/proveedores` existen y están probadas contra PostgreSQL. **Pero no hay ninguna pantalla que las use.** TKT-029a se definió «solo backend, sin pantalla» por el plazo de la tercera entrega, y la pantalla quedó asignada a TKT-032, que además depende de las órdenes de compra (TKT-030 y TKT-031), todavía sin construir. El resultado, visto en la prueba manual del 2026-11-17: la sección «Proveedores» del menú existe, pero es un marcador de ruta y quien entra no puede hacer nada.

TKT-032 reúne tres cosas que no tienen la misma dependencia: la **pantalla del catálogo** (depende solo de lo ya fusionado), la **consulta proveedor × obra** (esc. 11, que necesita órdenes) y las pantallas de **emisión y cancelación** de órdenes. Por el plazo de la entrega y por la lección de TKT-011, TKT-012 y TKT-029, la persona dueña validó el 2026-11-17 partir el ticket: **TKT-032a** (esta spec, solo la pantalla del catálogo, solo frontend) y **TKT-032b** (consulta por obra, emisión y cancelación, que sigue dependiendo de TKT-030 y TKT-031).

## Historia de usuario

**Como** responsable de Compras
**quiero** ver el catálogo de proveedores y darlos de alta, corregirlos, desactivarlos y darlos de baja desde una pantalla
**para** mantener el catálogo sin recurrir a la API y ver al instante qué proveedores están activos.

Historia de referencia: [HDU-004](../../../docs/04-historias-usuario.md#hdu-004--proveedores-y-emisión-de-órdenes-de-compra), escenarios 1, 2, 3, 12 y 13.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | Pantalla «Proveedores» en el menú de Compras: la lista del catálogo con nombre, RFC, estado, día de corte y día de pago, búsqueda por texto, filtro por estado y paginación |
| **Must** | Alta: el botón `+` abre el formulario con el foco en el nombre (esc. 1); captura nombre, RFC, tope de consignación, día de corte y día de pago, con jueves y sábado por omisión (esc. 2); el proveedor aparece en la lista al guardar |
| **Must** | RFC duplicado: el `409` `RFC_DUPLICADO` se pinta junto al campo con el proveedor existente, sin acción de verlo (H-1); no se crea nada (esc. 3) |
| **Must** | Editar: nombre, tope de consignación, día de corte y día de pago; el RFC se muestra de solo lectura |
| **Must** | Desactivar con motivo, ofrecido **solo** a un proveedor `ACTIVO` (esc. 12) |
| **Must** | Dar de baja con motivo, ofrecido a un proveedor `ACTIVO` o `DESACTIVADO` (esc. 13); con órdenes `ABIERTA` o `PARCIAL` el `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` se pinta como bloqueo con la lista de órdenes y la acción de desactivar tomada del contrato (esc. 12) |
| **Must** | Rol: Compras opera; los seis roles consultan (tabla de roles de `docs/08-wireframes.md`) |
| **Must** | Una prueba de extremo a extremo: alta → aparece en la lista → mismo RFC otra vez muestra el existente → desactivar → deja de verse con el filtro por omisión |
| **Should** | Mostrar `BAJA` y `DESACTIVADO` con una etiqueta distinta en la lista cuando se filtran |
| **Could** | — |
| **Won't** | La consulta proveedor × obra (esc. 11), la emisión de órdenes, el selector de proveedor, la cancelación y todo lo que dependa de TKT-030 y TKT-031: **TKT-032b**. Reactivar un proveedor `DESACTIVADO` o dado de `BAJA` (no existe operación en el contrato; `PA-24`). Cambiar el RFC. Facturas, anticipos y consignación (`RN-15`, `RN-16`, v1.1). Validar el RFC contra el SAT. Exportar la lista |

## Non-goals

- **No toca el backend.** El contrato de las seis rutas ya está fusionado y probado; si la pantalla descubre que falta algo, es un hallazgo para `/sdd-escalar`, no un cambio de esta spec.
- **No define la pantalla de emisión de órdenes ni su selector de proveedor.** El selector solo lista proveedores `ACTIVO` y vive en TKT-032b.
- **No decide la reactivación.** La pantalla ofrece las dos operaciones que el contrato tiene, y ninguna de ellas devuelve un proveedor a `ACTIVO`.
- **No prueba el `409` de baja con órdenes reales**: las órdenes llegan con TKT-030; la prueba del cliente usa una respuesta simulada del contrato y, en el E2E, una orden sembrada por la vía de pruebas del backend (ver D-3).

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-17` | El corte semanal de proveedores es jueves y el pago, sábado, por omisión | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| Invariante 28 | `UNIQUE (rfc)`: dos proveedores no comparten RFC, tampoco uno dado de baja | [`docs/03-modelo-datos.md`](../../../docs/03-modelo-datos.md) §9 |
| `PA-24` | La baja es terminal y conserva el RFC `(asumido)`; abierta | PRD, preguntas abiertas |
| Regla 8 de `CLAUDE.md` | El cliente nunca decide: el `409` lo decide el servidor y la pantalla solo lo pinta | [`CLAUDE.md`](../../../CLAUDE.md) |

`RN-15` y `RN-16` (consignación, anticipos) son v1.1: el tope se captura y se muestra, sin lógica.

## Invariantes que deben sobrevivir al cambio

El ticket **no modifica comportamiento del servidor**; amplía la ruta `/proveedores` del cliente, hoy un marcador, y reutiliza componentes compartidos.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Rutas protegidas y armazón por rol (TKT-008b) | `/proveedores` conserva su guarda de sección y su entrada de menú | `CA-R1` |
| `FormularioCatalogo`, captura de motivo y pantalla de bloqueo (TKT-008c) | Reutilizarlos no cambia sus pruebas ya verdes | `CA-R2` |
| Contrato publicado (`openapi.yaml` y `servidor.ts`) | La pantalla usa los tipos generados; ninguna ruta ni campo inventado | `CA-R3` |
| Dinero nunca flotante | El tope de consignación se captura, se envía y se muestra como cadena con `decimal.js` | `CA-R4` |

## Criterios de aceptación

Gherkin, en español.

### CA-1 `[M]` · La lista del catálogo · `HDU-004 esc. 2`

```gherkin
Escenario: Compras abre «Proveedores» y ve el catálogo
  Dado que existen proveedores en estados ACTIVO, DESACTIVADO y BAJA
  Cuando un usuario de Compras abre «Proveedores»
  Entonces ve por omisión solo los ACTIVO, ordenados por nombre
  Y cada fila muestra nombre, RFC, día de corte, día de pago y estado
  Y puede filtrar por estado, buscar por texto y paginar
```

Los cuatro estados de la lista (cargando, vacía, con error y con datos) están todos pintados; el error trae un botón de reintento.

### CA-2 `[M]` · Alta de proveedor · `RN-17` · `HDU-004 esc. 1 y 2`

```gherkin
Escenario: Se da de alta un proveedor con los valores por omisión
  Dado que el usuario de Compras está en «Proveedores»
  Cuando pulsa el botón «+»
  Entonces se abre el formulario de alta con el foco en el nombre
  Cuando captura nombre y RFC y guarda
  Entonces el formulario se cierra
  Y el proveedor aparece en la lista como ACTIVO con corte "jueves" y pago "sábado"
```

Variante: capturar tope de consignación, día de corte y día de pago distintos los envía tal cual.

### CA-3 `[M]` · Rechazo · RFC duplicado · `HDU-004 esc. 3`

```gherkin
Escenario: El RFC ya existe
  Dado que ya existe un proveedor con el RFC "COP010101AB1"
  Cuando el usuario de Compras intenta dar de alta otro con ese RFC
  Entonces el servidor responde 409 CONFLICTO RFC_DUPLICADO
  Y el formulario sigue abierto, con el error dentro del formulario y debajo de los campos (D-9 del diseño)
  Y muestra el nombre del proveedor existente, sin botón de verlo (el contrato no trae la acción; queda como ticket futuro)
  Y no aparece ninguna fila nueva
```

### CA-4 `[M]` · Rechazo · Error de forma, por campo

```gherkin
Esquema del escenario: El servidor rechaza la forma
  Dado el formulario de alta abierto
  Cuando el servidor responde 422 por <campo>
  Entonces el error se pinta junto a <campo> y el formulario sigue abierto

  Ejemplos:
    | campo             |
    | nombre            |
    | rfc               |
    | tope_consignacion |
    | dia_corte         |
    | dia_pago          |
```

El formulario también valida antes de enviar: nombre vacío y formato de RFC; la validación del cliente es cortesía y el `422` del servidor manda.

### CA-5 `[M]` · Editar un proveedor

```gherkin
Escenario: Se corrige el nombre y el día de pago
  Dado que el usuario de Compras abre «Editar» sobre un proveedor
  Entonces el RFC aparece de solo lectura
  Cuando cambia el nombre y el día de pago y guarda
  Entonces el formulario se cierra y la lista muestra los datos nuevos
```

Un `422` se pinta junto al campo; un `404` (el proveedor desapareció) lo avisa y recarga la lista.

### CA-6 `[M]` · Desactivar con motivo · `HDU-004 esc. 12`

```gherkin
Escenario: Se desactiva un proveedor ACTIVO
  Dado un proveedor ACTIVO
  Cuando el usuario de Compras pulsa «Desactivar», captura el motivo y confirma
  Entonces el proveedor pasa a DESACTIVADO
  Y deja de verse con el filtro por omisión
  Y sin motivo el botón de confirmar no envía y el campo señala el error
```

«Desactivar» **no se ofrece** a un proveedor `DESACTIVADO` ni `BAJA`.

### CA-7 `[M]` · Dar de baja con motivo · `HDU-004 esc. 13`

```gherkin
Escenario: Se da de baja un proveedor sin órdenes pendientes
  Dado un proveedor ACTIVO o DESACTIVADO sin órdenes ABIERTA ni PARCIAL
  Cuando el usuario de Compras pulsa «Dar de baja», captura el motivo y confirma
  Entonces el proveedor pasa a BAJA
  Y deja de verse con el filtro por omisión
  Y no se ofrece ninguna acción más sobre él
```

### CA-8 `[M]` · Rechazo · Baja con órdenes pendientes · `HDU-004 esc. 12`

```gherkin
Escenario: El proveedor ACTIVO tiene órdenes abiertas
  Dado un proveedor ACTIVO con órdenes ABIERTA o PARCIAL
  Cuando el usuario de Compras intenta darlo de baja
  Entonces el servidor responde 409 CONFLICTO PROVEEDOR_CON_ORDENES_ABIERTAS
  Y la pantalla muestra el bloqueo con las órdenes listadas (folio y estado)
  Y ofrece la acción «Desactivar» tomada del contrato, no cableada
  Y el proveedor sigue ACTIVO

Escenario: El proveedor ya está DESACTIVADO
  Dado un proveedor DESACTIVADO con órdenes pendientes
  Cuando intenta darlo de baja
  Entonces el bloqueo lista las órdenes y NO ofrece desactivar, porque ya lo está
```

### CA-9 `[M]` · Rechazo · Rol y sesión

```gherkin
Esquema del escenario: Quien no opera
  Dado que el usuario entró como <rol>
  Cuando abre «Proveedores»
  Entonces <resultado>

  Ejemplos:
    | rol                                   | resultado                                              |
    | Compras                               | ve la lista y todas las acciones                        |
    | los otros cinco roles                 | ve la lista y no ve «+», «Editar», «Desactivar» ni «Dar de baja» |
    | cualquier rol, el servidor responde 403 | pinta el mensaje que manda el servidor, «Tu rol no permite esta operación.», sin cifras (D-6 del diseño) |
    | sin sesión                            | la guarda lo redirige al inicio de sesión              |
```

Ocultar los botones es cortesía de navegación (como en TKT-012a): el control real es el `403`.

### CA-10 `[M]` · Rechazo · Transición ya no válida · `HDU-004 esc. 12`

```gherkin
Escenario: Otro usuario cambió el estado mientras tanto
  Dado un proveedor que otro usuario ya dio de baja
  Cuando el usuario de Compras confirma «Desactivar» sobre la fila vieja
  Entonces el servidor responde 409 ESTADO_NO_PERMITE_OPERACION
  Y la pantalla muestra el mensaje del servidor y recarga la fila con su estado actual
```

### CA-11 `[M]` · Prueba de extremo a extremo

```gherkin
Escenario: Recorrido del catálogo
  Dado un usuario de Compras autenticado y un RFC único por corrida
  Cuando da de alta un proveedor, lo ve en la lista y repite el alta con el mismo RFC
  Entonces ve el conflicto con el proveedor existente
  Cuando desactiva el proveedor con motivo
  Entonces deja de verse con el filtro por omisión y aparece al filtrar por DESACTIVADO
```

### Criterios de regresión

- **CA-R1 `[M]`** La entrada «Proveedores» del menú y su guarda de sección siguen como en TKT-008b.
- **CA-R2 `[M]`** Las pruebas de `FormularioCatalogo`, de la captura de motivo y del bloqueo de TKT-008c siguen en verde sin cambios.
- **CA-R3 `[M]`** Un test recorre las llamadas de la pantalla y comprueba que cada ruta y cada cuerpo existen en `servidor.ts` generado.
- **CA-R4 `[M]`** El tope de consignación nunca pasa por `number`: entra y sale como cadena y se compara con `decimal.js`.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Solo depende de TKT-029a y TKT-029b, archivados |
| **N** | Describe el qué, no impone el cómo | Sí | Estructura de componentes y consultas quedan para el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Compras opera el catálogo desde la pantalla |
| **E** | Estimable sin investigar antes | Sí | El wireframe (D-1) es la primera fila del diseño, decidido el 2026-11-17 |
| **S** | Cabe en una sesión sin romper contexto | Sí | Solo frontend, patrón de TKT-012a; el diseño decide si lleva una o dos entregas |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio nombra un resultado observable |

Cero fallos.

## Definition of Done

La de funcionalidad de `sdd/metodologia.md` §8, solo frontend.

- [ ] Los criterios `[M]` `CA-1` a `CA-11` y `CA-R1` a `CA-R4` con su prueba en verde
- [ ] Una prueba de extremo a extremo (`CA-11`) en el pipeline
- [ ] Wireframe del catálogo de proveedores en `docs/08-wireframes.md`, reconciliado con el borrador (D-1)
- [ ] `docs/05-tickets-trabajo.md` con la partición de TKT-032 registrada
- [ ] Ningún cambio a `cimenta/`, a las migraciones ni a `openapi.yaml`; solo el sembrador local de pruebas `backend/herramientas/semilla_orden_proveedor_local.py` (H-2)

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| D-1 | **No existe wireframe de la pantalla del catálogo.** `docs/08-wireframes.md` solo nombra el menú y dice que el alta «usa el formulario de catálogo» sin dibujarla, y está en desacuerdo con el borrador sobre la baja (lo reconoce `docs/05`). Recomendación: el diseño incluye una fila que dibuja la pantalla y reconcilia la baja, con revisión de la persona dueña | Sin boceto, la pantalla se inventa; con boceto distinto, hay retrabajo | **Resuelta 2026-11-17**: el boceto es la primera fila del diseño |
| D-2 | **Quién ve qué** `(asumido)`: Compras opera; los otros cinco roles solo consultan, según la tabla de roles del wireframe y el `x-roles` de las rutas de lectura | Si Administración o Dirección General también operan, `CA-9` cambia | `(asumido)` |
| D-3 | **Cómo se prueba el `409` de la baja con órdenes en E2E**, si TKT-030 aún no existe: recomendación, sembrar una orden `PARCIAL` por la vía de pruebas de TKT-029b (`sembrar_orden_compra`) en la preparación global del E2E; si no se quiere tocar la semilla, el criterio se prueba solo con la respuesta simulada del contrato | Sin la siembra, el E2E no cubre `CA-8` | **Resuelta 2026-11-17**: se siembra una orden `PARCIAL` con `sembrar_orden_compra`, a través del sembrador local de H-2 que invoca el spec con `e2e/sembrar-orden.ts`; `preparacion-global.ts` no cambia |
| D-4 | **Un proveedor `DESACTIVADO` no puede volver a `ACTIVO`.** El contrato no tiene reactivación y `PA-24` está abierta. La pantalla lo deja explícito en el texto de la acción «Desactivar» («no recibirá órdenes nuevas») | Si Compras espera poder revertirlo, hay que abrir el ticket de reactivación (futuro) | Abierta · ya registrada como `PA-24` |
| D-5 | **Filtro por omisión: solo `ACTIVO`**, igual que el servidor. Para ver los desactivados y los dados de baja hay que filtrar | Si Compras espera ver todos, el primer uso confunde | `(asumido)` |
| S-1 | El motivo de desactivar y de dar de baja es obligatorio `(asumido por el contrato)` | `CA-6` y `CA-7` cambian | `(asumido)` |

## Pasada adversarial

Aplicada por quien redacta esta spec, no por un subagente `abogado-del-diablo`; conviene repetirla con la skill en `/sdd-disenar`.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | La pantalla sin wireframe se inventa. Esto es lo que hizo que TKT-029a saliera sin pantalla | D-1: el boceto es la primera fila del diseño y requiere visto bueno |
| 2 | Alta | La baja con órdenes no se puede probar de punta a punta sin órdenes reales | D-3 y `CA-8`: siembra por la vía de pruebas o respuesta simulada del contrato; se declara en el DoD qué se cubrió |
| 3 | Media | Hay dos operaciones de estado con efectos distintos (desactivar y baja) que se confunden fácilmente en una fila | El texto de cada acción dice su efecto en una línea; `CA-6` y `CA-7` prueban cada una |
| 4 | Media | Ocultar botones por rol no es seguridad | `CA-9`: el `403` del servidor se pinta; los botones son cortesía, como en TKT-012a |
| 5 | Media | La lista muestra por omisión solo `ACTIVO`: un proveedor desactivado «desaparece» y parece un borrado | D-5 y el Should de etiquetas; el filtro por estado es visible y el E2E lo recorre |
| 6 | Baja | El RFC se pinta con un patrón del cliente que podría divergir del servidor | `CA-4`: la validación del cliente es cortesía y el `422` manda; `CA-R3` ata los contratos |

## Contexto técnico

- **Frontend, solo:** `frontend/src/modulos/proveedores/rutas.tsx` (hoy el marcador) y la entrada de `frontend/src/app/navegacion/secciones.ts`. El patrón a seguir es `frontend/src/modulos/presupuesto/obras/` (`PantallaObras.tsx`, `obras.consultas.ts`, `obras.formulario.ts`) de TKT-012a.
- **Componentes compartidos a reutilizar:** `FormularioCatalogo`, la captura de motivo y la pantalla de bloqueo de TKT-008c.
- **Contrato (ya fusionado):** `GET/POST /api/v1/proveedores`, `GET/PATCH /api/v1/proveedores/{proveedor_id}`, `POST …/desactivacion` y `POST …/baja`, con `Proveedor`, `ProveedorNuevo`, `ProveedorCambios`, `EstadoProveedor` y los `409` `RFC_DUPLICADO`, `PROVEEDOR_CON_ORDENES_ABIERTAS` y `ESTADO_NO_PERMITE_OPERACION`. La lista acepta `estado` (repetible, por omisión `ACTIVO`), `q`, `pagina` y `tamano_pagina` (1 a 200, 50 por omisión). Tipos en `frontend/src/api/generado/servidor.ts`.
- **E2E:** `frontend/e2e/` con la preparación global que ya siembra usuarios de humo por rol; un spec nuevo `proveedores.spec.ts`, con un RFC único por corrida.
- **Backend de apoyo para la prueba:** `backend/herramientas/soporte_tkt029b_ordenes.py` (`sembrar_orden_compra`), solo si D-3 se confirma.
