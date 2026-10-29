# Design · TKT-009 · Pipeline de integración continua

> [← index](_index.md) | [← spec](spec.md) | Siguiente: impl (pendiente)

## Estrategia

Un único flujo de GitHub Actions, `.github/workflows/ci.yml`, disparado por `pull_request` y con `permissions: contents: read`, ejecuta en trabajos separados los mismos comandos que [`docs/arranque-local.md`](../../../docs/arranque-local.md) ya documenta y que hoy solo corre quien se acuerda. Lo que no existe se resuelve primero con lo nativo de la plataforma —Dependabot, escaneo de secretos, `npm audit --audit-level=high`, `node-version-file`— y después con herramientas ya decididas o de terceros sin código propio —`zizmor` para la seguridad de los workflows, `lychee`, `markdownlint-cli2`, `Vale`, `mermaid-cli`—. Solo dos piezas son código nuevo en `tools/`, y las dos porque ninguna herramienta lo hace: el verificador de escenarios de [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md) y el filtro de severidad de `pip-audit`, que no reporta severidad. Cada compuerta nace en rojo dos veces: con su prueba en `tools/tests/` o su mutante local, y con una rama de ensayo que la viola en el propio pipeline.

**El ticket no cabe en una sesión.** El orden de implementación suma unas **1,230 líneas escritas a mano**, más la limpieza de la línea base documental, frente al tope orientativo de ~400. Se propone partirlo en cuatro, como se hizo con TKT-008; la sección siguiente dice cómo. El diseño está escrito por bloques que coinciden con esa partición, así que vale igual si la persona que aprueba prefiere ejecutarlo entero.

## Propuesta de partición

| Parte | Musts | Qué entrega | Líneas estimadas | Depende de |
|---|---|---|---|---|
| **TKT-009a** · Pipeline de pruebas y fronteras | M1, M2, M3, M4, M6, M9, M12 (parcial) | `ci.yml` con los trabajos de backend, fronteras, contrato reservado, frontend, humo, herramientas, `verificar_docs` y `zizmor`; `pytest-cov` | ~265 | — |
| **TKT-009b** · Cadena de suministro | M7, M8, M12 (parcial) | `pip-audit` con filtro de severidad, `npm audit`, Dependabot, escaneo de secretos y protección de empuje, ADR de severidad | ~300 | 009a |
| **TKT-009c** · Verificador de escenarios | M5, M12 (parcial) | `tools/verificar_escenarios.py`, sus pruebas, `tools/historias_activas.txt`, ADR de la política | ~440 | 009a |
| **TKT-009d** · Calidad documental | M10, M11, S1, M12 (parcial) | `markdownlint-cli2`, `Vale`, `lychee`, `mermaid-cli`, cron semanal, línea base limpia, ADR de `Vale` en español | ~225, más la limpieza | 009a |

TKT-009c queda algo por encima del tope y no se parte más: el verificador y sus pruebas son una unidad, y las pruebas, que construyen documentos de ejemplo, son la mitad.

**Las partes b, c y d no son independientes entre sí.** Además de `ci.yml`, las tres editan `docs/06-stack-tecnologico.md`, `tools/README.md` y `docs/arranque-local.md`, y la limpieza de la parte d (D3 y D4) recorre todo `docs/` y `sdd/`, incluido `docs/04-historias-usuario.md`, que la parte c lee y modifica. Por eso el orden de fusión es fijo: **a → c → b → d**, con d siempre al final para que su limpieza se aplique sobre la documentación ya escrita por las otras tres. Una parte posterior se rebasa sobre la anterior ya fusionada antes de su propio PR. Ninguna limpieza de la parte d toca el título de un escenario (`**Escenario N: … **`), que es el texto que leen `verificar_docs.py` y el verificador de escenarios: si `--fix` lo modificara, ese cambio se revierte a mano en D3.

**Partir es una decisión de alcance y la toma el usuario en el gate**: si se aprueba, `/sdd-definir` reparte la spec en cuatro, conservando los criterios tal como están, y la fila A0 registra la partición en `docs/05-tickets-trabajo.md`; si no, A0 no se ejecuta y las demás filas siguen el orden de abajo.

## Supuestos abiertos resueltos en el diseño

| # | Resolución | Peldaño |
|---|---|---|
| `A-2` | Cobertura **sin umbral**: `pytest-cov` imprime el resumen en el registro y sube `cobertura.xml` como artefacto. Sin `--cov-fail-under`. Fijar un mínimo es otro ticket, con una base medida | 1 · YAGNI |
| `A-3` | `pip-audit` **no da severidad**: su salida JSON trae `id`, `fix_versions`, `aliases` y `description`, y ninguna opción filtra por gravedad (consultado con Context7, pip-audit 2.10). La severidad sale del aviso de GitHub (`GHSA-…`) en OSV, campo `database_specific.severity`. `HIGH` y `CRITICAL` fallan; `MODERATE` y `LOW` se informan; sin `GHSA` o sin severidad, **falla** (política de fallo cerrado). En el cliente basta lo nativo: `npm audit --audit-level=high` informa todo y solo devuelve código distinto de cero desde `high` | 5 para Python, 2 para npm |
| `A-4` | El escaneo de secretos y la protección de empuje son **ajustes del repositorio**. Se verifican con `gh api` y con un empuje de ensayo que la persona dueña del repositorio hace con un token real revocado; la evidencia queda en `impl.md`. Si el repositorio es privado y no tiene *Secret Protection*, se escala: ver fila B5 | 2 · nativo |
| `A-5` | Línea base desconocida: la fila D2 la **mide** antes de tocar nada. Si quedan **más de 120 hallazgos** que `--fix` no corrige, se detiene la parte d y se escala proponiendo separar la limpieza en su propio ticket | — |
| `A-6` | La fase 2 empieza cuando `tools/historias_activas.txt` contiene la línea exacta `fase 2`. Sin ella, los escenarios de fase 2 no cuentan. Como las historias, la línea no sale del archivo: el verificador falla si la base del PR la tenía y el PR la quita | 4 · cambio mínimo sobre el archivo de ADR-012 |
| `A-7` | Un escenario se retira con el segmento ` · retirado por TKT-0NN` en su título, la misma forma que ya usa ` · fase 2`: `**Escenario 14: Mano de obra y avance simulados, y rotulados como tales · fase 1 · retirado por TKT-069**`. El texto del escenario no cambia. Una nota en prosa, sin el segmento, no retira nada. Hoy no se retira ninguno: lo hará TKT-069 | 4 · extiende una convención existente |
| `A-8` | El verificador busca en `backend/tests/` (`test_*.py`), `frontend/src/` y `frontend/scripts/` (`*.test.ts`, `*.test.tsx`) y `frontend/e2e/` (`*.spec.ts`), saltando `node_modules`. En pytest lee `def test_…`; en Vitest y Playwright, el título de `it(…)`, `test(…)` y `describe(…)`. El nombre de un test de historia en TypeScript sigue la forma de los de fundación: `"hdu002_esc04 · …"` | 5 |
| `A-9` | **Python 3.14 en CI**, con el comando literal `uv sync --locked --python 3.14`; los `uv run` posteriores usan el `.venv` ya creado, incluido el `webServer` de Playwright. Node desde `engines` con `node-version-file: frontend/package.json`, que `actions/setup-node` lee (consultado con Context7). Sin matriz 3.13: se acepta que un fallo solo en 3.13 no se vea. `backend/.python-version` se descarta aquí: cambia el comportamiento local y TKT-001 lo dejó a una decisión propia | 3 · reuso del comando documentado |
| `A-10` | No es de diseño. Se cierra en `/sdd-completar` | — |
| `A-11` | **Sin el estilo Microsoft**, que es de inglés y marcaría casi cada frase. Estilos activos: `Vale` (solo `Vale.Terms` y `Vale.Repetition`; `Vale.Spelling = NO`, porque su diccionario es inglés) y uno propio, `Cimenta`, con una regla `Cimenta.Vocabulario` de sustitución para las variantes erradas del glosario. Todo a nivel `warning`. Ortografía española con Hunspell, descartada: marcaría cada término técnico en inglés. Se registra en ADR | 3 y 5 |

**Interpretación que se señala en el gate.** `CA-13` esc. 1 pide que los cuatro verificadores documentales pasen «sin avisos». `tools/verificar_docs.py` emite por diseño el aviso de `RNF` huérfanos sin fallar ([`tools/README.md`](../../../tools/README.md)), y convertirlo en error cambiaría un verificador que el ticket no debe cambiar. El diseño aplica «sin avisos» a `markdownlint-cli2`, `Vale` y `lychee`, y deja el aviso de `verificar_docs.py` como está `(asumido)`.

