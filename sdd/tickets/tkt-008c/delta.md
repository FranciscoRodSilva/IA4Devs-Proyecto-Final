# Delta · TKT-008c · Componentes reutilizables

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| La pantalla de bloqueo: cabecera por `tipo` («Operación bloqueada» y la regla, «No se puede completar» y el código, «Inténtalo de nuevo»), las cifras del `detalle` formateadas tal como llegaron, las tablas por insumo y por renglón, las claves desconocidas con su nombre crudo, un botón por acción en su orden y «Reintentar» con la espera que pide el servidor. Tratamiento visual propio en ámbar (`data-estado="bloqueado"`), distinto del error | `frontend/src/compartido/componentes/bloqueo/` (`PantallaBloqueo`, `CabeceraBloqueo`, `DetalleCifras`, `BotonesAcciones`, `etiquetas.ts`) | Que toda pantalla de la fase 1 pinte un `409` de `RN-03`, `RN-07` o del catálogo de conflictos igual y sin calcular ninguna cifra (`CA-8` a `CA-10`) |
| La captura de motivo obligatorio: diálogo con foco en «Motivo», recorte del texto, tope de 2,000 caracteres, el `422` del servidor junto al campo y cualquier otro rechazo entregado a la pantalla | `frontend/src/compartido/formularios/CapturaMotivo.tsx`, `motivo.formulario.ts` | `RN-04` en las historias que exigen motivo (`CA-12`) |
| El formulario de catálogo: foco en el primer campo, validación con el esquema que recibe, el `422` junto a cada campo, el duplicado en línea sin perder lo escrito, `REGLA_NEGOCIO` y `CONCURRENCIA` delegados a la pantalla, y la baja con confirmación previa o con motivo (`PA-T12`) | `frontend/src/compartido/formularios/` (`FormularioCatalogo`, `ConflictoEnLinea`, `ConfirmacionBaja`, `catalogo.formulario.ts`) | Los catálogos de HDU-001, HDU-004 y HDU-007 (`CA-11`) |
| Identidad visual de la constructora, a petición del usuario: el logo de AP Buildings en la cabecera del armazón y en el inicio de sesión, y una paleta derivada del logo en los tokens de `:root` (verde bosque `#1c3a2f` como primario, arenas y taupes como secundarios) | `frontend/src/assets/ap-logo.jpeg`, `frontend/src/index.css`, `Armazon.tsx`, `PaginaInicioSesion.tsx` | Que el cliente lleve la marca del cliente final. Solo presentación |
| Pruebas: 60 casos nuevos en el cliente sobre los 154 de TKT-008b (214 en total), y cinco fábricas de cuerpos de error (`errorRn03ExcedeImporte`, `errorRn03PorVolumen`, `errorRn07ExcedeOrdenado`, `errorConflictoEstado`, `errorConcurrencia`) | `frontend/src/compartido/**/*.test.tsx`, `frontend/src/pruebas/cuerpos.ts`, tres pruebas de marca en `Armazon.test.tsx`, `PaginaInicioSesion.test.tsx` y `scripts/esqueleto.test.ts` | Los criterios de la tabla de `impl.md` y los hallazgos de la revisión |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Cierre por defecto de los diálogos de shadcn | `frontend/src/components/ui/dialog.tsx` | El texto accesible de la X y el del pie decían «Close» → «Cerrar» |
| Armazón e inicio de sesión | `Armazon.tsx`, `PaginaInicioSesion.tsx` | Sin marca → logo, cabecera sobre `bg-card`, menú lateral sobre `bg-sidebar` con el enlace activo marcado, inicio de sesión en una tarjeta. Textos, roles e identificadores sin cambio |
| Paleta | `frontend/src/index.css` | Grises neutros de shadcn → tokens de la marca en `:root`; en `.dark` solo cambian el primario y el del menú lateral |
| Comentario de una prueba de TKT-008a | `frontend/src/api/cliente.test.ts:322` | Citaba literalmente la cookie del documento → la describe, para que la búsqueda de `CA-R3` salga vacía. La prueba no cambia |
| Spec común | `sdd/tickets/tkt-008/spec.md` | → preguntas abiertas `PA-T13` a `PA-T17` |
| Spec de este ticket | `sdd/tickets/tkt-008c/spec.md` | → excepción de non-goals por el ajuste de marca, `dialog.tsx` y el comentario; MT-33 a MT-35; `PA-T13` a `PA-T17` en su lista |
| Diseño común | `sdd/tickets/tkt-008/design.md` | Filas 11, 12 y 13 `⚠ Ajustado` y la parte de 008c de la fila 15 hecha |

