# Spec · TKT-001 · Estructura del repositorio y herramientas base

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

CIMENTA tiene hoy una especificación completa y ningún código. El repositorio contiene `docs/`, `sdd/`, `.claude/`, `tools/`, `CLAUDE.md`, `llms.txt`, `README.md`, `LICENSE` y un `.gitignore` parcial. No existe `backend/`, `frontend/`, ningún archivo de dependencias, ninguna configuración de formateador o linter, `.editorconfig`, `.gitattributes` ni `.env.example`.

Sin esa base, el resto de la Épica 0 no tiene dónde apoyarse: TKT-002 necesita un proyecto Python en el que instalar FastAPI y `import-linter`; TKT-008 necesita un proyecto Node en el que instalar React y Vite; TKT-009 necesita comandos de calidad que el pipeline pueda invocar. Además, el aprendizaje registrado en [`sdd/_evolucion.md`](../../_evolucion.md) (2026-10-01) exige que el `.editorconfig` fije `charset = utf-8` sin BOM para los `.md`, porque un BOM rompió el análisis del `---` inicial de seis agentes.

Este ticket es de fundación: no entrega valor al cliente y no contiene lógica de negocio. Entrega la capacidad de que el equipo, humano o agente, instale dependencias, formatee, lintee y tipe el código con comandos reproducibles desde una copia limpia del repositorio.

El estado de partida, criterio por criterio, es:

| Criterio del ticket | Estado de partida |
|---|---|
| `backend/` y `frontend/` con su gestor de dependencias | Falta todo |
| Formateador y linter con versiones fijadas | Falta todo |
| `.gitignore`, `.editorconfig`, archivo de entorno de ejemplo | `.gitignore` existe e incompleto; los otros dos no existen |
| `CLAUDE.md` con convenciones, comandos y reglas | Ya existe y es un superconjunto de `llms.txt`; hay que revisarlo, no crearlo |
| `README.md` con arranque local verificado | Existe como ficha de la Entrega 1, sin instrucciones de arranque |

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario asociada. El rol que lo usa es quien desarrolla el proyecto, sea persona o agente.

**Como** persona o agente que desarrolla CIMENTA
**quiero** clonar el repositorio y obtener, con comandos documentados, un backend y un frontend con sus dependencias, formateador, linter y verificación de tipos en verde
**para** que los tickets siguientes añadan código sobre una base reproducible, con las mismas reglas de calidad para todos.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** `backend/` con proyecto `uv` (`pyproject.toml` y `uv.lock`), Ruff como formateador y linter, y mypy con modo estricto limitado a `dominio/` |
| | **M2.** `frontend/` con `npm` (`package.json` y `package-lock.json`), TypeScript en modo `strict`, ESLint, y la versión de Node fijada |
| | **M3.** `.gitignore` completado, `.editorconfig` (UTF-8 sin BOM, finales de línea LF, excepción con BOM para `*.ps1`), `.gitattributes` y `.env.example` sin valores |
| | **M4.** `CLAUDE.md` revisado contra `llms.txt` y contra el estado real del repositorio, con los comandos que aún no funcionan marcados «desde TKT-00x» |
| | **M5.** Arranque local documentado y verificado en una copia limpia: `uv sync`, `npm ci`, y los comandos de formato, lint y tipos terminan en verde |
| | **M6.** `README.md` y [convenciones §3](../../../docs/convenciones.md) actualizados con la estructura real, en el mismo cambio |
| **Should** | **S1.** El conjunto de reglas de Ruff queda declarado explícitamente en `pyproject.toml`, no heredado de los valores por omisión |
| **Could** | — |
| **Won't** | CI (TKT-009) · framework web y ORM (TKT-002) · `import-linter` y paquetes de módulos (TKT-002) · Docker Compose con PostgreSQL (TKT-003) y MinIO (TKT-059) · regla de Ruff contra `float` (TKT-004) · React, Vite y cliente de API (TKT-008) · `pydantic-settings` y guarda de arranque (TKT-057) · Dockerfile (TKT-058) · `pip-audit`, `npm audit`, Dependabot, markdownlint, Vale, lychee (TKT-009) |

