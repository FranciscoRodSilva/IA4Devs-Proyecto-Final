# Delta · TKT-009a · Pipeline de pruebas y fronteras

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Flujo de integración continua con ocho trabajos: `backend`, `fronteras`, `contrato-api`, `frontend`, `humo`, `herramientas`, `workflows` y `documentacion` | `.github/workflows/ci.yml` | Que cada pull request ejecute las compuertas que hasta ahora solo corría quien se acordaba: formato, lint, tipos, regla de `float`, pruebas contra PostgreSQL con cobertura, fronteras entre módulos, cliente, humo de Playwright, suite de `tools/`, seguridad de los workflows y `verificar_docs.py` |
| Pruebas de la definición del flujo, con mutantes sintéticos por compuerta | `tools/tests/test_definicion_ci.py` | Que una compuerta comentada, movida de trabajo o desactivada (`continue-on-error`, `\|\| true`, `if: false`, `pytest -k`) ponga una prueba en rojo en lugar de pasar sin que nadie lo note |
| Trabajo reservado `contrato-api` | `ci.yml` | Hueco entre `backend` y `frontend` donde TKT-061 pondrá la prueba de contrato de la API; `frontend` espera a este trabajo |
| `pytest-cov` y su dependencia `coverage` en el grupo `dev` | `backend/pyproject.toml`, `backend/uv.lock` | Cobertura sin umbral: el resumen queda en el registro y `cobertura.xml` y `pytest.xml` se suben como artefacto `backend-pruebas` |
| Entradas de `.gitignore` para `backend/.coverage`, `backend/cobertura.xml` y `backend/pytest.xml` | `.gitignore` | Que los informes locales no se cuelen en un commit |
| Sección «Integración continua» | `docs/arranque-local.md` | Cómo reproducir en local cada trabajo del pipeline |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Reglas 1, 2 y 3 | `CLAUDE.md` líneas 20 a 22 | «en el pipeline desde TKT-009» → dicen qué trabajo hace fallar cada una (`backend` para `float` y Ruff, `fronteras` para `lint-imports`) |
| Comandos | `CLAUDE.md` | Sin mención del pipeline → un párrafo que remite a `ci.yml`, con las excepciones exactas de lo que no corre como comando |
| Skills `conv-dominio-python` y `conv-docker` | `.claude/skills/` | Futuro («desde TKT-009») → presente |
| Integración continua | `docs/06-stack-tecnologico.md` §10 | Descripción prospectiva → los ocho trabajos reales, la cobertura sin umbral y la desviación de MinIO |
| TKT-009 y TKT-059 | `docs/05-tickets-trabajo.md` | TKT-009 pedía MinIO en el trabajo de backend → MinIO queda fuera del sprint 1; TKT-059 añade como criterio el servicio y las pruebas de MinIO al trabajo `backend` |
| Docstrings de dos pruebas de `tools/` | `tools/tests/test_sembrar_usuario_humo.py`, `test_verificar_codificacion.py` | Prometían lo que haría TKT-009 → describen que el trabajo `herramientas` ya las corre |
| Doble de sesión de las pruebas del cierre | `frontend/src/app/armazon/Armazon.test.tsx` | Respondía siempre 200 → `dobleSesionQueTermina` responde 401 tras el cierre, como el servidor real. Ajuste fuera de alcance, autorizado por la persona dueña |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Las marcas «(en el pipeline desde TKT-009)» de las reglas 1 a 3 y de dos skills | `CLAUDE.md`, `.claude/skills/` | El pipeline ya hace cumplir esas reglas. La marca de `CLAUDE.md:78` (verificador de escenarios) se conserva: es de TKT-009c |

## Comportamiento observable nuevo

- Cada pull request ejecuta ocho trabajos y no se puede fusionar con confianza si alguno está en rojo: un `float` en una firma del dominio, un import cruzado entre módulos, una prueba rota, tipos del cliente desactualizados, un recorrido de inicio de sesión roto o un workflow sin permisos acotados lo ponen en rojo con el mensaje de la regla.
- El pipeline ya mostró su utilidad en la primera ejecución: destapó una prueba de TKT-008b que fallaba en Linux con CPU escasa y pasaba en Windows.
- Quien abre un PR recibe los informes de cobertura y de JUnit como artefacto, y los de Playwright si el humo falla.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoint, DTO, tipo generado o esquema | Ninguno | No |
| Dependencias de desarrollo | `pytest-cov` y `coverage` | No: solo el grupo `dev` |
| Tokens del repositorio | Los workflows piden `contents: read` y ningún secreto | No |

## Decisiones (ADR)

Ningún ADR nuevo para esta parte. El diseño prevé tres ADR, uno por cada parte b, c y d, porque en ellas hubo opciones descartadas que una persona nueva cuestionaría. En la parte a las decisiones son de aplicación directa del stack ya decidido ([stack §10](../../../docs/06-stack-tecnologico.md)).

Queda una decisión a la que el auditor de documentación apuntó como posible ADR y que se deja a criterio de la persona dueña:

