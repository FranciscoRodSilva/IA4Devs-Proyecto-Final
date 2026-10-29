# Delta · TKT-004 · Tipos base del dominio con decimal exacto

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Paquete `tipos_base` con los objetos de valor `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`, inmutables, sobre `Decimal`, y la función `sumar(valores, tipo)`. Calculan con un contexto de `decimal` propio e independiente del proceso: sumas, restas y productos son exactos, y una división da un `Porcentaje` con 28 dígitos significativos o falla con `ZeroDivisionError`. Solo `cuantizar()` redondea, con `ROUND_HALF_UP` `(asumido)`, a la escala de la columna; `serializar()` produce la cadena de escala completa y **no redondea**: rechaza lo que no se ha cuantizado | `backend/tipos_base/` (`__init__.py`, `numericos.py`), fuera de `cimenta/` | Que ninguna regla posterior pueda introducir un error de coma flotante ni un redondeo oculto, y que todas compartan una sola escala, un solo modo de redondeo y una sola forma de serializar |
| Rechazos de entrada: `float`, `bool`, `NaN` e infinitos, cadenas que no son decimal llano (de hasta 100 caracteres), `Decimal` construido desde un `float` (más de 18 dígitos significativos y exactamente un `double`), y todo valor con más de 40 decimales o con una magnitud de 10^41 o más `(asumido)` | `backend/tipos_base/numericos.py` | Que un `Dinero` solo nazca de un valor exacto y que un `Decimal('1E+999999999')` no bloquee el proceso |
| Verificador `herramientas.verificar_float`: busca `float` en parámetros, retornos, campos anotados y anotaciones compuestas o en cadena de `cimenta/*/dominio/` y de `tipos_base/`. Termina con 0, con 1 si encuentra algo o no puede leer un archivo, y con 2 si no encuentra ningún archivo que revisar | `backend/herramientas/verificar_float.py` | Que la regla 1 de `CLAUDE.md` deje de ser un texto y falle ante su violación |
| Tipo de contrato propio `lista_blanca` de `import-linter` y los contratos `dominio-sin-framework` (ahora lista blanca) y `tipos-base-puro` | `backend/herramientas/contrato_lista_blanca.py` y `[tool.importlinter]` de `backend/pyproject.toml` | Cerrar la deuda `O1` de TKT-002: ningún `dominio/` alcanza nada que no sea la biblioteca estándar o `tipos_base`, ni directa ni indirectamente; y que `tipos_base` solo alcance la biblioteca estándar |
| Suite de 386 casos (en 9 archivos) que no necesita Docker: construcción, aritmética, los 27 insumos sintéticos con total literal calculado de forma independiente, redondeo y serialización, límites de entrada, mypy, el verificador de `float` y las fronteras con copias del árbol en `tmp_path` | `backend/tests/` (`test_tipos_base_*.py`, `test_verificar_float.py`, `test_fronteras_dominio.py`, `test_tkt004_conftest.py`) | Que cada garantía se haya visto fallar: 33 mutantes anotados en `impl.md` (24 de la entrega A y 9 de la B), aplicados de uno en uno con SHA-256 verificado, más los de las dos pasadas de revisión, aplicados en copias |
| ADR-020, tipos numéricos base, y ADR-021, lista blanca del dominio | `docs/adr/20261019-tipos-numericos-base.md` y `docs/adr/20261019-lista-blanca-del-dominio.md` | Registrar las opciones descartadas de la ubicación, la aritmética, el redondeo, la serialización, la regla contra `float` y la lista blanca |
| Pregunta abierta `PA-23`, modo de redondeo de los importes | `docs/01-descripcion-producto.md` | Que el supuesto `ROUND_HALF_UP` conste en el PRD para que negocio lo confirme antes de TKT-016 |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `dominio-sin-framework` | `backend/pyproject.toml` | Lista negra de tres paquetes (`fastapi`, `sqlalchemy`, `pydantic`) con `forbidden` → lista blanca: solo la biblioteca estándar y `tipos_base`. Un `requests`, un `numpy` o la interfaz de otro módulo ya rompen el contrato |
| Raíces de `import-linter` | `backend/pyproject.toml` | `root_package = "cimenta"` → `root_packages = ["cimenta", "tipos_base"]`; los 13 contratos restantes de TKT-002 no cambian y el total pasa de 14 a 15 |
| Reglas de Ruff y mypy | `backend/pyproject.toml` | `select` sin `RUF032` → con `RUF032` en todo `backend/`, que marca `Decimal(0.1)`; el override estricto de mypy cubría `cimenta.*.dominio.*` → cubre también `tipos_base.*` |
| Regla 1 de `CLAUDE.md` | `CLAUDE.md` | «el linter lo bloquea (desde TKT-004)» → lo marcan `verificar_float` y `RUF032` (en el pipeline desde TKT-009), y se nombran los cuatro tipos y el redondeo |
| Regla 2 de `CLAUDE.md` | `CLAUDE.md` | «Ni FastAPI, ni SQLAlchemy, ni Pydantic» → «ni ningún otro paquete: solo la biblioteca estándar y `tipos_base`», con la salvedad de que `datetime`, `os`, `socket`… pasan el contrato y los vigila la revisión |
| Estructura del backend | `CLAUDE.md`, `docs/convenciones.md` | `migraciones/`, `herramientas/` y `tests/` → aparece `tipos_base/`, que importa cualquier capa de cualquier módulo, y `import-linter` analiza `cimenta/` y `tipos_base/` |
| Conteo de ADR y de preguntas | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/02-arquitectura.md` §12, `docs/06-stack-tecnologico.md` §8, §11 y §13 | 19 → 21 decisiones; 22 → 23 preguntas |
| Convención de dominio | `.claude/skills/conv-dominio-python/SKILL.md` | Ejemplo con escala fija de dos decimales en el constructor → ejemplo con los tipos de `tipos_base`, que no fijan la escala en el constructor; «no comparten escala» → «no comparten precisión» |
| Arquitectura §7.4 y arranque local | `docs/02-arquitectura.md`, `docs/arranque-local.md` | Sin tipos ni verificador → tipos, operaciones permitidas, redondeo, límites del verificador y la frase «los tests de los tipos base no necesitan Docker» |
| ADR-018 | `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` | `Aceptado` → «Aceptado · el contrato `dominio-sin-framework` fue sustituido por ADR-021» |
| Agente `desarrollador-dominio` | `.claude/agents/desarrollador-dominio.md` | Escribe solo bajo `cimenta/<modulo>/dominio/` → también bajo `backend/tipos_base/` |
| Literales de la spec | `sdd/tickets/tkt-004/spec.md` | `PA-T5` decía que ningún documento fija el modo de redondeo → consta como `PA-23` del PRD |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Marca «(desde TKT-004)» de la regla 1 | `CLAUDE.md` | El verificador y `RUF032` ya fallan ante un `float`; verificado con violaciones generadas en `tmp_path` |
| La lista negra de tres paquetes como contrato de dominio | `backend/pyproject.toml` | La lista blanca la contiene: `fastapi`, `sqlalchemy` y `pydantic` siguen rompiendo el contrato, directa e indirectamente (TC-92, TC-93) |

## Comportamiento observable nuevo

- `Dinero("12.10")`, `Cantidad(...)`, `Rendimiento(...)` y `Porcentaje(...)` solo se construyen desde `str`, `int` o `Decimal`; un `float`, un `bool`, `NaN` o una cadena como `"1e3"`, `"1,234.50"` o `" 12.10"` lanzan `TypeError` o `ValueError` citando lo recibido. Son excepciones corrientes de Python, nunca un rechazo de negocio.
- `Dinero + Cantidad`, `Dinero * Dinero`, `Dinero * 2`, `float(dinero)` y `round(dinero)` lanzan `TypeError`. Solo existen `Cantidad × Rendimiento`, `Dinero × Cantidad` y `Dinero × Porcentaje`, en los dos órdenes, y `Cantidad ÷ Cantidad` y `Dinero ÷ Dinero`, que dan un `Porcentaje`.
- Una división entre cero lanza `ZeroDivisionError` y **nunca devuelve cero**: quien necesita «sin avance, `NULL`» (regla 12) decide antes de dividir.
- Los tipos admiten signo y no validan rangos de negocio: el [invariante 8](../../../docs/03-modelo-datos.md#13-invariantes-en-base-de-datos) del modelo de datos, «cantidades y precios no negativos», lo valida cada caso de uso. Rechazan al construir un valor con más de 40 decimales o con una magnitud de 10^41 o más.
- `cuantizar()` y `serializar()` fallan con `ValueError` si el valor no cabe en `NUMERIC(18,4)`, `(14,4)`, `(18,6)` o `(9,6)`; `serializar()` falla además ante un valor con más decimales que su escala. Un cero negativo se serializa como `0.0000`.
- `uv run python -m herramientas.verificar_float` termina con 1 ante un `float` en una firma de `dominio/` o de `tipos_base/`, ante un archivo que no se puede leer o analizar, y con 2 si no encuentra ningún archivo que revisar (por ejemplo, con `--raiz` apuntando a la raíz del repositorio). Ejecutado desde la raíz sin `--raiz`, el módulo no se encuentra y Python termina con 1. `uv run ruff check` marca `Decimal(0.1)` en todo `backend/`.
- `uv run lint-imports` pasa de 14 a 15 contratos y rechaza ahora cualquier paquete de tercero, o la interfaz de otro módulo, dentro de un `dominio/`.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO y tipos generados | Ninguno; el borrador OpenAPI no tiene operaciones con este ticket | No |
| Interfaz de `tipos_base` | `Dinero`, `Cantidad`, `Rendimiento`, `Porcentaje` y `sumar`; errores `TypeError`, `ValueError` y `ZeroDivisionError`. TKT-005 convierte a `422` lo que llegue de fuera | No: no existían |
| Contratos de `import-linter` | `dominio-sin-framework` pasa de `forbidden` a `lista_blanca`; nuevo `tipos-base-puro`; `root_packages` con dos raíces | Para un `dominio/` futuro que importe un tercero o la interfaz de otro módulo, sí: dejará de pasar. Es la regla 2 escrita |
| Esquema de base de datos, variables de entorno | Ninguno | No |

## Decisiones (ADR)

Las dos decisiones tuvieron opciones descartadas con evidencia citable y se escribieron como ADR del repositorio:

- [ADR-020](../../../docs/adr/20261019-tipos-numericos-base.md), tipos numéricos base con aritmética exacta y redondeo explícito. **Ubicación:** `backend/tipos_base/`, frente a un undécimo módulo `cimenta/comun` o `cimenta/tipos.py` (ambos rompen `esqueleto-modulos`) y a un tipo por módulo (cuatro sitios donde el redondeo diverge). **Aritmética:** contexto propio con precisión máxima, frente al del proceso (cualquier `getcontext().prec = …` cambiaría los importes) y a una precisión fija de 28 (redondea en silencio el producto de los máximos de columna, de 32 dígitos). **Serialización:** no redondea, frente a serializar redondeando (es el redondeo oculto que la regla prohíbe). **`float`:** `RUF032` más un verificador AST, frente a `banned-api`, un plugin de mypy y un hook de agente.
- [ADR-021](../../../docs/adr/20261019-lista-blanca-del-dominio.md), la lista blanca del dominio. Un tipo de contrato propio, frente a `forbidden` con una lista negra más larga (no cierra `O1`), con todos los paquetes instalados (se desincroniza de `uv.lock`), con `*` (los comodines no admiten negación) y a un verificador AST fuera de `import-linter` (no ve los indirectos). Sustituye el contrato `dominio-sin-framework` de ADR-018.
- **Evidencia:** los 9 mutantes del límite de entrada, aplicados por los auditores en copias, y los 9 del contrato (8 de la ejecución y MT-21, que la revisión añadió tras el hallazgo F003) mueren; el contrato sin `modulo == p or …startswith(f"{p}.")` sobrevivía a 15 pruebas hasta que TC-99 y TC-100 lo cerraron.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| El contexto por omisión de `decimal` tiene 28 dígitos y **redondea en silencio**: el producto de `Cantidad` y `Rendimiento` máximos de columna tiene 32 dígitos. Con `prec=MAX_PREC` es exacto, pero entonces el coste de sumar o cuantizar es lineal en la distancia entre exponentes | TC-26 (`9999999999999899990000.0000000001`) y el hallazgo `M-01`: `Decimal('1E+999999999')` tardaba segundos y generaba mensajes de 1 GB | Todo tipo de valor sobre `Decimal`: acotar la entrada y resumir los valores en los mensajes |
| Los tipos de valor reciben datos hostiles aunque nadie los llame todavía: `M-01` lo encontró un auditor que partía desde cero, y no los dos de la ejecución | Revisión de TKT-004: tres auditorías, un Mayor | `/sdd-disenar` de cualquier tipo o parser que acepte texto o números de fuera |
| Contar los dígitos significativos de un `Decimal` exige quitar los ceros finales a mano: `Decimal.normalize` redondea al contexto. Un `Decimal(float)` real no trae ceros finales; uno con ceros de escala (`0.5000000000000000000`) es legítimo | TC-05b y TC-05c | La heurística de «viene de un `float`» y cualquier comprobación de dígitos |
| `grimp` trata la biblioteca estándar como externa; `import-linter` admite tipos de contrato propios con `contract_types`, y `sys.stdlib_module_names` reconoce la biblioteca estándar. El recorrido de indirectos es `find_upstream_modules(as_package=True)` | `lint-imports` 15 kept; TC-90 a TC-100 | Futuros contratos propios, incluidos los de `tests/` y los de TKT-009 |
| `RUF032` es estable en Ruff 0.17.1 y marca `Decimal(0.1)` sin modo *preview* | `ruff check --isolated --select RUF032` | El `select` de Ruff |
| En Python 3.14, añadir un atributo a una dataclass `frozen=True, slots=True` lanza `TypeError`, no `AttributeError`; la asignación a un campo lanza `FrozenInstanceError` | TC-10 | Pruebas de inmutabilidad |
| Una comprobación de ids de test únicos se hace con `grep` de los docstrings `"""TC-…`; sin ella, tres ciclos arrastraron ids duplicados | `uniq -d` sobre los 9 archivos | Cualquier ticket con ids de caso |
| Un `Decimal` con exponente enorme puede hacer que **la suma** de dos valores válidos bloquee el proceso, no solo la construcción: acotar la entrada protege las operaciones internas, que no pasan por el límite | Revisión: 2000 multiplicaciones tardan 5 ms | Casos de uso que acumulen importes |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Siguen faltando `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `auditor-sql`, `meta-sdd` y `desarrollador-aplicacion`. Quinta vez. En la revisión se sustituyeron por agentes generales con la convención cargada: el de documentación, en `haiku`, no pudo verificar cuatro hallazgos porque su encargo no incluía el texto de la auditoría anterior | Alta |
| `herramienta` | `verificar_docs.py` falla durante todo el ticket por los enlaces del hub y de `impl.md` a `delta.md`. Cuarta vez (TKT-001, TKT-002, TKT-003 y este) | Alta |
| `comando` | El diseño descansó en afirmaciones no ejecutadas porque el arquitecto no tiene terminal: el contrato `lista_blanca`, el límite de la heurística de `Decimal` y el mensaje del rechazo. Esta vez el orquestador comprobó tres a mano y el desarrollador la cuarta, y el literal del diseño funcionó; en `_viene_de_float` falló y lo destapó el tester. Tercera vez (TKT-002, TKT-003 y este) | Alta |
| `guardrail` | Las dos auditorías de la ejecución aprobaron el tipo y la auditoría de revisión desde cero encontró el Mayor `M-01` (entradas con exponente enorme). El diseño de un tipo de valor no tenía una lista de «entradas hostiles»; conviene en `/sdd-disenar` para todo tipo que acepte datos de fuera | Alta |
| `comando` | El orden de implementación sumó unas 1,340 líneas, más de tres veces el tope. La partición en entregas A y B, segunda vez tras TKT-003, tampoco separa los PR: ambas viven en una rama, y los archivos de documentación y `pyproject.toml` mezclan cambios de las dos. Separar en dos commits exige hunks | Media |
| `herramienta` | Los conteos de ADR y de preguntas en texto (19, 20, 21; 22, 23) se editan a mano en seis o siete archivos y `verificar_docs.py` no los comprueba: el segundo ticket seguido que lo toca | Media |
| `comando` | El gate del diseño dejó pasar un `design.md` con código literal que el ejecutor tuvo que corregir (la heurística de `Decimal`) o ampliar (`verificar_float`, límites). `/sdd-ejecutar` debería anotar en `design.md` «el código literal está superado por `backend/`» en la misma pasada, y no solo en el delta | Media |
| `modelo` | `haiku` con código literal salió bien a la primera (filas 1, 4 y 5, y las correcciones de documentación). El tester en `sonnet` añadió mutantes extra y encontró uno que sobrevivía (F003 de la B); la mutación por garantía vale su coste en tickets de fundación | Baja |
| `contexto` | Escribir la documentación del ciclo de corrección en paralelo con los tests en rojo hizo que la documentación fuese por delante del código dos veces; el corrector lo avisó y se resolvió, pero costó una reauditoría | Baja |
| `convención` | Cuatro tests nacen en verde (oráculos de `float` y pruebas del espacio negativo) y el diseño los daba en rojo: conviene que el diseño marque cuáles nacen en verde y por qué | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `__bool__` que lance `TypeError`: `if consumido:` con `Dinero("0")` es verdadero y sería un error silencioso | Ningún criterio lo pide | Ticket de endurecimiento de `tipos_base`, o el primero que compare importes (TKT-020) |
| El verificador de `float` no detecta `type X = float`, `TypeVar(bound=float)`, límites PEP 695, `b.float`, valores por omisión `x=0.5`, `float(x)` en el cuerpo ni `# type:`; y da un falso positivo con `Literal["float"]` y `Annotated[int, "float"]` (`PA-T14`) | Es la regla de firma de la spec; ampliar la detección crece el alcance | Ticket de endurecimiento del linter |
| Ruff solo selecciona `E,W,F,I,B,UP,SIM,RUF032`; `conv-dominio-python` §7 dice `E,F,W,B,UP,SIM,RUF,ANN,TRY,PL` | Non-goal de este ticket | Ticket de convenciones de Ruff |
| Dónde cae el centavo en el reparto 3/5 y 2/5 de la nómina (`PA-T10`) | No hay reparto en este ticket | Antes de implementar `RN-23`, fase 2 |
| Comparación con tolerancia explícita y `Dinero ÷ Cantidad` para reconstruir el precio unitario (`PA-T11`) | Ningún ticket los necesita todavía | TKT-014 |
| Ratificar `ROUND_HALF_UP` con negocio y reconciliar el total real de la explosión, `2755187.2112`, con los tipos | Los datos reales no se versionan; el fixture es sintético | TKT-016, con `PA-23` del PRD |
| La segunda puerta `cimenta/<m>/__init__.py` que TKT-002 asignó a «TKT-004 y TKT-009»: la lista blanca la cierra solo para `dominio/` | Esta vez no era el ticket | TKT-009 |
| El contrato propio no ve imports dinámicos (`importlib`, `__import__`, `exec`), ni un subdirectorio de `dominio/` sin `__init__.py`; la biblioteca estándar pasa entera, también `datetime`, `os` y `socket`; y `import cimenta` en un `dominio/` rompe con una excepción de `grimp` de mensaje engañoso (F005) | Límites de la herramienta, declarados en ADR-021 | Ticket de endurecimiento de contratos, junto a TKT-009 |
| TKT-009 debe ejecutar en el pipeline `uv run lint-imports` (15 contratos, y dos pruebas fijan ese número) y `uv run python -m herramientas.verificar_float`; y el verificador de escenarios no mira `test_tkt004_*` | Es del pipeline | TKT-009 |
| `markdownlint-cli2`, `Vale` y `lychee` no se ejecutaron en esta sesión | No están instalados | El pipeline de TKT-009 |
| El cuerpo de ADR-018 aún describe el contrato `forbidden` original; `docs/02-arquitectura.md` §12 y `docs/06-stack-tecnologico.md` §13 no listan ADR-018; el ✅ de «explosión real» en `docs/06-stack-tecnologico.md` apunta a un fixture sintético | Fuera del alcance de este ticket o sin efecto funcional | Siguiente cambio de documentación |
| `design.md` conserva el código literal de `_viene_de_float`, de los límites de entrada y de `verificar_float`, superado por `backend/` | Es el diseño aprobado en el gate | Ninguno: este delta lo supera |
| Un `int` de 41 o 42 dígitos se resume en el mensaje como `Decimal('…')` y no como «int de N bits» | Mensaje corto y correcto; solo menos uniforme | Cuando se toque `numericos.py` |
| Una división puede producir un `Porcentaje` que su propio constructor rechazaría al volver a envolver su `.valor` (cociente menor que unos 1e-13); lo mismo con la heurística de `float` en cocientes de 19 o más dígitos | Los valores de PostgreSQL tienen 18 o menos; `cuantizar` y `serializar` funcionan | Documentado en ADR-020 |
| TKT-005 también modifica `pyproject.toml` y `uv.lock` y traduce a `422` los errores de estos tipos | El segundo que llegue rebasa | TKT-005 |
| Las entregas A y B están en una sola rama y un solo commit | Los hunks de `pyproject.toml`, `CLAUDE.md` y la documentación mezclan A y B | Si se quieren dos PR, separarlos al abrirlos |

## Pull request

**Título:** `TKT-004 · tipos base del dominio con decimal exacto`
**Origen:** `agent`
**Cuerpo:**

Qué: crea el paquete `backend/tipos_base/` con `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje` sobre `Decimal`: aritmética exacta con un contexto propio, redondeo solo con `cuantizar()` (`ROUND_HALF_UP`, `(asumido)`), serialización a cadena de escala completa que no redondea, y rechazo de `float`, de valores no finitos y de entradas con más de 40 decimales o una magnitud de 10^41 o más. Añade el verificador `herramientas.verificar_float` y la regla `RUF032` de Ruff contra el `float` en el dominio, y cierra la deuda `O1` de TKT-002: `dominio-sin-framework` pasa a una lista blanca (solo la biblioteca estándar y `tipos_base`) con un tipo de contrato propio de `import-linter`, y `tipos_base` tiene su propio contrato de pureza. Añade 386 pruebas sin Docker, ADR-020 y ADR-021, y la pregunta abierta `PA-23` del PRD.

Por qué: la regla 1 de `CLAUDE.md` decía que el linter bloquea el `float` y no era cierto, y ningún ticket de negocio puede escribir `RN-03`, `RN-06` ni la explosión de insumos sin tipos de dinero compartidos. Cada ticket habría elegido su propia escala, su modo de redondeo y su forma de serializar.

Criterios cubiertos: `CA-1` a `CA-13` y `CA-R1` a `CA-R7` de `sdd/tickets/tkt-004/spec.md`. Los 33 mutantes anotados en `impl.md`, aplicados de uno en uno con SHA-256 verificado al restaurar, y los de las dos pasadas de revisión, mueren. Decisiones del usuario aplicadas: fixture sintético para los 27 insumos, paquete fuera de `cimenta/`, cuatro tipos con la escala en la frontera, alcance de la regla contra `float` en `dominio/` y `tipos_base/`, la huella heurística de `Decimal(float)`, la lista blanca que también prohíbe la interfaz de otro módulo, `PA-23` y el límite de entrada de 40 decimales y magnitud de 10^41. **Hallazgo a revisar con atención:** el hallazgo Mayor `M-01` de la revisión (un `Decimal('1E+999999999')` bloqueaba el proceso) se resolvió con ese límite, que es un supuesto `(asumido)`.

Cómo verificarlo, con `uv` y Docker instalados:

```bash
cd backend && uv sync --locked
uv run pytest tests/test_tipos_base_*.py tests/test_verificar_float.py tests/test_fronteras_dominio.py tests/test_tkt004_conftest.py   # sin Docker
uv run pytest && uv run ruff check . && uv run mypy . && uv run lint-imports
uv run python -m herramientas.verificar_float
cd .. && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en `sdd/tickets/tkt-004/delta.md`. Auditorías: arquitectura aprobada en la ejecución y en la revisión, tras dos ciclos de corrección; un auditor de código y uno de documentación, por sustitución, porque esos agentes no existen en este entorno. La ejecución se hizo en dos entregas, tipos y linter por un lado y fronteras por otro, sobre una sola rama; el PR es único y, si se prefieren dos, hay que separar los hunks de `pyproject.toml`, `CLAUDE.md` y la documentación.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