## Non-goals

- No configura CI ni ningún workflow de GitHub Actions: es TKT-009.
- No instala FastAPI, SQLAlchemy, Pydantic, Alembic ni `import-linter`: es TKT-002. Por eso `uv run fastapi dev` y `uv run lint-imports` no funcionan al cerrar este ticket.
- No crea las carpetas de módulos ni las de capas (`api/`, `aplicacion/`, `dominio/`, `infraestructura/`): es TKT-002. La configuración de mypy estricto se declara sobre el patrón `cimenta/*/dominio/` y se verifica con un archivo de prueba desechable, no con módulos reales.
- No instala React, Vite, TanStack, Tailwind ni shadcn/ui: es TKT-008. ESLint y `tsc` se verifican con un archivo TypeScript mínimo que no forma parte de ninguna aplicación.
- No define reglas de negocio ni toca la base de datos.
- No añade la regla que prohíbe `float` en firmas de dominio, aunque `CLAUDE.md` diga que «el linter lo bloquea»: la regla pertenece al criterio de TKT-004.
- No incluye claves reales en `.env.example`: las claves llegan con TKT-003, TKT-057 y TKT-059.

## Reglas de negocio implicadas

Ninguna regla `RN-xx`: el ticket no tiene lógica de negocio. Lo que sí implica son dos requisitos no funcionales.

| Requisito | Qué exige | Dónde está |
|---|---|---|
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen. De ahí el `.env.example` sin valores y el `.env` ignorado | PRD §9 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RNF-08` | Solo de forma indirecta: las versiones fijadas en los archivos de bloqueo son el insumo de la auditoría de dependencias que construye TKT-009 | PRD §9 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |

## Invariantes que deben sobrevivir al cambio

El ticket no crea tablas ni toca la base de datos, así que no pone en riesgo ninguno de los 38 invariantes del modelo de datos. Sí modifica archivos que ya funcionan —`.gitignore`, `README.md`, `CLAUDE.md`, `convenciones.md`— y un hook que depende de la codificación de un archivo. Estas son las garantías que deben sobrevivir:

| Garantía existente | Qué protege | Criterio de regresión |
|---|---|---|
| El hook `.claude/hooks/recordar-caveman.ps1` conserva su BOM | Windows PowerShell 5.1 lee como ANSI un script sin BOM y corrompe los acentos | `CA-R1` |
| Los archivos `.md` y los agentes de `.claude/` no ganan BOM | Un BOM rompe el análisis del `---` inicial del frontmatter ([`sdd/_evolucion.md`](../../_evolucion.md), 2026-10-01) | `CA-R2` |
| Los verificadores de `tools/` siguen pasando | La documentación existente no se rompe por actualizar README, `CLAUDE.md` y convenciones | `CA-R3` |
| `.gitignore` sigue ignorando lo que ignoraba | `Doc de contexto/`, `.env`, `.env.local` y los artefactos de Python y Node no llegan al repositorio | `CA-R4` |

## Criterios de aceptación

Gherkin, en español. Como el ticket no tiene reglas de negocio, el «rechazo» de cada criterio es la demostración de que la herramienta falla ante su violación: una compuerta que nunca se ha visto fallar no está verificada.

### CA-1 `[M]` · El backend instala y sus herramientas pasan en una copia limpia · M1, M5

```gherkin
Escenario: El backend arranca desde una copia limpia
  Dado una copia limpia del repositorio sin directorio de entorno virtual
  Cuando se ejecuta "uv sync" dentro de backend/
  Entonces la instalación termina sin errores usando las versiones de uv.lock
  Y "uv run ruff format --check ." termina con código 0
  Y "uv run ruff check ." termina con código 0
  Y "uv run mypy ." termina con código 0
