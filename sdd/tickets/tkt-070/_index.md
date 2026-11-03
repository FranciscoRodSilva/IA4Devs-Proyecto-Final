# TKT-070 · Despliegue de prueba en una VPS con Caddy y PostgreSQL

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (Definition of Done de Documentación, por decisión de la persona dueña) |
| **Historia** | Épica 0 · Fundación, sin historia de usuario. Va en el bloque «Endurecimiento y operación» de `docs/05-tickets-trabajo.md` |
| **Épica / sprint** | Sin sprint asignado |
| **Puntos** | Ninguno de historia. Talla por estimar en el diseño |
| **Reglas implicadas** | Ninguna `RN-xx`. Requisitos `RNF-07` y `RNF-09`; declara que no cumple `RNF-10` ni `RNF-11` |
| **Invariantes en riesgo** | 10, 14, 20 y 21, por los permisos que reproduce la migración en la VPS |
| **Módulos en alcance** | Ninguno de `backend/cimenta/`. Archivos de despliegue y documentación |
| **Capas en alcance** | Infraestructura de despliegue y documentación. Ni dominio, ni aplicación, ni api, ni frontend |
| **Depende de** | TKT-003 (estado: archivado) |
| **Rama** | `tkt-070-despliegue-de-prueba-en-vps` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-02 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-02 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada con 13 criterios `[M]` y 5 `[S]`; la persona dueña validó el Must |
| 2026-11-02 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño de 15 filas escrito; la revisión de impacto lo devolvió como incompleto y se corrigió en el mismo cambio |
| 2026-11-02 | `DISEÑO PENDIENTE REVISIÓN` | `DISEÑO PENDIENTE REVISIÓN` | Revisión previa a ejecutar | Se ejecutaron en local 14 de los 15 experimentos locales; uno refutó el diseño (Caddy con el usuario 1000 no escribe en `/data`) y se corrigió |
| 2026-11-02 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | Aprobación humana | La persona dueña aprobó el diseño corregido |
| 2026-11-03 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas A y V cerradas; repo documentado; `impl.md` con evidencia VPS; auditorías en `/sdd-revisar` |
| 2026-11-03 | `EN REVISIÓN` | `REQUIERE CAMBIOS` | `/sdd-revisar` | Auditorías: F001 guía `sed` (Mayor); script y docs con hallazgos; ciclo 1 aplicó F001 guía, scp, `05-tickets`, parseo 5432 y `.dockerignore` |
| 2026-11-03 | `REQUIERE CAMBIOS` | `EN REVISIÓN` | Corrección ciclo 2 | Guía §3/§7/§10, placeholders, acentos, design/ADR/spec alineados, tests ampliados, LF, duckdns@v0.4.0 |
| 2026-11-03 | `EN REVISIÓN` | `REQUIERE CAMBIOS` | `/sdd-revisar` reauditoría | Suite verde; 4/5 auditores APROBADO; codigo Menores F005–F010 |
| 2026-11-03 | `REQUIERE CAMBIOS` | `EN REVISIÓN` | Corrección ciclo 3 código | F004–F008; `.env.prod`/`.env.test` con 3 contraseñas distintas (confirmado) |
| 2026-11-03 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` ciclo 3 | Suite verde; 5/5 auditores APROBADO |
| 2026-11-03 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución; PR abierto; archivado al fusionarse (número en comentario de registro del PR) |

## Decisiones registradas

Recortes de alcance aprobados, escalaciones resueltas, excepciones autorizadas. Cada una con fecha y quién decidió.

- 2026-11-02 · La persona dueña confirmó el presupuesto: un mes de VPS a 4.07 USD.
- 2026-11-02 · La persona dueña decidió que la migración se aplica por túnel SSH desde su equipo, con cada base publicada solo en `127.0.0.1` de la VPS.
- 2026-11-02 · La persona dueña decidió que el tipo «Fundación», sin Definition of Done en `convenciones.md` §6, usa la de Documentación.
- 2026-11-02 · La persona dueña aceptó como supuestos que el rol de migración sea superusuario en la VPS y que la fila genérica «Constructora Celsius» de la migración 0008 no cuenta como dato real.
- 2026-11-02 · La persona dueña validó el Must propuesto.
- 2026-11-02 · La persona dueña decidió que el destino de despliegue final lo decide TKT-058 en su diseño, y se corrigió el non-goal de TKT-058 que decía «se decide aparte».
- 2026-11-02 · La persona dueña decidió que `PA-T5` de TKT-057 queda en TKT-058, y que TKT-070 solo la cita.
- 2026-11-02 · En el gate del diseño, la persona dueña autorizó corregir `CA-7` y `CA-8` en la spec, confirmó las opciones descartadas del ADR, aprobó editar los recuentos de ADR en `CLAUDE.md`, `README.md` y `llms.txt` y añadir una nota en `conv-docker`, y decidió mantener el ticket entero pese a las ~790 líneas.
- 2026-11-03 · La persona dueña eligió la **Alternativa A**: ACME **DNS-01** con DuckDNS, imagen Caddy con `caddy-dns/duckdns`, puertos publicados **10004/10005** (no 80/443 estándar), redirección explícita a `:10005` en el Caddyfile (sin `https_port` global) y `remoto --http-port 10004 --https-port 10005`. Enmienda de `CA-3`, `CA-4` y del diseño acordada al preparar la VPS.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- Respaldo diario con `pg_dump` hacia un bucket externo, pospuesto por decisión de la persona dueña. Mientras no exista, el único respaldo es el del proveedor, cada cuatro semanas.
- Despliegue automático desde el pipeline, cuando exista la imagen de TKT-058.
- Resolución de `PA-T5` de TKT-057, el origen del cliente detrás de Caddy, antes de poner una aplicación tras el proxy. Ya está remitida a TKT-058.
