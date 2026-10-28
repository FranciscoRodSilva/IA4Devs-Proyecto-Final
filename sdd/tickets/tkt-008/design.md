# Design · TKT-008 · Esqueleto del frontend y cliente de API

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

`frontend/` pasa de un esqueleto de TypeScript a una aplicación de página única con Vite, React 19, React Router en modo de datos, TanStack Query, Tailwind v4 y cinco primitivas de shadcn/ui copiadas al repositorio. El cliente de API es `openapi-fetch` tipado con `src/api/generado/servidor.ts`, que `npm run tipos:generar` produce del OpenAPI que publica FastAPI **sin servidor en marcha**: un script de Node en `frontend/scripts/` invoca `uv run python -c …` con `backend/` como directorio de trabajo y llama a `crear_aplicacion(...).openapi()`, así que ningún archivo de `backend/` cambia (`CA-R2`). Del borrador sale solo el **subconjunto** de esquemas del contrato de error, como tipos provisionales con cabecera de retirada. Un único *middleware* de `openapi-fetch` pone `X-CSRF-Token` en toda mutación, reinicia el token tras iniciar y cerrar sesión y tras cualquier `403`, y avisa al armazón de un `401` o un `403`; la función `pedir` convierte toda respuesta en un `ResultadoApi` cuya rama de error es una unión discriminada por `tipo`, con dos tipos propios del cliente: `GENERICO` y `RED`. El dinero entra por un solo módulo, `src/compartido/dinero/`, con `decimal.js`, y ESLint prohíbe `Number()`, `parseFloat()`, `parseInt()`, `document.cookie`, `decimal.js` y `zod` fuera de su sitio. Sobre eso se montan la pantalla de inicio de sesión, el armazón con la tabla de secciones del wireframe §2, los tres componentes reutilizables y un recorrido de humo de Playwright contra el backend real. Suma unas 4,600 líneas: D-1 recomienda partir el ticket en tres hermanos —TKT-008a (andamiaje, tipos, cliente y dinero), TKT-008b (inicio de sesión, armazón, humo y documentación) y TKT-008c (los tres componentes)— y deja como alternativa dos entregas, A y B, dentro del mismo ticket.

## Fuentes y verificación

**El arquitecto no tiene terminal en esta sesión.** Lo que sigue se apoya en Context7 (`openapi-fetch` y `openapi-typescript`, Vite 8, Vitest 5, React Router 7, TanStack Query 5, `@hookform/resolvers` con Zod 4, shadcn/ui para Vite y Tailwind v4) y en la lectura de `frontend/` entero, `backend/servidor/fabrica.py`, `backend/servidor/principal.py`, `backend/servidor/manejadores.py`, `backend/cimenta/identidad/api/rutas.py`, `esquemas.py`, `dependencias.py`, `backend/cimenta/identidad/aplicacion/configuracion.py`, `backend/herramientas/conexion.py`, las migraciones `v0001` y `v0002`, `docs/api/openapi.yaml` (l. 3790 a 4368), el wireframe §0, §1, §2 y §6, el ADR de frontend, `docs/arranque-local.md`, `.gitattributes`, `.gitignore` y `.env.example`. Lo que solo se demuestra ejecutando lleva su comprobación en la fila indicada, con la regla que aplica el ejecutor si falla.

| Fuente | Hecho | Consecuencia para el diseño |
|---|---|---|
| `fabrica.py`, `configuracion.py` | `crear_aplicacion(destino_registro=..., entorno=...)` no conecta a la base (motor perezoso) y con `entorno={}` toma los valores por omisión | El script exporta con `crear_aplicacion(destino_registro=sys.stderr, entorno={}).openapi()`: sin `.env`, sin base y sin que el registro ensucie la salida estándar |
| `pyproject.toml` | `[tool.fastapi] entrypoint = "servidor.principal:app"` | Playwright arranca el backend con `uv run --locked --env-file ../.env fastapi run --host 127.0.0.1 --port 8000` desde `backend/` |
| `rutas.py` | Las rutas llevan el prefijo completo `/api/v1/sesion`; las cookies se fijan `Secure`, `SameSite=Lax`, `path=/`, sin `Domain`; el token CSRF va en el cuerpo `TokenCsrf` y en una cookie legible | El cliente usa `baseUrl` igual al origen, sin reescribir rutas; lee el token **del cuerpo**, nunca de la cookie (`PA-T9`, `CA-R3`) |
| `dependencias.py`, `manejadores.py` | Sin cookie, `GET /sesion` responde `401` `SESION` con motivo `SIN_SESION`; un error no controlado responde `500` con `mensaje` y `correlacion_id` y **sin** `tipo` | `normalizarError` produce `GENERICO` con mensaje y correlación para el `500` (`CA-4` esc. 2) |
| OpenAPI publicado, `POST /sesion` | Como la ruta tiene cuerpo, FastAPI publica `HTTPValidationError` y `ValidationError`, cuyo `loc` es `anyOf [string, integer]`: `openapi-typescript` emite `(string \| number)[]`. En ejecución, el manejador de TKT-005 sustituye ese cuerpo por `VALIDACION` | `HTTPValidationError` convive en `servidor.ts` con el contrato de error hasta el ticket de `responses=`. **Nadie lo importa**, y `pedir` no lo mapea: un `422` con la forma `{ detail: [...] }` no tiene `tipo` y sale `GENERICO` con `estado: 422` (TC-27). Mapearlo a `VALIDACION` inventaría `campo` y `codigo` a partir de `loc` y `type`, que el servidor ya no envía. TC-18 se acota a importes y cantidades |
| Borrador, esquemas de error | Los ocho `tipo` llevan `const`; `ErrorConflicto` es un `oneOf` con discriminador; `ErrorConcurrencia.detalle.espera_maxima_ms` y `ErrorLimiteIntentos.reintentar_en_s` son los únicos `integer` del contrato | El subconjunto se genera con `const` convertido también en `enum` de un valor, para que `openapi-typescript` emita el literal aunque su versión no trate `const` (`CA-2` esc. 2). TC-18 admite solo esos dos `number` |
| Context7, `openapi-fetch` | `client.use(middleware)` con `onRequest` y `onResponse`; `onRequest` puede devolver el `Request` modificado; un error de `fetch` se relanza; el cuerpo de error se entrega ya interpretado como JSON o como texto | La normalización acepta `unknown`; el error de red se atrapa en `pedir` (`CA-4` esc. 3) |
| Context7, `openapi-typescript` | API de Node: `openapiTS(esquema)` devuelve un AST y `astToString(ast)` el texto, sin marca de tiempo | Generación en memoria, determinista; la comparación es de cadenas |
| Context7, Vite 8 | `server.proxy` con `target`; `resolve.tsconfigPaths: true` resuelve el alias `@/*` de `tsconfig.json` | Proxy de `/api` a `http://127.0.0.1:8000` sin `changeOrigin` ni `rewrite`; alias sin `@types/node` en la configuración de Vite |
| Context7, Vitest 5 | `test.projects` en línea y MSW con `setupServer` y `onUnhandledRequest: 'error'` | Dos proyectos: `cliente` (jsdom, `src/`) y `herramientas` (Node, `scripts/`) |
| Context7, React Router 7 | Modo de datos con `createBrowserRouter`, rutas con `Component` y `children`, `Outlet`; `createMemoryRouter` para pruebas | El mismo árbol de rutas sirve al navegador y a las pruebas |
| Context7, TanStack Query 5 | `queryOptions`; `retry: false` en `defaultOptions` evita reintentos | La sesión se pide con `sesionOptions`; los `401` no se reintentan |
| Context7, `@hookform/resolvers` 5 | `zodResolver` acepta Zod 4 e infiere `z.input` y `z.output` | Formularios con `useForm<z.input<E>, unknown, z.output<E>>` |
| Context7, shadcn/ui para Vite | `components.json`, componentes en `@/components/ui`, utilidades en `@/lib/utils`; Tailwind v4 por `@tailwindcss/vite` | Se aceptan las rutas por omisión del CLI para que futuros `add` no choquen |
| W3C *Secure Contexts* y RFC 6265bis | `http://localhost` es un origen «potencialmente de confianza»: Chromium (desde la 89) y Firefox (desde la 75) aceptan una cookie `Secure` fijada desde él; WebKit no | `PA-T7` se resuelve sin tocar el backend: el cliente se sirve en `http://localhost:5173`, el *proxy* conserva el mismo origen, y el desarrollo se hace en Chromium o Firefox (D-9). El humo de `CA-14` en Chromium es la prueba empírica |
| `frontend/package.json` | TypeScript 6.0.3 y ESLint 10.0.1 ya fijados; TypeScript 6 desaconseja `baseUrl` y su `types` por omisión es vacío | `tsconfig.json` declara `paths` sin `baseUrl` y `types` explícito |
| `.gitattributes` | `* text=auto eol=lf` | Los archivos generados se escriben con `\n`; la verificación compara cadenas exactas |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Aplicación Vite con React 19 y TypeScript (`index.html`, `src/main.tsx`, `vite.config.ts`) | 5 · objeto nuevo | `M1`. No existe; el stack lo fija el ADR de frontend |
| *Proxy* `/api` de Vite | 2 · nativo | `M1`, `CA-1` esc. 1. Mismo origen sin CORS ni configuración de cookies cruzadas |
| Alias `@/*` por `resolve.tsconfigPaths` | 2 · nativo | Lo usan shadcn y todo el código; evita `path.resolve` y `@types/node` en la configuración |
| Tailwind v4 con `@tailwindcss/vite`, sin archivo de configuración | 2 · nativo | `M1`. El tema lo escribe el CLI de shadcn con `@theme` en `src/index.css` |
| Primitivas shadcn `button`, `input`, `label`, `textarea`, `dialog` | 3 · reuso (copiadas) | `M4`, `M6`, `M7`, `M8`. Diálogos con foco y teclado resueltos |
| `alert`, `alert-dialog`, `sheet`, `form`, `sonner`, `select` de shadcn | 1 · YAGNI | El aviso es un `div role="alert"`; la confirmación de baja usa `dialog`; el menú plegable es un botón con `aria-expanded` |
| React Router en modo de datos | 2 · nativo | `M1`, `M5`. `loader` y `action` quedan fuera (1 · YAGNI): los datos los lleva TanStack Query |
| `QueryClient` con `retry: false` | 3 · reuso | `M3`. Caché persistida: 1 · fuera (TKT-063) |
| TanStack Table | 1 · YAGNI | Ninguna tabla en este ticket |
| `scripts/tipos.ts` (`generar` y `verificar`) | 5 · objeto nuevo | `M2`, `CA-2`. El CLI de `openapi-typescript` no exporta el OpenAPI sin servidor, no recorta el borrador ni compara |
| Exportar con `crear_aplicacion().openapi()` por `uv run`, sin archivo en `backend/` | 3 · reuso | `PA-T10`, `CA-R2`. Un `herramientas/exportar_openapi.py` sería más limpio pero rompe el non-goal «no toca el backend» (D-5) |
| Subconjunto del borrador: los nueve esquemas de error y su cierre por `$ref` | 5 · objeto mínimo | `M2`, decisión del intake. Generar el borrador entero daría unas 6,000 líneas de tipos de rutas que no existen y cambiarían en cada ticket (D-10) |
| `constComoEnum` | 5 · objeto mínimo | `CA-2` esc. 2: garantiza el literal de `tipo` sin depender de cómo trata `const` la versión instalada |
| `yaml` (dependencia de desarrollo) | 5 · objeto mínimo | Node no lee YAML; el recorte exige recorrer el documento |
| `src/api/errores.ts` (`normalizarError` y la unión `ErrorApi`) | 5 · objeto nuevo | `M3`, `CA-4`. Sin Zod: el discriminador y el código de estado son la única comprobación (`CA-13` esc. 4) |
| `src/api/cliente.ts` (`crearClienteApi`, `aplicarCsrf`, `pedir`, `exigir`, `FalloApi`) | 3 · reuso del *middleware* de `openapi-fetch`, más objeto mínimo | `M3`, `CA-3`, `CA-5` |
| `ProveedorApi` y `useApi` | 2 · nativo (contexto de React) | Cada prueba crea su cliente, su caché y su enrutador |
| `src/api/sesion.ts` (`claves`, `sesionOptions`) | 3 · reuso (`queryOptions`) | `M5`, conv. frontend §4 |
| `crearAplicacion` | 5 · objeto mínimo | Raíz de composición del cliente: liga el *middleware* con la caché y el enrutador, y la usan `main.tsx` y las pruebas |
| `src/app/navegacion/secciones.ts` y `rutaMarcador` | 5 · objeto nuevo | `M5`, decisión del intake (`PA-T8`) |
| `rutas.tsx` en `presupuesto`, `analitica`, `compras`, `proveedores`, `almacen` y `auditoria` | 5 · objeto mínimo | `CA-1` esc. 2: cada módulo es dueño de sus rutas; el ticket de cada pantalla sustituye su marcador sin tocar el armazón |
| `Armazon`, `InicioArmazon`, `GuardaSeccion`, `AvisoSinPermiso`, `SeccionMarcador`, `NoEncontrado` | 5 · objeto mínimo | `M5`, `CA-1` esc. 3, `CA-7` |
| `PaginaInicioSesion` y `inicio-sesion.formulario.ts` | 5 · objeto nuevo | `M4`, `CA-6` |
| `useEnLinea` | 2 · nativo (`useSyncExternalStore` y `navigator.onLine`) | `CA-6` esc. 6. TKT-063 lo reutiliza |
| `useCuentaAtras` | 5 · objeto mínimo | Una sola cuenta atrás para el `429` (`CA-6` esc. 5) y el `Retry-After` (`CA-9` esc. 2) |
| `src/compartido/dinero/dinero.ts` | 5 · objeto nuevo sobre `decimal.js` (3 · reuso) | `M9`, `CA-13` |
| `PantallaBloqueo`, `DetalleCifras`, `BotonesAcciones`, `etiquetas.ts` | 5 · objeto nuevo | `M6`. `DetalleCifras` y `BotonesAcciones` los reutiliza el formulario |
| `CapturaMotivo` | 5 · objeto nuevo | `M8` |
| `FormularioCatalogo`, `ConflictoEnLinea`, `ConfirmacionBaja` | 5 · objeto nuevo | `M7`. `ConfirmacionBaja` existe porque la baja sin motivo no puede usar `CapturaMotivo`, que exige motivo (`PA-T12`) |
| Reglas `no-restricted-syntax` y `no-restricted-imports` de ESLint | 2 · nativo | `CA-13` esc. 3 y 4, `CA-R3`. Un complemento de ESLint propio: 1 · descartado |
| `eslint-plugin-react-hooks`, solo `rules-of-hooks` y `exhaustive-deps` | 3 · reuso | Un *hook* condicional es un fallo que las pruebas de componente no siempre ven |
| jsdom y Testing Library | 3 · reuso | `M10`. happy-dom: descartado por menor fidelidad de foco y diálogos |
| MSW como doble del servidor | 5 · objeto nuevo (dependencia de desarrollo) | `M10`. `vi.stubGlobal('fetch')` descartado: obliga a crear el cliente después del doble y no observa la petición real con sus cabeceras (D-2) |
| Playwright, `preparacion-global.ts` y `sembrar_usuario_humo.py` | 5 · objeto nuevo | `S1`, `CA-14`. Contra la base local de Compose; testcontainers en Playwright: descartado (D-4) |
| `.gitignore`, borrar `src/index.ts` | 4 · cambio mínimo | Artefactos de Playwright; la constante de TKT-001 se sustituye por `main.tsx` |
| Service worker, cola, caché persistida, indicador sin conexión | 1 · fuera | Won't: TKT-063 |
| Esquema Zod de cualquier respuesta | 1 · prohibido | `CA-13` esc. 4 |