```

### CA-2 `[M]` · Rechazo · Ruff y mypy fallan ante su violación · M1

```gherkin
Escenario: Ruff rechaza un archivo mal formateado
  Dado un archivo Python con una línea sin formatear
  Cuando se ejecuta "uv run ruff format --check ."
  Entonces el comando termina con código distinto de 0
  Y la salida nombra el archivo infractor

Escenario: mypy estricto rechaza una función sin anotar bajo dominio
  Dado un archivo desechable en una ruta que coincide con "cimenta/*/dominio/" con una función sin anotaciones de tipo
  Cuando se ejecuta "uv run mypy ."
  Entonces el comando termina con código distinto de 0
  Y el error cita la falta de anotación de la función

Escenario: mypy no aplica el modo estricto fuera de dominio
  Dado el mismo archivo desechable en una ruta que no coincide con "dominio/"
  Cuando se ejecuta "uv run mypy ."
  Entonces el comando no emite el error de anotación obligatoria
```

### CA-3 `[M]` · El frontend instala y sus herramientas pasan en una copia limpia · M2, M5

```gherkin
Escenario: El frontend arranca desde una copia limpia
  Dado una copia limpia del repositorio sin node_modules
  Cuando se ejecuta "npm ci" dentro de frontend/
  Entonces la instalación termina sin errores usando package-lock.json
  Y "npm run lint" termina con código 0
  Y "npm run typecheck" termina con código 0
```

### CA-4 `[M]` · Rechazo · ESLint y TypeScript fallan ante su violación · M2

```gherkin
Escenario: TypeScript strict rechaza un tipo implícito
  Dado un archivo TypeScript desechable con un parámetro sin tipo
  Cuando se ejecuta "npm run typecheck"
  Entonces el comando termina con código distinto de 0
  Y el error cita el parámetro con tipo "any" implícito

Escenario: ESLint rechaza una infracción de sus reglas
  Dado un archivo TypeScript desechable con una variable declarada y nunca usada
  Cuando se ejecuta "npm run lint"
  Entonces el comando termina con código distinto de 0
  Y la salida nombra la regla infringida

Escenario: Una versión de Node distinta a la fijada se advierte
  Dado una versión de Node fuera del rango declarado en "engines"
  Cuando se ejecuta "npm ci" con el modo estricto de engines activado
  Entonces la instalación falla y nombra la versión requerida
```

### CA-5 `[M]` · Las versiones quedan fijadas en los archivos de bloqueo · M1, M2 · `RNF-08`

```gherkin
Escenario: Cada herramienta tiene una versión exacta y reproducible
  Dado "backend/uv.lock" y "frontend/package-lock.json" versionados
  Cuando se instalan las dependencias en dos copias limpias distintas
  Entonces ambas obtienen exactamente las mismas versiones de Ruff, mypy, TypeScript y ESLint
  Y las versiones elegidas son la última estable de cada herramienta en la fecha del ticket
  Y ninguna dependencia se declara con la etiqueta "latest" ni sin límite inferior
```

### CA-6 `[M]` · El `.editorconfig` fija la codificación y las excepciones · M3

```gherkin
Escenario: Los archivos de texto se guardan en UTF-8 sin BOM con LF
  Dado el archivo ".editorconfig" en la raíz con "root = true"
  Cuando se consulta la configuración efectiva de un archivo "*.md", un "*.py" y un "*.ts"
  Entonces cada uno resuelve "charset = utf-8", "end_of_line = lf" e "insert_final_newline = true"

Escenario: Los scripts de PowerShell conservan su BOM
  Dado el archivo ".editorconfig"
  Cuando se consulta la configuración efectiva de "recordar-caveman.ps1"
  Entonces resuelve "charset = utf-8-bom"
