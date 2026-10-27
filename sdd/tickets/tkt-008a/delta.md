# Delta · TKT-008a · Andamiaje, tipos, cliente de API y dinero

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| La aplicación de cliente: React 19, Vite 8 con un *proxy* de `/api` a `127.0.0.1:8000` en el mismo origen (`localhost:5173`, sin `changeOrigin`), Tailwind v4 sin archivo de configuración y un `main.tsx` provisional | `frontend/index.html`, `frontend/vite.config.ts`, `frontend/src/main.tsx`, `frontend/src/index.css` | Que exista un cliente que arranque con `npm run dev` y hable con el backend con la cookie de sesión, sin configuración cruzada |
| Cinco primitivas de shadcn/ui copiadas al repositorio (`button`, `input`, `label`, `textarea`, `dialog`), con el preset `base-nova` sobre `@base-ui/react` y la utilidad `cn` | `frontend/components.json`, `frontend/src/components/ui/`, `frontend/src/lib/utils.ts` | La base visual de los componentes de TKT-008b y TKT-008c |
| Reglas de ESLint del proyecto: sin `Number`, `parseFloat`, `parseInt` ni `+` unario fuera del módulo de dinero (también por `globalThis.`, `window.` y `self.`); sin lectura de `document.cookie` en ninguna de sus formas habituales; `decimal.js` solo en su módulo, también por `import()`; Zod solo en formularios; `react-hooks` en error | `frontend/eslint.config.js` | Que `npm run lint` haga cumplir en el cliente la regla 1 y la regla 9 de `CLAUDE.md` y `CA-13` |
| Generación y verificación de tipos: `npm run tipos:generar` exporta el OpenAPI de FastAPI sin arrancar el servidor (por `uv run` en `backend/`) y recorta del borrador el subconjunto del contrato de error; `npm run tipos:verificar` sale con 1 y nombra el archivo si el versionado difiere, y con 2 si no se pudo generar | `frontend/scripts/tipos.ts`, `frontend/src/api/generado/servidor.ts`, `frontend/src/api/generado/contrato-error.provisional.ts` | Tipos del cliente generados y nunca escritos a mano, con todo importe como cadena; la verificación es la que TKT-009 engancha al pipeline |
| Módulo de dinero: el único que importa `decimal.js`; redondea con `ROUND_HALF_UP` solo al presentar, formatea en `es-MX` desde la cadena, presenta el cero sin signo y devuelve `null` ante una cadena inválida o un valor no finito | `frontend/src/compartido/dinero/dinero.ts` | Regla 1 en el cliente: ninguna cifra pasa por `number` |
| Normalización del contrato de error: unión discriminada por `tipo` con los ocho del contrato más `GENERICO` y `RED`; exige que el `tipo` case con el código de estado; un `HTTPValidationError` de FastAPI es `GENERICO` con su estado | `frontend/src/api/errores.ts` | Que toda pantalla reciba el rechazo con su regla, cifras y acciones sin interpretar el cuerpo |
| Cliente de API sobre `openapi-fetch`: `X-CSRF-Token` en `POST`, `PUT`, `PATCH` y `DELETE`, con el token leído del cuerpo de `GET /sesion/csrf`, compartido entre peticiones simultáneas y descartado tras iniciar o cerrar sesión, ante un `403` o si su obtención falla; `pedir` nunca lanza y devuelve `RED` solo si falla el `fetch`; un `401` fuera de las rutas de sesión llama a `alTerminarSesion` y un `403` a `alDenegarPermiso` | `frontend/src/api/cliente.ts`, `frontend/src/api/sesion.ts`, `frontend/src/api/ProveedorApi.tsx` | `RNF-05` y `RNF-01` en el cliente; la base de toda llamada de las pantallas |
| Siete archivos de prueba con 78 casos (Vitest con MSW en jsdom para `src/`, Node para `scripts/`) y la preparación de MSW | `frontend/scripts/*.test.ts`, `frontend/src/**/*.test.ts`, `frontend/src/pruebas/` | Los criterios `CA-1` esc. 1, `CA-2`, `CA-3` esc. 1 y 2, `CA-4`, `CA-13` y `CA-R1` a `CA-R3` |
| Partición de TKT-008 en TKT-008a, TKT-008b y TKT-008c, con sus hubs y specs repartidas | `docs/05-tickets-trabajo.md`, `sdd/tickets/tkt-008a/`, `sdd/tickets/tkt-008b/`, `sdd/tickets/tkt-008c/` | El diseño aprobado sumaba unas 4,600 líneas (D-1) |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `package.json` y su lock | `frontend/package.json`, `frontend/package-lock.json` | Dos scripts y cuatro dependencias de desarrollo → ocho scripts (`dev`, `build`, `lint`, `typecheck`, `test`, `tipos:generar`, `tipos:verificar`, `e2e`), todas las versiones exactas y un `overrides` de `openapi-typescript` para aceptar TypeScript 6 |
| `tsconfig.json` | `frontend/tsconfig.json` | Sin `jsx` → React JSX, `erasableSyntaxOnly`, `verbatimModuleSyntax`, alias `@/`, tipos de Node y de `vite/client`, e `include` de `src`, `scripts`, `e2e` y las dos configuraciones |
| Comandos del frontend | `CLAUDE.md`, bloque «Desde `frontend/`» | `npm run dev` marcado «desde TKT-008» → `npm test`, `tipos:generar` (requiere `uv`), `tipos:verificar` y `npm run dev` con el *proxy*, sin marca |
| Arranque del frontend | `docs/arranque-local.md`, sección «Frontend» y tabla «Lo que todavía no arranca» | Tres comandos → cinco, con dos párrafos sobre la generación de tipos y sobre `npm run dev` (abrir como `localhost`, Chromium o Firefox; Safari `(asumido)`, `PA-T7`); la fila de `npm run dev` sale de la tabla |
| Convención del frontend | `.claude/skills/conv-frontend-react/SKILL.md` §4 y §6 | → el cliente de API queda fuera de la clave de consulta como excepción declarada, y `erasableSyntaxOnly` prohíbe `enum` y propiedades de parámetro (D-11) |
| Fichas de TKT-008 y TKT-008b | `sdd/tickets/tkt-008/{_index,design}.md`, `sdd/tickets/tkt-008b/{_index,spec}.md` | TKT-008 pasa a paraguas `EN CURSO`; la documentación de comandos sale de la fila 16 de 008b hacia 008a; 008b hereda las condiciones de la revisión |
| `.gitignore` | Raíz | → `frontend/playwright-report/` y `frontend/test-results/` |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| La constante `NOMBRE_SISTEMA` | `frontend/src/index.ts` | Era el marcador de TKT-001 para que `tsc` tuviera algo que compilar; nadie la importaba (solo la citan los artefactos históricos de TKT-001) |

