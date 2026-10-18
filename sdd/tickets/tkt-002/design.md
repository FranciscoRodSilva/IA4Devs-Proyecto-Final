# Design · TKT-002 · Esqueleto del backend por capas y verificación de fronteras

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

El ticket se resuelve con paquetes vacíos y con la configuración nativa de `import-linter`, sin ningún script propio. Cada módulo publica su interfaz en un único archivo, `cimenta/<modulo>/interfaz.py`, que vive fuera de las cuatro capas: así las capas enteras quedan privadas y el contrato que las protege no necesita ninguna excepción. Las fronteras se declaran en `[tool.importlinter]` de `backend/pyproject.toml` en cuatro familias de contratos, cada una con un solo trabajo: dos contratos `layers` exhaustivos comprueban el esqueleto, un `forbidden` sin imports indirectos mantiene el dominio libre de framework, un `forbidden` con `allow_indirect_imports` impide entrar al interior de otro módulo, y un `protected` por módulo declara quién puede importarlo. Los nombres de módulo solo aparecen en campos que `import-linter` valida contra el grafo, de modo que un nombre mal escrito rompe la ejecución en lugar de dar verde. Cada contrato nace con su demostración de fallo y con un mutante que demuestra que esa demostración depende de él.

## Fuentes y verificación de la herramienta

**Context7 no respondió**: la consulta de `import-linter` agotó el tiempo de espera de 1800 segundos. El diseño se apoya en tres fuentes, por este orden:

1. **El experimento del orquestador** del 2026-10-17, con `import-linter` 2.15 y `grimp` 3.17, que confirmó `PA-T6`, confirmó `PA-T7` y verificó la configuración en `[tool.importlinter]` de `pyproject.toml` ejecutada con `uv run lint-imports`.
2. **El código fuente de esas mismas versiones**, instalado en el entorno del experimento. Lo leído y lo que se deduce:

| Archivo leído | Hecho | Consecuencia para el diseño |
|---|---|---|
| `importlinter/contracts/forbidden.py` | `source_modules` se valida contra el grafo (`Module '…' does not exist.`). `forbidden_modules` internos que no existen **se descartan en silencio** (`forbidden_modules_in_graph`). Los pares origen-destino que se solapan se omiten, lo que admite un comodín como `cimenta.*.dominio` con origen `cimenta.compras`. Con `allow_indirect_imports` solo se miran imports directos | Ningún nombre de módulo va en `forbidden_modules`: solo comodines de capa y paquetes externos |
| `importlinter/contracts/protected.py` | Comprueba solo imports **directos**. Con `as_packages = true`, tanto `protected_modules` como `allowed_importers` pasan por `find_descendants` o `is_module_squashed`, que en `grimp/application/graph.py` lanzan `ModuleNotPresent` si el módulo no existe | Un nombre mal escrito en cualquiera de los dos campos rompe la ejecución: cubre `CA-7` esc. 1 |
| `importlinter/contracts/layers.py` | Con `containers`, cada capa declarada debe existir en cada contenedor (`Missing layer in container '…': module … does not exist.`); con `exhaustive = true`, cualquier hijo no declarado rompe el contrato (`The following modules are not listed as layers`). `containers` admite comodines | La comprobación del esqueleto (`CA-2`, `CA-3` esc. 2, `CA-7` esc. 2) es nativa |
| `importlinter/application/use_cases.py` | Toda excepción durante la comprobación se captura, se imprime y termina con código 1 | Un nombre inexistente da código distinto de 0, nunca verde |
| `importlinter/cli.py` | `lint-imports` inserta el directorio actual en `sys.path`; ofrece `--contract <id>` y `--no-cache` | No hace falta `[build-system]` si se ejecuta desde `backend/` |
| `grimp/adaptors/caching.py` | La caché `.import_linter_cache/` se crea con su propio `.gitignore` que contiene `*` | No hace falta tocar el `.gitignore` del repositorio |

