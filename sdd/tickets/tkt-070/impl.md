# Impl · TKT-070 · Despliegue de prueba en una VPS con Caddy y PostgreSQL

> [← index](_index.md) | [← design](design.md) | [delta](delta.md)

## Qué se implementó

Filas **A1–A7** y **V1–V8**: artefactos en `despliegue/` (incluida imagen Caddy con DNS-01 DuckDNS), `tools/verificar_despliegue.py` con pruebas unitarias, ADR-034, guía `docs/despliegue-prueba-vps.md` y documentación enlazada. Ensayos locales E-L1…E-L15 (salvo repetición de E-L14 con Docker caído el 2026-11-03) según tabla del diseño. Verificación en VPS por la persona dueña el **2026-11-03** con puertos publicados **10004/10005** y SSH **10003**.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-03 | **Alternativa A:** ACME DNS-01, `Dockerfile` + plugin DuckDNS, `remoto --http-port 10004 --https-port 10005` | Puertos 80/443 estándar de la IPv4 compartida no llegan a Caddy; decisión en `_index.md` |
| 2026-11-03 | Caddyfile: redirección explícita `https://{host}:10005{uri}` en bloque `:10004` HTTP; **sin** `https_port` global | `https_port` global desplazaba el listener interno de HTTPS |
| 2026-11-03 | `evaluar_certificado` acepta emisor Let's Encrypt anidado (OpenSSL en Windows) | `remoto` fallaba con certificados válidos |
| 2026-11-02 | Guía §4: `scp` archivo por archivo a rutas espejo | Un solo destino `/srv/cimenta/` no crea subárboles |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `despliegue/compose.vps.yaml` | nuevo | infraestructura |
| `despliegue/comprobar_permisos.sql` | nuevo | infraestructura |
| `despliegue/caddy/*` | nuevo | infraestructura |
| `tools/verificar_despliegue.py` | nuevo | pruebas / operación |
| `tools/tests/test_verificar_despliegue.py` | nuevo | pruebas |
| `docs/despliegue-prueba-vps.md`, `docs/adr/20261102-destino-de-prueba-en-vps.md` | nuevo | documentación |
| `lychee.toml`, `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/02-arquitectura.md`, `docs/06-stack-tecnologico.md`, `docs/05-tickets-trabajo.md`, `docs/convenciones.md`, `.editorconfig`, `.claude/skills/conv-docker/SKILL.md`, `tools/README.md` | modificado | documentación |
| `sdd/tickets/tkt-070/spec.md`, `design.md` | modificado | SDD |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-U1…TC-U12 | `tools/tests/test_verificar_despliegue.py` (16 métodos) | feliz / rechazo simulado | `CA-S3`, `CA-1`, `CA-2`, `CA-4` | FALLA (`ModuleNotFoundError: verificar_despliegue`) | PASA |
| TC-06a… | Ensayo local migración `cimenta-sonda` | feliz / rechazo | `CA-7`, `CA-8`, `CA-R1` | FALLA (roles inexistentes) | PASA (E-L9…E-L13, diseño) |
| TC-01…TC-10 | Filas V en VPS | manual | `CA-1`…`CA-10`, `CA-S*` | — | PASA (evidencia abajo) |

### Ciclo TDD por fila

#### Fila A5 · script de verificación

**Rojo:**

```text
ModuleNotFoundError: No module named 'verificar_despliegue'
```

**Verde:**

```text
Ran 16 tests in …
OK
```

**Refactor:** emisor LE anidado; puertos HTTP/HTTPS en `remoto`; deduplicación de fallos HTTP.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar:**

```text
docker info → demonio no disponible (2026-11-03); E-L14 no repetido; evidencia E-L14 en design §Resultados
python -m unittest discover -s tools/tests → OK (sin skipped=)
python tools/verificar_docs.py → ✓ Sin problemas. (adrs 34)
```

**Mutación en rutas críticas:** M1–M3 del design (operador en `exposiciones_docker` / umbral certificado): tests en rojo al mutar; revertidos. No aplica mutación en rutas HTTP del backend.