### 2026-10-28 — MinIO fuera del trabajo `backend` hasta TKT-059

**Contexto:** el criterio original de TKT-009 pedía PostgreSQL y MinIO reales en el trabajo de backend, pero no existe adaptador de almacén que ejerza MinIO antes de TKT-059.
**Opciones consideradas:** levantar MinIO ya en el trabajo `backend` sin código que lo use; dejarlo fuera y añadirlo con TKT-059.
**Decisión:** dejarlo fuera. La persona dueña la tomó el 2026-10-28 en el gate del diseño.
**Evidencia:** sin adaptador no hay prueba que lo ejerza; el servicio solo alargaría el trabajo.
**Consecuencias:** TKT-059 gana un criterio nuevo en `docs/05-tickets-trabajo.md`. Está registrada en `docs/05` y `docs/06` §10; no se escribe ADR porque la alternativa descartada no tiene evidencia propia más allá de esa ausencia.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Una prueba que pasa en Windows puede fallar en el corredor Linux por tiempos: el primer pipeline mostró una carrera de TKT-008b que ningún desarrollo local había visto. Reproducirla exigió un contenedor con CPU limitada (`docker run --cpus=0.4`) | `Armazon.test.tsx`: 3 de 4 ejecuciones en rojo con 0.4 CPU antes del arreglo; 8 de 8 en verde después | Todo ticket con pruebas de interfaz asíncronas; `conv-docker` y `conv-frontend-react` |
| Las acciones de GitHub se pueden fijar por SHA sin `gh` autenticado: `git ls-remote --tags` basta cuando las etiquetas son ligeras | SHA de las cuatro acciones, verificados después por `auditor-seguridad` | Regla común 2 del diseño y cualquier workflow nuevo |
| `unittest -v` imprime la primera línea del docstring de cada prueba; una guarda que busca una cadena en esa salida da falsos rojos si algún docstring la contiene | `skipped=` en tres docstrings de `test_definicion_ci.py` | Toda guarda por texto sobre la salida de una suite |
| `zizmor` por omisión no marca `concurrency` ni lo que `--persona auditor` y `pedantic` añaden; `uvx zizmor --offline` no llega a las auditorías que necesitan token | Salida de `zizmor` en las auditorías de seguridad | Mantenimiento de los workflows |
| Para pruebas de definición sin analizador YAML, una comprobación por expresión regular solo vale si busca dentro del bloque de su trabajo, ignora comentarios y se acompaña de mutantes: los primeros 52 casos dejaban pasar nueve formas de desactivar una compuerta | Hallazgo F001 de código y sus nueve mutantes | `tools/tests/test_definicion_ci.py` y las partes b, c y d |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | `/sdd-ejecutar TKT-009` se lanzó sobre un ticket paraguas ya partido en cuatro. El gate no lo detecta por sí solo: el estado `LISTO PARA EJECUTAR` del paraguas es válido y nada dice que no se ejecuta. Se detectó leyendo su `_index.md` | Media |
| `herramienta` | `gh` no estaba autenticado y el diseño daba por hecho `gh api` (regla común 2) y la apertura de PR. Un despacho entero se perdió esperando ese comando, y los PR de ensayo y las ejecuciones del pipeline dependen de una sesión que el agente no puede abrir. El gate de `/sdd-ejecutar` debería comprobar `gh auth status` si el diseño usa GitHub | Media |
| `guardrail` | Un agente ejecutó `contrasenas_roles` y sembró un usuario de humo contra la base de desarrollo de la persona usuaria, y dejó el árbol local de `frontend/node_modules` roto (`EPERM`). Las filas con efectos sobre el entorno local deberían declararlo en el diseño y usar una base y un árbol desechables | Alta |
| `agente` | Las reauditorías acotadas pierden el informe anterior: el auditor no puede reclasificar «Resuelto, Persiste, Nuevo» sin el texto literal. Hay que pasarle sus hallazgos previos en el encargo. Y cada ciclo de corrección de documentación trajo un Menor nuevo sobre el texto que el ciclo anterior había escrito, incluso aplicando el texto literal que el propio auditor dictó (`CLAUDE.md:97`, cuatro versiones). Quinta vez que se ve este patrón | Media |
| `agente` | El desarrollador (`haiku`) añadió sin que se pidiera la versión fija de `uv` en `setup-uv` y quitó `-v` del paso de la suite; el orquestador tuvo que revisar ambas desviaciones. El primer caso se revirtió; el segundo era correcto y se documentó | Baja |
| `guardrail` | La auditoría de código de `/sdd-ejecutar` y la de `/sdd-revisar` coincidieron esta vez, pero la primera encontró un Mayor (compuertas desactivables) que 52 pruebas y la autoverificación del tester no veían. Se repite el patrón de que la revisión con mutación exploratoria sobre el artefacto real encuentra lo que los mutantes del diseño no | Media |
| `plantilla` | El diseño estimaba unas 265 líneas para la parte a y `test_definicion_ci.py` acabó en unas 2,300. Las estimaciones de líneas de las pruebas de definición no cuentan los mutantes, que son la mayor parte | Media |
| `modelo` | Los dos primeros despachos de `haiku` al `ingeniero-devsecops` cerraron sin subir a `sonnet`. La corrección del ciclo 1 de código fue en `sonnet` porque escribía lógica de pruebas nueva, y las reauditorías de Menores en `haiku`, que por no conservar contexto necesitaron el historial en el encargo | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Petición espuria a `GET /sesion` tras cerrar sesión (`Armazon.tsx`, `salir()`) | Inocua con un servidor real; evitarla es un cambio de producción fuera de alcance | Pequeño ticket de TKT-008 |
| Falta `concurrency:` en `ci.yml` | El diseño no lo pedía y cambia el comportamiento de las ejecuciones | Aprovechar TKT-009b o TKT-062 |
| `zizmor` sin lockfile para sus transitivas; cachés de `setup-uv` y `setup-node` por omisión | Riesgo bajo mientras no haya un workflow de publicación | Revisar con TKT-058 o el primer workflow de despliegue |
| La lista blanca de opciones de pytest rechaza opciones legítimas futuras; `PYTEST_ADDOPTS: -k nada` en `env:` pasaría | Heurística declarada como límite en el docstring del módulo | Ampliar cuando una parte posterior añada opciones |
| `ruff` no corre sobre `tools/` en el pipeline | Fuera del alcance de esta parte | Ticket de calidad de `tools/` |
| `test_definicion_ci.py` mide unas 2,300 líneas (2,308 al cierre) | El tamaño viene de los mutantes; partirlo no cambia lo que cubre | Partir en `test_definicion_ci_trabajos.py` y `_seguridad.py` si crece más con las partes b, c y d |
| El comentario de `frontend/playwright.config.ts` dice `npx playwright install chromium` sin `--with-deps` | Está fuera del diff de esta parte | Corregir cuando se toque ese archivo |
| El texto «TKT-009» de la parte c sigue vivo en `docs/06` §9, `tools/README.md:61` y la ficha de TKT-069; `CLAUDE.md:78` conserva su marca | Pertenecen a TKT-009c | TKT-009c |
| TC-58 del diseño dice «26 `FALTA`» y la fila C5, 27 | Es de la parte c | Corregir en TKT-009c |
| La prueba `Armazon.test.tsx` repite la desestructuración del doble en dos lugares | Cosmético | — |
| Segunda puerta `cimenta/<m>/__init__.py`, contratos para `tests/` y `servidor/`, `interrogate`, *digest* de Compose, política de versiones de `eslint`, y un `it.skip` que nombra un escenario | Heredado de la lista de tickets futuros de TKT-009 | Ver `sdd/tickets/tkt-009/_index.md` |