3. **Las filas 1 a 3 confirman** lo que el experimento no probó: el contrato `protected`, el `layers` exhaustivo de un solo nivel y la validación de nombres. Si alguna de esas confirmaciones falla como se describe en «Riesgos», la fila se detiene y se aplica el plan alternativo escrito allí; si el plan alternativo tampoco basta, se escala.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `import-linter` como dependencia de desarrollo | 3 · reuso | Es la herramienta que ya eligió el [stack §8](../../../docs/06-stack-tecnologico.md#8-calidad-y-herramientas) para sostener ADR-001. Se instala con `uv add --dev import-linter`, que toma la última estable de PyPI (2.15 en el experimento) |
| Configuración en `[tool.importlinter]` de `backend/pyproject.toml` | 4 · cambio mínimo | Un `.importlinter` o un `setup.cfg` aparte serían un archivo más; la sección en `pyproject.toml` funciona, verificado en el experimento |
| `include_external_packages = true` | 2 · nativo | Es lo que permite prohibir `fastapi`, `sqlalchemy` y `pydantic` sin instalarlos (`PA-T6`, confirmada) |
| `exclude_type_checking_imports = false`, explícito | 2 · nativo | Un import bajo `if TYPE_CHECKING:` también acopla y es la forma habitual de esquivar un ciclo: debe contar. Va explícito por la lección de TKT-001: un valor por omisión que nadie escribió es una decisión que nadie ve |
| `[build-system]` y empaquetado | 1 · YAGNI, fuera | `lint-imports` añade el directorio actual a `sys.path` (`importlinter/cli.py`) y el experimento funcionó sin él. Basta ejecutarlo desde `backend/` |
| Entrada en `.gitignore` para `.import_linter_cache/` | 2 · nativo, sin cambio | `grimp` crea la caché con su propio `.gitignore`; TC-37 lo comprueba |
| Contrato `esqueleto-modulos` (`layers` exhaustivo sobre `cimenta`) | 2 · nativo | Detecta un módulo que falta, uno que sobra y uno ausente de la declaración, y valida sus diez nombres. Sustituye a una comprobación propia en `tools/` |
| Contrato `esqueleto-capas` (`layers` exhaustivo sobre `cimenta.*`) | 2 · nativo | Detecta una capa que falta, una interfaz que falta o una segunda, y cubre por comodín cualquier módulo. Declararlo en dos niveles —`dominio` debajo de las otras cuatro piezas— no cuesta ninguna línea y hace cumplir dentro del módulo la regla 2 de `CLAUDE.md`, «`dominio/` no importa nada» |
| Contrato `dominio-sin-framework` (`forbidden`, sin indirectos) | 2 · nativo | `M4`. El nombre es el que ya citan [metodología §10](../../metodologia.md#10--agencia-real) y `conv-dominio-python` |
| Contrato `solo-por-interfaz` (`forbidden` con `allow_indirect_imports`) | 2 · nativo | `M3` y `PA-T8` en un solo contrato, gracias a los comodines y a la omisión de pares solapados |
| Diez contratos `grafo-<modulo>` (`protected`) | 2 · nativo | `M5`. Solo miran imports directos, que es lo que significa una arista del grafo, y validan los dos campos de nombres |
| `broken_contract_guidance` en cada contrato | 2 · nativo | Cuando un contrato se rompe, la salida dice dónde está documentada la frontera y que no se arregla con una excepción. Es lo que mantiene el contrato y `docs/02-arquitectura.md` atados en el momento en que alguien quiere cambiarlos (`S1`) |
| Diez paquetes de módulo y cuarenta de capa | 5 · objeto nuevo, mínimo | `M1`. Los de capa son archivos vacíos; los de módulo, una línea de docstring |
| Diez `interfaz.py` | 5 · objeto nuevo, mínimo | `M2`. Solo docstring; ningún módulo publica nada todavía |
| Docstring de `backend/cimenta/__init__.py` | 4 · cambio mínimo | Hoy dice «Los paquetes de módulo llegan con TKT-002», que deja de ser cierto |
| Comprobación del esqueleto en `tools/` | 1 · YAGNI, fuera | Los dos contratos `layers` exhaustivos la hacen con el mismo comando que vigila las fronteras |
| Verificador automático de que §5 y el contrato coinciden | 1 · YAGNI, fuera | `S1` pide documentar, no un verificador. TC-28 comprueba en este ticket que el contrato coincide arista por arista con la tabla de la spec, y TC-36 que §5 coincide con ella. Queda como sugerencia para TKT-009 |
| Contrato de dirección entre `api`, `aplicacion` e `infraestructura` dentro de un módulo | 1 · YAGNI, fuera | Ningún Must lo pide, y fijarlo ahora condicionaría cómo TKT-005 y los tickets de módulo colocan puertos y adaptadores. El ejemplo `capas` del stack §8 se retira del documento |
| pytest | 1 · YAGNI, fuera | `PA-T3`: el contrato se demuestra con archivos desechables y el código de salida |
| `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md`, ADR-018 | 5 · objeto nuevo | Ver «¿Merece ADR?». Aprobado por el usuario el 2026-10-17 (D-3) |
| Documentación de `docs/`, `CLAUDE.md`, `llms.txt`, `README.md` y `conv-backend-fastapi` | 4 · cambio mínimo | Solo las frases que el grafo declarado contradice y las marcas de disponibilidad |

Ningún objeto que paró en el peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`. La regla 3 recibe una precisión —dónde está la interfaz y quién lo verifica—, no un cambio de contenido.

## Capas afectadas

El ticket no escribe dominio, casos de uso, esquema, API ni frontend. Toca la estructura del backend, su configuración y la documentación.

### Estructura del backend

Sesenta archivos nuevos bajo `backend/cimenta/`, uno por paquete o punto de entrada. Para cada `<m>` de `identidad`, `auditoria`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores` y `analitica`:

| Archivo | Contenido exacto |
|---|---|
| `cimenta/<m>/__init__.py` | Una línea: `"""Módulo <m>. Sin código aquí: otros módulos usan solo cimenta.<m>.interfaz."""` |
| `cimenta/<m>/api/__init__.py` | Vacío, 0 bytes |
| `cimenta/<m>/aplicacion/__init__.py` | Vacío, 0 bytes |
| `cimenta/<m>/dominio/__init__.py` | Vacío, 0 bytes |
| `cimenta/<m>/infraestructura/__init__.py` | Vacío, 0 bytes |
| `cimenta/<m>/interfaz.py` | El docstring de abajo, sin ninguna otra línea |

```python
"""Interfaz publicada de <m>: lo único que otro módulo puede importar.

Quién la importa lo fija el contrato grafo-<m> de pyproject.toml.
"""
```

`avance` y `personal` llevan exactamente lo mismo que los demás: sin clase, función ni constante (`CA-1` esc. 2). La responsabilidad de cada módulo no se repite en su docstring: vive en [arquitectura §5](../../../docs/02-arquitectura.md#5-contextos-delimitados), y una segunda copia divergiría.

`cimenta/__init__.py` pasa a contener solo `"""Backend de CIMENTA. Las fronteras entre sus diez módulos las fija [tool.importlinter] en pyproject.toml."""`.

**El punto de entrada (`PA-T8`)** es `cimenta/<modulo>/interfaz.py`, un módulo hoja al lado de las cuatro capas. Reexporta lo que el módulo publica —casos de uso de `aplicacion/`, los puertos que declara y los tipos que aparecen en sus firmas— y no lo importa nadie de su propio módulo. Las cuatro capas de un módulo son privadas **enteras**: otro módulo no puede importar ni `api/`, ni `aplicacion/` ni nada de dentro, porque la puerta no está dentro de ninguna capa. Las dos alternativas se descartan:

- **`cimenta/<modulo>/aplicacion/__init__.py`.** El contrato tendría que prohibir los hijos de `aplicacion` y permitir el paquete, con un comodín `cimenta.*.aplicacion.*`. El fallo es de ejecución: importar cualquier submódulo, por ejemplo `aplicacion.puertos` desde la `infraestructura` que implementa el puerto, ejecuta antes `aplicacion/__init__.py`, que reexporta los casos de uso, que importan la infraestructura: un ciclo de importación dentro del módulo que ningún contrato ve.
- **`cimenta/<modulo>/__init__.py`.** Python lo ejecuta antes de **cualquier** submódulo, también al importar un `dominio/` puro desde su prueba unitaria: con reexportaciones, cada prueba de una regla cargaría la aplicación y el ORM. Además, prohibir `cimenta.<m>` como paquete prohibiría también su puerta.

`cimenta/<m>/__init__.py` sigue siendo importable por quien tiene la arista, pero no lleva código: su docstring lo dice y el `auditor-arquitectura` lo revisa. Es el único hueco que el contrato no cierra; está en «Riesgos».

### Configuración del backend

`uv add --dev import-linter`, desde `backend/`, añade una línea al grupo `dev` y actualiza `uv.lock`. No se edita a mano. Después, al final de `backend/pyproject.toml`, tras `[[tool.mypy.overrides]]`, se añade este bloque literal. Las secciones `[tool.ruff]` y `[tool.mypy]` no se tocan.

```toml
[tool.importlinter]
root_package = "cimenta"
include_external_packages = true
exclude_type_checking_imports = false

[[tool.importlinter.contracts]]
id = "esqueleto-modulos"
name = "cimenta tiene exactamente los diez módulos de arquitectura §5"
type = "layers"
containers = ["cimenta"]
layers = [
    "identidad : auditoria : archivos : presupuesto : compras : almacen : avance : personal : proveedores : analitica",
]
exhaustive = true
broken_contract_guidance = "Un módulo nuevo o renombrado se decide en un ticket y se documenta en docs/02-arquitectura.md §5 en el mismo cambio."

[[tool.importlinter.contracts]]
id = "esqueleto-capas"
name = "Cada módulo tiene sus cuatro capas y una sola interfaz, y su dominio no importa las otras"
type = "layers"
containers = ["cimenta.*"]
layers = [
    "api : aplicacion : infraestructura : interfaz",
    "dominio",
]
exhaustive = true
broken_contract_guidance = "La estructura de un módulo está en docs/02-arquitectura.md §6, y dominio/ no importa nada de su módulo (regla 2 de CLAUDE.md)."

[[tool.importlinter.contracts]]
id = "dominio-sin-framework"
name = "dominio/ no importa FastAPI, SQLAlchemy ni Pydantic, ni directa ni indirectamente"
type = "forbidden"
source_modules = ["cimenta.*.dominio"]
forbidden_modules = ["fastapi", "sqlalchemy", "pydantic"]
allow_indirect_imports = false
broken_contract_guidance = "El dominio es Python puro (docs/adr/20260918-dominio-puro.md). No se arregla con una excepción en el contrato."

[[tool.importlinter.contracts]]
id = "solo-por-interfaz"
name = "Un módulo usa a otro solo por cimenta.<modulo>.interfaz"
type = "forbidden"
source_modules = ["cimenta.*"]
forbidden_modules = [
    "cimenta.*.api",
    "cimenta.*.aplicacion",
    "cimenta.*.dominio",
    "cimenta.*.infraestructura",
]
allow_indirect_imports = true
broken_contract_guidance = "Otro módulo se usa solo por su interfaz (docs/adr/20260918-monolito-modular.md). No se arregla con una excepción en el contrato."
```

Y los diez contratos del grafo, uno por módulo, en este orden y con esta forma; cambian `<m>` y la lista de `allowed_importers`:

```toml
[[tool.importlinter.contracts]]
id = "grafo-<m>"
name = "Quién puede importar <m>"
type = "protected"
protected_modules = ["cimenta.<m>"]
allowed_importers = [<lista de la tabla>]
as_packages = true
broken_contract_guidance = "La arista no está en el grafo de docs/02-arquitectura.md §5. Una arista nueva la decide el usuario y se añade aquí y en §5 en el mismo cambio."
```

| Contrato | `allowed_importers`, en una sola línea y en este orden |
|---|---|
| `grafo-identidad` | `"cimenta.archivos", "cimenta.presupuesto", "cimenta.compras", "cimenta.almacen", "cimenta.avance", "cimenta.personal", "cimenta.proveedores", "cimenta.analitica"` |
| `grafo-auditoria` | `"cimenta.identidad"` seguido de la misma lista que `grafo-identidad`. La arista `identidad` → `auditoria` la decidió el usuario el 2026-10-17 (D-1) |
| `grafo-archivos` | `"cimenta.presupuesto", "cimenta.almacen", "cimenta.avance"` |
| `grafo-presupuesto` | `"cimenta.compras", "cimenta.almacen", "cimenta.avance", "cimenta.personal", "cimenta.analitica"` |
| `grafo-compras` | `"cimenta.almacen", "cimenta.avance", "cimenta.proveedores", "cimenta.analitica"` |
| `grafo-almacen` | `"cimenta.analitica"` |
| `grafo-avance` | `"cimenta.analitica"` |
| `grafo-personal` | `"cimenta.avance", "cimenta.analitica"` |
| `grafo-proveedores` | `"cimenta.proveedores"` |
| `grafo-analitica` | `"cimenta.analitica"` |

`grafo-proveedores` y `grafo-analitica` se nombran a sí mismos porque nadie los importa y el campo no admite quedar vacío; el propio módulo ya puede importarse a sí mismo, así que la entrada no abre nada. Son 33 aristas permitidas —la tabla «Grafo declarado» de la spec leída desde el importado— y 57 prohibidas de las 90 posibles.

Por qué cada familia tiene su tipo:

- **`solo-por-interfaz` es `forbidden` con `allow_indirect_imports = true` (`PA-T7`).** Sin esa opción, `compras` → `presupuesto.interfaz` → `presupuesto.aplicacion` sería una cadena prohibida y el contrato fallaría por usar la interfaz como se debe. Con ella, el contrato mira solo imports directos, y un import directo de `cimenta.presupuesto.infraestructura` desde `compras` sigue rompiéndolo (confirmado en el experimento). Un solo contrato basta: el origen `cimenta.*` y los destinos `cimenta.*.<capa>` cubren los noventa pares, y la omisión de pares solapados deja a cada módulo usar sus propias capas.
- **`dominio-sin-framework` no lleva `allow_indirect_imports`**: queda en `false`, escrito. Un `dominio/` que llega a SQLAlchemy a través de su propia infraestructura, o de la interfaz de otro módulo cuya infraestructura usa el ORM, viola ADR-003 igual que con un import directo.
- **El grafo es `protected` y no `forbidden`.** Un `forbidden` por módulo de origen tendría que listar 57 destinos prohibidos en `forbidden_modules`, el campo cuyos nombres internos inexistentes se descartan en silencio: una errata dejaría pasar la arista sin aviso. `protected` lista los 33 importadores permitidos, valida cada nombre y solo mira imports directos. Una errata en `allowed_importers` falla además hacia el lado seguro: prohíbe de más, y TC-23 lo detecta.
- **`layers` no expresa el grafo.** Un orden por capas permite toda arista hacia abajo, y el grafo declarado prohíbe varias que irían hacia abajo en cualquier orden, como `compras` → `archivos` o `proveedores` → `presupuesto`. Haría falta un `forbidden` de excepciones, con el grafo partido entre dos mecanismos y mutantes redundantes que no se pueden demostrar.
- **`independence` no sirve**: comprueba también imports indirectos y no tiene opción para ignorarlos, así que todo uso de una interfaz que llegue por dentro a otro módulo independiente lo rompería.

Ningún contrato lleva `ignore_imports`. Una excepción en el contrato es la forma en que se erosiona una frontera, y `conv-dominio-python` y `corrector-revision` ya la prohíben. Por eso tampoco se fija `unmatched_ignore_imports_alerting`: su valor por omisión, `error`, hace fallar una excepción que no coincida con nada si alguien la añadiera.

**Qué valida la herramienta y qué no (`CA-7`).** Los nombres de módulo aparecen solo en campos validados: las capas de `esqueleto-modulos` y los dos campos de los `grafo-<m>`. Los demás contratos usan comodines —`cimenta.*`, `cimenta.*.dominio`, `cimenta.*.api`…—, que cubren por construcción cualquier módulo y no contienen nombres que se puedan escribir mal. Lo que la herramienta no valida, porque un comodín que no coincide con nada o un paquete externo no instalado se descartan sin aviso, son los nombres de capa dentro de un comodín y los tres paquetes externos. Esos los vigilan las demostraciones de rechazo y sus mutantes, no la herramienta.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Todos los comandos se ejecutan **desde `backend/`**, salvo los verificadores de documentación, que van desde la raíz.

**Excepción registrada a la forma de las pruebas**, como en TKT-001 y por `PA-T3`: no hay pytest. Cada caso es un comando con su código de salida y una cadena que debe aparecer o desaparecer en la salida, ejecutado sobre archivos desechables. El rojo de una compuerta es el desechable que la compuerta todavía no rechaza; la prueba de que la demostración depende del contrato es su mutante.

**Reglas comunes a las filas 3 a 6.**

- Las demostraciones ejecutan `uv run lint-imports --no-cache`, para que la caché no esconda un cambio entre dos ejecuciones seguidas. La verificación final de cada fila ejecuta `uv run lint-imports` tal cual, que es el comando documentado.
- Cada desechable vive en un paquete `desechable_tkt002/`, con su `__init__.py` vacío, **dentro de la capa** que nombra el escenario: `backend/cimenta/<modulo>/<capa>/desechable_tkt002/`. No puede ir en `backend/cimenta/desechable_tkt002/`, como en TKT-001, porque `esqueleto-modulos` lo rechazaría como módulo no declarado. Las tres excepciones, `inventado`, `publico.py` y la línea añadida a `presupuesto/interfaz.py`, las fija su caso.
- Cada caso de rechazo se ejecuta **solo**, con únicamente sus desechables presentes, para que su código de salida le pertenezca. Para los mutantes, el caso se repite con `--contract <id>` del contrato mutado.
- Antes de editar `pyproject.toml` o `cimenta/presupuesto/interfaz.py` para un caso o un mutante, se anota su SHA-256; al restaurar, se comprueba que coincide. Los mutantes se aplican de uno en uno y se revierten antes del siguiente.
- La fila termina con TC-37: no queda ningún desechable y los archivos editados recuperan su hash.

Ninguna fila cae en un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo): no hay dinero, límites, bloqueo, autorización, inmutabilidad, permisos de rol de base de datos ni semáforo. Las filas de `ingeniero-devsecops` bajan a `haiku` por la fila de §14.2 «tarea mecánica y verificable por comando»: el contenido exacto está en este diseño. `tester-backend` conserva `sonnet` porque no baja por debajo de quien verifica, y es quien elige qué desechable demuestra qué.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | Instalar `import-linter` y declarar los contratos del esqueleto. Rojo previo: `uv run lint-imports` falla con «program not found». `uv add --dev import-linter`; después `[tool.importlinter]` y los contratos `esqueleto-modulos` y `esqueleto-capas`, literales. El esqueleto todavía no existe | Ninguno: deja TC-01 en rojo por la razón esperada | `ingeniero-devsecops` | `haiku` | `uv sync --locked` con código 0; `uv tree --depth 1` lista como dependencias directas de desarrollo solo `import-linter`, `mypy` y `ruff`; `uv run lint-imports` termina con código 1 y la salida contiene `Missing layer in container 'cimenta'` y `does not exist`. Esa es la prueba de que encuentra el paquete `cimenta` sin `[build-system]`. Si `uv add` resuelve una versión anterior a 2.15, se detiene y se escala | ✓ Hecho |
| 2 | Crear el esqueleto: los sesenta archivos de «Estructura del backend» y el docstring nuevo de `cimenta/__init__.py` | TC-01, TC-02, TC-10, TC-32 | `ingeniero-devsecops` | `haiku` | `uv run lint-imports` con código 0 y `Contracts: 2 kept, 0 broken`; `uv run mypy .` con código 0 y sin `unused section`; `uv run ruff format --check .` y `uv run ruff check .` con código 0; TC-02 | ✓ Hecho |
| 3 | Demostraciones del esqueleto. El tester ejecuta TC-03 a TC-09 y TC-11, que deben rechazar ya, porque el contrato se escribió en la fila 1 antes que el código. Su dependencia del contrato se demuestra con los mutantes M1 a M6. Sin código de producción | TC-03 a TC-09, TC-11, TC-37 | `tester-backend` | `sonnet` | Salida de cada caso y de cada mutante en `impl.md`; TC-37; después TC-01 y TC-10 siguen en verde | ✓ Hecho |
| 4 | Contrato `dominio-sin-framework`. Rojo: el tester crea los desechables de TC-13 a TC-16 y comprueba que **todavía no** se rechazan: TC-13 a TC-15 terminan con código 0, y en TC-16 no aparece la línea de `sqlalchemy`. Verde: el desarrollador añade el contrato literal. El tester repite los casos, ejecuta TC-12 y los mutantes M7 a M9 | TC-12 a TC-16, TC-37 | rojo: `tester-backend` · verde: `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | Salidas en `impl.md`; TC-37; `uv run lint-imports` con `3 kept, 0 broken` | ✓ Hecho |
| 5 | Contrato `solo-por-interfaz`. Rojo: TC-17 a TC-21 terminan con código 0 sin el contrato. Verde: se añade literal. El tester repite, ejecuta TC-22 antes y después del contrato, y los mutantes M10 a M14 | TC-17 a TC-22, TC-37 | rojo: `tester-backend` · verde: `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | Salidas en `impl.md`; TC-37 con el hash de `presupuesto/interfaz.py` restaurado; `uv run lint-imports` con `4 kept, 0 broken` | ✓ Hecho |
| 6 | Los diez contratos `grafo-<m>`. Rojo: TC-24 a TC-28 terminan con código 0 sin ellos. Verde: se añaden literales, en el orden de la tabla. El tester ejecuta TC-23 a TC-30 y los mutantes M15 a M20 | TC-23 a TC-30, TC-37 | rojo: `tester-backend` · verde: `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | Salidas en `impl.md`, incluida la lista de 57 pares de TC-28; TC-37; `uv run lint-imports` con `14 kept, 0 broken` | ✓ Hecho |
| 7 | Documentación y ADR, según «Documentación afectada»: primero el ADR y su fila del índice, después el resto, porque arquitectura §3 enlaza al ADR | TC-33 en su parte documental, TC-34, TC-35, TC-36 | Orquestador, con `conv-documentacion`, por sustitución: no hay agente redactor de documentación ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)) | `haiku` | `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` según TC-34; búsquedas de TC-33; tabla de TC-36 en `impl.md` | ✓ Hecho |
| 8 | Copia limpia y cierre. Copia con su ruta relativa de los archivos que lista `git ls-files --cached --others --exclude-standard` a `<scratchpad>/tkt002-limpia`, como en TKT-001, y en ella TC-31 a TC-33. Si la versión de `uv` o de Python difiere de la anotada en `docs/arranque-local.md`, se actualiza su línea «Verificado en copia limpia» | TC-31, TC-32, TC-33, TC-37 | `ingeniero-devsecops` | `haiku` | Salidas en `impl.md`, con fecha, sistema operativo y versiones de `uv`, Python e `import-linter` | ✓ Hecho |

**Modelo:** `haiku` por omisión; ninguna fila cita disparador de `sonnet` para el desarrollador. Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

## Plan de pruebas

Todos los casos se ejecutan desde `backend/`. «Rechaza» significa código de salida distinto de 0 **y** la cadena indicada en la salida; un código distinto de 0 por otra causa no cuenta.

### Esqueleto

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-01 | `uv run lint-imports` sobre el esqueleto limpio termina con código 0. En la fila 2 informa `2 kept, 0 broken`; en la 6 y en la copia limpia, `14 kept, 0 broken` | feliz | `CA-1` esc. 1, `CA-3` esc. 2 | comando |
| TC-02 | `uv run python -c` con `ast` recorre todo `.py` bajo `cimenta/` y comprueba que su `body` está vacío o es exactamente un `ast.Expr` con un `ast.Constant` de tipo `str`. Imprime el número de archivos revisados, 61, y termina con código 0 | feliz | `CA-1` esc. 2 | comando |
| TC-03 | Se mueve `cimenta/compras/dominio/` fuera de `backend/`, al scratchpad: rechaza con `cimenta.compras.dominio` y `does not exist`. Se devuelve a su sitio | **rechazo** | `CA-2` esc. 1 | comando |
| TC-04 | `cimenta/inventado/__init__.py`, vacío: rechaza y la salida contiene `cimenta.inventado`. Lo detectan los dos contratos del esqueleto; el mutante que aísla `esqueleto-modulos` se demuestra sobre TC-07 | **rechazo** | `CA-2` esc. 2 | comando |
| TC-05 | Se mueve `cimenta/almacen/interfaz.py` al scratchpad: rechaza con `cimenta.almacen.interfaz` y `does not exist` | **rechazo** | `CA-3` esc. 2 | comando |
| TC-06 | `cimenta/almacen/publico.py` con `"""Desechable TKT-002."""`: rechaza con `cimenta.almacen.publico` y `not listed as layers`. Es una segunda puerta | **rechazo** | `CA-3` esc. 2 | comando |
| TC-07 | Se quita `proveedores :` de la capa de `esqueleto-modulos`: rechaza con `cimenta.proveedores` y `not listed as layers` | **rechazo** | `CA-7` esc. 2 | comando |
| TC-08 | En la capa de `esqueleto-modulos`, `presupuesto` pasa a `presupesto`: rechaza con `cimenta.presupesto does not exist` | **rechazo** | `CA-7` esc. 1 | comando |
| TC-09 | `cimenta/compras/dominio/desechable_tkt002/intra.py` con `import cimenta.compras.infraestructura`: rechaza con `cimenta.compras.dominio is not allowed to import cimenta.compras.infraestructura` | **rechazo** | regla 2 de `CLAUDE.md`, borde de `CA-5` | comando |
| TC-10 | `uv run mypy .` termina con código 0 y la salida no contiene `unused section` | regresión | `CA-8` esc. 2 | comando |
| TC-11 | `cimenta/presupuesto/dominio/desechable_tkt002/regla.py` con `def sumar(a, b):` y `return a + b`: `uv run mypy .` termina con código 1 y cita `no-untyped-def`. Rechaza desde ya porque el `override` existe desde TKT-001; lo que demuestra es que alcanza un `dominio/` real, y su mutante es M6 | **rechazo** | `CA-8` esc. 3 | comando |

### Dominio sin framework

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-12 | `cimenta/presupuesto/dominio/desechable_tkt002/puro.py` con `import decimal` e `import cimenta.presupuesto.dominio.desechable_tkt002.otro`, y `otro.py` con un docstring: código 0, antes y después del contrato | feliz | `CA-5` esc. 4 | comando |
| TC-13 | `cimenta/presupuesto/dominio/desechable_tkt002/malo.py` con `import fastapi`: rechaza con `cimenta.presupuesto.dominio is not allowed to import fastapi` | **rechazo** | `CA-5` esc. 1 | comando |
| TC-14 | `cimenta/compras/dominio/desechable_tkt002/malo.py` con `import sqlalchemy`: rechaza con `is not allowed to import sqlalchemy` | **rechazo** | `CA-5` esc. 2 | comando |
| TC-15 | `cimenta/almacen/dominio/desechable_tkt002/malo.py` con `import pydantic`: rechaza con `is not allowed to import pydantic` | **rechazo** | `CA-5` esc. 3 | comando |
| TC-16 | `cimenta/presupuesto/infraestructura/desechable_tkt002/orm.py` con `import sqlalchemy`, y `cimenta/presupuesto/dominio/desechable_tkt002/indirecto.py` que lo importa. Con `--contract dominio-sin-framework`: rechaza con `cimenta.presupuesto.dominio is not allowed to import sqlalchemy` y la cadena pasa por `orm`. Se aísla con `--contract` porque `esqueleto-capas` también lo rechaza | **rechazo** | `CA-5`, borde: indirecto | comando |

### Solo por la interfaz

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-17 | `cimenta/compras/aplicacion/desechable_tkt002/uso.py` con `import cimenta.presupuesto.dominio`: rechaza con `Un módulo usa a otro solo por`, `cimenta.compras is not allowed to import cimenta.presupuesto.dominio` | **rechazo** | `CA-4` esc. 1 | comando |
| TC-18 | `cimenta/almacen/api/desechable_tkt002/ruta.py` con `import cimenta.compras.infraestructura`: rechaza con `cimenta.almacen is not allowed to import cimenta.compras.infraestructura` | **rechazo** | `CA-4` esc. 2 | comando |
| TC-19 | `cimenta/presupuesto/aplicacion/desechable_tkt002/uso.py` con `import cimenta.archivos.infraestructura`: rechaza con `cimenta.archivos.infraestructura` | **rechazo** | `CA-4` esc. 3 | comando |
| TC-20 | `cimenta/compras/aplicacion/desechable_tkt002/uso_aplicacion.py` con `import cimenta.presupuesto.aplicacion`: rechaza con `cimenta.compras is not allowed to import cimenta.presupuesto.aplicacion`. Es la `aplicacion/` ajena más allá del punto de entrada | **rechazo** | `CA-3`, `PA-T8` | comando |
| TC-21 | `cimenta/compras/aplicacion/desechable_tkt002/uso_api.py` con `import cimenta.presupuesto.api`: rechaza con `cimenta.compras is not allowed to import cimenta.presupuesto.api` | **rechazo** | `CA-3`, `PA-T8` | comando |
| TC-22 | Cadena real a través de la interfaz: `cimenta/presupuesto/infraestructura/desechable_tkt002/repositorio.py` con un docstring; `cimenta/presupuesto/aplicacion/desechable_tkt002/caso.py` que lo importa; una línea añadida al final de `cimenta/presupuesto/interfaz.py`, `import cimenta.presupuesto.aplicacion.desechable_tkt002.caso  # desechable TKT-002`; y `cimenta/compras/aplicacion/desechable_tkt002/consumo.py` con `import cimenta.presupuesto.interfaz`. Código 0 antes y después del contrato. Sin la línea añadida, la cadena indirecta no existiría y el caso no probaría nada | feliz, falso positivo | `CA-3` esc. 1, `PA-T7` | comando |

### Grafo

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-23 | Un archivo por cada una de las 33 aristas permitidas, incluida `identidad` → `auditoria`: `cimenta/<origen>/aplicacion/desechable_tkt002/arista_<destino>.py` con `import cimenta.<destino>.interfaz`. Código 0 | feliz | `CA-6` esc. 1 | comando |
| TC-24 | `cimenta/compras/aplicacion/desechable_tkt002/prohibida_analitica.py` con `import cimenta.analitica.interfaz`: rechaza con `Illegal imports of protected package cimenta.analitica` y una línea que empieza por `- cimenta.compras.` | **rechazo** | `CA-6` esc. 2 | comando |
| TC-25 | `cimenta/presupuesto/aplicacion/desechable_tkt002/prohibida_compras.py` con `import cimenta.compras.interfaz`: rechaza con `protected package cimenta.compras` y `- cimenta.presupuesto.` | **rechazo** | `CA-6` esc. 3 | comando |
| TC-26 | `cimenta/archivos/aplicacion/desechable_tkt002/prohibida_presupuesto.py` con `import cimenta.presupuesto.interfaz`: rechaza con `protected package cimenta.presupuesto` y `- cimenta.archivos.` | **rechazo** | `CA-6` esc. 4 | comando |
| TC-27 | `cimenta/compras/aplicacion/desechable_tkt002/prohibida_almacen.py` con `import cimenta.almacen.interfaz`: rechaza con `protected package cimenta.almacen` y `- cimenta.compras.` | **rechazo** | `CA-6` esc. 5 | comando |
| TC-28 | Rechazo exhaustivo. Con los 33 archivos de TC-23 presentes, el tester añade un `prohibida_<destino>.py` por cada uno de los 57 pares que **no** están en la tabla «Grafo declarado» de la spec, generados por un script del scratchpad que lee esa tabla y no el contrato. Rechaza, y el conjunto de pares (origen, destino) extraído de las líneas `- cimenta.<origen>.aplicacion.desechable_tkt002.prohibida_<destino> -> cimenta.<destino>.interfaz` es **exactamente** el de los 57, y `auditoria` → `identidad` está entre ellos; ninguna línea nombra un `arista_` | **rechazo** | `CA-6`, el Must `M5` entero | comando y script, lista en `impl.md` |
| TC-29 | En `grafo-presupuesto`, `protected_modules` pasa a `["cimenta.presupesto"]`: rechaza con `"cimenta.presupesto" not present in the graph` | **rechazo** | `CA-7` esc. 1 | comando |
| TC-30 | En `grafo-compras`, `"cimenta.almacen"` de `allowed_importers` pasa a `"cimenta.almacen_"`: rechaza con `"cimenta.almacen_" not present in the graph` | **rechazo** | `CA-7` esc. 1 | comando |

### Regresión y cierre

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-31 | En la copia limpia, desde `backend/`: `uv sync --locked` y `uv run lint-imports` con código 0 y `14 kept, 0 broken`. `git diff --stat` de `pyproject.toml` frente a `Produccion` muestra la línea de `import-linter` en `dev` y el bloque `[tool.importlinter]`, nada más. `uv tree --depth 1` lista solo `import-linter`, `mypy` y `ruff` como directas | regresión | `CA-8` esc. 1, `CA-R2` | comando |
| TC-32 | `uv run ruff format --check .`, `uv run ruff check .` y `uv run mypy .` con código 0 | regresión | `CA-R1` | comando |
| TC-33 | En `CLAUDE.md`, la línea de `uv run lint-imports` no contiene `desde TKT-002`; la regla 2 contiene `(en el pipeline desde TKT-009)` y no `desde TKT-002`; las líneas de `uv run pytest` y `uv run fastapi dev` conservan su marca literal. En `docs/arranque-local.md`, la tabla «Lo que todavía no arranca» no tiene fila de `lint-imports`. En la copia limpia, `uv run pytest` y `uv run fastapi dev` siguen fallando | regresión | `CA-8` esc. 4, `CA-R3` | búsqueda y comando |
| TC-34 | Desde la raíz, `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py`. Única excepción admitida, la misma de TKT-001: los enlaces del hub a `impl.md` o `delta.md` que aún no existen, listados uno a uno en `impl.md` | regresión | `CA-R4` | comando |
| TC-35 | `verificar_docs.py` no informa ningún problema `Codificación ·`, y `python -c "print(open('.claude/hooks/recordar-caveman.ps1','rb').read(3).hex())"` imprime `efbbbf` | regresión | `CA-R5` | comando |
| TC-36 | Tabla en `impl.md` con una fila por módulo: lo que dice la columna «Importa» de arquitectura §5, lo que dice la tabla de la spec y lo que se deduce de los `allowed_importers` de los diez `grafo-<m>`. Las tres columnas coinciden en las diez filas | revisión | `S1` | revisión |
| TC-37 | Limpieza: no queda ningún directorio `desechable_tkt002` ni `cimenta/inventado` ni `cimenta/almacen/publico.py`; `pyproject.toml` y `cimenta/presupuesto/interfaz.py` tienen el SHA-256 anotado; `git status --short --ignored backend/` muestra `.import_linter_cache/` como `!!` y nunca como `??` | regresión | `CA-R5`, DoD | comando |

**Mutación.** El ticket no toca rutas de dinero, límites ni congelado, pero la DoD exige demostrar que cada contrato hace falta. Cada mutante se aplica solo, se repite el caso indicado y se confirma el cambio de resultado; después se revierte y se comprueba el hash.

| Mutante | Dónde | Resultado esperado del caso |
|---|---|---|
| M1 | `esqueleto-modulos`: `exhaustive = false` | TC-07 pasa a código 0 |
| M2 | `esqueleto-capas`: `exhaustive = false` | TC-06 pasa a código 0 |
| M3 | `esqueleto-capas`: `interfaz` pasa a `(interfaz)`, opcional | TC-05 pasa a código 0 |
| M4 | `esqueleto-capas`: `dominio` pasa a `(dominio)`, opcional | TC-03 pasa a código 0 |
| M5 | `esqueleto-capas` en un solo nivel: `layers = ["api : aplicacion : dominio : infraestructura : interfaz"]` | TC-09 pasa a código 0 |
| M6 | `[[tool.mypy.overrides]]`: `module = ["cimenta.dominio.*"]` | TC-11 pasa a código 0 |
| M7 | `dominio-sin-framework` sin `"pydantic"` | TC-15 pasa a código 0 |
| M8 | `dominio-sin-framework`: `allow_indirect_imports = true` | TC-16 pasa a código 0 |
| M9 | `dominio-sin-framework`: `source_modules = ["cimenta.*.aplicacion"]` | TC-13 pasa a código 0 |
| M10 | `solo-por-interfaz` sin la línea `allow_indirect_imports`, que vale `false` por omisión | **TC-22 pasa a código 1**: el falso positivo que `PA-T7` temía, y la prueba de que la opción es la que lo evita |
| M11 | `solo-por-interfaz` sin `"cimenta.*.dominio"` | TC-17 pasa a código 0 |
| M12 | `solo-por-interfaz` sin `"cimenta.*.infraestructura"` | TC-18 y TC-19 pasan a código 0 |
| M13 | `solo-por-interfaz` sin `"cimenta.*.aplicacion"` | TC-20 pasa a código 0 |
| M14 | `solo-por-interfaz` sin `"cimenta.*.api"` | TC-21 pasa a código 0 |
| M15 | `grafo-analitica` con `"cimenta.compras"` en `allowed_importers` | TC-24 pasa a código 0 |
| M16 | `grafo-compras` con `"cimenta.presupuesto"` en `allowed_importers` | TC-25 pasa a código 0 |
| M17 | `grafo-presupuesto` con `"cimenta.archivos"` en `allowed_importers` | TC-26 pasa a código 0 |
| M18 | `grafo-almacen` con `"cimenta.compras"` en `allowed_importers` | TC-27 pasa a código 0 |
| M19 | `grafo-analitica`: `as_packages = false` | TC-24 pasa a código 0: sin descendientes, el contrato solo protege `cimenta/analitica/__init__.py` y no la interfaz |
| M20 | Se borra el contrato `grafo-proveedores` entero | TC-28 informa 48 pares en lugar de 57: faltan los nueve que apuntan a `proveedores` |

TC-04 no tiene mutante propio: lo rechazan los dos contratos del esqueleto a la vez, y M1 aísla `esqueleto-modulos` sobre TC-07. TC-08, TC-29 y TC-30 no tienen mutante porque prueban una propiedad de la herramienta, no del contrato.

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `backend/pyproject.toml` | Ruff, mypy y `uv` de TKT-001 | Un error de TOML rompe `uv sync --locked`; una edición accidental de `[tool.ruff]` o `[tool.mypy]` cambia las compuertas de TKT-001 | El bloque se añade al final, sin tocar lo anterior; TC-31 revisa el diff y TC-32 corre las tres herramientas |
| `backend/uv.lock` | `CA-5` de TKT-001, `RNF-08` | Que entre algo más que `import-linter` y sus transitivas | TC-31 |
| `[[tool.mypy.overrides]]` empieza a aplicarse | Todo `dominio/` futuro | Es el comportamiento buscado: el modo estricto deja de estar sin uso | TC-10 y TC-11 |
| `CLAUDE.md` | Todos los agentes, en cada sesión | Una marca mal retirada, o una frase que diga otro grafo | TC-33 con texto literal; las frases nuevas salen de este diseño |
| `docs/02-arquitectura.md` y los demás documentos | `verificar_docs.py`, las specs futuras | Un ancla rota o una frase que contradiga el grafo | TC-34 y TC-36 |
| Comandos y agentes que ya citan `lint-imports` (`auditor-arquitectura`, `corrector-revision`, `desarrollador-dominio`, `sdd-revisar`) | El pipeline SDD | Ninguno: el comando que nombran empieza a funcionar con el mismo nombre | — |
| TKT-003 | Migraciones con Alembic | Si el entorno de Alembic se coloca dentro de `cimenta/` como hijo nuevo, `esqueleto-modulos` lo rechaza | Va fuera del paquete, por ejemplo en `backend/migraciones/`, o el ticket ajusta el contrato con la decisión documentada |
| TKT-004 | Tipos compartidos, como `Dinero` | Un paquete compartido bajo `cimenta/` rompe `esqueleto-modulos`, y un `dominio/` que lo importe necesita ajustar el contrato | Ya está en los non-goals de la spec: lo decide TKT-004 |
| TKT-005 | La aplicación FastAPI y su raíz de composición | La raíz monta los enrutadores de los diez `api/`. Si vive en `cimenta/` como `cimenta.principal`, la rechazan `esqueleto-modulos`, `solo-por-interfaz` y los diez `grafo-<m>` | TKT-005 decide dónde vive, fuera de `cimenta/` o como excepción declarada en el contrato y documentada. Es también donde se conectan los adaptadores de los puertos, como `CatalogoProveedores` |
| TKT-006 y TKT-007 | Identidad y bitácora | TKT-006 usa el servicio `DENEGAR` de TKT-007, y `GET /bitacora`, de `auditoria`, exige rol | Resuelto (D-1): `identidad` → `auditoria` está declarada. `auditoria` → `identidad` sigue prohibida, así que la comprobación de rol de `GET /bitacora` la resuelven TKT-005 o TKT-007 sin esa arista, por ejemplo aplicando la dependencia al montar el enrutador desde la raíz de composición |
| TKT-009 | CI | `lint-imports` debe ejecutarse desde `backend/` | Documentado en `docs/arranque-local.md`; deuda para TKT-009 |
| TKT-060, TKT-069 | Sus criterios | Dicen que ellos declaran `compras ↛ analitica` y `avance → compras` | Se corrigen sus textos en este cambio |
| TKT-066 | «Ningún `dominio/` importa de `archivos`» | Lo añadirá como contrato nuevo; con `dominio-sin-framework` sin indirectos, un `dominio/` que use cualquier interfaz cuya infraestructura importe el ORM ya falla | Ninguno: es coherente con ADR-003 |

**Fronteras entre módulos:** no. El ticket no hace hablar a ningún módulo con otro; declara y verifica las fronteras.

## Documentación afectada

Todos los textos de reemplazo son literales para que la fila 7 los copie sin reformular: es la lección de la reauditoría de TKT-001.

| Documento | Qué cambia |
|---|---|
| `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` (nuevo) | MADR, estado `Aceptado`. **Contexto:** ADR-001 exige que un módulo hable con otro solo por su interfaz y que se verifique automáticamente, sin decir dónde está la interfaz ni cómo se verifica. **Opciones**, en tres decisiones: punto de entrada en `interfaz.py`, en `aplicacion/__init__.py` o en el `__init__.py` del módulo; grafo con `protected` por módulo, con `forbidden` por origen, con `layers` o con `independence`; esqueleto con `layers` exhaustivo o con una función en `tools/`. **Decisión:** las cuatro familias de este diseño, con el porqué de «Configuración del backend». **Consecuencias:** sin excepciones en el contrato; nombres validados; comodines y paquetes externos sin validar y cubiertos por demostraciones; `cimenta/<m>/__init__.py` sin código por convención; la raíz de composición queda para TKT-005. **Cuándo revisar:** si `import-linter` deja de validar los nombres o si un módulo necesita una segunda puerta |
| `docs/adr/README.md` | Fila nueva en el índice, con las columnas de las demás: fecha `2026-10-17`; decisión «Interfaz publicada en un único archivo y fronteras verificadas con import-linter», enlazada al archivo del ADR con ruta relativa al índice; estado `Aceptado`; afecta a «Todo el backend» |
| `CLAUDE.md` | (1) Línea 14: `17 decisiones` → `18 decisiones`. (2) Regla 2: `(desde TKT-002; en el pipeline desde TKT-009)` → `(en el pipeline desde TKT-009)`. (3) Regla 3: `Nunca por sus repositorios, modelos o tablas.` → `Nunca por sus repositorios, modelos o tablas: solo por cimenta.<modulo>.interfaz, y import-linter lo verifica (en el pipeline desde TKT-009).`, con `cimenta.<modulo>.interfaz` e `import-linter` entre comillas invertidas. (4) Bloque «Estructura del backend»: `└── infraestructura/` pasa a `├── infraestructura/` y se añade al final `└── interfaz.py       Interfaz publicada: lo único que otro módulo importa`. (5) La frase de `presupuesto` y `analitica` pasa a: `` `presupuesto` es el núcleo y no depende de ningún módulo de negocio. `analitica` lee de los demás —salvo `archivos` y `proveedores`— y **solo lee**; ningún módulo la importa. Quién importa a quién: arquitectura §5 (`docs/02-arquitectura.md`, sección 5). `` (6) Línea de comandos: `# fronteras entre módulos · desde TKT-002` → `# esqueleto y fronteras entre módulos` |
| `docs/arranque-local.md` | En el bloque «Backend», `uv run lint-imports` tras `uv run mypy .`, y este párrafo tras el que explica los tres comandos: «`uv run lint-imports` comprueba que existan los diez módulos con sus cuatro capas y su `interfaz.py`, que ningún `dominio/` importe FastAPI, SQLAlchemy ni Pydantic, y que un módulo importe a otro solo por su interfaz y solo si el grafo de arquitectura §5 (enlace relativo al documento destino) lo permite. Se ejecuta desde `backend/`, porque busca el paquete `cimenta` en el directorio actual. Su caché, `.import_linter_cache/`, se ignora sola.» Se borra la fila de `uv run lint-imports` de «Lo que todavía no arranca» |
| `docs/02-arquitectura.md` §3 | `Se verifica automáticamente en CI mediante análisis de dependencias entre paquetes.` → `Se verifica automáticamente con análisis de dependencias entre paquetes: uv run lint-imports, con los contratos de [tool.importlinter] en backend/pyproject.toml.` Y un párrafo nuevo después: «**La interfaz publicada de un módulo es un único archivo, `cimenta/<modulo>/interfaz.py`.** Sus capas `api/`, `aplicacion/`, `dominio/` e `infraestructura/` son privadas enteras: otro módulo no importa nada de ellas, tampoco de `aplicacion/`. La interfaz reexporta lo que el módulo publica y es lo único que otro módulo puede importar, y solo si el grafo de §5 se lo permite. Por qué esta forma y estos contratos: ADR del 2026-10-17.», donde «ADR del 2026-10-17» es un enlace relativo a `adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` |
| `docs/02-arquitectura.md` §4 | `` `presupuesto` es el núcleo y no depende de nadie. `analítica` depende de todos pero **solo lee** `` → `` `presupuesto` es el núcleo y no depende de ningún módulo de negocio. `analítica` depende de todos los de negocio salvo `proveedores`, pero **solo lee** ``, conservando el resto de la frase. Al final del párrafo: «Las flechas hacia los transversales no se dibujan: están en §5.» |
| `docs/02-arquitectura.md` §5 | La columna «Depende de» pasa a llamarse «Importa, solo por su interfaz», con estos valores: identidad `auditoría`; auditoría `—`; archivos `identidad, auditoría`; presupuesto `identidad, auditoría, archivos`; compras `presupuesto, identidad, auditoría`; almacén `compras, presupuesto, identidad, auditoría, archivos`; avance `presupuesto, personal, compras, identidad, auditoría, archivos`; personal `presupuesto, identidad, auditoría`; proveedores `compras, identidad, auditoría`; analítica `presupuesto, compras, almacén, avance, personal, identidad, auditoría` *(lectura)*. En la fila de archivos, `**No conoce a nadie**` → `**No conoce a ningún módulo de negocio**`. Tras la tabla: «**El contrato es la fuente de esta columna.** Cada módulo tiene en `backend/pyproject.toml` un contrato `grafo-<modulo>` que enumera quién puede importarlo; la columna es ese mismo grafo leído desde quien importa. Ningún módulo importa `analitica` ni `proveedores`; `auditoria` no importa a ninguno, e `identidad` solo a `auditoria`, para asentar las denegaciones. Una arista nueva la decide el usuario y se añade al contrato y a esta tabla en el mismo cambio.» |
| `docs/02-arquitectura.md` §6 | En el árbol, `└── infraestructura/` pasa a `├── infraestructura/` y se añade `└── interfaz.py       Interfaz publicada: lo único que otro módulo puede importar` |
| `docs/02-arquitectura.md` §7.7 | `` **El módulo `archivos` no conoce a ningún otro, y ninguno lo conoce a él por dentro.** `` → `` **El módulo `archivos` no conoce a ningún módulo de negocio, y ninguno lo conoce a él por dentro.** Solo usa `identidad`, para comprobar el rol al emitir una URL, y `auditoria`, para asentar el hash en la bitácora. `` |
| `docs/06-stack-tecnologico.md` §8 | En la fila de import-linter, tras «o si `dominio/` importa el framework», se añade «, o si un módulo importa a otro que el grafo no le permite». El párrafo «Los contratos se declaran así:» y el bloque `ini` se sustituyen por: «Los contratos viven en `[tool.importlinter]` de `backend/pyproject.toml`, que es su única fuente, y forman cuatro familias:» y una tabla de tres columnas —contratos, tipo, qué hace fallar— con las filas: `esqueleto-modulos` y `esqueleto-capas`, `layers` exhaustivo, «un módulo o una capa que faltan o sobran, una segunda interfaz, o un `dominio/` que importa otra capa de su módulo»; `dominio-sin-framework`, `forbidden` con indirectos, «un `dominio/` que llega a FastAPI, SQLAlchemy o Pydantic, aunque sea a través de otro módulo»; `solo-por-interfaz`, `forbidden` solo directos, «un módulo que importa `api/`, `aplicacion/`, `dominio/` o `infraestructura/` de otro»; `grafo-<modulo>`, uno por módulo, `protected`, «un módulo que importa a otro que el grafo de arquitectura §5 (enlace relativo al documento destino) no le permite». Cierra con «Por qué estos tipos: ADR del 2026-10-17.», donde «ADR del 2026-10-17» es un enlace relativo a `adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` |
| `docs/03-modelo-datos.md` §11 | `` `presupuesto` no depende de `archivos`, y la referencia se valida por la interfaz publicada de `archivos` al crear la importación `` → `` en el esquema `presupuesto` no depende de `archivos`; en el código lo usa solo por su interfaz publicada, que valida la referencia al crear la importación `` |
| `docs/07-especificacion-api.md` | `` `archivos` no conoce a nadie `` → `` `archivos` no conoce a ningún módulo de negocio `` |
| `docs/05-tickets-trabajo.md` | TKT-059: `—no conoce a ningún otro módulo—` → `—no conoce a ningún módulo de negocio—`. TKT-060: `` Un contrato de `import-linter` impide que `compras` importe `analitica` `` → `` El contrato `grafo-analitica` de TKT-002 ya impide que `compras` importe `analitica`, y este ticket no lo relaja ``. TKT-064: `` El único que depende de todos es `analitica` `` → `` El único que depende a la vez de `almacen` y de `avance` es `analitica` ``. TKT-069: `` y se declara en el contrato de `import-linter` en este mismo PR `` → `` y ya está declarada en el contrato `grafo-compras` desde TKT-002 `` |
| `.claude/skills/conv-backend-fastapi/SKILL.md` §3 | La frase de `presupuesto` y `analitica`, la misma de `CLAUDE.md` (5) sin el enlace. Y al final del primer párrafo: «Lo publica en `cimenta/<modulo>/interfaz.py`, y `uv run lint-imports` rechaza cualquier otro import.» |
| `README.md`, `llms.txt` | `17 ADRs` → `18 ADRs`. En `llms.txt`, la línea «Un módulo solo habla con otro a través de su interfaz de aplicación publicada» termina con «: `cimenta/<modulo>/interfaz.py`, verificado con `import-linter`» |

No se toca ningún diagrama Mermaid: la frase añadida a §4 explica por qué las aristas hacia los transversales no se dibujan.

## ¿Merece ADR?

**Sí**: es el ADR-018, aprobado por el usuario el 2026-10-17 (D-3), y lo escribe la fila 7. Cumple las dos condiciones de [conv-documentacion §6](../../../.claude/skills/conv-documentacion/SKILL.md): quien llegue verá un `interfaz.py` que no está en ninguna de las cuatro capas de ADR-003 y un contrato que mira imports indirectos para el dominio pero no para el interior, y se preguntará por qué; y hubo opciones descartadas con motivo en tres decisiones distintas. A diferencia de las elecciones de TKT-001, esta no es configuración reversible en minutos: el nombre de la puerta condiciona cada ticket de módulo, y los tickets TKT-004, TKT-005, TKT-059, TKT-060, TKT-066 y TKT-069 tocarán el contrato sabiendo por qué tiene la forma que tiene.

## Decisiones sobre las preguntas abiertas

| # | Decisión |
|---|---|
| `PA-T5` | Las aristas hacia los transversales son exactamente las de la tabla «Grafo declarado»: `identidad` y `auditoria` las importan los otros ocho módulos, incluida `analitica` con su `(asumido)`, que se conserva; `identidad` importa `auditoria` y `auditoria` no importa a nadie (D-1); `archivos` lo importan solo `presupuesto`, `almacen` y `avance` (D-2). Se sigue la tabla y no la frase del hub «todo módulo puede importar `identidad`, `auditoria` y `archivos`», porque la tabla es la decisión precisa y cada arista hacia `archivos` tiene un ticket que la usa |
| `PA-T6` | Confirmada por el experimento: con `include_external_packages = true`, el contrato detecta `import fastapi` sin que FastAPI esté instalado. No se instala nada más; no hay escalación |
| `PA-T7` | `solo-por-interfaz` es un `forbidden` con `allow_indirect_imports = true`, verificado en el experimento. El grafo usa `protected`, que mira solo imports directos de forma nativa. `dominio-sin-framework` sí mira indirectos. TC-22 y el mutante M10 lo demuestran |
| `PA-T8` | El punto de entrada es `cimenta/<modulo>/interfaz.py`, un módulo hoja fuera de las cuatro capas. Lo hace único `esqueleto-capas`, que lo exige en cada módulo y rechaza cualquier hijo no declarado (TC-05 y TC-06); lo hace la única puerta `solo-por-interfaz`, que prohíbe las cuatro capas ajenas enteras, `aplicacion/` incluida (TC-20 y TC-21) |

## Decisiones del gate humano

Resueltas por el usuario el 2026-10-17. Ya están aplicadas en este diseño; ninguna queda pendiente.

| # | Pregunta | Decisión | Dónde se aplica |
|---|---|---|---|
| D-1 | TKT-006 asienta los `403` con el servicio `DENEGAR` que crea TKT-007, lo que exige `identidad` → `auditoria`. A la vez, `GET /bitacora`, de `auditoria`, exige rol: si lo comprobara importando `identidad`, habría ciclo | **Se permite `identidad` → `auditoria`**, que es acíclica porque `auditoria` no importa nada. `auditoria` → `identidad` sigue prohibida: la comprobación de rol de `GET /bitacora` la resuelven TKT-005 o TKT-007 sin esa arista | `grafo-auditoria` empieza por `"cimenta.identidad"`; §5 da `auditoría` en la fila de identidad; 33 aristas permitidas en TC-23 y 57 pares prohibidos en TC-28; M20 espera 48. Tabla «Grafo declarado» de la spec actualizada |
| D-2 | La frase del hub dice que todo módulo puede importar `archivos`; la tabla solo se lo permite a `presupuesto`, `almacen` y `avance` | **Se mantiene la tabla.** Las facturas de proveedores con su CFDI son F8.3, v1.1, y abrirán `proveedores` → `archivos` cuando lleguen | `grafo-archivos` |
| D-3 | ¿Se escribe el ADR? | **Sí**: ADR-018, `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md`, y el conteo pasa de 17 a 18 | Fila 7 y «Documentación afectada» |
| D-4 | `esqueleto-capas` en dos niveles hace cumplir dentro del módulo la regla 2, «`dominio/` no importa nada», además de lo que pide `M4` | **Se incluye** en dos niveles | `esqueleto-capas`, TC-09 y M5 |

## Pasada adversarial

Pasada del propio arquitecto con el método de `abogado-del-diablo` (modo A); el orquestador puede despacharla de nuevo en el gate.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Un `forbidden` descarta en silencio los módulos internos de `forbidden_modules` que no existen: con el grafo escrito así, una errata dejaría pasar una arista prohibida con el contrato en verde | Ningún nombre de módulo va en `forbidden_modules`. El grafo es `protected`, cuyos dos campos se validan; TC-08, TC-29 y TC-30 lo demuestran |
| 2 | Alta | El grafo de la spec prohibía `identidad` → `auditoria`, y TKT-006 la necesita | Resuelta por el usuario (D-1): la arista se permite y la tabla de la spec se actualizó |
| 3 | Alta | Las 33 aristas permitidas y las cuatro prohibidas de la spec no prueban que el contrato coincide con la tabla: cualquier arista no muestreada podría estar mal | TC-28 genera los 57 pares prohibidos desde la tabla, no desde el contrato, y exige el conjunto exacto. M20 demuestra que lo detecta |
| 4 | Media | El contrato `esqueleto-modulos` usa un `layers` de un solo nivel, un uso poco habitual | El código de `layers.py` no exige dos niveles; la fila 1 lo confirma con su rojo. Plan alternativo en «Riesgos» |
| 5 | Media | `cimenta/<m>/__init__.py` es una segunda puerta que el contrato no cierra | Docstring «Sin código aquí», ADR y revisión de `auditor-arquitectura`. Queda en «Riesgos» |
| 6 | Media | Los nombres de capa dentro de los comodines y los tres paquetes externos no los valida la herramienta | Cada uno tiene su demostración y su mutante (M7, M9, M11 a M14); el límite queda escrito en el ADR |
| 7 | Media | La raíz de composición de TKT-005 chocará con tres familias de contratos | En «Impacto», con dueño |
| 8 | Media | Los desechables dentro de las capas reales pueden quedarse en el repositorio | Paquete con nombre fijo `desechable_tkt002`, TC-37 al final de cada fila y hashes de los archivos editados |
| 9 | Media | `dominio-sin-framework` con indirectos hará fallar a un `dominio/` que use la interfaz de otro módulo en cuanto su infraestructura importe SQLAlchemy | Es lo que exige ADR-003; queda dicho en «Impacto» para TKT-004 y TKT-066 |
| 10 | Baja | Diez contratos `protected` alargan `pyproject.toml` | Cada uno se corresponde con una fila de §5 y nombra el módulo en el informe, lo que facilita leerlo y mutarlo |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| `lint-imports` rechaza un `layers` de un solo nivel en `esqueleto-modulos` | Baja | Medio | Se declara en dos niveles: `"analitica \| proveedores"` arriba, como capa independiente, y los otros ocho separados por `:` abajo. Es coherente con el grafo, porque nadie importa esos dos. Se anota en `impl.md`, y M15 y M20 se demuestran con `--contract` sobre su contrato |
| `protected` no lanza `ModuleNotPresent` con un nombre mal escrito en la versión resuelta | Baja | Alto | TC-29 y TC-30 lo detectan. Si fallan, la fila 6 se detiene y se escala: `CA-7` no se cumpliría de forma nativa y no se improvisa un verificador |
| La última versión de `import-linter` es anterior a 2.15 o cambia el comportamiento leído | Muy baja | Medio | La fila 1 comprueba la versión; las filas 3 a 6 comprueban cada comportamiento con su salida |
| Queda un desechable o un mutante sin revertir | Media | Alto | TC-37 en cada fila y comparación de hashes |
| `cimenta/<m>/__init__.py` acaba con código y se usa como segunda puerta | Baja | Medio | Docstring, ADR y `auditor-arquitectura`; un contrato que lo impida queda como mejora si llega a ocurrir |
| La caché de `import-linter` esconde un cambio durante las demostraciones | Baja | Bajo | `--no-cache` en todas las demostraciones |
| La documentación crece más de lo estimado | Baja | Bajo | Estimación: unas 300 líneas escritas a mano. Unas 115 de `pyproject.toml`, unas 50 de docstrings en los sesenta archivos —cuarenta de ellos vacíos—, unas 65 del ADR y unas 70 de documentación. Sin contar `uv.lock` ni los desechables. Por debajo del tope de 400; no se propone partir el ticket |
