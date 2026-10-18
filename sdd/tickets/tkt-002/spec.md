# Spec · TKT-002 · Esqueleto del backend por capas y verificación de fronteras

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

El backend de CIMENTA es hoy un paquete raíz vacío: `backend/cimenta/__init__.py` con un docstring, y las herramientas de calidad que dejó [TKT-001](../tkt-001/_index.md). No existe ninguno de los diez módulos de la arquitectura, ni sus cuatro capas, ni nada que impida que un módulo importe las entrañas de otro.

Ese último punto es el que justifica el ticket. La [decisión de monolito modular (ADR-001)](../../../docs/adr/20260918-monolito-modular.md) solo se sostiene si las fronteras entre módulos se verifican de forma automática: sin verificación, el monolito modular degenera en un monolito con carpetas a los pocos sprints. La [decisión de dominio puro (ADR-003)](../../../docs/adr/20260918-dominio-puro.md) necesita lo mismo para la capa `dominio/`, que no puede conocer el framework web ni el ORM.

Este ticket de fundación entrega el esqueleto y el contrato que lo vigila, y declara el grafo de dependencias entre módulos **entero y una sola vez**, incluidos los módulos que solo cobran contenido en la fase 2. No implementa lógica de ningún módulo.

Estado de partida, criterio por criterio:

| Criterio del ticket | Estado de partida |
|---|---|
| Diez paquetes de módulo | No existe ninguno |
| `archivos` aislado | No existe |
| `avance` y `personal` vacíos | No existen |
| Cuatro capas por módulo | No existen |
| Interfaz de aplicación publicada en un único punto de entrada | No existe, y ningún documento fija su nombre |
| Verificación: ningún módulo importa `dominio/` ni `infraestructura/` de otro | `import-linter` no está instalado y no hay contrato; `uv run lint-imports` responde «program not found» |
| Verificación: `dominio/` no importa el framework web ni el ORM | No existe |
| Grafo coincide con arquitectura §4 | No existe |

TKT-001 dejó además deuda para este ticket: el patrón de mypy estricto `cimenta.*.dominio.*` solo se probó con archivos desechables, y hoy `mypy` imprime `note: unused section(s)` porque ningún `dominio/` real lo satisface.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario asociada. El rol que lo usa es quien desarrolla el proyecto, persona o agente.

