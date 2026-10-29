# Impl · TKT-008a · Andamiaje, tipos, cliente de API y dinero

> [← index](_index.md) | [← design común](../tkt-008/design.md) | Siguiente: delta (pendiente de `/sdd-completar`)

## Qué se implementó

El andamiaje del cliente (Vite, Tailwind v4, shadcn/ui, Vitest con MSW, Playwright instalado, versiones exactas), las reglas de ESLint que prohíben `Number`, `document.cookie`, `decimal.js` y Zod fuera de su sitio, la generación y verificación de tipos del OpenAPI (`scripts/tipos.ts` y los dos archivos de `src/api/generado/`), el módulo de dinero con `decimal.js`, la normalización del error del contrato (`errores.ts`) y el cliente de API con CSRF, fin de sesión y permisos (`cliente.ts`, `sesion.ts`, `ProveedorApi.tsx`). La fila 7 comprueba por mutación que los tests dependen de algo y que el backend no cambió. Ningún archivo bajo `backend/` está en el diff.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-26 | `package.json` añade `"overrides": { "openapi-typescript": { "typescript": "$typescript" } }` y se reinstala `openapi-typescript@7.13.0` | `npm install` falló con `ERESOLVE`: el paquete declara como par `typescript@^5.x` y el proyecto fija `typescript` 6.0.3. Es el caso de la regla de «Versiones»; no se usó `--legacy-peer-deps` ni `--force`. |
| 2026-10-26 | Los paquetes de desarrollo se instalan con `npm install -E -D`, no solo con `-E` | El diseño omite `-D`. Sin él, npm los habría escrito en `dependencies`, y «Versiones» los clasifica como desarrollo. |
| 2026-10-26 | Librería y preset de shadcn elegidos por omisión: `npx shadcn@latest init -t vite -b base -p nova -y`. Componentes con `add` del CLI, versión 4.22.1 | El diseño dice «estilo por omisión» y no fija librería ni preset. `-d` usa la plantilla `next`, no Vite. Base UI es la librería recomendada por el CLI; Radix es la alternativa. El CLI añade `cn`, `@base-ui/react`, `class-variance-authority`, `lucide-react`, `tw-animate-css`, `@fontsource-variable/geist` y `shadcn`, que no figuran en «Versiones» pero están permitidos por su fila. |
| 2026-10-26 | `src/index.css` contiene el tema del CLI (`@theme`, variables, fuente Geist) y no solo `@import "tailwindcss";` | Lo escribe el CLI de shadcn al inicializar. |
| 2026-10-26 | `constComoEnum` no añade `enum` cuando el valor de `const` es un objeto | Una propiedad que se llama `const` dentro de `properties` es un esquema, no un valor literal, y el `enum` que le añadiría sería falso. El diseño no distingue ese caso. Sin test propio. |
| 2026-10-26 | `subconjuntoContratoError` lanza ante un `$ref` que no empieza por `#/components/schemas/` | El diseño solo fija el error para un esquema que falta. Una referencia a otra sección del borrador no se puede resolver dentro del subconjunto, y sin el error el resultado quedaría abierto. |
| 2026-10-26 | En `generar`, un fallo al escribir los archivos también sale con código 2 | El diseño no fija el código de un error de escritura. Un fallo sin capturar de Node sale con 1, que es el código de desfase, y lo confundiría con él. |
| 2026-10-26 | ~~TC-17 y TC-18 (`src/api/tipos.test.ts`) quedan pendientes de `tester-frontend`~~ **Cerrado el 2026-10-26**: `tester-frontend` escribió `src/api/tipos.test.ts` y ambos están en verde (véase «Cierre de la fila 3»). Queda la desviación de la fila siguiente | El diseño los escribe después de generar los archivos, y en la fila 3 solo se pidió el código y las verificaciones. |
| 2026-10-26 | TC-18 no afirma sobre `ImporteNoNegativo`, que el diseño lista | El subconjunto cerrado de nueve raíces de `RAICES_CONTRATO_ERROR` no alcanza ese esquema: ningún esquema de error lo referencia, y el provisional generado no lo declara (tampoco `servidor.ts`). Una aserción sobre él no compilaría. **Resuelto por el orquestador como ajuste menor:** `ImporteNoNegativo` sale de TC-18. Ningún esquema de error lo usa, y ampliar el subconjunto provisional para un esquema sin consumidor contradice D-10. Los mutantes MT-T1 a MT-T4 del tester se adoptan como la prueba de que TC-17 y TC-18 dependen de algo, porque ninguno de MT-1 a MT-14 los pone en rojo. |
| 2026-10-26 | La fila 7 añade TC-M6, TC-H1 y TC-H2 (véase «Pruebas») y no toca código de producción | MT-6 sobrevivía a TC-15, que solo prueba una edición que cambia la longitud. Los otros dos son los huecos que señalaron el tester y el desarrollador de la fila 6: el token fallido no se cachea y `exigir` con `FalloApi`. Por eso la fila queda `⚠ Ajustado`. |
| 2026-10-26 | Ciclo de corrección 1 · F001: `eslint.config.js` amplía los selectores de `document.cookie` (propiedad computada con `Literal`, `window.document.cookie` y cualquier objeto cuya propiedad se llame `document`, desestructuración `{ cookie } = document` en declaración y en asignación), de `Number`/`parseFloat`/`parseInt` (`globalThis.`, `window.` y `self.`, en llamada y en `new`) y de `import("decimal.js")` (`ImportExpression`), este último fuera del módulo de dinero. Las exenciones del módulo de dinero se mantienen y `document.title` sigue sin error (TC-F1f). | La regla solo reconocía la forma con identificador. Limitación aceptada por decisión del orquestador: las coerciones aritméticas (`"1" * 1`, `-"1"`, `.toFixed`, `Math.round`) siguen sin detectarse, porque prohibirlas daría falsos positivos en código que no maneja dinero. |
| 2026-10-26 | Ciclo de corrección 1 · F002: el tester escribió temporalmente `src/api/cliente.ts` en la fila 6, en contra de la metodología §16. Se repitieron los mutantes b, c y e sobre el archivo real (MT-B2b, MT-B2c y MT-B2e) y los tres cayeron (véase «Ciclo de corrección 1 · Rojo»). | Dejar constancia de la desviación y de que el archivo real quedó cubierto por los mismos mutantes. |
| 2026-10-26 | Ciclo de corrección 1 · F003: `shadcn` pasa de `dependencies` a `devDependencies` con `npm install -D -E shadcn@4.22.1`. Con `src/index.css` importado temporalmente desde `main.tsx`, `npm run build` resuelve `@import "shadcn/tailwind.css"` y genera el CSS (30,33 kB); después se revirtió. | Es una herramienta de generación de componentes y de estilos de tiempo de compilación, no de ejecución. Hoy `main.tsx` no importa `index.css`, así que la compilación normal no ejercita ese `@import`; lo hará la fila 9 de TKT-008b. |
| 2026-10-26 | Ciclo de corrección 1 · F004: `aDosDecimales` de `src/compartido/dinero/dinero.ts` redondea con `toDecimalPlaces(2, ROUND_HALF_UP)` y, si el resultado es cero, devuelve `"0.00"`. Cubre `formatearImporte` y `formatearCantidad`. | `toFixed(2)` da `"-0.00"` e `Intl` conserva el signo: se mostraba `-$0.00`. El arreglo vive en el módulo de dinero y usa `decimal.js`, sin conversión a `number`. |
| 2026-10-26 | Ciclo de corrección 1 · F005: en `src/api/cliente.ts`, `pedirToken` lanza `FalloApi` con el error normalizado si `GET /sesion/csrf` no es 2xx, o con `GENERICO` (estado de la respuesta) si es 200 sin `token` cadena no vacía; `pedir` devuelve ese error y solo da `RED` ante `TypeError` o `AbortError`. Cualquier otra excepción es `GENERICO` con `estado: 0` (asumido). Se mantienen la promesa compartida y el reinicio del token. | `RED` significa «la petición no llegó al servidor» (CA-4 esc. 3). Antes, un 500 del token salía como `RED` y un 200 sin `token` enviaba `X-CSRF-Token: undefined`. |
| 2026-10-26 | Revisión · ciclo 1 · C002: `src/api/cliente.ts` envuelve el `fetch` del cliente en un `try/catch` que lanza `FalloDeFetch` (clase local, sin propiedades de parámetro por `erasableSyntaxOnly`); `pedir` da `RED` solo ante esa marca. Cualquier otra excepción, incluido un `TypeError` de `headers.set`, es `GENERICO` con `estado: 0` (asumido). Se mantienen la promesa compartida y el reinicio del token | `RED` significa «la petición no llegó al servidor». Detectarlo por el tipo de la excepción en `pedir` confundía un `TypeError` del propio código con una caída de red. |
| 2026-10-26 | Revisión · ciclo 1 · C003 y F101: `aDosDecimales` devuelve `null` si el `Decimal` es `null` o no es finito, y con él `formatearImporte` y `formatearCantidad` | `Infinity`, `NaN` y `-Infinity` se presentaban como `$∞` o `∞`. |
| 2026-10-26 | Revisión · ciclo 1 · C005: `scripts/tipos.ts` justifica con un comentario el `as Parameters<typeof openapiTS>[0]` | `constComoEnum` devuelve `unknown` y `openapiTS` espera su tipo de documento OpenAPI, que no se puede estrechar sin duplicar su esquema. |
| 2026-10-26 | Revisión · ciclo 1 · C006, parte de producción: **aceptado sin cambio**. `esDocumento` (`scripts/tipos.ts`) y `esObjeto` (`src/api/errores.ts`, y la copia de `scripts/esqueleto.test.ts`) siguen separadas | `scripts/` y `src/` son proyectos distintos de Vitest y de TypeScript: unificarlas obligaría a que `scripts/` importe de `src/` o al revés. Son tres líneas. |
| 2026-10-26 | Revisión · ciclo 1 · documentación (D001 a D005, D007, D008 y F102), por decisión del usuario del 2026-10-26: 008a documenta lo que entrega. Cambian `CLAUDE.md`, `docs/arranque-local.md` y `conv-frontend-react`; la spec de 008a pierde el non-goal que lo prohibía; el diseño común y las fichas de 008 y 008b anotan la reasignación | Véase «Documentación actualizada». `docs/arranque-local.md` añade además la frase de D-9 (Chromium o Firefox) en el párrafo de `npm run dev`. |
| 2026-10-26 | Ciclo de corrección 1 · F006: `sesionOptions`, `ProveedorApi` y `useApi` quedan sin test en 008a. | Deuda registrada: la cierra TKT-008b, que los consume. |
| 2026-10-27 | Datos de prueba de `cliente.test.ts` normalizados al dominio reservado `@cimenta.test` y a una contraseña de prueba explícita, por decisión del usuario tras el aviso de `git-entrega` en el cierre | Decisión del usuario. |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `frontend/package.json` | Modificado: scripts literales, versiones exactas y `overrides` | Configuración |
| `frontend/package-lock.json` | Modificado por las instalaciones | Configuración |
| `frontend/tsconfig.json` | Modificado: literal de «Configuración» | Configuración |
| `frontend/vite.config.ts` | Creado: literal de «Configuración» | Configuración |
| `frontend/eslint.config.js` | Modificado en la fila 1 (bloque base y `ignores`) y en la fila 2 (`react-hooks`, `no-restricted-syntax` y `no-restricted-imports` de «Configuración») | Configuración |
| `frontend/components.json` | Creado por `shadcn init` | Configuración |
| `frontend/index.html` | Creado: `lang="es"`, `#raiz`, script `/src/main.tsx` | Aplicación |
| `frontend/src/main.tsx` | Creado: provisional, pinta `<p>CIMENTA</p>` (la fila 9 lo sustituye) | Aplicación |
| `frontend/src/index.css` | Creado: `@import "tailwindcss";`, ampliado con el tema del CLI | Estilos |
| `frontend/src/pruebas/preparacion.ts` | Creado: jest-dom, `listen`, `cleanup`, `close` de MSW | Pruebas |
| `frontend/src/pruebas/servidor.ts` | Creado: `servidorPruebas = setupServer()` | Pruebas |
| `frontend/src/lib/utils.ts` | Creado por el CLI (`cn`) | Compartido |
| `frontend/src/components/ui/button.tsx` | Creado por el CLI | Primitivas |
| `frontend/src/components/ui/input.tsx` | Creado por `shadcn add` | Primitivas |
| `frontend/src/components/ui/label.tsx` | Creado por `shadcn add` | Primitivas |
| `frontend/src/components/ui/textarea.tsx` | Creado por `shadcn add` | Primitivas |
| `frontend/src/components/ui/dialog.tsx` | Creado por `shadcn add` | Primitivas |
| `frontend/src/compartido/dinero/dinero.ts` | Creado en la fila 4: único importador de `decimal.js`; `Decimal` clonado con `ROUND_HALF_UP`, `aDecimal`, `formatearImporte`, `formatearCantidad`, `enteroNoNegativo`. Literal del diseño | Compartido |
| `frontend/src/api/errores.ts` | Creado en la fila 5: unión `ErrorApi` por `tipo`, `GENERICO`, `RED`, `ESTADO_DE_TIPO` y `normalizarError`. Literal del diseño | Compartido |
| `frontend/src/index.ts` | Borrado | — |
| `.gitignore` | Modificado: `frontend/playwright-report/` y `frontend/test-results/` bajo `# Node` | Raíz |
| `frontend/scripts/tipos.ts` | Creado en la fila 3: exportación del OpenAPI publicado, subconjunto del contrato de error, generación y verificación de tipos | Herramientas |
| `frontend/src/api/generado/servidor.ts` | Generado por `npm run tipos:generar` (241 líneas). No se edita a mano | Generado |
| `frontend/src/api/generado/contrato-error.provisional.ts` | Generado por `npm run tipos:generar` (276 líneas). Provisional, con cabecera de retirada. No se edita a mano | Generado |
| `frontend/src/api/cliente.ts` | Creado en la fila 6: `aplicarCsrf`, `crearClienteApi`, `pedir`, `exigir`, `FalloApi`. Literal del diseño | Compartido |
| `frontend/src/api/sesion.ts` | Creado en la fila 6: `claves`, `UsuarioActual`, `Rol`, `sesionOptions` | Compartido |
| `frontend/src/api/ProveedorApi.tsx` | Creado en la fila 6: `ProveedorApi` y `useApi` | Compartido |
| `frontend/src/api/cliente.ts` | Modificado en el ciclo de corrección 1 (F005): `pedirToken` y `pedir` | Compartido |
| `frontend/src/compartido/dinero/dinero.ts` | Modificado en el ciclo de corrección 1 (F004): un valor que redondea a cero va sin signo | Compartido |
| `frontend/eslint.config.js` | Modificado en el ciclo de corrección 1 (F001): selectores ampliados | Configuración |
| `frontend/package.json` y `frontend/package-lock.json` | Modificados en el ciclo de corrección 1 (F003): `shadcn` a `devDependencies` | Configuración |
| `frontend/src/api/cliente.ts` | Modificado en la revisión, ciclo 1 (C002): `FalloDeFetch` y el `fetch` envuelto; `pedir` | Compartido |
| `frontend/src/compartido/dinero/dinero.ts` | Modificado en la revisión, ciclo 1 (C003, F101): un valor no finito no se presenta | Compartido |
| `frontend/scripts/tipos.ts` | Modificado en la revisión, ciclo 1 (C005): comentario sobre el aserto de `openapiTS` | Herramientas |
| `docs/05-tickets-trabajo.md` | Modificado en la partición: TKT-008a, TKT-008b y TKT-008c como subsecciones de TKT-008 | Documentación |
| `frontend/scripts/esqueleto.test.ts`, `frontend/scripts/eslint-reglas.test.ts`, `frontend/scripts/tipos.test.ts`, `frontend/src/api/tipos.test.ts`, `frontend/src/api/errores.test.ts`, `frontend/src/api/cliente.test.ts` y `frontend/src/compartido/dinero/dinero.test.ts` | Creados por `tester-frontend` (siete archivos de prueba) y ampliados en los ciclos de corrección | Pruebas |
| `CLAUDE.md`, `docs/arranque-local.md` y `.claude/skills/conv-frontend-react/SKILL.md` | Modificados en la revisión, ciclo 1 (D001 a D005) | Documentación |
| `sdd/tickets/tkt-008/_index.md`, `sdd/tickets/tkt-008/design.md`, `sdd/tickets/tkt-008a/spec.md` y `sdd/tickets/tkt-008b/_index.md` | Modificados en la revisión, ciclo 1 (D007, D008, reasignación y F102) | Documentación |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `scripts/esqueleto.test.ts` · `tkt008_car1 · versiones fijadas` | rechazo (un rango cae) | `CA-R1` | no ejecutable: sin vitest | PASA |
| TC-02 | `scripts/esqueleto.test.ts` · `tkt008_ca01_esc01 · proxy en el mismo origen` | feliz | `CA-1` esc. 1 | no ejecutable: sin vitest | PASA |
| TC-04 | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc03 · Number en src` | rechazo | `CA-13` esc. 3 | rojo: `lintText` sin mensajes | PASA |
| TC-05 | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc03 · las demás conversiones` | rechazo | `CA-13` esc. 3, D-3 | rojo: `lintText` sin mensajes | PASA |
| TC-06 | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc03 · el módulo de dinero está exento` | feliz, con control de rechazo | `CA-13` esc. 3 | rojo: el control fuera del módulo no recibe mensaje | PASA |
| TC-07 | `scripts/eslint-reglas.test.ts` · `tkt008_car3 · document.cookie` | rechazo | `CA-R3` | rojo: `lintText` sin mensajes | PASA |
| TC-08 | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc04 · Zod solo en formularios` | rechazo y feliz | `CA-13` esc. 4 | rojo: `lintText` sin mensajes | PASA |
| TC-09 | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc03 · decimal.js solo en su módulo` | rechazo y feliz | `CA-13` esc. 3 | rojo: `lintText` sin mensajes | PASA |
| TC-10 | `scripts/eslint-reglas.test.ts` · `tkt008_car1 · TSX` | rechazo | `CA-R1` | rojo: `lintText` sin mensajes | PASA |
| TC-11 | `scripts/tipos.test.ts` · `tkt008_ca02_esc01 · subconjunto cerrado` | feliz y rechazo (un esquema que falta en el borrador se nombra; desde la revisión, contra una lista literal de 25 esquemas) | `CA-2` esc. 1 | rojo: módulo inexistente `scripts/tipos.ts` | PASA |
| TC-12 | `scripts/tipos.test.ts` · `tkt008_ca02_esc01 · cabecera provisional` | feliz | `CA-2` esc. 1 | rojo: módulo inexistente `scripts/tipos.ts` | PASA |
| TC-13 | `scripts/tipos.test.ts` · `tkt008_ca02_esc04 · determinista` | feliz | `CA-2` esc. 4 | rojo: módulo inexistente `scripts/tipos.ts` | PASA |
| TC-14 | `scripts/tipos.test.ts` · `tkt008_ca02_esc03 · desfase` | rechazo | `CA-2` esc. 3 | rojo: módulo inexistente `scripts/tipos.ts` | PASA |
| TC-15 | `scripts/tipos.test.ts` · `tkt008_ca02_esc05 · edición a mano` | rechazo | `CA-2` esc. 5 | rojo: módulo inexistente `scripts/tipos.ts` | PASA |
| TC-16 | `scripts/tipos.test.ts` · seis tests desde la revisión (C004): `tkt008_ca02_esc01 · exportación fallida…`, `tkt008_ca02_esc01 · exportación correcta…`, `tkt008_ca02_esc01 · salida 2…`, `tkt008_ca02_esc03 · salida 1…`, `tkt008_ca02_esc04 · salida 0…` y `tkt008_ca02 · salida 3…` | rechazo (códigos de salida 0, 1, 2 y 3) | `CA-2` esc. 1 y 3, `PA-T10` | rojo: módulo inexistente `scripts/tipos.ts` | PASA |
| TC-17 | `src/api/tipos.test.ts` · `tkt008_ca02_esc02 · el switch estrecha` | feliz (la parte de tipos la prueba `npm run typecheck`) | `CA-2` esc. 2 | nace en verde, por diseño: comprueba un archivo generado | PASA |
| TC-18 | `src/api/tipos.test.ts` · `tkt008_car3 · importes y cantidades como cadena` | rechazo (un `number` en un importe cae) | `CA-R3`, `CA-2` esc. 1 | nace en verde, por diseño: comprueba un archivo generado | PASA |
| TC-19 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca13_esc01 · suma exacta` | feliz | `CA-13` esc. 1 | rojo: módulo `./dinero` inexistente | PASA |
| TC-20 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca13_esc02 · redondeo al presentar` | feliz | `CA-13` esc. 2, `PA-T5` | rojo: módulo `./dinero` inexistente | PASA |
| TC-21 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca13_esc02 · sin pasar por number` | rechazo (cae con `Number`) | `CA-13` esc. 2 | rojo: módulo `./dinero` inexistente | PASA |
| TC-22 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca08_esc05 · cifra inválida` | rechazo | `CA-8` esc. 5 | rojo: módulo `./dinero` inexistente | PASA |
| TC-23 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca13_esc02 · negativo` | feliz | `CA-13` | rojo: módulo `./dinero` inexistente | PASA |
| TC-24 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca08_esc02 · cantidades` | feliz | `CA-8` esc. 2 | rojo: módulo `./dinero` inexistente | PASA |
| TC-25 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca09_esc02 · Retry-After` | rechazo | `CA-9` esc. 2 | rojo: módulo `./dinero` inexistente | PASA |
| TC-26 | `src/api/errores.test.ts` · ocho tests desde la revisión (C004), `tkt008_ca04_esc01 · <TIPO> con sus campos`, y `tkt008_ca04_esc01 · CONCURRENCIA sin Retry-After…` | feliz | `CA-4` esc. 1 | rojo: módulo `./errores` inexistente | PASA |
| TC-27 | `src/api/errores.test.ts` · `tkt008_ca04_esc02 · fuera del contrato` | rechazo (incluye `HTTPValidationError` → `GENERICO`, hallazgo M-1) | `CA-4` esc. 2 | rojo: módulo `./errores` inexistente | PASA |
| TC-28 | `src/api/errores.test.ts` · `tkt008_ca04_esc02 · tipo desconocido` | rechazo | `CA-4` esc. 2 | rojo: módulo `./errores` inexistente | PASA |
| TC-29 | `src/api/errores.test.ts` · `tkt008_ca04_esc04 · acciones intactas` | feliz | `CA-4` esc. 4 | rojo: módulo `./errores` inexistente | PASA |
| TC-30 | `src/api/cliente.test.ts` · `tkt008_ca03_esc01 · token antes de iniciar` | feliz | `CA-3` esc. 1 | rojo: módulo `./cliente` inexistente | PASA |
| TC-31 | `src/api/cliente.test.ts` · `tkt008_ca03_esc02 · mutaciones sí, GET no` | feliz y rechazo (`GET` y `HEAD` no llevan cabecera) | `CA-3` esc. 2 | rojo: módulo `./cliente` inexistente | PASA |
| TC-32 | `src/api/cliente.test.ts` · tres tests desde la revisión (C004), `tkt008_ca03_esc01 · PA-T9 · tras iniciar…`, `· tras cerrar…` y `· dos mutaciones simultáneas…` | feliz (token nuevo tras iniciar y tras cerrar; una sola petición compartida) | `CA-3`, `PA-T9` | rojo: módulo `./cliente` inexistente | PASA |
| TC-33 | `src/api/cliente.test.ts` · `tkt008_ca03_esc03 · origen no verificado` | rechazo (error `PERMISO` completo, sin reintento, token descartado, hallazgo m-4) | `CA-3` esc. 3, `PA-T9` | rojo: módulo `./cliente` inexistente | PASA |
| TC-34 | `src/api/cliente.test.ts` · `tkt008_ca04_esc03 · sin red` | rechazo | `CA-4` esc. 3 | rojo: módulo `./cliente` inexistente | PASA |
| TC-35 | `src/api/cliente.test.ts` · tres tests desde la revisión (C004), `tkt008_ca05_esc01 · GET /api/v1/sesion…`, `tkt008_ca05_esc03 · POST /api/v1/sesion…` y `tkt008_ca05_esc03 · POST /api/v1/sesion/cierre…` | feliz y rechazo (`GET /sesion` termina; `POST /sesion` y `POST /sesion/cierre` no) | `CA-5` esc. 1 y 3 | rojo: módulo `./cliente` inexistente | PASA |
| TC-36 | `src/api/cliente.test.ts` · `tkt008_ca05_esc04 · 403 pregunta de nuevo` | feliz | `CA-5` esc. 4 | rojo: módulo `./cliente` inexistente | PASA |
| TC-37 | `src/api/cliente.test.ts` · `tkt008_car3 · nadie lee la cookie` | rechazo | `CA-R3`, `RNF-02` | rojo: módulo `./cliente` inexistente | PASA |
| TC-38 | `src/api/cliente.test.ts` · `tkt008_ca07_esc07 · 204` | feliz | `CA-7` esc. 7 | rojo: módulo `./cliente` inexistente | PASA |
| TC-M6 | `scripts/tipos.test.ts` · `tkt008_ca02_esc05 · edición de igual longitud` | rechazo (una letra por otra, sin cambiar la longitud, también difiere) | `CA-2` esc. 5 | nace en verde, por diseño: MT-6 sobrevivía a TC-15 y lo pone en rojo | PASA |
| TC-H1 | `src/api/cliente.test.ts` · `tkt008_ca03_esc01 · el token fallido no se cachea` | rechazo (`GET /sesion/csrf` falla y la siguiente mutación vuelve a pedirlo) | `CA-3`, `PA-T9` | nace en verde, por diseño: hueco de la fila 6; MT-A1 lo pone en rojo | PASA |
| TC-H2 | `src/api/cliente.test.ts` · `tkt008_ca04_esc01 · exigir lanza FalloApi con el error normalizado` | feliz y rechazo (`FalloApi` con el error íntegro) | `CA-4` esc. 1 | nace en verde, por diseño: hueco de la fila 6; MT-A2 y MT-A2b lo ponen en rojo | PASA |
| TC-F1a | `scripts/eslint-reglas.test.ts` · `tkt008_car3 · TC-F1a · document["cookie"]` | rechazo (`src/modulos/x.ts` y el módulo de dinero) | `CA-R3`, `RNF-02`, F001 | rojo: `lintText` sin mensajes (`expected [] to have a length of 1`) | PASA |
| TC-F1b | `scripts/eslint-reglas.test.ts` · `tkt008_car3 · TC-F1b · window.document.cookie` | rechazo (ídem) | `CA-R3`, `RNF-02`, F001 | rojo: `lintText` sin mensajes | PASA |
| TC-F1c | `scripts/eslint-reglas.test.ts` · `tkt008_car3 · TC-F1c · const { cookie } = document` | rechazo (ídem) | `CA-R3`, `RNF-02`, F001 | rojo: `lintText` sin mensajes | PASA |
| TC-F1d | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc03 · TC-F1d · globalThis.Number y window.Number` | rechazo (líneas 1 y 2), con control de exención en el módulo de dinero | `CA-13` esc. 3, F001 | rojo: `expected [] to deeply equal [ 1, 2 ]` | PASA |
| TC-F1e | `scripts/eslint-reglas.test.ts` · `tkt008_ca13_esc03 · TC-F1e · import() dinámico de decimal.js` | rechazo (cualquiera de las dos reglas de ESLint), con control de exención en el módulo de dinero | `CA-13` esc. 3, `M9`, F001 | rojo: `lintText` sin mensajes | PASA |
| TC-F1f | `scripts/eslint-reglas.test.ts` · `tkt008_car3 · TC-F1f · control: document.title no se rechaza` | feliz (control: la regla no prohíbe `document` entero) | `CA-R3`, F001 | nace en verde, por diseño: es el control de TC-F1a a TC-F1c | PASA |
| TC-F4 | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca13_esc02 · TC-F4 · un negativo que redondea a cero no lleva signo` | rechazo (`"-0.0040"` → `$0.00`; `"-0.0010"` → `0.00`) | `CA-13`, F004 | rojo: `expected '-$0.00' to be '$0.00'` | PASA |
| TC-F5a | `src/api/cliente.test.ts` · `tkt008_ca04_esc02 · TC-F5a · el token con 500 es GENERICO con su correlación` | rechazo (`GENERICO`, estado 500, mensaje y `correlacion_id`; no se envía el `POST`) | `CA-4` esc. 2, F005 | rojo: `error: { tipo: 'RED' }` en lugar de `GENERICO` | PASA |
| TC-F5b | `src/api/cliente.test.ts` · `tkt008_ca04_esc02 · TC-F5b · el token con 200 y sin campo token es GENERICO` | rechazo (`GENERICO`, estado 200; no se envía el `POST`) | `CA-4` esc. 2, F005 | rojo: `expected true to be false`: hoy el cliente da la mutación por buena y envía `X-CSRF-Token: undefined` | PASA |
| TC-F5c | `src/api/cliente.test.ts` · `tkt008_ca04_esc03 · TC-F5c · un fallo de red al pedir el token sigue siendo RED` | rechazo (`HttpResponse.error()` de MSW) | `CA-4` esc. 3, F005 | nace en verde, por diseño: el caso real de `RED` que la corrección no debe romper | PASA |
| TC-R1a | `scripts/tipos.test.ts` · `tkt008_ca02_esc01 · TC-R1a · generar escribe los dos archivos con su contenido generado` | feliz (`escribirArchivo` recibe `ARCHIVO_SERVIDOR` y `ARCHIVO_CONTRATO_ERROR` con su contenido; salida 0 y `Tipos generados: …`) | `CA-2` esc. 1, C001 | nace en verde, por diseño: hueco de la revisión; MT-R1 lo pone en rojo | PASA |
| TC-R1b | `scripts/tipos.test.ts` · `tkt008_ca02_esc01 · TC-R1b · si escribir un archivo falla, sale con 2 y lo dice` | rechazo (`escribirArchivo` lanza: salida 2 y `No se pudieron generar los tipos`) | `CA-2` esc. 1, C001 | nace en verde, por diseño: MT-R1, MT-R2 y MT-R2b lo ponen en rojo | PASA |
| TC-R1c | `scripts/tipos.test.ts` · `tkt008_ca02_esc04 · TC-R1c · O4 · las claves del subconjunto salen en orden alfabético` | feliz (borrador con los esquemas en orden inverso; las claves salen en la lista literal alfabética) | `CA-2` esc. 4, O4 | nace en verde, por diseño: MT-R3 lo pone en rojo | PASA |
| TC-R1d | `src/api/cliente.test.ts` · `tkt008_ca04_esc02 · TC-R1d · un Error que no es de red es GENERICO con estado 0` | rechazo (`Error` que no es `TypeError` ni `AbortError`) | `CA-4` esc. 2, C002 | nace en verde, por diseño: MT-R6 lo pone en rojo | PASA |
| TC-R1e | `src/api/cliente.test.ts` · `tkt008_ca04_esc02 · TC-R1e · un TypeError de código propio, no de fetch, no es RED` | rechazo (un token con `\n` en medio hace que `headers.set` lance `TypeError`; sale `GENERICO` con `estado: 0`) | `CA-4` esc. 2 y 3, C002 | rojo: `error: { tipo: 'RED' }` en lugar de `GENERICO` | PASA |
| TC-R1f | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca08_esc05 · TC-R1f · un importe <Infinity, NaN, -Infinity> no se presenta` | rechazo (tres tests con `Decimal` no finito: `formatearImporte` da `null`) | `CA-8` esc. 5, C003, F101 | rojo: `expected '$∞' to be null` | PASA |
| TC-R1g | `src/compartido/dinero/dinero.test.ts` · `tkt008_ca08_esc05 · TC-R1g · una cantidad <Infinity, NaN, -Infinity> no se presenta` | rechazo (tres tests: `formatearCantidad` da `null`, con y sin unidad) | `CA-8` esc. 5, C003, F101 | rojo: `expected '∞' to be null` | PASA |

TC-17 y TC-18 nacieron en verde, como prevé el diseño. El mutante que los pone en rojo se registra en «Cierre de la fila 3»: ninguno de MT-1 a MT-14 lo hace.

TC-M6, TC-H1 y TC-H2 los añade la fila 7 (`M` por mutación, `H` por hueco de cobertura). No están en la tabla del diseño: sus números `TC-39` en adelante son de TKT-008b. La columna «Al cerrar» recoge la suite de la fila 7: 40 tests en verde en 7 archivos.

TC-H1 cambia en el ciclo de corrección 1 (F005): su aserción sobre el fallo del token pasa de `RED` a `GENERICO` con `estado: 500`. Lo demás —el token fallido no se cachea y la siguiente mutación vuelve a pedirlo— no cambia. La columna «Al cerrar» de los TC-F queda en `PASA` tras el verde de la corrección (50 tests en verde).

TC-R1a a TC-R1g los añade el ciclo de corrección de `/sdd-revisar` (`R1` por revisión, ciclo 1). Los nombres que cambian en esta tabla —TC-11, TC-16, TC-23, TC-26, TC-32, TC-35, TC-H1 y TC-F4— son la misma cobertura con otra estructura (C004 y C006); el detalle viejo y nuevo está en «Revisión · ciclo de corrección 1». La columna «Al cerrar» de TC-R1e, TC-R1f y TC-R1g pasó a `PASA` con el verde de la revisión, ciclo 1 (78 de 78).

### Ciclo TDD por fila

La rama `tkt-008a-andamiaje-cliente` sale de `Produccion` (`669ae61`), por decisión del usuario del 2026-10-26.

#### Fila 1 · Andamiaje

**Rojo.** Antes de instalar nada, desde `frontend/`, con Node 24.22.0 y npm 11.19.1, el tester ejecutó los dos comandos. El `package.json` solo tiene los scripts `lint` y `typecheck`, así que npm no encuentra ninguno de los dos. Es el rojo de infraestructura que el diseño prevé para esta fila.

```text
$ npm run dev
npm error Missing script: "dev"
npm error
npm error To see a list of scripts, run:
npm error   npm run
npm error A complete log of this run can be found in: C:\Users\romeo\AppData\Local\npm-cache\_logs\2026-10-27T01_10_35_641Z-debug-0.log
(código de salida 1)

