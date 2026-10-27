# Delta · TKT-008b · Inicio de sesión, armazón por rol y humo

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| La aplicación montada: `crearAplicacion` con React Router en modo de datos, TanStack Query y el cliente de API; las rutas, y un `main.tsx` definitivo que importa `index.css` | `frontend/src/app/crear-aplicacion.tsx`, `frontend/src/app/rutas.tsx`, `frontend/src/main.tsx` | Que el cliente tenga un punto de entrada real y que las pantallas de la fase 1 se monten como rutas |
| Tabla de secciones por rol, copia del wireframe §2 (nueve secciones, unión de roles, primera sección por orden de la tabla), con `seccionesDe`, `primeraSeccion` y `seccionPermitida` | `frontend/src/app/navegacion/secciones.ts` | El menú del armazón y la guarda de sección. Duplica los `x-roles` del borrador como cortesía de navegación (`PA-T8`): el control es el `403` del servidor |
| Una carpeta por módulo de negocio con su `rutas.tsx` de rutas marcador | `frontend/src/modulos/{analitica,presupuesto,compras,proveedores,almacen,auditoria}/rutas.tsx` | Que cada ticket de pantalla sustituya su marcador sin tocar el armazón |
| El armazón: menú con la unión de las secciones, nombre y rol, vencimiento más próximo de la sesión, *Salir* que avisa y se queda si el cierre falla, menú plegable en teléfono que se cierra con Escape, guarda de sección y aviso para el usuario sin roles | `frontend/src/app/armazon/` | `CA-7` y `M5` |
| La pantalla de inicio de sesión con sus cinco rechazos del wireframe §1: mensaje único ante credenciales incorrectas, cuenta atrás ante un `429` que sigue al reloj, «Recarga la página para continuar.» ante `ORIGEN_NO_VERIFICADO`, botón deshabilitado sin conexión y aviso de sesión terminada solo si había usuario | `frontend/src/modulos/identidad/PaginaInicioSesion.tsx`, `inicio-sesion.formulario.ts`, `frontend/src/compartido/red/useEnLinea.ts`, `frontend/src/compartido/tiempo/useCuentaAtras.ts` | `CA-5` y `CA-6` |
| El humo de Playwright contra el backend real: entrar y salir, credenciales incorrectas y menú en teléfono, con un usuario de correo fijo que la siembra reutiliza, reactiva con solo `COMPRAS` y nunca borra | `frontend/playwright.config.ts`, `frontend/e2e/` | `CA-14` (`S1`) |
| Una guarda en la siembra del humo: se niega a conectar si el host no es local o si `PGHOSTADDR` o `PGSERVICE` están definidas, y falla con un mensaje claro si falta el rol `COMPRAS` | `frontend/e2e/sembrar_usuario_humo.py` | Que el rol de migración nunca siembre un usuario con credencial en una base remota |
| Pruebas: 76 casos nuevos en el cliente sobre los 78 de TKT-008a (154 en total), 3 del humo y 4 nuevos en `tools/tests/` (12 en total) | `frontend/src/**/*.test.ts(x)`, `frontend/scripts/*.test.ts`, `frontend/src/pruebas/`, `tools/tests/` | Los criterios de la tabla de `impl.md` y las condiciones heredadas de TKT-008a |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Cliente de API | `frontend/src/api/cliente.ts` | El token CSRF sobrevivía a una sesión terminada → `reiniciarToken()`, que `terminarSesion` llama al terminar la sesión |
| Sesión | `frontend/src/api/sesion.ts` | Cada componente repetía la consulta → `useSesion()` compartido |
| Verificadores de documentación | `tools/verificar_docs.py`, `tools/extraer_mermaid.py` | Recorrían los artefactos de Playwright → `EXCLUIR` añade `test-results` y `playwright-report` en los dos |
| Arranque del backend | `CLAUDE.md`, `docs/arranque-local.md` | `uv sync --locked` a secas → `uv sync --locked --python 3.14`, porque `uv` elegía Python 3.15 y `pyyaml` no compila sin compilador |
| Comandos del frontend | `CLAUDE.md` | → `npm run e2e` |
| Arranque del frontend | `docs/arranque-local.md` | → fila «Navegador» (Chromium comprobado; Firefox y Safari `(asumido)`, `PA-T7`), cómo correr el humo, las pruebas de `tools/tests/` y la línea «Verificado en copia limpia» del 2026-10-27 con su alcance |
| Criterios de TKT-008 y TKT-009 | `docs/05-tickets-trabajo.md` | «Comprobada en CI» → un comando local que TKT-009 engancha; TKT-009 gana `tipos:verificar` con `uv` y Node, `npm run e2e` y los nombres por criterio de los tickets de fundación (`PA-T4`) |
| Stack | `docs/06-stack-tecnologico.md` §5.1 y §7.3 | → primitivas de shadcn (`base-nova`, `@base-ui/react`, `cn`); jsdom, MSW y el humo; la regla de conversión numérica no cubre las coerciones aritméticas |
| Spec y diseño comunes | `sdd/tickets/tkt-008/{spec,design}.md` | Estado de las filas 8 a 10, 14, 15 y 16; `PA-T7` parcialmente resuelta |

## Eliminado

Nada.

## Comportamiento observable nuevo

