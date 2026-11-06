# TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR · entrega TKT-059a

Paraguas con cinco entregas que se fusionan en este orden: TKT-059a, TKT-059b, TKT-059c, TKT-059d y TKT-059e. `ARCHIVADO` solo al cerrar TKT-059e.

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | «Épica 0 · Fundación»; sirve a [[HDU-001]] escenarios 24 a 26 |
| **Épica / sprint** | Épica 0 · Fundación, sprint 2 |
| **Puntos** | Talla M en el backlog; el diseño propone la partición |
| **Reglas implicadas** | Ninguna `RN-xx`. `RNF-06`, `RNF-07`, `RNF-17`, `RNF-19`, `PA-15` |
| **Invariantes en riesgo** | 23, 24, 25 y 26; arranque sin base (`CA-R4` de TKT-006, TC-51 de TKT-057, ADR-037 §5) |
| **Módulos en alcance** | `archivos`; `identidad` y `auditoria` por su interfaz; `servidor/`, Compose y pipeline |
| **Capas en alcance** | dominio · aplicación · api · infraestructura (migración, adaptador `boto3`) · servidor y CI. Sin frontend |
| **Depende de** | TKT-002, TKT-003, TKT-005, TKT-007 y TKT-015b (todas ARCHIVADO) |
| **Rama** | Una por entrega, con los nombres que fija `design.md`: `tkt-059a-esquema-y-dominio`, `tkt-059b-adaptadores`, `tkt-059c-ajustes-y-alta`, `tkt-059d-confirmacion` y `tkt-059e-lecturas-y-barrido` |
| **Ejecución** | `/sdd-ejecutar TKT-059a` ejecuta las filas 0 a 4 y se detiene tras la fila 4; cada entrega siguiente, con su propio `/sdd-ejecutar TKT-059x`. `impl.md` es uno solo, con una sección por entrega |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-05 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-05 |
| Impl | `impl.md` (lo escribe `/sdd-ejecutar`) | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-05 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must M1 a M9 validado por la persona dueña. 14 criterios `[M]`, 8 con escenario de rechazo, uno de regresión. Once decisiones de la persona dueña en el intake y una en la pasada adversarial. INVEST con un fallo (S, resuelto por la partición en el diseño) y dos reservas (V y E). Dos experimentos sin verificar: la suma SHA-256 firmada en MinIO y las lecturas por rango del `.xlsx` |
| 2026-11-05 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): experimentos contra MinIO real antes de construir (`E-0` a `E-4`), un puerto y un adaptador `boto3`, confirmación con la fila bloqueada y lecturas por rango acotadas, barrido sin almacén. Dieciocho filas, ~1,345 líneas de producción; condición de parada 3, con partición propuesta en cinco entregas (`P-2`). `revisor-impacto`: sin frontera cruzada (`lint-imports`, 16 contratos en verde), diseño incompleto; ocho omisiones incorporadas, entre ellas el `up -d db` de la VPS de prueba. Dos objeciones del orquestador incorporadas (suma perdida por `copy_object`, `.env` local anterior). Catorce preguntas (P-1 a P-14) esperan a la persona dueña |
| 2026-11-05 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones de P-1 a P-14 (ver «Decisiones registradas»). Cinco entregas (`P-2`). Siguiente: `/sdd-ejecutar TKT-059a` (filas 0 a 4), que empieza por los experimentos `E-0` a `E-4` |
| 2026-11-06 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | revisión independiente | Correcciones de ejecución en `design.md` sin reabrir decisiones del gate: filas 1 y 12 partidas (1a, 1b, 12a, 12b), agentes según sus definiciones, `interfaz.py` desde la fila 8, `evaluar_previa` sin `datetime` (`Ordenable`), vencimiento del bloqueo como `CONCURRENCIA`, `TC-25b` para los mutantes del detector, comandos para PowerShell, `pip-audit` en cada cierre y altas dentro del `TestClient` |
## Decisiones registradas