$ npm test
npm error Missing script: "test"
npm error
npm error To see a list of scripts, run:
npm error   npm run
npm error A complete log of this run can be found in: C:\Users\romeo\AppData\Local\npm-cache\_logs\2026-10-27T01_10_36_266Z-debug-0.log
(código de salida 1)
```

TC-01 y TC-02 están escritos en `frontend/scripts/esqueleto.test.ts` y no pueden correr todavía, porque `vitest` no está instalado. Nacen en verde por diseño tras la instalación de la fila 1, porque comprueban archivos que la propia fila crea. Su prueba de que dependen de algo son MT-1 (un `^` delante de una versión de `package.json`, que pone en rojo TC-01) y MT-2 (`changeOrigin: true` en `vite.config.ts`, que pone en rojo TC-02), en la fila 7.

**Verde.** Desde `frontend/`, con Node 24.22.0 y npm 11.19.1. Los paquetes se instalaron uno a uno con `npm install -E` (`-D` en los de desarrollo, para que caigan en `devDependencies`). Después se borró `node_modules` y se ejecutó `npm ci`. Salida real, resumida:

```text
$ npm ci                      (desde cero, tras borrar node_modules)
added 570 packages, and audited 571 packages in 23s
found 0 vulnerabilities
(código de salida 0)