#### Filas V1–V8 · VPS (persona dueña, sin secretos en log)

**Evidencia resumida (2026-11-03):**

```text
python tools/verificar_despliegue.py remoto --http-port 10004 --https-port 10005
→ Resultado: 0 fallas (Let's Encrypt en ambos nombres)

sudo python3 tools/verificar_despliegue.py anfitrion  → código 0
alembic current → 0008 (head) en prod y test
comprobar_permisos.sql → 22 filas ok en ambos entornos
CA-6 → password authentication failed en cruces; control positivo OK
grep -c "certificate obtained successfully" tras recrear Caddy → 0
Tras sudo reboot → tres contenedores Up; remoto otra vez 0 fallas
```

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A1–A3, A5 verde, A6–A7 | orquestador | `haiku` | Composer 2.5 | Sesión Cursor |
| A4 | `desarrollador-sql` | `sonnet` | evidencia design | No re-ejecutado con Docker caído |
| A5 rojo | `tester-backend` | `sonnet` | Composer 2.5 | Tests escritos antes del script |
| V1–V8 | persona dueña | — | — | SSH y VPS |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | `anfitrion` + `Test-NetConnection` puertos DB false; `remoto` sondeo |
| `CA-2` | `[M]` | Cumplido | V3 sonda + `anfitrion` |
| `CA-3` | `[M]` | Cumplido | DNS-01 LE prod; `remoto` certificado |
| `CA-4` | `[M]` | Cumplido | `remoto` HTTP → `:10005` |
| `CA-5` | `[M]` | Cumplido | `comprobar_permisos.sql` 22× True |
| `CA-6` | `[M]` | Cumplido | Bucle §8 guía |
| `CA-7` | `[M]` | Cumplido | `0008 (head)` ambos entornos |
| `CA-8` | `[M]` | Cumplido | `PGOPTIONS` + `RuntimeError` guarda |
| `CA-R1` | `[M]` | Cumplido | SQL permisos + disparadores |
| `CA-9` | `[M]` | Cumplido | `.env.prod`/`.env.test` ignorados; sin secretos en diff |
| `CA-10` | `[M]` | Cumplido | E-L1 |
| `CA-11` | `[M]` | Cumplido | ADR-034 |
| `CA-12` | `[M]` | Cumplido | `verificar_docs.py` |
| `CA-13` | `[M]` | Cumplido | Guía seguida en sesión VPS |
| `CA-S1`…`CA-S5` | `[S]` | Cumplido | V2, V8, mem_limit, reboot |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | **APROBADO** | F001–F005 Resuelto; ciclo 3 sin regresión | 3 |
| `auditor-sql` | **APROBADO** | O1–O4 observaciones | 1 |
| `auditor-codigo` | **APROBADO** | F004–F008 Resuelto; O011–O015 observación | 3 |
| `auditor-seguridad` | **APROBADO** | F001 Resuelto; F002 `@v0.4.0`; F003 `.dockerignore` (orquestador, ciclo 2) | 2 |
| `auditor-docs` | **APROBADO** | F001–F009 Resuelto (ciclo 2 reauditoría + `.dockerignore` en scp) | 2 |

### Hallazgos y su resolución (ciclo 1)

| ID | Auditor | Severidad | Estado |
|---|---|---|---|
| F001 | arquitectura / seguridad / docs | Mayor | **Resuelto** en guía §4 (`sed` por clave + `test … wc -l`) |
| F002 | arquitectura | Menor | **Resuelto** scp espejo + puerto 10003 |
| F003 | arquitectura / docs | Menor | **Resuelto** `docs/05-tickets-trabajo.md` DNS-01 |
| F004 | arquitectura / codigo | Menor | **Resuelto** rangos 5432 en `verificar_despliegue.py` |
| F003 | seguridad | Menor | **Resuelto** `despliegue/caddy/.dockerignore` |
| F001–F005 codigo | codigo | Mayor/Menor | **Resuelto** ciclo 2 (tests salida FALLA, rango 5432, DNS→2, notAfter; ruff limpio) |
| F005–F008 | docs | Menor | **Resuelto** ciclo 2 (acentos, §3 E-V3, one-liner §7, placeholders, LF) |
| F002 seguridad | seguridad | Menor | **Resuelto** `duckdns@v0.4.0` en Dockerfile |