Ningún objeto del peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`: el ticket no toca `backend/` y refuerza las reglas 1, 9 y 10 en el cliente.

## Versiones

`.npmrc` mantiene `engine-strict=true` y `save-exact=true`; Node `>=24.0.0 <25.0.0`. El diseño fija la **línea mayor**; la fila 1 instala con `npm install -E <paquete>@<mayor>`, que resuelve la última publicada de esa mayor, y anota en `impl.md` el número exacto que quedó en `package.json`. `typescript` 6.0.3, `eslint` 10.0.1, `@eslint/js` 10.0.1 y `typescript-eslint` 8.71.2 no cambian.

| Dependencias | Paquetes y mayor |
|---|---|
| Producción | `react@19`, `react-dom@19`, `react-router@7`, `@tanstack/react-query@5`, `openapi-fetch@0` (la última `0.x`), `react-hook-form@7`, `zod@4`, `@hookform/resolvers@5`, `decimal.js@10` |
| Desarrollo | `vite@8`, `@vitejs/plugin-react` (la mayor cuyo `peerDependencies.vite` admite la 8, según `npm view @vitejs/plugin-react peerDependencies`), `tailwindcss@4`, `@tailwindcss/vite` (mismo número exacto que `tailwindcss`), `vitest` (la mayor cuyo `peerDependencies.vite` admite la 8), `jsdom` (la mayor que declara `vitest` en `peerDependencies`), `@testing-library/react@16`, `@testing-library/user-event@14`, `@testing-library/jest-dom@6`, `msw@2`, `@playwright/test@1`, `openapi-typescript@7`, `yaml@2`, `@types/react@19`, `@types/react-dom@19`, `@types/node@24`, `eslint-plugin-react-hooks` (la última) |
| Las que instale el CLI de shadcn | Las que escriba `npx shadcn@<última> add`, también exactas por `save-exact` |

**Regla para conflictos de dependencias pares.** Si `npm install` falla con `ERESOLVE` porque un paquete declara como par una mayor anterior de `typescript` o de `eslint` (lo esperable con `openapi-typescript` y `eslint-plugin-react-hooks`), se añade a `package.json` `"overrides": { "<paquete>": { "typescript": "$typescript" } }` (o `"eslint": "$eslint"`), se reinstala y la fila queda `⚠ Ajustado`. **Nunca** `--legacy-peer-deps` ni `--force`. Un conflicto con cualquier otro par se escala.

## Capas afectadas

### Frontend · estructura

```text
frontend/
├── index.html                       lang="es", <div id="raiz">, script /src/main.tsx
├── vite.config.ts                   React, Tailwind, alias, proxy y los dos proyectos de Vitest
├── playwright.config.ts
├── components.json                  del CLI de shadcn
├── scripts/
│   ├── tipos.ts                     tipos:generar y tipos:verificar
│   ├── tipos.test.ts
│   ├── esqueleto.test.ts            versiones fijadas y configuración de Vite
│   └── eslint-reglas.test.ts
├── e2e/
│   ├── preparacion-global.ts
│   ├── sembrar_usuario_humo.py
│   └── humo.spec.ts
└── src/
    ├── main.tsx · index.css
    ├── api/
    │   ├── generado/servidor.ts                      generado, versionado
    │   ├── generado/contrato-error.provisional.ts    generado, versionado
    │   ├── errores.ts · cliente.ts · sesion.ts · ProveedorApi.tsx
    ├── app/
    │   ├── crear-aplicacion.tsx · rutas.tsx
    │   ├── navegacion/secciones.ts · ruta-marcador.tsx
    │   └── armazon/Armazon.tsx · InicioArmazon.tsx · GuardaSeccion.tsx · AvisoSinPermiso.tsx · SeccionMarcador.tsx · NoEncontrado.tsx
    ├── compartido/
    │   ├── dinero/dinero.ts                          único importador de decimal.js
    │   ├── red/useEnLinea.ts
    │   ├── tiempo/useCuentaAtras.ts
    │   ├── componentes/bloqueo/PantallaBloqueo.tsx · DetalleCifras.tsx · BotonesAcciones.tsx · etiquetas.ts
    │   └── formularios/CapturaMotivo.tsx · FormularioCatalogo.tsx · ConflictoEnLinea.tsx · ConfirmacionBaja.tsx · motivo.formulario.ts
    ├── components/ui/               shadcn copiado
    ├── lib/utils.ts                 shadcn
    ├── modulos/
    │   ├── identidad/PaginaInicioSesion.tsx · inicio-sesion.formulario.ts
    │   ├── presupuesto/rutas.tsx · analitica/rutas.tsx · compras/rutas.tsx
    │   └── proveedores/rutas.tsx · almacen/rutas.tsx · auditoria/rutas.tsx
    └── pruebas/preparacion.ts · servidor.ts · cuerpos.ts · render.tsx
```

Las pruebas de componente viven junto a su componente (`X.test.tsx`). `src/index.ts` se borra.

### Configuración

**`package.json`, `scripts`**, literal:

```json
{
  "dev": "vite",
  "build": "vite build",
  "lint": "eslint .",
  "typecheck": "tsc --noEmit",
  "test": "vitest run",
  "tipos:generar": "node scripts/tipos.ts generar",
  "tipos:verificar": "node scripts/tipos.ts verificar",
  "e2e": "playwright test"
}
```

Node 24 ejecuta `.ts` con el borrado de tipos que trae por omisión: por eso `tsconfig.json` exige `erasableSyntaxOnly` (nada de `enum`, de `namespace` ni de propiedades de parámetro en constructores, en todo el proyecto).

**`tsconfig.json`**, literal:

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "erasableSyntaxOnly": true,
    "types": ["node", "vite/client"],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src", "scripts", "e2e", "vite.config.ts", "playwright.config.ts"]
}
```

**`vite.config.ts`**, literal:

```ts
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export const DESTINO_API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { tsconfigPaths: true },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    // Sin changeOrigin: el backend ve Host localhost:5173, el mismo origen que la cookie y que el Origin (TKT-057).
    proxy: { "/api": { target: DESTINO_API } },
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "cliente",
          environment: "jsdom",
          include: ["src/**/*.test.{ts,tsx}"],
          setupFiles: ["./src/pruebas/preparacion.ts"],
          restoreMocks: true,
        },
      },
      { extends: true, test: { name: "herramientas", environment: "node", include: ["scripts/**/*.test.ts"] } },
    ],
  },
});
```

Regla de salida: si la versión instalada de Vite no reconoce `resolve.tsconfigPaths` (el alias `@/` no resuelve en `npm run build`), se sustituye por `resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } }` con `import { fileURLToPath } from "node:url"`, y la fila queda `⚠ Ajustado`.

**`eslint.config.js`**, literal:

```js
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

const MENSAJE_NUMERO =
  "Prohibido fuera de src/compartido/dinero (regla 1, PA-T11): los importes y las cantidades pasan por decimal.js.";
const NUMERO = [
  { selector: "CallExpression[callee.type='Identifier'][callee.name=/^(Number|parseFloat|parseInt)$/]", message: MENSAJE_NUMERO },
  { selector: "NewExpression[callee.type='Identifier'][callee.name='Number']", message: MENSAJE_NUMERO },
  { selector: "MemberExpression[object.name='Number'][property.name=/^parse(Float|Int)$/]", message: MENSAJE_NUMERO },
  { selector: "UnaryExpression[operator='+']", message: MENSAJE_NUMERO },
];
const COOKIE = {
  selector: "MemberExpression[object.name='document'][property.name='cookie']",
  message: "Prohibido leer document.cookie (RNF-02, regla 9): quién es el usuario se pregunta a GET /sesion.",
};
const DECIMAL = { group: ["decimal.js"], message: "decimal.js solo se importa en src/compartido/dinero (M9)." };
const ZOD = {
  group: ["zod", "zod/*"],
  message: "Zod solo valida formularios: *.formulario.ts o src/compartido/formularios (CA-13).",
};

export default defineConfig(
  { ignores: ["dist/", "src/api/generado/", "playwright-report/", "test-results/"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    plugins: { "react-hooks": reactHooks },
    rules: { "react-hooks/rules-of-hooks": "error", "react-hooks/exhaustive-deps": "error" },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": ["error", ...NUMERO, COOKIE],
      "no-restricted-imports": ["error", { patterns: [DECIMAL, ZOD] }],
    },
  },
  {
    files: ["src/compartido/dinero/**/*.ts"],
    rules: {
      "no-restricted-syntax": ["error", COOKIE],
      "no-restricted-imports": ["error", { patterns: [ZOD] }],
    },
  },
  {
    files: ["src/**/*.formulario.ts", "src/compartido/formularios/**/*.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    rules: { "no-restricted-imports": ["error", { patterns: [DECIMAL] }] },
  },
);
```

El `+` unario entra en la prohibición porque es la forma más común de saltársela (D-3). La generación queda fuera de ESLint; su integridad la vigila `tipos:verificar`.

**`.gitignore`**, bajo `# Node`: `frontend/playwright-report/` y `frontend/test-results/`.

### Frontend · generación de tipos (`scripts/tipos.ts`)

Firmas y constantes literales; el cuerpo de cada función sigue su docstring.

```ts
export const ARCHIVO_SERVIDOR = "src/api/generado/servidor.ts";
export const ARCHIVO_CONTRATO_ERROR = "src/api/generado/contrato-error.provisional.ts";
export const RAICES_CONTRATO_ERROR = [
  "ErrorConflicto", "ErrorReglaNegocio", "ErrorConflictoEstado", "ErrorConcurrencia", "ErrorValidacion",
  "ErrorPermiso", "ErrorSesion", "ErrorLimiteIntentos", "ErrorNoEncontrado",
] as const;

export const CABECERA_SERVIDOR = [
  "// Generado por `npm run tipos:generar` del OpenAPI que publica FastAPI",
  "// (servidor.fabrica.crear_aplicacion, sin servidor en marcha). No se edita a mano:",
  "// `npm run tipos:verificar` falla si este archivo difiere de lo que se generaría.",
  "", "",
].join("\n");
export const CABECERA_PROVISIONAL = [
  "// PROVISIONAL (TKT-008, PA-T1). Tipos del contrato de error generados del borrador",
  "// docs/api/openapi.yaml, porque el OpenAPI que publica FastAPI todavía no declara los",
  "// esquemas de error. Se retira cuando el servidor los publique con responses= en cada",
  "// ruta (ticket futuro, antes de TKT-061). Generado por `npm run tipos:generar`.",
  "// No se edita a mano: `npm run tipos:verificar` lo detecta.",
  "", "",
].join("\n");

const CODIGO_EXPORTACION = [
  "import json, sys",
  "from servidor.fabrica import crear_aplicacion",
  "esquema = crear_aplicacion(destino_registro=sys.stderr, entorno={}).openapi()",
  "sys.stdout.write(json.dumps(esquema, ensure_ascii=True))",
].join("\n");

export type Documento = Record<string, unknown>;
export type Ejecutar = (comando: string, argumentos: string[], cwd: string) =>
  { status: number | null; stdout: string; stderr: string };

/** M2 · PA-T10. Ejecuta `uv run --locked python -c CODIGO_EXPORTACION` con cwd = backend/ y devuelve el
 *  JSON. Estado distinto de 0: lanza Error con «No se pudo exportar el OpenAPI publicado: hace falta uv y
 *  `uv sync --locked` en backend/ (PA-T10).» seguido del stderr. ensure_ascii evita la página de códigos
 *  de la consola de Windows. Por omisión `ejecutar` es spawnSync con encoding utf8, shell false y
 *  maxBuffer de 64 MiB. */
export function exportarOpenapiPublicado(ejecutar?: Ejecutar): Documento;

/** Copia profunda: todo objeto con `const` y sin `enum` gana `enum: [const]`. */
export function constComoEnum(nodo: unknown): unknown;

/** Documento OpenAPI con `openapi` e `info.version` del borrador, `info.title` = «CIMENTA · contrato de
 *  error (provisional)», `paths: {}` y en `components.schemas` las RAICES y todo lo que alcanzan por
 *  `$ref: '#/components/schemas/X'`, recorrido a cualquier profundidad, con las claves en orden
 *  alfabético. Un $ref que no existe en el borrador lanza Error nombrándolo. */
export function subconjuntoContratoError(borrador: Documento): Documento;

/** Devuelve las dos rutas con su contenido: cabecera + astToString(await openapiTS(constComoEnum(doc))),
 *  con \r\n → \n y exactamente un \n final. */
export async function generarArchivos(entradas: { publicado: Documento; borrador: Documento }):
  Promise<Map<string, string>>;

/** Rutas cuyo contenido en disco (leer devuelve null si no existe) difiere del generado, en el orden de
 *  ARCHIVO_SERVIDOR, ARCHIVO_CONTRATO_ERROR. */
export function diferencias(generados: Map<string, string>, leer: (ruta: string) => string | null): string[];

/** El modo `generar` o `verificar` completo, con sus dependencias inyectables; devuelve el código de
 *  salida de la tabla de abajo y escribe sus mensajes con `escribir` y `escribirError`. Por omisión
 *  exporta con uv, lee el borrador del disco y lee y escribe los archivos reales. El bloque principal
 *  solo hace `process.exitCode = await principal(process.argv.slice(2))`. */
export async function principal(
  argumentos: string[],
  dependencias?: {
    exportar?: () => Documento;
    leerBorrador?: () => Documento;
    leer?: (ruta: string) => string | null;
    escribirArchivo?: (ruta: string, contenido: string) => void;
    escribir?: (linea: string) => void;
    escribirError?: (linea: string) => void;
  },
): Promise<number>;
```

El bloque principal corre solo si `process.argv[1] === fileURLToPath(import.meta.url)`. Códigos de salida, fijos:

| Código | Cuándo | Salida |
|---|---|---|
| 0 | `generar` escribió los dos archivos (creando `src/api/generado/`); o `verificar` no encontró diferencias | `Tipos al día.` en `verificar` |
| 1 | `verificar` encontró diferencias | Una línea `Difiere: <ruta>` por archivo y `Ejecuta npm run tipos:generar y versiona el resultado.` |
| 2 | No se pudo **generar**, en cualquiera de los dos modos: `exportarOpenapiPublicado` lanzó (falta `uv`, `uv sync` sin hacer, o la fábrica no construye), el borrador no se lee o `openapiTS` lanza | `No se pudieron generar los tipos: <mensaje>` en la salida de error. Nunca se confunde con un desfase |
| 3 | Argumento distinto de `generar` o `verificar` | El uso |

Si TKT-057 hace que `crear_aplicacion` exija secretos, el mensaje de `exportarOpenapiPublicado` incluye el `stderr` de Python, que nombra la variable que falta, y el código es 2: la verificación no puede pasar en verde por una exportación que no ocurrió. La llamada a `openapiTS` recibe el objeto con `as Parameters<typeof openapiTS>[0]`, la única aserción de tipo del script.

### Frontend · dinero (`src/compartido/dinero/dinero.ts`)

Literal salvo comentarios:

```ts
import DecimalBase from "decimal.js";

/** Precisión holgada para totales de presentación; el redondeo de presentación es ROUND_HALF_UP (PA-T5). */
export const Decimal = DecimalBase.clone({ precision: 40, rounding: DecimalBase.ROUND_HALF_UP });
export type Decimal = InstanceType<typeof Decimal>;

const DECIMAL_PLANO = /^-?\d+(\.\d+)?$/;
const ENTERO_NO_NEGATIVO = /^\d{1,9}$/;
const FORMATO_IMPORTE = new Intl.NumberFormat("es-MX", {
  style: "currency", currency: "MXN", minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const FORMATO_CANTIDAD = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Cadena decimal plana del API → Decimal; cualquier otra forma (exponente, Infinity, NaN, hexadecimal, vacío) → null. */
export function aDecimal(valor: string): Decimal | null {
  return DECIMAL_PLANO.test(valor) ? new Decimal(valor) : null;
}

function aDosDecimales(valor: string | Decimal): Intl.StringNumericLiteral | null {
  const d = typeof valor === "string" ? aDecimal(valor) : valor;
  return d === null ? null : (d.toFixed(2, Decimal.ROUND_HALF_UP) as Intl.StringNumericLiteral);
}

/** "1234.5650" → "$1,234.57". Redondea solo aquí; Intl recibe la cadena ya redondeada, nunca un number. */
export function formatearImporte(valor: string | Decimal): string | null {
  const texto = aDosDecimales(valor);
  return texto === null ? null : FORMATO_IMPORTE.format(texto);
}

/** "100.0000", "PZA" → "100.00 PZA". */
export function formatearCantidad(valor: string | Decimal, unidad?: string): string | null {
  const texto = aDosDecimales(valor);
  if (texto === null) return null;
  const cifra = FORMATO_CANTIDAD.format(texto);
  return unidad === undefined ? cifra : `${cifra} ${unidad}`;
}

/** Cabecera Retry-After en segundos → entero; cualquier otra forma → null. Vive aquí porque este
 *  módulo es el único exento de la prohibición de conversiones numéricas (PA-T11). */
export function enteroNoNegativo(texto: string | null): number | null {
  return texto !== null && ENTERO_NO_NEGATIVO.test(texto) ? new Decimal(texto).toNumber() : null;
}
```

Regla de salida: si TypeScript no acepta `Intl.StringNumericLiteral` con la `lib` declarada, la aserción pasa a `` `${number}` `` y se anota.

### Frontend · contrato de error (`src/api/errores.ts`)

```ts
import type { components } from "@/api/generado/contrato-error.provisional";
import { enteroNoNegativo } from "@/compartido/dinero/dinero";

type Esquemas = components["schemas"];
export type Accion = Esquemas["Accion"];
export type ErrorReglaNegocio = Esquemas["ErrorReglaNegocio"];
export type ErrorConflictoEstado = Esquemas["ErrorConflictoEstado"];
export type ErrorConcurrencia = Esquemas["ErrorConcurrencia"] & { reintentar_tras_s: number | null };
export type ErrorValidacion = Esquemas["ErrorValidacion"];
export type ErrorPermiso = Esquemas["ErrorPermiso"];
export type ErrorSesion = Esquemas["ErrorSesion"];
export type ErrorLimiteIntentos = Esquemas["ErrorLimiteIntentos"];
export type ErrorNoEncontrado = Esquemas["ErrorNoEncontrado"];
/** Fuera del contrato: 500, cuerpo que no es JSON, `tipo` desconocido o que no casa con su código. */
export type ErrorGenerico = { tipo: "GENERICO"; estado: number; mensaje: string | null; correlacion_id: string | null };
/** La petición no llegó al servidor. Distinto de cualquier tipo del contrato y de un 401 (CA-4 esc. 3). */
export type ErrorRed = { tipo: "RED" };

/** La entrada de la pantalla de bloqueo: solo los 409 (CA-9 esc. 4). */
export type ErrorBloqueo = ErrorReglaNegocio | ErrorConflictoEstado | ErrorConcurrencia;
export type ErrorApi =
  | ErrorBloqueo | ErrorValidacion | ErrorPermiso | ErrorSesion | ErrorLimiteIntentos | ErrorNoEncontrado
  | ErrorGenerico | ErrorRed;

export const ESTADO_DE_TIPO = {
  REGLA_NEGOCIO: 409, CONFLICTO: 409, CONCURRENCIA: 409, VALIDACION: 422,
  PERMISO: 403, SESION: 401, LIMITE_INTENTOS: 429, NO_ENCONTRADO: 404,
} as const;

export function esObjeto(valor: unknown): valor is Record<string, unknown>;   // objeto no nulo y no arreglo

/** M3 · CA-4. Un cuerpo es del contrato si y solo si es un objeto con `tipo` en ESTADO_DE_TIPO, ese tipo
 *  corresponde al código de estado recibido y `mensaje` es cadena; entonces se devuelve tal cual llegó
 *  (las acciones conservan orden y ruta), y CONCURRENCIA añade `reintentar_tras_s` =
 *  enteroNoNegativo(cabeceras.get("Retry-After")). Todo lo demás es GENERICO con `mensaje` y
 *  `correlacion_id` solo si son cadenas del cuerpo. No valida el resto de la forma con ningún esquema
 *  escrito a mano (CA-13 esc. 4): la forma la garantizan los tipos generados y TKT-061. Nunca lanza. */
export function normalizarError(estado: number, cuerpo: unknown, cabeceras: Headers): ErrorApi;
```

