# Impl · TKT-008c · Componentes reutilizables

> [← index](_index.md) | [← design común](../tkt-008/design.md) | [Siguiente: delta](delta.md)

## Qué se implementó

Los tres componentes reutilizables de la fase 1. La pantalla de bloqueo pinta cualquier `409` del contrato de error: la cabecera según su `tipo`, las cifras del `detalle` tal como llegaron (el excedente nunca se calcula en el cliente), las tablas por insumo y por renglón, las claves desconocidas con su nombre crudo, un botón por acción en su orden y el reintento con espera para `CONCURRENCIA`. La captura de motivo obligatorio (`RN-04`) recorta el texto, valida en el cliente solo la forma y entrega al servidor la decisión. El formulario de catálogo cubre foco, guardado, errores de forma y del servidor, el duplicado en línea sin perder lo escrito, la delegación de `REGLA_NEGOCIO` y `CONCURRENCIA`, y la baja con confirmación previa o con motivo (`PA-T12`).

Además, a petición del usuario al lanzar la ejecución, el cliente adopta la identidad visual de la constructora: el logo de AP Buildings (`docs/APLogo.jpeg`) en la cabecera del armazón y en el inicio de sesión, y una paleta derivada del logo (verde bosque del monograma como primario, arenas y taupes como secundarios) en los tokens de `src/index.css`. El cambio es solo de presentación; el ámbar del estado bloqueado se conserva para que no se confunda ni con el error ni con la marca.

