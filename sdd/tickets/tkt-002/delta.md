# Delta · TKT-002 · Esqueleto del backend por capas y verificación de fronteras

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Diez paquetes de módulo con sus cuatro capas y su `interfaz.py` | `backend/cimenta/<modulo>/` (60 archivos, 40 vacíos) | El esqueleto sobre el que escriben los tickets de módulo. `avance` y `personal` existen vacíos desde ahora, para no reabrir el grafo en la fase 2 |
| `import-linter` como dependencia de desarrollo | `backend/pyproject.toml` y `backend/uv.lock` (con `grimp`, `click`, `rich`, `markdown-it-py`, `mdurl` y `pygments`) | Hacer ejecutable `uv run lint-imports` |
| Catorce contratos de fronteras en cuatro familias | `[tool.importlinter]` de `backend/pyproject.toml` | Que el monolito modular se vigile solo: esqueleto exhaustivo, dominio sin framework, interior de cada módulo privado y grafo de quién importa a quién |
| ADR-018, interfaz publicada en un único archivo y fronteras verificadas con `import-linter` | `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` | Registrar las opciones descartadas de tres decisiones que condicionan a cada ticket de módulo |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Docstring del paquete raíz | `backend/cimenta/__init__.py` | «Los paquetes de módulo llegan con TKT-002» → remite a `[tool.importlinter]` |
| Grafo entre módulos | `docs/02-arquitectura.md` §3 a §7.7 | Sin transversales en el grafo, `archivos` «no conoce a nadie» → columna «Importa, solo por su interfaz» con 33 aristas, el contrato como fuente y `archivos` sin conocer a ningún módulo de negocio |
| Regla 2 y regla 3, estructura, comandos y frase de `presupuesto` y `analitica` | `CLAUDE.md` | La regla 3 solo se precisa: otro módulo se usa solo por `cimenta.<modulo>.interfaz`, y `import-linter` lo verifica. La regla 2 pierde la marca «desde TKT-002». Ninguna regla cambia de contenido |
| Ejemplo de contrato | `docs/06-stack-tecnologico.md` §8 | Bloque `ini` de ejemplo → tabla de las cuatro familias |
| Textos de tickets | `docs/05-tickets-trabajo.md` (TKT-059, 060, 064, 069) | Declaraban ellos las aristas `compras ↛ analitica` y `avance → compras`, o decían que `archivos` no conoce a ningún otro → ya están declaradas aquí, y `archivos` usa `identidad` y `auditoria` |
| Arranque local | `docs/arranque-local.md` | `lint-imports` figuraba como «todavía no arranca» → está en el arranque del backend |
| Conteo de ADR | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md` | 17 → 18 |
| Otros documentos | `docs/03-modelo-datos.md`, `docs/07-especificacion-api.md`, `.claude/skills/conv-backend-fastapi/SKILL.md` | Frases que el grafo contradecía |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Marca «desde TKT-002» de `uv run lint-imports` y de la regla 2 | `CLAUDE.md`, `docs/arranque-local.md` | El comando ya funciona. La regla 2 conserva «en el pipeline desde TKT-009» |
| La nota `unused section` de mypy | salida de `uv run mypy .` | Ya hay `dominio/` que satisfacen el patrón estricto de TKT-001 |

## Comportamiento observable nuevo

- `uv run lint-imports`, desde `backend/`, termina con código 0 y `Contracts: 14 kept, 0 broken` sobre el esqueleto.
- Falla con código distinto de 0, y nombrando el contrato y el módulo, si un módulo importa el `dominio/`, la `infraestructura/`, la `aplicacion/` o la `api/` de otro; si un `dominio/` importa `fastapi`, `sqlalchemy` o `pydantic`, directa o indirectamente; si se importa una arista que el grafo no declara; si falta un módulo, una capa o una interfaz, o sobra uno; o si un nombre de módulo del contrato está mal escrito.
- Un módulo ya se puede consultar por `cimenta.<modulo>.interfaz` sin que el contrato proteste, aunque esa interfaz use por dentro su propia infraestructura.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO, tipos generados, esquema de base de datos | Ninguno | No |
| Convención interna entre módulos | La puerta de un módulo es `cimenta/<modulo>/interfaz.py` | No: no había código que la usara |

## Decisiones (ADR)

La decisión tuvo opciones descartadas con evidencia citable y se escribió como ADR-018: [`docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md`](../../../docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md). Resumen:

- **Punto de entrada:** `interfaz.py` fuera de las cuatro capas, frente a `aplicacion/__init__.py` (provoca un ciclo de importación dentro del módulo) y al `__init__.py` del módulo (se ejecuta con cualquier submódulo y arrastraría el ORM a las pruebas del dominio puro).
- **Grafo:** un contrato `protected` por módulo, frente a `forbidden` por origen (descarta en silencio los nombres internos inexistentes, así que una errata dejaría pasar la arista), `layers` (permite toda arista hacia abajo) e `independence` (mira imports indirectos y no se puede relajar).
- **Esqueleto:** `layers` exhaustivo, frente a una función propia en `tools/`.
- **Evidencia:** el experimento del 2026-10-17 con `import-linter` 2.15 y `grimp` 3.17, la lectura de su código fuente, 37 casos de prueba con 26 rechazos y 20 mutantes (`impl.md`).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un contrato `forbidden` descarta en silencio los módulos internos de `forbidden_modules` que no existen; solo valida `source_modules`. `protected` y `layers` sí validan sus nombres | Código fuente de `import-linter` 2.15 y `TC-29`, `TC-30` | Cualquier contrato nuevo: poner los nombres de módulo solo en campos validados |
| Por omisión, `forbidden` también marca los imports indirectos. El contrato que protege el interior de un módulo necesita `allow_indirect_imports = true` o fallará siempre que se use la interfaz | Experimento del orquestador, `TC-22` y mutante `M10` | Contratos de TKT-004, TKT-005, TKT-060 y TKT-066 |
| Con `include_external_packages = true`, `import-linter` detecta `import fastapi` aunque FastAPI no esté instalado | Experimento del orquestador y `TC-13` a `TC-15` | El contrato del dominio no obliga a instalar los frameworks antes de su ticket |
| Con `rich` a 80 columnas, la salida de `lint-imports` parte las frases y una búsqueda literal falla | Fila 1 | Cualquier prueba que busque cadenas: `COLUMNS=250` |
| `Missing layer in container …` es una excepción: termina con código 1 sin resumen y solo muestra el primer error | `TC-03` a `TC-08` | Cuando una demostración dé un mensaje distinto al del diseño |
| Un `layers` exhaustivo con comodines vigila las capas de cualquier módulo futuro sin tocar el contrato | `TC-04`, `TC-06` | Módulos nuevos de la fase 2 |
| `lint-imports` añade el directorio actual a `sys.path`, así que el proyecto no necesita `[build-system]` si se ejecuta desde `backend/` | Código fuente y fila 1 | TKT-009: el pipeline debe ejecutarlo desde `backend/` |
| El contrato no cierra `cimenta/<m>/__init__.py` como segunda puerta, ni prohíbe más paquetes de tercero que los tres nombrados | Auditoría de arquitectura, O1 | TKT-004 y TKT-009 |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Siguen faltando `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `meta-sdd` y `desarrollador-aplicacion`. Es la tercera vez que aparece (2026-10-01, TKT-001 y este ticket), con el mismo remedio: sustitución según metodología §13 | Media |
| `herramienta` | `verificar_docs.py` falla durante todo el ticket por los enlaces del hub a `impl.md` y `delta.md`, y de `design.md` a artefactos futuros como el ADR. Segunda vez; la excepción se repite en cada spec | Alta |
| `agente` | Context7 no respondió (1800 s) al diseñar, y `arquitecto-tecnico` no tiene terminal. Esta vez se resolvió porque el orquestador hizo un experimento real antes de despachar al arquitecto; sin él, el diseño habría descansado en una lectura de código fuente sin ejecutar | Media |
| `comando` | `/sdd-disenar` debería prever un paso de experimento previo cuando el diseño depende del comportamiento real de una herramienta, y decir quién lo ejecuta, porque el arquitecto no tiene terminal | Media |
| `guardrail` | Un contrato que nunca se vio fallar no está verificado: este ticket exigió una demostración y un mutante por regla, y detectó que `TC-17` de TKT-001 había nacido en verde. Merece volverse regla de `conv-pruebas` para tickets de verificación | Media |
| `convención` | Los textos de reemplazo literales dentro de `design.md`, escritos para otros documentos, hacían fallar `verificar_docs.py` como enlaces rotos hasta que se reformularon sin sintaxis de enlace. La plantilla de diseño debería decirlo | Baja |
| `comando` | El gate de `/sdd-disenar` de un ticket que declara aristas nuevas en un grafo ya documentado destapó una contradicción con la arquitectura (TKT-006 necesita `identidad` → `auditoria`). La spec debería cruzar el grafo con los tickets que lo usan antes de aprobarse | Media |
| `modelo` | Las filas de `haiku` salieron bien a la primera en cuarenta y tantos despachos; el tester en `sonnet` necesitó ayudas (scripts de aislamiento) que pasaron de fila en fila. Conviene que el diseño nombre un directorio común de scripts de prueba | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `dominio-sin-framework` es una lista negra de tres paquetes; la regla 2 dice «no importa nada». Otro paquete de tercero, o `dominio` → `interfaz` de otro módulo, pasan | Estaba dentro del alcance acordado (`M4`, `PA-T2`, `D-4`) | TKT-004: ampliar la lista o pasar a lista blanca |
| `cimenta/<m>/__init__.py` es una segunda puerta que el contrato no cierra | Ningún Must lo pide; lo cubren el docstring, el ADR y la revisión | TKT-009: comprobar que los diez solo tienen docstring |
| La raíz de composición de FastAPI, los tipos compartidos y la excepción de dominio chocarán con `esqueleto-modulos`, `solo-por-interfaz` y los `grafo-<m>` | Son non-goals de este ticket | TKT-004 y TKT-005: decidir si viven fuera de `cimenta/` o como excepción declarada |
| Alembic debe quedar fuera de `cimenta/` | Si el entorno de migraciones fuera un hijo de `cimenta/`, `esqueleto-modulos` lo rechazaría | TKT-003 |
| La comprobación de rol de `GET /bitacora` sin la arista `auditoria` → `identidad` | La arista está prohibida; se resuelve al montar el enrutador | TKT-005 o TKT-007 |
| `uv run lint-imports` en CI, desde `backend/` | CI es TKT-009 | TKT-009 |
| Verificador de que arquitectura §5 y el contrato dicen el mismo grafo | `TC-36` lo comprueba una vez; automatizarlo es otro ticket | TKT-009 |
| `analitica` → `identidad` y `analitica` → `auditoria` siguen `(asumido)` | Ningún ticket de `analitica` las ha confirmado | TKT-039 o el primer ticket de `analitica` |
| `sdd/00-propuesta-toolkit.md` línea 17 dice «17 ADRs» | Es un documento de propuesta histórico | Siguiente cambio del toolkit |
| `docs/arranque-local.md` coloca el párrafo de `lint-imports` tras el que habla de Ruff y mypy | Sin efecto funcional | Siguiente cambio de documentación |