```

### CA-7 `[M]` · Rechazo · Un archivo con la codificación incorrecta se detecta · M3

```gherkin
Escenario: Un Markdown con BOM se detecta
  Dado un archivo ".md" que empieza con los bytes EF BB BF
  Cuando se ejecuta la verificación de codificación del repositorio
  Entonces la verificación termina con código distinto de 0
  Y nombra el archivo con BOM

Escenario: Un script de PowerShell sin BOM se detecta
  Dado un archivo ".ps1" que no empieza con los bytes EF BB BF
  Cuando se ejecuta la verificación de codificación del repositorio
  Entonces la verificación termina con código distinto de 0
  Y nombra el archivo sin BOM
```

### CA-8 `[M]` · Los secretos no entran al repositorio · M3 · `RNF-07`

```gherkin
Escenario: .env.example documenta las claves sin valores
  Dado el archivo ".env.example" en la raíz
  Cuando se lee su contenido
  Entonces no contiene ningún valor asignado a ninguna clave
  Y su cabecera explica que las claves se añaden con cada ticket que las introduce

Escenario: Rechazo — un .env real no se puede versionar por descuido
  Dado un archivo ".env" con un valor cualquiera en la raíz
  Cuando se ejecuta "git add ." y después "git status --porcelain"
  Entonces ".env" no aparece como archivo preparado
  Y ".env.example" sí aparece como versionado
```

### CA-9 `[M]` · `CLAUDE.md` coincide con el repositorio real · M4

```gherkin
Escenario: Cada comando de CLAUDE.md está disponible o declara desde cuándo lo estará
  Dado la sección "Comandos" de CLAUDE.md
  Cuando se revisa cada comando contra el estado del repositorio al cerrar el ticket
  Entonces cada comando que funciona es exactamente el que se ejecuta, con el directorio correcto
  Y cada comando que aún no funciona lleva la marca «desde TKT-00x» con el ticket que lo habilita
  Y las 17 reglas y el contenido de "llms.txt" no se contradicen

Escenario: Rechazo — un comando documentado que no existe se detecta
  Dado un comando listado en CLAUDE.md sin marca de disponibilidad
  Cuando se ejecuta en la copia limpia
  Entonces falla, y la revisión del ticket registra la discrepancia como hallazgo
```

### CA-10 `[M]` · README y convenciones reflejan la estructura real · M6

```gherkin
Escenario: La documentación describe el repositorio que existe
  Dado el repositorio al cerrar el ticket
  Cuando se lee "README.md" y "docs/convenciones.md" §3
  Entonces ambos listan "backend/", "frontend/", "tools/", "sdd/" y ".claude/"
  Y el README enlaza al documento de arranque local en lugar de contenerlo
  Y ya no dicen «sin código todavía»

Escenario: Rechazo — la documentación no se rompe al cambiar
  Dado los cambios del ticket aplicados
  Cuando se ejecuta "python tools/verificar_docs.py"
  Entonces termina con código 0, sin enlaces, anclas ni identificadores rotos
```

### CA-R1 `[M]` · Regresión · El hook conserva su BOM

```gherkin
Escenario: recordar-caveman.ps1 sigue empezando por EF BB BF
  Dado el estado del repositorio tras aplicar el ticket
  Cuando se leen los tres primeros bytes de ".claude/hooks/recordar-caveman.ps1"
  Entonces son EF BB BF
```

### CA-R2 `[M]` · Regresión · Ningún `.md` ni agente gana BOM

```gherkin
Escenario: Los archivos de .claude/agents y .claude/skills siguen sin BOM
  Dado el estado del repositorio tras aplicar el ticket
  Cuando se leen los tres primeros bytes de cada ".md" bajo ".claude/", "docs/" y "sdd/"
  Entonces ninguno es EF BB BF
```

### CA-R3 `[M]` · Regresión · Los verificadores existentes pasan

```gherkin
Escenario: Los verificadores de tools/ terminan en verde
  Dado los cambios del ticket aplicados
  Cuando se ejecutan "python tools/verificar_docs.py" y "python tools/extraer_mermaid.py"
  Entonces ambos terminan con código 0