Las dos aserciones (`cuerpo as unknown as ...`) se concentran en `normalizarError`, después de la comprobación del discriminador, con un comentario que lo dice.

### Frontend · cliente (`src/api/cliente.ts`)

Literal salvo comentarios:

```ts
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@/api/generado/servidor";
import { type ErrorApi, normalizarError } from "@/api/errores";

export const CABECERA_CSRF = "X-CSRF-Token";
const METODOS_QUE_MUTAN = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const RUTA_INICIO = "/api/v1/sesion";
const RUTA_CIERRE = "/api/v1/sesion/cierre";

export type ResultadoApi<T> = { ok: true; datos: T } | { ok: false; error: ErrorApi };

export class FalloApi extends Error {
  readonly error: ErrorApi;
  constructor(error: ErrorApi) {
    super(error.tipo);
    this.error = error;
  }
}

/** RNF-05 · CA-3. Toda mutación lleva X-CSRF-Token; un GET, nunca. */
export async function aplicarCsrf(request: Request, obtenerToken: () => Promise<string>): Promise<Request> {
  if (!METODOS_QUE_MUTAN.has(request.method)) return request;
  request.headers.set(CABECERA_CSRF, await obtenerToken());
  return request;
}

export interface OpcionesCliente {
  baseUrl: string;
  /** Un 401 que no sea del propio inicio ni del cierre de sesión (CA-5 esc. 1 y 3). */
  alTerminarSesion: () => void;
  /** Cualquier 403: el armazón vuelve a preguntar quién es (CA-5 esc. 4, RNF-01). */
  alDenegarPermiso: () => void;
}

export function crearClienteApi(opciones: OpcionesCliente) {
  const cliente = createClient<paths>({
    baseUrl: opciones.baseUrl,
    credentials: "same-origin",
    // Se lee globalThis.fetch en cada llamada, no al crear el cliente: así lo intercepta MSW en pruebas.
    fetch: (request: Request) => globalThis.fetch(request),
  });
  let token: Promise<string> | null = null;
  async function pedirToken(): Promise<string> {
    const { data, response } = await cliente.GET("/api/v1/sesion/csrf");
    if (!response.ok || data === undefined) throw new Error("No se obtuvo el token CSRF");
    return data.token; // PA-T9: del cuerpo, nunca de la cookie
  }
  function obtenerToken(): Promise<string> {
    // Dos mutaciones simultáneas comparten una sola petición del token.
    token ??= pedirToken().catch((error: unknown) => {
      token = null;
      throw error;
    });
    return token;
  }
  const middleware: Middleware = {
    onRequest: ({ request }) => aplicarCsrf(request, obtenerToken),
    onResponse: ({ request, response }) => {
      const ruta = new URL(request.url).pathname;
      const esDeSesion = request.method === "POST" && (ruta === RUTA_INICIO || ruta === RUTA_CIERRE);
      if (esDeSesion) token = null; // PA-T9: se vuelve a pedir tras iniciar y tras cerrar
      if (response.status === 401 && !esDeSesion) opciones.alTerminarSesion();
      if (response.status === 403) {
        // Un 403 puede ser ORIGEN_NO_VERIFICADO (token viejo o ausente): se descarta el token sin leer
        // el cuerpo; en un ROL_INSUFICIENTE cuesta un GET de más en la siguiente mutación.
        token = null;
        opciones.alDenegarPermiso();
      }
      return undefined;
    },
  };
  cliente.use(middleware);
  return cliente;
}

export type ClienteApi = ReturnType<typeof crearClienteApi>;

/** M3. Nunca lanza: el error de red es RED; toda respuesta no 2xx se normaliza. */
export async function pedir<T>(
  llamada: () => Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<ResultadoApi<T>> {
  let resultado: { data?: T; error?: unknown; response: Response };
  try {
    resultado = await llamada();
  } catch {
    return { ok: false, error: { tipo: "RED" } };
  }
  const { data, error, response } = resultado;
  if (!response.ok) return { ok: false, error: normalizarError(response.status, error, response.headers) };
  return { ok: true, datos: data as T }; // en un 204, T es el tipo vacío que declara openapi-fetch
}

/** Para queryFn: devuelve los datos o lanza FalloApi, que TanStack Query guarda como error de la consulta. */
export function exigir<T>(resultado: ResultadoApi<T>): T {
  if (!resultado.ok) throw new FalloApi(resultado.error);
  return resultado.datos;
}
```

`src/api/sesion.ts`: `claves = { sesion: ["sesion"] as const }`; `type UsuarioActual = components["schemas"]["UsuarioActual"]` del archivo del servidor; `type Rol = UsuarioActual["roles"][number]`; `sesionOptions = (api: ClienteApi) => queryOptions({ queryKey: claves.sesion, queryFn: async () => exigir(await pedir(() => api.GET("/api/v1/sesion"))), staleTime: 30_000 })`. **Excepción declarada a `conv-frontend-react` §4** («toda dependencia de la función de consulta va en la clave»): la instancia del cliente `api` no entra en la clave. La regla existe para que dos registros distintos no compartan caché; `api` no selecciona ningún registro, es el transporte, y cada `QueryClient` convive con exactamente un `api` porque los dos nacen juntos en `crearAplicacion`. Meterla en la clave tampoco es posible: no es serializable. Los parámetros de datos (un `obra_id`, una página) sí van siempre en la clave. La excepción se añade a la convención (D-11) para que el auditor no la marque.

`src/api/ProveedorApi.tsx`: `ContextoApi = createContext<ClienteApi | null>(null)`, `ProveedorApi({ api, children })` y `useApi()`, que lanza `Error("useApi fuera de ProveedorApi")` si no hay proveedor.

### Frontend · aplicación y rutas

**`src/app/crear-aplicacion.tsx`**: `crearAplicacion(opciones: { rutaInicial?: string } = {}): { elemento: ReactElement; router: Router; queryClient: QueryClient; api: ClienteApi }`, con `type Router = ReturnType<typeof createBrowserRouter>`.

1. `queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })`.
2. `api = crearClienteApi({ baseUrl: globalThis.location.origin, alTerminarSesion: terminarSesion, alDenegarPermiso: () => void queryClient.invalidateQueries({ queryKey: claves.sesion }) })`.
3. `router = opciones.rutaInicial === undefined ? createBrowserRouter(rutas) : createMemoryRouter(rutas, { initialEntries: [opciones.rutaInicial] })`.
4. `terminarSesion()`: `const habia = queryClient.getQueryData(claves.sesion) !== undefined`; si la ruta actual no es `RUTA_INICIO_SESION`, `void router.navigate(RUTA_INICIO_SESION, { replace: true, state: habia ? { aviso: "SESION_TERMINADA" } : null })`; después `queryClient.clear()`. **El aviso sale si y solo si había un usuario cargado** (D-6): la primera visita no lo tenía (`CA-5` esc. 2) y quien está dentro del armazón sí (`CA-5` esc. 1).
5. `elemento = <ProveedorApi api={api}><QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider></ProveedorApi>`.

`src/main.tsx` monta `crearAplicacion().elemento` dentro de `<StrictMode>` sobre `#raiz`; si falta, lanza `Error("Falta #raiz en index.html")`.

**`src/app/rutas.tsx`**: `RUTA_INICIO_SESION = "/inicio-sesion"` y

```tsx
export const rutas: RouteObject[] = [
  { path: RUTA_INICIO_SESION, Component: PaginaInicioSesion },
  {
    path: "/",
    Component: Armazon,
    children: [
      { index: true, Component: InicioArmazon },
      ...rutasAnalitica, ...rutasPresupuesto, ...rutasCompras, ...rutasProveedores, ...rutasAlmacen, ...rutasAuditoria,
      { path: "*", Component: NoEncontrado },
    ],
  },
];
```

**`src/app/navegacion/secciones.ts`** — la tabla del wireframe §2, unión de *Opera* y *Consulta*, en su orden. Literal:

```ts
export type ClaveSeccion =
  | "SEMAFORO" | "LINEA_BASE" | "PRESUPUESTO_CONTROL" | "REQUISICIONES" | "ORDENES_COMPRA"
  | "PROVEEDORES" | "RECEPCION" | "AUTORIZACIONES" | "BITACORA";

export interface Seccion {
  clave: ClaveSeccion;
  grupo: "Obra" | "Compras" | "Almacén" | "Dirección";
  titulo: string;
  ruta: string;
  roles: readonly Rol[];
}

const TODOS: readonly Rol[] = ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"];

/** M5 · wireframe §2. Cortesía de navegación (PA-T8): el control real es el 403 del servidor. */
export const SECCIONES: readonly Seccion[] = [
  { clave: "SEMAFORO", grupo: "Obra", titulo: "Semáforo", ruta: "/obra/semaforo", roles: ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "LINEA_BASE", grupo: "Obra", titulo: "Línea base", ruta: "/obra/linea-base", roles: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL", "COMPRAS"] },
  { clave: "PRESUPUESTO_CONTROL", grupo: "Obra", titulo: "Presupuesto de control", ruta: "/obra/presupuesto-control", roles: ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "COMPRAS"] },
  { clave: "REQUISICIONES", grupo: "Compras", titulo: "Requisiciones", ruta: "/compras/requisiciones", roles: ["COMPRAS", "DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "ORDENES_COMPRA", grupo: "Compras", titulo: "Órdenes de compra", ruta: "/compras/ordenes-compra", roles: ["COMPRAS", "ALMACEN", "RESIDENTE", "DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "PROVEEDORES", grupo: "Compras", titulo: "Proveedores", ruta: "/compras/proveedores", roles: TODOS },
  { clave: "RECEPCION", grupo: "Almacén", titulo: "Recepción · Pendientes de recibir", ruta: "/almacen/recepcion", roles: ["ALMACEN", "RESIDENTE", "COMPRAS", "DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "AUTORIZACIONES", grupo: "Dirección", titulo: "Autorizaciones", ruta: "/direccion/autorizaciones", roles: ["DIRECCION_GENERAL"] },
  { clave: "BITACORA", grupo: "Dirección", titulo: "Bitácora de excepciones", ruta: "/direccion/bitacora", roles: ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
];

export const NOMBRE_ROL: Readonly<Record<Rol, string>> = {
  DIRECCION_GENERAL: "Dirección General", DIRECTOR_PROYECTOS: "Director de Proyectos", RESIDENTE: "Residente de obra",
  COMPRAS: "Compras", ALMACEN: "Almacén", ADMINISTRACION: "Administración",
};

/** La unión de los roles, en el orden de la tabla y sin repetir (CA-7 esc. 2). */
export function seccionesDe(roles: readonly Rol[]): Seccion[] {
  return SECCIONES.filter((s) => s.roles.some((r) => roles.includes(r)));
}
/** PA-T2: la primera de la tabla que permite alguno de los roles; null sin roles. */
export function primeraSeccion(roles: readonly Rol[]): Seccion | null {
  return seccionesDe(roles)[0] ?? null;
}
export function seccionPermitida(clave: ClaveSeccion, roles: readonly Rol[]): boolean {
  return seccionesDe(roles).some((s) => s.clave === clave);
}
export function seccion(clave: ClaveSeccion): Seccion;   // la de SECCIONES; lanza si no existe
```

Los nombres de rol son los de la semilla `v0002`. **`src/app/navegacion/ruta-marcador.tsx`**: `rutaMarcador(clave: ClaveSeccion): RouteObject` devuelve `{ path: seccion(clave).ruta.slice(1), element: <GuardaSeccion clave={clave}><SeccionMarcador clave={clave} /></GuardaSeccion> }`.

**Rutas por módulo**, cada una un arreglo de `rutaMarcador`: `analitica` → `SEMAFORO`; `presupuesto` → `LINEA_BASE`, `PRESUPUESTO_CONTROL`; `compras` → `REQUISICIONES`, `ORDENES_COMPRA`, `AUTORIZACIONES` (en la tabla de módulos de `docs/02-arquitectura.md`, la solicitud de autorización es de `compras`); `proveedores` → `PROVEEDORES`; `almacen` → `RECEPCION`; `auditoria` → `BITACORA`. `identidad` aloja la pantalla de inicio.

### Frontend · vistas y componentes

Textos literales: las pruebas los buscan tal cual.

| Componente o vista | Datos | Estados |
|---|---|---|
| `Armazon` | `useQuery(sesionOptions(useApi()))` | **cargando**: `<div aria-busy="true" aria-label="Cargando la sesión">` con esqueleto · **error** distinto de `SESION`: «No se pudo cargar la sesión.» y botón «Reintentar» (`refetch`); con `RED`, además «Sin conexión con el servidor.» · error `SESION`: no pinta nada (navega el *middleware*) · **vacío**: sin roles, `InicioArmazon` dice «No tienes secciones asignadas. Pide a un administrador que te asigne un rol.» (`PA-T3`) · **bloqueado**: no aplica |
| `Armazon`, cabecera | `nombre`, `roles`, `sesion` | «CIMENTA»; el nombre; los roles con `NOMBRE_ROL` unidos por « · »; «Sesión vigente hasta» + `<time dateTime={iso}>` con el **menor** de `expira_en` y `expira_por_inactividad_en` (comparados con `Date.parse`), presentado con `Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" })`; botón «Salir» |
| `Armazon`, menú | `seccionesDe(roles)` | `<nav id="menu-secciones" aria-label="Secciones">`, un encabezado por grupo con secciones, un `NavLink` por sección. Botón «≡» con `aria-label="Menú"`, `aria-controls="menu-secciones"`, `aria-expanded` y clase `md:hidden`; el `nav` lleva `data-abierto` y clases `hidden md:block` cerrado o `block` abierto; elegir una sección lo cierra |
| *Salir* | `POST /api/v1/sesion/cierre` por `pedir` | Si `ok` o el error es `SESION`: `await navigate(RUTA_INICIO_SESION, { replace: true })` y después `queryClient.clear()`, sin aviso. Con otro error: «No se pudo cerrar la sesión. Inténtalo de nuevo.» y se queda |
| `InicioArmazon` | `primeraSeccion(roles)` | `<Navigate to={ruta} replace />`; sin roles, el aviso de la fila de arriba |
| `GuardaSeccion({ clave, children })` | roles de la caché | Si `seccionPermitida`, `children`; si no, `AvisoSinPermiso` |
| `AvisoSinPermiso` | ninguno | `<h1>No tienes permiso para esta sección</h1>`, sin cifras. Exportado para que cada pantalla pinte su `403` igual |
| `SeccionMarcador({ clave })` | `seccion(clave)` | `<h1>{titulo}</h1>` y «Esta sección aún no está disponible.» |
| `NoEncontrado` | ninguno | Dentro del armazón: `<h1>Página no encontrada</h1>` y enlace «Ir al inicio» a `/` |
| `PaginaInicioSesion` | `POST /api/v1/sesion` por `pedir`; luego `queryClient.fetchQuery({ ...sesionOptions(api), staleTime: 0 })` | Ver abajo |
| `PantallaBloqueo` | el `ErrorBloqueo` que recibe | **bloqueado**, con su propio tratamiento visual (ámbar, `data-estado="bloqueado"`), nunca el rojo de error |
| `FormularioCatalogo` | lo que devuelve `alGuardar` | **cargando** (en vuelo) · **error** en la cabecera · **bloqueado** en línea o delegado |
| `CapturaMotivo` | lo que devuelve `alConfirmar` | **cargando** (en vuelo) · **error** junto al campo · rechazo delegado |

**`PaginaInicioSesion`.** Esquema en `inicio-sesion.formulario.ts`: `esquemaInicioSesion = z.object({ email: z.email("Escribe un correo válido."), contrasena: z.string().min(1, "Escribe tu contraseña.") })`. Campos con etiqueta «Correo» y «Contraseña» (`type="password"`), botón «Iniciar sesión». Un solo `div role="alert"` para el mensaje general.

| Situación | Comportamiento literal |
|---|---|
| `location.state` con `aviso === "SESION_TERMINADA"` | «Tu sesión terminó. Vuelve a iniciarla.» |
| En vuelo | Botón `disabled` mientras `formState.isSubmitting` (`RNF-03`) |
| `ok` | `fetchQuery` de la sesión y `navigate(primeraSeccion(roles)?.ruta ?? "/", { replace: true })` |
| `SESION` con `CREDENCIALES_INVALIDAS` | «Correo o contraseña incorrectos.»; `setValue("contrasena", "")`; el correo se conserva; sin redirección |
| `VALIDACION` | Cada `errores[i]` con `campo` `email` o `contrasena` va con `setError(campo, { type: "servidor", message })`; los demás, al mensaje general |
| `LIMITE_INTENTOS` | «Demasiados intentos fallidos. Vuelve a intentarlo en {describirEspera(s)}.» con `describirEspera(s)` = `s >= 60` ? `Math.ceil(s / 60)` + « minuto» o « minutos» : `s` + « segundo» o « segundos»; botón `disabled` con texto «Iniciar sesión (mm:ss)» por `useCuentaAtras(reintentar_en_s)`; se rehabilita en 0 |
| `useEnLinea()` falso | Botón `disabled` y «Sin conexión. Para iniciar sesión hace falta conexión con el servidor.»; no se envía nada |
| `PERMISO` con `ORIGEN_NO_VERIFICADO` | «No se pudo verificar el origen de la petición. Recarga la página para continuar.» y botón «Recargar» (`window.location.reload()`); no reintenta |
| `RED` | «No se pudo conectar con el servidor. Inténtalo de nuevo.» |
| Cualquier otro | «No se pudo iniciar sesión.» y, si hay `correlacion_id`, « Referencia: {id}» |