Ningún archivo bajo `backend/` está en el diff.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-27 | La rama `tkt-008c-componentes` sale de `Produccion`, que ya contiene TKT-008a y TKT-008b fusionados; la abre el orquestador sin despachar `git-entrega` | Es un `git switch -c` sobre un árbol limpio; no había nada que revisar en el diff de apertura |
| 2026-10-27 | Fila 11: `BotonesAcciones` recibe `{ acciones, alAccion, alCerrar?, alReintentar?, esperaReintentoS? }` en lugar de `{ acciones, alAccion, reintento? }`. «Cerrar» solo se pinta si llega `alCerrar` | `ConflictoEnLinea` (fila 13) necesita los botones sin «Cerrar»; así no hace falta una bandera aparte. El comportamiento del contrato no cambia |
| 2026-10-27 | Fila 11: el desarrollador añadió un texto «Disponible en mm:ss» junto a «Reintentar»; el orquestador lo quitó antes de cerrar la fila | Funcionalidad que nadie pidió. La suite de la fila siguió en verde (13 de 13) tras quitarlo |
| 2026-10-27 | Fila 11: `etiquetas.ts` exporta, además de `CLAVES_DETALLE` y `ETIQUETAS_ACCION`, las claves de tablas, las partes del consumido, las claves ocultas (D-8) y `CLAVE_EXCEDENTE` | Evita literales dispersos en `DetalleCifras`. Sin efecto en el comportamiento |
| 2026-10-27 | Fila 11: un `consumido_desglose` que llegue sin `consumido` no se pinta | El desglose va dentro de la fila «Consumido», según el diseño, que no cubre el caso del desglose huérfano. Queda como hueco anotado abajo |
| 2026-10-27 | Filas 12 y 13: el foco inicial se fija con `initialFocus={ref}` de `@base-ui/react`, no con `onOpenAutoFocus` + `setFocus` | El `Dialog` de shadcn que instaló TKT-008a es `@base-ui/react` 1.9, no Radix, y no expone `onOpenAutoFocus`. El efecto es el mismo y TC-78 y TC-82 lo prueban |
| 2026-10-27 | Filas 12 y 13: `CapturaMotivo` y `ConfirmacionBaja` llevan `showCloseButton={false}`; el formulario vive en un hijo que se desmonta al cerrar | La X por omisión de shadcn sería un segundo botón de cierre que el contrato no pide. Desmontar al cerrar hace que cada apertura empiece vacía |
| 2026-10-27 | Fila 12: un `VALIDACION` sin ninguna entrada en `errores` se entrega a `alRechazo`; con varias entradas para `motivo`, se marca la primera `(asumido)` (`PA-T13`) | El diseño no cubre esos casos y la captura no tiene dónde pintarlos |
| 2026-10-27 | Fila 13: `CabeceraBloqueo.tsx` se extrae de `PantallaBloqueo` con `tamano: "bloque" \| "linea"`, y la reutiliza `ConflictoEnLinea` | Una sola cabecera por `tipo`. `PantallaBloqueo.test.tsx` siguió en verde |
| 2026-10-27 | Fila 13: `catalogo.formulario.ts` concentra la frontera entre Zod 4 y react-hook-form con tres conversiones documentadas (`resolverCatalogo`, `valoresDeFormulario`, `rutaDeCampo`) | Con el esquema como parámetro de tipo `E`, las sobrecargas de `zodResolver` no enlazan `z.input<E>` y `z.output<E>` y `useForm` infiere `Record<string, unknown>`. Sin `any` ni `!`. Se deja para revisión `(asumido)` (`PA-T17`) |
| 2026-10-27 | Fila 13: cualquier rechazo de la baja cierra el diálogo de confirmación o de motivo y se pinta en el formulario principal; un `ok` cierra el diálogo antes de `alHecha()`; el aviso genérico de la baja dice «No se pudo dar de baja.» | El diseño no dice dónde se pinta el `409` de la baja ni da texto para su error genérico. El texto queda `(asumido)` para validación (`PA-T16`) |
| 2026-10-27 | Ajuste de marca, pedido por el usuario: `src/assets/ap-logo.jpeg` (copia de `docs/APLogo.jpeg`), tokens de `:root` en `src/index.css` con la paleta de AP Buildings, logo en `Armazon.tsx` (cabecera, `h-8`) y en `PaginaInicioSesion.tsx` (encima del título, `h-24`), menú lateral con `bg-sidebar` y enlace activo marcado. En `.dark` solo cambian `--primary`, `--primary-foreground` y `--sidebar-primary` | Instrucción explícita del usuario al lanzar `/sdd-ejecutar`. Toca archivos de TKT-008a y TKT-008b (`Armazon.tsx`, `PaginaInicioSesion.tsx`, `index.css`) solo en clases, tokens de color y una imagen; todos sus textos, roles e identificadores se conservan y sus tests siguen en verde. Se añaden tres pruebas `tkt008c_marca` escritas antes del cambio. Se comprobó a mano a 375 px que no hay desplazamiento horizontal en el inicio de sesión, y el humo TC-92 sigue en verde |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `frontend/src/compartido/componentes/bloqueo/PantallaBloqueo.tsx` | nuevo | frontend |
| `frontend/src/compartido/componentes/bloqueo/CabeceraBloqueo.tsx` | nuevo (refactor de la fila 13) | frontend |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | nuevo | frontend |
| `frontend/src/compartido/componentes/bloqueo/BotonesAcciones.tsx` | nuevo | frontend |
| `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | nuevo | frontend |
| `frontend/src/compartido/formularios/CapturaMotivo.tsx` | nuevo | frontend |
| `frontend/src/compartido/formularios/motivo.formulario.ts` | nuevo | frontend |
| `frontend/src/compartido/formularios/FormularioCatalogo.tsx` | nuevo | frontend |
| `frontend/src/compartido/formularios/ConflictoEnLinea.tsx` | nuevo | frontend |
| `frontend/src/compartido/formularios/ConfirmacionBaja.tsx` | nuevo | frontend |
| `frontend/src/compartido/formularios/catalogo.formulario.ts` | nuevo | frontend |
| `frontend/src/assets/ap-logo.jpeg` | nuevo (ajuste de marca) | frontend |
| `frontend/src/index.css` | modificado (ajuste de marca) | frontend |
| `frontend/src/app/armazon/Armazon.tsx` | modificado (ajuste de marca, solo presentación) | frontend |
| `frontend/src/modulos/identidad/PaginaInicioSesion.tsx` | modificado (ajuste de marca, solo presentación) | frontend |
| `frontend/src/compartido/componentes/bloqueo/PantallaBloqueo.test.tsx` | nuevo | pruebas |
| `frontend/src/compartido/formularios/CapturaMotivo.test.tsx` | nuevo | pruebas |
| `frontend/src/compartido/formularios/FormularioCatalogo.test.tsx` | nuevo | pruebas |
| `frontend/src/pruebas/cuerpos.ts` | modificado: `errorRn03ExcedeImporte`, `errorRn03PorVolumen`, `errorRn07ExcedeOrdenado`, `errorConflictoEstado`, `errorConcurrencia` | pruebas |
| `frontend/src/app/armazon/Armazon.test.tsx` | modificado: `tkt008c_marca` | pruebas |
| `frontend/src/modulos/identidad/PaginaInicioSesion.test.tsx` | modificado: `tkt008c_marca` | pruebas |
| `frontend/scripts/esqueleto.test.ts` | modificado: `tkt008c_marca` | pruebas |
| `frontend/src/components/ui/dialog.tsx` | modificado en la revisión: «Close» pasa a «Cerrar» (C6) | frontend |
| `frontend/src/compartido/formularios/ConflictoEnLinea.test.tsx` | nuevo en la revisión | pruebas |
| `frontend/src/compartido/formularios/ConfirmacionBaja.test.tsx` | nuevo en la revisión | pruebas |
| `frontend/src/api/cliente.test.ts` | modificado en la revisión: comentario reformulado, sin tocar la prueba | pruebas |
| `sdd/tickets/tkt-008/design.md` | modificado: estado de las filas 11, 12, 13 y 15 | especificación |
| `sdd/tickets/tkt-008/spec.md` | modificado en la revisión: `PA-T13` a `PA-T17` | especificación |
| `sdd/tickets/tkt-008c/spec.md` | modificado en la revisión: excepción de non-goals y MT-33 a MT-35 | especificación |
| `sdd/tickets/tkt-008c/impl.md`, `_index.md` | nuevo · modificado | especificación |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-65 | `tkt008_ca08_esc01 · bloqueo por importe` | feliz | `CA-8` esc. 1, `RNF-13` | FALLA: módulo inexistente | PASA |
| TC-66 | `tkt008_ca08_esc01 · el excedente es el que llegó` | **rechazo** | `CA-8` esc. 1 | FALLA: módulo inexistente | PASA |
| TC-67 | `tkt008_ca08_esc02 · por volumen` | feliz | `CA-8` esc. 2 | FALLA: módulo inexistente | PASA |
| TC-68 | `tkt008_ca08_esc03 · excedente de recepción` | feliz | `CA-8` esc. 3, `RN-07` | FALLA: módulo inexistente | PASA |
| TC-69 | `tkt008_ca08_esc04 · clave desconocida` | **rechazo** | `CA-8` esc. 4, D-8 | FALLA: módulo inexistente | PASA |
| TC-70 | `tkt008_ca08_esc05 · cifra no decimal` | **rechazo** | `CA-8` esc. 5 | FALLA: módulo inexistente | PASA |
| TC-71 | `tkt008_ca09_esc01 · conflicto` | feliz y **rechazo** | `CA-9` esc. 1 | FALLA: módulo inexistente | PASA |
| TC-72 | `tkt008_ca09_esc02 · reintentar con espera` | feliz | `CA-9` esc. 2, `RNF-16` | FALLA: módulo inexistente | PASA |
| TC-73 | `tkt008_ca09_esc03 · sin función de reintento` | **rechazo** | `CA-9` esc. 3 | FALLA: módulo inexistente | PASA |
| TC-74 | `tkt008_ca09_esc04 · solo 409` (con `npm run typecheck`) | **rechazo** | `CA-9` esc. 4 | FALLA: `TS2307` y los dos `@ts-expect-error` sin usar | PASA |
| TC-75 | `tkt008_ca10_esc01 · un botón por acción` | feliz | `CA-10` esc. 1 | FALLA: módulo inexistente | PASA |
| TC-76 | `tkt008_ca10_esc02 · solo Cerrar` | **rechazo** | `CA-10` esc. 2 | FALLA: módulo inexistente | PASA |
| TC-77 | `tkt008_ca10_esc03 · clave desconocida` | **rechazo** | `CA-10` esc. 3, D-7 | FALLA: módulo inexistente | PASA |
| TC-78 | `tkt008_ca12_esc01 · confirmar con motivo` | feliz | `CA-12` esc. 1, `RN-04` | FALLA: módulo inexistente | PASA |
| TC-79 | `tkt008_ca12_esc02 · sin motivo` (vacío y solo espacios) | **rechazo** | `CA-12` esc. 2 | FALLA: módulo inexistente | PASA |
| TC-80 | `tkt008_ca12_esc03 · el servidor rechaza el motivo` | **rechazo** | `CA-12` esc. 3 | FALLA: módulo inexistente | PASA |
| TC-81 | `tkt008_ca12_esc04 · el servidor rechaza la operación` | **rechazo** | `CA-12` esc. 4 | FALLA: módulo inexistente | PASA |
| TC-C1 | `tkt008_ca12 · cancelar no envía nada` | **rechazo** | `CA-12`, contrato | FALLA: módulo inexistente | PASA |
| TC-C2 | `tkt008_ca12 · el error de otro campo va a la alerta del diálogo` | **rechazo** | `CA-12`, contrato | FALLA: módulo inexistente | PASA |
| TC-C3 | `tkt008_ca12 · Escape cierra como cancelar` | **rechazo** | `CA-12`, contrato | FALLA: módulo inexistente | PASA |
| TC-82 | `tkt008_ca11_esc01 · foco en el primer campo` | feliz | `CA-11` esc. 1 | FALLA: módulo inexistente | PASA |
| TC-83 | `tkt008_ca11_esc02 · guardar` | feliz | `CA-11` esc. 2 | FALLA: módulo inexistente | PASA |
| TC-84 | `tkt008_ca11_esc03 · forma inválida` | **rechazo** | `CA-11` esc. 3 | FALLA: módulo inexistente | PASA |
| TC-85 | `tkt008_ca11_esc04 · el servidor responde 422` | **rechazo** | `CA-11` esc. 4 | FALLA: módulo inexistente | PASA |
| TC-86 | `tkt008_ca11_esc05 · duplicado en línea` | **rechazo** | `CA-11` esc. 5 | FALLA: módulo inexistente | PASA |
| TC-87 | `tkt008_ca11 · una regla de negocio / una concurrencia al guardar se delega a la pantalla` (dos casos) | **rechazo** | `CA-11`, `M6` | FALLA: módulo inexistente | PASA |
| TC-C4 | `tkt008_ca11 · cualquier otro error al guardar va a la cabecera` (con y sin mensaje del servidor) | **rechazo** | `CA-11`, contrato | FALLA: módulo inexistente | PASA |
| TC-88 | `tkt008_ca11_esc06 · …` (cancelar no envía nada, confirmar sin motivo envía `null`, con `exigeMotivo` abre «Motivo») | feliz y **rechazo** | `CA-11` esc. 6, `PA-T12` | FALLA: módulo inexistente | PASA |
| TC-89 | `tkt008_ca11_esc07 · la baja la rechaza el servidor` y `· cualquier otro error de la baja va a la cabecera` | **rechazo** | `CA-11` esc. 7 | FALLA: módulo inexistente | PASA |
| TC-M1 | `tkt008c_marca · la cabecera muestra el logo de AP Buildings` · `Armazon.test.tsx` | feliz | Ajuste de marca | FALLA: ningún `img` en el `banner` | PASA |
| TC-M2 | `tkt008c_marca · el inicio de sesión muestra el logo de AP Buildings` · `PaginaInicioSesion.test.tsx` | feliz | Ajuste de marca | FALLA: ningún `img` | PASA |
| TC-M3 | `tkt008c_marca · el logo vive en src/assets y la paleta usa el verde de la marca` · `esqueleto.test.ts` | feliz | Ajuste de marca | FALLA: `src/assets/ap-logo.jpeg` no existe | PASA |

| TC-R101 | `tkt008_ca09_esc02 · una segunda concurrencia reinicia la espera` · `PantallaBloqueo.test.tsx` | **rechazo** | `CA-9` esc. 2, `RNF-16`; C1, A1 | FALLA: «Reintentar» habilitado tras el `rerender` | PASA |
| TC-R102 | `tkt008_ca08_esc03 · el identificador interno de la orden no se pinta` · `PantallaBloqueo.test.tsx` | **rechazo** | `CA-8` esc. 3, D-8; C7a | Nace en verde; mutante: `orden_compra_id` fuera de las claves ocultas | PASA |
| TC-R103 | `tkt008_ca11_esc05 · una segunda concurrencia reinicia la espera` · `ConflictoEnLinea.test.tsx` | **rechazo** | `CA-11` esc. 5, `RNF-16`; C1, A1 | FALLA: «Reintentar» habilitado tras el `rerender` | PASA |
| TC-R104 | `tkt008_ca11_esc05 · el conflicto se anuncia en una región viva` · `ConflictoEnLinea.test.tsx` | feliz | `CA-11` esc. 5; C4 | FALLA: sin región `aria-live` | PASA |
| TC-R105 | `tkt008_ca12_esc02 · el aviso de motivo obligatorio es la descripción del campo` · `CapturaMotivo.test.tsx` | **rechazo** | `CA-12` esc. 2; C7b | Nace en verde; mutante: sin `aria-describedby` | PASA |
| TC-R106 | `tkt008_ca12_esc03 · el mensaje del servidor es la descripción del campo` · `CapturaMotivo.test.tsx` | **rechazo** | `CA-12` esc. 3; C7b | Nace en verde; mutante: sin `aria-describedby` | PASA |
| TC-R107 | `tkt008_ca12_esc03 · tras el rechazo del servidor el foco va al campo del motivo` · `CapturaMotivo.test.tsx` | **rechazo** | `CA-12` esc. 3; C5 | FALLA: el foco queda en el botón | PASA |
| TC-R108 | `tkt008_ca12_esc02 · un motivo de 2,001 caracteres no se envía` · `CapturaMotivo.test.tsx` | **rechazo** | `CA-12` esc. 2, `RN-04`; C7c | Nace en verde; mutante: `.max(2001)` | PASA |
| TC-R109 | `tkt008_ca12_esc01 · un motivo de 2,000 caracteres sí se envía` · `CapturaMotivo.test.tsx` | feliz | `CA-12` esc. 1; C7c | Nace en verde; mutante: `.max(1999)` | PASA |
| TC-R110 | `tkt008_ca12 · cerrar y reabrir deja el campo vacío` · `CapturaMotivo.test.tsx` | feliz | `CA-12`; C7d | Nace en verde; mutante: `keepMounted` en el portal del diálogo | PASA |
| TC-R111 | `tkt008_ca12_esc04 · una validación sin errores se delega a la pantalla` · `CapturaMotivo.test.tsx` | **rechazo** | `CA-12` esc. 4, `PA-T13`; C7e | Nace en verde; mutante: sin la condición de `errores` vacío | PASA |
| TC-R112 | `tkt008_ca11_esc06 · mientras la baja está en vuelo no admite otra confirmación` · `ConfirmacionBaja.test.tsx` | **rechazo** | `CA-11` esc. 6; C2 | Nace en verde; mutante: `disabled={false}` | PASA |
| TC-R113 | `tkt008_ca11_esc06 · si la baja lanza, entrega un rechazo genérico y al reabrir el botón vuelve a estar habilitado` · `ConfirmacionBaja.test.tsx` | **rechazo** | `CA-11` esc. 6, `PA-T16`; C2 | FALLA: el botón sigue deshabilitado y el rechazo escapa sin manejar | PASA |
| TC-R114 | `tkt008_ca11_esc06 · si alHecho lanza tras una baja exitosa, no se entrega un rechazo` · `ConfirmacionBaja.test.tsx` | **rechazo** | `CA-11` esc. 6; N2 de código | FALLA: `alRechazo` llamado una vez | PASA |
| TC-R115 | `tkt008_ca11_esc07 · si alRechazo lanza tras un rechazo del servidor, se llama una sola vez` · `ConfirmacionBaja.test.tsx` | **rechazo** | `CA-11` esc. 7; N2 de código | FALLA: `alRechazo` llamado dos veces | PASA |
| TC-R116 | `tkt008_ca11_esc04 · una validación del servidor sin errores muestra un aviso en la cabecera` · `FormularioCatalogo.test.tsx` | **rechazo** | `CA-11` esc. 4, `PA-T13`; C3 | FALLA: sin `role="alert"` | PASA |
| TC-R117 | `tkt008_ca11_esc04 · tras el 422 del servidor el foco va al campo señalado` · `FormularioCatalogo.test.tsx` | **rechazo** | `CA-11` esc. 4; C5 | FALLA: el foco queda en «Guardar» | PASA |
| TC-R118 | `tkt008_ca11_esc04 · con varios errores del servidor el foco va al primer campo señalado` · `FormularioCatalogo.test.tsx` | **rechazo** | `CA-11` esc. 4; N1 de código | FALLA: el foco queda en «Nombre» | PASA |
| TC-R119 | `tkt008_ca11_esc05 · el conflicto en línea se anuncia en una región viva que ya existía` · `FormularioCatalogo.test.tsx` | **rechazo** | `CA-11` esc. 5; C4 | FALLA: ninguna región `aria-live` antes de guardar | PASA |
| TC-R120 | `tkt008_ca11 · la X de cierre se llama «Cerrar», no «Close»` · `FormularioCatalogo.test.tsx` | feliz | `CA-11`; C6 | FALLA: la X se llama «Close» | PASA |
| TC-R121 | `tkt008_ca11 · reabrir el formulario muestra los valores iniciales, no lo editado` · `FormularioCatalogo.test.tsx` | feliz | `CA-11`; C7d | Nace en verde; mutante: `keepMounted` en el portal del diálogo | PASA |
| TC-R122 | `tkt008_ca11_esc06 · Escape en la confirmación anidada no cierra el formulario padre` · `FormularioCatalogo.test.tsx` | **rechazo** | `CA-11` esc. 6; C7e | Nace en verde; mutante: cancelar la baja también llama a `alCerrar` | PASA |

TC-R101 a TC-R122 nacen en los ciclos de corrección de la revisión: TC-R114, TC-R115 y TC-R118 en el ciclo 2, el resto en el ciclo 1. Algunos nombres de prueba conservan entre paréntesis el identificador del hallazgo que los originó; los de `ConfirmacionBaja.test.tsx` y los añadidos a `FormularioCatalogo.test.tsx` lo perdieron en el ciclo 3, y la trazabilidad queda en esta tabla.

TC-C1 a TC-C4 cubren ramas del contrato literal del diseño que no tenían TC propio; los añadió el tester en la fase roja de su fila.

### Ciclo TDD por fila

#### Fila 11 · Pantalla de bloqueo

**Rojo** (`tester-frontend`, `npm test -- src/compartido/componentes`):

```text
 ❯ |cliente| src/compartido/componentes/bloqueo/PantallaBloqueo.test.tsx (0 test)
 FAIL  ... PantallaBloqueo.test.tsx
