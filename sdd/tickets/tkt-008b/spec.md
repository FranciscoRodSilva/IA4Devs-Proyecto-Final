# Spec · TKT-008b · Inicio de sesión, armazón por rol y humo

> [← index](_index.md) | Spec común: [TKT-008](../tkt-008/spec.md) | Diseño común: [design](../tkt-008/design.md)

## Contexto y problema

TKT-008 se partió en tres tickets hermanos al aprobarse su diseño, el 2026-10-26, porque el plan sumaba unas 4,600 líneas (decisión D-1). Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-008/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-008b es lo que un usuario ve primero: el enrutado, la pantalla de inicio de sesión, el armazón con el menú de su rol y la salida. Se apoya en el cliente de API y en los tipos de TKT-008a. Cierra además el recorrido de humo de Playwright y la documentación del arranque, que describe el ticket completo.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-008/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1**, en su parte de enrutado: React Router, carpetas por módulo de negocio y la página de «no encontrado» |
| | **M3**, en su parte de sesión: un `401` fuera del inicio de sesión devuelve al inicio con el aviso; un `403` vuelve a pedir `GET /sesion` |
| | **M4** completo: la pantalla de inicio de sesión del wireframe §1 y sus cinco estados de rechazo |
| | **M5** completo: el armazón del wireframe §2 con la unión de las secciones, las rutas marcador, la guarda de sección, el usuario sin roles, *Salir* y el menú plegable en teléfono |
| | **M10**, en su parte: las pruebas de las filas 8 a 10 y la documentación (fila 16), incluidos los cambios que el diseño asigna a `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md` y `tools/verificar_docs.py` |
| **Should** | **S1**: el recorrido de humo de Playwright contra el backend real |
| **Won't** | Los componentes reutilizables (TKT-008c), lo de TKT-008a y los Won't de la spec común |

## Non-goals

- No construye la pantalla de bloqueo, el formulario de catálogo ni la captura de motivo: el inicio de sesión usa su propio formulario.
- No cambia el cliente de API ni la generación de tipos de TKT-008a, salvo que una prueba de esta parte revele un fallo; en ese caso se corrige con su test en rojo y se anota en `impl.md`.
- Los non-goals de la [spec común](../tkt-008/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

`RNF-01`, `RNF-02`, `RNF-03`, `RNF-04` y `RNF-05`, y las reglas 9 y 10 de `CLAUDE.md`. Detalle en la [spec común](../tkt-008/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-008/spec.md#invariantes-que-deben-sobrevivir-al-cambio). `CLAUDE.md` y `docs/arranque-local.md` ya los modificó TKT-008a, con el bloque de comandos de frontend, la sección «Frontend» y la tabla. Aquí solo se añade lo que la fila 16 aún no cubre. Este ticket modifica `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md` y `tools/verificar_docs.py`.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-1` `[M]` | Esc. 2 y 3: estructura por módulo y ruta que no existe | 8, 9 |
| `CA-3` `[M]` | Esc. 3: origen no verificado, visto en la pantalla | 10 |
| `CA-5` `[M]` | Todos: sesión terminada, primera visita sin aviso, el `401` del propio inicio y el rol retirado | 9, 10 |
| `CA-6` `[M]` | Todos: iniciar sesión, sesión vigente y sus cinco rechazos | 10 |
| `CA-7` `[M]` | Todos: secciones por rol, unión, marcadores, vencimiento, sección ajena, usuario sin roles, *Salir* y teléfono | 8, 9 |
| `CA-14` `[S]` | Todos: entrar y salir, y credenciales incorrectas | 14 |
| `CA-R1` a `CA-R3` `[M]` | Repetidos sobre el árbol con esta parte | 15 |
| `CA-R4` `[M]` | Documentación | 16 |

Los mutantes que corren aquí son MT-15 a MT-23 (su parte de la fila 15).

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-008a. Puede ir en paralelo con TKT-008c |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común, ya aprobado |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Los seis roles inician sesión y ven solo las secciones de su rol |
| **E** | Estimable sin investigar antes | Sí | Unas 1,600 líneas según el diseño |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Por encima del tope de unas 400 líneas (D-1) |
| **T** | Sus criterios se pueden ejecutar | Sí | Vitest con MSW; Playwright con Docker y la base migrada |

Una sola reserva: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan, cada uno con su test nombrado por el criterio.
- [ ] Ningún mutante de MT-15 a MT-23 deja la suite en verde.
- [ ] `npm run e2e` en verde dos veces seguidas, con la siembra idempotente.
- [ ] `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y los tests de `tools/` en verde.
- [ ] Auditoría de arquitectura, de código, de seguridad y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-008/spec.md#preguntas-abiertas-y-supuestos), los que toca este ticket: `PA-T2` (primera sección tras iniciar sesión), `PA-T3` (usuario sin roles), `PA-T4` (nombre de los tests por criterio), `PA-T6` (`429` y origen probados contra un doble), `PA-T7` (la cookie `Secure` en desarrollo) y `PA-T8` (la tabla de secciones duplica los `x-roles`).

## Pasada adversarial

La de la [spec común](../tkt-008/spec.md#pasada-adversarial) y la del diseño común. La partición no añade objeciones: solo reparte criterios ya revisados.

## Contexto técnico

El de la [spec común](../tkt-008/spec.md#contexto-técnico). Filas 8, 9, 10, 14 y 16, y su parte de la 15, del [diseño común](../tkt-008/design.md).
