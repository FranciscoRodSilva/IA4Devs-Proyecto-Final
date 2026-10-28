# Spec · TKT-008c · Componentes reutilizables

> [← index](_index.md) | Spec común: [TKT-008](../tkt-008/spec.md) | Diseño común: [design](../tkt-008/design.md)

## Contexto y problema

TKT-008 se partió en tres tickets hermanos al aprobarse su diseño, el 2026-10-26, porque el plan sumaba unas 4,600 líneas (decisión D-1). Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-008/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-008c construye los tres componentes que reúsan las historias de la fase 1: la pantalla de bloqueo, que pinta cualquier `409` del contrato de error; el formulario de catálogo; y la captura de motivo obligatorio. Se apoya en el error normalizado y en el módulo de dinero de TKT-008a. Ninguna pantalla los usa todavía: los prueba Vitest, y los cablea cada pantalla consumidora.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-008/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M6** completo: la pantalla de bloqueo del wireframe §6, con la cabecera por `tipo`, las cifras del detalle, un botón por acción y el reintento entregado por quien la abre |
| | **M7** completo: el formulario de catálogo |
| | **M8** completo: la captura de motivo obligatorio |
| | **M10**, en su parte: las pruebas de las filas 11 a 13 con los cuatro estados donde aplican |
| **Should** | — |
| **Won't** | Cablear el efecto de una acción de negocio, salvo `REINTENTAR` · usar los componentes en una pantalla real · lo de TKT-008a y TKT-008b y los Won't de la spec común |

## Non-goals

- No decide qué hace el botón de una acción de negocio: lo entrega a quien abrió la pantalla de bloqueo.
- No filtra acciones por rol: el servidor ya las filtra.
- No toca el cliente de API, el armazón ni la documentación, salvo que una prueba de esta parte revele un fallo de TKT-008a; en ese caso se corrige con su test en rojo y se anota en `impl.md`. Excepción registrada el 2026-10-27: el ajuste de marca que pidió el usuario toca `Armazon.tsx`, `PaginaInicioSesion.tsx` e `index.css`, con sus pruebas (`Armazon.test.tsx`, `PaginaInicioSesion.test.tsx`, `scripts/esqueleto.test.ts`) y el activo `src/assets/ap-logo.jpeg`; la lista completa está en «Archivos tocados» de `impl.md`, solo en presentación (`impl.md`, «Ajustes respecto al design»); y, sin cambio de comportamiento, en la revisión: el texto del cierre por defecto de `components/ui/dialog.tsx` pasa de «Close» a «Cerrar» (hallazgo C6) y se reformula un comentario de `api/cliente.test.ts:322` que citaba literalmente la cookie (`CA-R3`).
- Los non-goals de la [spec común](../tkt-008/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

`RN-03` y `RN-07` como contenido de la pantalla de bloqueo, `RN-04` por la captura de motivo, `RNF-13` y `RNF-16`, y la regla 1 de `CLAUDE.md`. El cliente no evalúa ninguna regla: pinta lo que llega. Detalle en la [spec común](../tkt-008/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-008/spec.md#invariantes-que-deben-sobrevivir-al-cambio). En especial: ninguna cifra se calcula en el cliente, y el excedente que se muestra es el que llegó.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-8` `[M]` | Todos: importe, volumen, recepción, clave desconocida y cifra no decimal | 11 |
| `CA-9` `[M]` | Todos: conflicto, concurrencia con reintento, sin función de reintento y el rechazo de un `422` o un `403` | 11 |
| `CA-10` `[M]` | Todos: un botón por acción, sin acciones y clave desconocida | 11 |
| `CA-11` `[M]` | Todos: abrir con foco, guardar, forma inválida, `422`, duplicado, confirmación de baja y baja rechazada | 13 |
| `CA-12` `[M]` | Todos: confirmar con motivo, sin motivo, `422` del servidor y `409` | 12 |
| `CA-R1` a `CA-R3` `[M]` | Repetidos sobre el árbol con esta parte | 15 |

Los mutantes que corren aquí son MT-24 a MT-32 (su parte de la fila 15) y MT-33 a MT-35, añadidos por el orquestador. MT-24 es el que resta el excedente en vez de mostrar el que llegó.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-008a. Puede ir en paralelo con TKT-008b |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común, ya aprobado |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Con reservas | El valor llega con la primera pantalla que los use; hasta entonces evita tres implementaciones divergentes |
| **E** | Estimable sin investigar antes | Sí | Unas 1,430 líneas según el diseño |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Por encima del tope de unas 400 líneas (D-1). Si el sprint 1 no aguanta, cada componente puede viajar con su primer consumidor |
| **T** | Sus criterios se pueden ejecutar | Sí | Vitest con dobles del servidor |

Dos reservas y ningún fallo: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan, cada uno con su test nombrado por el criterio.
- [ ] Ningún mutante de MT-24 a MT-32 deja la suite en verde.
- [ ] `npm run lint`, `npm run typecheck` y `npm test` en verde.
- [ ] Auditoría de arquitectura, de código y de seguridad sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-008/spec.md#preguntas-abiertas-y-supuestos), los que toca este ticket: `PA-T5` (`ROUND_HALF_UP` al presentar), `PA-T12` (la confirmación de baja como diálogo previo) y `PA-T13` a `PA-T17` (la captura de motivo, la baja y el formulario de catálogo, abiertas en la revisión).

## Pasada adversarial

La de la [spec común](../tkt-008/spec.md#pasada-adversarial) y la del diseño común. La partición no añade objeciones: solo reparte criterios ya revisados.

## Contexto técnico

El de la [spec común](../tkt-008/spec.md#contexto-técnico). Filas 11, 12 y 13, y su parte de la 15, del [diseño común](../tkt-008/design.md); la fila 11 va en `sonnet` por las cifras de `RN-03` y `RN-07`.