`useCuentaAtras(segundos: number | null): number` devuelve los segundos restantes, decrementa con un `setInterval` de 1,000 ms y se limpia al desmontar; `formatearCuentaAtras(s)` da `mm:ss` con `padStart`. `useEnLinea(): boolean` usa `useSyncExternalStore` sobre los eventos `online` y `offline` de `window` y `navigator.onLine`.

**`PantallaBloqueo`**, contrato literal:

```ts
export interface PropsPantallaBloqueo {
  error: ErrorBloqueo;                    // solo los 409: un 422 o un 403 no compilan (CA-9 esc. 4)
  alAccion: (accion: Accion) => void;     // entrega la acción tal como llegó, sin invocarla
  alCerrar: () => void;
  alReintentar?: () => void;              // la pantalla que la abrió repite su petición original
}
```

- Contenedor `<section aria-labelledby="titulo-bloqueo" data-estado="bloqueado">`. Cabecera `<h2 id="titulo-bloqueo">`: «Operación bloqueada» y, aparte, «Regla {regla}» (`REGLA_NEGOCIO`); «No se puede completar» y el `codigo` (`CONFLICTO`); «Inténtalo de nuevo» (`CONCURRENCIA`). Cuerpo: `mensaje` tal cual.
- `DetalleCifras({ detalle })` pinta un `<dl>`. Recorre primero las claves conocidas de `CLAVES_DETALLE` de `etiquetas.ts`, en este orden: `obra` «Obra», `tipo_partida` «Tipo de partida», `folio` «Folio», `folio_orden` «Orden de compra», `estado` «Estado», `causa` «Causa» (texto); `presupuestado` «Presupuestado», `consumido` «Consumido», `disponible` «Disponible», `solicitado` «Solicitado», `excedente` «Excedente» (importe). `consumido_desglose` va dentro de la fila de *Consumido*: «requisiciones vivas {importe} · comprometido {importe} · ejercido {importe}». Después, las tablas `insumos` (Insumo, Presupuestado, Consumido, Disponible, Solicitado, Excedente, cada cantidad con su `unidad`; si `presupuestado_en_partida` es `false`, la fila añade «no presupuestado en esta partida»), `renglones` (Insumo, Ordenado, Recibido, Saldo pendiente, Entrante, Excedente) y `renglones_con_saldo` (Insumo, Saldo pendiente, Fecha compromiso). Las claves `requisicion_id`, `solicitud_autorizacion_id`, `orden_compra_id`, `insumo_id` y `orden_compra_renglon_id` no se pintan (D-8). Al final, toda clave desconocida en su orden de llegada, con su nombre crudo como `<dt>` y su valor: la cadena tal cual, o `JSON.stringify` si no es cadena (`CA-8` esc. 4).
- Un importe o una cantidad cuyo formateo devuelve `null` se muestra «No disponible» (`CA-8` esc. 5). El `<dd>` del excedente lleva `data-resaltada="true"` y el marcador visual «◄»; su valor es el que llegó, sin restar nada.
- `BotonesAcciones({ acciones, alAccion, reintento? })`: un botón por acción, en su orden, rotulado con `ETIQUETAS_ACCION[clave] ?? clave` (D-7): `VER_SOLICITUD_AUTORIZACION` «Ver solicitud de autorización», `SOLICITAR_AUTORIZACION` «Solicitar autorización», `CANCELAR_REQUISICION` «Cancelar la requisición», `REPROGRAMAR` «Reprogramar», `CONGELAR_LINEA_BASE` «Congelar la línea base», `CAPTURAR_PRESUPUESTO_CONTROL` «Capturar el presupuesto de control», `CONFIRMAR_REEMPLAZO` «Confirmar el reemplazo», `CONFIRMAR_TOPE_SUPERIOR` «Confirmar el tope», `VER_ENTRADA` «Ver la entrada», `REINTENTAR` «Reintentar». Después, el botón fijo «Cerrar».
- `REINTENTAR` queda `disabled` mientras `useCuentaAtras(error.reintentar_tras_s)` sea mayor que cero; al pulsarlo, si hay `alReintentar` se llama a ella y **no** a `alAccion`; si no la hay, se entrega con `alAccion` como cualquier otra (`CA-9` esc. 3).
- Pie: «Referencia: {correlacion_id}».

**`CapturaMotivo`**, contrato literal:

```ts
export interface PropsCapturaMotivo {
  abierta: boolean;
  titulo: string;
  descripcion?: string;
  etiquetaConfirmar: string;
  alConfirmar: (motivo: string) => Promise<ResultadoApi<unknown>>;   // la pantalla envía; RN-04
  alHecho: () => void;
  alRechazo: (error: ErrorApi) => void;                               // 409 y demás: los pinta la pantalla
  alCancelar: () => void;
}
```

`Dialog` de shadcn con `open={abierta}`; al cerrarse por teclado o por fuera llama a `alCancelar`. `motivo.formulario.ts`: `esquemaMotivo = z.object({ motivo: z.string().trim().min(1, "El motivo es obligatorio.").max(2000, "El motivo admite hasta 2,000 caracteres.") })`. Campo `Textarea` con etiqueta «Motivo» y foco al abrir. Botón con `etiquetaConfirmar`, `disabled` mientras está en vuelo, y «Cancelar». Resultado `ok` → `alHecho()`. `VALIDACION` con un error en `motivo` → `setError("motivo", { type: "servidor", message: <el del servidor> })` y el texto se conserva; los errores de otros campos, en un `div role="alert"` del diálogo. Cualquier otro error → `alRechazo(error)` sin mensaje propio.

**`FormularioCatalogo`**, contrato literal:

```ts
export interface CampoCatalogo<N extends string> {
  nombre: N;
  etiqueta: string;
  tipo?: "text" | "email" | "date";          // "text" por omisión; los importes son texto
}
export interface BajaCatalogo {
  etiqueta: string;                          // p. ej. «Dar de baja»
  pregunta: string;                          // texto de la confirmación
  exigeMotivo: boolean;                      // PA-T12
  alConfirmar: (motivo: string | null) => Promise<ResultadoApi<unknown>>;
  alHecha: () => void;
}
export interface PropsFormularioCatalogo<E extends z.ZodObject, R> {
  abierto: boolean;
  titulo: string;
  esquema: E;
  campos: ReadonlyArray<CampoCatalogo<keyof z.input<E> & string>>;
  valoresIniciales: z.input<E>;
  etiquetaGuardar?: string;                  // «Guardar» por omisión
  alGuardar: (valores: z.output<E>) => Promise<ResultadoApi<R>>;
  alGuardado: (respuesta: R) => void;
  alBloqueo: (error: ErrorReglaNegocio | ErrorConcurrencia) => void;
  alAccion: (accion: Accion) => void;
  alCerrar: () => void;
  baja?: BajaCatalogo;
}
```

- `Dialog` con `open={abierto}`; `onOpenAutoFocus` hace `preventDefault()` y `setFocus(campos[0].nombre)` (`CA-11` esc. 1). `useForm<z.input<E>, unknown, z.output<E>>({ resolver: zodResolver(esquema), defaultValues: valoresIniciales, shouldFocusError: true })`.
- Guardar: botón `disabled` en vuelo. `ok` → `alGuardado(datos)` y `alCerrar()`. `VALIDACION` → cada error cuyo `campo` es el `nombre` de un campo va con `setError`; los demás, a una lista en el `div role="alert"` de la cabecera. `CONFLICTO` → `ConflictoEnLinea` sobre los botones, **sin reiniciar** el formulario. `REGLA_NEGOCIO` y `CONCURRENCIA` → `alBloqueo(error)`. Cualquier otro → la cabecera con su `mensaje` o «No se pudo guardar.», y la referencia si existe.
- `ConflictoEnLinea({ error, alAccion })` acepta un `ErrorBloqueo`: muestra la cabecera de su `tipo` en tamaño de línea, el `mensaje`, `DetalleCifras` con el `detalle` (el registro existente) y `BotonesAcciones` sin «Cerrar».
- Baja (si llega `baja`): botón con `baja.etiqueta`. Con `exigeMotivo`, abre `CapturaMotivo` con `alConfirmar={(m) => baja.alConfirmar(m)}`. Sin motivo, abre `ConfirmacionBaja` (`Dialog` con `baja.pregunta`, «Cancelar» y «Confirmar baja»), que llama a `baja.alConfirmar(null)`. Cancelar no envía nada. `ok` → `baja.alHecha()`. Cualquier `409` de la baja → `ConflictoEnLinea` con sus acciones, sin decidir otra alternativa (`CA-11` esc. 7); otro error → la cabecera.

### Pruebas · dobles y ayudas

- `src/pruebas/servidor.ts`: `export const servidorPruebas = setupServer()`. `preparacion.ts`: importa `@testing-library/jest-dom/vitest`; `beforeAll(() => servidorPruebas.listen({ onUnhandledRequest: "error" }))`, `afterEach` con `cleanup()` y `servidorPruebas.resetHandlers()`, `afterAll(() => servidorPruebas.close())`.
- `src/pruebas/cuerpos.ts`: fábricas con nombre del dominio, cada una con `satisfies` contra el esquema provisional o el del servidor, para que los cuerpos cumplan el borrador por compilación: `usuarioActual(roles, cambios?)`, `tokenCsrf()`, `errorRn03ExcedeImporte(cambios?)` (las cifras de `CA-8` esc. 1), `errorRn03PorVolumen()`, `errorRn07ExcedeOrdenado()`, `errorConflictoEstado(codigo, cambios?)`, `errorConcurrencia()`, `errorValidacion(errores)`, `errorPermiso(motivo)`, `errorSesion(motivo)`, `errorLimiteIntentos(s)`, `errorNoEncontrado(recurso)`. Los identificadores, constantes fijas.
- `src/pruebas/render.tsx`: `renderizarAplicacion(rutaInicial)` devuelve `crearAplicacion({ rutaInicial })` renderizada más `usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`.
- Nombres: `it("tkt008_caNN_escMM · <escenario>", …)` y `it("tkt008_carN · …", …)` (`PA-T4`); en Playwright, `test("tkt008_ca14_escMM · …", …)`. Los tiempos se controlan con `vi.useFakeTimers({ shouldAdvanceTime: true })`; ningún `sleep`.

### Playwright

**`playwright.config.ts`**, literal salvo comentarios:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/preparacion-global.ts",
  workers: 1,
  retries: 0,
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run --locked --env-file ../.env fastapi run --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/openapi.json",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true, timeout: 60_000 },
  ],
});
```

Requisito previo, documentado y no automatizado: `docker compose up -d db`, `alembic upgrade head` y `contrasenas_roles`, y `npx playwright install chromium`.

**`e2e/preparacion-global.ts`**: correo fijo `humo.compras@cimenta.test`; contraseña `randomBytes(24).toString("base64url")`, nueva en cada corrida (ningún secreto en el repositorio). Ejecuta `spawnSync("uv", ["run", "--locked", "--env-file", "../.env", "python", "../frontend/e2e/sembrar_usuario_humo.py"], { cwd: <backend>, encoding: "utf8", env: { ...process.env, PYTHONPATH: ".", CIMENTA_HUMO_CORREO, CIMENTA_HUMO_CONTRASENA } })`. Estado distinto de 0 → `Error` con «No se pudo sembrar el usuario de humo. ¿Corre `docker compose up -d db` y está migrada la base?» y el `stderr`. Al terminar deja ambos valores en `process.env`, de donde los leen las pruebas.

**Reutilización, nunca borrado (D-4).** Hay **un solo** usuario de humo, con correo fijo: cada corrida actualiza su contraseña, lo reactiva y le deja exactamente el rol `COMPRAS`, sin crear otro usuario. No se borra al terminar: `sesion` e `intento_acceso` lo referencian por clave foránea, `intento_acceso` y `bitacora` solo admiten anexar (invariantes de TKT-003 y TKT-007), y un `DELETE` del usuario fallaría o exigiría borrar historia que el diseño declara permanente. Lo que se acumula son sus sesiones y sus intentos de acceso, unas pocas filas por corrida en la base de **desarrollo**; se aceptan y `docker compose down -v` las borra. Una base de prueba propia (testcontainers) aislaría también eso, a cambio de lo que dice D-4.

**`e2e/sembrar_usuario_humo.py` queda fuera de `ruff`, `mypy` y `lint-imports`**, que solo recorren `backend/`. Es aceptable por el mismo motivo que `backend/tests/conftest.py` y `herramientas/` quedan fuera de `lint-imports`: es una herramienta de preparación, sin reglas de negocio, que no importa nada de `cimenta/` y solo usa `herramientas.conexion`, `pwdlib` y SQL con parámetros ligados. Su verificación es funcional: la fila 14 lo ejecuta dos veces seguidas.

**`e2e/sembrar_usuario_humo.py`**, literal:

```python
"""Siembra el usuario del recorrido de humo de TKT-008 (CA-14) en la base local. Idempotente.

Se ejecuta desde backend/ con PYTHONPATH=. para importar herramientas.conexion. Usa el rol de
migración: es una herramienta de preparación, no una prueba de permisos. El hash es Argon2id de
pwdlib; el backend lo verifica con los parámetros que el propio hash declara.
"""

import os
import uuid

from pwdlib import PasswordHash
from sqlalchemy import create_engine, text

from herramientas.conexion import url_migracion


def main() -> None:
    correo = os.environ["CIMENTA_HUMO_CORREO"]
    huella = PasswordHash.recommended().hash(os.environ["CIMENTA_HUMO_CONTRASENA"])
    motor = create_engine(url_migracion())
    try:
        with motor.begin() as conexion:
            usuario_id = conexion.execute(
                text(
                    "INSERT INTO usuario (id, nombre, email, password_hash) "
                    "VALUES (:id, 'Humo Compras', :email, :huella) "
                    "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
                    "activo = true, bloqueado_hasta = NULL RETURNING id"
                ),
                {"id": uuid.uuid4(), "email": correo, "huella": huella},
            ).scalar_one()
            conexion.execute(
                text(
                    "DELETE FROM usuario_rol WHERE usuario_id = :u "
                    "AND rol_id <> (SELECT id FROM rol WHERE clave = 'COMPRAS')"
                ),
                {"u": usuario_id},
            )
            conexion.execute(
                text(
                    "INSERT INTO usuario_rol (id, usuario_id, rol_id) "
                    "SELECT :id, :u, id FROM rol WHERE clave = 'COMPRAS' "
                    "ON CONFLICT (usuario_id, rol_id) DO NOTHING"
                ),
                {"id": uuid.uuid4(), "u": usuario_id},
            )
    finally:
        motor.dispose()


if __name__ == "__main__":
    main()