**Segunda interpretación que se señala en el gate.** `CA-11` esc. 3 pide que las contraseñas de desarrollo de `.env.example` estén «declaradas como excepción documentada». El diseño **no crea ninguna excepción** en el escaneo: los patrones de proveedor de GitHub no reconocen los valores `solo-desarrollo-*` ni la contraseña de prueba, y una exclusión por ruta (`paths-ignore`) dejaría fuera cualquier otro secreto que alguien pegara en ese archivo. Si una alerta genérica marcara alguno de esos valores, se descarta **esa alerta concreta** como «usada en pruebas», citando este diseño, y la documentación de la excepción es la nota de `docs/06-stack-tecnologico.md` §6.4 (fila B7). Es una reinterpretación del criterio `(asumido)`: si la persona que aprueba quiere un archivo de excepción, se vuelve a diseñar B4.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `.github/workflows/ci.yml` | 5 · objeto nuevo | No hay ningún workflow. GitHub Actions es la plataforma decidida en [stack §10](../../../docs/06-stack-tecnologico.md#integración-continua) |
| Trabajos `backend`, `fronteras`, `frontend` | 3 · reuso | Los comandos son los de `arranque-local.md`, sin variantes propias del pipeline |
| `pytest-cov` en el grupo `dev` | 5 · dependencia mínima | Cobertura exige una herramienta; `pytest-cov` es la integración estándar con el `addopts` actual |
| Trabajo `contrato-api` | 5 · mínimo | Un paso que imprime que está reservado. `needs: backend`, y `frontend` lo necesita a él |
| Trabajo `humo` | 3 · reuso | `npm run e2e`, Compose y `herramientas.contrasenas_roles` existen. El informe HTML se pide con `-- --reporter=list,html`, sin tocar `playwright.config.ts` (2 · nativo) |
| Paso de pruebas de `tools/` con guarda de saltos | 2 · nativo | `unittest` imprime `skipped=N`; un `grep` sobre su salida falla el paso. No hace falta tocar ninguna prueba |
| `tools/verificar_docs.py` en el pipeline | 3 · reuso | Ya devuelve 1 ante cualquier problema, incluida la codificación que TKT-001 dejó para TKT-009 |
| `zizmor` sobre `.github/workflows/` | 3 · reuso de terceros | Detecta workflows sin `permissions`, `pull_request_target`, acciones sin fijar por SHA, credenciales persistidas e inyección de plantillas. Escribir esas comprobaciones sería código propio sin razón |
| `tools/tests/test_definicion_ci.py` | 5 · pequeño | Los criterios «cuando se lee su definición» (`CA-1`, `CA-3` a `CA-5`, `CA-9`, `CA-11`, `CA-12` esc. 1 y 2, `CA-14`) no tienen otro oráculo ejecutable. Comprueba estructura —trabajos, orden, comandos, permisos y disparadores—; el fijado por SHA lo deja a `zizmor` |
| `pip-audit` en el grupo `dev` | 3 · reuso de `uv.lock` | Fija su versión como las demás; cierra la deuda de TKT-001 y TKT-003 |
| `tools/severidad_pip_audit.py` | 5 · objeto nuevo | `pip-audit` no da severidad (`A-3`) y `RNF-08` distingue «alta» |
| `npm audit --audit-level=high` | 2 · nativo | La opción hace exactamente lo que pide `CA-10` |
| `.github/dependabot.yml` | 2 · nativo | Tres ecosistemas: `uv`, `npm`, `github-actions` |
| Escaneo de secretos y protección de empuje | 2 · nativo | Ajuste del repositorio; `gitleaks` se descarta salvo que el ajuste no esté disponible |
| Excepción de las credenciales de `.env.example` | 1 · YAGNI | Ningún archivo de excepción: los patrones de proveedor no reconocen `solo-desarrollo-*`. Si una alerta genérica las marcara, se descarta **esa alerta** como «usada en pruebas», citando este diseño; nunca `paths-ignore`, que excluiría el archivo entero |
| `tools/verificar_escenarios.py` | 5 · objeto nuevo | Lo prevé ADR-012 y no existe herramienta. Copia los dos patrones de `verificar_docs.py` (`^## (HDU-\d{3}) · ` y `\*\*Escenario (\d+): `) en lugar de importarlo: allí están dentro de funciones con estado global |
| `tools/historias_activas.txt` | 5 · objeto nuevo | Lo exige ADR-012. Arranca sin historias |
| Marcador de fase 2 | 4 · cambio mínimo | Una línea en el mismo archivo, que se mantiene en el mismo momento que las historias |
| Nota de retiro | 4 · cambio mínimo | Segmento del título, como ` · fase 2` |
| Comparación con la base del PR | 2 · nativo | `git show <sha base>:tools/historias_activas.txt`, con `fetch-depth: 0` |
| `.markdownlint-cli2.jsonc`, `.vale.ini`, `.vale/styles/`, `lychee.toml` | 3 · reuso | Herramientas ya decididas en [convenciones §10](../../../docs/convenciones.md#10-validación-de-documentación-en-ci); solo se configuran |
| Regla `Cimenta.Vocabulario` | 5 · pequeño | Ninguna regla de terceros conoce *tablaroca* |
| `.github/workflows/enlaces.yml` | 2 · nativo | Disparador `schedule` de GitHub Actions |
| `mermaid-cli` en el trabajo de documentación | 3 · reuso | Lo prevé [stack §9](../../../docs/06-stack-tecnologico.md#verificadores-propios); `tools/extraer_mermaid.py` sigue para uso local |
| `.github/puppeteer-config.json` | 2 · nativo | `{"args": ["--no-sandbox"]}`, el arreglo documentado por `mermaid-cli` para Chromium en Linux |

Ningún objeto paró en el peldaño 4 tocando un invariante ni una regla de `CLAUDE.md`.

## Reglas comunes de la ejecución

Valen para todas las filas. Son decisiones tomadas: quien ejecuta no las reabre.

1. **Corredor fijo:** `runs-on: ubuntu-24.04` en todos los trabajos. Cada trabajo lleva `timeout-minutes` (backend 25, humo 20, el resto 15).
2. **Acciones fijadas por SHA.** Cada `uses:` apunta al SHA del commit de la última etiqueta estable de la versión mayor vigente el día de la fila, con la etiqueta en un comentario. El SHA se obtiene con `git ls-remote https://github.com/<dueño>/<acción>.git "refs/tags/<etiqueta>^{}"` y se anota en `impl.md`. La forma `^{}` pide el commit al que apunta una etiqueta anotada; si la etiqueta es ligera, esa línea no aparece y vale la del SHA sin sufijo. Se usa `git ls-remote` en lugar de `gh api` (ver «Ajustes registrados» en la parte a). Ejemplo verificado con Context7: `astral-sh/setup-uv@18d369b23da25a81e9458561248e1aafff6a70fa # v10.3.1`.
3. **Herramientas fijadas por versión exacta** (`zizmor`, `vale`, `markdownlint-cli2`, `@mermaid-js/mermaid-cli`, `lychee`): la última estable publicada el día de la fila, escrita literal en el workflow y en `impl.md`.
4. **`actions/checkout` con `persist-credentials: false`** en todos los trabajos. El de herramientas usa además `fetch-depth: 0`.
5. **Sin secretos.** Ningún workflow lee `secrets.*`. El `.env` del humo se construye con `cp .env.example .env`.
6. **Pasos de comprobación con `if: ${{ !cancelled() }}`** dentro de `backend`, `frontend` y `documentacion`, para que un PR vea todas las compuertas rotas de un trabajo a la vez y no solo la primera. El trabajo termina en rojo si cualquiera falló.
7. **Ningún `continue-on-error`** en el pipeline: una compuerta que no falla está desactivada.
8. **Valores de GitHub en `run:` siempre por `env:`**, nunca interpolados con `${{ }}` dentro del guion: es lo que `zizmor` marca como inyección de plantillas.
9. **Todo paso con una tubería (`|`) declara `shell: bash`.** Solo así GitHub lo ejecuta con `-eo pipefail`; con el intérprete por omisión (`bash -e {0}`) el paso toma el estado del último comando de la tubería y una compuerta rota terminaría en verde.

## Objetos por zona

No hay capas de la aplicación en alcance: no se toca `backend/cimenta/` ni `frontend/src/`.

### Pipeline · `.github/`

Esqueleto de la cabecera de `ci.yml`, que fija lo que `CA-12` exige:

```yaml
name: CI
on:
  pull_request:
permissions:
  contents: read
jobs:
  backend:
    name: Backend · formato, lint, tipos, float y pruebas
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    defaults:
      run:
        working-directory: backend
    steps: []   # ver la tabla de trabajos
```

| Trabajo (`id`) | `needs` | Pasos, en orden | Parte |
|---|---|---|---|
| `backend` | — | checkout · setup-uv · `uv sync --locked --python 3.14` · `uv run ruff format --check .` · `uv run ruff check .` · `uv run mypy .` · `uv run python -m herramientas.verificar_float` · `uv run pytest --cov=cimenta --cov=tipos_base --cov=contrato_error --cov=servidor --cov-report=term --cov-report=xml:cobertura.xml --junitxml=pytest.xml` · `upload-artifact` de `backend/cobertura.xml` y `backend/pytest.xml` con `if: always()`, `if-no-files-found: error`, nombre `backend-pruebas`, 14 días | a |
| `fronteras` | — | checkout · setup-uv · `uv sync --locked --python 3.14` · `uv run lint-imports`, todo con `working-directory: backend` | a |
| `contrato-api` | `backend`, con `if: ${{ !cancelled() }}` | Nombre «Prueba de contrato de la API · reservado para TKT-061». Un único paso: `echo "Reservado para TKT-061: sin contenido todavía."` | a |
| `frontend` | `contrato-api`, con `if: ${{ !cancelled() }}` | checkout · setup-uv · setup-node (`node-version-file: frontend/package.json`, `cache: npm`, `cache-dependency-path: frontend/package-lock.json`) · `uv sync --locked --python 3.14` en `backend/` · en `frontend/`: `npm ci` · `npm run lint` · `npm run typecheck` · `npm test` · `npm run tipos:verificar` | a |
| `humo` | — | checkout · setup-uv · setup-node · `cp .env.example .env` · `docker compose up -d --wait db` · en `backend/`: `uv sync --locked --python 3.14`, `uv run --env-file ../.env alembic upgrade head`, `uv run --env-file ../.env python -m herramientas.contrasenas_roles` · en `frontend/`: `npm ci`, `npx playwright install --with-deps chromium`, `npm run e2e -- --reporter=list,html` · `upload-artifact` de `frontend/playwright-report/` y `frontend/test-results/` con `if: failure()`, nombre `humo-playwright` | a |
| `herramientas` | — | checkout con `fetch-depth: 0` · setup-uv · `uv sync --locked --python 3.14` en `backend/` · paso con `shell: bash` declarado explícitamente, que es lo que hace que GitHub lo ejecute con `bash --noprofile --norc -eo pipefail {0}`: `uv run --no-project --python 3.14 python -m unittest discover -s tools/tests 2>&1 \| tee "$RUNNER_TEMP/tools.txt"`. Sin `shell: bash`, el intérprete por omisión es `bash -e {0}`, sin `pipefail`, y el estado del paso sería el de `tee`, siempre 0: una prueba rota no lo pondría en rojo · `! grep -q "skipped=" "$RUNNER_TEMP/tools.txt"`. La regla vale para todo paso del pipeline que use una tubería, también el de Vale de la parte d. La parte c añade el paso del verificador de escenarios | a, c |
| `workflows` | — | checkout · setup-uv · `uvx zizmor@<versión> --offline .github/workflows` | a |
| `documentacion` | — | checkout · `python3 tools/verificar_docs.py`. La parte d añade `markdownlint-cli2`, `Vale`, `lychee` y `mermaid-cli` | a, d |
| `dependencias` | — | checkout · setup-uv · setup-node · en `backend/`: `uv export --locked --all-groups --no-emit-project --format requirements.txt -o "$RUNNER_TEMP/req.txt"` · `uv run pip-audit -r "$RUNNER_TEMP/req.txt" --require-hashes --disable-pip --strict -f json -o "$RUNNER_TEMP/pip-audit.json"` sin cortar el guion si devuelve 1 (`\|\| true`) · `python3 tools/severidad_pip_audit.py "$RUNNER_TEMP/pip-audit.json"` · en `frontend/`: `npm audit --audit-level=high` | b |

El paso de `pip-audit` admite que termine en 1 porque así señala que encontró vulnerabilidades; quien decide es `severidad_pip_audit.py`, que falla con código 2 si el JSON no existe o no se puede leer, de modo que un error de `pip-audit` no pasa en verde. Una excepción a una vulnerabilidad concreta se declara con `--ignore-vuln <ID>` en ese paso y un comentario que nombra quién la decidió; el ticket arranca sin ninguna.

**`.github/workflows/enlaces.yml`** (parte d): `on: schedule: - cron: "0 13 * * 1"` (lunes a las 07:00 de la Ciudad de México) y `workflow_dispatch`; `permissions: contents: read`; un trabajo con checkout y `lycheeverse/lychee-action` con la misma configuración que el del PR.

**`.github/dependabot.yml`** (parte b): versión 2, tres entradas semanales: `package-ecosystem: "uv"` en `/backend`, `"npm"` en `/frontend` y `"github-actions"` en `/`. Si GitHub rechaza el ecosistema `uv` al validar el archivo, se sustituye por `"pip"` en la misma fila y se anota.

### Herramientas · `tools/`

**`tools/severidad_pip_audit.py`** (parte b). Biblioteca estándar, como el resto de `tools/`.

```python
SEVERIDADES_QUE_FALLAN = frozenset({"HIGH", "CRITICAL"})
URL_OSV = "https://api.osv.dev/v1/vulns/{}"

@dataclass(frozen=True)
class Hallazgo:
    paquete: str
    version: str
    identificador: str            # el `id` de pip-audit
    aviso: str | None             # el primer GHSA-… entre el id y sus alias
    severidad: str                # LOW · MODERATE · HIGH · CRITICAL · DESCONOCIDA

def leer_informe(texto: str) -> list[dict]: ...   # acepta {"dependencies": [...]} y la lista antigua
def consultar_osv(identificador: str) -> dict: ... # urllib, timeout de 15 s
def clasificar(dependencias: list[dict], consultar: Callable[[str], dict]) -> list[Hallazgo]: ...
def main(argv: Sequence[str] | None = None) -> int: ...
```

Una línea por hallazgo: `ALTA  django 3.2  GHSA-xxxx-xxxx-xxxx (CVE-…, PYSEC-…) → falla el pipeline (RNF-08)`, con las etiquetas `BAJA`, `MEDIA`, `ALTA`, `CRÍTICA` y `DESCONOCIDA`. Termina en 0 si nada falla, en 1 si algún hallazgo es `HIGH`, `CRITICAL` o `DESCONOCIDA`, y en 2 si el JSON falta, no se puede leer o la consulta a OSV falla.

**`tools/verificar_escenarios.py`** (parte c). Biblioteca estándar.

```python
CARPETAS_DE_TESTS = ("backend/tests", "frontend/src", "frontend/scripts", "frontend/e2e")
PATRON_HDU = re.compile(r"^(?:test_)?hdu(\d{3})_esc(\d{2,})(?=$|[_\s·])")
PATRON_FUNDACION = re.compile(r"^(?:test_)?tkt\d{3}[a-z]?_car?\d+_esc\d+(?=$|[_\s·])")

@dataclass(frozen=True)
class Escenario:
    historia: str                 # "HDU-002"
    numero: int
    titulo: str
    fase: int                     # 1 o 2
    retirado_por: str | None      # "TKT-069" o None

@dataclass(frozen=True)
class NombreDeTest:
    archivo: str                  # ruta relativa con /
    linea: int
    nombre: str

class EntradaInvalida(Exception): ...

def leer_historias(texto: str) -> dict[str, list[Escenario]]: ...
def leer_activas(texto: str) -> tuple[frozenset[str], bool]: ...   # (historias, fase 2 iniciada)
def recolectar_tests(raiz: Path) -> list[NombreDeTest]: ...
def clasificar(historias, activas, fase_2, tests, base: tuple[frozenset[str], bool] | None) -> Informe: ...
def main(argv: Sequence[str] | None = None) -> int: ...   # --raiz, --activas-base
```

- **Fase de un escenario.** Es 2 si algún segmento del título, separado por ` · `, es `fase 2`; si no, es 2 cuando la columna `Fase` de su historia en la tabla «El conjunto» vale `2`; en cualquier otro caso, 1. Así `1+2` sin marca da fase 1 (`CA-7` esc. 3) y HDU-007 a HDU-009 quedan en fase 2.
- **Retiro.** Un segmento `retirado por TKT-\d{3}` en el título.
- **Qué cuenta.** Un escenario es exigido si su historia está activa, no está retirado y su fase es 1, o es 2 con la fase 2 iniciada.
- **Tests.** En Python, `^\s*def (test_\w+)\s*\(`; en TypeScript, el primer argumento de cadena de `it(`, `test(` o `describe(`. Un nombre que cumple `PATRON_HDU` cubre su escenario; uno que cumple `PATRON_FUNDACION` se cuenta como «de fundación» y nunca es error; cualquier otro se ignora.
- **Errores.** Un test que nombra una historia o un escenario inexistentes; una historia, o la línea `fase 2`, presentes en `--activas-base` y ausentes del archivo actual.
- **Salida.** Una línea por hecho, con estas etiquetas exactas, y un resumen final:

```text
FALTA      HDU-002 esc. 4 · La requisición excede el importe presupuestado
PENDIENTE  HDU-007 · <n> escenarios · historia sin ticket en curso
PENDIENTE  HDU-002 esc. 14 · fase 2 sin iniciar
RETIRADO   HDU-006 esc. 14 · TKT-069
ERROR      backend/tests/test_x.py:12 · test_hdu099_esc01_x nombra una historia que no existe (hdu099)
ERROR      HDU-003 salió de tools/historias_activas.txt: una historia no sale nunca (ADR-012)
Escenarios: 162 · exigidos 0 · cubiertos 0 · faltan 0 · pendientes 162 · retirados 0 · tests HDU 0 · tests de fundación N
```

- **Códigos.** 0 si no hay `FALTA` ni `ERROR`; 1 si hay alguno; 2 si la entrada está mal formada: una línea de `historias_activas.txt` que no es `HDU-\d{3}`, `fase 2`, comentario `#` o vacía, una historia activa que no existe, o una historia sin fila en la tabla «El conjunto».

**`tools/historias_activas.txt`** (parte c). Tres líneas de comentario que dicen qué es, quién lo actualiza (la planificación de cada sprint) y que ninguna historia sale nunca; ninguna historia y ninguna línea `fase 2`.

**Paso en `herramientas`** (parte c): con `BASE: ${{ github.event.pull_request.base.sha }}` en `env`, si `git cat-file -e "$BASE:tools/historias_activas.txt"` responde, `git show` la vuelca a `$RUNNER_TEMP/activas_base.txt` y se pasa como `--activas-base`; después, `python3 tools/verificar_escenarios.py`.

### Dependencias de desarrollo · `backend/pyproject.toml`

`uv add --dev pytest-cov` (parte a) y `uv add --dev pip-audit` (parte b), con el rango `>=` que ya usa el grupo. Nada más cambia en `pyproject.toml`: ni `[tool.importlinter]` ni `[tool.pytest]`.

### Configuración de documentación (parte d)

**Alcance común** de las tres herramientas: `docs/**/*.md`, `sdd/**/*.md`, `README.md`, `CLAUDE.md` y `tools/README.md`. Fuera quedan `.claude/` y `Doc de contexto/`.

| Archivo | Contenido decidido |
|---|---|
| `.markdownlint-cli2.jsonc` | `config`: `default: true`; `MD013: false` (la prosa no se parte en líneas); `MD033: false` (tablas con `<br>`); `MD036: false` (los títulos de escenario en negrita son el formato que leen `verificar_docs.py` y el verificador de escenarios); `MD024: { siblings_only: true }`; `MD060: false` (alineación de tablas). `ignores`: `**/node_modules/**`, `Doc de contexto/**`. Sin `globs`: el comando los recibe |
| `.vale.ini` | `StylesPath = .vale/styles` · `MinAlertLevel = suggestion` · `Vocab = Cimenta` · sección `[*.md]` con `BasedOnStyles = Vale, Cimenta`, `Vale.Spelling = NO`, `Vale.Terms = warning`, `Vale.Repetition = warning`, `Cimenta = warning` |
| `.vale/styles/config/vocabularies/Cimenta/accept.txt` | `[Tt]ablaroca` · `[Dd]estajos?` · `[Pp]erfacinta` · `[Aa]ntepechos?` · `[Cc]ajillos?` · `[Pp]lafón` · `[Pp]lafones` · `[Rr]edimix` · `CIMENTA` |
| `.vale/styles/Cimenta/Vocabulario.yml` | `extends: substitution`, `level: warning`, `ignorecase: true`, mensaje «Usa '%s' en lugar de '%s' (glosario).», `swap`: `tablaroka`, `tabla roca`, `tabla-roca` → `tablaroca`; `plafon` → `plafón`; `redi mix`, `ready mix` → `redimix`; `perfa cinta`, `perfa-cinta` → `perfacinta` |
| `lychee.toml` | `exclude_path` = `node_modules`, `.venv`, `Doc de contexto`; `exclude_loopback = true`; `exclude_all_private = true`; `include_fragments = false` (las anclas las comprueba `verificar_docs.py` con el algoritmo de GitHub); `max_retries = 3`; `timeout = 20`; `accept = ["200..=206", "429"]`; `exclude` = `cimenta\.test` |
| `.github/puppeteer-config.json` | `{"args": ["--no-sandbox"]}` |

**Aviso en local, error en CI.** En local, `vale docs sdd README.md CLAUDE.md tools/README.md` informa los avisos y termina en 0, porque solo el nivel `error` cambia el código de salida (documentación de `MinAlertLevel`, consultada con Context7). En CI el paso ejecuta `vale --output=line <alcance> > "$RUNNER_TEMP/vale.txt"`, imprime el archivo y falla si el código es distinto de cero **o** el archivo no está vacío. `markdownlint-cli2` y `lychee` fallan con cualquier hallazgo en los dos sitios; en local nada los ejecuta por obligación, así que su salida es informativa.

**Pasos del trabajo `documentacion`**, tras el de `verificar_docs.py` y cada uno con `if: ${{ !cancelled() }}`: setup-node · `npx --yes markdownlint-cli2@<versión> "docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md` · setup-uv · el paso de Vale con `uvx --from vale==<versión> vale` · `lycheeverse/lychee-action` con `args: --config lychee.toml --no-progress 'docs/**/*.md' 'sdd/**/*.md' README.md CLAUDE.md tools/README.md` y `fail: true` · `npm install --no-save --prefix "$RUNNER_TEMP/mmdc" @mermaid-js/mermaid-cli@<versión>` y un bucle sobre los `.md` del alcance que contienen ```` ```mermaid ````, que ejecuta `mmdc -p .github/puppeteer-config.json -i <archivo> -o "$RUNNER_TEMP/mermaid/<archivo aplanado>.md"`, escribe `::error file=<archivo>::diagrama Mermaid inválido` por cada fallo y termina en 1 si hubo alguno.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd). En las filas de configuración, el rojo es la violación intencionada que hace fallar la compuerta, como manda la última regla del ciclo. Las pruebas de `tools/tests/` las escribe `tester-backend` en `unittest`, igual que las existentes.

**Modelo.** Ninguna fila cae en un disparador de [metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho): no hay dinero, límites, concurrencia, autorización por obra, disparadores ni permisos de un rol de la base. Todas van en `haiku`; el juicio va un escalón arriba, en el tester y en los auditores en `sonnet`. Se aplica el reintento en `sonnet` de §14.2 si una fila no cierra en dos intentos.

**Ramas de ensayo.** Cada parte demuestra sus compuertas en el pipeline con una rama `ensayo/tkt-009<parte>-compuertas` y un PR en borrador hacia la rama del ticket, que **abre la persona usuaria a mano**; el agente empuja los commits. Las violaciones nunca se fusionan: al terminar, el PR se cierra sin fusionar y la rama se borra.

### Parte a · Pipeline de pruebas y fronteras

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | **Solo si el gate aprueba partir.** Registro de la partición en `docs/05-tickets-trabajo.md`, dentro de la ficha de TKT-009, con una subsección «Partición en cuatro tickets hermanos» que sigue el precedente de TKT-008 (`#### Partición en tres tickets hermanos`, ~l.276): una ficha `##### TKT-009a` … `##### TKT-009d` por parte con su «Qué hace» y sus criterios técnicos tomados de la tabla de partición, y el orden de fusión a → c → b → d | — | `ingeniero-devsecops` | `haiku` | `python tools/verificar_docs.py` en 0; las cuatro fichas existen y suman los Musts M1 a M12 y S1 sin repetir ninguno | ✓ Hecho |
| A1 | `uv add --dev pytest-cov` en `backend/`, y en el `.gitignore` de la raíz las líneas `backend/.coverage`, `backend/cobertura.xml` y `backend/pytest.xml`, que A1, A5 y quien reproduzca el trabajo en local generan. Rojo previo: `uv run pytest --cov=cimenta -q` falla con «unrecognized arguments: --cov» | TC-01b, TC-R2a | `ingeniero-devsecops` | `haiku` | `uv sync --locked --python 3.14`; `uv run pytest --cov=cimenta --cov=tipos_base --cov=contrato_error --cov=servidor --cov-report=xml:cobertura.xml --junitxml=pytest.xml -q` en verde y `cobertura.xml` creado; `git status --porcelain` no lista ninguno de los tres archivos; `git diff backend/pyproject.toml` solo muestra la línea del grupo `dev` | ✓ Hecho |
| A2 | `tools/tests/test_definicion_ci.py` con los casos de la parte a, en rojo porque `ci.yml` no existe. Después, `ci.yml` con la cabecera y los trabajos `backend`, `fronteras`, `contrato-api` y `frontend` (~85 líneas). Los casos estáticos buscan dentro del bloque de su trabajo e ignoran líneas comentadas; con un mutante local por caso (comentar el paso, o moverlo a otro trabajo) que debe ponerlo en rojo | TC-01, TC-05, TC-06, TC-12, TC-13, TC-R1a | `ingeniero-devsecops` | `haiku` | `python -m unittest tools.tests.test_definicion_ci -v` en verde; los comandos de cada trabajo, ejecutados en local desde `backend/` y `frontend/`, terminan en 0 | ✓ Hecho |
| A3 | Trabajo `humo` | TC-08 | `ingeniero-devsecops` | `haiku` | TC-08 en verde; `npm run e2e -- --reporter=list,html` en local crea `frontend/playwright-report/index.html` | ⚠ Ajustado |
| A4 | Trabajos `herramientas`, `workflows` y `documentacion` (solo `verificar_docs.py`) | TC-23, TC-20, TC-21, TC-22, TC-R4b | `ingeniero-devsecops` | `haiku` | TC-23 en verde; `uvx zizmor@<versión> --offline .github/workflows` termina en 0; rojo de TC-20: un `ci.yml` temporal sin `permissions` en un directorio de prueba hace que `zizmor` termine distinto de cero y nombre el archivo; rojo de TC-R4b: con `uv` fuera del `PATH`, la salida de `unittest` contiene `skipped=` y la guarda devuelve 1 | ✓ Hecho |
| A5 | Mutantes locales de regresión, sin commit: la conexión de pruebas al rol propietario, y un contrato borrado de `[tool.importlinter]` | TC-R1b, TC-R2b | `tester-backend` | `sonnet` (tester) | Cada mutante pone en rojo el test nombrado en el plan; se revierte y la suite vuelve a verde. Salidas en `impl.md` | ✓ Hecho |
| A6 | Ensayo en el pipeline: ronda 1 y ronda 2 de la parte a (ver «Ensayo de compuertas») | TC-02, TC-03, TC-04, TC-07, TC-09, TC-10, TC-24 | `git-entrega` | `haiku` | Cada trabajo nombrado termina en rojo con el mensaje esperado; enlace a la ejecución y extracto del registro en `impl.md`; ronda 3 en verde | ✓ Hecho |
| A7 | Documentación y marcas de la parte a (ver «Documentación afectada»): las de las reglas 1, 2 y 3 de `CLAUDE.md` (líneas 20 a 22), no la de la línea 78, que es de la parte c | TC-70a | `ingeniero-devsecops` | `haiku` | `python tools/verificar_docs.py` en 0; búsqueda de TC-70a sin coincidencias y `CLAUDE.md:78` aún con su «(desde TKT-009)» | ✓ Hecho |
| A8 | Cierre de la parte: recuento de pruebas de backend, frontend y `tools/` frente al de antes del ticket, y búsqueda en el diff de `skip`, `xfail` y `.only` nuevos; PR de la parte con el pipeline completo en verde | TC-R4a | `tester-backend` | `sonnet` (tester) | Recuentos iguales o mayores y búsqueda sin coincidencias, en `impl.md` con el enlace a la ejecución verde | ✓ Hecho |

**Ajustes registrados al ejecutar la parte a.** Lo construido difiere del diseño en los puntos siguientes, cada uno con su motivo:

- **`herramientas` sin `-v`.** La fila de `herramientas` se escribió con `-v`, y el paso del pipeline lo ejecuta sin él. Con `-v`, `unittest` imprime el docstring de cada prueba, y un docstring que contenga `skipped=` haría que la guarda diera un falso rojo.
- **SHAs por `git ls-remote`, no por `gh api`.** La regla común 2 lo dice ahora. Así no hace falta `gh` autenticado en la máquina que fija las versiones.
- **`if-no-files-found: error`** en la subida de `backend-pruebas`. Sin esa opción, un `pytest` que no escribiera `cobertura.xml` dejaría un artefacto vacío y el trabajo en verde.
- **Prueba `Armazon.test.tsx` de TKT-008b.** Fuera de alcance y autorizada por el usuario. El pipeline mostró que `tkt008_ca07_esc07` falla en Linux con CPU escasa: el doble de sesión respondía 200 tras el cierre y repoblaba la caché. Se corrigió con `dobleSesionQueTermina` (commit `968519b`), sin cambiar aserciones ni tiempos. No hay defecto de producción.
- **Comprobaciones de las reglas comunes 6 y 7 y del pytest completo.** No estaban en el diseño. Las añadió `tester-backend` tras el hallazgo F001 (Mayor) de `auditor-codigo`, que mostró que nueve formas de desactivar una compuerta pasaban en verde.
- **Ronda 1 de ensayo: `as` de TypeScript.** La violación de la ruta de inicio de sesión lleva un `as`. Sin él, `openapi-fetch` rompía el tipado y caía también `frontend`; con él, `frontend` cayó igualmente por una prueba de componente que simula esa ruta.
- **Ronda 1 de ensayo: trabajos no previstos.** `herramientas` cayó porque TC-22 detecta `pull_request_target` en `ensayo.yml`, una segunda compuerta sobre la misma violación. `frontend` cayó por la prueba de componente citada en el punto anterior. La tabla de ensayo del diseño no recogía ninguno de los dos.
- **Ronda 2 de ensayo: `summary` nuevo.** La ronda añadió un `summary` nuevo a `GET /api/v1/sesion` en lugar de cambiar uno existente, porque ninguna ruta de `identidad` declaraba `summary=`.

Estados de la tabla: A0 a A2 y A4 a A8 quedan `✓ Hecho`. A3 queda `⚠ Ajustado`, porque `npm run e2e -- --reporter=list,html` no pudo verificarse en local; su comprobación real es el trabajo `humo` del pipeline, que ejecuta la fila A6.

### Parte b · Cadena de suministro

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B1 | `uv add --dev pip-audit` en `backend/`. Rojo previo: `uv run pip-audit --version` falla | TC-R2a | `ingeniero-devsecops` | `haiku` | `uv sync --locked --python 3.14`; `uv run pip-audit --version`; `git diff backend/pyproject.toml` solo en `dev` | Pendiente |
| B2 | `tools/tests/test_severidad_pip_audit.py` en rojo; después `tools/severidad_pip_audit.py` con las firmas de arriba | TC-30 a TC-38 | `ingeniero-devsecops` | `haiku` | `python -m unittest tools.tests.test_severidad_pip_audit -v` en verde; sobre el árbol real, el `uv export` y el `pip-audit` del trabajo seguidos del script terminan en 0 | Pendiente |
| B3 | Trabajo `dependencias` en `ci.yml` y sus casos en `test_definicion_ci.py` | TC-14 | `ingeniero-devsecops` | `haiku` | TC-14 en verde; `npm audit --audit-level=high` en `frontend/` termina en 0 sobre el árbol real; `zizmor` sigue en 0 | Pendiente |
| B4 | `.github/dependabot.yml` y sus casos, incluido el que comprueba que no existe `.github/secret_scanning.yml` ni ningún `paths-ignore` que cite `.env.example` | TC-15, TC-18 | `ingeniero-devsecops` | `haiku` | TC-15 y TC-18 en verde | Pendiente |
| B5 | Ajustes del repositorio. El agente prepara los comandos; **los ejecuta la persona dueña del repositorio**: `gh api repos/FranciscoRodSilva/IA4Devs-Proyecto-Final --jq '{visibility, security_and_analysis}'`; activa alertas de Dependabot, actualizaciones de seguridad, escaneo de secretos y protección de empuje; repite la consulta. Si el escaneo no está disponible para el plan del repositorio, se detiene la parte y se ejecuta `/sdd-escalar` con tres opciones: hacer público el repositorio, contratar *Secret Protection* o añadir `gitleaks` al pipeline | TC-16, TC-17 | persona usuaria | — | La segunda consulta muestra `secret_scanning` y `secret_scanning_push_protection` en `enabled`. Empuje de ensayo: la persona crea un token personal de GitHub sin permisos, lo **revoca**, lo pega en un archivo de la rama de ensayo e intenta empujar; el empuje se rechaza o queda la alerta. Evidencia en `impl.md` sin el token | Pendiente |
| B6 | Ensayo en el pipeline de la parte b | TC-11a, TC-11b | `git-entrega` | `haiku` | Rojo con la dependencia `ALTA` de Python y con la de npm; verde con la `MEDIA` de npm, que se ve informada en el registro | Pendiente |
| B7 | Documentación, marcas y ADR de severidad | TC-70b | `ingeniero-devsecops` | `haiku` | `verificar_docs.py` en 0, con el ADR en el índice | Pendiente |

### Parte c · Verificador de escenarios

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| C1 | `tools/tests/test_verificar_escenarios.py` con una función que construye en un directorio temporal un `docs/04-historias-usuario.md` de ejemplo (tabla «El conjunto» con fases `1`, `1+2` y `2`, y tres historias), un `historias_activas.txt` y archivos de test. Todos en rojo. Después, `leer_historias` y `leer_activas` | TC-44, TC-45, TC-46, TC-47, TC-48, TC-49, TC-55 | `ingeniero-devsecops` | `haiku` | `python -m unittest tools.tests.test_verificar_escenarios -v`: esos casos en verde, los demás aún en rojo | ✓ Hecho |
| C2 | `recolectar_tests` y `clasificar` | TC-40, TC-41, TC-42, TC-43, TC-50, TC-51, TC-52 | `ingeniero-devsecops` | `haiku` | Los casos de la fila en verde | ✓ Hecho |
| C3 | `main` con `--raiz` y `--activas-base`, y la salida con sus etiquetas | TC-53, TC-54 y el resto | `ingeniero-devsecops` | `haiku` | Toda la clase en verde; `python tools/verificar_escenarios.py` sobre el árbol real, con `tools/historias_activas.txt` aún inexistente, termina en 2 | ✓ Hecho |
| C4 | `tools/historias_activas.txt` real, paso del verificador en el trabajo `herramientas` y su caso en `test_definicion_ci.py` | TC-56, TC-57 | `ingeniero-devsecops` | `haiku` | Sobre el árbol real termina en 0 con «pendientes 162», «exigidos 0» y los tests de fundación contados; TC-57 en verde | ✓ Hecho |
| C5 | Ensayo en el pipeline de la parte c | TC-58 | `git-entrega` | `haiku` | Con `HDU-001` añadida a la lista en la rama de ensayo, el trabajo `herramientas` termina en rojo y lista sus 27 escenarios como `FALTA` | ⚠ Ajustado |
| C6 | Documentación, la marca de `CLAUDE.md:78`, las prosas de retiro de HDU-006 y TKT-069 y ADR (ver «Documentación afectada») | TC-70c | `ingeniero-devsecops` | `haiku` | `verificar_docs.py` en 0 con 162 escenarios y el mismo conteo de HDU-006; búsqueda de TC-70c sin coincidencias | ✓ Hecho |

### Parte d · Calidad documental

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| D1 | Los seis archivos de configuración de la tabla de arriba. Rojo previo: en un directorio temporal, un `.md` con «tablaroka» no produce ningún aviso de `Vale` sin la configuración | TC-60, TC-61 | `ingeniero-devsecops` | `haiku` | Con la configuración: el `.md` con «tablaroka» da un aviso `Cimenta.Vocabulario` con su línea y código 0; un `.md` con los ocho términos del glosario, cero alertas | Pendiente |
| D2 | **Medición de la línea base, sin editar.** Sobre el alcance: hallazgos de `markdownlint-cli2` por regla; los que quedan tras `--fix` en una copia desechable; alertas de `Vale` por regla; enlaces rotos de `lychee`. Tabla en `impl.md`. **Umbral:** si los hallazgos que `--fix` no corrige, más las alertas de `Vale`, más los enlaces rotos suman **más de 120**, la parte se detiene y se ejecuta `/sdd-escalar` proponiendo partir la limpieza en su propio ticket. Si `Vale.Repetition` marca celdas contiguas de tabla como repetición, se desactiva la regla en `.vale.ini` y se anota; ninguna otra regla se apaga para bajar el número | — | `ingeniero-devsecops` | `haiku` | Tabla de recuento en `impl.md` y decisión aplicada según el umbral | Pendiente |
| D3 | Limpieza automática: `markdownlint-cli2 --fix` sobre el alcance, en un commit propio que no contiene otro cambio, después de fusionadas las partes a, c y b | TC-69 (parcial) | `ingeniero-devsecops` | `haiku` | `verificar_docs.py` en 0 con el mismo número de escenarios y de puntos; `git diff -U0 -- docs/04-historias-usuario.md` sin ninguna línea `**Escenario N:` cambiada (si aparece, se revierte a mano); `git diff --stat` en `impl.md` | Pendiente |
| D4 | Limpieza manual de lo que queda, un commit por herramienta | TC-69 | `ingeniero-devsecops` | `haiku` | `markdownlint-cli2`, `vale --output=line` y `lychee` sobre el alcance, con cero hallazgos | Pendiente |
| D5 | Pasos nuevos del trabajo `documentacion`, `.github/workflows/enlaces.yml` y sus casos en `test_definicion_ci.py` | TC-64, TC-65 | `ingeniero-devsecops` | `haiku` | TC-64 y TC-65 en verde; `zizmor` en 0 | Pendiente |
| D6 | Ensayo en el pipeline de la parte d | TC-62, TC-63, TC-66, TC-67, TC-68 | `git-entrega` | `haiku` | Cada violación pone el trabajo en rojo citando archivo y línea; ronda de limpieza en verde | Pendiente |
| D7 | Documentación, marcas y ADR de `Vale` en español | TC-70d | `ingeniero-devsecops` | `haiku` | `verificar_docs.py` en 0 y el trabajo `documentacion` en verde | Pendiente |

**Cierre de cada parte:** el PR de la parte corre el pipeline completo en verde sobre su árbol, sin la rama de ensayo, y `impl.md` enlaza esa ejecución.

## Ensayo de compuertas

Cada ronda es un commit en la rama de ensayo. Las violaciones de una ronda caen en trabajos o pasos independientes, así que una no tapa a otra (regla común 6). El trabajo `frontend` se ensaya en una ronda en la que `backend` está sano, porque depende de él a través de `contrato-api`.

| Parte | Ronda | Violación | Trabajo que debe quedar en rojo | Mensaje esperado |
|---|---|---|---|---|
| a | 1 | Archivo `cimenta/presupuesto/dominio/_ensayo.py` con un parámetro `float` y una línea `Decimal(0.1)`, mal formateado | `backend` | `ruff format --check` lo nombra; `RUF032`; `verificar_float` con «(regla 1 de CLAUDE.md)» |
| a | 1 | `backend/tests/test_ensayo_roto.py` con `assert False` | `backend` | El resumen de `-ra` y el `pytest.xml` nombran `test_ensayo_roto` |
| a | 1 | `cimenta/compras/aplicacion/_ensayo.py` que importa `cimenta.presupuesto.infraestructura` | `fronteras` | Contrato `solo-por-interfaz` roto, con la importación |
| a | 1 | La ruta de inicio de sesión que llama el cliente, cambiada por `/api/sesion-ensayo` | `humo` | Playwright falla; el artefacto `humo-playwright` existe |
| a | 1 | `.github/workflows/ensayo.yml` sin `permissions` y con `pull_request_target` | `workflows` | `zizmor` nombra el archivo y las dos auditorías |
| a | 2 | Un cambio en el `summary` de una ruta existente de `cimenta/identidad/api/`, sin regenerar los tipos | `frontend` | `tipos:verificar` con «Ejecuta npm run tipos:generar» |
| a | 3 | Revertir todo | todos | Verde |
| b | 1 | `django==3.2` en el grupo `dev` | `dependencias` | Línea `ALTA` o `CRÍTICA` con paquete, versión y `GHSA` |
| b | 1 | `lodash@4.17.20` en `devDependencies` | `dependencias` | `npm audit` con severidad `high` |
| b | 2 | Solo un paquete de npm cuyo único aviso sea `moderate` (candidato: `nanoid@3.1.30`; se confirma en la base de avisos de GitHub antes de empujar, y si ya no es solo `moderate` se elige otro que lo sea) | ninguno | El aviso aparece en el registro y el trabajo queda en verde |
| c | 1 | `HDU-001` añadida a `tools/historias_activas.txt` | `herramientas` | 27 líneas `FALTA HDU-001 esc. N` |
| d | 1 | Un enlace relativo roto, «tablaroka» en un documento, un diagrama con `A -> B` en un `flowchart` y un enlace a `https://cimenta-ensayo.invalid/` | `documentacion` | `verificar_docs.py` y `lychee` con el enlace y su archivo; `Cimenta.Vocabulario` con archivo y línea; `::error` con el archivo del diagrama |

El cron de `enlaces.yml` no se puede lanzar antes de que el archivo llegue a la rama por omisión. Su disparo se comprueba leyendo la definición (TC-64) y su detección con la misma configuración en el trabajo del PR (TC-68). La primera ejecución manual con `gh workflow run enlaces.yml` tras la fusión se anota en `delta.md`.

## Plan de pruebas

Los casos «estáticos» viven en `tools/tests/test_definicion_ci.py` y leen el texto de los workflows con expresiones regulares: `tools/` no tiene dependencias y no hay un analizador de YAML en la biblioteca estándar. De lo que mira `zizmor` solo se repiten los permisos y los disparadores (TC-21 y TC-22), porque `CA-12` los exige comprobables en la propia definición; el fijado por SHA y las credenciales persistidas quedan solo en `zizmor`.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | El trabajo `backend` contiene, en orden, `uv sync --locked --python 3.14`, `ruff format --check`, `ruff check`, `mypy`, `herramientas.verificar_float`, `pytest` con `--cov` y `--junitxml`, y `upload-artifact` con `if: always()` | estático | `CA-1` | esc. 1 |
| TC-01b | `pytest --cov` en local genera `cobertura.xml` | feliz | `CA-1` | esc. 1 |
| TC-02 | Ensayo: test roto, `backend` en rojo y el informe lo nombra | **rechazo** | `CA-2` | esc. 1 |
| TC-03 | Ensayo: `float` en `dominio/`, `verificar_float` en rojo con el archivo y la regla 1 | **rechazo** | `CA-2` | esc. 2 |
| TC-04 | Ensayo: `Decimal(0.1)`, `ruff check` en rojo con `RUF032` | **rechazo** | `CA-2` | esc. 3 |
| TC-05 | El trabajo `fronteras` ejecuta `lint-imports` con `working-directory: backend` | estático | `CA-3` | esc. 1 |
| TC-06 | El trabajo `frontend` hace `uv sync --locked --python 3.14` antes de `npm ci`, y después los cuatro scripts en el orden del criterio | estático | `CA-4` | esc. 1 |
| TC-07 | Ensayo: tipos desactualizados, `frontend` en rojo con «Ejecuta npm run tipos:generar» | **rechazo** | `CA-4` | esc. 2 |
| TC-08 | El trabajo `humo` copia `.env.example`, levanta `db` con `--wait`, migra, fija contraseñas, ejecuta `npm run e2e` y sube el informe con `if: failure()` | estático | `CA-5` | esc. 1 |
| TC-09 | Ensayo: inicio de sesión roto, `humo` en rojo con artefacto | **rechazo** | `CA-5` | esc. 2 |
| TC-10 | Ensayo: import cruzado, `fronteras` en rojo con el contrato y la importación | **rechazo** | `CA-3` | esc. 2 |
| TC-11a | Ensayo: dependencia alta en Python y en npm, `dependencias` en rojo | **rechazo** | `CA-10` | esc. 2 |
| TC-11b | Ensayo: dependencia media en npm, verde con el aviso en el registro | **rechazo** (de bloqueo de más) | `CA-10` | esc. 3 |
| TC-12 | Existe `contrato-api`, su nombre cita TKT-061, tiene `needs: backend` y `frontend` tiene `needs: contrato-api` | estático | `CA-9` | esc. 1 |
| TC-13 | Ningún workflow tiene disparador `workflow_run`, y todo `needs` apunta a un trabajo del mismo archivo | **rechazo** (estático) | `CA-9` | esc. 2 |
| TC-14 | El trabajo `dependencias` ejecuta `pip-audit` con `--require-hashes`, el script de severidad y `npm audit --audit-level=high` | estático | `CA-10` | esc. 1 |
| TC-15 | `dependabot.yml` declara `uv` o `pip` en `/backend`, `npm` en `/frontend` y `github-actions` en `/` | estático | `CA-11` | esc. 1 |
| TC-16 | `gh api` muestra escaneo de secretos y protección de empuje activos | manual | `CA-11` | esc. 2 |
| TC-17 | Empuje con un token revocado: rechazado o registrado | **rechazo** (manual) | `CA-11` esc. 2, `CA-R3` esc. 2 | — |
| TC-18 | `.env.example` no aparece en ningún `paths-ignore` y no existe `secret_scanning.yml` | **rechazo** (estático) | `CA-11` | esc. 3 |
| TC-20 | `zizmor` falla ante un workflow sin `permissions` y nombra el archivo | **rechazo** | `CA-12` | esc. 3 |
| TC-21 | Cada workflow declara `permissions:` a nivel de flujo con `contents: read`, y ninguna línea con `: write` carece de comentario | estático | `CA-12` | esc. 1 |
| TC-22 | Ningún workflow contiene `pull_request_target` ni `secrets.`; `ci.yml` usa `pull_request` | **rechazo** (estático) | `CA-12` esc. 2, `CA-R3` esc. 1 | — |
| TC-23 | El trabajo `herramientas` instala `uv`, hace `uv sync --locked --python 3.14`, el paso que ejecuta la suite de `tools/` con una tubería declara `shell: bash` (y así `pipefail`), y tiene la guarda de `skipped=` | estático | `CA-R4` | esc. 2 |
| TC-24 | Ensayo: `ensayo.yml` sin permisos y con `pull_request_target`, `workflows` en rojo | **rechazo** | `CA-12` | esc. 2 y 3 |
| TC-30 | Un hallazgo `HIGH` termina en 1 y la línea nombra paquete, versión y `GHSA` | **rechazo** | `CA-10` | esc. 2 |
| TC-31 | Un hallazgo `CRITICAL` termina en 1 | **rechazo** | `CA-10` | esc. 2 |
| TC-32 | Un hallazgo `MODERATE` termina en 0 y se informa como `MEDIA` | **rechazo** (de bloqueo de más) | `CA-10` | esc. 3 |
| TC-33 | Un hallazgo `LOW` termina en 0 | feliz | `CA-10` | esc. 3 |
| TC-34 | Un hallazgo sin `GHSA` termina en 1 como `DESCONOCIDA` | **rechazo** | `CA-10` | esc. 2 |
| TC-35 | Un informe sin vulnerabilidades termina en 0 | feliz | `CA-10` | esc. 1 |
| TC-36 | JSON inexistente o ilegible termina en 2 | **rechazo** | `CA-10` | — |
| TC-37 | Un error de la consulta a OSV termina en 2 | **rechazo** | `CA-10` | — |
| TC-38 | Acepta el formato `{"dependencies": […]}` y la lista antigua | feliz | `CA-10` | — |
| TC-40 | Historia activa con el esc. 4 sin test: código 1 y `FALTA HDU-002 esc. 4` | **rechazo** | `CA-6` | esc. 1 |
| TC-41 | Con `test_hdu002_esc04_…`: código 0 y sin `FALTA` | feliz | `CA-6` | esc. 2 |
| TC-42 | `test_hdu002_4_…`, `test_hdu002_escenario4_…` y `test_hdu002_esc04x_…` no cubren: código 1 | **rechazo** | `CA-6` | esc. 3 |
| TC-43 | `it("hdu002_esc04 · …")` en un `.test.ts` cubre el escenario | feliz | `CA-6` | esc. 2 |
| TC-44 | Historia no activa sin tests: código 0 y `PENDIENTE` con su recuento | feliz | `CA-7` | esc. 1 |
| TC-45 | Historia activa: el escenario `· fase 2` sin test es `PENDIENTE` y uno de fase 1 sin test es `FALTA` | **rechazo** | `CA-7` | esc. 2 |
| TC-46 | Con la línea `fase 2`, el escenario de fase 2 sin test pasa a `FALTA` | **rechazo** | `CA-7` | esc. 2 |
| TC-47 | Historia `1+2` con escenario sin marca: cuenta como fase 1. Historia `2` sin marca: fase 2 | feliz | `CA-7` | esc. 3 |
| TC-48 | Esc. 14 y 15 con `· retirado por TKT-069`, sin tests: ni `FALTA` ni error; `RETIRADO` | feliz | `CA-7` | esc. 4 |
| TC-49 | Nota de retiro en prosa, sin el segmento: sigue `FALTA` | **rechazo** | `CA-7` | esc. 5 |
| TC-50 | `test_tkt003_ca10_esc01_…` y `"tkt008_ca3_esc02 · …"`: contados como de fundación, sin error | feliz | `CA-8` | esc. 1 |
| TC-51 | `test_identidad_…` y `tkt004_ca11_…`: ignorados, código 0 | feliz | `CA-8` | esc. 2 |
| TC-52 | `test_hdu099_esc01_…` y `test_hdu002_esc99_…`: código 1 y `ERROR` con el test y el identificador | **rechazo** | `CA-8` | esc. 3 |
| TC-53 | `--activas-base` con HDU-003 que ya no está: código 1 y `ERROR` con HDU-003 | **rechazo** | `CA-8` | esc. 4 |
| TC-54 | `--activas-base` con `fase 2` que ya no está: código 1 | **rechazo** | `CA-8` | esc. 4 |
| TC-55 | Línea inválida o historia inexistente en la lista: código 2 | **rechazo** | `CA-6` | — |
| TC-56 | Sobre el árbol real: código 0, 162 pendientes | feliz | `CA-7` | esc. 1 |
| TC-57 | El trabajo `herramientas` ejecuta el verificador y le pasa la base del PR por `env` | estático | `CA-6` | esc. 1 |
| TC-58 | Ensayo: HDU-001 activa, `herramientas` en rojo con 27 `FALTA` | **rechazo** | `CA-6` | esc. 1 |
| TC-60 | `Vale` local sobre «tablaroka»: aviso con línea y código 0 | feliz | `CA-13` | esc. 2 |
| TC-61 | `Vale` sobre los ocho términos del glosario: cero alertas | **rechazo** (de falso error) | `CA-13` | esc. 4 |
| TC-62 | Ensayo: «tablaroka», `documentacion` en rojo con archivo y línea | **rechazo** | `CA-13` | esc. 3 |
| TC-63 | Ensayo: enlace relativo roto, `documentacion` en rojo con archivo y línea | **rechazo** | `CA-13` | esc. 3 |
| TC-64 | `enlaces.yml` tiene `schedule` con un cron de un día por semana y `workflow_dispatch` | estático | `CA-14` | esc. 1 |
| TC-65 | `documentacion` ejecuta `verificar_docs.py`, `markdownlint-cli2`, `vale --output=line` con la guarda de salida vacía, `lychee` y `mmdc` | estático | `CA-13` esc. 1, `CA-16` esc. 1 | — |
| TC-66 | Ensayo: diagrama con `A -> B`, `documentacion` en rojo con el archivo | **rechazo** | `CA-16` | esc. 2 |
| TC-67 | Los diagramas reales pasan `mmdc` | feliz | `CA-16` | esc. 1 |
| TC-68 | Ensayo: enlace externo a `.invalid`, `lychee` en rojo con el enlace y su archivo | **rechazo** | `CA-14` | esc. 2 |
| TC-69 | El trabajo `documentacion` en verde sobre la rama del ticket: cero avisos y cero errores | regresión | `CA-13` | esc. 5 |
| TC-70a | Parte a: `CLAUDE.md` líneas 20 a 22 (reglas 1, 2 y 3) y `conv-dominio-python` sin «desde TKT-009»; **`CLAUDE.md:78` conserva su «(desde TKT-009)»**, porque el verificador de escenarios aún no corre; `desde TKT-059` sigue presente; `verificar_docs.py` en 0 | regresión y **rechazo** | `CA-15` | esc. 1 y 2 |
| TC-70b | Parte b: ninguna marca nueva que retirar; `docs/06-stack-tecnologico.md` §6.4 describe la política vigente; `verificar_docs.py` en 0 | regresión | `CA-15` | esc. 1 |
| TC-70c | Parte c: `CLAUDE.md:78` sin «(desde TKT-009)»; la fila del verificador en `docs/06-stack-tecnologico.md` §9 sin «⏳ TKT-009»; `tools/README.md` sin la sección «Pendiente»; ninguna coincidencia de `desde TKT-009` ni de `⏳ TKT-009` en los archivos de `CA-15`; `desde TKT-059` sigue presente | regresión y **rechazo** | `CA-15` | esc. 1 y 2 |
| TC-70d | Parte d: el párrafo de `mermaid-cli` de `docs/06-stack-tecnologico.md` §9 en presente; `verificar_docs.py` en 0 y `desde TKT-059` presente | regresión | `CA-15` | esc. 1 y 2 |
| TC-R1a | `ci.yml` no contiene `sqlite` ni `create_all`; las pruebas de TKT-003 sobre el rol de aplicación siguen en verde | regresión de invariante | `CA-R1` | esc. 1 |
| TC-R1b | Mutante: `motor_aplicacion` conectado como `cimenta_migracion`; las pruebas que usan el motor caen por la guarda `_exigir_motor_de_aplicacion` | **rechazo** | `CA-R1` | esc. 2 |
| TC-R2a | `git diff` de `backend/pyproject.toml` no toca `[tool.importlinter]` | regresión de invariante | `CA-R2` | esc. 1 |
| TC-R2b | Mutante: un contrato borrado; `test_tkt004_ca10_arbol_real` cae con `(14, 0)` | **rechazo** | `CA-R2` | esc. 2 |
| TC-R4a | Recuento de pruebas de backend, frontend y `tools/` antes y después: iguales o mayores, y el diff no añade `skip`, `xfail` ni `.only` | regresión | `CA-R4` | esc. 1 |
| TC-R4b | Sin `uv`, la guarda de `skipped=` falla | **rechazo** | `CA-R4` | esc. 2 |

**Mutación.** El ticket no toca rutas de dinero, límites ni congelado. Los mutantes que se prueban son los de las compuertas, y cada uno tiene su test rojo esperado:

| Mutante | Test que debe caer |
|---|---|
| `SEVERIDADES_QUE_FALLAN` sin `CRITICAL` | TC-31 |
| `DESCONOCIDA` tratada como informativa | TC-34 |
| `PATRON_HDU` sin el anclaje `(?=$\|[_\s·])` | TC-42: `test_hdu002_esc04x_…` captura `04` y cubriría el esc. 4. (Con `esc041` no sirve como ejemplo: `\d{2,}` es voraz, captura `041` y el test cae en TC-52 como escenario inexistente, haya o no anclaje) |
| `shell: bash` quitado del paso de la suite de `tools/` | TC-23 |
| Fase calculada solo por la marca, sin la columna `Fase` | TC-47 (historia `2`) |
| Retiro aceptado por cualquier mención de «retir» en el bloque | TC-49 |
| Comparación con la base desactivada | TC-53 |
| Paso de guarda `skipped=` borrado del trabajo | TC-23 |
| `needs: contrato-api` quitado de `frontend` | TC-12 |

## Impacto

Resultado de `revisor-impacto`: pendiente; lo despacha `/sdd-disenar` antes del gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `backend/pyproject.toml` y `uv.lock` (`pytest-cov`, `pip-audit`) | Toda la suite, TKT-058 | Una dependencia nueva arrastra transitivas con avisos | El propio trabajo `dependencias` las audita; TC-R2a |
| `ci.yml` | TKT-061 ocupa `contrato-api`; TKT-062 exige este pipeline en verde para fusionar; TKT-059 añade MinIO al trabajo `backend` | Que TKT-061 meta su prueba en otro sitio, o que TKT-062 se acople a él | TC-12 y TC-13 fijan el hueco y la independencia |
| `tools/` (dos scripts y sus pruebas) | Quien ejecuta `python -m unittest discover -s tools/tests` | La suite de `tools/` hace llamadas de red | Las pruebas inyectan `consultar`; ninguna llama a OSV |
| `tools/historias_activas.txt` | Cada planificación de sprint | Olvidar añadir una historia la deja sin exigir | Coste aceptado en ADR-012; la salida lista lo pendiente con su recuento |
| Formato de títulos de escenario (`· retirado por`) | `verificar_docs.py`, TKT-069 | Que el segmento rompa el conteo | El patrón de `verificar_docs.py` solo lee `**Escenario N: `; TC-48 |
| Limpieza documental con `--fix` | Todo `docs/` y `sdd/`, incluidos artefactos archivados | Un diff enorme que esconda un cambio de contenido | Commit propio solo de formato (D3) y `verificar_docs.py` con los mismos conteos |
| `convenciones.md` §10 y `conv-documentacion` (Vale sin estilo Microsoft) | Quien escribe documentación | Discrepancia entre lo documentado y lo configurado | Se actualizan en D7 con enlace al ADR |
| Ajustes del repositorio | Toda persona que empuja | La protección de empuje rechaza un empuje legítimo | Se resuelve en el propio aviso de GitHub; nunca con exclusión de rutas |

**Fronteras entre módulos:** ¿algún módulo habla con otro por fuera de su interfaz de aplicación publicada? **No.** El ticket no toca `backend/cimenta/` fuera de la rama de ensayo, que no se fusiona.

## Documentación afectada

| Documento | Qué cambia | Parte |
|---|---|---|
| `CLAUDE.md`, líneas 20 a 22 | Reglas 1, 2 y 3: se quitan «(en el pipeline desde TKT-009)» y se dice que el pipeline lo hace fallar. Comandos: una línea que remite a `.github/workflows/ci.yml` como el lugar donde corren | a |
| `CLAUDE.md`, línea 78 | «Un verificador en CI falla si algún escenario … se queda sin test (desde TKT-009)»: se quita la marca, porque el verificador ya corre en el trabajo `herramientas` | c |
| `CLAUDE.md:14`, `README.md:30` y `llms.txt:27` | El total de decisiones: «23» sube en uno con cada ADR nuevo. Con el orden de fusión a → c → b → d, la parte c lo deja en 24, la b en 25 y la d en 26 | c, b, d |
| `.gitignore` | `backend/.coverage`, `backend/cobertura.xml` y `backend/pytest.xml` (fila A1) | a |
| `docs/05-tickets-trabajo.md`, ficha de TKT-009 | Solo si se aprueba partir: subsección de partición con las fichas TKT-009a a TKT-009d (fila A0) | a |
| `docs/05-tickets-trabajo.md`, ficha de TKT-069 (~l.2017) | «salen del verificador con una nota en la historia (TKT-009)» pasa a «salen del verificador con el segmento ` · retirado por TKT-069` en su título» | c |
| `.claude/skills/conv-dominio-python/SKILL.md` | Líneas 8 y 13: «en el pipeline desde TKT-009» pasa a presente | a |
| `.claude/skills/conv-docker/SKILL.md` | §3, último punto: el corredor de GitHub Actions trae Docker y la suite corre igual, en presente | a |
| `docs/06-stack-tecnologico.md` | §10 «Integración continua»: los trabajos reales, la cobertura sin umbral y la desviación de MinIO hasta TKT-059. §6.4: la política de severidad y la excepción por alerta de las credenciales de desarrollo. §7.2: la forma `"hduXXX_escNN · …"` en TypeScript, la línea `fase 2` y la nota de retiro. §9: la fila del verificador pasa a «✅ En uso» y el párrafo de `mermaid-cli`, a presente | a, b, c, d |
| `docs/arranque-local.md` | Sección nueva «Integración continua», corta: el pipeline corre los mismos comandos de este documento; cómo auditar en local (`pip-audit` y el script, `npm audit --audit-level=high`); cómo ejecutar `markdownlint-cli2`, `Vale` y `lychee` | a, b, d |
| `docs/05-tickets-trabajo.md` | TKT-009: «y MinIO» con la desviación y su porqué; TKT-059: criterio nuevo «añade el servicio y las pruebas de MinIO al trabajo `backend` del pipeline» | a |
| `docs/04-historias-usuario.md` | Las tres prosas de retiro: la del bloque «La captura sin conexión y la evidencia ya están descritas» (~l.68), la nota tras el esc. 15 de HDU-006 (~l.1256) y su Definition of Done (~l.1298). Las tres dicen que TKT-069 los retira añadiendo ` · retirado por TKT-069` a su título, la marca que lee el verificador. El texto y los títulos de los escenarios no cambian | c |
| `docs/convenciones.md` §10 (~l.320-336) | Fila «Prosa»: «`Vale` con estilo Microsoft» pasa a «`Vale` con el estilo del proyecto», con enlace al ADR (parte d). Fila «Diagramas»: `tools/extraer_mermaid.py` en local y `@mermaid-js/mermaid-cli` en CI (parte d). Fila «Escenarios sin test»: el verificador propio pasa a nombrar `tools/verificar_escenarios.py` con su enlace (parte c) | c, d |
| `.claude/skills/conv-documentacion/SKILL.md` | §7 (l.65): la misma corrección de `Vale`. §8 (l.72): los diagramas se validan con `tools/extraer_mermaid.py` en local y con `mermaid-cli` en el pipeline | d |
| `tools/README.md` | Secciones de `severidad_pip_audit.py` y `verificar_escenarios.py`; «Pendiente» desaparece; `extraer_mermaid.py` queda para local y CI usa `mermaid-cli`; las pruebas las corre el trabajo `herramientas` | a, b, c, d |
| `tools/tests/test_verificar_codificacion.py` y `test_sembrar_usuario_humo.py` | Solo el docstring: lo que decía que haría TKT-009 pasa a presente. Lo edita `tester-backend`, sin tocar ningún caso | a |
| `docs/adr/README.md` | Las entradas de los tres ADR | b, c, d |

## ¿Merece ADR?

**Sí, tres**, uno por parte, porque en los tres hubo opciones descartadas y una persona nueva preguntaría «¿por qué así?». Formato MADR, con fecha del día en que se escriben.

1. **`docs/adr/<fecha>-severidad-en-la-auditoria-de-dependencias.md`** (parte b). Opciones: fallar ante cualquier vulnerabilidad, que contradice `CA-10` esc. 3; `actions/dependency-review-action` con `fail-on-severity: high`, que solo mira las dependencias que el PR añade y no las ya presentes; `osv-scanner`, que no trae umbral de severidad; **la severidad del aviso de GitHub leída en OSV, con fallo cerrado si falta**, elegida.
2. **`docs/adr/<fecha>-politica-del-verificador-de-escenarios.md`** (parte c). Marcador de fase 2: archivo propio frente a **línea en `historias_activas.txt`**. Nota de retiro: comentario HTML invisible, párrafo en prosa con formato fijo o **segmento del título**. Archivo de historias: inferirlo de los tests existentes, que no ve una historia activa sin tests, frente a **comparar con la base del PR**. Forma de los nombres en TypeScript. El ADR nuevo enlaza a ADR-012, que no se modifica.
3. **`docs/adr/<fecha>-vale-para-prosa-en-espanol.md`** (parte d). Estilo Microsoft, ortografía con Hunspell en español, o **estilo propio mínimo** con `Vale.Terms`, `Vale.Repetition` y `Cimenta.Vocabulario`; y cómo se consigue aviso en local y error en CI con un solo `.vale.ini`.

## Pasada adversarial

Las objeciones 1 a 10 las hizo el arquitecto sobre su propio diseño; las 11 y 12 las añadió el orquestador con `abogado-del-diablo` antes del gate.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El diseño completo suma unas 1,230 líneas, tres veces el tope | **Acogida.** Partición en cuatro, propuesta para el gate |
| 2 | Alta | `lychee` con red en cada PR hace que la caída de un sitio ajeno bloquee un PR que no toca documentación | **Acogida parcialmente.** `CA-13` lo exige en el PR. Se mitiga con tres reintentos, `429` aceptado y `exclude` revisado en el PR que lo amplía. Si en el primer mes falla más de una vez por causas ajenas, se propone limitarlo a los archivos cambiados |
| 3 | Alta | El fallo cerrado de `DESCONOCIDA` puede bloquear PRs por un aviso `PYSEC` sin equivalente `GHSA` | **Acogida.** Es la opción segura para `RNF-08`; la salida es `--ignore-vuln` con su comentario, visible en la revisión |
| 4 | Media | El escaneo de secretos depende del plan del repositorio | **Acogida.** B5 lo comprueba antes de nada y escala con tres opciones |
| 5 | Media | `frontend` espera a `backend` por `contrato-api` y alarga el pipeline | **Aceptada.** El orden lo exige `CA-9`. `humo`, `fronteras` y el resto corren en paralelo |
| 6 | Media | Un `Vale` sin ortografía ni estilo es casi decorativo | **Aceptada con ADR.** El valor real es el vocabulario y la repetición; la ortografía española, con su diccionario, marcaría cada término técnico en inglés y obligaría a desactivar la compuerta |
| 7 | Media | `npm audit` incluye las dependencias de desarrollo; una vulnerabilidad en una herramienta bloquea PRs | **Aceptada.** Las herramientas corren en CI junto al código y un agente las añade con la misma facilidad (stack §6.4). `--omit=dev` descartado |
| 8 | Media | Un `it.skip("hdu002_esc04 …")` cubriría el escenario sin ejecutarse | **No acogida en este ticket.** Ningún criterio lo pide; queda como ticket futuro sugerido |
| 9 | Media | Un empuje directo a `Produccion` se salta la comparación con la base | **Aceptada.** La protección de rama es de TKT-062 |
| 10 | Baja | Los PR de ensayo los abre una persona; el agente no puede cerrar el ciclo solo | **Aceptada.** Es la regla del proyecto para abrir PR |
| 11 | Alta | Los casos estáticos de `test_definicion_ci.py` leen `ci.yml` con expresiones regulares: un paso comentado, o movido a otro trabajo, seguiría pasando la prueba y la compuerta estaría desactivada sin que nada lo note | **Acogida** (orquestador, `abogado-del-diablo`). Cada caso busca dentro del bloque de su trabajo e ignora las líneas comentadas. Se añade un mutante local por criterio estático: comentar el paso o moverlo de trabajo debe poner en rojo el caso. Queda anotado en la fila A2 y en la regla común 6 |
| 12 | Media | Con `frontend` detrás de `contrato-api` y este detrás de `backend`, un fallo de `backend` deja `frontend` en «omitido»: el PR no ve que además rompió el cliente, que es justo lo que busca la regla común 6 | **Acogida.** `contrato-api` y `frontend` llevan `if: ${{ !cancelled() }}`, de modo que corren aunque `backend` falle y el orden que exige `CA-9` se conserva. El trabajo sigue en rojo por `backend` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| La línea base documental supera el umbral | Alta | Retrasa la parte d | D2 mide antes de editar y escala con la propuesta de partir la limpieza |
| `zizmor` no marca un workflow sin `permissions` en su modo por omisión | Baja | `CA-12` esc. 3 con una sola compuerta | El rojo de A4 lo descubre. TC-21, que corre en el trabajo `herramientas`, ya falla ante un workflow sin `permissions` y nombra el archivo: queda como compuerta de `CA-12` esc. 3 y se anota |
| `testcontainers` o `docker compose` lentos o limitados por Docker Hub en el corredor | Media | Trabajos lentos o rojos intermitentes | `timeout-minutes` por trabajo; la imagen es la única de `compose.yaml` |
| Dependabot no acepta el ecosistema `uv` | Baja | `CA-11` esc. 1 | Sustitución por `pip` en B4, prevista |
| Python 3.13 no se prueba | Media | Un fallo solo en 3.13 llega a producción si TKT-058 elige 3.13 | Registrado en `A-9`; TKT-058 fija el intérprete de la imagen y puede añadir la matriz |
| El ensayo deja código violatorio en una rama | Baja | Una fusión accidental | PR en borrador hacia la rama del ticket, cerrado sin fusionar y rama borrada en la misma fila |
| La versión mayor de una acción cambia entre el diseño y la ejecución | Media | Pasos con entradas renombradas | La regla común 2 fija la versión el día de la fila; Dependabot de `github-actions` la mantiene |