Error: Failed to resolve import "./PantallaBloqueo" from "src/compartido/componentes/bloqueo/PantallaBloqueo.test.tsx". Does the file exist?
  Plugin: vite:import-analysis
 Test Files  1 failed (1)
      Tests  no tests
```

`npm run typecheck`: `TS2307` por `./PantallaBloqueo` y dos `TS2578` por los `@ts-expect-error` de TC-74, que quedan sin usar mientras `PropsPantallaBloqueo` resuelve a `any`. Suite completa: `Test Files 1 failed | 12 passed (13)`, `Tests 154 passed (154)`.

**Verde** (`desarrollador-react`, `sonnet`):

```text
npm test -- src/compartido/componentes   →  Test Files  1 passed (1) · Tests  13 passed (13)
npm test                                  →  Test Files  13 passed (13) · Tests  167 passed (167)
npm run lint → 0 · npm run typecheck → 0
```

**Refactor:** sin cambios después del verde. El orquestador quitó el texto «Disponible en mm:ss» que el desarrollador había añadido sin que nadie lo pidiera, y repitió la fila: `Tests 13 passed (13)`, `tsc` 0, `eslint` 0.

**Tests devueltos al tester:** ninguno.

#### Fila 12 · Captura de motivo

**Rojo** (`tester-frontend`, `npm test -- src/compartido/formularios`):

```text
 ❯ |cliente| src/compartido/formularios/CapturaMotivo.test.tsx (0 test)
