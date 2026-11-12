# TKT-018b · Flujo de importación del presupuesto

> Hub del ticket. Se lee **primero**, siempre.

## Estado

SPEC PENDIENTE

La ejecución queda bloqueada hasta que TKT-059 entregue, como mínimo, el alta del archivo, su confirmación y el lector del contenido (entregas 059c a 059e).

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenarios 4 a 13, 21 y 24 a 29 |
| **Épica / sprint** | HDU-001 · Obra y línea base, fase 1 |
| **Puntos** | Talla M en el backlog (parte de TKT-018 partido en TKT-018a y TKT-018b); el diseño debe partirlo en entregas |
| **Reglas implicadas** | `RN-01`, `RN-02`, `RN-24`, `RNF-06`, `RNF-17`, `RNF-19` |
| **Invariantes en riesgo** | `INV-05`, `INV-14`, `INV-26` |
| **Módulos en alcance** | `presupuesto` (casos de uso, rutas, lectura de la previsualización), consumo de la interfaz de `archivos`, frontend `modulos/presupuesto` |
| **Capas en alcance** | dominio (resumen, si aplica) · aplicación · api · infraestructura · frontend |
| **Criterios `[M]`** | `CA-1` a `CA-24`, `CA-R1` a `CA-R4`; `S1` a `S3` son *Should* |
| **Depende de** | TKT-018a (ARCHIVADO), TKT-017 (ARCHIVADO), TKT-012a (ARCHIVADO), TKT-059 (`LISTO PARA EJECUTAR · entrega TKT-059a`, sin código) |
| **Rama** | `tkt-018b-importacion-presupuesto` (una sola por ticket, también si el diseño lo parte en entregas) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-11 |
| Design | `design.md` (se enlaza en `/sdd-disenar`) | `/sdd-disenar` | Pendiente |
| Impl | `impl.md` (se enlaza en `/sdd-ejecutar`) | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-11 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada tras el análisis de `analista-dominio`. Must validado por la persona dueña: las siete rutas de importación y la de tipos de partida, las pantallas 3a a 3c, los escenarios 4 a 13, 21 y 24 a 29 y la deuda del `NUL` de `motivo_reemplazo`. 24 criterios `[M]` (tras descartar el de `Q-7`) más cuatro de regresión y tres *Should*; rechazos de formato, obra sin admisión, archivo no disponible o rechazado, importación con errores, tipos sin asignar, fallo a mitad, reemplazo sin confirmar, motivo con `NUL`, descarte y permisos. Siete objeciones adversariales incorporadas. INVEST con un fallo (tamaño) y dos reservas (TKT-059 sin ejecutar y huecos de contrato). Catorce preguntas o supuestos abiertos |

## Decisiones registradas

- **2026-11-11 · persona dueña.** Must completo: backend y frontend en un ticket, con `S1` a `S3` como *Should*.
- **2026-11-11 · persona dueña.** Los huecos del OpenAPI (nombres de partida sin publicar, `por_tipo_partida` antes de asignar, resumen sin dueño) se registran como hallazgo en la spec y se corrigen en `/sdd-disenar` con su revisión; las operaciones pasan a `TKT-018b` (`DOC-10` de TKT-018a).
- **2026-11-11 · persona dueña.** TKT-059 es dueño de los tests de HDU-001 esc. 25 y 26; TKT-018b prueba solo la consecuencia en la importación.
- **2026-11-11 · persona dueña.** «Exportar errores» es *Should* y se hace como CSV en el cliente; el progreso se consulta cada 3 segundos `(asumido)`.
- **2026-11-11 · persona dueña.** `Q-7`: una obra con línea base `CONGELADA` no reimporta (`RN-01`). Se descarta el criterio de ver un borrador más nuevo que la congelada y la spec queda con `CA-1` a `CA-24`.
- **2026-11-11 · persona dueña.** Sin servicio de pago: el almacén de objetos es MinIO propio (TKT-059, TKT-073).

## Tickets futuros sugeridos

- **Tablas «Ver conceptos» y «Ver explosión por tipo de partida»** del boceto 4a, ya sugeridas por TKT-018a.
- **Ruta de exportación de errores en el servidor**, si el CSV del cliente no basta.
- **Publicar `crear_obra` en la interfaz de `presupuesto`** y migrar la semilla de TKT-018a (`F001`).
- **Corregir HDU-001 esc. 4** para que diga `RECIBIDO` en vez de `ANALIZANDO` (hallazgo D6), y el esc. 13 de `descartar_importacion` (hallazgo D4).