## Comportamiento observable nuevo

- `npm run dev` sirve el cliente en `http://localhost:5173` y `curl http://localhost:5173/api/v1/sesion/csrf` llega al backend y devuelve `200` con la cookie `cimenta_csrf`. La página es todavía un marcador: no hay pantallas.
- `npm run tipos:verificar` falla con salida 1 y la línea `Difiere: <ruta>` si alguien edita a mano un tipo generado o si el OpenAPI publicado cambió sin regenerar.
- `npm run lint` rechaza, con un mensaje que cita la regla, una conversión numérica nativa fuera del módulo de dinero y una lectura de `document.cookie` en sus formas habituales (no por un alias de `document`).
- `npm run e2e` queda declarado sin configuración ni pruebas: su primer uso llega con TKT-008b.
- Ningún comportamiento del backend cambia: `backend/` no tiene ningún archivo en el diff y su suite sigue con 1138 casos en verde.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Tipos generados del cliente | Nuevos: `servidor.ts` (del OpenAPI publicado) y `contrato-error.provisional.ts` (del borrador, con cabecera de retirada) | No: no existían |
| `docs/api/openapi.yaml` | Sin cambio | — |
| Endpoints, DTO y esquema de base de datos | Sin cambio | — |

## Decisiones (ADR)

Las decisiones de este ticket se tomaron en el intake de la spec común y en el gate del diseño común (D-1 a D-11), y constan en [`../tkt-008/_index.md`](../tkt-008/_index.md#decisiones-registradas). No se creó ADR del repositorio: el stack, la generación de tipos, Zod solo en formularios y `decimal.js` ya están en el [ADR de frontend](../../../docs/adr/20260918-frontend-react-spa.md) y en la especificación de la API §6.2.

**Queda abierta para la persona que aprueba:** si los tipos del contrato de error tomados del borrador, como provisionales, merecen un ADR propio (véase «¿Merece ADR?» en el [diseño común](../tkt-008/design.md)). Hubo una alternativa real —publicar los esquemas de error en FastAPI con `responses=` antes de este ticket— y el usuario eligió la provisional en el intake. La consecuencia está acotada: el archivo se retira cuando exista el ticket de `responses=`, previo a TKT-061.

### 2026-10-26 — Primitivas de shadcn sobre Base UI, no Radix

**Contexto:** el diseño fijaba «estilo por omisión» sin nombrar la librería base, y el CLI de shadcn 4 ofrece Base UI y Radix.
**Opciones consideradas:** Base UI (`base-nova`), la recomendada por el CLI; Radix, la histórica.
**Decisión:** Base UI, por ser la opción por omisión del CLI. El ADR de frontend dice «shadcn/ui» sin fijar la base, así que no lo contradice.
**Evidencia:** `frontend/components.json`; las primitivas importan `@base-ui/react`; lint, tipos y build en verde.
**Consecuencias:** la elección se registra en `docs/06-stack-tecnologico.md` §5.1 en la fila 16 de TKT-008b. No merece ADR del repositorio: es reversible copiando de nuevo las primitivas.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Clasificar un fallo como «sin red» por el tipo de la excepción confunde un `TypeError` del propio código con una caída de red. La marca tiene que nacer alrededor del `fetch` | C002 y TC-R1e: un token con `\n` hacía que `headers.set` lanzara `TypeError` y el cliente lo pintaba como `RED` | Todo cliente HTTP del proyecto |
| `Decimal` acepta `Infinity` y `NaN` sin quejarse, y `Intl` los pinta como `$∞` y `$NaN`. Validar la cadena de entrada no basta: el valor que sale de una operación también se valida | F101, C003 y TC-R1f/g | Toda presentación de dinero |
| `toFixed(2)` conserva el signo del cero (`-0.00`) | F004 y TC-F4 | Toda presentación de dinero |
| ESLint conserva las opciones de una regla del bloque anterior cuando un bloque posterior solo cambia su gravedad | MT-5′ de la fila 7 | Cualquier `eslint.config.js` con bloques que se solapan |
| Un selector de `no-restricted-syntax` con `property.name` no ve el acceso computado (`document["cookie"]`), y uno con `object.name` no ve `window.document.cookie` | F001 y TC-F1a a TC-F1e | Toda guarda de ESLint por AST |
| MSW lee `document.cookie` por su cuenta en jsdom: un espía simple sobre la cookie falla con cualquier implementación | TC-37 y su sondeo de la pila | Pruebas que vigilan la lectura de la cookie |
| Un test que prueba el desfase con una línea añadida no detecta una edición que conserva la longitud | MT-6 y TC-M6 | Toda verificación de archivos generados |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | Un diseño de unas 4,600 líneas llegó al gate humano antes de que nadie propusiera partir el ticket: la condición de parada 3 de `/sdd-disenar` (`.claude/skills/sdd-disenar/SKILL.md`, «Stop conditions»: más de unas 400 líneas estimadas) se aplicó al final, no al estimar. La partición, después del gate, obligó a repartir a mano la spec en tres hubs | Media |
| `agente` | El tester escribió un `cliente.ts` provisional para validar sus tests, en contra de §16, y lo borró. La prohibición no estaba en el encargo y el agente la razonó como sondeo legítimo. Hubo que repetir tres mutantes sobre el archivo real | Media |
| `comando` | La partición dejó la documentación de los comandos entregados en la fila 16 de 008b, y la auditoría de documentación lo marcó como Mayor: la regla «documentar en el mismo cambio» choca con un reparto de filas que separa código y documentación | Media |
| `herramienta` | El recuento de `\r` con `grep -c $'\r'` en Git Bash dio cifras falsas (contaba todas las líneas); solo el recuento binario (`tr -cd '\r' \| wc -c`) es fiable. Dos agentes tropezaron con lo mismo | Baja |
| `herramienta` | La herramienta de escritura de archivos dejó CRLF en Windows en algunos artefactos y en la skill editada; `.gitattributes` lo normaliza al commitear, pero la auditoría de documentación lo marca en disco | Baja |
| `modelo` | Ningún paso en `haiku` necesitó subir a `sonnet`; las dos filas en `sonnet` (6 y los correctores) fueron las que el diseño citaba. El corrector se despachó en `sonnet` por tocar la sesión | Baja |
| `proceso` | La auditoría de cierre de `/sdd-ejecutar` y la pasada independiente de `/sdd-revisar` encontraron hallazgos distintos (F001–F006 frente a F101–F102), y las cuatro auditorías de la revisión encontraron dos defectos reales que los 50 tests no veían | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `sesionOptions`, `ProveedorApi` y `useApi` sin test (F006) | Los consume el armazón | TKT-008b, filas 9 y 10 |
| `main.tsx` no importa `index.css`: el `@import "shadcn/tailwind.css"` y el tema no se ejercitan en la compilación | El `main.tsx` de la fila 1 es provisional | TKT-008b, fila 9 |
| Ningún test comprueba que `verificar` no escribe archivos (N-1) | Fuera de los hallazgos del ciclo | TKT-008b, o el siguiente toque a `scripts/tipos.ts` |
| Un token CSRF que `headers.set` rechaza queda en caché hasta el siguiente `403` o cambio de sesión (N-2) | Caso casi irreal: el servidor tendría que emitir un token inválido | TKT-057, con la rotación del token |
| `normalizarError` no valida `acciones` ni `detalle` (O1); la pantalla de bloqueo debe tratarlos como posiblemente ausentes | Decisión de `CA-13` esc. 4: no hay esquema Zod que espeje respuestas | TKT-008c, fila 11; TKT-061 lo garantiza por contrato |
| Un token desfasado entre pestañas da `403` `ORIGEN_NO_VERIFICADO` sin reintento (S001) | El servidor todavía no verifica el token | TKT-057 |
| Las coerciones aritméticas (`"1" * 1`, `.toFixed`, `Math.round`) no las detecta ESLint, ni un alias de `document` | Prohibirlas daría falsos positivos | Sin ticket: TC-37 vigila la cookie en ejecución |
| Los tipos de error salen del borrador y no del OpenAPI publicado | FastAPI no publica `responses=` | Publicar los esquemas de error en FastAPI, antes de TKT-061 (ya sugerido en `tkt-008/_index.md`) |

## Pull request

**Título:** `TKT-008a · Andamiaje, tipos, cliente de API y dinero`
**Origen:** `agent+human-review`
**Cuerpo:** lo prepara `git-entrega` en el cierre, con qué, por qué, criterios cubiertos y cómo verificarlo.