Error: Failed to resolve import "./CapturaMotivo" from "src/compartido/formularios/CapturaMotivo.test.tsx". Does the file exist?
 Test Files  1 failed (1)
      Tests  no tests
```

`npm run typecheck`: un solo `TS2307` por `./CapturaMotivo`.

**Verde** (`desarrollador-react`, `haiku`):

```text
npm test -- src/compartido/formularios   →  Test Files  1 passed (1) · Tests  8 passed (8)
npm test                                  →  Test Files  14 passed (14) · Tests  175 passed (175)
npm run lint → 0 · npm run typecheck → 0
```

**Refactor:** el tratamiento de `VALIDACION` pasó de un bucle con bandera a `find` y `filter`; la suite se repitió en verde.

**Tests devueltos al tester:** ninguno.

#### Fila 13 · Formulario de catálogo

**Rojo** (`tester-frontend`, `npm test -- src/compartido/formularios/FormularioCatalogo`):

```text
 FAIL  |cliente| src/compartido/formularios/FormularioCatalogo.test.tsx
Error: Failed to resolve import "./FormularioCatalogo" from "src/compartido/formularios/FormularioCatalogo.test.tsx". Does the file exist?
 Test Files  1 failed (1)
      Tests  no tests
```

`npm run typecheck`: un solo `TS2307`. Suite completa: `Test Files 1 failed | 14 passed (15)`, `Tests 175 passed (175)`.

**Verde** (`desarrollador-react`, `haiku`):

```text
npm test -- src/compartido/formularios   →  Test Files  2 passed (2) · Tests  22 passed (22)
npm test                                  →  Test Files  15 passed (15) · Tests  189 passed (189)
npm run lint → 0 · npm run typecheck → 0
```

**Refactor:** `CabeceraBloqueo.tsx` extraída de `PantallaBloqueo`; la frontera de tipos entre Zod y react-hook-form, concentrada en `catalogo.formulario.ts`.

**Tests devueltos al tester:** ninguno.

#### Ajuste de marca

**Rojo** (`tester-frontend`, `npx vitest run` sobre los tres archivos):

```text
 × tkt008c_marca · el logo vive en src/assets y la paleta usa el verde de la marca
   AssertionError: src/assets/ap-logo.jpeg existe: expected false to be true
 × tkt008c_marca · la cabecera muestra el logo de AP Buildings
   TestingLibraryElementError: Unable to find an accessible element with the role "img" and name "AP Buildings"
 × tkt008c_marca · el inicio de sesión muestra el logo de AP Buildings
   TestingLibraryElementError: Unable to find role="img" and name "AP Buildings"
 Test Files  3 failed (3)
      Tests  3 failed | 65 passed (68)