## Eliminado

Nada.

## Comportamiento observable nuevo

- Al abrir el cliente, el inicio de sesión y la cabecera del armazón muestran el logo de AP Buildings, y la interfaz usa la paleta de la marca. Nada más cambia para el usuario: ninguna pantalla consume todavía los tres componentes.
- Los diálogos del cliente anuncian su botón de cierre como «Cerrar».
- Para un integrador del cliente: `PantallaBloqueo`, `CapturaMotivo` y `FormularioCatalogo` están disponibles en `src/compartido/`. Las pantallas de la fase 1 los cablean; ninguno decide qué hace una acción de negocio, salvo `REINTENTAR`.
- El backend no cambia: `backend/` no tiene ningún archivo en el diff.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO, esquema y `docs/api/openapi.yaml` | Sin cambio | — |
| Tipos generados del cliente | Sin cambio | — |
| Componentes compartidos del cliente | Añade `PantallaBloqueo`, `CapturaMotivo`, `FormularioCatalogo` y sus props, más `DetalleCifras`, `BotonesAcciones`, `CabeceraBloqueo` y `ConflictoEnLinea` | No |
| Texto accesible de `DialogContent` | «Close» → «Cerrar» | No para el código; sí para una prueba que busque «Close», y ninguna lo hacía |

## Decisiones (ADR)

No se creó ADR. Ninguna decisión del ticket tuvo alternativas descartadas con evidencia que un recién llegado necesite encontrar en `docs/adr/`:

