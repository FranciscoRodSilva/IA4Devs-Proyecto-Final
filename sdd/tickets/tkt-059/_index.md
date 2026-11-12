# TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR · entrega TKT-059e

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
| **Rama** | Una sola para todo el ticket, `tkt-059-archivos-minimo`, que acumula las cinco entregas (regla vigente de `CLAUDE.md`; los nombres por entrega que fijaba `design.md` quedan sin efecto) |
| **Ejecución** | `/sdd-ejecutar TKT-059a` ejecuta las filas 0 a 4 y se detiene tras la fila 4; cada entrega siguiente, con su propio `/sdd-ejecutar TKT-059x`. `impl.md` es uno solo, con una sección por entrega |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-05 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-05 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Secciones de las entregas 059a, 059b, 059c y 059d escritas; las demás entregas añaden la suya |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-05 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must M1 a M9 validado por la persona dueña. 14 criterios `[M]`, 8 con escenario de rechazo, uno de regresión. Once decisiones de la persona dueña en el intake y una en la pasada adversarial. INVEST con un fallo (S, resuelto por la partición en el diseño) y dos reservas (V y E). Dos experimentos sin verificar: la suma SHA-256 firmada en MinIO y las lecturas por rango del `.xlsx` |
| 2026-11-05 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): experimentos contra MinIO real antes de construir (`E-0` a `E-4`), un puerto y un adaptador `boto3`, confirmación con la fila bloqueada y lecturas por rango acotadas, barrido sin almacén. Dieciocho filas, ~1,345 líneas de producción; condición de parada 3, con partición propuesta en cinco entregas (`P-2`). `revisor-impacto`: sin frontera cruzada (`lint-imports`, 16 contratos en verde), diseño incompleto; ocho omisiones incorporadas, entre ellas el `up -d db` de la VPS de prueba. Dos objeciones del orquestador incorporadas (suma perdida por `copy_object`, `.env` local anterior). Catorce preguntas (P-1 a P-14) esperan a la persona dueña |
| 2026-11-05 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones de P-1 a P-14 (ver «Decisiones registradas»). Cinco entregas (`P-2`). Siguiente: `/sdd-ejecutar TKT-059a` (filas 0 a 4), que empieza por los experimentos `E-0` a `E-4` |
| 2026-11-06 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | revisión independiente | Correcciones de ejecución en `design.md` sin reabrir decisiones del gate: filas 1 y 12 partidas (1a, 1b, 12a, 12b), agentes según sus definiciones, `interfaz.py` desde la fila 8, `evaluar_previa` sin `datetime` (`Ordenable`), vencimiento del bloqueo como `CONCURRENCIA`, `TC-25b` para los mutantes del detector, comandos para PowerShell, `pip-audit` en cada cierre y altas dentro del `TestClient` |
| 2026-11-06 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | persona dueña | Tres decisiones nuevas aplicadas en `spec.md` y `design.md`: destino de producción en MinIO de la VPS (TKT-073, sin R2; `PA-T59.1` actualizada y `PA-T59.7` sin efecto), dos variables del almacén (endpoint interno y origen público, sustituye a P-3) con un criterio nuevo en `CA-2`, y CORS por resultado (`CA-14`, experimento `E-5`, mutante `M-20`). Total ~1,375 líneas, misma partición. Pregunta nueva `P-15` (variable del origen de la SPA) para la persona dueña |
| 2026-11-11 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` (entrega 059a) | `/sdd-ejecutar TKT-059a` | Filas 0 a 4 ejecutadas. `E-0` falló con `minio/minio` (ya no se descarga) y la persona dueña eligió `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`; `E-4` obligó a un segundo archivo de Compose (`compose.almacen.yaml`), también decisión suya; `E-5` cayó en el caso (c2). Migración `0012` (la cabeza era `0011`). Suite `2905 passed, 26 skipped`; ocho mutantes caídos; `pip-audit` limpio. `auditor-sql` `APROBADO`; `auditor-arquitectura` `REQUIERE CAMBIOS` por un hallazgo menor (falta de `impl.md`), resuelto y en reauditoría. Alcance de CORS aclarado en `CA-14` el 2026-11-11 por la persona dueña (ver «Alcance real» en `spec.md`). Siguiente: `/sdd-revisar TKT-059` para esta entrega |
| 2026-11-11 | `EN REVISIÓN` (entrega 059a) | `LISTO PARA EJECUTAR · TKT-059b` | `/sdd-revisar TKT-059` | Entrega 059a revisada y acumulada en la rama `tkt-059-archivos-minimo`, sin PR. Dos ciclos de corrección: `auditor-codigo` `APROBADO`, `auditor-seguridad` `APROBADO`, `auditor-sql` `APROBADO`, `auditor-arquitectura` `APROBADO` y `auditor-docs` `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` (N-1, N-2, N-3, N-4, F007 y F009, solo redacción; comunicados a la persona dueña). Suite `2916 passed, 26 skipped`. ADR `20261111-almacen-local-en-compose-aparte.md` escrito a petición de la persona dueña (42 ADR). Deuda aceptada: `UPDATE` sobre toda la tabla `archivo` (`O-01`). Siguiente: `/sdd-ejecutar TKT-059b` (filas 5 a 7) |
| 2026-11-11 | `LISTO PARA EJECUTAR` (entrega 059b) | `EN REVISIÓN` (entrega 059b) | `/sdd-ejecutar TKT-059b` | Filas 5 a 7 ejecutadas con TDD. Puerto y adaptador `AlmacenS3` con dos clientes `boto3`; detector del tipo por los bytes con lecturas por rango y firma propia de HEIC. Ajuste: `UrlFirmada` vive en `dominio/` por el contrato de capas. Suite `2959 passed, 26 skipped` más cinco tests añadidos después (46 pasan en los dos archivos de la entrega); `pip-audit` limpio. Mutación: `M-06`, `M-07`, `M-08`, `M-16` y `M-21` caen; una laguna (`M-08c`) y tres huecos de la auditoría cerrados con tests. `auditor-arquitectura` `APROBADO` tras un ciclo. ADR nuevo de la confirmación (43 ADR). Decisión de la persona dueña (2026-11-11): se deja la regla `ftyp` del diseño, que clasifica `avif`, `qt` y `3gp` como `video/mp4`. Siguiente: `/sdd-revisar TKT-059` |

| 2026-11-11 | `EN REVISIÓN` (entrega 059b) | `LISTO PARA EJECUTAR · TKT-059c` | `/sdd-revisar TKT-059` | Entrega 059b revisada y acumulada en la rama `tkt-059-archivos-minimo`, sin PR. Dos ciclos de corrección: `auditor-arquitectura`, `auditor-codigo` y `auditor-seguridad` `APROBADO`; `auditor-docs` `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` (`N001` a `N006`, `O-N1` y `O-N2`, solo redacción; comunicados a la persona dueña). Se cerraron un fallo real (`LookupError` o `ValueError` con una codificación XML desconocida), la amplificación de memoria (`MAXIMO_PARTE` baja de 1 MiB a 256 KiB), el fallo abierto de la lista blanca (RIFF como WebP, candidatas débiles), la entrada duplicada de `[Content_Types].xml` y el rango inválido de `leer_rango`. Suite `3019 passed, 26 skipped`. Pendientes para 059c: `O4` y `O5` de seguridad, `NUL` en `nombre_original`, `field(repr=False)` en `UrlFirmada.url`, validar la disposición en `url_lectura`. Siguiente: `/sdd-ejecutar TKT-059c` (filas 8 a 10) |

| 2026-11-12 | `LISTO PARA EJECUTAR` (entrega 059c) | `EN REVISIÓN` (entrega 059c) | `/sdd-ejecutar TKT-059c` | Filas 8 a 10 ejecutadas con TDD (se pidió también 059a y 059b, ya revisadas y acumuladas: no se reejecutaron). Diez campos de ajustes y almacén obligatorio con base, `ContextoArchivos` y composición perezosa en la fábrica, repositorio de `archivo` y `registrar_archivo`. Decisión de la persona dueña: `NUL` y sustitutos Unicode en `nombre_original` se rechazan con `FORMATO` en `evaluar_declaracion` (hallazgo F001). Suite `3162 passed, 26 skipped`; `M-05b`, `X1` y `X2` caen; `pip-audit` limpio. `auditor-arquitectura` `APROBADO` tras un ciclo. Pendientes para 059d o 059e: `O4`, `O5` y `Body.read(fin - inicio + 1)`. Siguiente: `/sdd-revisar TKT-059` |

| 2026-11-12 | `EN REVISIÓN` (entrega 059c) | `LISTO PARA EJECUTAR · TKT-059d` | `/sdd-revisar TKT-059` | Entrega 059c revisada y acumulada en la rama `tkt-059-archivos-minimo`, sin PR. Un ciclo de corrección: `auditor-arquitectura`, `auditor-codigo` y `auditor-seguridad` `APROBADO`; `auditor-docs` `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` (`F001` a `F006`, solo redacción y cifras; comunicados a la persona dueña). Decisión de la persona dueña: `registrar_archivo` rechaza con `ValueError` un `referencia_tipo` fuera de los seis valores o distinto de `OBRA` sin `referencia_id`. Suite `3162 passed, 26 skipped`. Pendientes: `O4`, `O5` y `Body.read(fin - inicio + 1)` de 059b sin decisión de aplazamiento registrada; para TKT-018, el DTO con `Literal` de `referencia_tipo` y la verificación de rol y obra. Siguiente: `/sdd-ejecutar TKT-059d` (filas 11 a 13) |

| 2026-11-12 | `LISTO PARA EJECUTAR` (entrega 059d) | `EN REVISIÓN` (entrega 059d) | `/sdd-ejecutar TKT-059d` | Filas 11 a 13 ejecutadas con TDD. La fila 11 no necesitó código: `nombres_de_usuarios` y `UsuarioResumen` ya los había publicado TKT-017b1. `confirmar_archivo` con sus once pasos, la ruta `POST /api/v1/archivos/{archivo_id}/confirmacion`, el orden A de `E-1` (g1) y el cambio del borrador OpenAPI de 059d (**señalar a quien apruebe el PR: toca `docs/api/openapi.yaml`**). Suite `3201 passed, 26 skipped`; los cinco mutantes de la fila 13 y treinta de la fila 12b caen; `pip-audit` limpio. `auditor-arquitectura` `APROBADO` en un ciclo. Siguiente: `/sdd-revisar TKT-059` |

| 2026-11-12 | `EN REVISIÓN` (entrega 059d) | `LISTO PARA EJECUTAR · TKT-059e` | `/sdd-revisar TKT-059` | Entrega 059d revisada y acumulada en la rama `tkt-059-archivos-minimo`, sin PR. Dos ciclos de corrección: `auditor-arquitectura` y `auditor-seguridad` `APROBADO`; `auditor-codigo` y `auditor-docs` `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` (`F005`, `F007` y `F001` a `F003` de docs, de redacción y de código de pruebas; comunicados a la persona dueña). Se cerraron dos huecos de cobertura Mayores (la rama `57014` y `referencia_id` nulo), la ruta de fallo de la denegación y la deriva del `Literal` de `referencia_tipo`. Suite `3206 passed, 26 skipped`. **Señal para quien apruebe el PR: esta entrega modifica `docs/api/openapi.yaml`.** Pendientes para 059e: en `url_lectura`, fijar siempre `ResponseContentType` y la disposición (`O-4` de seguridad); `O4`, `O5` y `Body.read(fin - inicio + 1)` de 059b siguen sin decisión de aplazamiento registrada. Siguiente: `/sdd-ejecutar TKT-059e` (filas 14 a 17) |

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
- **Gate de diseño (2026-11-05, persona dueña):** aprobadas las recomendaciones de `design.md` para P-1 a P-14. P-1: la migración toma el siguiente número libre al ejecutar y quien fusione segundo, entre este ticket y TKT-017, renumera. P-2: cinco entregas, 059a (filas 0 a 4), 059b (5 a 7), 059c (8 a 10), 059d (11 a 13) y 059e (14 a 17); cada mutante corre en la entrega del código que muta. P-3: `CIMENTA_ALMACEN_ORIGEN` es a la vez el `endpoint_url` y el origen de la política de contenido. P-4: los límites son en MiB. P-5 y P-13: `nombres_de_usuarios` y una sola clase `UsuarioResumen` en `identidad`, publicadas por quien llegue primero entre la fila 11 y TKT-017b1; el otro las importa. P-6: el bucket local lo crea `herramientas.almacen_local`. P-7: sin MinIO en el trabajo `humo`. P-8: ADR nuevo en 059b; el conteo de ADR pasa a 40 o 41 según el orden con TKT-017, en `CLAUDE.md`, `README.md` y `llms.txt`. P-9: un XML con `DOCTYPE` se rechaza. P-10: un archivo `ANULADO` responde `ESTADO_NO_PERMITE_OPERACION` al confirmar y `ARCHIVO_NO_DISPONIBLE` al descargar. P-11: un objeto sin suma es `ARCHIVO_HASH_DISTINTO`. P-12: el tipo declarado se compara exacto, sin alias. P-14: MinIO detrás del perfil `almacen` de Compose. **Superada el 2026-11-11** por E-4: `compose.almacen.yaml` sin perfil (ver `impl.md`).
- **Destino de producción (2026-11-06, persona dueña):** los archivos vivirán en MinIO autoalojado en la VPS de Database Mart (TKT-070), no en R2. Desplegarlo —nombre propio detrás de Caddy, bucket por entorno, CORS, respaldo propio (`RNF-19`), regla de ciclo de vida y el ADR que reemplaza la elección de destino de ADR-016— es TKT-073, no este ticket. `PA-T59.7` (la suma en R2) deja de aplicar. TKT-059 solo añade a ADR-016 un aviso que remite a TKT-073.
- **Dos variables (2026-11-06, persona dueña; sustituye a P-3):** `CIMENTA_ALMACEN_ENDPOINT`, interna y opcional (si falta, vale el origen), para las operaciones del servidor; `CIMENTA_ALMACEN_ORIGEN`, pública, con la que se firman las URL y que entra en la política de contenido. El adaptador usa dos clientes `boto3`.
- **CORS (2026-11-06, persona dueña):** el almacén acepta el preflight y el `PUT` firmado solo desde el origen de la SPA (`CA-14`); el experimento `E-5` decide si se aplica por bucket o por la variable global de MinIO. El origen de la SPA y su variable quedan como `P-15` del diseño, con recomendación `CIMENTA_SPA_ORIGEN`.
- **P-15 (2026-11-06, persona dueña):** el origen de la SPA para CORS es `CIMENTA_SPA_ORIGEN`, activa en `.env.example` como `http://localhost:5173`. Solo la lee la configuración de CORS (herramienta del bucket o Compose, según `E-5`), no `AjustesServidor`. En la VPS la fija TKT-073.

## Tickets futuros sugeridos

- TKT-073 · MinIO autoalojado en la VPS: nombre público detrás de Caddy, bucket por entorno, CORS con el origen público de la SPA, respaldo propio, la regla de ciclo de vida para los objetos de `PENDIENTE` caducados (`PA-T59.3`), las variables `CIMENTA_ALMACEN_*` de cada entorno y el ADR que reemplaza la elección de destino de ADR-016. Ya está en [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md) desde el 2026-11-06.