```

**Verde** (`desarrollador-react`, `sonnet`):

```text
npm test → Test Files  15 passed (15) · Tests  192 passed (192)
npm run lint → 0 · npm run typecheck → 0 · npm run build → 0
```

**Refactor:** sin refactor.

**Tests devueltos al tester:** ninguno.

#### Fila 15 · Mutación y regresión (parte de 008c)

Cada mutante se aplicó solo, se ejecutó `npx vitest run src/compartido` (49 pruebas en la línea base) y se restauró el archivo, comprobando que el SHA-256 coincidía con el original. Ninguno sobrevivió y no hizo falta ninguna prueba nueva.

| Mutante | Archivo | Qué se mutó | Cayó |
|---|---|---|---|
| MT-24 | `DetalleCifras.tsx` | El excedente como `solicitado − disponible` | TC-66 |
| MT-25 | `DetalleCifras.tsx` | Omite las claves desconocidas | TC-69, TC-86, TC-89 |
| MT-26 | `DetalleCifras.tsx` | «NaN» en lugar de «No disponible» | TC-70 |
| MT-27 | `BotonesAcciones.tsx` | «Reintentar» habilitado desde el principio | TC-72 |
| MT-28 | `BotonesAcciones.tsx` | Sin `alReintentar`, «Reintentar» no hace nada | TC-73 |
| MT-29 | `BotonesAcciones.tsx` | Acciones en orden inverso | TC-75, TC-89 |
| MT-30 | `motivo.formulario.ts` | Esquema sin `.trim()` | TC-79, TC-78 |
| MT-31 | `CapturaMotivo.tsx` | «El motivo es obligatorio.» ante un `422` | TC-80 |
| MT-32 | `FormularioCatalogo.tsx` | `reset()` al recibir un `CONFLICTO` | TC-86 |
| MT-33 | `FormularioCatalogo.tsx` | `CONFLICTO` a `alBloqueo` en vez de en línea | TC-86 |
| MT-34 | `ConfirmacionBaja.tsx` | «Cancelar» llama a `alConfirmar` | TC-88 |
| MT-35 | `CapturaMotivo.tsx` | `alRechazo` ante un `VALIDACION` de `motivo` | TC-80 |

MT-33 a MT-35 los añadió el orquestador sobre ramas que la tabla del diseño no cubría. MT-24 muere porque TC-66 usa un excedente incoherente a propósito; con cifras coherentes, un componente que restara daría el mismo número.

**Evidencia de ejecución al cerrar** (`tester-frontend`, `sonnet`, con `docker info` respondiendo 29.8.2):

```text
npm run lint            → código 0
npm run typecheck       → código 0
npm test                → Test Files  15 passed (15) · Tests  192 passed (192)
npm run build           → ✓ built in 253ms (aviso de Vite: un chunk de 558.90 kB, ya existente)
npm run tipos:verificar → Tipos al día.
git diff --stat Produccion -- backend → vacío
npm run e2e (con la base de Compose migrada):
  ok 1 [chromium] › e2e\humo.spec.ts:40:1 › tkt008_ca14_esc01 · entrar y salir (1.4s)
  ok 2 [chromium] › e2e\humo.spec.ts:53:1 › tkt008_ca14_esc02 · credenciales incorrectas (524ms)
  ok 3 [chromium] › e2e\humo.spec.ts:64:3 › teléfono › tkt008_ca07_esc08 · teléfono (552ms)
  3 passed (9.5s)