## Pull request

**Título:** `TKT-009a · Pipeline de pruebas y fronteras`
**Origen:** `agent` (pasa a `agent+human-review` cuando una persona lo revise)
**Cuerpo:**

> **Qué.** Crea `.github/workflows/ci.yml`, que corre en cada pull request ocho trabajos con permisos de solo lectura y sin secretos: `backend` (formato, lint, tipos, regla de `float` y pruebas contra PostgreSQL con cobertura), `fronteras` (`lint-imports`), `contrato-api` (reservado para TKT-061), `frontend`, `humo` (Playwright contra una base migrada), `herramientas`, `workflows` (`zizmor`) y `documentacion` (`verificar_docs.py`). Añade `tools/tests/test_definicion_ci.py`, con mutantes que demuestran que cada compuerta se pone en rojo si alguien la desactiva, y `pytest-cov`. Retira las marcas «desde TKT-009» de las reglas 1 a 3 de `CLAUDE.md`. Incluye, fuera de alcance y con aprobación, el arreglo de una prueba de TKT-008b que fallaba en Linux.
>
> **Por qué.** `CLAUDE.md` promete que `import-linter`, `ruff` y el verificador de `float` hacen fallar el pipeline, y hasta ahora no existía. Es la primera de cuatro partes de TKT-009; fusiona antes que c, b y d.
>
> **Criterios cubiertos.** `CA-1` a `CA-5`, `CA-9`, `CA-12`, `CA-R1`, `CA-R2`, `CA-R4` y la parte de `CA-15` de esta parte.
>
> **Cómo verificarlo.** El pipeline del propio PR está en verde sobre el último commit de código y de configuración, `f2bb169` (`actions/runs/40798645609`); los commits posteriores solo tocan registros de `sdd/`. En local: `cd backend && uv run ruff check . && uv run mypy . && uv run lint-imports && uv run python -m herramientas.verificar_float`, `uv run pytest`, `python -m unittest discover -s tools/tests` y `python tools/verificar_docs.py`. Las compuertas se ensayaron en dos PR en borrador, ya cerrados sin fusionar, con las ejecuciones `40791191850` y `40791201877`.
>
> **Aviso a quien revisa.** La rama pasa por una excepción de alcance registrada en `_index.md`: `Armazon.test.tsx`. No toca `docs/api/openapi.yaml`.
>
> 🤖 Generated with [Claude Code](https://claude.com/claude-code)