$ npm run build
vite v8.3.5 building client environment for production...
✓ 14 modules transformed.
dist/index.html                  0.31 kB │ gzip:  0.23 kB
dist/assets/index-CeNtAqIq.js  219.56 kB │ gzip: 68.61 kB
✓ built in 77ms
(código de salida 0)

$ npm run lint                (sin mensajes de ESLint; código de salida 0)
$ npm run typecheck           (tsc --noEmit sin errores; código de salida 0)

$ npm test
 Test Files  1 passed (1)
      Tests  2 passed (2)
(código de salida 0; TC-01 y TC-02 en verde)

$ npm run dev                 VITE v8.3.5 ready · Local: http://localhost:5173/
$ curl -i http://localhost:5173/api/v1/sesion/csrf      (backend en 127.0.0.1:8000)
HTTP/1.1 200 OK
set-cookie: cimenta_csrf=<token>; Path=/; SameSite=lax; Secure
{"token":"<token>"}
```

La petición de CSRF pasa por el *proxy* de Vite (`/api` a `127.0.0.1:8000`) y devuelve el token en el cuerpo y la cookie `cimenta_csrf`. Se pidió `GET /` del dev server, que responde `200`. Comprobaciones de la fila: `npm ci` desde cero en verde; ningún `^` ni `~` en `package.json` (búsqueda sin coincidencias); `frontend/scripts/esqueleto.test.ts` sin cambios. La base se levantó con `docker compose up -d db`; la petición de CSRF no la consulta, y no se verificó la migración con `alembic`. Los procesos de Vite, del backend y el contenedor de la base se detuvieron al terminar.

**Refactor.** Ninguno que aplicar: el código de la fila es el literal de «Configuración» del diseño y no hay duplicación que limpiar. Tras cada cambio se volvió a ejecutar la suite.

**Tests devueltos al tester.** Ninguno. TC-01 y TC-02 se ejecutaron tal como llegaron y no se modificaron.

**Versiones exactas en `package.json`.** Resultado de `npm install -E`, con la mayor del diseño como criterio:

| Paquete | Versión exacta | Bloque |
|---|---|---|
| `react` | 19.3.1 | dependencies |
| `react-dom` | 19.3.1 | dependencies |
| `react-router` | 7.18.4 | dependencies |
| `@tanstack/react-query` | 5.105.0 | dependencies |
| `openapi-fetch` | 0.17.0 | dependencies |
| `react-hook-form` | 7.91.0 | dependencies |
| `zod` | 4.6.7 | dependencies |
| `@hookform/resolvers` | 5.9.2 | dependencies |
| `decimal.js` | 10.6.0 | dependencies |
| `vite` | 8.3.5 | devDependencies |
| `@vitejs/plugin-react` | 6.1.2 | devDependencies |
| `tailwindcss` | 4.3.3 | devDependencies |
| `@tailwindcss/vite` | 4.3.3 | devDependencies |
| `vitest` | 5.0.5 | devDependencies |
| `jsdom` | 30.1.3 | devDependencies |
| `@testing-library/react` | 16.3.3 | devDependencies |
| `@testing-library/user-event` | 14.6.8 | devDependencies |
| `@testing-library/jest-dom` | 6.9.1 | devDependencies |
| `msw` | 2.15.0 | devDependencies |
| `@playwright/test` | 1.64.1 | devDependencies |
| `openapi-typescript` | 7.13.0 | devDependencies |
| `yaml` | 2.9.1 | devDependencies |
| `@types/react` | 19.3.0 | devDependencies |
| `@types/react-dom` | 19.3.0 | devDependencies |
| `@types/node` | 24.19.2 | devDependencies |
| `eslint-plugin-react-hooks` | 7.1.1 | devDependencies |
| `@eslint/js` | 10.0.1 | devDependencies (sin cambio) |
| `eslint` | 10.0.1 | devDependencies (sin cambio) |
| `typescript` | 6.0.3 | devDependencies (sin cambio) |
| `typescript-eslint` | 8.71.2 | devDependencies (sin cambio) |
| `shadcn` | 4.22.1 | dependencies (lo añade el CLI) |
| `@base-ui/react` | 1.9.0 | dependencies (lo añade el CLI) |
| `class-variance-authority` | 0.7.1 | dependencies (lo añade el CLI) |
| `cn` | 0.5.0 | dependencies (lo añade el CLI) |
| `lucide-react` | 1.61.0 | dependencies (lo añade el CLI) |
| `tw-animate-css` | 1.4.0 | dependencies (lo añade el CLI) |
| `@fontsource-variable/geist` | 5.3.0 | dependencies (lo añade el CLI) |

`overrides`: `{ "openapi-typescript": { "typescript": "$typescript" } }`.

#### Fila 2 · Reglas de ESLint

**Rojo.** El tester escribió `frontend/scripts/eslint-reglas.test.ts` con TC-04 a TC-10 y lo ejecutó desde `frontend/` con Node 24.22.0, tal como indica el diseño para la fila: `npx vitest run scripts/eslint-reglas.test.ts`. El proyecto `herramientas` de Vitest ya existe en `vite.config.ts` y recoge el archivo (`|herramientas|`). `eslint.config.js` solo tiene el bloque base, sin `no-restricted-syntax` ni `no-restricted-imports`, así que `lintText` no devuelve ningún mensaje de esas reglas y las siete pruebas fallan en la primera afirmación, no por un error de importación o de entorno. Salida real, recortada a lo relevante:

```text
$ npx vitest run scripts/eslint-reglas.test.ts
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ❯ |herramientas| scripts/eslint-reglas.test.ts (7 tests | 7 failed) 488ms
   ❯ TKT-008 · reglas de ESLint del cliente (7)
     × tkt008_ca13_esc03 · Number en src 469ms
     × tkt008_ca13_esc03 · las demás conversiones 6ms
     × tkt008_ca13_esc03 · el módulo de dinero está exento 2ms
     × tkt008_car3 · document.cookie 2ms
     × tkt008_ca13_esc04 · Zod solo en formularios 3ms
     × tkt008_ca13_esc03 · decimal.js solo en su módulo 2ms
     × tkt008_car1 · TSX 3ms

 FAIL  ... > tkt008_ca13_esc03 · Number en src
AssertionError: expected [] to have a length of 1 but got +0
 ❯ scripts/eslint-reglas.test.ts:30:22
 FAIL  ... > tkt008_ca13_esc03 · las demás conversiones
AssertionError: expected [] to deeply equal [ 1, 2, 3, 4, 5, 6 ]
 ❯ scripts/eslint-reglas.test.ts:48:53
 FAIL  ... > tkt008_ca13_esc03 · el módulo de dinero está exento
AssertionError: expected [] to have a length of 1 but got +0
 ❯ scripts/eslint-reglas.test.ts:60:19        (control fuera del módulo de dinero)
 FAIL  ... > tkt008_car3 · document.cookie
AssertionError: src/app/x.ts: expected [] to have a length of 1 but got +0
 ❯ scripts/eslint-reglas.test.ts:72:30
 FAIL  ... > tkt008_ca13_esc04 · Zod solo en formularios
AssertionError: expected [] to have a length of 1 but got +0
 ❯ scripts/eslint-reglas.test.ts:83:23
 FAIL  ... > tkt008_ca13_esc03 · decimal.js solo en su módulo
AssertionError: expected [] to have a length of 1 but got +0
 ❯ scripts/eslint-reglas.test.ts:97:23
 FAIL  ... > tkt008_car1 · TSX
AssertionError: expected [] to have a length of 1 but got +0
 ❯ scripts/eslint-reglas.test.ts:112:22

 Test Files  1 failed (1)
      Tests  7 failed (7)
   Start at  19:19:36
   Duration  709ms (tests 81%, import 15%, transform 3%)