```

Al cerrar la ejecución, `rg -n "document\.cookie" frontend/src` devolvía una sola línea: un comentario de `src/api/cliente.test.ts:322`, heredado de TKT-008a, que explica que MSW lee la cookie por su cuenta. En el ciclo de corrección 1 de la revisión el tester reformuló ese comentario («la cookie del documento») sin tocar la prueba, y la búsqueda sale vacía.

La parte de backend de TC-R2 no se ejecutó al cerrar la ejecución. Se ejecutó en `/sdd-revisar`, con `docker info` respondiendo 29.8.2:

```text
uv run pytest            → 1138 passed in 237.10s (0:03:57)
uv run ruff check .      → All checks passed!
uv run mypy .            → Success: no issues found in 153 source files
uv run lint-imports      → Contracts: 15 kept, 0 broken.
verificar_float          → archivos revisados: 18; hallazgos: 0
```

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 11 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 11 · verde y refactor | `desarrollador-react` | `sonnet` | `sonnet` | — (disparador de cifras de `RN-03` y `RN-07`) |
| Fila 12 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 12 · verde y refactor | `desarrollador-react` | `haiku` | `haiku` | — |
| Fila 13 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Fila 13 · verde y refactor | `desarrollador-react` | `haiku` | `haiku` | — |
| Ajuste de marca · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Ajuste de marca · verde | `desarrollador-react` | `haiku` | `sonnet` | Decisiones visuales (contraste, jerarquía de la cabecera) sin diseño previo que las fije |
| Fila 15 · mutación y regresión | `tester-frontend` | `sonnet` | `sonnet` | — |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Revisión · auditorías | `auditor-arquitectura`, `auditor-codigo`, `auditor-seguridad` | `sonnet` | `sonnet` | — |
| Revisión · auditoría de documentación | `auditor-docs` | `haiku` | `haiku` | — |
| Revisión · ciclo 1 · rojo y ajuste del test de C2 | `tester-frontend` | `sonnet` | `sonnet` | — |
| Revisión · ciclo 1 · corrección | `corrector-revision` | `haiku` | `sonnet` | C1 era Mayor y toca `RNF-16` (espera del reintento) |
| Revisión · ciclo 1 · reauditoría | `auditor-codigo` / `auditor-arquitectura`, `auditor-docs` | `sonnet` / `haiku` | `sonnet` / `haiku` | Código en `sonnet` por el Mayor C1; los demás, acotados a Menores |
| Revisión · ciclo 2 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| Revisión · ciclo 2 · corrección | `corrector-revision` | `haiku` | `haiku` | — |
| Revisión · ciclo 2 · reauditoría | `auditor-codigo`, `auditor-arquitectura`, `auditor-docs` | `haiku` | `haiku` | Los hallazgos que verificaba eran Menores (el F005 de documentación era una fila de tabla); la de código encontró además el Mayor N3 |
| Revisión · ciclo 3 · pruebas | `tester-frontend` | `sonnet` | `sonnet` | — |
| Revisión · ciclo 3 · corrección (tres despachos) | `corrector-revision` | `haiku` | `haiku` | Solo documentación y comentarios |
| Revisión · ciclo 3 · reauditoría de código | `auditor-codigo` | `haiku` | `sonnet` | Verificaba el Mayor N3 |
| Revisión · ciclo 3 · reauditorías de arquitectura y documentación, y firmas finales | `auditor-arquitectura`, `auditor-docs` | `haiku` | `haiku` | Solo hallazgos Menores |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-8` | `[M]` | Cumplido | TC-65 a TC-70 |
| `CA-9` | `[M]` | Cumplido | TC-71 a TC-74 |
| `CA-10` | `[M]` | Cumplido | TC-75 a TC-77 |
| `CA-11` | `[M]` | Cumplido | TC-82 a TC-89, TC-C4 |
| `CA-12` | `[M]` | Cumplido | TC-78 a TC-81, TC-C1 a TC-C3 |
| `CA-R1` | `[M]` | Cumplido | `lint`, `typecheck`, `test` y `build` en código 0 |
| `CA-R2` | `[M]` | Cumplido | Diff de `backend/` vacío; `pytest` (1138), `ruff`, `mypy`, `lint-imports` y `verificar_float` en verde en `/sdd-revisar` |
| `CA-R3` | `[M]` | Cumplido | TC-18 y TC-37 en verde; la búsqueda de `document.cookie` en `frontend/src` sale vacía tras el ciclo de corrección 1 |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` (cierre de fase, en `/sdd-ejecutar`) | APROBADO | Cuatro observaciones, ninguna crítica, mayor ni menor | 0 |
| `auditor-arquitectura` (revisión) | APROBADO | A1 (Menor); en las reauditorías, N1 a N6 y F001 (Menores); observaciones N7 a N9 y O001 | 3 |
| `auditor-codigo` | APROBADO | C1 (Mayor), C2 a C7 (Menores); en las reauditorías, N1, N2, N4 (Menores) y N3 (Mayor) | 3 |
| `auditor-seguridad` | APROBADO | S1 a S3, observaciones bajas sin cambio | 0 |
| `auditor-docs` | APROBADO | D1, D2 (Mayores), D3 a D6 (Menores); en las reauditorías, F001 a F004, F006, F007 (Menores), F005 (Mayor) y el residuo de N4 (Menor) | 3 |
| `auditor-sql` | No aplica: sin esquema | — | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| O1 | `auditor-arquitectura` | Observación | `spec.md:30` frente a `Armazon.tsx`, `PaginaInicioSesion.tsx` e `index.css` | El non-goal «no toca el armazón» choca con el ajuste de marca, que pidió el usuario y debía quedar registrado | Resuelto: registrado en «Ajustes respecto al design»; el PR lo menciona como ajuste pedido por el usuario, solo de presentación |
| O2 | `auditor-arquitectura` | Observación | `frontend/scripts/esqueleto.test.ts` (`tkt008c_marca`) | La prueba fija el hex exacto de `--primary`; una recoloración futura la rompería sin cambiar comportamiento | Aceptada: fija la decisión de marca que pidió el usuario |
| O3 | `auditor-arquitectura` | Observación | `DetalleCifras.tsx:24-29,53` | Un `consumido_desglose` sin `consumido` se descarta en silencio | Aceptada; anotada en «Hallazgos fuera de alcance». El contrato actual siempre manda ambos |
| O4 | `auditor-arquitectura` | Observación | `ConfirmacionBaja.tsx:24-31` | Si `alConfirmar` lanzara, `enVuelo` quedaría en `true` | Resuelto en la revisión como C2 |
| A1 · C1 | arquitectura · código | Mayor (código) | `PantallaBloqueo.tsx`, `ConflictoEnLinea.tsx` | La espera del reintento no se reiniciaba ante un segundo `CONCURRENCIA` | Resuelto (ciclo 1): `key={error.correlacion_id}`; TC-R101, TC-R103 |
| C2 | código | Menor | `ConfirmacionBaja.tsx` | `enVuelo` atascado si la baja lanza | Resuelto (ciclo 1): `try/catch/finally`, rechazo genérico (`PA-T16`); TC-R112, TC-R113 |
| C3 | código | Menor | `FormularioCatalogo.tsx` | `VALIDACION` sin entradas no pintaba nada | Resuelto (ciclo 1): aviso en la cabecera (`PA-T13`); TC-R116 |
| C4 | código | Menor | `FormularioCatalogo.tsx`, `ConflictoEnLinea.tsx` | Conflicto en línea sin anunciar | Resuelto (ciclo 1): región `aria-live` persistente; TC-R104, TC-R119 |
| C5 | código | Menor | `FormularioCatalogo.tsx`, `CapturaMotivo.tsx` | Sin foco tras el `422` del servidor | Resuelto (ciclo 1); TC-R107, TC-R117 |
| C6 | código | Menor | `components/ui/dialog.tsx` | La X de cierre decía «Close» | Resuelto (ciclo 1): «Cerrar»; TC-R120; TC-89 excluye la X |
| C7 | código | Menor | Pruebas de las filas 11 y 12 | Cinco vacíos de prueba | Resuelto (ciclo 1): TC-R102, TC-R105, TC-R106, TC-R108 a TC-R111, TC-R121, TC-R122 |
| D1 a D6 | documentación | D1, D2 Mayores; D3 a D6 Menores | `impl.md`, specs, `_index.md`, tres archivos con CRLF | Casilla de auditorías, supuestos sin pregunta abierta (`PA-T13` a `PA-T16`), `CA-R2` y `CA-R3`, finales de línea, excepción de non-goals, dependencia | Resueltos (ciclo 1) |
| N1 (código) | código | Menor | `FormularioCatalogo.tsx` | Con varios errores, el foco iba al último campo | Resuelto (ciclo 2); TC-R118 |
| N2 (código) · N1 (arquitectura) | código · arquitectura | Menor | `ConfirmacionBaja.tsx` | El `try` envolvía `alHecho` y `alRechazo` | Resuelto (ciclo 2); TC-R114, TC-R115 |
| N2, N3 (arquitectura) · F002, F004 | arquitectura · documentación | Menor | `spec.md`, `impl.md` | `dialog.tsx` y el comentario de `cliente.test.ts` sin registrar | Resueltos (ciclo 2) |
| F001, F003, F005 | documentación | F005 Mayor; resto Menores | Dos pruebas con CRLF; `impl.md`; `tkt-008/spec.md` | Finales de línea, `PA-T16` sin citar, supuesto sin pregunta abierta (`PA-T17`) | Resueltos (ciclo 2) |
| N3 (código) | código | Mayor | `ConfirmacionBaja.test.tsx` | El ayudante de rechazos sin manejar descartaba lo capturado | Resuelto (ciclo 3): las dos pruebas afirman el error capturado |
| N4 (código) · N9 (arquitectura) | código · arquitectura | Menor · Observación | Pruebas y comentarios de producción | Etiqueta «N1» donde el hallazgo era N2; identificadores de auditoría en el código | Resuelto (ciclo 3) en producción y en `ConfirmacionBaja.test.tsx` y `FormularioCatalogo.test.tsx` |
| N4 (arquitectura) · F007 | arquitectura · documentación | Menor | `impl.md` | Tablas sin la revisión y recuento del ciclo 1 | Resuelto (ciclo 3, orquestador) |
| N4 (residuo) | documentación | Menor | `BotonesAcciones.tsx:9`, `DetalleCifras.tsx:20` | Dos comentarios de producción citaban `(O1)` | Resuelto (cierre del ciclo 3) |
| F001 (arquitectura, ciclo 3) | arquitectura | Menor | `sdd/tickets/tkt-008/spec.md`, fila `PA-T17` | Citaba un contrato genérico que no existe en el diseño | Resuelto (cierre del ciclo 3): cita `E extends z.ZodObject` y describe la alternativa |
| N5, N6, N8 (arquitectura) · F006 | arquitectura · documentación | Menor · Observación | `tkt-008c/spec.md`, `impl.md`, `tkt-008/spec.md` | Excepción incompleta, `VER_OBRA` sí está en el borrador, `PA-T17` sin la conversión `as unknown as`, lista de preguntas abiertas | Resueltos (ciclo 3) |
| S1 a S3 | seguridad | Observación baja | `etiquetas.ts`, `motivo.formulario.ts`, `BotonesAcciones.tsx` | Lista de ocultos por nombre, tope del motivo solo en cliente, `Accion.ruta` para pantallas futuras | Aceptadas: comportamiento diseñado; las pantallas consumidoras deben resolver cada `clave` a una operación tipada |

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/src/compartido/formularios/CapturaMotivo.tsx` | Escape o un clic fuera durante el envío llaman a `alCancelar`; el diseño no dice si el cierre debe bloquearse mientras la petición está en vuelo (`PA-T14`) | Media |
| `frontend/src/compartido/formularios/FormularioCatalogo.tsx` | Si la baja con motivo es rechazada, el diálogo se cierra y el motivo escrito se pierde; el diseño no dice si debe conservarse (`PA-T15`) | Baja |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | Un `consumido_desglose` sin `consumido` no se pinta | Baja |
| `frontend/src/compartido/formularios/CapturaMotivo.tsx` | `alConfirmar` no se protege con `try`, a diferencia de `ConfirmacionBaja`; hoy es inerte porque `pedir` no lanza | Baja |
| `frontend/src/index.css` (`--input`) | El borde de los campos queda por debajo de 3:1 de contraste contra blanco; tampoco lo cumplía el valor anterior | Baja |
| `frontend/src/compartido/componentes/bloqueo/DetalleCifras.tsx` | Las cantidades se presentan con dos decimales aunque la columna guarde cuatro; el redondeo al presentar es `PA-T5`, de TKT-008a | Baja |
| `frontend/src/compartido/componentes/bloqueo/PantallaBloqueo.tsx` | `PantallaBloqueo` fija `id="titulo-bloqueo"` en su título; dos instancias en una pantalla duplicarían el `id`. Literal del diseño (`tkt-008/design.md:700`) | Baja |
| `Armazon.tsx:52`, `PaginaInicioSesion.tsx:126,158`, `cliente.test.ts` (377-495), `sesion.test.ts:12`, `ProveedorApi.test.tsx:6`, `dinero.test.ts:49,54` | Comentarios con identificadores de auditoría de tickets anteriores (`C106`, `C104`, `S102`, `C003`, `F004`, `F005`, `F006`). Fuera del alcance de la revisión | Baja |
| Pruebas de la fila 13 | El `detalle` de `CODIGO_OBRA_DUPLICADO` de TC-86 usa `codigo` y `nombre`, mientras el ejemplo del borrador OpenAPI usa `obra_existente_id` y `obra_existente`. `VER_OBRA` sí está en el borrador (ejemplo `409` de `CODIGO_OBRA_DUPLICADO` en `docs/api/openapi.yaml`); solo `VER_ORDENES_ABIERTAS` es ajena al borrador y se rotula con la clave cruda (D-7) | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `sdd/tickets/tkt-008/design.md` | Estado de las filas 11, 12, 13 y 15 |
| `sdd/tickets/tkt-008/spec.md` | `PA-T13` a `PA-T17` |
| `sdd/tickets/tkt-008c/spec.md` | Excepción de non-goals y MT-33 a MT-35 |

