# Impl · TKT-071 · Mantenimiento de dependencias: mermaid-cli y parches de Dependabot

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta](delta.md)

## Qué se implementó

Se subió `@mermaid-js/mermaid-cli` a **12.2.0** en `.github/mermaid/` (elimina `katex` vulnerable del lock), se actualizaron **sqlalchemy 2.1.6**, **alembic 1.20.1** y **ruff 0.17.3** en `backend/uv.lock`, y **eslint 10.13.0** en el frontend. TC-65 exige ahora la versión exacta 12.2.0. La documentación afectada y una nota fechada en el ADR de Vale reflejan las versiones nuevas.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-05 | Mutación manual `^12.2.0` en `package.json` no ejecutada en local | Los mutantes permanentes de TC-65 en `test_definicion_documentacion.py` ya cubren CA-7; la versión exacta en el manifiesto real quedó en 12.2.0 |
| 2026-11-05 | `npm run e2e` | `(sin ejecutar)` en local: `webServer` de Playwright agotó 120 s al arrancar el backend (mismo entorno que en diseño, fila 7). Lo verifica el trabajo `humo` del PR |
| 2026-11-05 | Comandos de verificación K/D/U/V | Scripts en `$ESC` (`C:\Users\romeo\AppData\Local\Temp\cimenta-tkt071-esc\`), no versionados; el bucle de diagramas en `mermaid-ci-loop.sh` por limitación de quoting de PowerShell con rutas con espacio |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `.github/mermaid/package.json` | modificado | cadena de suministro |
| `.github/mermaid/package-lock.json` | modificado | cadena de suministro |
| `backend/uv.lock` | modificado | cadena de suministro |
| `frontend/package.json` | modificado | cadena de suministro |
| `frontend/package-lock.json` | modificado | cadena de suministro |
| `tools/tests/test_definicion_documentacion.py` | modificado | pruebas |
| `docs/06-stack-tecnologico.md` | modificado | documentación |
| `tools/README.md` | modificado | documentación |
| `.claude/skills/conv-documentacion/SKILL.md` | modificado | documentación |
| `docs/adr/20261029-vale-para-prosa-en-espanol.md` | modificado | documentación |
| `sdd/tickets/tkt-071/design.md` | modificado | SDD |
| `sdd/tickets/tkt-071/impl.md` | nuevo | SDD |
| `sdd/tickets/tkt-071/_index.md` | modificado | SDD |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | K + `npm audit` antes | **rechazo** | CA-2 | katex 0.16.47 / audit low | — |
| TC-02 | K copia sintética anidada | **rechazo** | CA-3 | exit 1 | — |
| TC-05 | TC-65 manifiesto y lock | feliz | CA-7 | FALLA (12.0.0) | PASA |
| TC-R1 | `uv run pytest` | regresión | CA-R1 | 2022 passed | 2022 passed |
| TC-R3a | bucle mmdc 6 archivos | regresión | CA-R3 | — | files=6 fallos=0 |
| TC-R3b | diagrama `A -->> B` | **rechazo** | CA-R3 | — | exit 1 |
| TC-R4 | pip-audit + npm audit high | regresión | CA-R4 | — | exit 0 en los tres |
| TC-R5 | lint, typecheck, vitest, tipos | regresión | CA-R5 | — | exit 0; e2e sin ejecutar |

### Ciclo TDD por fila

#### Fila 1 · Evidencia del antes

**Rojo:** K sobre lock actual:

```text
VULNERABLE node_modules/katex 0.16.47
ok node_modules/mermaid/node_modules/katex 0.18.10
```

K sobre copia sintética (TC-02):

```text
ok node_modules/katex 0.18.10
VULNERABLE node_modules/mermaid/node_modules/katex 0.16.47
```

`npm audit --audit-level=high`: exit 0. `uv lock --dry-run --upgrade` lista muchos paquetes (>3).

**Recuentos de partida:** backend `2022 passed, 26 skipped`; tools `510` tests OK; npm 11.19.1.

#### Fila 2 · Rojo TC-65

```text
FAIL test_tc65_mermaid_cli_package_json_declara_la_version_exacta_12_2_0
  ... declara ... en '12.0.0'; debe ser la versión exacta '12.2.0'
FAIL test_tc65_mermaid_cli_package_lock_fija_la_version_12_2_0_con_su_integridad
```

#### Fila 3 · Verde mermaid-cli

```text
ok node_modules/katex 0.18.10
K exit: 0
Ran 2 tests ... OK
```

#### Fila 4 · Diagramas

```text
mmdc --version: 12.2.0
files=6 fallos=0
invalido.md: exit 1
```

#### Fila 5 · Backend lock

```text
alembic 1.20.0 -> 1.20.1
ruff 0.17.1 -> 0.17.3
sqlalchemy 2.1.5 -> 2.1.6
ruff 0.17.3 · lint-imports 16 kept · verificar_float 0 hallazgos
```

#### Fila 6 · Suite backend

```text
2022 passed, 26 skipped in 383.84s
28 passed (migraciones ciclo)
```

#### Fila 7 · Frontend

```text
eslint 10.13.0 · lint/typecheck/vitest 214 passed · tipos al día
e2e: Timed out waiting 120000ms from config.webServer
```

#### Fila 8 · Auditorías

```text
severidad_pip_audit.py: exit 0
frontend npm audit --audit-level=high: exit 0
mermaid npm audit --audit-level=high: found 0 vulnerabilities
```

#### Fila 9 · Documentación

```text
verificar_docs.py: Sin problemas
extraer_mermaid.py: 30 diagramas
agentes_cursor.py --verificar: coinciden
```

#### Fila 10 · Cierre tools

```text
Ran 510 tests in 26.883s OK
```

**Mutación:** copia sintética de lock (TC-02) y diagrama inválido (TC-R3b). Mutante `^12.2.0` cubierto por pruebas de mutantes TC-65 existentes, no repetido a mano.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Filas 1–10 | Orquestador Cursor (Composer 2.5) | `haiku` | Composer 2.5 | Ejecución en sesión única; sin reintentos en `sonnet` |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| CA-1 lock mermaid 12.2.0 sin katex <0.18.2 | `[M]` | Cumplido | K exit 0; TC-05 |
| CA-2 rechazo katex antes / ausente después | `[M]` | Cumplido | audit antes; mermaid audit 0 vulns |
| CA-3 K detecta anidado vulnerable | `[M]` | Cumplido | TC-02 |
| CA-4 versiones backend y eslint | `[M]` | Cumplido | script V |
| CA-5 locks acotados | `[M]` | Cumplido | U + diffs |
| CA-6 documentación | `[M]` | Cumplido | fila 9 |
| CA-7 TC-65 exacta | `[M]` | Cumplido | TC-05 |
| CA-R1–R5 regresiones | `[M]` | Cumplido | pytest, compuertas, audits; e2e pendiente PR |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO | F001–F002 observaciones (16 contratos lint-imports; `impl.md` en commit del PR) | 1 |
| `auditor-sql` | N/A | Sin migraciones ni esquema | — |
| `auditor-seguridad` | APROBADO | F001–F002 BAJA (avisos moderados frontend con `--audit-level=high` en 0; transitivas eslint) | 1 |
| `auditor-docs` | APROBADO | O001: versionar `impl.md` en el PR | 1 |
| `auditor-codigo` | N/A | Solo cambio mecánico de versión en prueba de `tools/` | — |

Ciclos de corrección: **0** (ningún `REQUIERE CAMBIOS`).

## Verificación final (`/sdd-revisar` · 2026-11-05)

### Suite (salida real)

```text
docker info → Client 29.9.2 (demonio OK)

backend/
  uv run ruff format --check . → 233 files already formatted
  uv run ruff check . → All checks passed!
  uv run mypy cimenta/ → Success: no issues found in 102 source files
  uv run lint-imports → Contracts: 16 kept, 0 broken
  uv run python -m herramientas.verificar_float → hallazgos: 0
  uv run pytest -q → 2022 passed, 26 skipped in 358.81s
  migraciones ciclo → 28 passed in 13.71s

frontend/
  npm run lint / typecheck / test / tipos:verificar → OK (214 tests Vitest)
  npm run e2e → (sin ejecutar en revisión) Timed out waiting 120000ms from config.webServer

tools/
  python tools/verificar_docs.py → ✓ Sin problemas (259 documentos)
  python tools/extraer_mermaid.py → 30 diagramas
  python tools/agentes_cursor.py --verificar → coinciden
  python -m unittest discover -s tools/tests -q → OK (510 tests)
  PruebasDeMutantesDeLaFilaD5ParaTC65 → Ran 18 tests OK

dependencias (local):
  pip-audit → No known vulnerabilities found
  severidad_pip_audit.py → Sin vulnerabilidades
  npm audit --audit-level=high (.github/mermaid/) → found 0 vulnerabilities
  npm audit --audit-level=high (frontend/) → exit 0

K (.github/mermaid/package-lock.json) → ok node_modules/katex 0.18.10
V (CA-4) → sqlalchemy 2.1.6, alembic 1.20.1, ruff 0.17.3, eslint 10.13.0

git diff Produccion -- backend/pyproject.toml → sin cambios
git diff Produccion -- .github/workflows/ci.yml → sin cambios
git diff Produccion -- frontend/eslint.config.js → sin cambios
```

### Criterios `[M]`

| Criterio | Estado | Nota |
|---|---|---|
| M1 / CA-1 | Cumplido | mermaid-cli 12.2.0; K exit 0 |
| CA-2 | Cumplido | Evidencia fila 1 en impl (audit antes con katex low) |
| CA-3 | Cumplido | Copia sintética + K |
| CA-4 / M2 | Cumplido | V + locks |
| CA-5 | Cumplido | U acotado; non-goals sin bump mayor en `package.json` |
| CA-6 / M4 | Cumplido | Docs + verificadores + Vale (auditor-docs) |
| CA-7 | Cumplido | Mutantes TC-65 (18 tests), incl. circunflejo |
| M3 | **Parcial local · PR** | Nueve trabajos de `ci.yml` y `humo`/`e2e` se verifican en el PR; diseño filas 4 y 7 |
| CA-R1 | Cumplido | pytest + 28 migraciones |
| CA-R2 | Cumplido | Compuestas; 16 contratos (spec citaba 15; el repo ya tenía 16) |
| CA-R3 | Cumplido | 6 archivos mmdc Windows; Linux en PR |
| CA-R4 | Cumplido | Audits arriba; ci.yml intacto |
| CA-R5 | **Parcial local · PR** | lint/typecheck/test/tipos OK; e2e pendiente PR |

### Veredicto de revisión

**LISTO PARA PR** — Must verificables en local cumplidos; M3/CA-R5 (humo/e2e) y mmdc en Linux quedan como compuerta del PR (`/sdd-completar` no fusiona sin ellos).

## Pendiente del PR (`/sdd-completar`)

- Ejecutor Linux: paso «Diagramas con mermaid-cli» con `mmdc` 12.2.0.
- Trabajo `humo`: Playwright e2e.
- Cierre alerta GitHub y PR Dependabot (#22, #16, #13, #12) tras fusión.
- Incluir `sdd/tickets/tkt-071/impl.md` en el commit del PR (O001).