Todas de la persona dueña, el 2026-11-05, durante `/sdd-definir`.

- **Costos:** sin R2 en este ticket; pruebas contra MinIO. La contratación se decide en TKT-058 o TKT-070; si no hay presupuesto, producción usa MinIO en el servidor.
- **Partición:** una sola spec; el diseño propone cómo partir por tamaño.
- **Arranque:** variables del almacén obligatorias solo con base configurada.
- **Barrido:** solo marca `CADUCADO`; no toca el almacén ni la bitácora; el objeto huérfano lo recoge una regla de ciclo de vida del bucket.
- **Duraciones por omisión:** URL de subida 15 minutos, de lectura 5 minutos, umbral del barrido 24 horas, configurables.
- **Roles:** confirma solo el Director de Proyectos que subió; otro, `403` `NO_ES_SOLICITANTE` asentado `DENEGAR`. Leen y descargan Dirección General y Director de Proyectos.
- **Lista blanca:** solo `.xlsx` entre las hojas de cálculo; la interfaz de alta recibe el tipo declarado para elegir el límite, sin guardarlo.
- **Hash:** la spec exige que el almacén verifique la suma firmada; el diseño lo comprueba primero y, si falla, se escala.
- **Códigos:** `ARCHIVO_NO_SUBIDO`, `ARCHIVO_CADUCADO` y `ARCHIVO_NO_DISPONIBLE` con los disparadores de `CA-7` y `CA-9`; `CADUCADO` entra en `EstadoArchivo`.
- **Bitácora y permisos:** solo se asientan la confirmación y las denegaciones; el rol de aplicación no tiene `DELETE` sobre `archivo`.
- **Dueños:** TKT-059 conecta la lectura del contenido en `fabrica.py` y es dueño de los tests de HDU-001 esc. 25 y 26; el 24 es de TKT-018.
- **Pasada adversarial:** un `PENDIENTE` vencido que el barrido no alcanzó se trata como caducado al confirmar.
- **Gate de diseño (2026-11-05, persona dueña):** aprobadas las recomendaciones de `design.md` para P-1 a P-14. P-1: la migración toma el siguiente número libre al ejecutar y quien fusione segundo, entre este ticket y TKT-017, renumera. P-2: cinco entregas, 059a (filas 0 a 4), 059b (5 a 7), 059c (8 a 10), 059d (11 a 13) y 059e (14 a 17); cada mutante corre en la entrega del código que muta. P-3: `CIMENTA_ALMACEN_ORIGEN` es a la vez el `endpoint_url` y el origen de la política de contenido. P-4: los límites son en MiB. P-5 y P-13: `nombres_de_usuarios` y una sola clase `UsuarioResumen` en `identidad`, publicadas por quien llegue primero entre la fila 11 y TKT-017b1; el otro las importa. P-6: el bucket local lo crea `herramientas.almacen_local`. P-7: sin MinIO en el trabajo `humo`. P-8: ADR nuevo en 059b; el conteo de ADR pasa a 40 o 41 según el orden con TKT-017, en `CLAUDE.md`, `README.md` y `llms.txt`. P-9: un XML con `DOCTYPE` se rechaza. P-10: un archivo `ANULADO` responde `ESTADO_NO_PERMITE_OPERACION` al confirmar y `ARCHIVO_NO_DISPONIBLE` al descargar. P-11: un objeto sin suma es `ARCHIVO_HASH_DISTINTO`. P-12: el tipo declarado se compara exacto, sin alias. P-14: MinIO detrás del perfil `almacen` de Compose.
## Tickets futuros sugeridos

- Configurar la regla de ciclo de vida del bucket para los objetos de `PENDIENTE` caducados, en TKT-058 o TKT-070 (`PA-T59.3`).
- Verificar la suma SHA-256 firmada contra R2 antes de usarlo en producción (`PA-T59.7`).
