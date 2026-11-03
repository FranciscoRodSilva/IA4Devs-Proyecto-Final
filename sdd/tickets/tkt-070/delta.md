# Delta · TKT-070 · Despliegue de prueba en una VPS con Caddy y PostgreSQL

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Compose de anfitrión para dos entornos `prod` y `test`: PostgreSQL 18.6, puerto de bucle local distinto por entorno, red interna y límite de memoria | `despliegue/compose.vps.yaml` | Levantar las dos bases en la VPS sin publicar PostgreSQL a Internet |
| Imagen Caddy con plugin `caddy-dns/duckdns`, Caddyfile con HTTPS en dos nombres, redirección HTTP al puerto público **10005** y respuesta fija «sin aplicación (TKT-070)» | `despliegue/caddy/` | Terminar TLS con Let's Encrypt por **DNS-01** cuando el proveedor no reenvía 80/443 estándar |
| Script SQL de comprobación de permisos e invariantes 10, 14, 20 y 21 | `despliegue/comprobar_permisos.sql` | Verificar en la VPS que la migración reprodujo las revocaciones |
| Guía de operación: copia por `scp`, `.env` en la VPS, migración por túnel SSH, comprobaciones manuales y script | `docs/despliegue-prueba-vps.md` | Repetir el despliegue de prueba sin adivinar pasos |
| ADR-034 del destino de prueba temporal (no cumple `RNF-10`/`RNF-11`) | `docs/adr/20261102-destino-de-prueba-en-vps.md` | Registrar límites y opciones descartadas |
| Herramienta CLI `anfitrion` / `remoto` con pruebas unitarias | `tools/verificar_despliegue.py`, `tools/tests/test_verificar_despliegue.py` | Automatizar `CA-S3` y parte de `CA-1`, `CA-2`, `CA-4` desde fuera de la VPS |
| Exclusión de `duckdns.org` en el verificador de enlaces | `lychee.toml` | No fallar CI por nombres dinámicos de la VPS |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Conteo de ADR | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md` | 33 → **34** |
| Stack e infraestructura | `docs/06-stack-tecnologico.md`, `docs/02-arquitectura.md` | Sin destino de prueba documentado → enlace a guía VPS y ADR-034 |
| Ficha TKT-070 en backlog | `docs/05-tickets-trabajo.md` | HTTP-01 y puertos 80/443 estándar → DNS-01 DuckDNS y reenvío **10004→80**, **10005→443**, **10003→22** |
| Convenciones Docker | `.claude/skills/conv-docker/SKILL.md` | Sin nota de VPS → destino de prueba y separación respecto a TKT-058 |
| Convenciones de documentación | `docs/convenciones.md` | — → referencia a la guía de despliegue de prueba |
| Índice de herramientas | `tools/README.md` | — → `verificar_despliegue.py` |
| `.editorconfig` | raíz | — → regla explícita para `despliegue/caddy/.dockerignore` |
| Artefactos SDD del ticket | `sdd/tickets/tkt-070/*` | Spec y design → más `impl.md`, `delta.md`, enmienda Alternativa A |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| — | — | Nada eliminado del producto; solo adiciones y documentación |

## Comportamiento observable nuevo

- Existe un **destino de prueba** en una VPS Database Mart: dos bases PostgreSQL (`prod` y `test`) con esquema en `0008 (head)`, tres roles con contraseñas distintas por entorno, y un Caddy que sirve HTTPS en `apbuildings.duckdns.org` y `apbuildings-test.duckdns.org` con certificados Let's Encrypt (DNS-01).
- Desde **fuera** de la VPS, los puertos de PostgreSQL no responden; HTTP en el puerto publicado **10004** redirige a HTTPS en **10005** sin contenido de la aplicación.
- Quien opera puede ejecutar `python tools/verificar_despliegue.py anfitrion` en la VPS y `python tools/verificar_despliegue.py remoto --http-port 10004 --https-port 10005` desde su equipo.
- **No** hay imagen ni contenedor del backend CIMENTA: la aplicación sigue siendo TKT-058.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Borrador OpenAPI / DTO / tipos generados | Ninguno | No |
| Esquema PostgreSQL del repositorio | Ninguno (se **replica** el existente en la VPS) | No |
| API HTTP de CIMENTA | Ninguna | No |
| Variables de entorno documentadas | Ejemplo DuckDNS en `despliegue/caddy/.env.example`; contraseñas de base solo en `.env` de la VPS | No para integradores del repo |

## Decisiones (ADR)

→ **ADR-034:** [`docs/adr/20261102-destino-de-prueba-en-vps.md`](../../../docs/adr/20261102-destino-de-prueba-en-vps.md) — destino temporal, sin PITR ni respaldo diario, un solo Caddy, sin aplicación.

**Enmienda operativa (2026-11-03, no ADR aparte):** Database Mart publica **10004/10005/10003** en lugar de 80/443/22 estándar. Se eligió ACME DNS-01 con DuckDNS y redirección explícita a `:10005` en el Caddyfile (evitar `https_port` global). Evidencia: certificados emitidos y `remoto` con 0 fallas en la VPS.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Caddy como usuario no root (UID 1000) no puede escribir certificados en `/data` montado desde el anfitrión con permisos restrictivos | Experimento E-L del diseño (2026-11-02) | Cualquier imagen Caddy con volumen persistente en VPS |
| `https_port` global en Caddy desplaza el listener interno de HTTPS y rompe la redirección cuando el puerto público no es 443 | Ajuste Alternativa A en VPS | Proxies con puertos publicados no estándar |
| Un `sed -i 's/REEMPLAZAR/…/' .env` sin anclar la clave deja **una sola** contraseña en las tres variables | Auditoría seguridad ciclo 1; guía corregida con `sed` por clave y `wc -l` = 3 | Cualquier guía que genere secretos en shell |
| `getpeercert()` devuelve el emisor Let's Encrypt con tuplas anidadas según OpenSSL; hay que aceptar ambas formas | Fallo inicial de `remoto` en Windows; fix en `evaluar_certificado` | Scripts TLS multiplataforma |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | TKT-070 se ejecutó en VPS antes de cerrar `impl.md` en el repo; `/sdd-revisar` bloqueó hasta reconstruir evidencia. Conviene que `/sdd-ejecutar` exija `impl.md` mínimo aunque la verificación manual sea externa. | Media |
| `herramienta` | `ruff`/`mypy` del job `backend` no cubren `tools/`; hallazgos de formato en scripts nuevos solo aparecen en revisión manual. | Baja |
| `agente` | Reauditoría de código sin el texto literal de F005–F012 del ciclo 1 obligó a reclasificar por observación; conviene que `impl.md` copie los IDs de hallazgo del informe del auditor. | Baja |
| `documentación` | La guía y `05-tickets-trabajo.md` quedaron desfasados respecto a DNS-01 hasta el ciclo 2 de corrección. | Media |
| `guardrail` | Tres ciclos de corrección (Mayor `sed`, docs/LF, Menores de código) para un ticket sin backend. | Media |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Respaldo diario `pg_dump` a bucket externo | Decisión de la persona dueña | Nuevo ticket (anotado en `_index.md`) |
| Imagen y despliegue de la aplicación | TKT-058 | TKT-058 |
| `PA-T5` origen del cliente tras Caddy | Fuera de alcance | TKT-058 |
| Despliegue automático desde CI | Won't de este ticket | Tras TKT-058 |
| Observaciones O011–O015 del verificador (timeout subprocess, test DNS más estricto) | Menor, no bloquea destino de prueba | Mejora o ticket de operación |
| Los nueve trabajos de `ci.yml` en el PR | Solo verificable en pipeline | Este PR |

## Pull request

**Título:** `TKT-070 · Despliegue de prueba en una VPS con Caddy y PostgreSQL`

**Origen:** `agent+human-review`

**Cuerpo:** ver PR abierto por `git-entrega` (qué, por qué, criterios CA-1…CA-13, verificación con `verificar_despliegue.py` y guía).

**Fusión con omisión:** si aplica, el registro va en comentario del PR tras aprobación explícita de la persona dueña (procedimiento `git-entrega`).