```

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** del siguiente. Todos los comandos, desde `frontend/`, salvo los de documentación y los de `CA-R2`.

**Reglas comunes.**

- Rojo con `tester-frontend` en `sonnet`; verde con `desarrollador-react`. Un rojo válido es una aserción que falla o un módulo que no existe; un error de sintaxis o de entorno, no.
- **Rojo de infraestructura (fila 1).** Antes de instalar, el tester ejecuta `npm run dev` y `npm test` y pega el «Missing script» de npm: es el rojo de la fila. TC-01 y TC-02 se escriben con la fila y nacen en verde tras la instalación; su prueba de que dependen de algo son MT-1 y MT-2.
- **Tests que nacen en verde, ya previstos:** TC-01, TC-02, TC-17 y TC-18 (comprueban archivos que la propia fila genera) y los de regresión. Se anotan en `impl.md` con el mutante que los pone rojos.
- Cada fila termina con `npm run lint`, `npm run typecheck` y `npm test` en verde, además de su verificación propia.

**Por qué cada fila lleva su modelo** ([metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)). La fila 6 decide qué petición lleva la prueba de origen (`RNF-05`) y cuándo se descarta la sesión (`RNF-01`): es la frontera de autorización del cliente, el análogo en esta capa de «los permisos de un rol». La fila 11 pinta las cifras de `RN-03` y `RN-07` («regla de dinero o de límite»). El resto tiene su código o su contrato literal en este diseño y no cae en ningún disparador.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Andamiaje (A).** Instalar según «Versiones»; `package.json` (scripts), `tsconfig.json`, `vite.config.ts`, `eslint.config.js` sin las reglas de la fila 2 (solo el bloque base y los `ignores`), `index.html`, `src/main.tsx` provisional que pinta `<p>CIMENTA</p>`, `src/index.css` con `@import "tailwindcss";`, `src/pruebas/preparacion.ts` y `servidor.ts`; después `npx shadcn@latest init` (estilo por omisión, color base `neutral`, variables CSS) y `npx shadcn@latest add button input label textarea dialog`; borrar `src/index.ts`; `.gitignore` | TC-01, TC-02 | `desarrollador-react` | `haiku` | `npm ci` desde cero; `npm run dev` sirve `http://localhost:5173` y, con el backend arrancado, `curl -i http://localhost:5173/api/v1/sesion/csrf` responde `200` con `Set-Cookie: cimenta_csrf`; `npm run build`, `lint`, `typecheck` y `test` en verde; ningún rango (`^`, `~`) en `package.json` | ⚠ Ajustado |
| 2 | **Reglas de ESLint (A).** Rojo: TC-04 a TC-10 fallan porque `lintText` no devuelve mensajes. Verde: los bloques de `eslint.config.js` de «Configuración», literales | TC-04 a TC-10 | `desarrollador-react` | `haiku` | `npm test -- --project herramientas`; `npm run lint` en verde sobre el árbol real | ✓ Hecho |
| 3 | **Generación de tipos (A).** Rojo: TC-11 a TC-16 fallan con módulo inexistente `scripts/tipos.ts`. Verde: `scripts/tipos.ts`; después `npm run tipos:generar` y se versionan los dos archivos; TC-17 y TC-18 se escriben entonces | TC-11 a TC-18 | `desarrollador-react` | `haiku` | `npm run tipos:generar` dos veces y `git diff --exit-code -- src/api/generado` tras la segunda; `npm run tipos:verificar` → 0 y `Tipos al día.`; añadir una línea a `servidor.ts` → `verificar` termina con 1 y nombra el archivo; restaurar; `npm run typecheck` | ⚠ Ajustado |
| 4 | **Dinero (A).** Rojo: TC-19 a TC-25 fallan con módulo inexistente. Verde: `dinero.ts`, literal | TC-19 a TC-25 | `desarrollador-react` | `haiku` | `npm test -- src/compartido/dinero`; `npm run lint` (el módulo usa `toNumber` y `Decimal` sin violar sus reglas) | ✓ Hecho |
| 5 | **Normalización del error (A).** Rojo: TC-26 a TC-29 fallan con módulo inexistente. Verde: `errores.ts` | TC-26 a TC-29 | `desarrollador-react` | `haiku` | `npm test -- src/api/errores`; `npm run typecheck` | ✓ Hecho |
| 6 | **Cliente (A).** Rojo: TC-30 a TC-38 fallan con módulo inexistente. Verde: `cliente.ts`, literal; `sesion.ts`; `ProveedorApi.tsx` | TC-30 a TC-38 | `desarrollador-react` | `sonnet` · prueba de origen y fin de sesión (`RNF-05`, `RNF-01`) | `npm test -- src/api`; `npm run lint` y `typecheck` | ✓ Hecho |
| 7 | **Mutación y regresión (A).** Sin código. MT-1 a MT-14, de uno en uno, con el SHA-256 del archivo antes y al restaurar; después TC-R1 a TC-R4 | TC-R1 a TC-R4 | `tester-frontend` | `sonnet` | Tabla de mutantes en `impl.md`; las salidas de `npm ci`, `lint`, `typecheck`, `test` y `build`, con su línea de resumen; `git diff --stat Produccion -- backend` vacío | ⚠ Ajustado |
| 8 | **Secciones y carpetas (B).** Rojo: TC-39 a TC-45 fallan con módulo inexistente o carpetas ausentes. Verde: `secciones.ts`, literal; `ruta-marcador.tsx`; `SeccionMarcador`, `GuardaSeccion`, `AvisoSinPermiso`; los seis `rutas.tsx` y la carpeta `identidad` | TC-39 a TC-45 | `desarrollador-react` | `haiku` | `npm test -- src/app/navegacion` | ⚠ Ajustado |
| 9 | **Aplicación y armazón (B).** Rojo: TC-46 a TC-56 fallan con `crearAplicacion` inexistente. Verde: `crear-aplicacion.tsx`, `rutas.tsx` (con `PaginaInicioSesion` como componente vacío que pinta su `<h1>Iniciar sesión</h1>`; la fila 10 lo completa), `Armazon`, `InicioArmazon`, `NoEncontrado`; `main.tsx` definitivo | TC-46 a TC-56 | `desarrollador-react` | `haiku` | `npm test -- src/app`; `npm run dev` con el backend: la raíz lleva a `/inicio-sesion` | ⚠ Ajustado |
| 10 | **Inicio de sesión (B).** Rojo: TC-57 a TC-64 fallan porque la pantalla está vacía. Verde: `PaginaInicioSesion`, `inicio-sesion.formulario.ts`, `useEnLinea`, `useCuentaAtras` | TC-57 a TC-64 | `desarrollador-react` | `haiku` | `npm test -- src/modulos/identidad src/app` | ⚠ Ajustado |
| 11 | **Pantalla de bloqueo (B).** Rojo: TC-65 a TC-77 fallan con módulo inexistente. Verde: `PantallaBloqueo`, `DetalleCifras`, `BotonesAcciones`, `etiquetas.ts` | TC-65 a TC-77 | `desarrollador-react` | `sonnet` · cifras de `RN-03` y `RN-07` (regla de dinero o de límite) | `npm test -- src/compartido/componentes`; `npm run typecheck` (TC-74) | ⚠ Ajustado: firma de `BotonesAcciones` (TKT-008c, impl) |
| 12 | **Captura de motivo (B).** Rojo: TC-78 a TC-81 fallan con módulo inexistente. Verde: `CapturaMotivo`, `motivo.formulario.ts` | TC-78 a TC-81 | `desarrollador-react` | `haiku` | `npm test -- src/compartido/formularios/CapturaMotivo` | ⚠ Ajustado: foco con `initialFocus` de `@base-ui/react` (TKT-008c, impl) |
| 13 | **Formulario de catálogo (B).** Rojo: TC-82 a TC-89 fallan con módulo inexistente. Verde: `FormularioCatalogo`, `ConflictoEnLinea`, `ConfirmacionBaja` | TC-82 a TC-89 | `desarrollador-react` | `haiku` | `npm test -- src/compartido/formularios`; `npm run typecheck` | ⚠ Ajustado: `CabeceraBloqueo` y `catalogo.formulario.ts` (TKT-008c, impl) |
| 14 | **Humo de Playwright (B).** Rojo: con el backend y la base en marcha, TC-90 a TC-92 fallan en `globalSetup` porque `sembrar_usuario_humo.py` no existe. Verde: `playwright.config.ts`, `preparacion-global.ts` y el script, literales | TC-90 a TC-92 | `desarrollador-react` | `haiku` | Con `docker compose up -d db` y la base migrada: `npm run e2e` en verde con su resumen; se repite una segunda vez seguida (idempotencia de la siembra) | ✓ Hecho |
| 15 | **Mutación y regresión (B).** MT-15 a MT-32; después TC-R1 a TC-R4 completos | TC-R1 a TC-R4 | `tester-frontend` | `sonnet` | Tabla completa en `impl.md`; ningún mutante deja la suite en verde; desde `backend/`, `uv run pytest`, `ruff check`, `mypy`, `lint-imports` y `verificar_float` en verde con Docker (`CA-R2`) | ⚠ Ajustado: parte de 008b (MT-15 a MT-23) hecha; parte de 008c (MT-24 a MT-32 y tres propios) hecha |
| 16 | **Documentación y exclusiones del verificador (B).** Rojo: `tools/tests/test_verificar_docs_exclusiones.py` falla porque `EXCLUIR` no contiene `test-results`. Verde: `EXCLUIR` y después todos los cambios de «Documentación afectada»; la línea «Verificado en copia limpia» al final, tras la ejecución en copia limpia | TC-R4, TC-R5 | Orquestador con `conv-documentacion`, por sustitución | `haiku` · textos fijados abajo. Reasignación: los cambios de `CLAUDE.md` (bloque de comandos de frontend), de `docs/arranque-local.md` (sección «Frontend» y tabla «Lo que todavía no arranca») y de `conv-frontend-react` (D-11) se hicieron en TKT-008a por decisión del usuario del 2026-10-26. La fila 16 de TKT-008b conserva el resto: `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `tools/`, el humo, la línea «Verificado en copia limpia» y lo que añada el armazón. | `python -m unittest discover -s tools/tests -v` (el test nuevo en verde), `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` desde la raíz con código 0, también con un `frontend/test-results/x.md` con un enlace roto creado a mano y borrado después | ✓ Hecho |

**Modelo:** `haiku` por omisión; `sonnet` en las filas 6 y 11, que citan su disparador, y en el tester. Nunca `opus` en una fila de ejecución. **Reintento:** si una fila en `haiku` no cierra tras dos intentos —lo más probable en la 13, por la inferencia de tipos genéricos de React Hook Form con Zod 4—, el orquestador la reintenta en `sonnet` sin pedir permiso y lo anota.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño: supera con holgura el tope de unas 400 líneas.** Estimación de líneas escritas a mano, sin contar lo que copia el CLI de shadcn (unas 350) ni los dos archivos generados:

| Fila | Producción y configuración | Pruebas | Total |
|---|---|---|---|
| 1 Andamiaje | 200 | 30 | 230 |
| 2 ESLint | 50 | 130 | 180 |
| 3 Tipos | 150 | 180 | 330 |
| 4 Dinero | 60 | 120 | 180 |
| 5 Error | 110 | 190 | 300 |
| 6 Cliente | 130 | 220 | 350 |
| **A** | **700** | **870** | **unas 1,570** |
| 8 Secciones | 110 | 90 | 200 |
| 9 Armazón | 300 | 320 | 620 |
| 10 Inicio de sesión | 200 | 280 | 480 |
| 11 Bloqueo | 300 | 340 | 640 |
| 12 Motivo | 100 | 160 | 260 |
| 13 Catálogo | 230 | 300 | 530 |
| 14 Humo | 120 | 70 | 190 |
| 16 Documentación y verificador | 90 | 20 | 110 |
| **B** | **1,450** | **1,580** | **unas 3,030** |

**Unas 4,600 en total.** Se parte en entregas sin partir el ticket, como TKT-004 a TKT-007:

| Entrega | Filas | Criterios que cierra | Líneas | Fusionable sola |
|---|---|---|---|---|
| **A · andamiaje, tipos, cliente y dinero** | 1 a 7 | `CA-2`, `CA-3` esc. 1 y 2, `CA-4`, `CA-13`, `CA-1` esc. 1, `CA-R1` a `CA-R3` | unas 1,570 | **Sí.** `npm run dev` arranca; los tickets de pantalla pueden tipar y llamar al API |
| **B · pantallas, componentes, humo y documentación** | 8 a 16 | `CA-1` esc. 2 y 3, `CA-3` esc. 3, `CA-5` a `CA-12`, `CA-14`, `CA-R4` | unas 3,030 | Sí, sobre A |

**Ni siquiera una entrega cabe en el tope.** Por eso D-1 recomienda **partir el ticket** en tres hermanos —TKT-008a (filas 1 a 7, unas 1,570), TKT-008b (filas 8 a 10, 14 y 16, unas 1,600 con la documentación y las exclusiones del verificador) y TKT-008c (filas 11 a 13, unas 1,430)— y deja como alternativa las dos entregas de esta tabla, con B en dos PR. Las filas y sus números no cambian con la opción elegida: solo cambia a qué ticket o PR pertenece cada una.

## Plan de pruebas

Los de `scripts/` corren en el proyecto `herramientas` (Node, sin MSW); los de `src/`, en `cliente` (jsdom con MSW). Ninguno necesita Docker ni `uv`, salvo la verificación de la fila 3 y el humo de la fila 14.

### Andamiaje (fila 1, `scripts/esqueleto.test.ts`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-01 | `tkt008_car1 · versiones fijadas`: toda versión de `dependencies` y `devDependencies` casa con `^\d+\.\d+\.\d+$`; `engines.node === ">=24.0.0 <25.0.0"`; `.npmrc` contiene `engine-strict=true` y `save-exact=true`; los ocho scripts de «Configuración» existen con ese texto | **rechazo** (un rango cae) | `CA-R1` |
| TC-02 | `tkt008_ca01_esc01 · proxy en el mismo origen`: importa `vite.config.ts`; `server.proxy["/api"]` tiene `target === "http://127.0.0.1:8000"` y ni `changeOrigin` ni `rewrite`; `host === "localhost"`, `port === 5173`, `strictPort === true` | feliz | `CA-1` esc. 1 |

### Reglas de ESLint (fila 2, `scripts/eslint-reglas.test.ts`)

Con `new ESLint({ cwd: <frontend> })` y `lintText(codigo, { filePath })`; cada rechazo comprueba `ruleId`, la línea y que el mensaje cita la regla 1, `RNF-02` o `CA-13`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-04 | `tkt008_ca13_esc03 · Number en src`: `const a = Number("1");` en `src/modulos/compras/x.ts` → un error `no-restricted-syntax` en la línea 1 | **rechazo** | `CA-13` esc. 3 |
| TC-05 | `tkt008_ca13_esc03 · las demás conversiones`: `parseFloat`, `parseInt`, `Number.parseFloat`, `Number.parseInt`, `new Number(1)` y `+texto`, cada uno en su línea → un error por línea, con su número | **rechazo** | `CA-13` esc. 3, D-3 |
| TC-06 | `tkt008_ca13_esc03 · el módulo de dinero está exento`: el mismo código en `src/compartido/dinero/x.ts` → sin errores | feliz | `CA-13` esc. 3 |
| TC-07 | `tkt008_car3 · document.cookie`: `const c = document.cookie;` en `src/app/x.ts` y en `src/compartido/dinero/x.ts` → error en ambos | **rechazo** | `CA-R3` |
| TC-08 | `tkt008_ca13_esc04 · Zod solo en formularios`: `import { z } from "zod"` en `src/modulos/compras/x.ts` → error `no-restricted-imports`; en `src/modulos/identidad/inicio-sesion.formulario.ts` y en `src/compartido/formularios/X.tsx` → sin errores | **rechazo** y feliz | `CA-13` esc. 4 |
| TC-09 | `tkt008_ca13_esc03 · decimal.js solo en su módulo`: `import Decimal from "decimal.js"` en `src/api/x.ts` → error; en `src/compartido/dinero/x.ts` → sin errores | **rechazo** | `CA-13` esc. 3 |
| TC-10 | `tkt008_car1 · TSX`: `export const A = () => <p>{Number("1")}</p>;` en `src/app/A.tsx` → error de `no-restricted-syntax` (el `.tsx` se analiza) | **rechazo** | `CA-R1` |

### Tipos (fila 3, `scripts/tipos.test.ts` y `src/api/tipos.test.ts`)

Las entradas de TC-11 a TC-16 son documentos de prueba en memoria: un publicado mínimo con `/api/v1/sesion` y el borrador real leído con `yaml`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-11 | `tkt008_ca02_esc01 · subconjunto cerrado`: contiene las nueve raíces; todo `$ref` dentro del resultado resuelve dentro de él; no contiene `UsuarioActual` ni `Insumo`; `paths` es `{}`; con un borrador al que se le quita `Accion`, lanza nombrando `Accion` | feliz y **rechazo** | `CA-2` esc. 1 |
| TC-12 | `tkt008_ca02_esc01 · cabecera provisional`: el contenido de `ARCHIVO_CONTRATO_ERROR` empieza por `CABECERA_PROVISIONAL` y contiene «Se retira»; el de `ARCHIVO_SERVIDOR`, por `CABECERA_SERVIDOR` | feliz | `CA-2` esc. 1 |
| TC-13 | `tkt008_ca02_esc04 · determinista`: dos llamadas a `generarArchivos` con las mismas entradas dan mapas iguales cadena a cadena; ningún contenido tiene `\r`; cada uno termina en un único `\n` | feliz | `CA-2` esc. 4 |
| TC-14 | `tkt008_ca02_esc03 · desfase`: `diferencias` con un `leer` que devuelve otro contenido para el servidor → `[ARCHIVO_SERVIDOR]`; con `null` para el provisional → lo incluye | **rechazo** | `CA-2` esc. 3 |
| TC-15 | `tkt008_ca02_esc05 · edición a mano`: `leer` devuelve lo generado más `"// a mano\n"` → esa ruta; con lo generado exacto → `[]` | **rechazo** | `CA-2` esc. 5 |
| TC-16 | `tkt008_ca02 · exportación sin uv`: `exportarOpenapiPublicado` con un `ejecutar` que devuelve `status: 1` y `stderr` «Falta la variable X» → lanza un `Error` cuyo mensaje contiene `uv`, `PA-T10` y «Falta la variable X»; con `status: 0` y un JSON → lo devuelve. `principal(["verificar"], { exportar: () => { throw … } })` devuelve **2** y escribe en error «No se pudieron generar los tipos»; con archivos que difieren devuelve 1; iguales, 0; `principal(["otro"])` devuelve 3 | **rechazo** | `CA-2` esc. 1 y 3, `PA-T10` |
| TC-17 | `tkt008_ca02_esc02 · el switch estrecha`: una función con `switch (e.tipo)` sobre `ErrorBloqueo` lee `e.regla`, `e.codigo` y `e.detalle.espera_maxima_ms` sin aserciones; `expectTypeOf<ErrorReglaNegocio["tipo"]>().toEqualTypeOf<"REGLA_NEGOCIO">()`, y lo mismo para los otros siete | feliz (lo prueba `npm run typecheck`) | `CA-2` esc. 2 |
| TC-18 | `tkt008_car3 · importes y cantidades como cadena`: `expectTypeOf` es `string` para `Importe`, `ImporteNoNegativo`, `Cantidad`, `CantidadNoNegativa`, `ConsumidoDesglose` campo a campo, `DetalleExcedePresupuesto` en `presupuestado`, `consumido`, `disponible`, `solicitado`, `excedente` y los cinco `cantidad_*`/`excedente` de `insumos[number]`, `DetalleExcedeOrdenado["renglones"][number]` en sus cinco cantidades y `DetalleOrdenConSaldo["renglones_con_saldo"][number]["saldo_pendiente"]`. Además, leído como texto, en el provisional las únicas líneas con `number` declaran `espera_maxima_ms` y `reintentar_en_s`. **No** se exige que `servidor.ts` carezca de `number`: `ValidationError.loc` lo contiene legítimamente (ver «Fuentes») | **rechazo** | `CA-R3`, `CA-2` esc. 1 |

### Dinero (fila 4, `src/compartido/dinero/dinero.test.ts`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-19 | `tkt008_ca13_esc01 · suma exacta`: `aDecimal("0.1000")` más `aDecimal("0.2000")` es instancia de `Decimal` y `formatearImporte` da `"$0.30"` | feliz | `CA-13` esc. 1 |
| TC-20 | `tkt008_ca13_esc02 · redondeo al presentar`: `formatearImporte("1234.5650") === "$1,234.57"`; `aDecimal("1234.5650").toFixed(4) === "1234.5650"` | feliz | `CA-13` esc. 2, `PA-T5` |
| TC-21 | `tkt008_ca13_esc02 · sin pasar por number`: `formatearImporte("12345678901234.5650") === "$12,345,678,901,234.57"` | **rechazo** (cae con `Number`) | `CA-13` esc. 2 |
| TC-22 | `tkt008_ca08_esc05 · cifra inválida`: `"abc"`, `"1e3"`, `"Infinity"`, `"NaN"`, `"0x10"` y `""` → `null` en `aDecimal`, `formatearImporte` y `formatearCantidad`, sin lanzar | **rechazo** | `CA-8` esc. 5 |
| TC-23 | `tkt008_ca13 · negativo`: `formatearImporte("-3000.0000") === "-$3,000.00"` | feliz | `CA-13` |
| TC-24 | `tkt008_ca08_esc02 · cantidades`: `formatearCantidad("100.0000", "PZA") === "100.00 PZA"`; `formatearCantidad("1234.5") === "1,234.50"` | feliz | `CA-8` esc. 2 |
| TC-25 | `tkt008_ca09_esc02 · Retry-After`: `enteroNoNegativo("2") === 2`; `"-1"`, `"2.5"`, `"abc"`, `""` y `null` → `null` | **rechazo** | `CA-9` esc. 2 |

### Normalización del error (fila 5, `src/api/errores.test.ts`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-26 | `tkt008_ca04_esc01 · cada tipo con sus campos`: tabla de los ocho cuerpos de `cuerpos.ts` con su código; el resultado conserva `tipo`, `mensaje` y `correlacion_id`, y: `REGLA_NEGOCIO` `regla`, `detalle` y `acciones`; `CONFLICTO` `codigo`, `detalle` y `acciones`; `CONCURRENCIA` `codigo`, `detalle` y `reintentar_tras_s === 2` con `Retry-After: 2`; `VALIDACION` `errores` con `campo`, `codigo` y `mensaje`; `PERMISO` `motivo` y `roles_requeridos`; `SESION` `motivo`; `LIMITE_INTENTOS` `reintentar_en_s`; `NO_ENCONTRADO` `recurso` | feliz | `CA-4` esc. 1 |
| TC-27 | `tkt008_ca04_esc02 · fuera del contrato`: `500` con `{ mensaje, correlacion_id }` → `GENERICO` con ambos y `estado: 500`; cuerpo `"<html>"` → `GENERICO` con `null` y `null`; `{ detail: "x" }` → `GENERICO`; el cuerpo `HTTPValidationError` de FastAPI (`422` con `{ detail: [{ loc: ["body", "email"], msg: "x", type: "value_error" }] }`) → `GENERICO` con `estado: 422`, nunca `VALIDACION`; `{ tipo: "SESION", mensaje: "x" }` con `500` → `GENERICO` (no inventa el tipo); nada lanza | **rechazo** | `CA-4` esc. 2 |
| TC-28 | `tkt008_ca04_esc02 · tipo desconocido`: `409` con `tipo: "OTRO"` → `GENERICO` | **rechazo** | `CA-4` esc. 2 |
| TC-29 | `tkt008_ca04_esc04 · acciones intactas`: tres acciones con rutas `/api/v1/...` conservan orden, `metodo` y `ruta` exactas | feliz | `CA-4` esc. 4 |

### Cliente (fila 6, `src/api/cliente.test.ts`, con MSW)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-30 | `tkt008_ca03_esc01 · token antes de iniciar`: un registro de MSW anota cada petición; `POST /api/v1/sesion` sin token previo → el registro es `[GET /api/v1/sesion/csrf, POST /api/v1/sesion]` y el `POST` lleva `X-CSRF-Token` igual al `token` del cuerpo | feliz | `CA-3` esc. 1 |
| TC-31 | `tkt008_ca03_esc02 · mutaciones sí, GET no`: `aplicarCsrf` con `Request` de `POST`, `PUT`, `PATCH` y `DELETE` → cabecera con el token; con `GET` → sin cabecera y `obtenerToken` no se llama | feliz y **rechazo** | `CA-3` esc. 2 |
| TC-32 | `tkt008_ca03 · PA-T9`: tras un `POST /sesion` aceptado, la siguiente mutación vuelve a pedir el token (dos `GET /sesion/csrf`); igual tras `POST /sesion/cierre`; dos mutaciones simultáneas sin token hacen **un** solo `GET` | feliz | `CA-3`, `PA-T9` |
| TC-33 | `tkt008_ca03_esc03 · origen no verificado`: `403` `PERMISO` `ORIGEN_NO_VERIFICADO` → `pedir` devuelve ese error con su `motivo`; el registro tiene un solo `POST`. La **siguiente** mutación vuelve a pedir `GET /sesion/csrf` (dos en el registro) y lleva el token nuevo | **rechazo** | `CA-3` esc. 3, `PA-T9` |
| TC-34 | `tkt008_ca04_esc03 · sin red`: `HttpResponse.error()` → `{ ok: false, error: { tipo: "RED" } }`; `alTerminarSesion` no se llama | **rechazo** | `CA-4` esc. 3 |
| TC-35 | `tkt008_ca05 · qué 401 terminan la sesión`: `401` en `GET /api/v1/sesion` → `alTerminarSesion` una vez; `401` en `POST /api/v1/sesion` y en `POST /api/v1/sesion/cierre` → ninguna | feliz y **rechazo** | `CA-5` esc. 1 y 3 |
| TC-36 | `tkt008_ca05_esc04 · 403 pregunta de nuevo`: `403` → `alDenegarPermiso` una vez | feliz | `CA-5` esc. 4 |
| TC-37 | `tkt008_car3 · nadie lee la cookie`: con `Object.defineProperty(document, "cookie", { get: espia })`, un inicio y un cierre de sesión completos no invocan el espía | **rechazo** | `CA-R3`, `RNF-02` |
| TC-38 | `tkt008_ca07_esc07 · 204`: `POST /sesion/cierre` con `204` → `{ ok: true }` | feliz | `CA-7` esc. 7 |

### Secciones (fila 8)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-39 | `tkt008_ca01_esc02 · carpetas por módulo` (proyecto `herramientas`): `src/modulos` contiene exactamente `almacen`, `analitica`, `auditoria`, `compras`, `identidad`, `presupuesto` y `proveedores`; los seis primeros salvo `identidad` tienen `rutas.tsx`; existen `src/api`, `src/app` y `src/compartido` | feliz | `CA-1` esc. 2 |
| TC-40 | `tkt008_ca07_esc01 · ALMACEN`: títulos de `seccionesDe(["ALMACEN"])` = `["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir"]` | feliz | `CA-7` esc. 1 |
| TC-41 | `tkt008_ca07_esc02 · unión sin repetir`: `["COMPRAS", "ALMACEN"]` → `["Línea base", "Presupuesto de control", "Requisiciones", "Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir"]` | feliz | `CA-7` esc. 2 |
| TC-42 | `tkt008_ca07 · la tabla del wireframe`: lista exacta por cada uno de los seis roles (`ADMINISTRACION` → solo «Proveedores»; `DIRECCION_GENERAL` → las nueve; `RESIDENTE` → «Órdenes de compra», «Proveedores», «Recepción · Pendientes de recibir») | feliz y **rechazo** | `CA-7`, `PA-T8` |
| TC-43 | `tkt008_ca06_esc01 · primera sección`: `ALMACEN` → `/compras/ordenes-compra`; `COMPRAS` → `/obra/linea-base`; `[]` → `null` | feliz | `CA-6` esc. 1, `PA-T2` |
| TC-44 | `tkt008_ca07_esc05 · sección ajena`: `seccionPermitida("AUTORIZACIONES", ["ALMACEN"])` es `false`; con `DIRECCION_GENERAL`, `true` | **rechazo** | `CA-7` esc. 5 |
| TC-45 | `tkt008_ca07_esc06 · sin roles`: `seccionesDe([])` es `[]` | **rechazo** | `CA-7` esc. 6 |

### Aplicación y armazón (fila 9, `src/app/armazon/Armazon.test.tsx`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-46 | `tkt008_ca06_esc02 · ya hay sesión`: `GET /sesion` `200` con `COMPRAS`, ruta `/` → `router.state.location.pathname === "/obra/linea-base"`; no hay campo «Contraseña» | feliz | `CA-6` esc. 2 |
| TC-47 | `tkt008_ca07_esc01 · cabecera y menú`: con `ALMACEN`, el nombre, «Almacén» y el botón «Salir»; la navegación «Secciones» tiene exactamente tres enlaces | feliz | `CA-7` esc. 1 |
| TC-48 | `tkt008_ca07_esc03 · ruta marcador`: con `DIRECCION_GENERAL`, pulsar «Bitácora de excepciones» → ruta `/direccion/bitacora`, `<h1>` «Bitácora de excepciones» y «Esta sección aún no está disponible.» | feliz | `CA-7` esc. 3 |
| TC-49 | `tkt008_ca07_esc04 · el menor vencimiento`: `expira_en` `2026-10-26T20:00:00-06:00` y `expira_por_inactividad_en` `2026-10-26T10:30:00-06:00` → el `<time>` lleva `dateTime="2026-10-26T10:30:00-06:00"`; con los valores invertidos, el otro | feliz y **rechazo** | `CA-7` esc. 4 |
| TC-50 | `tkt008_ca07_esc05 · sección ajena por URL`: `ALMACEN` en `/direccion/autorizaciones` → «No tienes permiso para esta sección»; el contenido principal no contiene `$`; el menú no tiene «Autorizaciones» | **rechazo** | `CA-7` esc. 5 |
| TC-51 | `tkt008_ca07_esc06 · sin roles`: `roles: []` → ningún enlace en «Secciones», el aviso de `PA-T3` literal, «Salir» presente | **rechazo** | `CA-7` esc. 6, `PA-T3` |
| TC-52 | `tkt008_ca07_esc07 · salir`: «Salir» → el `POST /sesion/cierre` lleva `X-CSRF-Token`; la ruta pasa a `/inicio-sesion` sin el aviso; `queryClient.getQueryData(claves.sesion)` es `undefined`. Con `401` en el cierre, el mismo resultado | feliz y **rechazo** | `CA-7` esc. 7 |
| TC-53 | `tkt008_ca07_esc08 · menú plegable`: «Menú» empieza con `aria-expanded="false"` y la navegación con `data-abierto="false"`; al pulsar, ambos `true`; al elegir una sección, `false` | feliz | `CA-7` esc. 8 |
| TC-54 | `tkt008_ca01_esc03 · ruta que no existe`: con sesión, `/no-existe` → «Página no encontrada» con la cabecera del armazón («Salir») presente | **rechazo** | `CA-1` esc. 3 |
| TC-55 | `tkt008_ca05_esc04 · rol retirado`: sesión `["COMPRAS", "ALMACEN"]`; el doble de `GET /sesion` pasa a `["ALMACEN"]`; un `403` provocado con `api.POST("/api/v1/sesion/cierre")` → el menú deja de mostrar «Requisiciones» y conserva «Órdenes de compra» | feliz | `CA-5` esc. 4, `RNF-01` |
| TC-56 | `tkt008_m10 · estados del armazón`: mientras `GET /sesion` no responde, hay un elemento `aria-busy="true"`; con `HttpResponse.error()`, «No se pudo cargar la sesión.», «Sin conexión con el servidor.» y «Reintentar», que al pulsarse con el doble ya en `200` muestra el menú | **rechazo** | `M10` |

### Inicio de sesión (fila 10, `src/modulos/identidad/PaginaInicioSesion.test.tsx`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-57 | `tkt008_ca06_esc01 · iniciar sesión`: el doble de `POST /sesion` espera una promesa que la prueba resuelve; mientras tanto el botón está `disabled`; tras resolver, el registro muestra `GET /sesion` después del `POST`, y la ruta es `/obra/linea-base` para `COMPRAS` | feliz | `CA-6` esc. 1, `RNF-03` |
| TC-58 | `tkt008_ca06_esc03 · credenciales incorrectas`: `401` `CREDENCIALES_INVALIDAS` → «Correo o contraseña incorrectos.»; «Contraseña» vacía; «Correo» conserva lo escrito; la ruta sigue en `/inicio-sesion`; no aparece «Tu sesión terminó» | **rechazo** | `CA-6` esc. 3, `CA-5` esc. 3 |
| TC-59 | `tkt008_ca06_esc04 · forma inválida`: correo `x@` → «Escribe un correo válido.» junto al campo y el registro de MSW vacío (ni siquiera el token); contraseña vacía → «Escribe tu contraseña.». Con datos válidos y un `422` con errores en `email` y `contrasena`, cada mensaje del servidor junto a su campo | **rechazo** | `CA-6` esc. 4 |
| TC-60 | `tkt008_ca06_esc05 · demasiados intentos`: `429` con `reintentar_en_s: 900` → «Demasiados intentos fallidos. Vuelve a intentarlo en 15 minutos.» y botón `disabled` con «15:00»; tras avanzar 899 s sigue `disabled` con «00:01»; tras 900 s, habilitado | **rechazo** | `CA-6` esc. 5, `RNF-04` |
| TC-61 | `tkt008_ca06_esc06 · sin conexión`: `navigator.onLine` falso → botón `disabled` y el mensaje literal; pulsar no registra ninguna petición; al disparar `online` con `onLine` verdadero, se habilita | **rechazo** | `CA-6` esc. 6, regla 10 |
| TC-62 | `tkt008_ca06_esc07 · origen no verificado`: `403` `ORIGEN_NO_VERIFICADO` → el mensaje literal y el botón «Recargar»; un solo `POST` en el registro | **rechazo** | `CA-6` esc. 7, `CA-3` esc. 3 |
| TC-63 | `tkt008_ca05_esc01 · sesión terminada`: dentro del armazón, el doble de `GET /sesion` pasa a `401` `SESION_CADUCADA` y la prueba invalida la consulta → ruta `/inicio-sesion` con «Tu sesión terminó. Vuelve a iniciarla.» y caché vacía; igual con `SESION_REVOCADA` | feliz | `CA-5` esc. 1 |
| TC-64 | `tkt008_ca05_esc02 · primera visita sin aviso`: `GET /sesion` `401` `SIN_SESION` en `/` → la pantalla de inicio sin «Tu sesión terminó» | **rechazo** | `CA-5` esc. 2 |

### Pantalla de bloqueo (fila 11, `src/compartido/componentes/bloqueo/PantallaBloqueo.test.tsx`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-65 | `tkt008_ca08_esc01 · bloqueo por importe`: con `errorRn03ExcedeImporte()`, «Operación bloqueada» y «Regla RN-03»; el `mensaje` literal; los `<dt>` de cifras en orden «Presupuestado», «Consumido», «Disponible», «Solicitado», «Excedente» con «$45,000.00», «$33,000.00», «$12,000.00», «$15,000.00» y «$3,000.00»; el desglose «requisiciones vivas $6,000.00 · comprometido $9,000.00 · ejercido $18,000.00»; el excedente con `data-resaltada="true"`; «Referencia: » y el `correlacion_id` | feliz | `CA-8` esc. 1, `RNF-13` |
| TC-66 | `tkt008_ca08_esc01 · el excedente es el que llegó`: el mismo cuerpo con `excedente: "2999.0000"` muestra «$2,999.00», no «$3,000.00» | **rechazo** | `CA-8` esc. 1 |
| TC-67 | `tkt008_ca08_esc02 · por volumen`: cada insumo con sus cinco cantidades y su unidad («100.00 PZA»…); el de `presupuestado_en_partida: false` lleva «no presupuestado en esta partida» y el otro no | feliz | `CA-8` esc. 2 |
| TC-68 | `tkt008_ca08_esc03 · excedente de recepción`: cada renglón con ordenado, recibido, saldo pendiente, entrante y excedente | feliz | `CA-8` esc. 3 |
| TC-69 | `tkt008_ca08_esc04 · clave desconocida`: `detalle` con `cifra_nueva: "12.0000"` y `otra: { a: 1 }` → `<dt>` «cifra_nueva» con «12.0000» y «otra» con `{"a":1}`; `requisicion_id` no aparece | **rechazo** | `CA-8` esc. 4, D-8 |
| TC-70 | `tkt008_ca08_esc05 · cifra no decimal`: `disponible: "abc"` → «No disponible»; el texto no contiene `NaN`; no lanza | **rechazo** | `CA-8` esc. 5 |
| TC-71 | `tkt008_ca09_esc01 · conflicto`: `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` → «No se puede completar» y el código; ningún texto «Regla» | feliz y **rechazo** | `CA-9` esc. 1 |
| TC-72 | `tkt008_ca09_esc02 · reintentar con espera`: `CONCURRENCIA` con `reintentar_tras_s: 2` → «Inténtalo de nuevo»; «Reintentar» `disabled` a los 1,999 ms y habilitado a los 2,000; al pulsar, `alReintentar` una vez y `alAccion` ninguna | feliz | `CA-9` esc. 2, `RNF-16` |
| TC-73 | `tkt008_ca09_esc03 · sin función de reintento`: sin `alReintentar`, pulsar «Reintentar» llama a `alAccion` con `{ clave: "REINTENTAR", metodo, ruta }` exactos | **rechazo** | `CA-9` esc. 3 |
| TC-74 | `tkt008_ca09_esc04 · solo 409`: en el archivo, dos asignaciones a `PropsPantallaBloqueo["error"]` de un `ErrorValidacion` y de un `ErrorPermiso`, cada una con `// @ts-expect-error`; la prueba en tiempo de ejecución solo afirma que existe; la comprueba `npm run typecheck` | **rechazo** | `CA-9` esc. 4 |
| TC-75 | `tkt008_ca10_esc01 · un botón por acción`: acciones `VER_SOLICITUD_AUTORIZACION` y `CANCELAR_REQUISICION` → botones, en orden, «Ver solicitud de autorización», «Cancelar la requisición», «Cerrar»; pulsar el primero llama a `alAccion` con el objeto exacto y el registro de MSW sigue vacío | feliz | `CA-10` esc. 1 |
| TC-76 | `tkt008_ca10_esc02 · solo Cerrar`: `acciones: []` → un único botón, «Cerrar», que llama a `alCerrar` | **rechazo** | `CA-10` esc. 2 |
| TC-77 | `tkt008_ca10_esc03 · clave desconocida`: `HACER_ALGO` → botón «HACER_ALGO» que entrega la acción | **rechazo** | `CA-10` esc. 3, D-7 |