- Al abrir `http://localhost:5173` sin sesión, la aplicación lleva al inicio de sesión. Con credenciales válidas entra al armazón en la primera sección de su rol, y el menú muestra solo las secciones de sus roles. Cada sección es todavía un marcador: «Esta sección aún no está disponible.»
- Si la sesión caduca o se revoca mientras se usa la aplicación, vuelve al inicio con «Tu sesión terminó. Vuelve a iniciarla.»; en la primera visita no hay aviso.
- *Salir* revoca la sesión en el servidor. Si el cierre falla, avisa y no saca al usuario.
- `npm run e2e` corre el humo contra el backend real y la base de Compose.
- El backend no cambia: `backend/` no tiene ningún archivo en el diff.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO, esquema y `docs/api/openapi.yaml` | Sin cambio | — |
| Tipos generados del cliente | Sin cambio | — |
| Interfaz del cliente de API para las pantallas | Añade `reiniciarToken()` y `useSesion()` | No |

## Decisiones (ADR)

No se creó ADR. Las decisiones del ticket son las del diseño común (D-1 a D-11) y dos del usuario durante la ejecución:

- **La rama sale de la de TKT-008a**, no de `Produccion`, porque 008b necesita su código. El PR se abre después del de 008a o apilado sobre él.
- **Python 3.14 fijado en la guía.** Con Python 3.15, `uv` construía `pyyaml` desde el código fuente y fallaba sin compilador. Se descartó fijar `backend/.python-version` porque `CA-R2` prohíbe tocar `backend/`. Evidencia: la verificación en copia limpia falló con 3.15 y pasó completa con `--python 3.14`. **Queda para la persona que aprueba** si esta decisión merece un ADR, y fijar el intérprete en `backend/` queda sugerido para TKT-009 o un ticket propio.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un token CSRF en caché tiene que descartarse en todo cambio de sesión, no solo al iniciar y cerrar sesión: también cuando la sesión termina por un `401` | S101 y TC-R312 | Todo cliente con doble envío |
| Vaciar la caché al iniciar sesión, no solo al salir: un usuario puede llegar al inicio sin pasar por *Salir* | S102 y TC-R305 | Toda aplicación con caché de consultas por usuario |
| Una cuenta atrás que cuenta ticks de `setInterval` se retrasa en pestañas ocultas; hay que calcularla contra `Date.now()` | C105 y TC-R307 | Todo temporizador visible |
| Un test de tiempo no detecta una comparación de cadenas ISO si los dos valores comparten desfase horario | C102 y los dos casos de desfases mixtos | Toda comparación de fechas |
| `uv` elige el intérprete más nuevo que cumpla `requires-python`, y un Python recién publicado puede no tener ruedas de las dependencias | F203 | Todo arranque con `uv` |
| La consola de Windows no emite UTF-8 en `stderr`: un mensaje con tildes rompe a quien lo lee desde `subprocess` | TC-R317, primera corrida | Scripts que se prueban por su salida |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `plantilla` | La fila 14 del diseño pedía un rojo que dependía de un archivo del verde (`playwright.config.ts`): el tester no podía obtenerlo en el árbol sin escribir configuración y lo obtuvo en una copia | Media |
| `agente` | El verde de la fila 9 se escribió en una sola pasada, y la auditoría encontró justo ahí una rama del diseño sin test (F201). El «de uno en uno» del ciclo TDD no se hizo cumplir | Media |
| `guardrail` | Las auditorías de `/sdd-revisar` encontraron tres Mayores de código (ramas sin test) que 130 pruebas y la auditoría de cierre de fase no veían; la mutación de la fila 15 se limitó a los mutantes del diseño. Hace falta mutación exploratoria, no solo la lista del diseño | Media |
| `herramienta` | La verificación en copia limpia descubrió un fallo de entorno (Python 3.15) que nada más habría detectado; el diseño ya la exigía, pero se intentó cerrar sin ejecutarla | Media |
| `herramienta` | `verificar_docs.py` toma como enlace un `](` dentro de un bloque de código, y hubo que recortar evidencia pegada en `impl.md` | Baja |
| `modelo` | Ningún paso de desarrollo subió por fallar en `haiku`. `corrector-revision` se despachó en `sonnet` en la primera corrección de la revisión porque tocaba la sesión y el token CSRF (disparador de §14.2), y el tester bajó a `haiku` en la segunda corrección por ser mecánica; ambos con su motivo en `impl.md` | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Fijar el intérprete de Python en `backend/` (`.python-version` o un tope en `requires-python`) | `CA-R2` prohíbe tocar `backend/` | TKT-009 o ticket propio |
| Que el trabajo de `tools/` del pipeline instale `uv`: sin él se saltan las pruebas de la guarda de la siembra | Es del pipeline | TKT-009 |
| El umbral y la ventana del `429` frente al humo, que deja un intento fallido por corrida sobre el mismo correo (F306) | El servidor no emite todavía el `429` | TKT-057 |
| La rama «falta el rol COMPRAS» de la siembra solo tiene prueba manual (C109) | Necesita una base sin el rol | Sin ticket |
| Ayudas de prueba duplicadas entre `Armazon.test.tsx` y `PaginaInicioSesion.test.tsx` (C107) | Aceptado en la revisión | El siguiente ticket que toque esas pruebas |
| El menú usa `<button>` propios y no el `Button` de shadcn | Opcional en C106 de la revisión de código (registrado en «Ajustes» de `impl.md`) | TKT-008c o el primer ticket de pantalla |
| El mensaje de error de `tipos.ts` no menciona `--python 3.14` | Cambiarlo exige tocar su test | Sin ticket |
| `verificar_docs.py` lee `](` como enlace dentro de un bloque de código | Fuera de alcance | Ticket propio de herramientas |

## Pull request

**Título:** `TKT-008b · Inicio de sesión, armazón por rol y humo`
**Origen:** `agent+human-review`
**Cuerpo:** lo prepara `git-entrega` en el cierre, con qué, por qué, criterios cubiertos y cómo verificarlo. Base: la rama de TKT-008a hasta que su PR se fusione.
