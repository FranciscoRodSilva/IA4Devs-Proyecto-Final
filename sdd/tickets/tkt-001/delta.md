# Delta · TKT-001 · Estructura del repositorio y herramientas base

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Proyecto Python con `uv`, Ruff y mypy; mypy estricto solo sobre `cimenta.*.dominio.*` | `backend/pyproject.toml`, `backend/uv.lock`, `backend/cimenta/__init__.py` | Que el backend se instale, formatee, lintee y tipe con comandos reproducibles, y que TKT-002 encuentre un proyecto sobre el que construir |
| Proyecto Node con TypeScript estricto, ESLint plano y Node fijado a la línea 24 con `engine-strict` | `frontend/package.json`, `package-lock.json`, `.npmrc`, `tsconfig.json`, `eslint.config.js`, `src/index.ts` | Lo mismo para el frontend, y que TKT-008 instale React y Vite sobre una base ya verificada |
| Reglas de editor y de finales de línea | `.editorconfig`, `.gitattributes` | UTF-8 sin BOM y LF para todo, con la excepción de `*.ps1`, que lleva BOM |
| Archivo de entorno de ejemplo, sin claves | `.env.example` | Cumplir `RNF-07`: las claves se documentan sin valores y cada ticket añade las suyas |
| Comprobación de codificación | `tools/verificar_docs.py` (función `verificar_codificacion`) y `tools/tests/test_verificar_codificacion.py` | Detectar un `.md` con BOM o un `.ps1` sin él, que es lo que rompió seis agentes el 2026-10-01 |
| Documento de arranque local | `docs/arranque-local.md` | Requisitos, comandos verificados, tabla de lo que todavía no arranca y constancia de la verificación en copia limpia |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `.gitignore` | raíz | No cubría `.env.production` ni sus variantes → ignora `.env.*` y exceptúa `.env.example` |
| Sección «Comandos» y marcas de disponibilidad | `CLAUDE.md` | Comandos mezclados y algunos inexistentes → tres grupos con su directorio y marca «desde TKT-xxx» en lo que aún no funciona. Las 17 reglas no cambian de texto |
| Estado y estructura | `README.md`, `llms.txt` | «Sin código todavía» → «Entrega 2 en curso» y enlace al arranque local |
| Árbol del repositorio | `docs/convenciones.md` §3 | No listaba `backend/`, `frontend/`, `tools/`, `sdd/` ni `.claude/` → los lista |
| Descripción del verificador | `docs/06-stack-tecnologico.md` §9, `tools/README.md` | No mencionaba la codificación → la documenta y explica cómo correr `tools/tests/` |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Nada | — | — |

## Comportamiento observable nuevo

- Desde una copia limpia, `uv sync --locked` y `npm ci` instalan sin errores, y Ruff, mypy, ESLint y `tsc` terminan en verde.
- `python tools/verificar_docs.py` falla ahora con un `.md` con BOM o un `.ps1` sin BOM, y nombra el archivo.
- `npm ci` falla con `EBADENGINE` si el Node instalado no es de la línea 24.
- Un `.env.production` o cualquier `.env.*` ya no se puede preparar por descuido.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO, tipos generados, esquema de base de datos | Ninguno | No |

## Decisiones (ADR)

