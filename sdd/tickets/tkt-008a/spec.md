# Spec · TKT-008a · Andamiaje, tipos, cliente de API y dinero

> [← index](_index.md) | Spec común: [TKT-008](../tkt-008/spec.md) | Diseño común: [design](../tkt-008/design.md)

## Contexto y problema

TKT-008 se partió en tres tickets hermanos al aprobarse su diseño, el 2026-10-26, porque el plan sumaba unas 4,600 líneas (decisión D-1). Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-008/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-008a es la base de los otros dos. Entrega la aplicación instalada y configurada, la generación de tipos, el cliente de API que entiende el contrato de error y el módulo de dinero. No tiene pantallas: lo que se ve en el navegador al cerrarlo es una página provisional.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-008/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1**, en su parte de andamiaje: React 19, TypeScript, Vite, Tailwind v4 sin archivo de configuración, las primitivas de shadcn/ui del diseño y `npm run dev` con el *proxy* al backend. El enrutado y las carpetas por módulo son de TKT-008b |
| | **M2** completo: tipos generados, comando de generación y comando de verificación |
| | **M3**, en su parte de cliente: cookie, prueba de origen en toda mutación y normalización del contrato de error. La reacción del armazón ante un `401` o un `403` (`CA-5`) es de TKT-008b |
| | **M9** completo: dinero con `decimal.js`, prohibición de la conversión numérica nativa fuera del módulo de dinero y Zod solo en formularios |
| | **M10**, en su parte: Vitest configurado, con las pruebas de las filas 1 a 6 |
| **Should** | — |
| **Won't** | Todo lo de TKT-008b y TKT-008c, más los Won't de la spec común |

## Non-goals

- No monta rutas, armazón, inicio de sesión ni ningún componente reutilizable.
- Documenta lo que entrega, por decisión del usuario del 2026-10-26: toca el bloque de comandos de frontend de `CLAUDE.md`, la sección «Frontend» y la tabla «Lo que todavía no arranca» de `docs/arranque-local.md` y `conv-frontend-react` (D-11). El resto de la documentación, el humo y la línea «Verificado en copia limpia» son la fila 16, de TKT-008b.
- Los non-goals de la [spec común](../tkt-008/spec.md#non-goals) siguen en pie, en especial: ningún archivo bajo `backend/`.

## Reglas de negocio implicadas

`RNF-05` (prueba de origen), `RNF-13` (correlación en el error normalizado) y las reglas 1, 9 y 10 de `CLAUDE.md`. Detalle en la [spec común](../tkt-008/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-008/spec.md#invariantes-que-deben-sobrevivir-al-cambio). Este ticket es el que modifica `frontend/package.json`, su lock, `tsconfig.json` y `eslint.config.js`, y el que borra `frontend/src/index.ts`.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-1` `[M]` | Esc. 1: el cliente arranca en desarrollo contra el backend | 1 |
| `CA-2` `[M]` | Todos: generar sin servidor, estrechar los `409`, determinismo y los dos rechazos | 3 |
| `CA-3` `[M]` | Esc. 1 y 2: token antes de iniciar sesión y cabecera en toda mutación | 6 |
| `CA-4` `[M]` | Todos: los ocho `tipo`, la respuesta fuera del contrato, sin red y las acciones tal como llegan | 5, 6 |
| `CA-13` `[M]` | Todos: conversión exacta, redondeo al presentar y los dos rechazos | 2, 4 |
| `CA-R1` `[M]` | Esqueleto de TKT-001 | 7 |
| `CA-R2` `[M]` | El backend no cambia | 7 |
| `CA-R3` `[M]` | Sesión ilegible y dinero como cadena | 7 |

El escenario 3 de `CA-3` (origen no verificado) lo cierra TKT-008b, porque se ve en la pantalla de inicio de sesión. Los mutantes que corren aquí son MT-1 a MT-14 (fila 7).

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-005 y TKT-006, archivados. Bloquea a TKT-008b y TKT-008c |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común, ya aprobado |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Con reservas | Ningún rol ve nada todavía; el valor es que toda pantalla posterior hable con el servidor de una sola forma |
| **E** | Estimable sin investigar antes | Sí | Unas 1,570 líneas según el diseño |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Sigue por encima del tope de unas 400 líneas; partir más daría piezas sin valor por sí solas (D-1) |
| **T** | Sus criterios se pueden ejecutar | Sí | Vitest con MSW; la exportación real se verifica en la fila 3 |

Dos reservas y ningún fallo: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan, cada uno con su test nombrado por el criterio.
- [ ] Ningún mutante de MT-1 a MT-14 deja la suite en verde.
- [ ] `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` y `npm run tipos:verificar` en verde.
- [ ] Ningún archivo bajo `backend/` en el diff.
- [ ] Auditoría de arquitectura, de código y de seguridad sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-008/spec.md#preguntas-abiertas-y-supuestos), los que toca este ticket: `PA-T1` (tipos provisionales del contrato de error), `PA-T5` (`ROUND_HALF_UP` al presentar), `PA-T6` (la verificación de origen se prueba contra un doble), `PA-T7` (la cookie `Secure` en `http://localhost`), `PA-T9` (cuándo se vuelve a pedir el token), `PA-T10` (`uv` para generar los tipos) y `PA-T11` (alcance de la prohibición de la conversión nativa).

## Pasada adversarial

La de la [spec común](../tkt-008/spec.md#pasada-adversarial) y la del diseño común. La partición no añade objeciones: solo reparte criterios ya revisados.

## Contexto técnico

El de la [spec común](../tkt-008/spec.md#contexto-técnico). Filas 1 a 7 del [diseño común](../tkt-008/design.md); la fila 6 va en `sonnet` por la prueba de origen y el fin de sesión.