Ningún documento de `docs/` describe todavía estos componentes ni la identidad visual. `python tools/verificar_docs.py` → `✓ Sin problemas.`

## Revisión

### Suite al abrir la revisión

Ejecutada por el orquestador, sin fiarse de lo anotado arriba, con `docker info` respondiendo 29.8.2:

```text
frontend · npm run lint       → código 0
frontend · npm run typecheck  → código 0
frontend · npm test           → Test Files  15 passed (15) · Tests  192 passed (192)
frontend · npm run build      → ✓ built in 232ms
backend  · uv run pytest      → 1138 passed in 237.10s (0:03:57)
backend  · ruff · mypy · lint-imports · verificar_float → limpios (15 contratos, 0 hallazgos de float)
raíz     · verificar_docs.py  → ✓ Sin problemas. · extraer_mermaid.py → 30 diagramas, código 0
```

### Primera pasada de auditorías

| Auditor | Veredicto | Hallazgos que exigían cambio |
|---|---|---|
| `auditor-arquitectura` | REQUIERE CAMBIOS | A1 (Menor): la espera del reintento no se reiniciaba ante un segundo `CONCURRENCIA` |
| `auditor-codigo` | REQUIERE CAMBIOS | C1 (Mayor, el mismo defecto que A1); C2 a C7 (Menores): `enVuelo` atascado si la baja lanza, `VALIDACION` sin entradas silenciosa, conflicto en línea sin región viva, foco tras un `422` del servidor, la X «Close» en inglés y cinco vacíos de prueba |
| `auditor-seguridad` | APROBADO | Tres observaciones bajas (S1 a S3), sin cambio |
| `auditor-docs` | REQUIERE CAMBIOS | D1 y D2 (Mayores): casilla de auditorías que afirmaba de más y supuestos sin `(asumido)` ni pregunta abierta; D3 a D6 (Menores): `CA-R2` y `CA-R3`, finales de línea CRLF, excepción de non-goals sin registrar en la spec y dependencia desactualizada |

### Ciclo de corrección 1

**Rojo.** El tester escribió primero las pruebas de C1 a C7 y la corrección del comentario de `cliente.test.ts` (`CA-R3`). El ciclo añadió 19 pruebas (la suite pasó de 192 a 211) y amplió las aserciones de TC-68, TC-79 y TC-80: nueve pruebas cayeron por la razón esperada, y las que nacieron en verde se demostraron una a una con su mutante temporal, revertido por SHA-256. Corrigió también una aserción de TC-89, que excluye ahora el botón de cierre del diálogo (`data-slot="dialog-close"`) porque pasa a llamarse «Cerrar».