### Captura de motivo (fila 12, `CapturaMotivo.test.tsx`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-78 | `tkt008_ca12_esc01 · confirmar con motivo`: el foco abre en «Motivo»; con «  Material dañado  », `alConfirmar` recibe «Material dañado»; el botón está `disabled` mientras la promesa no resuelve; con `ok`, `alHecho` una vez | feliz | `CA-12` esc. 1, `RN-04` |
| TC-79 | `tkt008_ca12_esc02 · sin motivo`: vacío y «   » → `alConfirmar` no se llama; «El motivo es obligatorio.» y `aria-invalid="true"` | **rechazo** | `CA-12` esc. 2 |
| TC-80 | `tkt008_ca12_esc03 · el servidor rechaza el motivo`: `alConfirmar` devuelve `VALIDACION` con `{ campo: "motivo", mensaje: "El motivo no puede repetir el anterior." }` → ese texto junto al campo, no «El motivo es obligatorio.»; el texto escrito se conserva; `alRechazo` no se llama | **rechazo** | `CA-12` esc. 3 |
| TC-81 | `tkt008_ca12_esc04 · el servidor rechaza la operación`: devuelve un `REGLA_NEGOCIO` → `alRechazo` con ese error exacto y la captura no muestra mensaje propio | **rechazo** | `CA-12` esc. 4 |