### Corrección ciclo 3 (`auditor-codigo` Menores)

| ID | Estado | Cambio |
|---|---|---|
| F004 | **Resuelto** | Tests `remoto` con `redirect_stdout`, aserciones `FALLA`/`192.0.2.1:5433`; TC-U7 explícito; `notAfter` ausente; `CalledProcessError`, HTTP/cert `OSError`, `BadStatusLine` |
| F005 | **Resuelto** | `_iter_publicaciones_db` compartido por `exposiciones_docker` y `puertos_db_publicados` |
| F006 | **Resuelto** | `escuchas_expuestas`: quitado `"[::1]"` inalcanzable |
| F007 | **Resuelto** | HTTP captura `http.client.HTTPException`; certificado solo `OSError` |
| F008 | **Resuelto** | `ErrorEjecucionAnfitrion` → `main` devuelve `2` (sin `sys.exit` en helper) |
| F009–F010 | Observación | Desalineación Docker/`ss` en `127.0.0.2` y rangos en `ss`; no bloquea |

**Contraseñas VPS (2026-11-03):** la persona dueña confirmó que `.env.prod` y `.env.test` se generaron con el procedimiento §4 (`sed` por clave) y que **cada archivo tiene tres contraseñas distintas** (`CIMENTA_DB_CONTRASENA_*`). No van al repositorio.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| — | Respaldo `pg_dump` a bucket (decisión persona dueña) | Ticket futuro en `_index.md` |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| ADR-034 + índice | Destino de prueba temporal |
| `docs/despliegue-prueba-vps.md` | Guía completa con DNS-01 y puertos 10004/10005 |
| Recuentos 34 ADR | `CLAUDE.md`, `README.md`, `llms.txt` |
| `lychee.toml` | Excluye `duckdns.org` |
| Resto | Ver tabla «Documentación afectada» del design |

`python tools/verificar_docs.py` → resultado:

```text
✓ Sin problemas.
adrs                  34
```

## Verificación final

**Suite (`/sdd-revisar`, 2026-11-03, Docker activo):**

```text
docker info → OK (Client 29.9.2)
uv run pytest → 1800 passed, 10 skipped in 321.77s (0:05:21)
uv run ruff check . → All checks passed!
uv run mypy cimenta/ → Success: no issues found in 88 source files
uv run lint-imports → Contracts: 15 kept, 0 broken
python tools/verificar_docs.py → ✓ Sin problemas. (adrs 34, codificación 230)
python -m unittest discover -s tools/tests → Ran 509 tests in 16.056s OK
python -m unittest tools.tests.test_verificar_despliegue → Ran 25 tests in 0.009s OK
```

**Criterios `[M]`:** 13/13 · **`[S]`:** 5/5.

**Reauditoría ciclo 3:** `auditor-codigo` y `auditor-arquitectura` **APROBADO**. Resto sin cambio desde ciclo 2 (**APROBADO**). Tres ciclos de corrección (guía `sed`, docs/LF, código Menores). Observaciones abiertas no bloqueantes: O011–O015 (`auditor-codigo`), respaldo `pg_dump` (ticket futuro).

**Contraseñas:** `.env.prod` y `.env.test` en VPS con tres valores distintos cada uno (confirmación persona dueña).

**Pipeline PR:** los nueve trabajos de `ci.yml` se verifican en `/sdd-completar` (este comando no abre PR).

## Resultado

**ARCHIVADO** (planificación) · PR en `/sdd-completar` · [delta](delta.md)

- [x] Ciclo TDD A5 documentado
- [x] Cinco auditorías **APROBADO**
- [x] Documentación afectada en este cambio
- [x] Suite backend y `tools/tests` en verde
- [x] Sin secretos en diff