**Corrección.** `key={error.correlacion_id}` en `BotonesAcciones` desde `PantallaBloqueo` y `ConflictoEnLinea` (C1, A1); `ConfirmacionBaja` con `try/catch/finally`, que entrega un rechazo genérico si la baja lanza (C2, `PA-T16`); aviso en la cabecera para un `VALIDACION` sin entradas (C3, `PA-T13`); región `aria-live="polite"` persistente en el formulario y prop `regionViva` en `ConflictoEnLinea` (C4); foco en el campo del error del servidor (C5); «Close» pasa a «Cerrar» en `dialog.tsx` (C6); `PA-T13` a `PA-T16`, excepción de non-goals, dependencia y finales de línea (D2, D4 a D6). D1 y D3 los corrigió el orquestador con la suite de backend ya ejecutada.

**Test devuelto al tester.** La prueba de C2 cerraba el diálogo dentro de `alRechazo` y después buscaba «Cancelar». Chocaba con la decisión de entregar el rechazo genérico; el tester la reescribió para afirmar ese comportamiento, y un mutante que quita `setEnVuelo(false)` la hace caer.

**Reauditoría.** C1 a C7, A1 y D1 a D6, resueltos. Aparecieron hallazgos nuevos introducidos por la corrección: el foco iba al último campo con varios errores y el `try` de `ConfirmacionBaja` envolvía también `alHecho` y `alRechazo` (código N1 y N2, arquitectura N1); `dialog.tsx` y el comentario de `cliente.test.ts` sin registrar en la spec, e `impl.md` sin el ciclo (arquitectura N2 a N4; documentación F002 y F004); dos pruebas con CRLF (F001); `PA-T16` sin citar (F003) y un supuesto sin pregunta abierta (F005, Mayor).

### Ciclo de corrección 2

**Rojo.** Tres pruebas nuevas cayeron por la razón esperada: con dos errores del servidor el foco quedaba en «Nombre»; si `alHecho` lanzaba tras una baja exitosa se entregaba un rechazo; si `alRechazo` lanzaba se llamaba dos veces. El tester convirtió a LF las dos pruebas con CRLF (F001).

**Corrección.** El foco va solo al primer campo señalado; el `try` de `ConfirmacionBaja` envuelve solo `await alConfirmar()`. `PA-T17`, la cita de `PA-T16`, la excepción ampliada de non-goals y las filas que faltaban en «Archivos tocados» y «Documentación actualizada».

```text
npx vitest run src/compartido → Test Files  6 passed (6) · Tests  71 passed (71)
npm test                      → Test Files  17 passed (17) · Tests  214 passed (214)
npm run lint · npm run typecheck → código 0
python tools/verificar_docs.py → ✓ Sin problemas.
```

**Reauditoría.** N1 y N2 de código, N1 a N3 de arquitectura y F001 a F005, resueltos. Nuevos: el ayudante que captura rechazos sin manejar descartaba lo capturado (código N3, Mayor) y una etiqueta «N1» donde el hallazgo era N2 (código N4); tablas de `impl.md` sin la revisión, excepción de non-goals incompleta y `VER_OBRA` mal atribuida (arquitectura N4 a N6); lista de preguntas abiertas de la spec sin `PA-T13` a `PA-T17` y recuento del ciclo 1 (F006, F007).

### Ciclo de corrección 3

**Pruebas.** El tester hizo que las dos pruebas que usan el ayudante afirmen el error capturado (`toHaveLength(1)` y `toBe(fallo)`) y quitó de los nombres de prueba de `ConfirmacionBaja.test.tsx` y `FormularioCatalogo.test.tsx` los identificadores de auditoría. Un mutante que llama a `alHecho` dentro del `try` hace caer TC-R114; se revirtió con el mismo SHA-256.

**Corrección.** Los comentarios de producción describen el comportamiento en lugar de citar hallazgos; la spec de TKT-008c lista `PA-T13` a `PA-T17` y nombra en la excepción las pruebas y el activo del ajuste de marca; `PA-T17` declara la conversión `as unknown as`; la fila de acciones de «Hallazgos fuera de alcance» dice que solo `VER_ORDENES_ABIERTAS` es ajena al borrador. El orquestador completó las tablas de pruebas, auditorías y hallazgos de este documento.

**Suite al cerrar la revisión**, ejecutada por el orquestador:

```text
frontend · npm run lint            → código 0
frontend · npm run typecheck       → código 0
frontend · npm test                → Test Files  17 passed (17) · Tests  214 passed (214)
frontend · npm run build           → ✓ built in 224ms
frontend · npm run tipos:verificar → Tipos al día.
raíz     · verificar_docs.py       → ✓ Sin problemas.
git ls-files --eol (modificados y nuevos) → ninguno w/crlf
git diff --stat Produccion -- backend     → vacío
```

**Reauditoría y cierre.** Código APROBADO. Documentación encontró dos comentarios de producción que aún citaban `(O1)`, y arquitectura, que la fila `PA-T17` citaba un contrato genérico inexistente; los dos son Menores y se corrigieron con el texto literal de cada auditor. Las reauditorías mínimas de ambos dieron APROBADO. Tras esos dos cambios, que solo tocan comentarios y una fila de la spec común:

```text
frontend · npm test       → Test Files  17 passed (17) · Tests  214 passed (214)
frontend · lint · typecheck → código 0
raíz · verificar_docs.py  → ✓ Sin problemas. · tools/tests → OK
```

### Veredicto

**LISTO PARA PR.** Los siete criterios `[M]` (`CA-8` a `CA-12`, `CA-R1` a `CA-R3`) cumplidos con test; al menos un test de rechazo por regla implicada; mutación MT-24 a MT-35 sin supervivientes en la ejecución, y cada prueba de la revisión que nació en verde demostrada con su mutante; cuatro auditores en APROBADO tras tres ciclos de corrección, sin hallazgos críticos, mayores ni menores abiertos.

Desviaciones que conviene ver antes de aprobar el PR:

- El ajuste de marca (logo y paleta de AP Buildings), que pidió el usuario al lanzar la ejecución, toca archivos de TKT-008a y TKT-008b solo en presentación; está registrado como excepción de non-goals en la spec.
- `components/ui/dialog.tsx` cambia «Close» por «Cerrar» y se reformula un comentario de `cliente.test.ts`; ambos están registrados en la misma excepción.
- Quedan abiertas `PA-T13` a `PA-T17` en la spec común: deciden producto o la persona que aprueba, no este ticket.
- Algunos nombres de prueba de `PantallaBloqueo.test.tsx`, `ConflictoEnLinea.test.tsx` y `CapturaMotivo.test.tsx` conservan entre paréntesis el identificador del hallazgo que los originó; la trazabilidad está en la tabla de pruebas.
- El PR no toca `docs/api/openapi.yaml`.

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas
- [x] Auditorías `APROBADO`: arquitectura, código, seguridad y documentación, tras tres ciclos de corrección (ver «Revisión»)
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios, y `pytest` con 1138 pruebas en verde, aunque el diff no toca `backend/`
- [x] Rama correcta y sin secretos en el diff