### Formulario de catálogo (fila 13, `FormularioCatalogo.test.tsx`)

El arnés pinta un botón «+» que abre el formulario con dos campos, `codigo` y `nombre`, y el esquema `z.object({ codigo: z.string().min(1, "El código es obligatorio."), nombre: z.string().min(1, "El nombre es obligatorio.") })`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-82 | `tkt008_ca11_esc01 · foco en el primer campo`: tras «+», el foco está en «Código» | feliz | `CA-11` esc. 1 |
| TC-83 | `tkt008_ca11_esc02 · guardar`: botón `disabled` en vuelo; con `ok`, `alGuardado` recibe la respuesta y `alCerrar` se llama | feliz | `CA-11` esc. 2 |
| TC-84 | `tkt008_ca11_esc03 · forma inválida`: «Nombre» vacío → «El nombre es obligatorio.» junto al campo, foco en «Nombre», `alGuardar` no se llama | **rechazo** | `CA-11` esc. 3 |
| TC-85 | `tkt008_ca11_esc04 · 422 del servidor`: errores en `codigo`, `nombre` y `rfc` → los dos primeros junto a su campo y el de `rfc` en la cabecera | **rechazo** | `CA-11` esc. 4 |
| TC-86 | `tkt008_ca11_esc05 · duplicado en línea`: `CONFLICTO` `CODIGO_OBRA_DUPLICADO` con `detalle: { codigo: "AP-058-25", nombre: "Union Square F2" }` y una acción → el conflicto en línea muestra ambos valores y el botón de la acción; `alBloqueo` no se llama; los campos conservan lo escrito; pulsar la acción la entrega con `alAccion` | **rechazo** | `CA-11` esc. 5 |
| TC-87 | `tkt008_ca11 · regla de negocio delegada`: `REGLA_NEGOCIO` al guardar → `alBloqueo` con ese error | **rechazo** | `CA-11`, `M6` |
| TC-88 | `tkt008_ca11_esc06 · confirmación de baja`: sin motivo, «Dar de baja» abre la pregunta; «Cancelar» → `alConfirmar` de la baja nunca se llama; con `exigeMotivo`, se abre «Motivo» | feliz y **rechazo** | `CA-11` esc. 6, `PA-T12` |
| TC-89 | `tkt008_ca11_esc07 · la baja la rechaza el servidor`: la baja devuelve `409` `CONFLICTO` `PROVEEDOR_CON_ORDENES_ABIERTAS` con dos acciones → el rechazo en línea con esos dos botones en su orden y ninguno más | **rechazo** | `CA-11` esc. 7 |

### Humo (fila 14, `e2e/humo.spec.ts`, contra el backend real)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-90 | `tkt008_ca14_esc01 · entrar y salir`: `/` lleva a `/inicio-sesion`; con el usuario sembrado, la navegación «Secciones» tiene exactamente los seis enlaces de `seccionesDe(["COMPRAS"])`, listados abajo; «Salir» lleva a `/inicio-sesion`; `page.request.get("/api/v1/sesion")` responde `401` | feliz | `CA-14` esc. 1, `CA-1` esc. 1, `PA-T7` |
| TC-91 | `tkt008_ca14_esc02 · credenciales incorrectas`: una contraseña equivocada → «Correo o contraseña incorrectos.» y «Contraseña» con valor `""` | **rechazo** | `CA-14` esc. 2 |
| TC-92 | `tkt008_ca07_esc08 · teléfono`: viewport 375 × 812; tras iniciar sesión, la navegación no está visible; «Menú» la muestra; `document.documentElement.scrollWidth <= 375` | **rechazo** | `CA-7` esc. 8 |

Los enlaces esperados en TC-90 son, literalmente: «Línea base», «Presupuesto de control», «Requisiciones», «Órdenes de compra», «Proveedores» y «Recepción · Pendientes de recibir».

### Regresión

| # | Caso | Criterio |
|---|---|---|
| TC-R1 | `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` y `npm run build` con código 0 desde copia limpia; TC-01 en verde | `CA-R1` |
| TC-R2 | `git diff --stat Produccion -- backend` vacío; desde `backend/`, `uv run pytest` (con Docker), `ruff check`, `mypy`, `lint-imports` y `verificar_float` en verde | `CA-R2` |
| TC-R3 | TC-07, TC-18 y TC-37 en verde; `rg -n "document\.cookie" frontend/src` sin resultados | `CA-R3` |
| TC-R4 | Los tres comandos de documentación con código 0; `npm run dev` sin la marca en `CLAUDE.md` ni en `docs/arranque-local.md` | `CA-R4` |
| TC-R5 | `test_excluye_los_artefactos_de_playwright` en `tools/tests`: rojo antes del cambio de `EXCLUIR`, verde después | `CA-R4` |

### Concurrencia

No hay bloqueo pesimista en el cliente. La única concurrencia propia es la de dos mutaciones que piden el token a la vez: TC-32 exige una sola petición.

### Mutación

Cada mutante se aplica solo, se ejecutan los tests del ticket y se confirma que **al menos** los indicados se ponen rojos; después se revierte y se comprueba el SHA-256.

| Mutante | Dónde y qué | Debe ponerse rojo |
|---|---|---|
| MT-1 | `package.json`: `^` delante de una versión | TC-01 |
| MT-2 | `vite.config.ts`: `changeOrigin: true` | TC-02 |
| MT-3 | `eslint.config.js`: sin el selector de `parseInt` | TC-05 |
| MT-4 | `eslint.config.js`: el bloque de `src/compartido/dinero` también prohíbe `Number` | TC-06 |
| MT-5 | `eslint.config.js`: sin `COOKIE` en el bloque de `dinero` | TC-07 |
| MT-6 | `tipos.ts`: `diferencias` compara solo longitudes | TC-15 |
| MT-7 | `tipos.ts`: `subconjuntoContratoError` sin recorrido recursivo (solo las raíces) | TC-11 |
| MT-8 | `dinero.ts`: `ROUND_HALF_EVEN` | TC-20 |
| MT-9 | `dinero.ts`: `formatearImporte` con `Number(valor).toFixed(2)` | TC-21 |
| MT-10 | `dinero.ts`: sin la comprobación de `DECIMAL_PLANO` | TC-22 |
| MT-11 | `errores.ts`: invertir el discriminador (`CONFLICTO` ↔ `REGLA_NEGOCIO` en la salida) | TC-26 |
| MT-12 | `errores.ts`: sin comprobar que el código casa con el tipo | TC-27 |
| MT-13 | `cliente.ts`: `aplicarCsrf` no pone la cabecera / la pone también en `GET` (dos mutantes) | TC-30, TC-31 |
| MT-14 | `cliente.ts`: no se reinicia el token tras iniciar sesión; no se reinicia ante un `403`; `pedir` devuelve `SESION` en lugar de `RED` (tres mutantes) | TC-32; TC-33; TC-34 |
| MT-15 | `cliente.ts`: `alTerminarSesion` también para `POST /sesion` | TC-35, TC-58 |
| MT-16 | `crear-aplicacion.tsx`: el aviso siempre, sin mirar la caché | TC-64 |
| MT-17 | `secciones.ts`: intersección en lugar de unión | TC-41 |
| MT-18 | `secciones.ts`: `ORDENES_COMPRA` sin `ALMACEN` | TC-40, TC-42 |
| MT-19 | `Armazon`: el mayor de los dos vencimientos | TC-49 |
| MT-20 | `GuardaSeccion`: siempre devuelve `children` | TC-50 |
| MT-21 | `crear-aplicacion.tsx`: `alDenegarPermiso` vacío | TC-55 |
| MT-22 | `PaginaInicioSesion`: no vacía la contraseña | TC-58 |
| MT-23 | `PaginaInicioSesion`: ignora `useEnLinea` | TC-61 |
| MT-24 | `DetalleCifras`: el excedente como `solicitado − disponible` | TC-66 |
| MT-25 | `DetalleCifras`: omite las claves desconocidas | TC-69 |
| MT-26 | `DetalleCifras`: «NaN» en lugar de «No disponible» | TC-70 |
| MT-27 | `BotonesAcciones`: «Reintentar» habilitado desde el principio | TC-72 |
| MT-28 | `BotonesAcciones`: sin `alReintentar`, «Reintentar» no hace nada | TC-73 |
| MT-29 | `BotonesAcciones`: acciones en orden inverso | TC-75 |
| MT-30 | `CapturaMotivo`: esquema sin `.trim()` | TC-79 |
| MT-31 | `CapturaMotivo`: muestra «El motivo es obligatorio.» ante un `422` | TC-80 |
| MT-32 | `FormularioCatalogo`: `reset()` al recibir un `CONFLICTO` | TC-86 |

MT-1 a MT-14 en la fila 7; MT-15 a MT-32 en la fila 15.

## Impacto

`revisor-impacto` existe pero no se despachó en esta sesión; el análisis lo hace el arquitecto.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `frontend/package.json` y su lock | TKT-009 (pipeline) | Pares desalineados con TypeScript 6 y ESLint 10 | Regla de `overrides` de «Versiones»; TC-R1 |
| `tsconfig.json` con `erasableSyntaxOnly` | Todo el código de cliente futuro | Un `enum` de TypeScript deja de compilar | Es lo buscado: los tipos vienen generados como uniones de literales; lo dice `conv-frontend-react` (D-11) |
| `eslint.config.js` | Todo `src/` | Un uso legítimo de `Number()` exige una excepción anotada | `PA-T11`; la excepción lleva `eslint-disable-next-line` con su porqué |
| Los dos archivos generados | TKT-009, TKT-061, el ticket futuro de `responses=` | Que un PR del backend cambie el OpenAPI y nadie regenere | `tipos:verificar` lo detecta; TKT-009 lo engancha |
| Base local de Compose | Quien corre `npm run e2e` | El humo deja un usuario `humo.compras@cimenta.test`, reutilizado, y sus sesiones e intentos | Un solo usuario, nunca borrado (D-4); `docker compose down -v` lo borra todo |
| `tools/verificar_docs.py` y `tools/tests/` | El verificador de documentación de todo el repositorio | Excluir de más | Solo dos nombres de directorio que nunca contienen documentación; TC-R5. Queda fuera de «Módulos en alcance» de la spec: se aprueba en el gate |
| `docs/05-tickets-trabajo.md` (TKT-008 y TKT-009), `docs/06-stack-tecnologico.md` §7.3 | TKT-009; quien lea el stack | Ninguno | Textos fijados; también fuera de «Módulos en alcance», por el mismo gate |
| `CLAUDE.md`, `docs/arranque-local.md` | Todos los agentes | Ninguno | Textos fijados abajo |

**Fronteras entre módulos:** no. El cliente no tiene módulos de backend; `src/modulos/*` solo importa de `src/app`, `src/api` y `src/compartido`, nunca de otro módulo.

### Impacto en tickets posteriores

| Ticket | Qué hereda | Qué tiene que saber |
|---|---|---|
| TKT-009 | `npm run tipos:verificar`, `npm test`, `npm run e2e` | `tipos:verificar` necesita `uv` y `uv sync --locked` en `backend/` en el mismo trabajo (`PA-T10`); el humo, Docker y la base migrada. El verificador de escenarios debe aceptar `tkt008_caNN_escMM` (`PA-T4`) |
| TKT-057 | `aplicarCsrf`, el reinicio del token y la exportación del OpenAPI | **Exportación:** `npm run tipos:generar` y `tipos:verificar` construyen la aplicación con `crear_aplicacion(destino_registro=sys.stderr, entorno={})`, sin `.env`. Si TKT-057 hace que la fábrica no construya cuando falta un secreto, debe conservar una costura de exportación que construya sin secretos (por ejemplo, que la comprobación de secretos ocurra al arrancar el servidor y no al construir la aplicación) o, si no puede, cambiar `CODIGO_EXPORTACION` para pasar en `entorno` valores ficticios declarados como tales, en el mismo PR. Mientras tanto, el script termina con 2 y nombra la variable, nunca con un falso «Tipos al día». **CSRF:** el cliente ya pide token nuevo tras iniciar sesión, tras cerrarla y tras **cualquier** `403` (incluido `ORIGEN_NO_VERIFICADO`); lo que queda de la rotación es decidir si el servidor rota el token en cada mutación —entonces `onResponse` reinicia tras toda mutación— y el `429` y `ORIGEN_NO_VERIFICADO` reales, que ya tienen pantalla |
| TKT-061 y el ticket de `responses=` | `contrato-error.provisional.ts` | Al publicar los esquemas, `errores.ts` importa del archivo del servidor y el provisional se borra con su script |
| TKT-063 | `useEnLinea`, `crearAplicacion`, el `QueryClient` | La persistencia y el service worker se montan en `crearAplicacion` |
| Pantallas de la fase 1 | `rutaMarcador`, `GuardaSeccion`, `AvisoSinPermiso`, los tres componentes, `pedir`, `exigir`, `useApi` | Cada una sustituye su `rutaMarcador` en el `rutas.tsx` de su módulo y cablea el efecto de cada acción de la pantalla de bloqueo |

## Documentación afectada

Textos literales para la fila 16.