Ninguna merece ADR. Las elecciones del ticket (extender `verificar_docs.py` en lugar de crear un script, `unittest` en lugar de pytest para `tools/`, `engines` con `engine-strict` en lugar de `.nvmrc`, proyecto `uv` sin empaquetar) son configuración reversible en minutos, y las herramientas ya las decidió el [stack §8](../../../docs/06-stack-tecnologico.md#8-calidad-y-herramientas). El porqué de cada una queda en la escalera de decisión de [`design.md`](design.md).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Ruff 0.17 activa por omisión un conjunto amplio de reglas, incluida `I001`. Un `select` explícito las sustituye, y por eso el mutante «quitar `"I"`» solo se detecta si `select` es explícito, nunca `extend-select` | TC-17 nació en verde; `ruff check --show-settings`; mutante M6 | Cualquier ticket que añada o cambie reglas de Ruff, empezando por TKT-004 |
| El comodín `cimenta.*.dominio.*` de mypy solo coincide si cada directorio intermedio tiene `__init__.py` | TC-14 y TC-15 con desechables; la auditoría lo reprodujo | TKT-002, al crear los `dominio/` reales |
| Sin ningún `dominio/` real, mypy emite `note: unused section(s)` por `warn_unused_configs`. Es una nota, con código de salida 0 | Salida de `uv run mypy .` | Desaparece con TKT-002; no es un error |
| `@eslint/js` no siempre publica la misma versión que `eslint`: el 2026-10-17 la última de `eslint` era 10.13.0 y la de `@eslint/js`, 10.0.1 | `npm view @eslint/js@10.13.0` responde E404 | TKT-008 y las actualizaciones de dependencias de TKT-009 |
| `npm ls --depth=0` imprime la ruta absoluta en la cabecera, así que comparar dos copias exige descartar esa línea | TC-25 | Verificaciones de arranque reproducible |
| `npm ci` sin `package-lock.json` falla por el archivo de bloqueo, no por la ausencia de `package.json` | Rojo de la fila 6 | Cualquier prueba de arranque del frontend |
| `git check-ignore -v` devuelve 0 para un archivo reincluido con `!`, porque informa del patrón negado; sin `-v`, devuelve 1 | TC-10 | Verificaciones de `.gitignore` |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | `verificar_docs.py` falla durante todo el ticket porque el hub (`_index.md`) y `design.md` enlazan `impl.md` y `delta.md`, que aún no existen. Afecta a todos los tickets: el verificador que el pipeline manda correr antes de cerrar no puede dar código 0 hasta `/sdd-completar` | Alta |
| `agente` | Faltan los agentes `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `meta-sdd` y `desarrollador-aplicacion`, que los comandos nombran. Se sustituyeron según [metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe), y el impacto lo hizo el arquitecto y la documentación el orquestador. Es la segunda vez que aparece esta fricción | Media |
| `comando` | `/sdd-ejecutar` y `/sdd-revisar` asumen `pytest`, testcontainers, Docker y `lint-imports`, que un ticket de fundación no tiene. Se resolvió con una excepción registrada en la spec y el diseño: las pruebas son `unittest` y comandos con su código de salida. Falta una variante «ticket de fundación» en esos dos comandos | Media |
| `guardrail` | `/sdd-ejecutar` no comprueba el entorno antes de empezar. El diseño fijó Node 24 y el equipo tenía Node 22: la verificación se detuvo hasta que el usuario instaló Node 24. El gate debería comparar las versiones de `engines` y `requires-python` con las instaladas | Media |
| `agente` | `arquitecto-tecnico` no tiene terminal, así que no pudo consultar versiones ni valores por omisión reales y fijó una regla determinista en lugar de un número. Funcionó, pero tres supuestos del diseño fallaron al ejecutar: el rojo de `npm ci`, `I001` en el conjunto por omisión de Ruff y la existencia de `@eslint/js` 10.13.0 | Baja |
| `agente` | Cada reauditoría de `auditor-arquitectura` devolvió hallazgos sobre el texto exacto de una marca que el corrector había escrito de forma aproximada. Fueron tres ciclos para dos celdas de texto. Conviene que el hallazgo incluya el texto literal esperado y que el corrector lo copie sin reformular | Media |
| `convención` | El `.editorconfig` fija LF y la copia de trabajo en Windows está en CRLF porque Git convierte al descargar. La contradicción es aparente: el índice está en LF y `.gitattributes` lo mantiene, pero `docs/arranque-local.md` no lo aclara para quien edite en Windows | Baja |
| `guardrail` | `git-entrega` en modo apertura manda parar si hay cambios ajenos sin commitear. Aquí había dos archivos de `.claude/` modificados antes del ticket, y se abrió la rama con ellos arrastrados. Quedan fuera del commit del ticket, pero el procedimiento no dice cómo separarlos | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `eslint` en 10.0.1, no en la última (10.13.0), para mantener `@eslint/js` en la misma versión | La regla de versiones del diseño lo exige; cumplir `CA-5` con la última pide aceptar un par de versiones distintas | TKT-009 (política de actualización de dependencias) |
| Integrar `verificar_codificacion` en el pipeline | CI es TKT-009, non-goal de este ticket | TKT-009 |
| Declarar `pip-audit` como dependencia de desarrollo o documentar `uvx pip-audit` | La auditoría lo ejecutó con `uvx`; la compuerta de CI es de TKT-009 | TKT-009 |
| Confirmar que el patrón de mypy estricto sigue aplicando a los `dominio/` reales | Solo se probó con desechables | TKT-002 |
| Quitar o corregir las marcas «desde TKT-xxx» de `CLAUDE.md` y de `docs/arranque-local.md` al completar cada ticket que las habilita. Las de `uv run pytest` y `uv run fastapi dev` son `(asumido)` | Sin esa tarea el documento miente cuando el comando ya funciona | `/sdd-completar` de TKT-002, TKT-003, TKT-004, TKT-005, TKT-008 y TKT-059 |
| `design.md` conserva la marca original de `uv run pytest` (`desde TKT-003 (asumido)`) | Es el plan aprobado; `impl.md` documenta el cambio | Ninguno |
| Sin `.python-version`, el intérprete de `uv` depende de la máquina (aquí, CPython 3.14.3 con `requires-python >=3.13`) | El diseño lo descartó por YAGNI | TKT-009 o TKT-058 |
| `docs/arranque-local.md` no menciona que `extraer_mermaid.py` escribe `tools/mermaid-check.html` (ignorado por Git) ni la aclaración de LF frente a CRLF en Windows | Baja prioridad, sin efecto en el repositorio | Siguiente cambio de documentación |
| `.env.example` sin claves, mientras `conv-docker` pide «valores de desarrollo evidentes» cuando lleguen | La tensión nace con la primera clave | TKT-003 |
| `tools/verificar_docs.py` y `README.md` no recogen una variante de Definition of Done para tickets de fundación | Fuera del alcance del ticket | Mejora del toolkit propuesta en `_evolucion.md` |

## Pull request

**Título:** `TKT-001 · Estructura del repositorio y herramientas base`
**Origen:** `agent`
**Cuerpo:**

Qué: crea el andamiaje del repositorio. `backend/` es un proyecto `uv` con Ruff y mypy (estricto solo sobre `dominio/`); `frontend/` es un proyecto `npm` con TypeScript estricto, ESLint y Node 24 fijado con `engine-strict`. Añade `.editorconfig`, `.gitattributes` y `.env.example` sin claves, completa `.gitignore`, incorpora la comprobación de codificación a `tools/verificar_docs.py` con sus pruebas, y documenta el arranque en `docs/arranque-local.md`. Actualiza `CLAUDE.md`, `README.md`, `llms.txt` y convenciones §3, con las marcas «desde TKT-xxx» en los comandos que aún no funcionan.

Por qué: la Épica 0 necesita una base reproducible antes de que exista la primera regla de negocio. Además, el 2026-10-01 un BOM dejó ilegibles seis agentes, y nada lo detectaba.

Criterios cubiertos: `CA-1` a `CA-10` y `CA-R1` a `CA-R4` de [`spec.md`](spec.md), con el `S1` (reglas de Ruff explícitas). Cada compuerta se vio fallar con un archivo desechable y se mutó (M1 a M9). Desviación: `eslint` queda en 10.0.1 y no en la última, porque `@eslint/js` no publica 10.13.0.

Cómo verificarlo, con Node 24 y `uv` instalados:

```bash
cd backend && uv sync --locked && uv run ruff format --check . && uv run ruff check . && uv run mypy .
cd ../frontend && npm ci && npm run lint && npm run typecheck
cd .. && python -m unittest discover -s tools/tests -v && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en [`delta.md`](delta.md). Auditorías: seguridad aprobada; arquitectura aprobada tras tres ciclos de corrección. No se despacharon `auditor-codigo` ni `auditor-docs`, porque esos agentes no existen en este entorno.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