(código de salida 1)
```

Comprobación de que el rojo es por la regla ausente y no por un archivo ignorado: una sonda con `lintText('export const a = Number("1"); const b = 1;', { filePath: "src/modulos/compras/x.ts" })` devuelve solo `@typescript-eslint/no-unused-vars` en la línea 1, es decir, ESLint sí analiza el archivo, y `no-restricted-syntax` no aparece. `npm run typecheck` y `eslint scripts/eslint-reglas.test.ts` terminan con código 0 sobre el archivo nuevo.

**Notas del tester para el desarrollador.**

- Ninguna prueba nació en verde. El diseño pone TC-06 como caso feliz («sin errores»), que con la configuración actual pasaría de forma vacía. Por eso TC-06 incluye un control: el mismo código en `src/modulos/compras/x.ts` debe producir un error de `no-restricted-syntax`, y solo después se comprueba que `src/compartido/dinero/x.ts` no tiene errores de ninguna regla. TC-08 y TC-09 ya unen rechazo y exención en la misma prueba.
- Los rechazos filtran por `ruleId` (`no-restricted-syntax` o `no-restricted-imports`), porque `@typescript-eslint/no-unused-vars` y otras reglas del bloque base también emiten mensajes. Los casos de exención comprueban que no hay **ningún** error (gravedad 2) de cualquier regla, así que el código de prueba usa `export` para no activar `no-unused-vars`.
- Los mensajes se comprueban contra el literal del diseño: `Number`, `parseFloat`, `parseInt` y `+` citan «regla 1» (`/regla 1|RNF-02|CA-13/`); `document.cookie` cita `RNF-02`; Zod cita `CA-13`. El mensaje de `decimal.js` del diseño («decimal.js solo se importa en src/compartido/dinero (M9)») **no cita** ninguna de las tres, y TC-09 solo exige que mencione `decimal.js`. Si se quiere que cite `CA-13`, hay que cambiarlo en el diseño y en la prueba; el desarrollador no debe cambiar el mensaje por su cuenta.
- Ningún archivo de producción se tocó en esta fila: `eslint.config.js` sigue como lo dejó la fila 1.

**Verde.** El único cambio de la fila es `frontend/eslint.config.js`, que pasa a ser el literal de «Configuración» del diseño. Añade `eslint-plugin-react-hooks` (ya instalado en 7.1.1), con `rules-of-hooks` y `exhaustive-deps` en `error`; un bloque de `src/**` con `no-restricted-syntax` (números y `document.cookie`) y `no-restricted-imports` (`decimal.js` y `zod`); un bloque de `src/compartido/dinero/**` que quita la prohibición de números y de `decimal.js`, pero no la de `document.cookie` ni la de Zod; y un bloque de formularios y pruebas que solo deja libre Zod. Los mensajes son los del diseño, sin cambios. No se tocó ningún test ni ningún archivo de `src/`.

Salida real, resumida:

```text
$ npx vitest run scripts/eslint-reglas.test.ts
 Test Files  1 passed (1)
      Tests  7 passed (7)
(código de salida 0; TC-04 a TC-10 en verde)

$ npm test
 Test Files  2 passed (2)
      Tests  9 passed (9)
(código de salida 0; TC-01 y TC-02 siguen en verde)

$ npm test -- --project herramientas
 Test Files  2 passed (2)
      Tests  9 passed (9)
(código de salida 0; la opción --project no filtró en vitest 5 y corrió las dos cabeceras de prueba)

$ npm run lint
(sin mensajes de ESLint en el árbol real, incluidos src/components/ui/ y src/lib/; código de salida 0)

$ npm run typecheck
(tsc --noEmit sin errores; código de salida 0)

$ npm run build
✓ 14 modules transformed.
dist/assets/index-CeNtAqIq.js  219.56 kB │ gzip: 68.61 kB
✓ built in 77ms
(código de salida 0)
```

**Refactor.** Ninguno. El bloque es el literal del diseño, con las constantes `MENSAJE_NUMERO`, `NUMERO`, `COOKIE`, `DECIMAL` y `ZOD` ya factorizadas. Tras el cambio se ejecutó la suite completa y no hubo más ediciones.

**Tests devueltos al tester.** Ninguno. TC-04 a TC-10 se ejecutaron tal como llegaron. TC-09 exige solo que el mensaje de `decimal.js` mencione `decimal.js`, y lo cumple; el mensaje del diseño no cita `CA-13`, pero el test no lo pide, así que no es un fallo del test y se deja como está.

**Ajustes.** Ninguno en la fila. El lint del árbol real pasó con el código que copió shadcn en `src/components/ui/` y `src/lib/`, así que no fue necesario tocar ese código ni añadir `ignores`.

#### Fila 3 · Generación de tipos

**Rojo.** El tester escribió `frontend/scripts/tipos.test.ts` con TC-11 a TC-16 y lo ejecutó desde `frontend/` con Node 24.22.0: `npx vitest run scripts/tipos.test.ts`. El archivo importa de `./tipos.ts`, que no existe, así que la suite entera falla al resolver el módulo y ningún test llega a correr. Es el rojo que el diseño prevé para la fila («módulo inexistente `scripts/tipos.ts`»). Salida real, recortada a lo relevante:

```text
$ npx vitest run scripts/tipos.test.ts
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ❯ |herramientas| scripts/tipos.test.ts (0 test)

 FAIL  |herramientas| scripts/tipos.test.ts [ scripts/tipos.test.ts ]
Error: Cannot find module './tipos.ts' imported from D:/Documentos/LIDR/Proyecto Final/frontend/scripts/tipos.test.ts
 ❯ scripts/tipos.test.ts:4:1

 Test Files  1 failed (1)
      Tests  no tests
   Start at  19:23:02
   Duration  143ms (worker 95%, environment 5%)
(código de salida 1)
```

Comprobaciones del rojo: `eslint scripts/tipos.test.ts` termina con código 0. `tsc --noEmit` solo se queja de `TS2307` (módulo `./tipos.ts` inexistente) y de los `TS7006` de los parámetros de las funciones inyectadas, que se infieren de las firmas de `tipos.ts` y desaparecen cuando el módulo exista. No hay errores de sintaxis ni de entorno: `yaml` está instalado (2.9.1) y el borrador `docs/api/openapi.yaml` existe.

**Notas del tester para el desarrollador.**

- Las dependencias se inyectan, como prevé el diseño: `exportarOpenapiPublicado(ejecutar)` y `principal(argumentos, { exportar, leerBorrador, leer, escribirArchivo, escribir, escribirError })`. Ningún test invoca `uv`; `npm test` no depende de él.
- El publicado de prueba es un OpenAPI mínimo en memoria con `/api/v1/sesion` y un esquema propio; el borrador es el real, leído con `yaml`. `generarArchivos` tiene que aceptar ese publicado sin conexión ni servidor.
- TC-11 incluye el rechazo en la misma prueba: se le quita `Accion` al borrador y `subconjuntoContratoError` debe lanzar nombrándolo.
- TC-16 cubre los cuatro códigos de salida de la tabla: 2 (la exportación lanza), 1 (`Difiere: <ruta>`), 0 (`Tipos al día.`) y 3 (argumento desconocido, sin llamar a `exportar`). El modo `generar` (escritura de los archivos con `escribirArchivo`) no tiene test propio en el plan y queda sin cobertura unitaria; lo ejercita la verificación de la fila (`npm run tipos:generar` dos veces y `git diff --exit-code`).
- TC-17 y TC-18 (`src/api/tipos.test.ts`) se escriben después de generar los archivos, según el diseño.
- Ningún archivo de producción se tocó en esta fila.

**Verde.** `frontend/scripts/tipos.ts` se escribió en una sola pasada, porque los seis tests comparten el mismo módulo y ninguno tiene sentido sin él. Después se ejecutó cada test aislado con `-t` y el conjunto entero. Ningún test se modificó. Salida real, resumida:

```text
$ npx vitest run scripts/tipos.test.ts
 Test Files  1 passed (1)
      Tests  6 passed (6)
(código de salida 0; TC-11 a TC-16 en verde)

$ npx vitest run scripts/tipos.test.ts -t "<nombre>"     (uno por test, seis ejecuciones)
      Tests  1 passed | 5 skipped (6)                    (subconjunto cerrado, cabecera provisional, determinista, desfase, edición a mano, exportación sin uv)

$ npm run tipos:generar                                  (uv y uv sync --locked ya disponibles)
Tipos generados: src/api/generado/servidor.ts, src/api/generado/contrato-error.provisional.ts
(código de salida 0; unos 2 s)

$ wc -l src/api/generado/*.ts
  241 src/api/generado/servidor.ts
  276 src/api/generado/contrato-error.provisional.ts
```

Comprobación del contenido generado: `contrato-error.provisional.ts` no contiene `UsuarioActual` ni `Insumo`; su única línea con `number` declara `espera_maxima_ms` o `reintentar_en_s` (TC-18). `servidor.ts` contiene una línea con `number`, la de `ValidationError.loc`, prevista en el diseño. Los dos archivos terminan en un único `\n`, sin CRLF y sin BOM.

**Verificación de la fila.**

Segunda generación, con los hashes SHA-256 de antes y de después:

```text
$ sha256sum src/api/generado/*.ts      (antes de la segunda generación)
70261e0d638fe3c08bc54b4ccd395596e819e9a939acc7fe663efb4d108f799e *src/api/generado/contrato-error.provisional.ts
67757947cbc4ac8875f538a85f9642bb0b7bcccb676110d28d8cfb9b0af2d8f1 *src/api/generado/servidor.ts

$ npm run tipos:generar
Tipos generados: src/api/generado/servidor.ts, src/api/generado/contrato-error.provisional.ts
(código de salida 0)

$ sha256sum src/api/generado/*.ts      (después)   → idéntico al de antes; diff exit 0

$ git diff --exit-code -- src/api/generado
(sin salida; código de salida 0). Los archivos están sin seguimiento (`?? src/api/generado/`), así que git no compara nada: la comparación real son los hashes.
```

```text
$ npm run tipos:verificar
Tipos al día.
(código de salida 0)

$ (añadir la línea «// edición a mano» al final de servidor.ts, con copia previa)
$ npm run tipos:verificar
Difiere: src/api/generado/servidor.ts
Ejecuta npm run tipos:generar y versiona el resultado.
(código de salida 1)

$ (restaurar servidor.ts desde la copia previa)
SHA-256 67757947cbc4ac8875f538a85f9642bb0b7bcccb676110d28d8cfb9b0af2d8f1, igual que antes de la edición
$ npm run tipos:verificar
Tipos al día.
(código de salida 0)
```

Gates de la fila, desde `frontend/`:

```text
$ npm run lint          (eslint . sin mensajes; código de salida 0)
$ npm run typecheck     (tsc --noEmit sin errores; código de salida 0)
$ npm test
 Test Files  3 passed (3)
      Tests  15 passed (15)
(código de salida 0; los 9 anteriores y TC-11 a TC-16)
$ npm run build
✓ 14 modules transformed.
dist/assets/index-CeNtAqIq.js  219.56 kB │ gzip: 68.61 kB
✓ built in 78ms
(código de salida 0)
```

**Refactor.** Ninguno. No hubo cambios entre el verde y la verificación: la suite y el resto de gates se ejecutaron sobre el mismo código. `esDocumento`, `esquemasDe` y `normalizar` ya concentran las comprobaciones repetidas.

**Tests devueltos al tester.** Ninguno de TC-11 a TC-16: se ejecutaron tal como llegaron y no se tocaron. **Pendientes:** TC-17 y TC-18 (`src/api/tipos.test.ts`). El diseño los escribe ahora que los archivos generados existen, y nacen en verde. Esta fila no los escribió, porque el encargo era el verde de TC-11 a TC-16 y las verificaciones. Por eso la fila queda `⚠ Ajustado` y no `✓ Hecho`.

#### Fila 3 · cierre (TC-17, TC-18)

`tester-frontend` escribió `frontend/src/api/tipos.test.ts`, que corre en el proyecto `cliente`. Sin tocar ningún archivo de producción ni los dos generados.

- **TC-17** (`tkt008_ca02_esc02 · el switch estrecha`). Una función `describirBloqueo` hace `switch (e.tipo)` sobre `ErrorBloqueo` y lee `e.regla`, `e.codigo` y `e.detalle.espera_maxima_ms` sin aserciones. Dentro de cada rama, `expectTypeOf(e)` comprueba que el tipo es exactamente el de ese esquema, y el `default` asigna a `never`. Los ocho `tipo` se comprueban como literales con `expectTypeOf<…["tipo"]>().toEqualTypeOf<"…">()`. Además corre tres objetos construidos con los tipos generados y comprueba lo que devuelve la función. `ErrorBloqueo` se compone en el test (`ErrorReglaNegocio | ErrorConflictoEstado | ErrorConcurrencia`): su definición real vive en `errores.ts`, que es la fila 5.
- **TC-18** (`tkt008_car3 · importes y cantidades como cadena`). `expectTypeOf` es `string` para `Importe`, `Cantidad`, `CantidadNoNegativa`, los cuatro campos de `ConsumidoDesglose`, los cinco campos de `DetalleExcedePresupuesto` (`presupuestado` y `consumido` con `NonNullable`, porque son opcionales), los cinco `cantidad_*` o `excedente` de `insumos[number]`, las cinco cantidades de `DetalleExcedeOrdenado["renglones"][number]` y el `saldo_pendiente` de `DetalleOrdenConSaldo["renglones_con_saldo"][number]`. Además lee `contrato-error.provisional.ts` como texto y exige que las únicas líneas con `number` sean `espera_maxima_ms?: number;` y `reintentar_en_s: number;`. No mira `servidor.ts`, donde `ValidationError.loc` lleva `(string | number)[]` a propósito (hallazgo M-1 del revisor de impacto). **Sin `ImporteNoNegativo`**: véase «Ajustes».
- **Qué ejecuta cada comando.** `expectTypeOf` no hace nada en ejecución, así que `npm test` solo ejercita las aserciones normales (TC-17: los tres valores de `describirBloqueo`; TC-18: la lectura de texto). Las aserciones de tipo las comprueba `npm run typecheck`, que compila el archivo porque `tsconfig.json` incluye `src`. El diseño ya lo anota («lo prueba `npm run typecheck`»): una regresión de tipos no pone en rojo `npm test`, solo `typecheck`.

Salida real, desde `frontend/`:

```text
$ npx vitest run src/api/tipos.test.ts
 Test Files  1 passed (1)
      Tests  2 passed (2)
(código de salida 0)

$ npx vitest run scripts src/api
 Test Files  4 passed (4)
      Tests  17 passed (17)
(código de salida 0; los 15 anteriores y TC-17 y TC-18)

$ npm run typecheck    (tsc --noEmit sin errores sobre src/api/tipos.test.ts; código de salida 0)
$ npx eslint src/api/tipos.test.ts    (sin mensajes; código de salida 0)
```

**Mutantes.** Los dos tests nacen en verde, así que hay que demostrar que pueden fallar. **Ninguno de MT-1 a MT-14 los pone en rojo.** MT-6 toca `diferencias` y no cambia los tipos. MT-7 (sin recorrido recursivo) se aplicó y se regeneró: `npm run tipos:generar` falla antes de escribir nada (`Can't resolve $ref at #/components/schemas/ErrorValidacion/properties/correlacion_id`), los archivos generados quedan intactos y TC-17 y TC-18 siguen en verde (`Tests 2 passed (2)`, `typecheck` sin errores). Lo que sí los protege es `npm run tipos:verificar` más `typecheck`. Para no dejarlos sin prueba, se aplicaron cuatro mutantes **propuestos**, que no están en la tabla del diseño (llámense MT-T1 a MT-T4; el diseñador decide si pasan a la sección «Mutación»). Cada uno se aplicó solo sobre `src/api/generado/contrato-error.provisional.ts` y se revirtió con una copia previa:

| Mutante | Cambio | Resultado |
|---|---|---|
| MT-T1 | `Importe: string;` por `Importe: number;` | `npm run typecheck` falla en `tipos.test.ts` (líneas 80, 87, 88, 89 y más): `TS2344 Type 'string' does not satisfy the constraint '"Expected: string, Actual: number"'`. TC-18 en rojo |
| MT-T2 | `tipo: "REGLA_NEGOCIO";` por `tipo: string;` | `typecheck` falla en `tipos.test.ts` (líneas 24 a 28): `TS2344` (`Expected: literal string: CONFLICTO, Actual: string`) y `TS2339 Property 'codigo' does not exist`. TC-17 en rojo: el `switch` ya no estrecha |
| MT-T3 | `folio_orden: string;` por `folio_orden: number;` en `DetalleExcedeOrdenado` | `npx vitest run src/api/tipos.test.ts`: `Tests 1 failed \| 1 passed (2)`, `AssertionError: expected [ 'espera_maxima_ms?: number;', …(3) ] to deeply equal [ 'espera_maxima_ms?: number;', …(1) ]`. TC-18 en rojo por su comprobación de texto; los tipos no lo ven, porque ese campo no es una cifra |
| MT-T4 | `cantidad_disponible` de `insumos[number]` de `Cantidad` a `number` | `typecheck` falla en `tipos.test.ts` línea 102: `TS2344 … "Expected: string, Actual: number"`. TC-18 en rojo |

Tras revertir, el SHA-256 del provisional empieza por `70261e0d638fe3c0`, igual que el registrado en la verificación de la fila; `tipos.ts` y `servidor.ts` también quedaron como estaban tras el experimento de MT-7 y `npm run tipos:verificar` devuelve `Tipos al día.`.

**Estado de la fila 3.** TC-17 y TC-18 cierran con una sola desviación: la ausencia de `ImporteNoNegativo` en TC-18, registrada en «Ajustes». La marca de la fila (`⚠ Ajustado`) queda como está: la decide el orquestador. El orquestador la confirma como `⚠ Ajustado` y resuelve la desviación en «Ajustes».

#### Fila 4 · Dinero

**Rojo.** `tester-frontend` escribió `frontend/src/compartido/dinero/dinero.test.ts` con TC-19 a TC-25 y lo ejecutó desde `frontend/` con Node 24.22.0: `npx vitest run src/compartido/dinero`. El archivo importa `Decimal`, `aDecimal`, `enteroNoNegativo`, `formatearCantidad` y `formatearImporte` de `./dinero`, que no existe, así que Vite no resuelve el import y ningún test llega a correr. Es el rojo que el diseño prevé para la fila («módulo inexistente»). Salida real, recortada a lo relevante:

```text
$ npx vitest run src/compartido/dinero
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 FAIL  |cliente| src/compartido/dinero/dinero.test.ts [ src/compartido/dinero/dinero.test.ts ]
Error: Failed to resolve import "./dinero" from "src/compartido/dinero/dinero.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/Documentos/LIDR/Proyecto Final/frontend/src/compartido/dinero/dinero.test.ts:2:89
  1  |  import { describe, expect, test } from "vitest";
  2  |  import { Decimal, aDecimal, enteroNoNegativo, formatearCantidad, formatearImporte } from "./dinero";
     |                                                                                            ^

 Test Files  1 failed (1)
      Tests  no tests
   Start at  19:30:59
   Duration  716ms (environment 75%, setup 23%, transform 1%, worker 1%)
(código de salida 1)

$ npm test
 Test Files  1 failed | 4 passed (5)
      Tests  17 passed (17)
(código de salida 1: el archivo nuevo falla y los otros cuatro siguen en verde)
```

Comprobaciones del rojo: `eslint src/compartido/dinero/dinero.test.ts` termina con código 0 (el test importa `Decimal` de `./dinero`, no de `decimal.js`, y no usa `Number`). `npm run typecheck` solo devuelve `src/compartido/dinero/dinero.test.ts(2,90): error TS2307: Cannot find module './dinero'`, el mismo motivo: ningún error de sintaxis ni de entorno. `npm run lint` termina con código 0. Como el módulo no existe, no se pudo ejecutar contra él: se comprobaron las cifras esperadas con una sonda fuera del repositorio que copia la lógica literal del diseño sobre `decimal.js` e `Intl`, y da `$0.30`, `$1,234.57`, `1234.5650`, `$12,345,678,901,234.57`, `-$3,000.00`, `100.00 PZA`, `1,234.50` y `null` para las seis cifras inválidas. Con `Number(valor).toFixed(2)` el importe grande da `$12,345,678,901,234.56`, que es lo que TC-21 detecta.

**Notas del tester para el desarrollador.**

- Las pruebas importan `Decimal` del módulo, no de `decimal.js`: `eslint.config.js` prohíbe ese import fuera de `src/compartido/dinero` y, por el último bloque de configuración, también en el propio archivo de pruebas de esa carpeta. `Decimal` tiene que exportarse como valor y como tipo, como en el literal del diseño, porque TC-19 usa `toBeInstanceOf(Decimal)` y un auxiliar tipado `Decimal`.
- TC-19 llama a `formatearImporte` con una instancia de `Decimal`, no con una cadena: la firma es `string | Decimal`.
- TC-22 y TC-25 recorren sus cifras en un bucle con el valor en el mensaje de cada `expect`, para que un fallo diga qué cifra lo causó. Siguen siendo un test cada uno, como en el plan.
- TC-23 y TC-21 dependen del formato `es-MX` de `Intl`: se comprobaron con Node 24.22.0 (ICU completa). Una compilación de Node con ICU reducida los pondría en rojo por el formato, no por el código.
- Ningún archivo de producción se tocó en esta fila.

**Verde.** `desarrollador-react` (haiku) escribió `frontend/src/compartido/dinero/dinero.ts` con el literal de «Frontend · dinero» del diseño. Es el único módulo de `src/` que importa `decimal.js`; el redondeo es `ROUND_HALF_UP` y solo se aplica en `aDosDecimales`, al presentar; el formato va por `Intl.NumberFormat("es-MX")` desde la cadena ya redondeada, nunca desde un `number`. No hay `Number(...)`, `parseFloat` ni `toFixed` sobre `Number`. El literal se escribió completo de una vez y las siete pruebas pasaron en la primera ejecución: no hubo pasos intermedios de «una a una» que registrar. Salida real:

```text
$ npx vitest run src/compartido/dinero --reporter=verbose
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca13_esc01 · suma exacta 2ms
 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca13_esc02 · redondeo al presentar 0ms
 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca13_esc02 · sin pasar por number 0ms
 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca08_esc05 · cifra inválida 0ms
 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca13 · negativo 0ms
 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca08_esc02 · cantidades 0ms
 ✓ |cliente| src/compartido/dinero/dinero.test.ts > TKT-008 · dinero del cliente > tkt008_ca09_esc02 · Retry-After 0ms

 Test Files  1 passed (1)
      Tests  7 passed (7)
   EXIT=0

$ npm run lint        → eslint .                    EXIT=0
$ npm run typecheck   → tsc --noEmit               EXIT=0
$ npm test            → Test Files 5 passed (5) · Tests 24 passed (24)   EXIT=0
$ npm run build       → vite build · ✓ built in 76ms                      EXIT=0
```

**Refactor.** Ninguno. El literal ya es mínimo y coincide con el diseño; no se cambió nada tras el verde. `Intl.StringNumericLiteral` compila con `lib` ES2023 y TypeScript 6.0.3, así que no hizo falta la alternativa `` `${number}` ``.

**Tests devueltos al tester.** Ninguno. TC-19 a TC-25 son coherentes con el diseño: las cifras esperadas coinciden con la salida real y no se tocó `dinero.test.ts`.

#### Fila 5 · Normalización del error

**Rojo.** `tester-frontend` escribió `frontend/src/api/errores.test.ts` con TC-26 a TC-29 y lo ejecutó desde `frontend/` con Node 24.22.0: `npx vitest run src/api/errores`. El archivo importa `normalizarError` de `./errores`, que no existe, así que Vite no resuelve el import y ningún test llega a correr. Es el rojo que el diseño prevé para la fila («módulo inexistente»). Salida real, recortada a lo relevante:

```text
$ npx vitest run src/api/errores
 ❯ |cliente| src/api/errores.test.ts (0 test)

 FAIL  |cliente| src/api/errores.test.ts [ src/api/errores.test.ts ]
Error: Failed to resolve import "./errores" from "src/api/errores.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/Documentos/LIDR/Proyecto Final/frontend/src/api/errores.test.ts:3:32
  1  |  import { describe, expect, test } from "vitest";
  2  |  import { normalizarError } from "./errores";
     |                                   ^

 Test Files  1 failed (1)
      Tests  no tests
   Start at  19:35:01
   Duration  718ms (environment 75%, setup 23%, transform 1%, worker 1%)
(código de salida 1)
```

Comprobaciones del rojo: `eslint src/api/errores.test.ts` termina con código 0. `npm run typecheck` solo devuelve `TS2307` (módulo `./errores` inexistente) y tres `TS7006` en los `map` de TC-29, que se infieren de la firma de `normalizarError` y desaparecen cuando el módulo exista. Ningún error de sintaxis ni de entorno.

**Notas del tester para el desarrollador.**

- `src/pruebas/cuerpos.ts`, que el diseño cita para TC-26, todavía no existe. Los ocho cuerpos se declaran dentro de `errores.test.ts`, cada uno con `satisfies` contra `components["schemas"]` de `contrato-error.provisional.ts`, de modo que cumplen el borrador por compilación y llevan todas las cifras como cadena (p. ej. `"12345678901234.5650"`). Cuando la fila de `cuerpos.ts` exista, se pueden sustituir sin cambiar las aserciones.
- El test importa solo `normalizarError` de `./errores`. Usa el discriminador y la unión `ErrorApi` que el diseño fija: `GENERICO` lleva `estado`, `mensaje` y `correlacion_id` (los dos últimos `null` si no son cadenas del cuerpo), y `CONCURRENCIA` añade `reintentar_tras_s` (2 con `Retry-After: 2`, `null` sin cabecera).
- TC-27 cubre además, por la regla de salida del diseño: un tipo del contrato con el código de estado equivocado (`SESION` con 500, `REGLA_NEGOCIO` con 422, `SESION` con 409) y un tipo válido sin `mensaje` de cadena, todos `GENERICO`. Es lo que pone en rojo el mutante MT-12.
- TC-26 compara el resultado completo con `toEqual`, de modo que cualquier campo perdido o reescrito (acciones, detalle) cae. Es lo que pone en rojo el mutante MT-11 (discriminador invertido).
- Ningún archivo de producción se tocó en esta fila.

**Verde.** `desarrollador-react` (haiku) escribió `frontend/src/api/errores.ts` con el literal de «Frontend · contrato de error» del diseño: los tipos del contrato tomados de `components["schemas"]` de `contrato-error.provisional.ts`, `ErrorConcurrencia` con `reintentar_tras_s`, `ErrorGenerico` y `ErrorRed`, la unión `ErrorApi`, `ESTADO_DE_TIPO`, `esObjeto` y `normalizarError`. El discriminador se comprueba con `Object.hasOwn` sobre `ESTADO_DE_TIPO` (no con `in`, que aceptaría `"toString"`), y `tipo` debe casar con el código de estado y `mensaje` ser cadena. Un `HTTPValidationError` (`{ detail: [...] }` con 422) cae en `GENERICO` con `estado: 422`, como pide el hallazgo M-1. `reintentar_tras_s` sale de `enteroNoNegativo(cabeceras.get("Retry-After"))`. Las dos aserciones (`as unknown as`) quedan en `normalizarError`, después del discriminador. No hay Zod ni esquema escrito a mano.

Los cuatro tests se pusieron en verde en la primera ejecución del módulo completo, no uno a uno: los cuatro son del mismo módulo y el literal del diseño los cubre todos. No hubo pasos intermedios que registrar. Salida real:

```text
$ npx vitest run src/api/errores --reporter=verbose
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ✓ |cliente| src/api/errores.test.ts > TKT-008 · normalización del error > tkt008_ca04_esc01 · cada tipo con sus campos 3ms
 ✓ |cliente| src/api/errores.test.ts > TKT-008 · normalización del error > tkt008_ca04_esc02 · fuera del contrato 1ms
 ✓ |cliente| src/api/errores.test.ts > TKT-008 · normalización del error > tkt008_ca04_esc02 · tipo desconocido 0ms
 ✓ |cliente| src/api/errores.test.ts > TKT-008 · normalización del error > tkt008_ca04_esc04 · acciones intactas 0ms

 Test Files  1 passed (1)
      Tests  4 passed (4)
(código de salida 0)

$ npm run lint        → eslint .                    EXIT=0
$ npm run typecheck   → tsc --noEmit               EXIT=0
$ npm test            → Test Files 6 passed (6) · Tests 28 passed (28)   EXIT=0
$ npm run build       → vite build · ✓ built in 76ms                      EXIT=0
```

**Refactor.** Ninguno. El literal ya es mínimo y coincide con el diseño; no se cambió nada tras el verde.

**Tests devueltos al tester.** Ninguno. TC-26 a TC-29 coinciden con el diseño: el `satisfies` de los ocho cuerpos compila contra el provisional, y las cifras como cadena se conservan intactas en el resultado.

#### Fila 6 · Cliente

**Rojo.** `tester-frontend` escribió `frontend/src/api/cliente.test.ts` con TC-30 a TC-38 y lo ejecutó desde `frontend/` con Node 24.22.0: `npx vitest run src/api/cliente`. El archivo importa `aplicarCsrf`, `crearClienteApi` y `pedir` de `./cliente`, que no existe, así que Vite no resuelve el import y ningún test llega a correr. Es el rojo que el diseño prevé para la fila («módulo inexistente»). Salida real, recortada a lo relevante:

```text
$ npx vitest run src/api/cliente
 RUN  v5.0.5 D:/Documentos/LIDR/Proyecto Final/frontend

 ❯ |cliente| src/api/cliente.test.ts (0 test)

 FAIL  |cliente| src/api/cliente.test.ts [ src/api/cliente.test.ts ]
Error: Failed to resolve import "./cliente" from "src/api/cliente.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/Documentos/LIDR/Proyecto Final/frontend/src/api/cliente.test.ts:5:71
  2  |  import { describe, expect, test, vi } from "vitest";
  3  |  import { servidorPruebas } from "@/pruebas/servidor";
  4  |  import { aplicarCsrf, crearClienteApi, pedir } from "./cliente";
     |                                                       ^

 Test Files  1 failed (1)
      Tests  no tests
   Start at  19:41:20
   Duration  747ms (environment 73%, setup 25%, transform 1%, worker 1%)
(código de salida 1)
```

Comprobaciones del rojo: `eslint src/api/cliente.test.ts` termina con código 0. `npm run typecheck` solo devuelve `TS2307` (módulo `./cliente` inexistente) y un `TS7031` en el `map` de TC-32, que se infiere de la firma de `pedir` y desaparece cuando el módulo exista. Ningún error de sintaxis ni de entorno.

**Verificación previa de los tests (sin dejar rastro).** Para no entregar tests que nazcan rotos o que no puedan fallar, el tester escribió de forma temporal el literal de «Frontend · cliente» del diseño en `src/api/cliente.ts`, corrió la suite y lo borró antes de dejar el rojo. Con el literal, los nueve tests pasan (`Tests 9 passed (9)`) y `typecheck` queda sin errores. Con siete mutantes aplicados uno a uno sobre ese archivo temporal, cada uno puso en rojo al menos un test:

| Mutante | Cambio | Test en rojo |
|---|---|---|
| a | no se descarta el token ante un `403` (hallazgo m-4) | TC-33 |
| b | `pedirToken` lee `document["cookie"]` | TC-37 |
| c | el `401` de `POST /sesion` y de `/sesion/cierre` también llama a `alTerminarSesion` | TC-35 |
| d | no se reinicia el token tras `POST /sesion` y `/sesion/cierre` | TC-32 y TC-37 |
| e | sin promesa compartida (`token = pedirToken()`) | TC-32 |
| f | sin la guarda de métodos: un `GET` también lleva la cabecera | TC-30, TC-31, TC-32, TC-33, TC-35, TC-36, TC-37 y TC-38 (el `GET` del token se pide a sí mismo) |
| g | `pedir` devuelve `SESION` en lugar de `RED` | TC-34 |

El archivo temporal se borró y `src/api` solo contiene `cliente.test.ts`, `errores.test.ts`, `errores.ts`, `tipos.test.ts` y `generado/`. Estos siete son una comprobación del tester y no sustituyen a MT-13, MT-14 y MT-15 de la fila 7, que se aplican sobre el `cliente.ts` real.

**Notas del tester para el desarrollador.**

- El servidor se sustituye con MSW (`src/pruebas/servidor.ts`, `onUnhandledRequest: "error"`). Un doble de `GET /api/v1/sesion/csrf` emite `token-1`, `token-2`… y cada manejador anota método, ruta y cabecera `X-CSRF-Token` en un registro. El cliente se crea con `baseUrl` igual a `globalThis.location.origin` (jsdom), igual que `crearAplicacion`.
- **La ruta de mutación que no es de sesión la declara el test.** `/api/v1/requisiciones` no está en el `servidor.ts` generado, que solo publica rutas de sesión, y `POST /sesion` y `POST /sesion/cierre` ya reinician el token por la exclusión de `onResponse`. Un `403` sobre `/sesion` taparía el mutante «no se descarta el token ante un `403`» (hallazgo m-4). Por eso TC-32 (token compartido) y TC-33 (`403`) usan `POST /api/v1/requisiciones`, con un tipo local `RutaDePrueba` y una única aserción `as unknown as Client<…>` en el test, y no `any`. TC-33 sigue leyendo el plan: error `PERMISO` con `ORIGEN_NO_VERIFICADO`, un solo `POST` y dos `GET /sesion/csrf` tras la siguiente mutación, con el token nuevo.
- Cada rechazo (TC-33, TC-34, TC-35) compara el resultado de `pedir` completo con `toEqual`: `{ ok: false, error: <cuerpo íntegro> }`, no solo el `tipo`. Los cuerpos llevan `satisfies` contra los tipos generados.
- **TC-37 no puede exigir «el espía no se invoca» a la letra.** MSW lee `document.cookie` por su cuenta al emparejar cada petición en jsdom (`msw/src/core/utils/request/getRequestCookies.ts`, con `credentials: "same-origin"` y mismo origen), y el cliente fija `credentials: "same-origin"` por diseño. Un espía sin más fallaría con cualquier implementación. El test anota quién lee: el primer marco de la pila que no es el espía, jsdom ni `<anonymous>`, y exige que ningún lector esté fuera de `node_modules`. La sonda de la pila (jsdom envuelve `document` en un `Proxy`, por lo que el lector real está unos marcos más abajo) y el mutante b lo confirman. Si `msw` dejara de leer la cookie, el test seguiría siendo válido.
- TC-31 añade `HEAD` al `GET` como método que no lleva cabecera. El plan solo nombra `GET`; `HEAD` también está fuera de `METODOS_QUE_MUTAN`.
- TC-35 y TC-36 reinician los manejadores y crean un cliente nuevo por caso, para contar las llamadas a `alTerminarSesion` y a `alDenegarPermiso` caso por caso.
- Ningún archivo de producción quedó en el árbol: ni `cliente.ts`, ni `sesion.ts`, ni `ProveedorApi.tsx`.

**Sin cobertura en esta fila (pendiente de decisión del orquestador).** `exigir` y `FalloApi` no tienen test en el plan (TC-30 a TC-38), y ningún mutante del diseño los cubre. Tampoco hay test del caso en que `GET /sesion/csrf` falla (el token fallido no se cachea): el literal lo maneja con `.catch(() => { token = null; … })`, pero el plan no lo pide.

**Verde.** `cliente.ts` es el literal del diseño; `sesion.ts` y `ProveedorApi.tsx` siguen su descripción. Los nueve tests (TC-30 a TC-38) pasaron a la primera, sin tocar ningún test. Salida real, desde `frontend/`:

```text
$ npx vitest run src/api/cliente
 Test Files  1 passed (1)
      Tests  9 passed (9)

$ npm run lint        → eslint .                    EXIT=0
$ npm run typecheck   → tsc --noEmit               EXIT=0
$ npm test            → Test Files 7 passed (7) · Tests 37 passed (37)   EXIT=0
$ npm run build       → vite build · ✓ built in 76ms                      EXIT=0
```

**Refactor.** Ninguno. El literal ya es mínimo y no se cambió nada tras el verde.

**Tests devueltos al tester.** Ninguno. El literal del diseño y los nueve tests coinciden. Queda sin cubrir lo que el tester ya señaló: `exigir`, `FalloApi` y el fallo de `GET /sesion/csrf`.

#### Fila 7 · Mutación y regresión

`tester-frontend` aplicó MT-1 a MT-14 de uno en uno sobre los archivos reales, desde `frontend/`, con Node 24.22.0 y npm 11.19.1. Un guion fuera del repositorio (`mutar.mjs`, en el directorio temporal de la sesión) hace siempre lo mismo: calcula el SHA-256 del archivo, comprueba que la cadena a mutar aparece el número de veces previsto, escribe el mutante, ejecuta `npm test`, restaura los bytes originales dentro de un `finally` y vuelve a calcular el SHA-256. Ningún archivo de producción quedó modificado: los siete SHA-256 de abajo coinciden antes y después de cada mutante.

La fila no toca código de producción. Escribió tres tests nuevos (TC-M6, TC-H1 y TC-H2), todos en verde sobre el código real, y cada uno con un mutante que lo pone en rojo.

**Mutantes.** Todos se ejecutan con `npm test`; la columna «Test que cae» es lo que el comando devolvió, no lo que el diseño preveía.

| ID | Archivo | Cambio | Comando | Test que cae | SHA restaurado |
|---|---|---|---|---|---|
| MT-1 | `package.json` | `"react": "19.3.1"` pasa a `"^19.3.1"` | `npm test` | TC-01 · `versiones fijadas` (`dependencies.react = ^19.3.1`) | ✓ |
| MT-2 | `vite.config.ts` | `changeOrigin: true` en el proxy de `/api` | `npm test` | TC-02 · `proxy en el mismo origen` (`to not have property "changeOrigin"`) | ✓ |
| MT-3 | `eslint.config.js` | la expresión de `CallExpression` pierde `parseInt` | `npm test` | TC-05 · `las demás conversiones` (`[1, 3, 4, 5, 6]` en lugar de `[1, 2, 3, 4, 5, 6]`) | ✓ |
| MT-4 | `eslint.config.js` | el bloque de `src/compartido/dinero` pasa a `["error", ...NUMERO, COOKIE]` | `npm test` | TC-06 · `el módulo de dinero está exento` | ✓ |
| MT-5 | `eslint.config.js` | el bloque de `dinero` deja `no-restricted-syntax` en `"off"`: sin `COOKIE` | `npm test` | TC-07 · `document.cookie` (`src/compartido/dinero/x.ts: expected [] to have a length of 1`) | ✓ |
| MT-5′ | `eslint.config.js` | variante: el bloque de `dinero` con `["error"]` y sin selectores | `npm test` | TC-06, no TC-07: ESLint conserva las opciones del bloque anterior cuando una regla solo cambia de gravedad, así que `COOKIE` sigue prohibido y `Number` también | ✓ |
| MT-6 | `scripts/tipos.ts` | `diferencias` compara solo longitudes | `npm test` | **Sobrevivió.** TC-15 añade una línea y la longitud cambia. Tras añadir TC-M6, cae TC-M6 | ✓ |
| MT-7 | `scripts/tipos.ts` | `recoger` sin el bucle de `$ref`: solo las nueve raíces | `npm test` | TC-11 `subconjunto cerrado` (`el $ref #/components/schemas/Accion no resuelve dentro del subconjunto`) y los otros cinco de `tipos.test.ts`, que reciben `Can't resolve $ref` | ✓ |
| MT-8 | `src/compartido/dinero/dinero.ts` | `ROUND_HALF_UP` pasa a `ROUND_HALF_EVEN` (las tres apariciones, la del comentario incluida) | `npm test` | TC-20 · `redondeo al presentar` (`$1,234.56` en lugar de `$1,234.57`) y TC-21 | ✓ |
| MT-9 | `src/compartido/dinero/dinero.ts` | `formatearImporte` formatea `Number(d.toString()).toFixed(2)` | `npm test` | TC-21 · `sin pasar por number` (`$12,345,678,901,234.56` en lugar de `…234.57`) | ✓ |
| MT-10 | `src/compartido/dinero/dinero.ts` | `aDecimal` sin `DECIMAL_PLANO`: `try { return new Decimal(valor) } catch { return null }` | `npm test` | TC-22 · `cifra inválida` (`aDecimal("1e3"): expected 1000 to be null`) | ✓ |
| MT-11 | `src/api/errores.ts` | la salida intercambia `CONFLICTO` y `REGLA_NEGOCIO` | `npm test` | TC-26 · `cada tipo con sus campos` (`REGLA_NEGOCIO: expected 'CONFLICTO'`) | ✓ |
| MT-12 | `src/api/errores.ts` | sin `ESTADO_DE_TIPO[cuerpo.tipo] !== estado` | `npm test` | TC-27 · `fuera del contrato` (`SESION` con 500 deja de ser `GENERICO`) | ✓ |
| MT-13a | `src/api/cliente.ts` | `aplicarCsrf` pide el token pero no pone la cabecera | `npm test` | TC-30, TC-31, TC-32 y TC-33 (`expected null to be 'token-1'`) | ✓ |
| MT-13b | `src/api/cliente.ts` | sin la guarda de métodos: un `GET` también lleva la cabecera | `npm test` | TC-31 (`GET: expected 'token-de-prueba' to be null`) y siete más: el `GET /sesion/csrf` se pide a sí mismo (`RangeError: Maximum call stack size exceeded`) | ✓ |
| MT-14a | `src/api/cliente.ts` | no se reinicia el token tras `POST /sesion` ni `POST /sesion/cierre` | `npm test` | TC-32 · `PA-T9` y TC-37 | ✓ |
| MT-14b | `src/api/cliente.ts` | no se reinicia el token ante un `403` | `npm test` | TC-33 · `origen no verificado` (`expected [ { metodo: 'GET', … } ] to have a length of 2 but got 1`) | ✓ |
| MT-14c | `src/api/cliente.ts` | `pedir` devuelve `SESION` en lugar de `RED` | `npm test` | TC-34 · `sin red` | ✓ |
| MT-A1 | `src/api/cliente.ts` | el `catch` del token no pone `token = null` | `npm test` | TC-H1 · `el token fallido no se cachea` (`expected false to be true`) | ✓ |
| MT-A2 | `src/api/cliente.ts` | `exigir` lanza `FalloApi({ tipo: "RED" })` en lugar del error recibido | `npm test` | TC-H2 · `exigir lanza FalloApi` (`expected { tipo: 'RED' } to deeply equal { tipo: 'PERMISO', … }`) | ✓ |
| MT-A2b | `src/api/cliente.ts` | `exigir` lanza `Error` plano en lugar de `FalloApi` | `npm test` | TC-H2 (`expected Error: PERMISO to be an instance of FalloApi`) | ✓ |

**SHA-256 por archivo**, idénticos antes de mutar y tras restaurar:

| Archivo | SHA-256 |
|---|---|
| `package.json` | `99b13dd6cb4a3a46b136bd2b53102787f719dd6b6b551246fb809986b60010b5` |
| `vite.config.ts` | `c18e3c2e4a7f10a9ca5ca30561aabf8eba944a59a95bde6047a7168c7d954cea` |
| `eslint.config.js` | `387b2d147e6a01fd47ffd68263c289f45ffe8c7c70ef1934841bd6e5094a4cd9` |
| `scripts/tipos.ts` | `59eb8f4becb9cde9958f53ee29413e9d49aaf3b32a8fc392b0a9e238ac1450f9` |
| `src/compartido/dinero/dinero.ts` | `bff8e5bb68114a29ca55e2ac107d70c91beeaff89edb4d9b8012042d14545629` |
| `src/api/errores.ts` | `03560e9a5db864c5abaac758c73c771a349eae9abc64716c5e4a8087f78a0018` |
| `src/api/cliente.ts` | `40b5814c9e3c514e0f41cf2d798ccd1d1185d0d89eca74fca8584a1ec7a657e3` |

**Un mutante sobrevivió: MT-6.** TC-15 comprueba una edición a mano que **añade** una línea (`// a mano`), y con ella cambia la longitud del archivo. Un `diferencias` que compara solo longitudes la detecta igual, de modo que la suite seguía en verde (`Tests 37 passed (37)`, código 0). El hueco es real: una edición de igual longitud, como cambiar una letra, pasaría `npm run tipos:verificar` sin aviso. Se añadió **TC-M6** (`scripts/tipos.test.ts` · `tkt008_ca02_esc05 · edición de igual longitud`): cambia `export` por `exprot` en el `servidor.ts` generado, comprueba que el texto difiere y que la longitud es la misma, y exige que `diferencias` nombre `src/api/generado/servidor.ts`. Nace en verde sobre el código real y MT-6 lo pone en rojo (`expected [] to deeply equal [ 'src/api/generado/servidor.ts' ]`).

Salida real del mutante superviviente, antes y después del test:

```text
$ (MT-6 aplicado, sin TC-M6)  npm test
 Test Files  7 passed (7)
      Tests  37 passed (37)
(código de salida 0)  ← el mutante sobrevive

$ (MT-6 aplicado, con TC-M6)  npm test
 ❯ |herramientas| scripts/tipos.test.ts (7 tests | 1 failed) 131ms
     × tkt008_ca02_esc05 · edición de igual longitud 16ms
 Test Files  1 failed | 6 passed (7)
      Tests  1 failed | 37 passed (38)
AssertionError: expected [] to deeply equal [ 'src/api/generado/servidor.ts' ]
(código de salida 1; SHA-256 de tipos.ts restaurado, igual que antes)
```

**Huecos de cobertura de la fila 6.** `tester-frontend` y `desarrollador-react` señalaron dos cosas sin test en `src/api/cliente.test.ts`. Se añadieron en la misma fila, sin tocar `cliente.ts`:

- **TC-H1** (`tkt008_ca03 · el token fallido no se cachea`). `GET /sesion/csrf` responde `500` la primera vez. La mutación devuelve `{ ok: false, error: { tipo: "RED" } }`, no se envía el `POST` (solo hay un `GET` registrado) y la siguiente mutación vuelve a pedir el token, recibe `token-tras-el-fallo`, lo lleva en `X-CSRF-Token` y tiene éxito. Registro final: `GET csrf`, `GET csrf`, `POST`. MT-A1 lo pone en rojo.
- **TC-H2** (`tkt008_ca04_esc01 · exigir lanza FalloApi con el error normalizado`). Con `200`, `exigir` devuelve los datos tal cual. Con un `403` `ROL_INSUFICIENTE` normalizado por `pedir`, lanza una instancia de `FalloApi`, su `error` es el cuerpo íntegro (`toEqual(rolInsuficiente)`) y su `message` es `PERMISO`. MT-A2 (error sustituido) y MT-A2b (`Error` plano) lo ponen en rojo.

Los dos nacieron en verde, como pide la tarea. La prueba de que pueden fallar son sus mutantes.

**Mutantes del diseño con la predicción cambiada.** MT-5 estaba previsto contra TC-07, y con la variante `["error"]` cae TC-06 (véase MT-5′ en la tabla); la variante `"off"` es la que pone en rojo TC-07. MT-13b cae en ocho tests y no en TC-31 solo, porque sin la guarda el cliente se pide el token a sí mismo. Ninguno es un superviviente.

**Regresión.** Desde `frontend/`, con `npm ci` desde cero y Node 24.22.0:

```text
$ npm ci
added 570 packages, and audited 571 packages in 31s
found 0 vulnerabilities
(código de salida 0)

$ npm run lint           → eslint .            (sin mensajes; código de salida 0)
$ npm run typecheck      → tsc --noEmit        (sin errores; código de salida 0)

$ npm test
 Test Files  7 passed (7)
      Tests  40 passed (40)
(código de salida 0; los 37 anteriores y TC-M6, TC-H1 y TC-H2)

$ npm run build
✓ 14 modules transformed.
dist/index.html                  0.31 kB │ gzip:  0.23 kB
dist/assets/index-CeNtAqIq.js  219.56 kB │ gzip: 68.61 kB
✓ built in 78ms
(código de salida 0)

$ npm run tipos:verificar
Tipos al día.
(código de salida 0)
```

`CA-R2`, desde la raíz y desde `backend/` con Docker 29.8.2 en marcha:

```text
$ git diff --stat Produccion -- backend       (sin salida)
$ git status --short -- backend               (sin salida)

$ uv run pytest -q
1138 passed in 235.91s (0:03:55)
(código de salida 0)

$ uv run ruff check .
All checks passed!
(código de salida 0)

$ uv run mypy .
Success: no issues found in 153 source files
(código de salida 0)

$ uv run lint-imports
Contracts: 15 kept, 0 broken.
(código de salida 0)

$ uv run python -m herramientas.verificar_float
verificar_float: archivos revisados: 18; hallazgos: 0
(código de salida 0)
```

`CA-R3`: `grep -rn "document\.cookie" frontend/src` solo encuentra un comentario de `src/api/cliente.test.ts` (línea 323, que explica por qué MSW lee la cookie por su cuenta). Fuera de los tests no hay ninguna aparición, y TC-07 (la regla de ESLint), TC-18 (`tipos.test.ts`) y TC-37 (`nadie lee la cookie`) están en verde dentro de `npm test`.

**Estado de la fila 7.** MT-1 a MT-14 sin supervivientes tras añadir TC-M6. La fila queda `⚠ Ajustado`, porque añadió tres tests que el diseño no preveía. TC-R4 y TC-R5 del diseño (documentación y `tools/tests`, `CA-R4`) no son de esta fila: la regresión de la fila 7 cubre `CA-R1`, `CA-R2` y `CA-R3`.

### Ciclo de corrección 1

La auditoría de arquitectura devolvió **REQUIERE CAMBIOS** con hallazgos Menores. Esta subsección es el **rojo** del ciclo: `tester-frontend` escribió los tests y no tocó ningún archivo de producción (SHA-256 de `src/api/cliente.ts` `40b5814c…657e3`, de `src/compartido/dinero/dinero.ts` `bff8e5bb…45629` y de `eslint.config.js` `387b2d14…94cd9`, iguales antes y después). El código lo corrige otro agente. Quedan fuera, por decisión del orquestador, las coerciones aritméticas (`"1" * 1`, `-"1"`, `.toFixed`, `Math.round`): prohibirlas daría falsos positivos en código que no maneja dinero.

#### Rojo

**F002 · mutantes repetidos sobre el `cliente.ts` real** (antes de escribir los tests de F005). Un guion fuera del repositorio (`mutar.mjs`, en el directorio temporal de la sesión) calcula el SHA-256, aplica el cambio, ejecuta `npm test`, restaura los bytes originales en un `finally` y vuelve a calcular el SHA-256. SHA-256 antes y después de cada mutante: `40b5814c9e3c514e0f41cf2d798ccd1d1185d0d89eca74fca8584a1ec7a657e3`.

| ID | Cambio en `src/api/cliente.ts` | Test que cae | SHA restaurado |
|---|---|---|---|
| MT-B2b | `void document["cookie"];` antes de pedir el token | TC-37 · `tkt008_car3 · nadie lee la cookie` (`expected [ …(2) ] to deeply equal []`) | ✓ |
| MT-B2c | `response.status === 401 && (!esDeSesion \|\| ruta === RUTA_INICIO)`: el `401` de `POST /sesion` termina la sesión | TC-35 · `tkt008_ca05 · qué 401 terminan la sesión` (`POST /api/v1/sesion: expected "vi.fn()" to be called +0 times, but got 1 times`) | ✓ |
| MT-B2e | `token ??= pedirToken()` pasa a `token = pedirToken()`: sin promesa compartida | TC-32 · `tkt008_ca03 · PA-T9` (`expected [ { metodo: 'GET', …(2) }, …(1) ] to have a length of 1 but got 2`) | ✓ |

Cada mutante pone en rojo un solo test y ninguno sobrevive. La regla de ESLint no habría detectado MT-B2b (`document["cookie"]` es justo F001): lo detecta el test en tiempo de ejecución.

**Suite con los tests nuevos**, sobre el código de producción sin tocar (`npm test`, desde `frontend/`, Node 24.22.0):

```text
 ❯ |cliente| src/compartido/dinero/dinero.test.ts (8 tests | 1 failed)
     × tkt008_ca13 · TC-F4 · un negativo que redondea a cero no lleva signo
 ❯ |cliente| src/api/cliente.test.ts (14 tests | 3 failed)
     × tkt008_ca03 · el token fallido no se cachea
     × tkt008_ca04_esc02 · TC-F5a · el token con 500 es GENERICO con su correlación
     × tkt008_ca04_esc02 · TC-F5b · el token con 200 y sin campo token es GENERICO
 ❯ |herramientas| scripts/eslint-reglas.test.ts (13 tests | 5 failed)
     × tkt008_car3 · TC-F1a · document["cookie"]
     × tkt008_car3 · TC-F1b · window.document.cookie
     × tkt008_car3 · TC-F1c · const { cookie } = document
     × tkt008_ca13_esc03 · TC-F1d · globalThis.Number y window.Number
     × tkt008_ca13_esc03 · TC-F1e · import() dinámico de decimal.js
 Test Files  3 failed | 4 passed (7)
      Tests  9 failed | 41 passed (50)
(código de salida 1)
```

`npm run typecheck` y `eslint` sobre los tres archivos de prueba no dan mensajes. Razón de cada rojo, que es la esperada y no un error de importación o de entorno:

| Test | Razón del fallo |
|---|---|
| TC-F1a, TC-F1b, TC-F1c | `src/modulos/x.ts: expected [] to have a length of 1 but got +0`: `no-restricted-syntax` no da ningún mensaje, porque el selector solo reconoce `document.cookie` con el nombre escrito como identificador |
| TC-F1d | `expected [] to deeply equal [ 1, 2 ]`: el selector de `Number` solo mira `callee.type='Identifier'`, y `globalThis.Number(…)` y `window.Number(…)` pasan |
| TC-F1e | `expected [] to have a length of 1 but got +0`: ni `no-restricted-imports` ni `no-restricted-syntax` miran `import("decimal.js")` |
| TC-F4 | `expected '-$0.00' to be '$0.00'`: `toFixed(2)` da `"-0.00"` e `Intl` conserva el signo |
| TC-F5a | `expected { ok: false, error: { tipo: 'RED' } } to deeply equal { ok: false, error: { …(4) } }`: un `500` del servidor sale como `RED` |
| TC-F5b | `expected true to be false`: con `200` sin `token`, `pedirToken` devuelve `undefined`, la mutación se da por buena y viaja con `X-CSRF-Token: undefined` (no es `RED`, es peor: nadie lo detecta) |
| TC-H1 (ajustado) | `expected { ok: false, error: { tipo: 'RED' } } to deeply equal { ok: false, error: { …(4) } }`: mismo motivo que TC-F5a |

TC-F1f y TC-F5c nacen en verde, por diseño: el primero es el control de que `document.title` no se rechaza, y el segundo mantiene el caso real de `RED` (`HttpResponse.error()` de MSW sobre `GET /sesion/csrf`), que la corrección no debe romper. `tkt008_ca04_esc03 · sin red` (TC-34) ya cubría el `RED` de un `GET /sesion`.

**Corrección del tester por F005 · TC-H1.** TC-H1 es un test del tester (fila 7) y su aserción fijaba `RED` ante el fallo de `GET /sesion/csrf` con `500`. Esa aserción describía el comportamiento defectuoso: `RED` significa «la petición no llegó al servidor» (CA-4 esc. 3) y aquí el servidor respondió. Ahora exige `{ ok: false, error: { tipo: "GENERICO", estado: 500, mensaje: null, correlacion_id: null } }`. Se conserva todo lo demás: no se envía el `POST`, el token fallido no se cachea y la siguiente mutación vuelve a pedirlo y lleva `token-tras-el-fallo`. No lo cambia quien escribe el código.

#### Verde

Corrección aplicada por `corrector-revision` sin tocar ningún test. Desde `frontend/`, Node 24.22.0:

```text
$ npm run lint
> eslint .
(sin mensajes · código de salida 0)

$ npm run typecheck
> tsc --noEmit
(sin mensajes · código de salida 0)

$ npm test
 Test Files  7 passed (7)
      Tests  50 passed (50)
(código de salida 0)

$ npm run build
✓ 14 modules transformed.
dist/index.html                  0.31 kB │ gzip:  0.23 kB
dist/assets/index-CeNtAqIq.js  219.56 kB │ gzip: 68.61 kB
✓ built in 80ms

$ npm run tipos:verificar
Tipos al día.

$ git status --short -- ../backend
(vacío)
```

`npm ci` termina sin errores y repite el aviso conocido del `postinstall` de `msw` (véase «Hallazgos fuera de alcance»). Los nueve tests que estaban en rojo (TC-F1a a TC-F1e, TC-F4, TC-F5a, TC-F5b y TC-H1 ajustado) pasan; TC-F1f, TC-F5c y TC-34 siguen en verde. Con `src/index.css` importado temporalmente desde `main.tsx`, `npm run build` resuelve `@import "shadcn/tailwind.css"` y emite `index-CP98igRa.css` (30,33 kB); el cambio se revirtió.

### Revisión · ciclo de corrección 1

`/sdd-revisar` devolvió hallazgos sobre los tests y sobre el código. Esta subsección es el **rojo** de la parte de tests: `tester-frontend` escribió y reestructuró los tests y no tocó ningún archivo de producción (SHA-256 de `scripts/tipos.ts` `59eb8f4b…450f9`, de `src/api/cliente.ts` `d13d00c6…cc115`, de `src/api/errores.ts` `03560e9a…a0018`, de `src/compartido/dinero/dinero.ts` `b9d66c2c…eb99` y de `eslint.config.js` `a886eb01…2519b`, iguales antes y después). El código lo corrige otro agente. Los TC de esta sección llevan el prefijo `R1` (revisión, ciclo 1) para no chocar con los números `TC-39` en adelante, que son de TKT-008b.

#### Rojo

Suite completa (`npm test`, desde `frontend/`, Node 24.22.0) sobre el código de producción sin tocar:

```text
 ❯ |cliente| src/compartido/dinero/dinero.test.ts (14 tests | 6 failed)
     × tkt008_ca08_esc05 · TC-R1f · un importe Infinity no se presenta
     × tkt008_ca08_esc05 · TC-R1f · un importe NaN no se presenta
     × tkt008_ca08_esc05 · TC-R1f · un importe -Infinity no se presenta
     × tkt008_ca08_esc05 · TC-R1g · una cantidad Infinity no se presenta
     × tkt008_ca08_esc05 · TC-R1g · una cantidad NaN no se presenta
     × tkt008_ca08_esc05 · TC-R1g · una cantidad -Infinity no se presenta
 ❯ |cliente| src/api/cliente.test.ts (20 tests | 1 failed)
     × tkt008_ca04_esc02 · TC-R1e · un TypeError de código propio, no de fetch, no es RED
 Test Files  2 failed | 5 passed (7)
      Tests  7 failed | 71 passed (78)
(código de salida 1)
```

`npm run typecheck` y `npm run lint` terminan sin mensajes. Razón de cada rojo, que es la esperada y no un error de importación o de entorno:

| Test | Razón del fallo |
|---|---|
| TC-R1e | `expected { ok: false, error: { tipo: 'RED' } } to deeply equal { ok: false, error: { …(4) } }`: el servidor respondió, pero `headers.set` lanzó un `TypeError` dentro del cliente y `pedir` lo toma por una caída de red |
| TC-R1f | `formatearImporte(Infinity)` da `'$∞'` y no `null`; `NaN` y `-Infinity` salen igual de dibujados: `toFixed(2)` de un valor no finito devuelve texto e `Intl` lo presenta |
| TC-R1g | `formatearCantidad(Infinity)` da `'∞'` y no `null`; `NaN` y `-Infinity` igual: la misma causa |

TC-R1a, TC-R1b, TC-R1c y TC-R1d nacen en verde, por diseño: cubren comportamiento que el código ya tiene y que ningún test vigilaba. Lo demuestran sus mutantes.

#### Mutantes

Un guion fuera del repositorio (`mutar.mjs`, en el directorio temporal de la sesión) calcula el SHA-256 del archivo, aplica un cambio, ejecuta `npm test`, restaura los bytes originales en un `finally` y vuelve a calcular el SHA-256. La columna «Cae» omite TC-R1e, TC-R1f y TC-R1g, que están en rojo con o sin mutante. Ningún mutante sobrevive y todos restauran el archivo con el mismo SHA-256.

| ID | Cambio | Cae | SHA restaurado |
|---|---|---|---|
| MT-R1 | `scripts/tipos.ts`: se borra el bucle `for (const [ruta, contenido] of generados) escribirArchivo(ruta, contenido);` | TC-R1a (el mapa de escritos queda vacío) y TC-R1b (`escribirArchivo` nunca se llama y sale 0) | ✓ |
| MT-R2 | `scripts/tipos.ts`: `return 2;` pasa a `return modo === "generar" ? 1 : 2;` | solo TC-R1b | ✓ |
| MT-R2b | `scripts/tipos.ts`: `return 2;` pasa a `return 1;` | TC-R1b y `tkt008_ca02_esc01 · salida 2…` | ✓ |
| MT-R3 | `scripts/tipos.ts`: se quita `.sort()` de las claves | TC-R1c y `tkt008_ca02_esc01 · subconjunto cerrado` | ✓ |
| MT-R4 | `scripts/tipos.ts`: se quita la llamada recursiva `recoger(referencia…)` | `subconjunto cerrado`, TC-R1c y los tests de generación (19 rojos en total) | ✓ |
| MT-R5 | `scripts/tipos.ts`: se añade `"UsuarioActual"` a las raíces | `subconjunto cerrado` y TC-R1c (la lista literal ya no coincide) | ✓ |
| MT-R6 | `src/api/cliente.ts`: `esRed` pasa a `fallo instanceof Error` | solo TC-R1d | ✓ |
| MT-R7 | `src/api/cliente.ts`: el token solo se descarta tras iniciar sesión | solo `PA-T9 · tras cerrar…` | ✓ |
| MT-R8 | `src/api/cliente.ts`: el token solo se descarta tras cerrar sesión | `PA-T9 · tras iniciar…` y TC-37 (`nadie lee la cookie`) | ✓ |
| MT-R9 | `src/api/cliente.ts`: `token ??= pedirToken()` pasa a `token = pedirToken()` | solo `PA-T9 · dos mutaciones simultáneas…` | ✓ |
| MT-R10 | `src/api/cliente.ts`: se borra `alTerminarSesion()` | solo `tkt008_ca05_esc01 · GET /api/v1/sesion…` | ✓ |
| MT-R11 | `src/api/cliente.ts`: el `401` de `POST /sesion` termina la sesión | solo `tkt008_ca05_esc03 · POST /api/v1/sesion con 401…` | ✓ |
| MT-R12 | `src/api/cliente.ts`: el cierre deja de contar como ruta de sesión | `tkt008_ca05_esc03 · POST /api/v1/sesion/cierre…` y `PA-T9 · tras cerrar…` | ✓ |
| MT-R13 | `src/api/errores.ts`: `reintentar_tras_s` siempre `null` | solo `tkt008_ca04_esc01 · CONCURRENCIA con sus campos` | ✓ |
| MT-R14 | `src/api/errores.ts`: `enteroNoNegativo(…) ?? 0` | solo `tkt008_ca04_esc01 · CONCURRENCIA sin Retry-After…` | ✓ |
| MT-R15 | `src/api/errores.ts`: `LIMITE_INTENTOS: 429` pasa a `430` | solo `tkt008_ca04_esc01 · LIMITE_INTENTOS con sus campos` | ✓ |

MT-R2 aísla TC-R1b de la prueba de salida 2 que ya existía: esa usa `verificar` y TC-R1b usa `generar`. Los mutantes que caen en un solo test (MT-R2, MT-R6, MT-R7, MT-R9, MT-R10, MT-R11, MT-R13, MT-R14 y MT-R15) demuestran que la división de C004 no dejó dos tests con la misma cobertura. La lista literal de C006 mata también el mutante del `.sort()`, porque está en orden alfabético y el recorrido por raíces no lo está.

#### Tests nuevos y divididos

El conteo sube de 50 a 78 tests. Ninguna aserción existente se pierde: C004 solo cambió la estructura, salvo lo que indica la tabla.

| Hallazgo | Archivo | Antes | Ahora |
|---|---|---|---|
| C001 | `scripts/tipos.test.ts` | sin test de `generar` | TC-R1a y TC-R1b, nuevos |
| O4 | `scripts/tipos.test.ts` | sin test del `.sort()` | TC-R1c, nuevo |
| C002 | `src/api/cliente.test.ts` | — | TC-R1d y TC-R1e, nuevos. `RED` para `HttpResponse.error()` ya lo cubren TC-34 y TC-F5c |
| C003, F101 | `src/compartido/dinero/dinero.test.ts` | — | TC-R1f y TC-R1g, tres tests cada uno con `test.each` |
| C004 | `scripts/tipos.test.ts` | `tkt008_ca02 · exportación sin uv` (1 test) | seis tests: exportación fallida, exportación correcta, salida 2, salida 1, salida 0 y salida 3 |
| C004 | `src/api/cliente.test.ts` | `tkt008_ca03 · PA-T9` (1 test) | tres tests: tras iniciar, tras cerrar y mutaciones simultáneas |
| C004 | `src/api/cliente.test.ts` | `tkt008_ca05 · qué 401 terminan la sesión` (1 test, 3 casos) | tres tests con `test.each` y `%s` (con `$titulo` Vitest recorta el nombre a 40 caracteres) |
| C004 | `src/api/errores.test.ts` | `tkt008_ca04_esc01 · cada tipo con sus campos` (1 test) | ocho tests con `test.each`, uno por tipo, más uno para `CONCURRENCIA` sin `Retry-After`. Se quitó el `toMatchObject` de `mensaje` y `correlacion_id`, redundante con `toEqual(esperado)`; el bloque de campos propios pasó a cada caso |
| C004 | varios | nombres sin `escNN` | `tkt008_ca03_esc01 · el token fallido no se cachea`, `tkt008_ca13_esc02 · negativo` y `tkt008_ca13_esc02 · TC-F4…`; los tres de `PA-T9` llevan `esc01` |
| C006 | `scripts/tipos.test.ts` | el oráculo copiaba `referenciasDe` y `esquemasDe` de `tipos.ts` | lista literal `ESQUEMAS_ESPERADOS` (25 esquemas) y una expresión regular sobre el texto del resultado para comprobar que cada `$ref` resuelve; ninguna función de producción |

Dos nombres no llevan `escNN` porque ningún escenario de la spec los describe: `tkt008_ca02 · salida 3…` (argumento desconocido, sin escenario en `CA-2`) y `tkt008_car3 · nadie lee la cookie` (criterio de regresión). El cierre de sesión con `401` lleva `esc03` por analogía con el inicio; la spec no lo dice.

Un hueco que queda fuera de esta revisión: nada comprueba que `verificar` no escribe. Un mutante `if (modo === "generar")` → `if (true)` en `principal` sobreviviría. Se propone un test (`verificar` con `escribirArchivo` espiado) para el ciclo siguiente.

#### Verde

`corrector-revision` aplicó C002, C003/F101 y C005 sin tocar ningún test. C006 en producción queda aceptado sin cambio (véase «Ajustes»). Salida real, desde `frontend/`, con Node 24.22.0:

```text
$ npm run lint          (eslint . sin mensajes; código de salida 0)
$ npm run typecheck     (tsc --noEmit sin errores; código de salida 0)
$ npm test
 Test Files  7 passed (7)
      Tests  78 passed (78)
(código de salida 0; TC-R1e, TC-R1f y TC-R1g pasan de rojo a verde; TC-34, TC-F5c y TC-R1d siguen en verde)
$ npm run build
✓ built in 77ms         (código de salida 0)
$ npm run tipos:verificar
Tipos al día.           (código de salida 0)
```

Desde la raíz:

```text
$ python tools/verificar_docs.py
  story points          79
  escenarios           162
  codificación         134
✓ Sin problemas.
$ python tools/extraer_mermaid.py     (escribe tools/mermaid-check.html; código de salida 0)
$ python -m unittest discover -s tools/tests
Ran 6 tests in 0.012s
OK
$ git status --short -- backend       (sin salida: ningún archivo bajo backend/)
```

#### Documentación · reauditoría

Corrección de los cuatro hallazgos de documentación de la reauditoría del ciclo 1. Sin tests ni código: solo prosa y estado.

| Hallazgo | Qué cambié | Archivo |
|---|---|---|
| D010 (Mayor) | «Safari no.» pasa a «Safari no (asumido, `PA-T7`, hasta que el humo de TKT-008b lo compruebe).» en el párrafo de `npm run dev`. | `docs/arranque-local.md` |
| D011 (Menor) | Finales de línea CRLF convertidos a LF. Contenido sin cambios. Tras la conversión, recuento de `\r`: 0; sin BOM (primeros bytes `2d 2d 2d`). Las dos líneas que `git diff` muestra contra `HEAD` (`Excepción…` y `erasableSyntaxOnly`) ya estaban en el árbol de trabajo antes de esta corrección; no las toqué. | `.claude/skills/conv-frontend-react/SKILL.md` |
| D012 (Observación) | La frase de «Invariantes que deben sobrevivir al cambio» reescrita: `CLAUDE.md` y `docs/arranque-local.md` ya los modificó TKT-008a; TKT-008b modifica `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md` y `tools/verificar_docs.py`. En la fila «Módulos en alcance» de `_index.md`, `CLAUDE.md` y `docs/arranque-local.md` se conservan con la calificación «solo lo que la fila 16 aún no cubre», porque la spec dice que TKT-008b todavía añade contenido a esos dos archivos. | `sdd/tickets/tkt-008b/spec.md`, `sdd/tickets/tkt-008b/_index.md` |
| D007 (Observación) | Estado del paraguas: `EN CURSO · partido en TKT-008a, TKT-008b y TKT-008c`. La nota de debajo se conserva. | `sdd/tickets/tkt-008/_index.md` |

**Verificación:**

```text
$ python tools/verificar_docs.py
Documentos analizados: 133

  enlaces relativos   1122
  anclas internas      518
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
  codificación         134

✓ Sin problemas.   (código de salida 0)

$ python tools/extraer_mermaid.py
30 diagramas encontrados
Escrito: tools/mermaid-check.html   (código de salida 0)

$ python -m unittest discover -s tools/tests
Ran 6 tests in 0.027s

OK   (código de salida 0)
```

**Problemas nuevos detectados y NO corregidos:**

| Dónde | Qué | Por qué no lo toqué |
|---|---|---|
| `sdd/tickets/tkt-008b/spec.md`, tabla de «Invariantes» (intro, línea 93) | Dice que TKT-008b «modifica» `CLAUDE.md` y `docs/arranque-local.md`, la misma imprecisión que D012 corrige en la frase de arriba | Fuera de la lista de hallazgos de esta pasada |

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | `haiku` | `haiku` | — |
| Fila 1 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 1 · verde | desarrollador-react | haiku | haiku | — |
| Fila 2 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 2 · verde | desarrollador-react | haiku | haiku | — |
| Fila 3 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde | desarrollador-react | haiku | haiku | — |
| Fila 3 · cierre (TC-17, TC-18) | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 4 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 4 · verde | desarrollador-react | haiku | haiku | — |
| Fila 5 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 5 · verde | desarrollador-react | haiku | haiku | — |
| Fila 6 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 6 · verde | desarrollador-react | sonnet | sonnet | — |
| Fila 7 | tester-frontend | sonnet | sonnet | — |
| Ciclo de corrección 1 · rojo (F001, F002, F004, F005) | `tester-frontend` | `sonnet` | `sonnet` | — |
| Ciclo de corrección 1 · verde (F001, F003, F004, F005) | `corrector-revision` | `haiku` | `sonnet` | Orquestador: despacho del corrector. |
| Revisión · ciclo de corrección 1 · rojo (C001, O4, C002, C003, C004, C006) | `tester-frontend` | `sonnet` | `sonnet` | — |
| Revisión · ciclo de corrección 1 · verde (C002, C003, C005, C006 y documentación D001 a D008, F102) | `corrector-revision` | `haiku` | `sonnet` | Orquestador: despacho del corrector. |
| Documentación · reauditoría (D007, D010, D011, D012) | `corrector-revision` | `haiku` | `haiku` | — |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` esc. 1 | `[M]` | Cumplido | TC-02; verificación de la fila 1: `curl` por el *proxy* devuelve `200` y `Set-Cookie: cimenta_csrf` |
| `CA-2` | `[M]` | Cumplido | TC-11 a TC-18, TC-M6; verificación de la fila 3 (generación determinista y desfase con salida 1) |
| `CA-3` esc. 1 y 2 | `[M]` | Cumplido | TC-30, TC-31, TC-32, TC-33, TC-F5a, TC-F5b |
| `CA-4` | `[M]` | Cumplido | TC-26 a TC-29, TC-34, TC-F5c, TC-H2 |
| `CA-13` | `[M]` | Cumplido | TC-04 a TC-10, TC-19 a TC-25, TC-F1a a TC-F1f, TC-F4 |
| `CA-R1` | `[M]` | Cumplido | TC-01; `npm ci`, `lint`, `typecheck`, `test` y `build` en verde (fila 7) |
| `CA-R2` | `[M]` | Cumplido | Fila 7: `git diff --stat Produccion -- backend` vacío; `1138 passed`, `ruff`, `mypy`, `lint-imports` (15 contratos) y `verificar_float` en verde |
| `CA-R3` | `[M]` | Cumplido | TC-07, TC-F1a a TC-F1c, TC-18, TC-37; `grep` de `document.cookie` en `src` sin apariciones fuera de un comentario de prueba |

`CA-3` esc. 3, `CA-1` esc. 2 y 3, y el resto de criterios de la spec común son de TKT-008b y TKT-008c.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` · cierre de `/sdd-ejecutar` | `APROBADO` tras reauditoría | F001 a F006, todos Menores. F001 a F005 resueltos; F006 aceptado como deuda de TKT-008b | 1 |
| `auditor-arquitectura` · pasada independiente de `/sdd-revisar` | `APROBADO` tras reauditoría | F101 (`Decimal` no finito) y F102 (trazabilidad de `impl.md`), Menores, resueltos | 1 |
| `auditor-codigo` | `APROBADO` tras reauditoría | C001 Mayor (`generar` sin test) y C002 a C006 Menores. Resueltos todos salvo C006 en producción, aceptado: unificar las guardas acoplaría `scripts/` con `src/` | 1 |
| `auditor-seguridad` | `APROBADO` en la primera pasada | S001 a S004, Bajas, sin corrección: S001 (token desfasado entre pestañas) queda para TKT-057 | 0 |
| `auditor-docs` | `APROBADO` tras dos reauditorías | D001, D003 y D005 Mayores; D002 y D004 Menores. Por decisión del usuario, 008a documenta lo que entrega. La primera reauditoría abrió D010 (Mayor: supuesto sin marcar) y D011 (Menor: CRLF); los dos están resueltos. D009 (¿merece ADR?) queda para la persona que aprueba | 2 |
| `auditor-sql` | No aplica | Sin esquema ni migraciones | — |

Observaciones de la reauditoría que pasan a TKT-008b:

- **Condición para la fila 9:** `main.tsx` importa `src/index.css`, y la verificación incluye `npm run build` con el CSS generado, para ejercitar `@import "shadcn/tailwind.css"` y el tema del CLI.
- **O-5:** la regla de `document.cookie` no detecta un alias (`const d = document; d.cookie`) ni una aserción de tipo. Es una esquiva deliberada; TC-37 vigila los flujos en ejecución.
- **O-6:** `GENERICO` con `estado: 0` no es un código HTTP. Las pantallas no lo muestran como «Error 0».
- **F006:** `sesionOptions`, `ProveedorApi` y `useApi` reciben su primera prueba en las filas 9 y 10.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/package.json` | `npm ci` avisa de un script `postinstall` de `msw` sin aprobar (`allowScripts`). No se aprobó en esta fila; decidir en la auditoría de dependencias. | Baja |
| `frontend/src/lib/utils.ts` | El CLI genera `cn` desde el paquete `cn` y no desde `clsx` y `tailwind-merge`. Es la salida del CLI con el preset elegido; registrado, sin cambios. | Baja |
| `docs/06-stack-tecnologico.md` §5.1 | Registrar la elección de primitivas de shadcn: preset `base-nova`, `@base-ui/react` en lugar de Radix, y el paquete `cn`. Lo hace la fila 16 de TKT-008b | Baja |
| `sdd/tickets/tkt-008/design.md` | Matizar que la regla de conversión numérica no cubre las coerciones aritméticas (F001), en la documentación de la fila 16 | Baja |

## Documentación actualizada

Por decisión del usuario del 2026-10-26, 008a documenta lo que entrega. La fila 16 de TKT-008b conserva `docs/05-tickets-trabajo.md` (criterios de TKT-008 y TKT-009), `docs/06-stack-tecnologico.md`, `tools/`, el humo, la línea «Verificado en copia limpia» y lo que añada el armazón.

| Documento | Qué cambió |
|---|---|
| `CLAUDE.md`, «Desde `frontend/`» | El bloque añade `npm test`, `npm run tipos:generar` y `npm run tipos:verificar`, y `npm run dev` pierde la marca «desde TKT-008» y describe el proxy |
| `docs/arranque-local.md`, «Frontend» | Cinco comandos (`npm ci`, `lint`, `typecheck`, `npm test`, `tipos:verificar`) y dos párrafos nuevos: la generación de tipos con `uv` y el arranque con proxy en `localhost:5173`, con la exigencia de Chromium o Firefox de D-9 |
| `docs/arranque-local.md`, «Lo que todavía no arranca» | Se quita la fila de `npm run dev` |
| `.claude/skills/conv-frontend-react/SKILL.md` | §4: excepción del cliente de API fuera de la clave. §6: `erasableSyntaxOnly` (D-11, con el texto literal del diseño) |
| `docs/05-tickets-trabajo.md` | Partición de TKT-008 en TKT-008a, TKT-008b y TKT-008c, como subsecciones |
| `sdd/tickets/tkt-008/_index.md` | Ficha «Rama» con las tres ramas y una línea bajo «Estado»: el estado vive en los tres hermanos |
| `sdd/tickets/tkt-008/design.md` | Enlace al ADR de frontend en «¿Merece ADR?» y nota de reasignación en «Documentación afectada» y en la fila 16 |
| `sdd/tickets/tkt-008a/spec.md` | El non-goal que prohibía tocar `CLAUDE.md` y `arranque-local.md` pasa a describir lo que sí toca |
| `sdd/tickets/tkt-008b/_index.md` | La misma nota de reasignación en «Condiciones heredadas» |

`python tools/verificar_docs.py`: «✓ Sin problemas.» (79 puntos, 162 escenarios, 134 archivos de codificación). `extraer_mermaid.py` y `python -m unittest discover -s tools/tests` terminan en verde.

## Verificación final

- [x] Todos los criterios `[M]` de este ticket cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador. Con una desviación registrada (F002): el tester escribió y borró un `cliente.ts` provisional en la fila 6
- [x] Suite en verde, con la salida pegada arriba: 7 archivos y 78 tests en el cliente; 1138 en el backend (cifra de la fila 7: este ciclo no toca `backend/`)
- [x] Mutación MT-1 a MT-14 sin supervivientes (MT-6 sobrevivió y se mató con TC-M6; véase «Fila 7»)
- [x] Auditorías de arquitectura, código, seguridad y documentación aprobadas en `/sdd-revisar`

### Verificación de `/sdd-revisar` (2026-10-27)

Reejecutada por el orquestador tras el último ciclo de corrección:

```text
frontend/  npm run lint            → sin mensajes
frontend/  npm run typecheck       → sin errores
frontend/  npm test                → Test Files 7 passed (7) · Tests 78 passed (78)
frontend/  npm run build           → ✓ built
frontend/  npm run tipos:verificar → Tipos al día.
raíz       python tools/verificar_docs.py → ✓ Sin problemas.
raíz       git status --short -- backend  → vacío
backend/   uv run pytest -q        → 1138 passed in 251.66s (antes de los ciclos; ningún archivo de backend/ cambió después)
backend/   ruff · mypy · lint-imports · verificar_float → All checks passed · Success · 15 kept, 0 broken · 0 hallazgos
```

Los criterios `[M]` de TKT-008a están cumplidos con test. Hay un rechazo verificado por cada regla que toca el ticket: los criterios de dinero, de prueba de origen y del contrato de error tienen su caso de rechazo. Las rutas críticas, la prueba de origen y el dinero, tienen mutación probada. No se tocó `docs/api/openapi.yaml`.

**Deuda que pasa a TKT-008b**, además de la ya anotada: N-1, un test de que `verificar` no escribe archivos; N-2, validar el token CSRF en `pedirToken` para que un token inválido no quede en caché; O1, tratar `acciones` y `detalle` como posiblemente ausentes en la pantalla de bloqueo, que es de TKT-008c; y D013, añadir `tools/tests/` a la frase de invariantes de la spec de 008b.

- [x] Ningún archivo bajo `backend/` en el diff