```

### CA-R4 `[M]` · Regresión · `.gitignore` conserva lo que ignoraba

```gherkin
Escenario: Lo ignorado antes sigue ignorado
  Dado el ".gitignore" actualizado
  Cuando se ejecuta "git check-ignore" sobre "Doc de contexto/x", ".env", ".env.local", "__pycache__/x.pyc" y "node_modules/x"
  Entonces todos son ignorados
  Y ".env.example" no es ignorado
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | No depende de ningún ticket. Bloquea a TKT-002 y a los siguientes, pero no al revés |
| **N** | Describe el qué, no impone el cómo | Sí | Fija herramientas porque el stack ya las decidió; no fija reglas internas ni estructura de archivos de configuración |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Pasa con reservas | El valor es para quien desarrolla, no para un rol del PRD §4. Es esperado en un ticket de fundación y está declarado como tal |
| **E** | Estimable sin investigar antes | Sí | Talla S. Las preguntas abiertas están resueltas salvo `PA-T1` y `PA-T2`, que no cambian la estimación |
| **S** | Cabe en una sesión sin romper contexto | Sí | Seis ítems Must, todos de configuración |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es un comando con código de salida observable |

Un fallo, con reservas (V). La spec pasa.

## Definition of Done

La del tipo de ticket según [`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo). Un ticket de fundación sin criterios de negocio se asimila a *Documentación* para la revisión humana y a *Funcionalidad* para el resto, según la tabla de tipos de [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md).

- [ ] Todos los criterios `CA-1` a `CA-10` y `CA-R1` a `CA-R4` verificados, cada uno con su comando y su resultado en `impl.md`
- [ ] La demostración de fallo de cada compuerta (`CA-2`, `CA-4`, `CA-7`) ejecutada y registrada, no solo el camino verde
- [ ] `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde
- [ ] Arranque verificado por una segunda persona o por una copia limpia independiente, con constancia en `impl.md`
- [ ] PR enlazado al ticket, con su origen (`agent` o `agent+human-review`) y revisado por al menos una persona

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | El proyecto `uv` vive en `backend/`, no en la raíz. Los comandos de `CLAUDE.md` se corrigen a ejecutarse desde `backend/` | Los comandos documentados no corren | Resuelto por el usuario, 2026-10-17 |
| PA-T2 | En `frontend/` solo hay `package.json`, TypeScript strict y ESLint, sin Vite ni React | Si se adelanta el andamiaje, el ticket crece y pisa a TKT-008 | Resuelto por el usuario, 2026-10-17 |
| PA-T3 | «Arranque verificado en máquina limpia» significa `uv sync`, `npm ci` y los comandos de calidad en verde sobre una copia limpia | Una verificación más pesada (contenedor) infla la talla S | Resuelto por el usuario, 2026-10-17 |
| PA-T4 | UTF-8 sin BOM, LF, y excepción `utf-8-bom` solo para `*.ps1`, con `.gitattributes` | El hook de PowerShell se corrompe o los diffs se ensucian con finales de línea | Resuelto por el usuario, 2026-10-17 |
| PA-T5 | `.env.example` lleva solo cabecera y ninguna clave `(asumido)` | Si debe traer claves, hay que saber cuáles antes de que existan TKT-003 y TKT-057 | Abierta. Se escala si el diseño necesita claves |
| PA-T6 | Las versiones exactas se eligen en el diseño o la ejecución, tomando la última estable de la fecha. El stack §3.1 menciona Python 3.14 en el entorno y `requires-python >=3.13` `(asumido)` | El `requires-python` queda más estricto o más laxo de lo deseado | Abierta. Se resuelve en `/sdd-disenar` |
| PA-T7 | Node se fija con `engines` en `package.json` y un archivo `.nvmrc` `(asumido)`; el gestor es `npm` por lo que dice `CLAUDE.md` | Otro gestor cambia los comandos de instalación | Abierta. Se resuelve en `/sdd-disenar` |
| PA-T8 | La verificación de codificación de CA-7 se hace con un script pequeño en `tools/` y no con una dependencia nueva `(asumido)` | Si debe vivir en CI, TKT-009 la adopta | Abierta. Se resuelve en `/sdd-disenar` |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-7` exige una «verificación de codificación» que ningún criterio del ticket original pide ni que ninguna herramienta existente hace. Sin ella, el `.editorconfig` solo es una sugerencia al editor y el BOM puede volver | Se mantiene en el Must, porque `sdd/_evolucion.md` documenta el daño real. Se acota a un script mínimo en `tools/` (`PA-T8`). La integración en CI queda para TKT-009 |
| 2 | Alta | Probar que mypy estricto «solo aplica a `dominio/`» con un archivo desechable no prueba nada sobre los módulos reales de TKT-002: los patrones de `pyproject.toml` pueden no coincidir con la ruta final | `CA-2` verifica ambos lados (estricto dentro, laxo fuera). TKT-002 hereda un criterio de regresión: al crear los `dominio/` reales, el patrón debe seguir aplicando. Se anota en «Tickets futuros sugeridos» |
| 3 | Media | `CA-5` pide «la última estable» sin fecha. Dos ejecuciones en días distintos darían versiones distintas, y el ticket se volvería irrepetible | Se redactó con «en la fecha del ticket» y el archivo de bloqueo como evidencia. La fecha exacta queda en `impl.md` |
| 4 | Media | `CA-9` revisa `CLAUDE.md` contra «el estado real», pero `CLAUDE.md` es lo que lee el agente: una marca «desde TKT-00x» mal puesta lo lleva a ejecutar comandos que fallan | El criterio de rechazo exige ejecutar cada comando en la copia limpia. El diseño debe decidir el formato exacto de la marca |
| 5 | Baja | `INVEST·V` pasa con reservas porque ningún rol del PRD §4 usa el ticket | Se declara en la historia. Es la naturaleza de un ticket de fundación y no se fuerza una historia artificial |

Veredicto: 2 objeciones altas, ambas absorbidas en la spec. Ninguna revela una regla que el PRD no tenga, así que no hay escalación.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

- Ticket: [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md), TKT-001. Sprint 0, Épica 0, talla S, sin dependencias. Lo necesitan TKT-002 y TKT-062.
- Herramientas y su porqué: [`docs/06-stack-tecnologico.md`](../../../docs/06-stack-tecnologico.md) §2 y §8. El stack fija las herramientas; este ticket elige las versiones.
- Estructura del repositorio: [`docs/convenciones.md`](../../../docs/convenciones.md) §3, que hoy no lista `backend/`, `frontend/`, `tools/`, `sdd/` ni `.claude/`.
- Convención de documentación y del README como índice: [`.claude/skills/conv-documentacion/SKILL.md`](../../../.claude/skills/conv-documentacion/SKILL.md).
- Aprendizaje del BOM: [`sdd/_evolucion.md`](../../_evolucion.md), entrada del 2026-10-01. El hook [`.claude/hooks/recordar-caveman.ps1`](../../../.claude/hooks/recordar-caveman.ps1) exige BOM.
- Archivos que existen y se modifican: `.gitignore`, `README.md`, `CLAUDE.md`, `llms.txt`, `docs/convenciones.md`.
- Archivos que se crean: `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, configuración de ESLint, `.editorconfig`, `.gitattributes`, `.env.example`, `.nvmrc` `(asumido)`, un script de verificación de codificación en `tools/` `(asumido)` y el documento de arranque local.
- Módulos y tablas en alcance: ninguno. El ticket no toca `backend/cimenta/` ni la base de datos.
- Endpoints: ninguno. El borrador OpenAPI no tiene operaciones con este ticket en `x-tickets`.