## Pull request

**Título:** `TKT-002 · Esqueleto del backend por capas y verificación de fronteras`
**Origen:** `agent`
**Cuerpo:**

Qué: crea los diez módulos de la arquitectura bajo `backend/cimenta/`, cada uno con `api/`, `aplicacion/`, `dominio/`, `infraestructura/` y un único punto de entrada `interfaz.py`, sin lógica de negocio, e instala `import-linter` con catorce contratos de fronteras en `[tool.importlinter]`: esqueleto exhaustivo, dominio sin FastAPI, SQLAlchemy ni Pydantic, interior de cada módulo privado y un contrato `protected` por módulo con el grafo de quién importa a quién (33 aristas permitidas, 57 prohibidas). Añade el ADR-018 y actualiza `docs/02-arquitectura.md`, `CLAUDE.md` y los documentos que el grafo contradecía.

Por qué: la decisión de monolito modular (ADR-001, `docs/adr/20260918-monolito-modular.md`) solo se sostiene si las fronteras se verifican de forma automática; sin ello el monolito degenera en un monolito con carpetas.

Criterios cubiertos: `CA-1` a `CA-8` y `CA-R1` a `CA-R5` de `sdd/tickets/tkt-002/spec.md`, más `S1`. Cada contrato se vio fallar con un archivo desechable y se mutó (M1 a M20); `TC-28` comprueba que los 57 pares prohibidos son exactamente los de la tabla de la spec. Decisiones del usuario aplicadas: `identidad` → `auditoria` permitida, `archivos` solo importable por `presupuesto`, `almacen` y `avance`, ADR-018 y `esqueleto-capas` en dos niveles.

Cómo verificarlo, con `uv` instalado:

```bash
cd backend && uv sync --locked && uv run lint-imports && uv run mypy . && uv run ruff check .
cd .. && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en `sdd/tickets/tkt-002/delta.md`. Auditorías: arquitectura y seguridad aprobadas en el primer ciclo. No se despacharon `auditor-codigo` ni `auditor-docs`, porque esos agentes no existen en este entorno.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
