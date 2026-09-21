# Aplicación de página única con React, sin metaframework

## Estado

Aceptado · **actualizado el 2026-09-19** con la decisión de generar los tipos del OpenAPI y con la consecuencia de [ADR-015](20260919-captura-diferida-sin-conexion.md), que obliga a que esta aplicación funcione sin conexión en obra.

## Contexto y problema

El frontend es React por preferencia declarada al inicio del proyecto. Lo que queda por decidir es **cómo** se construye: aplicación de página única con Vite, o metaframework con renderizado en servidor como Next.js o Remix.

Las características del producto que condicionan la elección:

**No hay público anónimo.** Toda la aplicación está detrás de autenticación. No hay nada que indexar ni primera carga que optimizar para un visitante que llega de un buscador.

**Es mayoritariamente tablas.** Semáforo por partida, explosión de insumos, catálogos, nómina semanal, saldos pendientes con su antigüedad. Rejillas con ordenación, filtrado y desglose.

**El backend ya es Python.** Un metaframework añadiría un servidor Node junto al servidor Python, duplicando la superficie de despliegue de un producto que [ADR-008](20260918-despliegue-single-tenant.md) definió como un solo despliegue por empresa.

**El dinero llega como cadena.** El [contrato de error](20260918-contrato-error-negocio.md) y las respuestas transportan importes como texto para que no pasen por el flotante de JavaScript.

**En la obra no hay internet** (`PA-13`, `RNF-18`). Es lo último que se supo y lo que más condiciona: la aplicación tiene que poder instalarse, arrancar y capturar sin servidor al otro lado. Eso descarta cualquier composición que necesite una respuesta del servidor para pintar la primera pantalla.

## Opciones consideradas

* Aplicación de página única: React + Vite + React Router
* Next.js o Remix con renderizado en servidor
* Renderizado en servidor desde Python con plantillas y HTMX

## Decisión

Se elige la **aplicación de página única**, con esta composición:

| Pieza | Elección | Razón |
|---|---|---|
| Build | Vite | Estándar fuera de un metaframework |
| Enrutado | React Router v7 | Ecosistema amplio, sin necesidad de rutas tipadas exóticas |
| Estado de servidor | TanStack Query | Invalidación de caché tras cada mutación: es lo que hace que el semáforo refleje una entrada registrada hace un minuto. Su caché **persistida** es además la mitad de lectura del modo sin conexión |
| Tablas | TanStack Table | La aplicación es tablas; merece una librería de tablas de verdad |
| Estilos | Tailwind CSS v4 | |
| Componentes | shadcn/ui | Se **copian** al repositorio en lugar de instalarse |
| Formularios | React Hook Form | Estado y validación del formulario en el cliente |
| Validación de formulario | Zod | **Valida lo que el usuario escribe, no lo que la API devuelve.** Campos obligatorios, formato y rangos, para no gastar un viaje de red. La validación autoritativa sigue siendo la del servidor |
| Cliente y tipos de API | `openapi-typescript` + `openapi-fetch` | **Los tipos se generan del OpenAPI que FastAPI publica; no se escriben dos veces.** Pydantic v2 ya declara los importes como `string` en el esquema, así que el tipo generado es el que `decimal.js` espera |
| Sin conexión | Service worker + caché persistida + cola en IndexedDB | [ADR-015](20260919-captura-diferida-sin-conexion.md) |
| Decimal | decimal.js | Convierte los importes que llegan como cadena |

**shadcn/ui merece una nota.** No es una dependencia sino código que se copia al repositorio, y eso importa para un componente concreto: la **pantalla de bloqueo** de TKT-008, que renderiza cualquier violación de regla mostrando disponible, excedente y las acciones del contrato de error. No es un diálogo genérico: es un componente del dominio, y conviene poder modificarlo sin luchar contra la API de una librería.

**El contrato de API no se replica a mano, y esto corrige lo que decía la versión anterior de este ADR.** Aquí se afirmaba que *"los esquemas Zod replican las validaciones de Pydantic"* y se aceptaba escribir las validaciones dos veces. Es un error y el [stack §5.4](../06-stack-tecnologico.md#54-el-contrato-de-api-no-se-replica-a-mano) lo corrigió: **un esquema Zod que espeja un modelo de Pydantic duplica el contrato en dos lenguajes que nadie obliga a coincidir**. El día que un campo cambia de nombre en el servidor, el espejo sigue compilando y el error aparece en ejecución, en una pantalla, delante de alguien.

La separación correcta es: **Zod valida lo que el usuario escribe; el OpenAPI define lo que la API devuelve.** Lo primero es experiencia de usuario, es local y no tiene por qué parecerse a nada del servidor. Lo segundo se genera. Cuando un esquema Zod empieza a describir una respuesta, hay un contrato duplicado.

**Se descarta el metaframework.** El renderizado en servidor resuelve problemas que este producto no tiene —SEO, primera carga para anónimos, contenido público— al precio de un modelo de renderizado dual y un servidor Node adicional. Para una aplicación interna detrás de autenticación, es complejidad sin contrapartida. Sin conexión, además, **no habría servidor que renderizara nada**: `RNF-18` lo descarta por segunda vez y por un motivo más duro.

**Se descarta el renderizado desde Python con HTMX**, que sería la opción de menor superficie total y evitaría el segundo lenguaje. No encaja aquí porque el frontend tiene estado de cliente real: captura de requisiciones con varios renglones y cálculo de importes en vivo, previsualización de importación con tabla de errores navegable, y un tablero con desglose que se expande. Además, la preferencia por React está declarada desde el inicio.

## Consecuencias

**Positivas**

* Un solo artefacto de despliegue: el backend sirve los estáticos ya compilados.
* TanStack Query cubre la sincronización con el servidor, que es el problema real de esta aplicación: que lo mostrado refleje lo que acaba de pasar.
* La pantalla de bloqueo es código propio y evoluciona con el contrato de error.

**Negativas o costes aceptados**

* La primera carga descarga todo el paquete. Irrelevante en una intranet con usuarios recurrentes, y en obra ocurre **una sola vez**: el service worker lo conserva. Si creciera, se divide por ruta.
* Hay dos lenguajes y dos cadenas de herramientas que mantener. Es el precio de React sobre Python, asumido al declarar la preferencia.
* Las **validaciones de formulario** se escriben dos veces, en Zod y en Pydantic. Se acepta porque son dos cosas distintas con el mismo aspecto: la del cliente evita un viaje de red, la del servidor es la autoritativa. Lo que **no** se duplica es la forma de las respuestas, que se genera del OpenAPI.
* El diseño deja de ser solo de escritorio. La captura de avance y la de recepción se usan de pie en obra, y eso es trabajo de diseño que antes no estaba presupuestado ([ADR-015](20260919-captura-diferida-sin-conexion.md)).

**Cuándo revisar esta decisión**

* ~~Si el paquete inicial superara un tamaño que se note en obra con conexión pobre~~ — **ya ocurrió, y peor de lo previsto**: `PA-13` confirmó que en obra no hay conexión en absoluto. La respuesta no fue dividir por ruta sino [ADR-015](20260919-captura-diferida-sin-conexion.md). El tamaño del paquete pasa de ser una molestia a ser una restricción con motivo.
* Si apareciera un portal para clientes o proveedores —hoy descartado— el renderizado en servidor volvería a la mesa.
* Si la captura sin conexión llegara a necesitar cámara, almacenamiento grande o trabajo en segundo plano del sistema operativo, habría que reconsiderar la aplicación híbrida que ADR-015 descarta hoy por el criterio C4.
