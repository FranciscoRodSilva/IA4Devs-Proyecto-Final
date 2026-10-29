# CIMENTA · Wireframes

> **Capa SDD:** *Plan*, vertiente de experiencia de usuario. Son **bocetos de baja fidelidad**: fijan **qué contenido** muestra cada pantalla, **en qué jerarquía** y **qué pasa cuando algo se rechaza**. No fijan estilo visual —color, tipografía, espaciado, iconos—: eso lo da el sistema de diseño, que es [shadcn/ui sobre Tailwind](06-stack-tecnologico.md#5-frontend).
>
> **Alcance:** las pantallas del **hilo vertical** de la fase 1 —importar la línea base, levantar una requisición, que se bloquee o se autorice, emitir la orden, recibir el material y ver el semáforo— y una lista corta de las que llegan en la fase 2.
>
> **Trazabilidad:** cada pantalla cita los escenarios de [historias de usuario](04-historias-usuario.md) que cubre. **Si un boceto contradice a un escenario, manda el escenario** y el boceto se corrige. Ninguna pantalla se dibuja solo con el camino feliz (regla 14 de `CLAUDE.md`): cada una lleva debajo sus estados de rechazo.

**Vocabulario:** el del [glosario](glosario.md). *Tipo de partida*, *disponible*, *consumido*, *comprometido*, *ejercido* y *remisión* significan aquí exactamente lo que significan allí.

---

## Índice

0. [Convenciones de los bocetos](#0-convenciones-de-los-bocetos)
1. [Inicio de sesión](#1-inicio-de-sesión)
2. [Armazón de navegación por rol](#2-armazón-de-navegación-por-rol)
3. [Importación de la línea base](#3-importación-de-la-línea-base)
4. [Congelado y presupuesto de control](#4-congelado-y-presupuesto-de-control)
5. [Disponible y captura de requisición](#5-disponible-y-captura-de-requisición)
6. [Pantalla de bloqueo](#6-pantalla-de-bloqueo)
7. [Bandeja de autorizaciones y resolución](#7-bandeja-de-autorizaciones-y-resolución)
8. [Emisión de orden de compra](#8-emisión-de-orden-de-compra)
9. [Recepción de material en teléfono](#9-recepción-de-material-en-teléfono)
10. [Semáforo de obra y desglose](#10-semáforo-de-obra-y-desglose)
11. [Fase 2 · pantallas pendientes](#11-fase-2--pantallas-pendientes)
12. [Cómo se usan](#12-cómo-se-usan)
13. [Supuestos de este documento](#13-supuestos-de-este-documento)

---

## 0. Convenciones de los bocetos

| Notación | Significa |
|---|---|
| `[ Guardar ]` | Botón. Si va seguido de `(deshabilitado)`, se ve pero no responde |
| `[__________]` | Campo de captura |
| `[ MUROS  v ]` | Selector |
| `( ) / (•)` | Opción única |
| `[x] / [ ]` | Casilla |
| `*` | **Dato simulado** en la fase 1 ([ADR-017](adr/20261015-fuentes-simuladas-analitica.md)). La pantalla real lo rotula con texto, no con un asterisco |
| `~` | Cifra **ilustrativa**: calculada con al menos una fuente simulada |
| `▲ alerta` | Marca de umbral superado |

**Importes.** En la API viajan **como cadena decimal** con cuatro decimales (`"45000.0000"`), en el cliente se convierten con `decimal.js` y se redondean **solo al presentar** ([arquitectura §7.4](02-arquitectura.md#74-dinero-y-cantidades), [stack §5.3](06-stack-tecnologico.md#53-el-dinero-también-es-exacto-en-el-cliente)). Los bocetos muestran la forma presentada —`$45,000.00`— y las notas de cada pantalla dicen qué campos llegan como cadena. Ningún cálculo de la interfaz usa `Number`. Las cantidades siguen la misma regla.

**Rutas.** Las del [borrador OpenAPI](api/openapi.yaml), relativas a su base `/api/v1`: recursos en plural, en español y en `kebab-case`, y las transiciones de estado como sub-recursos `POST` (`/requisiciones/{id}/envio`), no como un `PATCH` del estado. Los roles que cada pantalla atribuye a quien consulta salen de su `x-roles`. Si el borrador cambia, manda el borrador y este documento se corrige; TKT-061 es quien compara lo diseñado con lo publicado.

**Códigos.** `409` violación de regla o conflicto de estado, con el [contrato de error](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio) y la [pantalla de bloqueo](#6-pantalla-de-bloqueo); `422` error de forma, que se pinta **en línea, junto al campo** a partir de `errores[].campo`; `403` falta de permiso, que nunca trae cifras; `401` sin sesión, que devuelve a la [pantalla de inicio](#1-inicio-de-sesión); `429` demasiados intentos de acceso.

**Datos de ejemplo.** Las pantallas 4 a 10 usan la escala reducida del ejemplo del contrato de error —`MUROS` con tope de $45,000.00, consumido $33,000.00, disponible $12,000.00— para que las cifras de la requisición, del bloqueo, de la bandeja y del semáforo **cuadren entre sí**; el semáforo muestra la obra **antes** de enviar `REQ-1042`. La pantalla 3 usa los conteos del archivo real de Union Square. No son el mismo conjunto de datos y no pretenden serlo: son bocetos.

---

## 1. Inicio de sesión

| | |
|---|---|
| **Rol** | Todos |
| **Historias** | Sin historia propia: es fundación. TKT-006, TKT-008 y TKT-057 · `RNF-01`, `RNF-02`, `RNF-04`, `RNF-05` |
| **Endpoints** | `GET /sesion/csrf` (token de doble envío) · `POST /sesion` (iniciar) · `GET /sesion` (sesión actual: usuario y roles) · `POST /sesion/cierre` (cerrar) |

```text
┌────────────────────────────────────────────────────────────┐
│                          CIMENTA                           │
│                 Control de costos de obra                  │
│                                                            │
│   Correo                                                   │
│   [ usuario@constructora.mx______________________ ]        │
│                                                            │
│   Contraseña                                               │
│   [ ••••••••••••_________________________________ ]        │
│                                                            │
│   [ Iniciar sesión ]                                       │
│                                                            │
│   ┌──────────────────────────────────────────────────┐     │
│   │ ! Correo o contraseña incorrectos.               │     │  ← 401
│   └──────────────────────────────────────────────────┘     │
│                                                            │
└────────────────────────────────────────────────────────────┘

  Estado · demasiados intentos
  ┌──────────────────────────────────────────────────┐
  │ ! Demasiados intentos fallidos. Vuelve a         │
  │   intentarlo en 15 minutos.                      │  ← bloqueo temporal (RNF-04)
  │   [ Iniciar sesión ] (deshabilitado · 14:52)     │
  └──────────────────────────────────────────────────┘

  Estado · sin conexión
  ┌──────────────────────────────────────────────────┐
  │ Sin conexión. Para iniciar sesión hace falta     │
  │ conexión con el servidor.                        │  ← detectado en el cliente
  │   [ Iniciar sesión ] (deshabilitado)             │
  └──────────────────────────────────────────────────┘
```

**Datos.** Ninguno numérico. La respuesta de `GET /sesion` trae nombre y roles; la cookie de sesión **no es legible desde JavaScript** (`RNF-02`), así que la interfaz nunca la lee: pregunta al servidor quién es.

**Acciones.**

- *Iniciar sesión* envía correo y contraseña. Al aceptar, carga la sesión actual y entra al [armazón](#2-armazón-de-navegación-por-rol) en la primera sección que permitan sus roles.
- El botón se deshabilita mientras la petición está en vuelo: Argon2 tarda a propósito (`RNF-03`) y un doble clic sería un doble intento.

**Estados de rechazo.**

- **Credenciales incorrectas (`401`, `CREDENCIALES_INVALIDAS`).** Un único mensaje para *"el correo no existe"* y *"la contraseña no coincide"*. Distinguirlos revelaría qué cuentas existen, que es lo que TKT-006 evita verificando un hash siempre. La contraseña se vacía; el correo se conserva.
- **Demasiados intentos (`429`).** Tras `N` fallos (TKT-057) el servidor rechaza aunque la contraseña sea correcta. La respuesta es la misma por cuenta que por origen, para no revelar qué cuentas existen, y trae `reintentar_en_s`: el mensaje dice **cuánto falta**, no *"cuenta bloqueada"* a secas, porque el bloqueo caduca solo. El botón se rehabilita al vencer la cuenta atrás.
- **Sin conexión.** No se inicia sesión sin servidor (regla 10 de `CLAUDE.md`, [ADR-015](adr/20260919-captura-diferida-sin-conexion.md)). El botón queda deshabilitado con la explicación; no hay modo "entrar y sincronizar después".
- **Sesión caducada o revocada (`401`, `SESION_CADUCADA` o `SESION_REVOCADA`).** Cualquier `401` en otra pantalla devuelve aquí con el aviso *"Tu sesión terminó. Vuelve a iniciarla."* Si a alguien le retiran un rol, la petición siguiente ya no lo tiene (`RNF-01`): no hay credencial que sobreviva.
- **Prueba de origen ausente o caducada (`403`, `ORIGEN_NO_VERIFICADO`).** Si el token de doble envío no coincide (`RNF-05`), la pantalla pide recargar. No se reintenta en silencio.

---

## 2. Armazón de navegación por rol

| | |
|---|---|
| **Rol** | Todos; el menú depende de sus roles |
| **Historias** | HDU-003 esc. 1 (contador de pendientes) · HDU-006 esc. 12 (sin permiso) |
| **Endpoints** | `GET /sesion` · `GET /obras` (selector) · `GET /solicitudes-autorizacion/contador` · `POST /sesion/cierre` |

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ CIMENTA    Obra [ AP-058-25 · Union Square F2           v ]         M. Torres · DG  [ Salir ] │
├────────────────────────────┬──────────────────────────────────────────────────────────────────┤
│ OBRA                       │                                                                  │
│   Semáforo                 │                                                                  │
│   Línea base               │                                                                  │
│   Presupuesto de control   │                (contenido de la sección elegida)                 │
│                            │                                                                  │
│ COMPRAS                    │                                                                  │
│   Requisiciones            │                                                                  │
│   Órdenes de compra        │                                                                  │
│   Proveedores              │                                                                  │
│                            │                                                                  │
│ ALMACÉN                    │                                                                  │
│   Recepción de material    │                                                                  │
│   Pendientes de recibir    │                                                                  │
│                            │                                                                  │
│ DIRECCIÓN                  │                                                                  │
│   Autorizaciones      ( 3 )│                                                                  │
│   Bitácora de excepciones  │                                                                  │
└────────────────────────────┴──────────────────────────────────────────────────────────────────┘

  En teléfono el menú lateral se pliega bajo un botón [ ≡ ] y el selector de obra pasa a la
  primera línea de cada pantalla.
```

**Qué ve cada rol.** Los escenarios dicen quién **opera** cada pantalla; quién puede además **consultarla** lo fija el `x-roles` de cada ruta del [borrador OpenAPI](api/openapi.yaml), y de ahí sale esta tabla. Un usuario con varios roles ve la **unión** ([arquitectura §7.1](02-arquitectura.md#71-autorización)).

| Sección | Opera | Consulta |
|---|---|---|
| Semáforo | — | Dirección General, Director de Proyectos |
| Línea base (importar, congelar) | Director de Proyectos | Dirección General; Compras ve la línea base congelada, no la importación |
| Presupuesto de control | Dirección General | Director de Proyectos, Compras |
| Requisiciones | Compras | Dirección General, Director de Proyectos |
| Órdenes de compra | Compras | Almacén, Residente de obra, Dirección General, Director de Proyectos |
| Proveedores | Compras | Todos |
| Recepción · Pendientes de recibir | Almacén, Residente de obra (corregir una entrada y reprogramar, solo Almacén) | Compras, Dirección General, Director de Proyectos |
| Autorizaciones | Dirección General | — |
| Bitácora de excepciones | — | Dirección General, Director de Proyectos |

**Acciones.**

- *Selector de obra*: fija la obra de contexto para todas las secciones; todo gasto lleva `obra_id` (regla 6 de `CLAUDE.md`). Lista solo obras `ACTIVA` y `PLANEACION`; las `SUSPENDIDA` y `CERRADA` aparecen bajo un filtro.
- *Contador de autorizaciones*: número de solicitudes `PENDIENTE`. Se refresca al volver a la pestaña y tras cada resolución (invalidación de TanStack Query). **Desaparece cuando es cero**, no muestra `( 0 )` (HDU-003 esc. 1).
- *Salir*: `POST /sesion/cierre` —la sesión se revoca, la fila no se borra— y vuelve al inicio.

**Estados de rechazo.**

- **Sección sin permiso (`403`).** Si alguien llega por URL a una sección que su rol no tiene, ve *"No tienes permiso para esta sección"* **sin ningún importe** (HDU-006 esc. 12). Ocultar la entrada del menú es cortesía; el control es el `403` del servidor ([arquitectura §7.6](02-arquitectura.md#76-seguridad-de-la-frontera)).
- **Rol retirado durante la sesión.** La petición siguiente responde `403`; el armazón vuelve a pedir `GET /sesion` y redibuja el menú sin esa sección.
- **Sin obras.** Si el usuario no tiene ninguna obra activa, el contenido muestra *"No hay obras activas"* y, solo para quien puede crearlas, la acción *Dar de alta una obra*.
- **Contador que no carga.** Si la consulta del contador falla, se omite el número; nunca se muestra un cero que nadie calculó.

---

## 3. Importación de la línea base

| | |
|---|---|
| **Rol** | Director de Proyectos |
| **Historias** | HDU-001 esc. 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 21, 24, 25, 26 y 27 |
| **Endpoints** | `POST /obras/{obra_id}/importaciones` (importación `RECIBIDO` + su `archivo` `PENDIENTE` + URL prefirmada de subida) · `PUT` a la URL prefirmada (almacén de objetos, **no** el API) · `POST /archivos/{archivo_id}/confirmacion` (tamaño, hash y tipo por bytes) · `POST /importaciones/{importacion_id}/analisis` · `GET /importaciones/{importacion_id}` · `GET /importaciones/{importacion_id}/errores` · `POST /importaciones/{importacion_id}/confirmacion` · `POST /importaciones/{importacion_id}/descarte` |

La pantalla tiene tres momentos sobre la misma importación: **carga**, **previsualización** y **errores**. La obra ya existe: su alta usa el formulario de catálogo de TKT-008 (HDU-001 esc. 1 a 3) y no se dibuja aquí.

### 3a · Carga con progreso

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Línea base · AP-058-25 · Union Square F2                                 Obra en PLANEACION  │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Importar catálogo de conceptos con análisis de precios unitarios                             │
│                                                                                              │
│ Archivo   AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx · 7.9 MB        [ Cambiar archivo ]  │
│                                                                                              │
│ 1. Subida al almacén        ████████████████████████████████  100 %   archivo DISPONIBLE     │
│ 2. Verificación             ✓ tamaño y hash coinciden · tipo leído de los bytes: XLSX        │
│ 3. Análisis                 ███████████████░░░░░░░░░░░░░░░░░   48 % · ANALIZANDO             │
│                                                                                              │
│ Puedes seguir trabajando; el análisis continúa aunque cierres esta pantalla.                 │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3b · Previsualización (`VALIDADO`)

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Previsualización · importación VALIDADO · nada se ha escrito todavía en la obra              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Jerarquía leída                          │ Importe total de venta         $9,184,320.55      │
│   Niveles       14                       │ Explosión de insumos           27 insumos         │
│   Áreas        151                       │                                $2,755,187.21      │
│   Partidas     572                       │                                                   │
│   Conceptos  4,212                       │                                                   │
├──────────────────────────────────────────┴───────────────────────────────────────────────────┤
│ Por tipo de partida          Conceptos        Importe de venta                               │
│   MUROS                          2,031           $5,412,880.10                               │
│   PLAFONES Y CAJILLOS            1,388           $2,604,117.35                               │
│   ENCHAPES                         522             $861,940.00                               │
│   GENERALES                        271             $305,383.10                               │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Insumos creados durante la importación (revísalos)                              2 insumos    │
│   Cinta de malla 5 cm            ROLLO    leído de la hoja APU 620417                        │
│   Esquinero metálico 3 m         PZA      leído de la hoja APU 620388                        │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Descartar importación ]                                     [ Confirmar importación ]      │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

  Si la obra ya tiene una línea base en BORRADOR, Confirmar abre antes:
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ Esta importación reemplazará la línea base en BORRADOR del 08-oct-2026.   │
  │ La anterior se descarta y el descarte queda en la bitácora.               │
  │                                 [ Cancelar ]   [ Reemplazar y confirmar ] │
  └───────────────────────────────────────────────────────────────────────────┘
```

### 3c · Errores (`CON_ERRORES`)

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Importación CON_ERRORES · 4,215 errores · no se puede confirmar                               │
│ Las filas válidas se conservan: al corregir el archivo no se repite el análisis completo.     │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ Tipo [ Todos           v ]   Hoja [ Todas      v ]                       [ Exportar errores ] │
├────────────┬───────┬─────────┬──────────────────────┬─────────────────────────────────────────┤
│ Hoja       │ Fila  │ Columna │ Tipo                 │ Detalle                                 │
├────────────┼───────┼─────────┼──────────────────────┼─────────────────────────────────────────┤
│ CATALOGO   │   214 │ H       │ REF_ROTA             │ Precio unitario = #REF!                 │
│ CATALOGO   │   214 │ I       │ REF_ROTA             │ Importe = #REF!                         │
│ CATALOGO   │   215 │ H       │ REF_ROTA             │ Precio unitario = #REF!                 │
│ CATALOGO   │ 1,877 │ A       │ SIN_APU              │ 620417 no tiene hoja de análisis: sin   │
│            │       │         │                      │ ella no hay explosión de ese concepto   │
│ CATALOGO   │ 2,090 │ E       │ UNIDAD_DESCONOCIDA   │ Valor encontrado: "M2."                 │
│ CATALOGO   │    88 │ A       │ DUPLICADO            │ 620001 también en la fila 1,204 con     │
│            │       │         │                      │ otra descripción                        │
├────────────┴───────┴─────────┴──────────────────────┴─────────────────────────────────────────┤
│ Página 1 de 85                                              [ ‹ Anterior ]  [ Siguiente › ]   │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Subir archivo corregido ]                    [ Confirmar importación ] (deshabilitado)      │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Datos como cadena decimal.** Importe total de venta, importe por tipo de partida e importe de la explosión. Los conteos son enteros.

**Acciones.**

- *Seleccionar archivo* registra la importación en `RECIBIDO` con su `archivo` en `PENDIENTE` y sube los bytes **directamente** a la URL prefirmada que devuelve; el progreso de la fase 1 es el de esa subida. Después confirma tamaño y hash y, con el archivo ya `DISPONIBLE`, pide el análisis: la importación **no arranca antes** (HDU-001 esc. 24). El Excel no pasa por el API (regla 15 de `CLAUDE.md`, [ADR-016](adr/20261001-almacenamiento-de-objetos.md)).
- El progreso del análisis se lee consultando `GET /importaciones/{id}`, que lo devuelve como **porcentaje** (`progreso`): la API no informa de hojas leídas ni por leer, y el boceto no las pinta. **No bloquea la pantalla** (esc. 4). **(asumido)** Consulta periódica cada pocos segundos; el intervalo lo fija TKT-018.
- *Confirmar importación* crea la jerarquía, los análisis y la línea base en `BORRADOR` en una sola transacción (esc. 11). Si ya hay un borrador, el servidor responde `409` `REEMPLAZO_NO_CONFIRMADO` con la acción `CONFIRMAR_REEMPLAZO`, que es la que abre el diálogo de reemplazo; solo al aceptarlo se reenvía con `reemplazar_borrador` (esc. 13).
- *Descartar* (`/descarte`) abandona la importación sin escribir nada en la obra.
- *Exportar errores* descarga la tabla de errores tal como está filtrada (TKT-018).
- *Subir archivo corregido* vuelve a 3a sobre la misma obra: el borrador OpenAPI trata un archivo corregido como una **importación nueva**, no como un reintento de esta.

**Estado vacío.** Obra sin ninguna importación: solo el selector de archivo, con el texto de qué se espera —un `.xlsx` con hoja de catálogo y hojas de análisis de precio unitario—.

**Estados de rechazo.**

- **`CON_ERRORES`** (esc. 6 a 9). Tabla 3c, navegable por hoja y fila. *Confirmar* **deshabilitado**, y aunque alguien enviara la petición, el servidor la rechaza: el botón deshabilitado es cortesía, no control.
- **Insumo creado durante la importación** (esc. 10). No es un error: aparece en la previsualización marcado para revisión. No bloquea la confirmación.
- **Formato declarado no admitido (`422`)** (esc. 21). Una extensión o un tipo declarado que no es `.xlsx` —también `.xls`— se rechaza **antes** de crear la importación y sin emitir URL de subida, junto al selector de archivo: *"Solo se admite .xlsx"*.
- **Hoja sin filas de concepto (`CON_ERRORES`, `SIN_CONCEPTOS`)** (esc. 27). No es un `422`: el formato era válido y solo se sabe al leerla. La importación termina en 3c con un único error `SIN_CONCEPTOS` y el mensaje de la estructura mínima esperada; *Confirmar* sigue deshabilitado.
- **Ejecutable renombrado `.xlsx` (`409`, `ARCHIVO_TIPO_NO_PERMITIDO`)** (esc. 26). El tipo se lee de los bytes al confirmar el archivo; se rechaza con *"El archivo no es una hoja de Excel aunque su extensión lo diga"*. El archivo no pasa a `DISPONIBLE` y la importación, ya registrada en `RECIBIDO`, no arranca.
- **Hash o tamaño que no coinciden (`409`, `ARCHIVO_HASH_DISTINTO` o `ARCHIVO_TAMANO_DISTINTO`)** (esc. 25). La subida se dio por buena en el navegador pero el objeto no es el declarado: el archivo no pasa a `DISPONIBLE`, la fase 2 de 3a muestra **✗**, la importación no arranca y la acción es *Volver a subir*. Si alguien pide el análisis igualmente, el servidor responde `409`.
- **Fallo a mitad de la confirmación** (esc. 12). La importación vuelve a `VALIDADO`, la pantalla regresa a 3b con *"La confirmación no se completó; la obra no cambió. Puedes reintentar."* y el identificador de correlación para citarlo.
- **Análisis interrumpido** (`RNF-17`). Si el servidor se reinició, la importación aparece en `CON_ERRORES` con un único error `PROCESO_INTERRUMPIDO` y la acción *Reintentar análisis*, que vuelve a pedir `/analisis` sobre la misma importación.
- **Sin permiso (`403`).** Dirección General ve la importación y sus errores en lectura, sin *Confirmar* ni *Descartar*; cualquier otro rol recibe `403` sin datos.

---

## 4. Congelado y presupuesto de control

| | |
|---|---|
| **Rol** | Director de Proyectos (congela) · Dirección General (captura y recaptura el tope) |
| **Historias** | HDU-001 esc. 14, 15, 17, 18, 19, 22 y 23 |
| **Endpoints** | `GET /obras/{obra_id}/lineas-base` · `GET /lineas-base/{linea_base_id}` · `GET /lineas-base/{linea_base_id}/conceptos` · `GET /lineas-base/{linea_base_id}/explosion` · `POST /lineas-base/{linea_base_id}/congelacion` · `GET /lineas-base/{linea_base_id}/presupuesto-control` · `PUT /lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}` (captura y recaptura) |

### 4a · Congelar la línea base

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Línea base · AP-058-25 · Union Square F2                          Estado: BORRADOR           │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Importada el 14-oct-2026 por J. Ramírez · 4,212 conceptos · 27 insumos en la explosión       │
│                                                                                              │
│ Al congelar, los conceptos y la explosión por tipo de partida se copian a la línea base y    │
│ dejan de poder modificarse por ninguna vía. La obra pasa a ACTIVA.                           │
│                                                                                              │
│ Motivo (obligatorio)                                                                         │
│ [ Contrato firmado el 13-oct-2026, precio alzado máximo garantizado_______________ ]         │
│                                                                                              │
│                                                                   [ Congelar línea base ]    │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

  Una vez CONGELADA, la misma pantalla se ve en modo lectura:
  Línea base · Estado: CONGELADA · 15-oct-2026 · J. Ramírez · "Contrato firmado el 13-oct-2026…"
  [ Ver conceptos ]  [ Ver explosión por tipo de partida ]        (sin controles de edición)
```

### 4b · Presupuesto de control por tipo de partida

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Presupuesto de control · AP-058-25 · Union Square F2           Línea base CONGELADA           │
├─────────────────────────┬───────────────┬───────────────┬────────────────┬────────────────────┤
│ Tipo de partida         │ Venta         │ Sugerido      │ Tope de control│ Capturado          │
├─────────────────────────┼───────────────┼───────────────┼────────────────┼────────────────────┤
│ MUROS                   │    $62,500.00 │    $44,100.00 │ [ 45,000.00  ] │ M. Torres · 15-oct │
│ PLAFONES Y CAJILLOS     │    $52,000.00 │    $36,700.00 │ [ 38,000.00  ] │ M. Torres · 15-oct │
│ ENCHAPES                │    $16,800.00 │    $11,850.00 │ [ 12,000.00  ] │ M. Torres · 15-oct │
│ GENERALES               │     $7,400.00 │     $5,200.00 │ [  8,000.00  ] │ sin capturar       │
│                         │               │               │ ! mayor que la │                    │
│                         │               │               │   venta        │                    │
├─────────────────────────┴───────────────┴───────────────┴────────────────┴────────────────────┤
│ El sugerido resta utilidad e indirectos al precio de venta. Es una referencia: manda el tope  │
│ capturado, y es contra ese contra el que se evalúan las requisiciones (RN-03).                │
│                                                                                               │
│                                                                      [ Guardar topes ]        │
└───────────────────────────────────────────────────────────────────────────────────────────────┘

  Tope mayor que la venta (al guardar):
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ GENERALES: el tope $8,000.00 supera la venta $7,400.00. Implicaría        │
  │ vender por debajo del costo tope.                                         │
  │ Motivo (obligatorio) [ Incluye andamiaje no presupuestado al cliente__ ]  │
  │                                   [ Corregir ]   [ Confirmar con motivo ] │
  └───────────────────────────────────────────────────────────────────────────┘

  Recaptura de un tope ya capturado (solo Dirección General):
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ Recapturar tope · MUROS                                                   │
  │ Tope vigente   $45,000.00   (M. Torres · 15-oct-2026)                     │
  │ Tope nuevo     [ 50,000.00_______ ]                                       │
  │ Motivo (obligatorio) [ Ampliación de muros en nivel 9 pactada en obra__ ] │
  │ Se registra en la bitácora con RN-03 y aparece en la bitácora de          │
  │ excepciones junto a las autorizaciones.                                   │
  │                                          [ Cancelar ]   [ Recapturar ]    │
  └───────────────────────────────────────────────────────────────────────────┘
```

**Datos como cadena decimal.** Venta, sugerido, tope capturado, tope vigente y tope nuevo. El campo de captura acepta texto y lo valida con Zod como decimal no negativo; **nunca se convierte a `Number`**.

**Acciones.**

- *Congelar línea base* exige motivo, copia conceptos y explosión, deja la línea base `CONGELADA` con fecha, usuario y motivo, y la obra `ACTIVA` (esc. 14). Tras congelar, la pantalla pasa a modo lectura (TKT-018).
- *Guardar topes* envía un `PUT` por cada fila capturada o cambiada y registra el importe con autor y fecha (esc. 15). La primera captura no exige motivo. Los campos vienen **vacíos**, no rellenados con el sugerido: precargarlo convertiría la sugerencia en el valor por omisión, y el tope se captura, no se deriva (`PA-03`). Si una fila falla, las demás conservan su resultado y la fallida queda marcada **(asumido: comportamiento de la interfaz, no del API)**.
- *Recapturar* abre el diálogo con motivo obligatorio y usa el mismo `PUT`. Al aceptar, el disponible del tipo de partida se recalcula de inmediato y la fila muestra el autor y la fecha nuevos (esc. 22).

**Estado vacío.** Línea base en `BORRADOR`: la sección 4b no se muestra; en su lugar, *"Congela primero la línea base para capturar el presupuesto de control"*.

**Estados de rechazo.**

- **Congelar sin motivo (`422`).** Mensaje junto al campo; la línea base sigue en `BORRADOR`.
- **Segunda línea base vigente (`409`, `RN-01`)** (esc. 19). Pantalla de bloqueo con el mensaje de que la sustitución exige una versión nueva que marque la anterior `SUPERSEDIDA`. En la fase 1 no hay versiones (`RN-18`, v1.1), así que no se ofrece acción.
- **Intento de modificar la línea base congelada (`409`, `RN-01`)** (esc. 18). La interfaz no tiene ningún control que lo permita; si llega por el API, el rechazo viene del disparador y el contrato de error, y queda en la bitácora.
- **Tope mayor que la venta (`409`)** (esc. 17). El servidor responde con la acción `CONFIRMAR_TOPE_SUPERIOR`, que abre el diálogo; al confirmarlo se reenvía con `confirmar_superior_a_venta` y el motivo, que va a la bitácora. Sin confirmación no se guarda.
- **Recaptura sin rol de Dirección General (`403`) o sin motivo (`422`)** (esc. 23). El tope conserva su valor; el `403` queda en la bitácora con la acción `DENEGAR`. Para quien no es Dirección General la columna *Tope de control* se ve en lectura y la acción *Recapturar* no aparece.

---

## 5. Disponible y captura de requisición

| | |
|---|---|
| **Rol** | Compras |
| **Historias** | HDU-002 esc. 1, 2, 3, 6, 7, 10, 11, 12 y 13 · HDU-001 esc. 16 |
| **Endpoints** | `GET /obras/{obra_id}/tipos-partida/{tipo_partida_id}/disponible` · `GET /obras/{obra_id}/tipos-partida/{tipo_partida_id}/requisiciones-vivas` · `POST /requisiciones` (borrador) · `PUT /requisiciones/{requisicion_id}` y `DELETE /requisiciones/{requisicion_id}` (solo en borrador) · `POST /requisiciones/{requisicion_id}/envio` · `POST /requisiciones/{requisicion_id}/cancelacion` · `GET /tipos-partida` · `GET /insumos` |

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Nueva requisición · AP-058-25 · Union Square F2           Tipo de partida [ MUROS        v ]  │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ DISPONIBLE DE MUROS EN TODA LA OBRA                                                           │
│   Tope de control            $45,000.00                                                       │
│   Consumido                  $33,000.00                                                       │
│     Requisiciones vivas        $6,000.00   ← 2 sin convertir   [ Ver y cancelar ]             │
│     Comprometido (OC)          $9,000.00                                                      │
│     Ejercido                  $18,000.00                                                      │
│   Disponible                 $12,000.00                                                       │
├────────────────────────────┬──────┬─────────────┬────────────┬───────────┬────────────────────┤
│ Insumo                     │ Ud.  │ Presupuest. │ Consumida  │ Disponible│ Solicitar          │
├────────────────────────────┼──────┼─────────────┼────────────┼───────────┼────────────────────┤
│ Tablero de yeso 1/2"       │ PZA  │      100.00 │      90.00 │     10.00 │ [   8.00 ] ×144.00 │
│ Poste 635 cal. 26          │ PZA  │    2,400.00 │   1,500.00 │    900.00 │ [ 577.00 ] × 24.00 │
│ Canal 635 cal. 26          │ PZA  │      800.00 │     610.00 │    190.00 │ [        ]         │
│ Tornillo S-1               │ CAJA │       60.00 │      41.00 │     19.00 │ [        ]         │
│ Compuesto Redimix          │ SACO │      150.00 │     102.00 │     48.00 │ [        ]         │
├────────────────────────────┴──────┴─────────────┴────────────┴───────────┴────────────────────┤
│                                                            Importe solicitado   $15,000.00    │
│ Borrador guardado 10:41 · REQ-1042                                                            │
│                                  [ Guardar borrador ]  [ Eliminar borrador ]  [ Enviar ]      │
└───────────────────────────────────────────────────────────────────────────────────────────────┘

  [ Ver y cancelar ] abre las requisiciones vivas de MUROS, de la más antigua a la más nueva
  (vista de L. Ortega, que solo puede cancelar las suyas):
  ┌──────────────────────────────────────────────────────────────────────────────────────┐
  │ Folio     Estado      Solicitante   Antigüedad   Importe                             │
  │ REQ-0987  EVALUADA    R. Castillo   23 días      $4,200.00   solo su solicitante     │
  │ REQ-1019  AUTORIZADA  L. Ortega      6 días      $1,800.00   [ Cancelar con motivo ] │
  └──────────────────────────────────────────────────────────────────────────────────────┘
```

**Datos como cadena decimal.** Tope, consumido y sus tres sumandos, disponible, cantidades presupuestada, consumida y disponible por insumo, costo unitario, importe de renglón e importe solicitado. El importe solicitado lo suma el cliente con `decimal.js` **solo para mostrarlo**; el que cuenta es el que calcula el servidor.

**Acciones.**

- *Tipo de partida*: al elegirlo se carga el disponible **del tipo de partida en el conjunto de la obra** —cuatro bolsas, no una por departamento— con el consumido desglosado en tres (esc. 1, esc. 13). No hay selector de nivel ni de área: no son nivel de control (`PA-01`).
- *Solicitar*: cantidad por insumo; el costo unitario se muestra junto a la cantidad. La columna *Disponible* **orienta y no bloquea**: el cliente no marca excesos ni impide enviar, porque **el cliente nunca evalúa una regla** (regla 10 de `CLAUDE.md`). Que el tablero de 8 piezas quepa en 10 lo decide el servidor.
- *Guardar borrador* crea o actualiza la requisición en `BORRADOR`: no consume presupuesto ni crea solicitud (esc. 2). *Eliminar borrador* solo existe en ese estado.
- *Enviar* llama a `/envio` sobre el borrador ya guardado. Si cabe, la requisición queda `EVALUADA` (`200`; crearla y enviarla en un solo paso respondería `201`, esc. 3) y la pantalla muestra *"REQ-1042 evaluada · disponible restante $X"* con la acción *Emitir orden de compra* para Compras. Si no cabe, la respuesta es `409` y se abre la [pantalla de bloqueo](#6-pantalla-de-bloqueo).
- *Ver y cancelar*: lista de requisiciones vivas por antigüedad con importe y solicitante; *Cancelar con motivo* usa el componente de captura de motivo y libera la reserva de inmediato (esc. 11, esc. 13). **Solo aparece en las requisiciones del usuario en sesión**: cancelar es del solicitante, y las demás se ven en lectura.

**Estado vacío.** Sin tipo de partida elegido, la tabla no se muestra y el panel de disponible dice *"Elige un tipo de partida para ver su disponible"*, no un `$0.00`.

**Estados de rechazo.**

- **Obra sin línea base congelada o sin tope capturado (`409`, `CONFLICTO` `SIN_LINEA_BASE_CONGELADA` o `SIN_PRESUPUESTO_CONTROL`)** (HDU-002 esc. 7, HDU-001 esc. 16). No es una regla: no se viola `RN-03`, falta contra qué evaluarla. El panel de disponible no muestra cifras: muestra el mensaje del contrato, que **distingue los dos casos por su `codigo`**, y la acción que corresponda —`CONGELAR_LINEA_BASE` o `CAPTURAR_PRESUPUESTO_CONTROL`— **solo si llega en `acciones[]`**, que el servidor filtra por los roles de quien llama. Compras, que no congela ni captura topes, ve el mensaje sin botón.
- **Cancelar una requisición ajena (`403`).** Solo la cancela su solicitante; el botón no aparece, y si alguien fuerza la petición, *"No tienes permiso"* y el intento queda en la bitácora con la acción `DENEGAR`.
- **Sin tipo de partida (`422`, `RN-02`)** (esc. 6). En línea: *"No existe gasto sin centro de costos: elige el tipo de partida."* No se crea la requisición.
- **Cantidad cero o negativa (`422`)** (esc. 10). El renglón inválido se marca en su fila; Zod lo detecta antes de enviar y el servidor lo vuelve a rechazar si llega.
- **Editar una requisición ya evaluada (`409`)** (esc. 12). Los renglones aparecen en lectura; si alguien fuerza la edición, el mensaje dice *"Cancélala y levanta una nueva"* con esa acción. Las cifras evaluadas no cambian.
- **Cancelar sin motivo (`422`).** El diálogo no se cierra.
- **Bloqueo por importe, por volumen, o por insumo ajeno a la explosión (`409`, `RN-03`)** y **perder la carrera concurrente** (esc. 4, 5, 8 y 9): pantalla de bloqueo.
- **Tiempo de espera de bloqueo vencido** (`RNF-16`). Contrato de error con la acción de reintentar, nunca un error genérico.
- **Sin conexión** (fase 2, HDU-002 esc. 14). *Enviar* se deshabilita con *"Las requisiciones necesitan conexión: el presupuesto se evalúa en el servidor"* y **no se encola**. En la fase 1 la aplicación no tiene cola, así que una pérdida de red da el error de red normal.

---

## 6. Pantalla de bloqueo

| | |
|---|---|
| **Rol** | Quien provocó la operación bloqueada |
| **Historias** | HDU-002 esc. 4, 5, 7, 8 y 9 · HDU-001 esc. 16, 18 y 19 · HDU-004 esc. 6 y 10 · HDU-005 esc. 5, 12, 22 y 23 · HDU-006 esc. 8 |
| **Endpoints** | Ninguno propio: **se alimenta de la respuesta `409`** que ya recibió la pantalla que la abre (esquema `ErrorConflicto`). Sus botones invocan las rutas de `acciones[]` |

Es el componente reutilizable de TKT-008. Renderiza **cualquier** `409` a partir del [contrato de error](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio) sin saber de qué pantalla viene: no recalcula nada ni interpreta el mensaje. El borrador OpenAPI distingue tres clases de `409` por su campo `tipo`, y el componente las pinta con la misma estructura y distinta cabecera:

| `tipo` | Cuándo | Cabecera |
|---|---|---|
| `REGLA_NEGOCIO` | Se viola una regla `RN-xx` | *Operación bloqueada* + la regla |
| `CONFLICTO` | El estado no admite la operación o falta un dato previo, sin violar ninguna `RN`: folio duplicado, solicitud ya resuelta, orden ya emitida, reemplazo sin confirmar, requisición bloqueada que se intenta convertir, obra sin línea base congelada o sin tope | *No se puede completar* + el `codigo` |
| `CONCURRENCIA` | Venció la espera de bloqueo (`RNF-16`) | *Inténtalo de nuevo* |

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ✕ OPERACIÓN BLOQUEADA                                                         Regla RN-03    │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ La requisición excede el presupuesto de control disponible del tipo de partida MUROS.        │
│                                                                                              │
│   Obra              AP-058-25 · Union Square F2                                              │
│   Tipo de partida   MUROS                                                                    │
│                                                                                              │
│   Presupuestado      $45,000.00                                                              │
│   Consumido          $33,000.00   requisiciones vivas $6,000.00 · comprometido $9,000.00 ·   │
│                                   ejercido $18,000.00                                        │
│   Disponible         $12,000.00                                                              │
│   Solicitado         $15,000.00                                                              │
│   Excedente           $3,000.00   ◄                                                          │
│                                                                                              │
│ La requisición REQ-1042 quedó registrada como BLOQUEADA. No avanza sin autorización.         │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Ver solicitud de autorización ]   [ Cancelar la requisición ]              [ Cerrar ]      │
│                                                            Referencia: 7f3c9a2e-41b0         │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

  Variante · por volumen (HDU-002 esc. 5) — el detalle señala el insumo:
  │   Insumo            Tablero de yeso 1/2"                                                  │
  │   Presupuestado     100.00 PZA    Consumido   90.00 PZA    Solicitado   25.00 PZA         │
  │   Excedente          15.00 PZA ◄  (el importe, $3,600.00, sí cabía)                       │

  Variante · excedente de recepción (HDU-005 esc. 5, RN-07):
  │   Ordenado  100.00 SACO   Recibido acumulado  50.00   Saldo pendiente  50.00             │
  │   Entrante   70.00 SACO   Excedente           20.00 ◄                                    │
  │   [ Solicitar autorización ]   [ Corregir cantidad ]                                     │

  Variante · tipo CONFLICTO al convertir una requisición BLOQUEADA (HDU-004 esc. 6):
  │ ! NO SE PUEDE COMPLETAR · ESTADO_NO_PERMITE_OPERACION                                    │
  │   REQ-1042 está BLOQUEADA: no se convierte en orden hasta que se autorice.               │
  │   [ Ver solicitud de autorización ]                                                      │

  Variante · tipo CONCURRENCIA (RNF-16, espera de bloqueo vencida):
  │ El presupuesto de esta partida está ocupado por otra operación. Vuelve a intentarlo.     │
  │   [ Reintentar ]                                                                         │
```

**Cómo se construye.**

- **Cabecera**: según `tipo` —la `regla`, el `codigo` o el aviso de reintento—. **Cuerpo**: `mensaje` tal cual.
- **Cifras**: cada clave de `detalle` con una etiqueta legible, en el orden de los esquemas del borrador OpenAPI. Por importe (`DetalleExcedePresupuesto`): `presupuestado`, `consumido` y su `consumido_desglose`, `disponible`, `solicitado`, `excedente`. Por volumen, la lista `insumos[]` con `cantidad_presupuestada`, `cantidad_consumida`, `cantidad_disponible`, `cantidad_solicitada` y `excedente`; un insumo con `presupuestado_en_partida: false` se rotula *"no presupuestado en esta partida"* (HDU-002 esc. 8). Por recepción (`DetalleExcedeOrdenado`), `renglones[]` con `cantidad_ordenada`, `cantidad_recibida`, `saldo_pendiente`, `cantidad_entrante` y `excedente`. Una clave desconocida se muestra con su nombre crudo en lugar de omitirse.
- **Todas las cifras llegan como cadena decimal** y se formatean con `decimal.js`. El excedente se resalta; no se deduce restando en el cliente.
- **Botones**: uno por cada elemento de `acciones[]`, con su `metodo` y su `ruta`. El componente **no cablea ningún botón de negocio**: si la respuesta no trae una acción, su botón no aparece (TKT-024). El servidor filtra `acciones[]` por los roles de quien llama salvo `REINTENTAR`, que repite una operación ya autorizada por `api/`; así que, fuera de esa excepción, nunca llega una acción que respondería `403`, y el componente no vuelve a filtrar. *Cerrar* es el único fijo.
- **Referencia**: `correlacion_id`, el identificador que TKT-005 devuelve en el cuerpo del error, para citarlo al pedir ayuda (`RNF-13`).

**Qué hace cada acción conocida.**

| Clave | Efecto en la interfaz | Escenario |
|---|---|---|
| `VER_SOLICITUD_AUTORIZACION` (`GET`, `RN-03`) | La solicitud **ya nació con el bloqueo**: *Ver solicitud de autorización* abre su estado. La requisición sigue `BLOQUEADA` | HDU-002 esc. 4 y 5, HDU-004 esc. 6 |
| `SOLICITAR_AUTORIZACION` (`POST /solicitudes-autorizacion`, `RN-07`) | La entrada se deshizo entera, así que no había solicitud: el botón la **crea** y muestra *"Solicitud enviada a Dirección General"*. La entrada no se registra, pero su captura se conserva: autorizada la solicitud, se reenvía con *Registrar con excedente autorizado* ([pantalla 9](#9-recepción-de-material-en-teléfono)) | HDU-005 esc. 5 y 21 |
| `CANCELAR_REQUISICION` | Abre la captura de motivo de cancelación. Solo llega si quien llama es el solicitante | HDU-002 esc. 4 y 12 |
| `REPROGRAMAR` | Navega al diálogo de reprogramación del faltante | HDU-005 esc. 12, HDU-004 esc. 10 |
| `CONGELAR_LINEA_BASE` · `CAPTURAR_PRESUPUESTO_CONTROL` | Navega a la [pantalla 4](#4-congelado-y-presupuesto-de-control), no ejecuta la ruta: congelar exige motivo y capturar exige importe | HDU-002 esc. 7, HDU-001 esc. 16, HDU-006 esc. 8 |
| `CONFIRMAR_REEMPLAZO` · `CONFIRMAR_TOPE_SUPERIOR` | Abren el diálogo de confirmación de su pantalla, con motivo cuando lo exige | HDU-001 esc. 13 y 17 |
| `VER_ENTRADA` | Abre la entrada previa con la misma remisión | HDU-005 esc. 7 |
| `REINTENTAR` | Repite la petición original, respetando `Retry-After` | `RNF-16` |

> **Una clave, un significado.** `VER_SOLICITUD_AUTORIZACION` abre una solicitud que ya existe —el bloqueo de `RN-03` la crea en la misma transacción— y `SOLICITAR_AUTORIZACION` crea una que no existe, lo que solo ocurre con el excedente de `RN-07`. Por eso el componente rotula cada botón por su clave y nunca crea una segunda solicitud para una requisición que ya la tiene.

**Qué no es esta pantalla.** Un `422` no la abre: se pinta junto al campo. Un `403` tampoco: es *"No tienes permiso"*, sin cifras. Un `409` de `tipo` `CONFLICTO` dentro de un formulario —código de obra duplicado, RFC duplicado— puede pintarse en línea junto al campo con los datos que trae la respuesta (la obra o el proveedor existente), porque no hay nada que bloquear: solo un dato que corregir.

**Estados de rechazo de las propias acciones.** Si la acción invocada responde a su vez con un `409`, la pantalla se **sustituye** por la nueva, no se apila. Si responde con un error de red, el botón vuelve a estar disponible y se muestra el error; la pantalla no se cierra, porque el usuario perdería las cifras.

---

## 7. Bandeja de autorizaciones y resolución

| | |
|---|---|
| **Rol** | Dirección General |
| **Historias** | HDU-003 esc. 1 a 11 · HDU-005 esc. 5 y 21 (excedente de recepción) |
| **Endpoints** | `GET /solicitudes-autorizacion` (por omisión, pendientes y sin efecto) · `GET /solicitudes-autorizacion/contador` · `GET /solicitudes-autorizacion/{solicitud_id}` · `POST /solicitudes-autorizacion/{solicitud_id}/resolucion` (`decision` y `motivo`) · `GET /bitacora` (paginada; filtros `regla_negocio`, obra y fechas) |

### 7a · Bandeja

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Autorizaciones pendientes (4)                          de la más antigua a la más reciente   │
├──────────┬───────────────────────────┬─────────────────────┬─────────────┬───────────┬───────┤
│ Recibida │ Obra · Tipo de partida    │ Solicitante         │ Solicitado  │ Excedente │ Regla │
├──────────┼───────────────────────────┼─────────────────────┼─────────────┼───────────┼───────┤
│ 09-oct   │ ENITI T5 · PLAFONES Y C.  │ R. Castillo         │   $9,400.00 │ $1,250.00 │ RN-03 │
│ 13-oct   │ AP-058-25 · ENCHAPES      │ R. Castillo         │  $10,200.00 │   $600.00 │ RN-03 │
│          │   SIN EFECTO · requisición cancelada: "Se surtió de sobrante de ENITI"    │       │
│ 15-oct   │ AP-058-25 · MUROS         │ L. Ortega           │  $15,000.00 │ $3,000.00 │ RN-03 │
│ 16-oct   │ AP-058-25 · MUROS         │ P. Núñez            │       70.00 │     20.00 │ RN-07 │
│          │   EXCEDE_ORDENADO · OC-0131 · Compuesto Redimix · cantidades en SACO      │       │
├──────────┴───────────────────────────┴─────────────────────┴─────────────┴───────────┴───────┤
│ Las solicitudes resueltas no aparecen aquí: están en la bitácora de excepciones.             │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7b · Detalle y resolución

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Solicitud de autorización · REQ-1042 · AP-058-25 · Union Square F2 · MUROS       PENDIENTE   │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Regla que bloqueó: RN-03 · presupuesto de control excedido                                   │
│ Cifras en el momento del bloqueo (15-oct-2026 10:42) — no recalculadas                       │
│   Presupuestado $45,000.00   Consumido $33,000.00   Disponible $12,000.00                    │
│   Solicitado    $15,000.00   Excedente  $3,000.00                                            │
│                                                                                              │
│ Renglones                                   Cantidad    Costo unit.     Importe              │
│   Tablero de yeso 1/2"                       8.00 PZA       $144.00      $1,152.00           │
│   Poste 635 cal. 26                        577.00 PZA        $24.00     $13,848.00           │
│                                                                                              │
│ Solicitante: L. Ortega (Compras) · 15-oct-2026 10:42                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Motivo (obligatorio también para autorizar)                                                  │
│ [ Se adelanta material del nivel 10 por cambio de secuencia acordado con la supervisión_ ]   │
│                                                                                              │
│                                                        [ Rechazar ]     [ Autorizar ]        │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

  Variante · excedente de recepción (HDU-005 esc. 5 y 21, RN-07):
  │ Solicitud de autorización · OC-0131 · AP-058-25 · MUROS · EXCEDE_ORDENADO   PENDIENTE    │
  │ Regla: RN-07 · recibir más de lo ordenado. Cifras recalculadas por el servidor al crear  │
  │   Compuesto Redimix · SACO  Ordenado 100.00  Recibido 50.00  Saldo 50.00                 │
  │   Entrante 70.00   Excedente solicitado 20.00 ◄                                          │
  │ Autorizar NO registra la entrada: habilita que Almacén la reenvíe con hasta 20.00 SACO   │
  │ de excedente, que se sumará a la recepción marcado como excedente. Se usa una sola vez.  │
  │                                                        [ Rechazar ]     [ Autorizar ]    │
```

### 7c · Bitácora de excepciones

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Bitácora de excepciones · Regla [ RN-03 v ]  Obra [ Todas v ]  Del [01-oct-2026] al [31-oct]  │
├───────────┬────────────┬──────────────────────┬───────────────┬───────────────────────────────┤
│ Fecha     │ Acción     │ Obra · Partida       │ Actor         │ Motivo                        │
├───────────┼────────────┼──────────────────────┼───────────────┼───────────────────────────────┤
│ 02-oct    │ AUTORIZAR  │ ENITI T5 · MUROS     │ M. Torres     │ Cambio de calibre por cliente │
│ 06-oct    │ RECHAZAR   │ AP-058-25 · GENERAL. │ M. Torres     │ Sin soporte de cotización     │
│ 10-oct    │ RECAPTURAR │ ENITI T5 · PLAFONES  │ M. Torres     │ $120,000.00 → $135,000.00 ·   │
│           │            │                      │               │ cambio de alcance pactado     │
│ 15-oct    │ BLOQUEAR   │ AP-058-25 · MUROS    │ L. Ortega     │ (pendiente de resolver)       │
├───────────┴────────────┴──────────────────────┴───────────────┴───────────────────────────────┤
│ Página 1 de 1                                              [ ‹ Anterior ]  [ Siguiente › ]    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

La columna *Acción* pinta el valor de `accion` tal cual llega, del enum cerrado de la bitácora: `CREAR`, `ACTUALIZAR`, `EVALUAR`, `BLOQUEAR`, `AUTORIZAR`, `RECHAZAR`, `CANCELAR`, `EMITIR`, `AJUSTAR`, `REPROGRAMAR`, `CONGELAR`, `RECAPTURAR`, `DESCARTAR`, `CONFIRMAR`, `ANULAR`, `SUSPENDER`, `REACTIVAR`, `CERRAR`, `DESACTIVAR`, `LIBERAR`, `VALIDAR` y `DENEGAR`. La interfaz no inventa etiquetas de estado como *"autorizada"* o *"recapturada"*: traduce la clave a texto legible, nada más.

**Datos como cadena decimal.** Solicitado, excedente, las cinco cifras del momento del bloqueo, cantidades, costos unitarios e importes de renglón, y los topes anterior y nuevo de una recaptura.

**Acciones.**

- *Abrir una solicitud* carga su detalle con las cifras **congeladas en el momento del bloqueo**, no las de hoy (esc. 3). La pantalla lo dice en texto para que nadie las compare con el disponible actual creyendo que es el mismo.
- *Autorizar* y *Rechazar* envían la decisión con el motivo (esc. 4, esc. 5). Tras resolver, la solicitud sale de la bandeja, el contador baja y, si era la última, desaparece (esc. 1). La autorización deja la requisición en `AUTORIZADA`, lista para la [pantalla 8](#8-emisión-de-orden-de-compra); el rechazo la deja en `RECHAZADA`, sin salida a orden de compra.
- No hay selección múltiple: no se autoriza en lote (non-goal de HDU-003).
- *Bitácora de excepciones* filtra por regla —parámetro `regla_negocio`—, obra y fechas, y pagina; muestra autorizaciones (`AUTORIZAR`), rechazos (`RECHAZAR`), **bloqueos nunca resueltos** (`BLOQUEAR`) y **recapturas de tope** (`RECAPTURAR`), distinguibles por la columna *Acción* (esc. 11, HDU-001 esc. 22). Los rechazos de forma o de estado que no son regla —`CONFLICTO`— no se asientan con `RN-03` y no aparecen aquí.

**Estado vacío.** Bandeja sin pendientes: *"No hay solicitudes pendientes"*. La entrada del menú pierde el contador.

**Estados de rechazo.**

- **Resolver sin motivo (`422`)** (esc. 6). *"El motivo es obligatorio también al autorizar"*, junto al campo. La solicitud sigue `PENDIENTE`. Los dos botones se deshabilitan mientras el motivo esté vacío, y el servidor lo rechaza igual si llega.
- **Autorizar la propia solicitud (`403`, `AUTO_RESOLUCION`)** (esc. 8). Si el solicitante es el usuario en sesión, el detalle muestra *"Tú levantaste esta requisición: nadie resuelve sus propias solicitudes"* y los botones no aparecen. Es cortesía: el control está en `dominio/` y el intento forzado queda en la bitácora.
- **Usuario sin rol de Dirección General (`403`, `ROL_INSUFICIENTE`)** (esc. 7). No ve la bandeja en el menú; si llega por URL, *"No tienes permiso"*, sin importes, y el intento queda en la bitácora con la acción `DENEGAR`, asentada en una transacción propia porque no hay cambio que acompañar.
- **Solicitud ya resuelta (`409`, `YA_RESUELTA`)** (esc. 9). Si otra sesión la resolvió entre la carga y el clic, el detalle se sustituye por *"Ya fue autorizada por M. Torres el 15-oct-2026 11:03"* con el motivo original, sin botones.
- **Requisición cancelada, *sin efecto*** (esc. 10). La bandeja la sigue listando, atenuada y con el motivo de la cancelación; el detalle no tiene botones de resolución, y si alguien la resuelve por el API recibe `409` `SOLICITUD_SIN_EFECTO`.
- **Solicitud de excedente de recepción (`RN-07`).** La bandeja es genérica (HDU-003 *comparte contrato con* HDU-005) y la muestra con su regla en la última columna, con **cantidades** en la unidad del insumo en lugar de importes. Su detalle (variante de 7b) muestra el renglón de la orden y las cifras que el servidor **recalculó** al crearla. **Autorizarla no registra la entrada: la habilita** (`PA-16`, resuelta el 2026-10-17). La solicitud pasa a `AUTORIZADA` y se asienta con `RN-07`, la orden no cambia, y Almacén reenvía la entrada desde la [pantalla 9](#9-recepción-de-material-en-teléfono) con *Registrar con excedente autorizado*. Hasta ese reenvío no hay entrada, ni movimiento, ni excedente en la orden: una autorización que nadie usa no altera nada. El detalle lo dice junto al botón, para que nadie espere ver la entrada registrada al autorizar. Rechazarla deja la captura de Almacén sin salida: se corrige la cantidad o se descarta.

---

## 8. Emisión de orden de compra

| | |
|---|---|
| **Rol** | Compras |
| **Historias** | HDU-004 esc. 4, 5, 6, 7, 8, 9 y 10 |
| **Endpoints** | `GET /requisiciones` (filtrada por obra y por estado `EVALUADA` y `AUTORIZADA`) · `GET /proveedores` (activos) · `POST /ordenes-compra` (`requisicion_id`, `proveedor_id`, `fecha_compromiso`) · `GET /ordenes-compra/{orden_compra_id}` · `POST /ordenes-compra/{orden_compra_id}/cancelacion` |

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Emitir orden de compra · AP-058-25 · Union Square F2                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Requisición  [ REQ-1042 · MUROS · AUTORIZADA · $15,000.00                              v ]   │
│              Autorizada por M. Torres el 15-oct-2026 11:03 · solicitud SA-0311               │
│                                                                                              │
│ Proveedor    [ Selecciona un proveedor activo…                                         v ]   │
│              CoPanel · Distribuidora Tablaroca del Centro · Aceros y Perfiles del Bajío      │
│                                                                                              │
│ Fecha comprometida de entrega  [ 22-oct-2026 ]                                               │
│                                                                                              │
│ Renglones copiados de la requisición (no editables)                                          │
│   Tablero de yeso 1/2"                       8.00 PZA       $144.00      $1,152.00           │
│   Poste 635 cal. 26                        577.00 PZA        $24.00     $13,848.00           │
│                                                                Total    $15,000.00           │
│ Hereda la obra AP-058-25 y el tipo de partida MUROS.                                         │
│                                                                                              │
│                                                              [ Emitir orden de compra ]      │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

  Tras emitir:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ ✓ Orden OC-0137 emitida a CoPanel · ABIERTA · $15,000.00                 │
  │   REQ-1042 pasa a CONVERTIDA.                                            │
  │   [ Ver orden ]   [ Imprimir ]   [ Cancelar orden con motivo ]           │
  └──────────────────────────────────────────────────────────────────────────┘
```

**Datos como cadena decimal.** Importe de la requisición, cantidades, costos unitarios, importes de renglón y total.

**Acciones.**

- *Requisición*: el selector solo lista requisiciones `EVALUADA` y `AUTORIZADA` sin convertir. Si es `AUTORIZADA`, muestra quién la autorizó y la solicitud que la habilitó, que la orden conserva como referencia (esc. 5).
- *Proveedor*: solo activos; uno desactivado no aparece pero conserva su historial (HDU-004 esc. 12). El alta y la desactivación de proveedores usan el formulario de catálogo de TKT-008 (esc. 1 a 3) y no se dibujan aquí. No hay *baja* aparte: la única operación es `POST /proveedores/{id}/desactivacion`, que es una baja lógica (`activo = false`) y conserva órdenes e historial.
- *Fecha comprometida*: obligatoria al emitir, una por orden, que se copia a cada renglón; el borrador OpenAPI admite además una fecha propia por renglón, que el boceto no dibuja. Es la fecha de la que parte la reprogramación de HDU-005 esc. 10.
- *Emitir* crea la orden en `ABIERTA` con folio único y consecutivo asignado por el servidor —el cliente no lo propone— y la requisición pasa a `CONVERTIDA` (esc. 4). El boceto abrevia los folios (`OC-0137`, `REQ-1042`); el borrador OpenAPI los forma con el código de la obra, como `OC-AP05825-0017`.
- *Imprimir*: la orden no se envía al proveedor desde el sistema (non-goal de HDU-004); se imprime o se comparte fuera.
- *Cancelar orden con motivo*: solo mientras no tenga recepciones. La requisición vuelve a `EVALUADA`, o a `AUTORIZADA` si nació de una excepción, y **el presupuesto no se libera**: la pantalla lo dice —*"El importe vuelve a contar como requisición viva; para liberarlo, cancela también la requisición"*— (esc. 9).

**Estado vacío.** Sin requisiciones convertibles: *"No hay requisiciones evaluadas o autorizadas pendientes de convertir en esta obra"*, con enlace a [nueva requisición](#5-disponible-y-captura-de-requisición).

**Estados de rechazo.**

- **Sin proveedor (`422`)** (esc. 8). Junto al selector; no se crea la orden.
- **Requisición `BLOQUEADA` o `RECHAZADA` (`409`, `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`)** (esc. 6). No aparecen en el selector; si se fuerza, pantalla de bloqueo con cabecera *No se puede completar*, **sin regla**: `RN-03` ya se aplicó al bloquear y este intento no se asienta como otra excepción. Si está bloqueada, trae la acción `VER_SOLICITUD_AUTORIZACION`; si fue rechazada, ninguna.
- **Requisición ya `CONVERTIDA` (`409`, `ORDEN_YA_EMITIDA`)** (esc. 7). *"Esta requisición ya originó la orden OC-0137"* con enlace a ella. Una requisición origina como mucho una orden.
- **Cancelar una orden con recepciones (`409`)** (esc. 10). Pantalla de bloqueo con *"Ya hay material recibido: reprograma el faltante"* y la acción `REPROGRAMAR`.
- **Proveedor desactivado entre la carga y el envío (`409`, `PROVEEDOR_INACTIVO`).** El selector se recarga sin él.
- **Cancelar sin motivo (`422`).** El diálogo no se cierra.

---

## 9. Recepción de material en teléfono

| | |
|---|---|
| **Rol** | Almacén · Residente de obra |
| **Historias** | HDU-005 esc. 1 a 14 y 21 a 23 |
| **Endpoints** | `GET /ordenes-compra` (filtrada por obra y por estado `ABIERTA` y `PARCIAL`) · `GET /obras/{obra_id}/saldos-pendientes` · `POST /entradas-almacen` · `POST /entradas-almacen/{entrada_id}/correccion` · `POST /ordenes-compra/{orden_compra_id}/renglones/{renglon_id}/reprogramacion` · `POST /solicitudes-autorizacion` (excedente de `RN-07`) · `GET /solicitudes-autorizacion/{solicitud_id}` (estado de esa solicitud) · `GET /obras/{obra_id}/movimientos-inventario` |

Se diseña para **pantalla de teléfono, de pie en obra** (TKT-008). Una columna, controles grandes, sin tablas anchas.

```text
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ ‹  Recepción · AP-058-25               │   │ ‹  OC-0131 · CoPanel                   │
├────────────────────────────────────────┤   ├────────────────────────────────────────┤
│ Órdenes por recibir                    │   │ Folio de remisión (obligatorio)        │
│                                        │   │ [ R-4588____________________ ]         │
│ OC-0131 · CoPanel            PARCIAL   │   │ Fecha de entrega  [ 15-oct-2026 ]      │
│ MUROS · $9,000.00 · emitida 02-oct     │   │                                        │
│                                        │   │ Compuesto Redimix · SACO               │
│                                        │   │ Ordenado        100.00                 │
│ OC-0137 · CoPanel            ABIERTA   │   │ Recibido         50.00                 │
│ MUROS · $15,000.00 · emitida 15-oct    │   │ Saldo pendiente  50.00                 │
│                                        │   │ Comprometida 17-oct · reprog. 1 vez    │
│                                        │   │ Llegó  [ 30.00______ ]                 │
│ OC-0129 · Aceros y Perfiles  ABIERTA   │   │                                        │
│ GENERALES · $1,200.00 · emitida 01-oct │   │ Tablero de yeso 1/2" · PZA             │
│                                        │   │ Ordenado        120.00                 │
│                                        │   │ Recibido        120.00                 │
│                                        │   │ Saldo pendiente   0.00   completo      │
│                                        │   │                                        │
│                                        │   │ [      Registrar entrada      ]        │
└────────────────────────────────────────┘   └────────────────────────────────────────┘

┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ ✓ Entrada registrada · R-4588          │   │ Reprogramar faltante                   │
├────────────────────────────────────────┤   ├────────────────────────────────────────┤
│ OC-0131 sigue PARCIAL                  │   │ Compuesto Redimix · saldo 20.00 SACO   │
│ Compuesto Redimix                      │   │ Comprometida vigente   17-oct-2026     │
│   saldo pendiente 20.00 SACO           │   │ Nueva fecha  [ 24-oct-2026 ]           │
│                                        │   │ Motivo (obligatorio)                   │
│ [ Reprogramar faltante ]               │   │ [ Proveedor sin existencia de______ ]  │
│ [ Corregir esta entrada ]              │   │ [ el compuesto hasta el lunes_____ ]   │
│ [ Volver a órdenes ]                   │   │                                        │
│                                        │   │ La orden sigue PARCIAL y el importe    │
│                                        │   │ sigue comprometido.                    │
│                                        │   │ [ Cancelar ]   [ Reprogramar ]         │
└────────────────────────────────────────┘   └────────────────────────────────────────┘

  Variante · excedente autorizado (HDU-005 esc. 5, 21 y 22): tras el 409 de RN-07 y la solicitud
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ ‹  OC-0131 · R-4588 · por reenviar     │   │ ✓ Entrada registrada · R-4588          │
├────────────────────────────────────────┤   ├────────────────────────────────────────┤
│ Captura conservada · NO registrada     │   │ OC-0131 pasa a CERRADA                 │
│ Compuesto Redimix · SACO               │   │ Compuesto Redimix                      │
│ Saldo pendiente  50.00                 │   │   recibido en esta entrada 70.00 SACO  │
│ Llegó            70.00                 │   │   EXCEDENTE 20.00 SACO ◄ autorizado    │
│ Excedente        20.00                 │   │   solicitud SA-0315 · M. Torres        │
│                                        │   │ Ordenado 100.00 · recibido 120.00      │
│ Solicitud SA-0315 · AUTORIZADA         │   │ Saldo pendiente 0.00                   │
│ M. Torres · hasta 20.00 SACO           │   │                                        │
│                                        │   │ [ Volver a órdenes ]                   │
│ [Registrar con excedente autorizado]   │   │                                        │
│ [ Descartar la captura ]               │   │                                        │
└────────────────────────────────────────┘   └────────────────────────────────────────┘

  Mientras la solicitud está PENDIENTE, en lugar del botón de reenvío:
  │ Solicitud SA-0315 · PENDIENTE de Dirección General  │
  │ [ Descartar la captura ]   [ Corregir cantidad ]    │
  RECHAZADA: "Dirección General rechazó el excedente: <motivo>" y los mismos dos botones.
```

**Datos como cadena decimal.** Ordenado, recibido acumulado, saldo pendiente y cantidad que llegó, por renglón. El importe ejercido no se muestra aquí: lo muestra el semáforo, al instante (esc. 14).

**Acciones.**

- *Elegir orden*: lista órdenes `ABIERTA` y `PARCIAL` de la obra con lo que devuelve el resumen de `GET /ordenes-compra` —folio, proveedor, estado, tipo de partida, importe y fecha de emisión—. La fecha comprometida vigente y **cuántas veces se ha reprogramado** son **por renglón** y salen del detalle de la orden (`GET /ordenes-compra/{orden_compra_id}`) o de `GET /obras/{obra_id}/saldos-pendientes`, no de la lista (esc. 13).
- *Registrar entrada*: envía la remisión y las cantidades. El servidor deriva el estado de la orden —`PARCIAL` o `CERRADA`—; la interfaz **no lo asigna ni lo presupone** (esc. 1 a 3). Un renglón con saldo cero se muestra *completo* y sin campo de captura.
- *Reprogramar faltante*: nueva fecha posterior a la vigente y motivo; la orden **permanece `PARCIAL`** y el presupuesto sigue comprometido (esc. 10). Lo puede hacer Almacén —y Compras desde su lado—, no el Residente de obra, que no ve el botón.
- *Corregir esta entrada*: pide la **cantidad correcta absoluta** —`cantidad_correcta`, lo que de verdad llegó— y el motivo; el servidor calcula la diferencia y genera el movimiento `AJUSTE`. El cliente no calcula ni envía el ajuste. **No edita ni borra** la entrada original: el historial muestra las dos (esc. 8). Solo Almacén.
- *Registrar con excedente autorizado* (esc. 21): reenvía **la misma captura** que rechazó `RN-07` —no se vuelve a teclear— citando `solicitud_autorizacion_id` en el renglón. El servidor suma el excedente a la recepción, marca el renglón con su `excedente` y deriva el estado —aquí `CERRADA`, porque lo ordenado quedó cubierto—. El excedente cuenta como ejercido: el semáforo lo muestra al instante. El botón solo aparece cuando `GET /solicitudes-autorizacion/{solicitud_id}` dice `AUTORIZADA`; es cortesía, porque el servidor vuelve a comprobarlo (esc. 22). La captura se guarda en el dispositivo, no en el servidor, hasta que se reenvía o se descarta **(asumido)**: no hay borrador de entrada en el API, y en el servidor la entrada no existe hasta el reenvío.
- *Descartar la captura*: la borra del dispositivo. No toca la solicitud, que queda como está en la bitácora.
- En el historial y en la entrada, un renglón con excedente se rotula **EXCEDENTE** con la cantidad y la solicitud que lo autorizó.
- **No existe un botón de cerrar la orden.** Una orden solo llega a `CERRADA` al entregarse completa (`RN-06`, `PA-07`). La ruta `/cierre` existe en el API para que el intento tenga un rechazo verificable, no para que la interfaz la ofrezca.

**Estado vacío.** Obra sin órdenes por recibir: *"No hay órdenes abiertas ni parciales en esta obra."*

**Estados de rechazo.**

- **Sin folio de remisión (`422`, `RN-05`)** (esc. 4). Junto al campo: *"La entrada se valida contra la remisión del proveedor, no contra la orden de compra."* No se crea ningún movimiento.
- **Cantidad mayor que el saldo (`409`, `RN-07`)** (esc. 5). Pantalla de bloqueo en formato de teléfono —una columna— con ordenado, recibido acumulado, saldo, entrante y excedente, y `SOLICITAR_AUTORIZACION`, que aquí **crea** la solicitud. La orden conserva su saldo; no se crea movimiento. La captura **se conserva** para reenviarla cuando la solicitud se autorice (variante *excedente autorizado*; `PA-16`, resuelta). El cliente **no** compara la cantidad con el saldo para impedir el envío: el saldo en pantalla orienta, no autoriza.
- **Reenvío con la solicitud `PENDIENTE` o `RECHAZADA`, o con más excedente del autorizado (`409`, `RN-07`)** (esc. 22). Pantalla de bloqueo con las cifras, el excedente intentado, el autorizado y el estado de la solicitud. No se registra nada y la orden conserva su saldo; la captura sigue en el dispositivo.
- **Solicitud de otro renglón o ya consumida (`409`, `CONFLICTO` `SOLICITUD_NO_APLICABLE`)** (esc. 22). *"Esa autorización no corresponde a este renglón o ya se usó"*. Una solicitud autorizada habilita una sola entrada.
- **Orden `CERRADA` o `CANCELADA` (`409`)** (esc. 6). Si cambió de estado mientras se capturaba: *"OC-0131 está CERRADA; no admite entradas"* y vuelta a la lista.
- **Remisión duplicada del mismo proveedor (`409`, `FOLIO_REMISION_DUPLICADO`)** (esc. 7). *"Ya existe la entrada de R-4521 de CoPanel del 03-oct"* con la acción `VER_ENTRADA`, para verificar si es un reingreso por error.
- **Corregir sin motivo (`422`)** (esc. 9). No se genera el ajuste.
- **Corregir una entrada de una orden `CERRADA` (`409`, `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`)** (esc. 23; `PA-17`, resuelta: no se corrige). Pantalla de bloqueo *No se puede completar* con *"OC-0131 está CERRADA: sus entradas ya no se corrigen"*; no se genera ningún `AJUSTE` y la orden sigue `CERRADA`. *Corregir esta entrada* no se ofrece sobre una orden cerrada, y si la petición llega por el API se rechaza igual. En una orden `ABIERTA` o `PARCIAL` funciona normal.
- **Reprogramar sin motivo o con fecha anterior a la vigente (`422`)** (esc. 11). Se marca el campo inválido; la fecha vigente no cambia.
- **Cierre con saldo (`409`, `RN-06`)** (esc. 12). La interfaz no lo ofrece; si llega por el API, pantalla de bloqueo con `REPROGRAMAR`.

**Fase 2 · qué cambia.** La captura pasa a ser **diferible sin conexión** (TKT-068): aparece el indicador de conexión y cola, el saldo se lee de caché **mostrando su antigüedad**, la entrada queda *en cola* sin generar movimiento hasta sincronizar, y una entrada que al subir excede lo ordenado vuelve con el contrato de `RN-07` y detiene la cola (HDU-005 esc. 15 a 18). Además se adjunta la foto de la remisión (esc. 19 y 20).

---

## 10. Semáforo de obra y desglose

| | |
|---|---|
| **Rol** | Dirección General (destinatario) · Director de Proyectos |
| **Historias** | HDU-006 esc. 1 a 16 |
| **Endpoints** | `GET /obras/{obra_id}/semaforo` (filas con `ejercido` real, `ejercido_simulado` aparte, `requisiciones_vivas`, `disponible`, desviación con `ilustrativa`, `estado` y `alerta`; totales, `cifra_parcial` y **metadato de fuentes** `fuentes[]`: `REAL` / `SIMULADA` / `SIN_DATOS`) · `GET /obras/{obra_id}/semaforo/partidas/{tipo_partida_id}` (desglose por fuente, por insumo y por ubicación: nivel y área) · `GET /obras/{obra_id}/semaforo/partidas/{tipo_partida_id}/movimientos` (hasta el documento de origen, con cantidad, unidad y motivo) · `GET /semaforo/alertas` (excluye las desviaciones ilustrativas) |

### 10a · Semáforo

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Semáforo de obra · AP-058-25 · Union Square F2                     Actualizado 15-oct-2026 12:10      │
│ Datos simulados (*): destajo, nómina y avance físico. Desviación ilustrativa (~): sin alertas.        │
│ ! Cifra parcial: el ejercido real solo incluye materiales. No es el costo real de la obra.            │
├─────────────────────┬────────────┬────────────┬────────────┬─────────────┬──────────┬─────────────┬───┤
│ Tipo de partida     │ Presupuest.│ Comprom.   │ Ejercido   │ Simulado *  │ Avance   │ Desviación  │   │
├─────────────────────┼────────────┼────────────┼────────────┼─────────────┼──────────┼─────────────┼───┤
│ MUROS               │  45,000.00 │   9,000.00 │  18,000.00 │  8,000.00 * │ 40.0 % * │ +8,000.00 ~ │ R │
│ PLAFONES Y CAJILLOS │  38,000.00 │   4,500.00 │   9,200.00 │  3,000.00 * │ 35.0 % * │ −1,100.00 ~ │ V │
│ ENCHAPES            │  12,000.00 │       0.00 │   2,400.00 │           — │        — │  no calcul. │ – │
│ GENERALES           │   8,000.00 │   1,200.00 │     950.00 │           — │ 11.0 % * │    +70.00 ~ │ A │
├─────────────────────┼────────────┼────────────┼────────────┼─────────────┼──────────┼─────────────┼───┤
│ Mano de obra de     │          — │          — │          — │ 22,000.00 * │        — │ no imputada │   │
│ nómina              │            │            │            │             │          │   a partida │   │
├─────────────────────┼────────────┼────────────┼────────────┼─────────────┼──────────┼─────────────┼───┤
│ TOTAL DE LA OBRA    │ 103,000.00 │  14,700.00 │  30,550.00 │ 33,000.00 * │          │             │   │
├─────────────────────┴────────────┴────────────┴────────────┴─────────────┴──────────┴─────────────┴───┤
│ V verde · A amarillo · R rojo (PA-18). – sin avance medido: estado aparte, no color.                  │
│ Corte con umbral_alerta_pct de la obra (15 %): A si la desviación relativa no lo supera, R si         │
│ lo supera. ▲ alerta: sale con R, pero ninguna fila la lleva porque toda desviación es ilustrativa.    │
│                                                                                                       │
│ Disponible para requisiciones (RN-03), solo con el ejercido real:                                     │
│   MUROS $12,000.00 · PLAFONES Y CAJILLOS $14,300.00 · ENCHAPES $9,600.00 · GENERALES $5,850.00.       │
│   MUROS sigue en $12,000.00 aunque su destajo simulado sume $8,000.00.                                │
│                                                                                                       │
│ Fuentes: presupuestado REAL · comprometido REAL · materiales REAL · destajo SIMULADA ·                │
│          nómina SIMULADA · avance físico SIMULADA                                                     │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Variante · obra sin línea base congelada (HDU-006 esc. 8): en lugar de la tabla, sin ceros
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ AP-058-25 no tiene presupuesto congelado contra el que comparar.         │
  │ [ Ir a congelar la línea base ]   (solo si llega en acciones[])          │
  └──────────────────────────────────────────────────────────────────────────┘

  Variante · fuentes SIN_DATOS (HDU-006 esc. 6; es lo que ve producción en la fase 1):
  sin columna Simulado ni letrero de datos simulados, y con el aviso de cifra parcial
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ ! Cifra parcial: el ejercido solo incluye materiales. Faltan destajo y   │
  │   nómina. No es el costo real completo de la obra.                       │
  └──────────────────────────────────────────────────────────────────────────┘
```

### 10b · Desglose de una partida hasta el movimiento

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Semáforo   MUROS · AP-058-25 · ejercido real $18,000.00 · simulado $8,000.00 *                          │
│ [ Materiales $18,000.00 ]  [ Destajo $8,000.00 * ]  [ Por nivel ]  [ Por área ]                           │
├───────────┬──────────┬────────────────────┬────────────┬─────────────┬─────────────┬──────────────────────┤
│ Fecha     │ Tipo     │ Documento de origen│ Responsable│ Cantidad    │     Importe │ Motivo               │
├───────────┼──────────┼────────────────────┼────────────┼─────────────┼─────────────┼──────────────────────┤
│ 03-oct    │ ENTRADA  │ E-0298 · OC-0131 › │ P. Núñez   │ 50.00 SACO  │   $6,250.00 │                      │
│ 08-oct    │ ENTRADA  │ E-0305 · OC-0122 › │ P. Núñez   │ 80.00 PZA   │  $11,520.00 │                      │
│ 09-oct    │ AJUSTE   │ E-0305 · OC-0122 › │ P. Núñez   │ −2.00 PZA   │    −$288.00 │ Se contaron 2 de más │
│ 14-oct    │ ENTRADA  │ E-0311 · OC-0126 › │ P. Núñez   │ 4.00 CAJA   │     $518.00 │                      │
├───────────┴──────────┴────────────────────┴────────────┴─────────────┴─────────────┴──────────────────────┤
│                                                                                Suma materiales $18,000.00 │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Pestaña Destajo en la fase 1: renglones marcados "dato simulado", sin documento de origen
  navegable, porque no existe ningún pago_destajo.
```

**Datos como cadena decimal.** Presupuestado, comprometido, ejercido y sus partes, desviación, disponible por tipo de partida, totales, cantidades e importes de cada movimiento. **El avance es un porcentaje que también viaja como cadena** y puede ser **nulo**; nulo no se pinta como `0 %`.

**Cómo se lee.**

- **Cuatro filas, una por tipo de partida, agregando toda la obra** —no una por departamento—, más la fila de **mano de obra de nómina**, marcada *no imputada a partida*, y la de totales (esc. 1, 5 y 13). La nómina entra en el total y **no** en ninguna desviación por partida.
- **Ejercido** es **solo el real**: el mismo que entra en el consumido de `RN-03`. Suma materiales y destajo reales, y el desglose dice cuánto aporta cada fuente (esc. 4). Lo simulado **nunca** se suma en esa celda: va en su propia columna, **Simulado**, marcada `*` (`ejercido_simulado`, que solo existe con fuente `SIMULADA`). En la fase 1 el ejercido real de cada fila es solo de materiales.
- **Desviación** = (ejercido + simulado) − presupuestado × avance (esc. 2, 3 y 16), y **desviación relativa** = desviación ÷ (presupuestado × avance). Si alguna entrada es simulada llega con `ilustrativa: true` y se rotula `~` (esc. 14).
- **Color y alerta los decide el servidor.** Cada fila trae `estado` —`VERDE`, `AMARILLO`, `ROJO` o `SIN_AVANCE_MEDIDO`— y `alerta`; la interfaz los pinta y no compara nada. **Tres colores** (`PA-18`, resuelta el 2026-10-17): verde con desviación cero o negativa; amarillo con desviación positiva cuya relativa **no supera** el `umbral_alerta_pct` de la obra —GENERALES, +$70.00 sobre $880.00, un 8 %—; rojo cuando lo supera —MUROS, +$8,000.00 sobre $18,000.00, un 44 %—, o con cualquier desviación positiva si la obra no tiene umbral. El corte es un supuesto sin bloqueo del [PRD §10](01-descripcion-producto.md#supuestos-asumidos-sin-bloqueo). `SIN_AVANCE_MEDIDO` **no es un color**: es la ausencia de juicio, y se pinta `–` con su leyenda. La alerta (esc. 11) sale con el rojo y **no se emite con desviación ilustrativa**: por eso en la fase 1 ninguna fila lleva `▲`, aunque MUROS supere el umbral. Una fila amarilla nunca alerta (esc. 16).
- **Letrero de datos simulados y aviso de cifra parcial.** Los dos se **generan desde `fuentes[]`**, no son texto fijo de la pantalla. El letrero nombra las fuentes `SIMULADA` y solo aparece si hay alguna; el aviso de cifra parcial aparece en cuanto **alguna fuente no es `REAL`**, sea `SIMULADA` o `SIN_DATOS` (esc. 6 y 14).
- **"Sin avance medido" no es cero.** ENCHAPES tiene gasto y ningún avance validado: el avance se muestra `—` con la leyenda y la desviación *no calculable*, no igual al ejercido (esc. 9; regla 12 de `CLAUDE.md`). Solo cuenta el avance `VALIDADO` (esc. 10).
- **El disponible no incluye nada simulado** (esc. 15). La franja inferior muestra el mismo disponible que aplica `RN-03` —calculado con la consulta del [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo)—, y MUROS sigue en $12,000.00 aunque su destajo simulado sume $8,000.00: una requisición que cabe en el disponible real **no** se bloquea por destajo simulado.
- **Fuentes**: el metadato de la respuesta —presupuestado, comprometido, materiales, destajo, nómina y avance físico, que cubre alcance y ejecutado—, pintado tal cual. La interfaz no decide qué es simulado: lo lee de la `fuente` que acompaña a cada cifra.

**Acciones.**

- *Abrir una fila* lleva al desglose (10b). Cada movimiento trae fecha, tipo, cantidad, unidad, importe, responsable y, si lo tiene —un `AJUSTE`—, su motivo, y enlaza a su entrada de almacén, y de ahí a la remisión y la orden (esc. 7). El enlace al renglón de nómina es de la fase 2. Las pestañas *Por nivel* y *Por área* reparten el presupuesto y el avance por ubicación, sin ser nivel de control (esc. 13).
- La tabla se refresca al volver a la pantalla y tras cualquier entrada registrada en la sesión (invalidación de TanStack Query); no hay botón de recalcular porque no hay nada que recalcular: se calcula al consultar.

**Estados de rechazo.**

- **Obra sin línea base congelada (`409`, `CONFLICTO` `SIN_LINEA_BASE_CONGELADA`)** (esc. 8). Ninguna cifra ni ningún cero que pueda confundirse con un dato: solo el mensaje y, si llega en `acciones[]` —el servidor la filtra por rol—, `CONGELAR_LINEA_BASE`, que lleva a la pantalla 4.
- **Usuario sin el rol (`403`)** (esc. 12). *"No tienes permiso para ver el semáforo"*, sin ningún importe en la respuesta ni en pantalla. En el MVP no hay permiso por obra: quien tiene el rol ve todas (non-goal de TKT-006).
- **Fuente que no es `REAL`** (esc. 6). Si `cifra_parcial` es verdadero, aviso de cifra parcial que **nombra las fuentes que faltan o están simuladas**; la cifra nunca se presenta como costo real completo. Con fuentes `SIN_DATOS` es lo que verá producción hasta el sprint 8 —la nómina, hasta el 9—, porque allí el adaptador simulado no arranca y destajo, nómina y avance se declaran `SIN_DATOS`.
- **Movimiento sin documento navegable.** Los renglones de destajo simulado no enlazan a nada y lo dicen; un enlace roto sería peor que ninguno.
- **Consulta lenta.** `RNF-15` exige menos de 2 segundos; si la respuesta tarda, la tabla muestra su esqueleto de carga, **nunca** filas en cero.

---

## 11. Fase 2 · pantallas pendientes

Se esbozan en la fase 2, con las historias que las piden. Se listan aquí para que el armazón de la fase 1 les deje sitio.

| Pantalla | Rol | Historias | Qué tiene que resolver |
|---|---|---|---|
| **Captura de avance en teléfono** | Residente de obra | HDU-008 · esc. 18 a 25 | Área, etapa y cuadrilla precargadas; captura de `m2_real` —`m2_contrato` viene del alcance y no se edita (regla 13 de `CLAUDE.md`)—; fotos desde la cámara que suben **después** del avance; funciona sin conexión. Un duplicado de área, etapa, cuadrilla y semana —la de destajo, de jueves a miércoles, identificada por su jueves de corte (`PA-19`)— se rechaza con la acción de pedir su rechazo al Director de Proyectos, nunca con *corregir el existente* |
| **Validación del Director de Proyectos** | Director de Proyectos | HDU-008 | Bandeja de mediciones `CAPTURADO` con evidencia; validar o rechazar con motivo; corrección de `m2_contrato` solo por él y con motivo; nadie valida su propia medición. Que la foto **no** sea condición para validar es `PA-14`, abierto |
| **Nómina semanal** | Administración | HDU-009 | Semana de viernes a jueves; días derivados de las jornadas; créditos y pagos agrupados; rechazo si la cuadrilla ya cobró por destajo esa semana (`RN-22`), **solo de esa cuadrilla**, con el resto de la nómina calculada (`PA-20`). Semana laboral de 6 días como divisor y máximo, descuentos por antigüedad del adeudo cuando el bruto no alcanza, y `PAGADA` la marca Administración (`PA-22`) |
| **Expediente de obra** | Todos los que consultan la obra | F8.5 · TKT-067 | Todos los adjuntos de la obra en una vista; anulación con motivo, **sin borrado** |
| **Indicador de cola sin conexión** | Residente de obra · Almacén | TKT-063 · `RNF-18` | Conectado o no, elementos en cola por estado —pendiente, sincronizado, en conflicto—, antigüedad de los datos mostrados y el conflicto que detuvo la cola |

Boceto mínimo del indicador, que vivirá en la barra superior del armazón:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ ○ Sin conexión · 3 en cola · datos de hace 2 h      [ Ver cola ]         │
│ ● Conectado · sincronizando 2 de 3                                       │
│ ! 1 en conflicto: R-4588 excede lo ordenado (RN-07) · cola detenida      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Cómo se usan

**Son contexto, no especificación.** El agente que implementa una interfaz recibe la pantalla correspondiente junto con el ticket y la historia:

| Pantalla | Ticket que la implementa |
|---|---|
| 1 · Inicio de sesión · 2 · Armazón · 6 · Pantalla de bloqueo | TKT-008 |
| 3 · Importación · 4 · Congelado y presupuesto de control | TKT-018 |
| 5 · Disponible y requisición | TKT-024 |
| 7 · Bandeja de autorizaciones | TKT-028 |
| 8 · Emisión de orden de compra | TKT-032 |
| 9 · Recepción de material | TKT-038 |
| 10 · Semáforo y desglose | TKT-041 |

**Qué fijan.** Qué datos aparecen, en qué orden, qué acciones hay, y **qué ve el usuario cuando el servidor dice que no**. Si una pantalla implementada no tiene uno de los estados de rechazo de aquí, está incompleta, igual que un test que solo cubre el camino feliz.

**Qué no fijan.** Estilo, colores, tipografía, iconos, espaciado ni el componente concreto. Eso lo da [shadcn/ui](06-stack-tecnologico.md#51-composición), cuyos componentes se copian al repositorio; la pantalla de bloqueo es un componente propio del dominio construido con ellos, no un diálogo genérico.

**Qué manda sobre ellos.** Los escenarios de [historias de usuario](04-historias-usuario.md), el contrato de error de la [arquitectura §7.3](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio) y el OpenAPI. Los tipos del cliente se generan del OpenAPI ([stack §5.4](06-stack-tecnologico.md#54-el-contrato-de-api-no-se-replica-a-mano)); si un nombre de campo de estos bocetos no coincide con el generado, gana el generado.

---

## 13. Supuestos de este documento

Todo lo marcado **(asumido)** arriba, reunido para revisarlo de una vez:

| Pantalla | Supuesto o pregunta | Quién lo cierra |
|---|---|---|
| 3 | Progreso del análisis por consulta periódica, sin canal de empuje | TKT-018 |
| 4 | *Guardar topes* envía un `PUT` por fila, y una fila que falla no deshace las demás | TKT-018 |
| 9 | La captura rechazada por `RN-07` se conserva en el dispositivo hasta reenviarla o descartarla, sin borrador en el servidor | TKT-038 |
| 10 | El corte entre amarillo y rojo es `obra.umbral_alerta_pct`, sobre la desviación relativa: el cliente dio los tres colores, no el corte ([PRD §10](01-descripcion-producto.md#supuestos-asumidos-sin-bloqueo)) | Dirección General, sin bloqueo |

`PA-16`, `PA-17` y `PA-18` se respondieron el 2026-10-17 y ya no figuran aquí: autorizar un excedente de recepción habilita reenviar la entrada, que lo suma marcado como excedente (pantallas 7 y 9); una entrada de una orden `CERRADA` no se corrige (pantalla 9); y el semáforo tiene tres colores (pantalla 10).

**Lo que el borrador OpenAPI ya cerró.** Este documento se empezó a escribir antes de que existiera [`docs/api/openapi.yaml`](api/openapi.yaml) y se alineó con él al terminar. Dejaron de ser supuestos: el `429` con `reintentar_en_s` y misma respuesta por cuenta y por origen; los roles que consultan cada sección (`x-roles`); los nombres de las claves de `detalle` y de `acciones`; que `RN-03` ofrezca `VER_SOLICITUD_AUTORIZACION`, un `GET` a la solicitud ya creada, y `RN-07` `SOLICITAR_AUTORIZACION`, un `POST` que la crea; la forma de los `409` sin regla (`tipo` `CONFLICTO` con `codigo`), que incluye la obra sin línea base o sin tope; que la fecha comprometida nazca al emitir la orden, y el color del semáforo, que llega calculado en `estado`.