**Como** persona o agente que desarrolla CIMENTA
**quiero** que cada módulo tenga su esqueleto de capas y que un comando falle cuando un módulo cruza la frontera de otro o cuando el dominio importa el framework
**para** que ninguna frontera se erosione sin que nadie lo note y para que los tickets de negocio se escriban sobre una arquitectura que se vigila sola.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Diez paquetes de módulo bajo `backend/cimenta/` (`identidad`, `auditoria`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores`, `analitica`), cada uno con sus carpetas `api/`, `aplicacion/`, `dominio/` e `infraestructura/`; `avance` y `personal` quedan vacíos, solo con lo imprescindible para existir como paquete |
| | **M2.** Cada módulo expone su interfaz de aplicación publicada en un único punto de entrada; el nombre y el archivo los fija el diseño |
| | **M3.** `import-linter` instalado, con un contrato que falla si un módulo importa de `dominio/` o de `infraestructura/` de otro |
| | **M4.** El contrato falla también si `dominio/` importa `fastapi`, `sqlalchemy` o `pydantic` |
| | **M5.** El grafo de dependencias entre módulos declarado entero: el de [arquitectura §4](../../../docs/02-arquitectura.md#nivel-3--componentes-del-api) más los tres módulos transversales (ver «Grafo declarado»), con `archivos` aislado, `compras` sin importar `analitica` y `avance → compras` ya declarada |
| | **M6.** `uv run lint-imports` funciona y termina en verde sobre el esqueleto; las marcas «desde TKT-002» de `CLAUDE.md` y `docs/arranque-local.md` se retiran; mypy estricto alcanza los `dominio/` reales y desaparece la nota `unused section` |
| **Should** | **S1.** El grafo declarado y el nombre del punto de entrada quedan documentados en la arquitectura, para que el contrato y el documento no diverjan |
| **Could** | — |
| **Won't** | Lógica de cualquier módulo · FastAPI, SQLAlchemy, Pydantic y pytest instalados (llegan con TKT-003 a TKT-005) · CI (TKT-009) · regla de Ruff contra `float` y tipos compartidos (TKT-004) · excepción de dominio y contrato de error (TKT-005) · «`analitica` solo lee» en tiempo de ejecución (TKT-003, mediante los roles de base de datos) · contrato «ningún `dominio/` importa de `archivos`» (TKT-067, fase 2) |

## Grafo declarado

Esta tabla es la decisión del usuario del 2026-10-17 y la base de `M5`. «Importa» significa **solo por la interfaz de aplicación publicada** del otro módulo, nunca por su `dominio/` ni su `infraestructura/`.

| Módulo | Puede importar (por interfaz) | Fuente |
|---|---|---|
| `identidad` | `auditoria` | TKT-006 y TKT-007: `identidad` asienta las denegaciones (`DENEGAR`) con el servicio de `auditoria`. Decisión del usuario, 2026-10-17; `auditoria` sigue sin importar `identidad` |
| `auditoria` | — | Arquitectura §5 |
| `archivos` | `identidad`, `auditoria` | TKT-059: comprueba el rol y asienta la bitácora. **Excepción a «no conoce a nadie»** de §7.7, decidida por el usuario |
| `presupuesto` | `identidad`, `auditoria`, `archivos` | §4 y TKT-018: `presupuesto` registra el archivo del Excel. «No depende de nadie» se lee como «de ningún módulo de negocio» |
| `compras` | `presupuesto`, `identidad`, `auditoria` | §4 |
| `almacen` | `compras`, `presupuesto`, `identidad`, `auditoria`, `archivos` | §4 y fase 2 |
| `proveedores` | `compras`, `identidad`, `auditoria` | §4 |
| `personal` | `presupuesto`, `identidad`, `auditoria` | §4 |
| `avance` | `compras`, `presupuesto`, `personal`, `identidad`, `auditoria`, `archivos` | §4 y fase 2 |
| `analitica` | `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `identidad`, `auditoria` `(asumido)` | §4. La dependencia de `identidad` y `auditoria` es `(asumido)` |

Quedan prohibidas, entre otras, estas aristas: cualquier módulo importando `analitica`; `presupuesto` importando `compras`, `almacen`, `avance`, `personal` o `proveedores`; `archivos` importando cualquier módulo de negocio; `auditoria` importando a cualquiera; `identidad` importando cualquier módulo que no sea `auditoria`.

## Non-goals

- No implementa lógica de ningún módulo: ni reglas, ni casos de uso, ni rutas, ni modelos.
- No instala FastAPI, SQLAlchemy, Pydantic, Alembic ni pytest. El contrato de `M4` nombra `fastapi`, `sqlalchemy` y `pydantic` como paquetes prohibidos sin necesidad de que estén instalados `(asumido, a confirmar en el diseño con la documentación de import-linter)`. Si la herramienta exige que estén instalados, es una **escalación**, no una decisión del diseño.
- No configura CI: eso es TKT-009. El contrato corre en local con `uv run lint-imports`.
- No garantiza en tiempo de ejecución que `analitica` solo lea: import-linter comprueba quién importa a quién, no quién escribe. Esa garantía es de TKT-003, con el rol de solo lectura de la base de datos.
- No decide dónde viven los tipos compartidos ni la excepción de dominio: son TKT-004 y TKT-005. Si necesitan importarse desde `dominio/`, ese ticket ajusta el contrato.
- No añade la regla contra `float`.

## Reglas de negocio implicadas

Ninguna regla `RN-xx`: el ticket no tiene lógica de negocio. Sostiene decisiones de arquitectura y dos requisitos.

| Referencia | Qué exige | Dónde está |
|---|---|---|
| ADR-001 | Monolito modular: un módulo solo habla con otro por su interfaz de aplicación publicada | [`docs/adr/20260918-monolito-modular.md`](../../../docs/adr/20260918-monolito-modular.md) |
| ADR-003 | Dominio puro: `dominio/` sin framework web ni ORM | [`docs/adr/20260918-dominio-puro.md`](../../../docs/adr/20260918-dominio-puro.md) |
| `CLAUDE.md` reglas 2 y 3 | `dominio/` no importa nada; un módulo solo habla con otro por su interfaz publicada | [`CLAUDE.md`](../../../CLAUDE.md) |
| `RNF-09` | La mitad «`analitica` solo lee» se verifica en tiempo de ejecución con los roles de base de datos, no con este contrato | [PRD §9](../../../docs/01-descripcion-producto.md#9-requisitos-no-funcionales) |

## Invariantes que deben sobrevivir al cambio

El ticket no crea tablas y no pone en riesgo ninguno de los 38 invariantes del modelo de datos. Sí modifica archivos que ya funcionan: `backend/pyproject.toml` y `backend/uv.lock`, `CLAUDE.md` y `docs/arranque-local.md`. Estas son las garantías de TKT-001 que deben sobrevivir:

| Garantía existente | Qué protege | Criterio de regresión |
|---|---|---|
| Ruff y mypy terminan en verde sobre `backend/` con sus reglas actuales | Que la base de calidad de TKT-001 no se rompa al añadir código | `CA-R1` |
| `uv sync --locked` sigue funcionando con el archivo de bloqueo actualizado | Instalación reproducible y versiones exactas (`RNF-08`) | `CA-R2` |
| Las marcas «desde TKT-xxx» de otros tickets siguen intactas | Que `uv run pytest` y `uv run fastapi dev` sigan diciendo que todavía no funcionan | `CA-R3` |
| `python tools/verificar_docs.py` sigue en verde | Enlaces, anclas e identificadores de la documentación | `CA-R4` |
| Los archivos nuevos no llevan BOM ni finales de línea fuera de LF | La comprobación de codificación de TKT-001 | `CA-R5` |

## Criterios de aceptación

Gherkin, en español. Como no hay reglas de negocio, el «rechazo» de cada criterio es la demostración de que la verificación **falla** ante su violación: un contrato que nunca se ha visto fallar no está verificado.

### CA-1 `[M]` · El esqueleto tiene los diez módulos y las cuatro capas · M1

```gherkin
Escenario: Cada módulo existe con sus capas
  Dado el repositorio con el ticket aplicado
  Cuando se listan los directorios bajo "backend/cimenta/"
  Entonces existen exactamente los diez paquetes: identidad, auditoria, archivos, presupuesto, compras, almacen, avance, personal, proveedores y analitica
  Y cada uno contiene los paquetes "api", "aplicacion", "dominio" e "infraestructura"
  Y cada directorio de módulo y de capa es un paquete importable de Python

Escenario: Los módulos de la fase 2 existen sin contenido
  Dado los paquetes "avance" y "personal"
  Cuando se inspeccionan sus archivos
  Entonces no contienen ninguna clase, función ni constante de negocio
```

### CA-2 `[M]` · Rechazo · Falta una capa o un módulo · M1

```gherkin
Escenario: Un módulo sin su capa de dominio se detecta
  Dado un módulo del esqueleto al que se le quita su carpeta "dominio"
  Cuando se ejecuta la comprobación del esqueleto
  Entonces la comprobación termina con código distinto de 0
  Y nombra el módulo y la capa ausentes

Escenario: Un módulo ajeno a los diez se detecta
  Dado un paquete "inventado" bajo "backend/cimenta/"
  Cuando se ejecuta la comprobación del esqueleto
  Entonces la comprobación termina con código distinto de 0
  Y nombra el paquete que no está en la lista
```

La comprobación del esqueleto es la verificación de `M1`. El diseño decide si es el propio contrato de import-linter o una comprobación aparte, sin mover el criterio.

### CA-3 `[M]` · Cada módulo expone un único punto de entrada de interfaz · M2

```gherkin
Escenario: Un módulo se consulta por su interfaz publicada
  Dado un módulo cualquiera del esqueleto
  Cuando otro módulo permitido por el grafo importa su punto de entrada de interfaz
  Entonces "uv run lint-imports" termina con código 0
  Y la importación no cuenta como violación de frontera

Escenario: Hay un único punto de entrada por módulo
  Dado los diez módulos
  Cuando se busca su punto de entrada de interfaz
  Entonces cada módulo tiene exactamente uno, en la ruta que fija el diseño
```

### CA-4 `[M]` · Rechazo · Un módulo importa el `dominio/` o la `infraestructura/` de otro · M3

```gherkin
Escenario: Importar el dominio de otro módulo rompe el contrato
  Dado un archivo desechable en "cimenta.compras.aplicacion" que importa de "cimenta.presupuesto.dominio"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el contrato roto, el módulo importador "compras" y el destino "presupuesto.dominio"

Escenario: Importar la infraestructura de otro módulo rompe el contrato
  Dado un archivo desechable en "cimenta.almacen.api" que importa de "cimenta.compras.infraestructura"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el contrato roto, el módulo importador "almacen" y el destino "compras.infraestructura"

Escenario: Importar el dominio o la infraestructura del módulo "archivos" rompe el contrato
  Dado un archivo desechable en "cimenta.presupuesto.aplicacion" que importa de "cimenta.archivos.infraestructura"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el destino "archivos.infraestructura"
```

### CA-5 `[M]` · Rechazo · El dominio importa el framework web o el ORM · M4

```gherkin
Escenario: El dominio no importa FastAPI
  Dado un archivo desechable en "cimenta.presupuesto.dominio" que importa "fastapi"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra la capa "dominio" del módulo "presupuesto" y el paquete "fastapi"

Escenario: El dominio no importa SQLAlchemy
  Dado un archivo desechable en "cimenta.compras.dominio" que importa "sqlalchemy"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el paquete "sqlalchemy"

Escenario: El dominio no importa Pydantic
  Dado un archivo desechable en "cimenta.almacen.dominio" que importa "pydantic"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el paquete "pydantic"

Escenario: El dominio puro sí puede importar la biblioteca estándar y su propio módulo
  Dado un archivo en "cimenta.presupuesto.dominio" que importa "decimal" y otro archivo de "cimenta.presupuesto.dominio"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código 0
```

### CA-6 `[M]` · El grafo declarado se cumple y las aristas no declaradas fallan · M5

```gherkin
Escenario: Las aristas del grafo declarado están permitidas
  Dado un archivo desechable por cada arista de la tabla «Grafo declarado»
  Cuando cada uno importa el punto de entrada del módulo destino
  Entonces "uv run lint-imports" termina con código 0 para todos

Escenario: Rechazo — un módulo importa a "analitica"
  Dado un archivo desechable en "cimenta.compras.aplicacion" que importa el punto de entrada de "cimenta.analitica"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el origen "compras" y el destino "analitica"

Escenario: Rechazo — "presupuesto" importa un módulo de negocio
  Dado un archivo desechable en "cimenta.presupuesto.aplicacion" que importa el punto de entrada de "cimenta.compras"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el origen "presupuesto" y el destino "compras"

Escenario: Rechazo — "archivos" importa un módulo de negocio
  Dado un archivo desechable en "cimenta.archivos.aplicacion" que importa el punto de entrada de "cimenta.presupuesto"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el origen "archivos" y el destino "presupuesto"

Escenario: Rechazo — un ciclo entre módulos
  Dado un archivo desechable en "cimenta.compras.aplicacion" que importa el punto de entrada de "cimenta.almacen"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el origen "compras" y el destino "almacen"
```

### CA-7 `[M]` · Rechazo · El contrato no puede pasar en verde por no ver nada · M3, M5

```gherkin
Escenario: Un nombre de módulo mal escrito en el contrato se detecta
  Dado el contrato con un módulo renombrado a "presupesto" en su declaración
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el error indica que el módulo no existe, y no un resultado en verde

Escenario: Un módulo del esqueleto ausente del contrato se detecta
  Dado un módulo del esqueleto que no aparece en ninguna declaración del contrato
  Cuando se ejecuta la comprobación del esqueleto
  Entonces termina con código distinto de 0
  Y nombra el módulo no cubierto
```

### CA-8 `[M]` · La herramienta queda operativa y la documentación al día · M6

```gherkin
Escenario: El comando de fronteras funciona
  Dado una copia limpia del repositorio con el ticket aplicado
  Cuando se ejecuta "uv sync --locked" y después "uv run lint-imports" desde "backend/"
  Entonces ambos terminan con código 0

Escenario: mypy estricto alcanza los dominios reales
  Dado el esqueleto con sus diez "dominio/"
  Cuando se ejecuta "uv run mypy ." desde "backend/"
  Entonces termina con código 0
  Y la salida ya no contiene "unused section"

Escenario: Rechazo — una función sin anotar en un dominio real se rechaza
  Dado un archivo desechable en "cimenta.presupuesto.dominio" con una función sin anotaciones de tipo
  Cuando se ejecuta "uv run mypy ." desde "backend/"
  Entonces termina con código distinto de 0
  Y el error cita la falta de anotación de la función

Escenario: Las marcas de disponibilidad se retiran
  Dado "CLAUDE.md" y "docs/arranque-local.md"
  Cuando se leen las marcas de "uv run lint-imports" y de la regla 2
  Entonces "uv run lint-imports" ya no lleva «desde TKT-002»
  Y la regla 2 conserva «en el pipeline desde TKT-009» y pierde «desde TKT-002»
```

### CA-R1 `[M]` · Regresión · La base de calidad de TKT-001 sigue en verde

```gherkin
Escenario: Ruff y mypy terminan en verde
  Dado el esqueleto aplicado
  Cuando se ejecutan "uv run ruff format --check ." y "uv run ruff check ." desde "backend/"
  Entonces ambos terminan con código 0
```

### CA-R2 `[M]` · Regresión · El archivo de bloqueo sigue reproducible

```gherkin
Escenario: uv sync --locked funciona con el bloqueo nuevo
  Dado "backend/uv.lock" actualizado con import-linter
  Cuando se ejecuta "uv sync --locked" desde "backend/"
  Entonces termina con código 0
  Y la única dependencia nueva respecto a TKT-001, además de sus transitivas, es "import-linter"
```

### CA-R3 `[M]` · Regresión · Las marcas de otros tickets no se tocan

```gherkin
Escenario: pytest y fastapi dev conservan su marca
  Dado "CLAUDE.md"
  Cuando se leen las líneas de "uv run pytest" y "uv run fastapi dev"
  Entonces siguen marcadas «desde TKT-003 o TKT-004» y «desde TKT-005»
  Y ambos comandos siguen sin funcionar, porque pytest y FastAPI no se instalaron
```

### CA-R4 `[M]` · Regresión · La documentación sigue consistente

```gherkin
Escenario: Los verificadores de documentación terminan en verde
  Dado los cambios del ticket aplicados
  Cuando se ejecutan "python tools/verificar_docs.py" y "python tools/extraer_mermaid.py"
  Entonces ambos terminan con código 0
```

### CA-R5 `[M]` · Regresión · La codificación se conserva

```gherkin
Escenario: Los archivos nuevos cumplen la regla de codificación
  Dado los archivos creados o modificados por el ticket
  Cuando se ejecuta "python tools/verificar_docs.py"
  Entonces no aparece ningún problema "Codificación ·"
  Y el hook ".claude/hooks/recordar-caveman.ps1" sigue empezando por EF BB BF
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-001, ya integrado. Bloquea a TKT-003 a TKT-005, TKT-009, TKT-059 y TKT-060 |
| **N** | Describe el qué, no impone el cómo | Sí | Fija las aristas y las prohibiciones, no el formato del contrato ni el nombre del punto de entrada: lo decide el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Pasa con reservas | El valor es para quien desarrolla y para ADR-001; ningún rol del PRD §4 lo usa. Es esperable en una fundación |
| **E** | Estimable sin investigar antes | Pasa con reservas | Talla M. Queda una incertidumbre técnica: si import-linter detecta imports de `fastapi`, `sqlalchemy` y `pydantic` sin que estén instalados. Si falla, es una escalación, no un recálculo |
| **S** | Cabe en una sesión sin romper contexto | Sí | Muchos archivos pero casi todos vacíos; la parte con contenido es el contrato y sus pruebas |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es un comando con código de salida y mensaje observables |

Dos reservas (V y E), ninguna es un fallo. La spec pasa. Si la incertidumbre de `E` se materializa, se reclasifica como Spike antes de diseñar.

## Definition of Done

La del tipo de ticket según [`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo): ticket de fundación sin criterios de negocio, asimilado a *Funcionalidad* para el cierre y a *Documentación* para la revisión humana.

- [ ] Todos los criterios `CA-1` a `CA-8` y `CA-R1` a `CA-R5` verificados, cada uno con su comando y su resultado en `impl.md`
- [ ] La demostración de fallo de cada compuerta (`CA-2`, `CA-4`, `CA-5`, `CA-6`, `CA-7`, `CA-8`) ejecutada y registrada, no solo el camino verde
- [ ] Mutación de cada contrato: quitar o relajar cada regla y confirmar que su demostración deja de fallar
- [ ] Marcas de `CLAUDE.md` y `docs/arranque-local.md` actualizadas en el mismo cambio
- [ ] `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde
- [ ] PR enlazado al ticket, con su origen (`agent` o `agent+human-review`) y revisado por al menos una persona

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | Todo módulo puede importar `identidad`, `auditoria` y `archivos` por su interfaz; `archivos` puede importar `identidad` y `auditoria`; «`presupuesto` no depende de nadie» se lee como «de ningún módulo de negocio» | El grafo de la tabla no coincide con la arquitectura | Resuelto por el usuario, 2026-10-17 |
| PA-T2 | `dominio/` no importa `fastapi`, `sqlalchemy` ni `pydantic`. Dónde viven los tipos compartidos y la excepción de dominio queda para TKT-004 y TKT-005 | Si TKT-004 necesita que `dominio/` importe un paquete compartido, reabre el contrato | Resuelto por el usuario, 2026-10-17 |
| PA-T3 | Se instala solo `import-linter`, sin pytest, FastAPI ni SQLAlchemy; el contrato se demuestra con archivos desechables y el código de salida | Si se necesita pytest, cambia la marca de `uv run pytest` | Resuelto por el usuario, 2026-10-17 |
| PA-T4 | El grafo se declara entero ahora, incluidas `avance → compras` y la prohibición `compras → analitica` | TKT-069 y TKT-060 dicen que ellos añaden esas aristas; sus textos quedan por corregir | Resuelto por el usuario, 2026-10-17. Los textos de TKT-060 y TKT-069 son deuda del ticket (ver `_index.md`) |
| PA-T5 | Los tres módulos transversales los importa todo módulo, incluida `analitica` con `identidad` y `auditoria` `(asumido)` | Un módulo no puede consultar el rol de quien opera | Resuelto en `/sdd-disenar`: se aplica la tabla «Grafo declarado»; la única arista nueva, `identidad` → `auditoria`, la decidió el usuario (D-1). Las aristas de `analitica` hacia `identidad` y `auditoria` siguen `(asumido)` |
| PA-T6 | import-linter detecta imports de paquetes externos que no están instalados `(asumido)` | El contrato de `M4` no puede probarse sin instalar FastAPI, SQLAlchemy y Pydantic | Abierta. **Escala** si es falso: instalar esos paquetes cambia el alcance acordado |
| PA-T7 | El contrato de `import-linter` evalúa imports directos y no cae en falsos positivos por imports indirectos a través de la interfaz publicada `(asumido)` | `compras → presupuesto` fallaría porque `presupuesto` importa su propia `infraestructura` | Abierta. Se resuelve en `/sdd-disenar` con la documentación de la herramienta |
| PA-T8 | El punto de entrada de interfaz de cada módulo es un solo archivo; su nombre y ruta los fija el diseño | Un módulo expone varios y el contrato no puede distinguir interfaz de interior | Abierta. Se resuelve en `/sdd-disenar` |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Los contratos de import-linter evalúan por omisión también los imports **indirectos**: `compras` importa la interfaz de `presupuesto`, y esa interfaz importa la `infraestructura` de `presupuesto`, así que un contrato ingenuo marcaría `compras → presupuesto.infraestructura` y fallaría siempre | Se añadió `CA-3` (la interfaz publicada se puede importar sin violar el contrato) y `PA-T7` para que el diseño elija el tipo de contrato y la opción adecuada. El criterio no impone el cómo |
| 2 | Alta | Un contrato con un nombre mal escrito puede dar verde sin comprobar nada: es el fallo más caro de una verificación de fronteras | `CA-7` exige que el nombre mal escrito falle y que un módulo ausente del contrato se detecte |
| 3 | Alta | `M4` supone que import-linter detecta `fastapi`, `sqlalchemy` y `pydantic` sin que estén instalados. Si la herramienta necesita el paquete en el entorno para verlo, el contrato pasa en verde y el dominio importa el framework sin que nadie lo note | `PA-T6`, abierta y marcada como escalación. El diseño debe demostrarlo con un desechable (`CA-5`) y, si falla, se escala en lugar de instalar los paquetes por su cuenta |
| 4 | Media | El grafo mezcla lo documentado (arquitectura §4) con lo decidido por el usuario (módulos transversales, `archivos → identidad/auditoria`, `analitica → identidad/auditoria`). La arquitectura y el contrato pueden divergir | `S1`: documentar el grafo declarado en la arquitectura. Los textos de TKT-060, TKT-069 y arquitectura §5 y §7.7 quedan como deuda en `_index.md` |
| 5 | Media | «`analitica` solo lee» no se puede verificar con import-linter: un contrato que lo declara da una falsa sensación de seguridad | Está en los non-goals, con su dueño (TKT-003) y `RNF-09`. El contrato solo prohíbe que alguien importe `analitica` y limita sus importaciones a los permitidos |
| 6 | Media | `CA-2` pide una «comprobación del esqueleto» sin decir qué es: ¿otro script, una prueba, el propio contrato? | Se declara que el diseño lo decide sin mover el criterio. Si requiere código propio nuevo, el diseño lo justifica en su escalera de decisión |
| 7 | Baja | `INVEST·V` pasa con reservas | Es la naturaleza de una fundación y no se fuerza una historia |

Veredicto: 3 objeciones altas, todas absorbidas como criterios o como supuestos con dueño. Ninguna revela una regla de negocio que el PRD no tenga, así que no hay escalación de entrada. `PA-T6` se escala si resulta falsa.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

- Ticket: [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md), TKT-002. Épica 0, talla M. Depende de TKT-001 (integrado en `Produccion`).
- Arquitectura: [`docs/02-arquitectura.md`](../../../docs/02-arquitectura.md) §4 (grafo de componentes), §5 (tabla de dependencias), §6 (capas), §7.6 (identidad y «`analitica` solo lee»), §7.7 (`archivos`).
- Decisiones: [ADR-001](../../../docs/adr/20260918-monolito-modular.md), [ADR-003](../../../docs/adr/20260918-dominio-puro.md) y [ADR-006](../../../docs/adr/) sobre el paso de modelos del ORM dentro de la capa de aplicación.
- Stack: [`docs/06-stack-tecnologico.md`](../../../docs/06-stack-tecnologico.md) §8, con el ejemplo de contrato de import-linter. Ese ejemplo omite `infraestructura` y su formato es `.ini`; el diseño decide dónde vive la configuración.
- Estado del backend: `backend/pyproject.toml` (sin `[build-system]`, con `[tool.mypy.overrides]` para `cimenta.*.dominio.*`), `backend/uv.lock` y `backend/cimenta/__init__.py`. Los directorios de `dominio/` necesitan `__init__.py` para que el patrón de mypy los alcance.
- Archivos que se modifican: `backend/pyproject.toml`, `backend/uv.lock`, `CLAUDE.md` (marcas de `uv run lint-imports` y de la regla 2), `docs/arranque-local.md` (tabla «Lo que todavía no arranca») y, por `S1`, `docs/02-arquitectura.md`.
- Deuda heredada de TKT-001 que este ticket cierra: regresión del patrón de mypy y nota `unused section`.
- Módulos y tablas en alcance: los diez módulos como paquetes vacíos. Ninguna tabla.
- Endpoints: ninguno. El borrador OpenAPI no tiene operaciones con este ticket en `x-tickets`.