> Nota del 2026-10-26: los cambios de `CLAUDE.md` (bloque de comandos de frontend), de `docs/arranque-local.md` (sección «Frontend» y tabla «Lo que todavía no arranca») y de `conv-frontend-react` (D-11) se hicieron en TKT-008a por decisión del usuario del 2026-10-26. La fila 16 de TKT-008b conserva el resto: `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `tools/`, el humo, la línea «Verificado en copia limpia» y lo que añada el armazón.

| Documento | Qué cambia |
|---|---|
| `CLAUDE.md`, «Comandos · Desde `frontend/`» | El bloque pasa a: `npm ci` · `npm run lint` · `npm run typecheck` · `npm test                         # Vitest: componentes, cliente y herramientas` · `npm run tipos:generar            # tipos del OpenAPI publicado y del contrato de error · requiere uv` · `npm run tipos:verificar          # falla si los tipos versionados difieren de los que se generarían` · `npm run dev                      # cliente en localhost:5173, con proxy de /api al backend` · `npm run e2e                      # humo de Playwright · requiere backend, base migrada y Docker`, con la misma alineación de comentarios que el resto del bloque |
| `docs/arranque-local.md`, «Requisitos» | Fila nueva: «Navegador \| Chromium o Firefox recientes \| Desarrollo local. La cookie de sesión es `Secure` y solo esos motores la aceptan en `http://localhost`; Safari no» |
| `docs/arranque-local.md`, «Frontend» | Se sustituye por: los comandos `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` y `npm run tipos:verificar`; el párrafo de `npm ci` se conserva; párrafo nuevo: «`npm run tipos:generar` exporta el OpenAPI de FastAPI sin arrancar el servidor, ejecutando `uv run` en `backend/`, y genera `src/api/generado/`. Por eso necesita `uv` y `uv sync --locked` hecho en `backend/`. Los tipos del contrato de error salen del borrador y son provisionales: su archivo lo dice en la cabecera.» Bloque para arrancar: «Con el backend en marcha en `127.0.0.1:8000`, `npm run dev` sirve el cliente en `http://localhost:5173` y reenvía `/api` al backend: la cookie de sesión viaja en el mismo origen. Ábrelo como `localhost`, no como `127.0.0.1`.» Y el humo: «`npm run e2e` arranca el backend y el cliente si no están en marcha, siembra un usuario de Compras con una contraseña aleatoria y recorre el inicio y el cierre de sesión. Antes: `docker compose up -d db`, `alembic upgrade head`, `contrasenas_roles` y una vez `npx playwright install chromium`.» |
| `docs/arranque-local.md`, «Lo que todavía no arranca» | Se quita la fila `` `npm run dev` \| TKT-008 ``. La línea «Iniciar sesión en local…» añade: «El humo de Playwright siembra el suyo (`frontend/e2e/sembrar_usuario_humo.py`).» |
| `docs/arranque-local.md`, última línea | «Verificado en copia limpia el: …» se reescribe **después** de que la fila 16 ejecute en copia limpia el arranque completo (backend, `npm ci`, `npm run dev`, `npm test`, `tipos:verificar` y `npm run e2e`), con la fecha y las versiones reales de esa ejecución, incluidas Node, npm y el navegador de Playwright. Si no se puede ejecutar, la línea no se toca y la fila queda `⚠ Ajustado` |
| `docs/05-tickets-trabajo.md`, TKT-008 | El criterio «**Los tipos del cliente se generan del OpenAPI**…» pasa a: «- [ ] **Los tipos del cliente se generan del OpenAPI** que FastAPI publica (`openapi-typescript`), exportado sin servidor en marcha, con `npm run tipos:generar`; `npm run tipos:verificar` falla si el archivo versionado difiere de lo que se generaría. Engancharlo al pipeline es de TKT-009. Los tipos del contrato de error salen del borrador como provisionales hasta que FastAPI publique sus esquemas» |
| `docs/05-tickets-trabajo.md`, TKT-009 | El criterio «Trabajo de tests de frontend» pasa a: «- [ ] Trabajo de frontend: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` y **`npm run tipos:verificar`**, este último con **`uv` y Node en el mismo trabajo** y `uv sync --locked` hecho en `backend/` (TKT-008, `PA-T10`)». Criterio nuevo tras él: «- [ ] Trabajo del humo de Playwright, `npm run e2e`, con Docker, la base migrada, las contraseñas de los roles fijadas y un `.env` construido desde `.env.example` (TKT-008)». En el criterio del verificador de escenarios, al final: «Los tickets de **fundación** sin historia propia nombran sus tests por criterio, `tkt0NN_caNN_escNN_…` en pytest y `"tkt0NN_caNN_escNN · …"` en Vitest y Playwright (`PA-T4` de TKT-008): el verificador los admite y no los cuenta como huérfanos» |
| `docs/06-stack-tecnologico.md` §7.3 | Tras la primera frase: «Las pruebas de componente corren en **jsdom**, y el servidor se sustituye con **MSW**, que intercepta la petición real con sus cabeceras —así se prueba que toda mutación lleve `X-CSRF-Token`— y simula la red caída. Un recorrido de humo de Playwright, iniciar y cerrar sesión, corre contra el backend real y la base de Compose (TKT-008).» |
| `tools/verificar_docs.py`, l. 29 | `EXCLUIR` añade `'test-results'` y `'playwright-report'`: Playwright escribe allí `.md` cuando falla, y el verificador los recorrería como documentación |
| `tools/tests/test_verificar_docs_exclusiones.py` (nuevo) | `test_excluye_los_artefactos_de_playwright`: lee `tools/verificar_docs.py` con `ast`, localiza la asignación de `EXCLUIR`, la evalúa con `ast.literal_eval` y afirma que contiene `test-results` y `playwright-report`. Se escribe y se ejecuta **antes** de cambiar `EXCLUIR`, y nace rojo |
| `docs/02-arquitectura.md`, `docs/api/openapi.yaml`, `docs/07-especificacion-api.md`, glosario, ADR | Sin cambio. API §6.2 ya permite los tipos provisionales del borrador |
| `.claude/skills/conv-frontend-react/SKILL.md` §4 y §6 (sujeto a D-11) | En §4, tras «Toda dependencia de la función de consulta va en la clave…»: «Excepción: el cliente de API (`useApi()`) no entra en la clave. No selecciona datos, es el transporte, y cada `QueryClient` nace junto a su único cliente en `crearAplicacion` (TKT-008).» En §6, viñeta nueva: «`erasableSyntaxOnly`: nada de `enum` ni de propiedades de parámetro; los conjuntos cerrados son uniones de literales, que además es lo que genera `openapi-typescript`.» |

## ¿Merece ADR?

**No.** El stack, los tipos generados del OpenAPI, Zod solo en formularios, `decimal.js` y shadcn copiado están decididos en el [ADR de frontend](../../../docs/adr/20260918-frontend-react-spa.md), en stack §5.3 y §5.4, y en API §6.2. Lo que este diseño añade son elecciones de implementación dentro de esas decisiones —exportar por `uv run` sin tocar el backend, el subconjunto provisional, MSW, el humo contra la base de Compose— y su porqué queda aquí y en `docs/arranque-local.md`. La única que alguien podría preguntarse en un año es por qué los tipos de error vienen del borrador, y la respuesta tiene fecha de caducidad: el ticket futuro de `responses=` la retira. Si en el gate se elige crear `backend/herramientas/exportar_openapi.py` (D-5), tampoco: es una herramienta, no una arquitectura.

## Decisiones sobre las preguntas abiertas de la spec y del encargo

| # | Decisión del diseño |
|---|---|
| Exportar el OpenAPI sin servidor | `scripts/tipos.ts` ejecuta `uv run --locked python -c …` con cwd `backend/`, `crear_aplicacion(destino_registro=sys.stderr, entorno={}).openapi()` y `ensure_ascii=True`. Ningún archivo de `backend/` cambia (D-5) |
| Dónde viven los generados | `src/api/generado/servidor.ts` y `src/api/generado/contrato-error.provisional.ts`, versionados y fuera de ESLint |
| Tipos provisionales | Solo los nueve esquemas de error y su cierre por `$ref`, con `const` también como `enum` (D-10) |
| Determinismo | Generación en memoria, sin marcas de tiempo, `\n` y un solo salto final; verificación por igualdad de cadenas |
| Comando de verificación | `npm run tipos:verificar`, salida 1 con `Difiere: <ruta>` |
| `PA-T7` | Parcialmente resuelta: `localhost:5173` con *proxy* sin `changeOrigin`; Chromium comprobado por el humo; Firefox y Safari `(asumido)`, sin comprobar (D-9) |
| `PA-T9` | Token del cuerpo, reiniciado tras `POST /sesion`, `POST /sesion/cierre` y cualquier `403`; una sola petición compartida |
| `PA-T10` | Aceptada: `tipos:generar` y `tipos:verificar` exigen `uv`; `npm test` no |
| `PA-T11` | Prohibición general en `src/` con `src/compartido/dinero/` exento; incluye el `+` unario (D-3) |
| `PA-T2`, `PA-T3`, `PA-T5`, `PA-T12` | Se adoptan como dice la spec, con los textos de «Vistas y componentes» |
| `PA-T4` | Nombres `tkt008_caNN_escMM` y `tkt008_carN` |
| `PA-T6` | `429` y `ORIGEN_NO_VERIFICADO` solo contra MSW |
| `401` global | En el *middleware*, salvo `POST /sesion` y `POST /sesion/cierre`; aviso solo si había usuario en caché (D-6) |
| `403` global | Invalida la sesión; el menú se redibuja con la respuesta nueva |
| Dobles | MSW con `onUnhandledRequest: "error"` (D-2) |
| Humo | Base local de Compose, usuario sembrado por `uv run` con el rol de migración, contraseña aleatoria por corrida (D-4) |

## Decisiones que requieren al usuario en el gate

| # | Pregunta | Recomendación | Si se decide otra cosa |
|---|---|---|---|
| D-1 | El orden suma unas 4,600 líneas, más de diez veces el tope de unas 400 (condición de parada 3). ¿Se parte **el ticket**? | **Sí: tres tickets hermanos**, con este diseño como plan común y las filas repartidas: **TKT-008a** · andamiaje, tipos, cliente y dinero (filas 1 a 7, unas 1,570 líneas; cierra `CA-1` esc. 1, `CA-2`, `CA-3` esc. 1 y 2, `CA-4`, `CA-13`, `CA-R1` a `CA-R3`). **TKT-008b** · inicio de sesión, armazón y humo (filas 8, 9, 10, 14, la parte de la 15 con MT-15 a MT-23, y la 16; unas 1,600; cierra `CA-1` esc. 2 y 3, `CA-3` esc. 3, `CA-5`, `CA-6`, `CA-7`, `CA-14`, `CA-R4`). **TKT-008c** · los tres componentes (filas 11 a 13 y la parte de la 15 con MT-24 a MT-32; unas 1,430; cierra `CA-8` a `CA-12`). 008b y 008c dependen de 008a y no entre sí: pueden ir en paralelo. Ninguno baja de 400; partir más (por ejemplo, tipos aparte del cliente) daría tickets sin valor por sí solos. Exige que `/sdd-definir` reparta la spec, los Must y los criterios entre los tres, y que `docs/05-tickets-trabajo.md` y el plan de sprints los registren con su talla | **Alternativa: un solo ticket en dos entregas**, A (filas 1 a 7) y B (8 a 16), con B fusionada en dos PR cortando tras la fila 10 (la 14 y la 16 en el primero; las 11 a 13 en el segundo). Menos trámite, pero cada PR sigue muy por encima del tope y el gate humano aprueba 4,600 líneas de una vez |
| D-2 | ¿Doble del servidor con MSW, una dependencia de desarrollo nueva? | **Sí**: observa la petición real con sus cabeceras y su red caída, y el código de producción no gana costuras de prueba | `fetch` inyectado por `crearClienteApi({ fetch })` en cada prueba: sin dependencia, pero TC-30, TC-32 y TC-34 pasan a probar el doble y no la red |
| D-3 | ¿La prohibición de `PA-T11` incluye el `+` unario? | **Sí**: es la forma más común de convertir una cadena sin escribir `Number` | Solo las tres funciones; TC-05 pierde su última línea y queda una puerta abierta |
| D-4 | ¿Contra qué base corre el humo, y qué pasa con su usuario? | **Opción 1: la de Compose, con un único usuario de correo fijo que se reutiliza.** Cada corrida le actualiza la contraseña (aleatoria, nunca versionada), lo reactiva y le deja solo `COMPRAS`. **Nunca se borra**: `sesion` e `intento_acceso` lo referencian, y `intento_acceso` y `bitacora` solo admiten anexar. Se acumulan sus sesiones e intentos en la base de desarrollo, y se acepta | **Opción 2: base de prueba propia** con testcontainers desde Playwright: no deja rastro en la base de desarrollo, pero exige migrar, fijar las contraseñas de los roles y apuntar el backend a un puerto dinámico. Es una fila más en `sonnet`, unas 120 líneas más, y TKT-009 la heredaría |
| D-5 | La exportación ejecuta código del backend desde un script del cliente, sin archivo en `backend/` | **Así**, para respetar el non-goal y `CA-R2` | `backend/herramientas/exportar_openapi.py` con su prueba: más legible y lo usaría TKT-061, pero exige enmendar el non-goal y `CA-R2` |
| D-6 | ¿Cuándo sale «Tu sesión terminó»? | **Si y solo si había un usuario en caché.** Consecuencia: quien vuelve al día siguiente con la cookie caducada ve el inicio sin aviso | Además ante `SESION_CADUCADA` o `SESION_REVOCADA` en la primera carga: más preciso, una condición más y un caso más |
| D-7 | `CA-10` dice «rotulados por su clave». ¿Clave cruda o etiqueta legible? | **Etiqueta del wireframe para las diez claves conocidas** y la clave cruda para las demás | Siempre la clave cruda («VER_SOLICITUD_AUTORIZACION»): más literal, peor para quien lee |
| D-8 | Los cinco `*_id` del detalle son referencias, no cifras | **No se pintan**; toda clave desconocida, sí | Se pintan todos: la pantalla muestra UUID que nadie lee |
| D-9 | El desarrollo local exige Chromium o Firefox | **Sí, documentado**, sin tocar el backend | Que el backend lea del entorno si la cookie es `Secure`: es un cambio de backend y de seguridad, ticket aparte |
| D-10 | ¿Tipos provisionales del borrador entero o solo del contrato de error? | **Solo el contrato de error y su cierre**: unas 300 líneas que cambian cuando cambia el contrato | El borrador entero: unas 6,000 líneas que cambian con cada ticket y tientan a llamar rutas que no existen |
| D-11 | Dos cambios a `conv-frontend-react`: `erasableSyntaxOnly` prohíbe `enum` en todo el cliente (§6), y el cliente de API queda fuera de la clave de consulta como excepción declarada a §4 | **Sí a los dos**, con los textos de «Documentación afectada» | Un `tsconfig` aparte para `scripts/` (dos configuraciones que mantener); y, para la clave, dejar la excepción solo justificada en este diseño, con el riesgo de que el auditor la marque en cada ticket |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `openapi-fetch` captura `globalThis.fetch` al crear el cliente: con un cliente creado antes de que MSW arranque, las pruebas irían a la red real o fallarían sin explicación | `fetch: (r) => globalThis.fetch(r)` en `crearClienteApi`; TC-30 lo ejerce |
| 2 | Alta | Si `openapi-typescript` emite `tipo: string` para `const`, el `switch` no estrecha y `CA-2` esc. 2 cae sin que el borrador esté mal | `constComoEnum` antes de generar; TC-11 y TC-17 |
| 3 | Alta | `formatearImporte` con `Number(...).toFixed(2)` pasa `0.1 + 0.2` y `1234.565` en muchos motores, y el módulo de dinero está exento de la regla de ESLint | TC-21 con 18 dígitos significativos; MT-9 |
| 4 | Alta | Con los datos de `CA-8` esc. 1, un componente que **resta** da el mismo excedente que el que llegó: el test feliz no distingue | TC-66 con un excedente incoherente a propósito; MT-24 |
| 5 | Alta | El `401` del propio inicio de sesión o del cierre dispararía «Tu sesión terminó» y una navegación en mitad del formulario | Exclusión en `onResponse`; TC-35, TC-58, MT-15 |
| 6 | Media | `print` del registro de `structlog` en la salida estándar corrompería el JSON exportado; la consola de Windows rompería los acentos | `destino_registro=sys.stderr` y `ensure_ascii=True` |
| 7 | Media | Dos mutaciones simultáneas pedirían dos tokens y, con la rotación de TKT-057, una llevaría uno viejo | Promesa compartida; TC-32 |
| 8 | Media | `queryClient.clear()` con el armazón montado relanza `GET /sesion`, que vuelve a dar `401` | `terminarSesion` navega antes de limpiar y es idempotente en `/inicio-sesion`; *Salir* espera a `navigate` |
| 9 | Media | La guarda de sección podría leerse como control de acceso | `PA-T8` y el comentario de `SECCIONES`; `AvisoSinPermiso` exportado para el `403` real |
| 10 | Media | `npm test` acabaría dependiendo de `uv` si las pruebas del script exportaran de verdad | `exportarOpenapiPublicado` recibe `ejecutar`; la exportación real solo en la verificación de la fila 3 |
| 11 | Media | Un humo contra una base compartida no es reproducible | Siembra idempotente y verificación de la fila 14 que lo corre dos veces seguidas |
| 12 | Baja | Las clases de Tailwind no se aplican en jsdom: TC-53 no demuestra que el menú se oculte en un teléfono | TC-92 en Playwright con 375 px |
| 13 | Baja | El arquitecto no ejecutó nada y las versiones exactas no están fijadas aquí | Declarado; regla de resolución y de `overrides` en «Versiones», y salidas escritas en las filas 1 y 3 |
| 14 | Alta | El OpenAPI publicado contiene `number` legítimo (`ValidationError.loc`): un TC-18 sobre todo `servidor.ts` nacería rojo (revisor de impacto, M-1) | TC-18 acotado a importes y cantidades; `HTTPValidationError` sale `GENERICO` (TC-27) |
| 15 | Alta | Si TKT-057 exige secretos al construir la aplicación, la exportación falla y podría confundirse con un desfase (M-2) | Código de salida 2, distinto del 1; fila de TKT-057 en «Impacto en tickets posteriores» |
| 16 | Media | Un token de CSRF rechazado seguiría en caché y todas las mutaciones siguientes darían `403` (m-4) | Reinicio ante cualquier `403`; TC-33 y MT-14 |
| 17 | Media | El humo contra la base de desarrollo acumularía usuarios (A-1) | Un usuario fijo reutilizado, nunca borrado (D-4) |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Pares de `openapi-typescript` o `eslint-plugin-react-hooks` que no admiten TypeScript 6 o ESLint 10 | Alta | Media | Regla de `overrides`; si el paquete falla en ejecución con la mayor nueva, se escala |
| `openapi-fetch` 0.x cambia la firma de `Middleware` o del `fetch` personalizado | Media | Media | La fila 1 fija la versión exacta; TC-30 a TC-38 lo detectan; ajuste anotado |
| El CLI de shadcn escribe más de lo pedido (otro `index.css`, otra versión de Tailwind) | Media | Baja | La fila 1 revisa el diff del CLI; se conserva solo lo de las cinco primitivas, `components.json`, `lib/utils.ts` y el tema |
| La inferencia genérica de React Hook Form con Zod 4 no compila en `FormularioCatalogo` | Media | Media | Reintento en `sonnet` por la regla de §14.2; ningún `any` |
| El navegador del desarrollador no acepta la cookie `Secure` | Baja | Media | Documentado (D-9); el humo en Chromium lo vigila |
| `Intl.NumberFormat` con cadenas no disponible | Baja | Alta | Node 24 y los navegadores de D-9 lo admiten; TC-21 lo caería |
| El humo deja intentos y sesiones en la base local | Alta | Baja | Aceptado; `docker compose down -v` |