- **El foco inicial de los diálogos se fija con `initialFocus` de `@base-ui/react`**, no con `onOpenAutoFocus` como decía el diseño, porque el `Dialog` instalado no es Radix. Es una adaptación a la biblioteca, no una elección entre opciones.
- **La paleta y el logo** son una instrucción del usuario, no una decisión de arquitectura.
- **Las conversiones de tipo de `catalogo.formulario.ts`** quedan como pregunta abierta (`PA-T17`): cambiar el contrato del diseño las eliminaría, y esa decisión corresponde a la persona que aprueba.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un hook que toma su valor al montar, como `useCuentaAtras`, exige una `key` en quien lo usa cuando el valor cambia sin desmontar; si no, la segunda espera nace vencida | C1 y A1, TC-R101 y TC-R103 | Todo componente con temporizador que reciba datos nuevos sin desmontarse |
| En react-hook-form, `setError` con `shouldFocus: true` dentro de un bucle deja el foco en el último campo: el foco se pide solo para el primero | N1 de código, TC-R118 | Todo formulario que pinte varios errores del servidor |
| Un `try` que envuelve también los callbacks del llamador convierte un fallo de la pantalla en un rechazo falso: el `try` debe cubrir solo la llamada que puede fallar | N2 de código, TC-R114 y TC-R115 | Todo componente que entregue el resultado a callbacks |
| Una región `aria-live` que nace junto con su contenido no se anuncia de forma fiable: tiene que existir antes | C4, TC-R119 | Todo aviso que aparezca dentro de un formulario |
| Un ayudante de prueba que captura rechazos sin manejar debe afirmar lo capturado; si lo descarta, silencia cualquier error | N3 de código | Toda prueba que intercepte `unhandledRejection` |
| El `Dialog` de shadcn instalado (`base-nova`) es `@base-ui/react`: no tiene `onOpenAutoFocus` y trae una X con texto en inglés | Ajustes de las filas 12 y 13, C6 | Todo diálogo nuevo del cliente |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `plantilla` | El diseño común fijó `onOpenAutoFocus` de Radix sin comprobar qué primitiva instaló TKT-008a; dos filas tuvieron que ajustarse. El diseño de una fila de interfaz debería citar la biblioteca real de la primitiva que usa | Baja |
| `guardrail` | La auditoría de cierre de fase de `/sdd-ejecutar` dio APROBADO y la de `/sdd-revisar`, sobre el mismo código, encontró un Mayor (la espera del reintento). Es la segunda vez, tras TKT-008b, que la revisión encuentra ramas sin test que la ejecución no veía | Media |
| `agente` | Los ciclos de corrección introdujeron hallazgos nuevos en cada reauditoría (el `try` amplio, el ayudante que descartaba lo capturado, etiquetas de auditoría en el código). Tres ciclos para cerrar Menores que el propio corrector creó | Media |
| `convención` | `corrector-revision` y `tester-frontend` dejaron identificadores de auditoría (C1, N1…) en nombres de prueba y comentarios de producción; hubo que limpiarlos en el ciclo 3 y aún quedan en nombres de prueba. Falta una convención escrita sobre dónde va la trazabilidad de un hallazgo | Media |
| `agente` | Un desarrollador añadió un texto «Disponible en mm:ss» que nadie pidió; lo quitó el orquestador. Otro corrector avisó de CRLF en un archivo que estaba en LF | Baja |
| `comando` | El usuario pidió un ajuste de marca al lanzar `/sdd-ejecutar`, fuera de los non-goals del ticket. No hay un sitio previsto para registrar una excepción de alcance pedida por el usuario sin pasar por `/sdd-escalar`; se registró en la spec a mitad de la revisión, tras dos hallazgos de auditoría | Media |
| `modelo` | `desarrollador-react` subió a `sonnet` en el ajuste de marca (decisiones visuales sin diseño) y `corrector-revision` en el ciclo 1 (Mayor que toca `RNF-16`). Las reauditorías acotadas a Menores fueron en `haiku`; la de código del ciclo 2 también, y encontró el Mayor N3, por lo que la del ciclo 3 subió a `sonnet` | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `PA-T13` a `PA-T17`: error del servidor sin campo visible, cierre de un diálogo durante el envío, motivo perdido tras una baja rechazada, textos de error no validados y conversiones de tipo del formulario de catálogo | Deciden producto o la persona que aprueba | El primer ticket de pantalla que use cada componente |
| Un `consumido_desglose` que llegue sin `consumido` no se pinta | El contrato siempre manda ambos | Sin ticket |
| `CapturaMotivo` no absorbe una excepción de `alConfirmar`, a diferencia de `ConfirmacionBaja` | `pedir` no lanza; asimetría señalada como observación | El siguiente ticket que toque los formularios compartidos |
| Las cantidades se presentan con dos decimales aunque la columna guarde cuatro | El redondeo al presentar es `PA-T5`, de TKT-008a | Ticket propio sobre la escala de presentación |
| Los nombres de prueba de `PantallaBloqueo.test.tsx`, `ConflictoEnLinea.test.tsx` y `CapturaMotivo.test.tsx` conservan identificadores de hallazgo, y quedan comentarios con identificadores de auditoría de tickets anteriores (`Armazon.tsx`, `PaginaInicioSesion.tsx`, `dinero.test.ts`, `cliente.test.ts`, `sesion.test.ts`, `ProveedorApi.test.tsx`) | Fuera del alcance de la revisión | El siguiente ticket que toque esas pruebas, una vez escrita la convención |
| El borde de los campos (`--input`) queda por debajo de 3:1 de contraste contra blanco | Observación de la auditoría de código; tampoco lo cumplía el valor anterior | Ticket de accesibilidad o el primero de pantalla |
| `PantallaBloqueo` usa un `id` fijo para su título; dos instancias en una pantalla lo duplicarían | Literal del diseño | El primer ticket que monte dos |
| Las pantallas que consuman `alAccion` deben resolver cada `clave` a una operación tipada y no invocar `Accion.ruta` (S3) | Lo decide cada pantalla | Cada ticket de pantalla |

## Pull request

**Título:** `TKT-008c · Componentes reutilizables e identidad visual`
**Origen:** `agent+human-review`
**Cuerpo:** lo prepara `git-entrega` en el cierre, con qué, por qué, criterios cubiertos y cómo verificarlo. Base: `Produccion`, que ya contiene TKT-008a y TKT-008b.
