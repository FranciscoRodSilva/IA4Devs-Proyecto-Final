# Propuesta · Toolkit SDD de CIMENTA

> **Qué es este documento.** El diseño del sistema de trabajo con agentes para CIMENTA: la decisión sobre OpenSpec, las convenciones de código investigadas por lenguaje, el catálogo de agentes especializados y el orquestador que los despacha.
>
> **Estado:** propuesta. Nada de esto está construido todavía. Se construye cuando se apruebe.
>
> **Fuentes consultadas:** `C:\GitHub\SDD-Nice` (toolkit de Nice, solo lectura), documentación oficial de Claude Code (subagentes y skills), OpenSpec, y búsqueda de convenciones por stack. Referencias al final.

---

## 1 · La decisión: toolkit propio, no OpenSpec

**Recomendación: construir `cimenta-sdd` propio, nativo de Claude Code. No instalar OpenSpec.**

Tres razones, en orden de peso:

**1. OpenSpec crearía una segunda fuente de verdad.** OpenSpec instala `openspec/specs/` como «el estado actual del sistema» y `openspec/changes/` como propuestas de cambio. CIMENTA ya tiene esa capa, y está validada en CI: el PRD con `RN-01`…`RN-25`, las historias con escenarios Gherkin numerados, los tickets `TKT-001`…`TKT-058`, 26 invariantes de datos, 16 ADRs, y `tools/verificar_docs.py` comprobando que ningún identificador citado sea inexistente. Montar `openspec/` encima significa mantener dos catálogos de reglas que se desincronizan en el tercer ticket. El problema que OpenSpec resuelve —*que haya spec antes que código*— aquí ya está resuelto.

**2. OpenSpec no orquesta agentes.** Es deliberadamente agnóstico: soporta más de 30 herramientas, lo que lo obliga al mínimo común denominador —comandos slash que escriben Markdown—. No tiene agentes especializados, ni ciclo auditor→corrector→reauditoría, ni veredictos bloqueantes, ni routing por stack. El requisito central de este encargo es exactamente eso: un orquestador que despliegue agentes especializados y decida si el trabajo va en lote o de uno en uno. Eso no se le puede pedir a OpenSpec; habría que construirlo igual, encima.

**3. Lo que sí vale de OpenSpec se puede tomar sin la dependencia.** Su mejor idea es el **delta spec**: no reescribir la especificación completa en cada cambio, sino declarar qué se añade, qué se modifica y qué se elimina respecto del comportamiento actual. Esa idea entra en nuestra plantilla `delta.md` —que SDD-Nice ya tiene— sin instalar Node ni un directorio paralelo.

### Comparativa

| | OpenSpec | SDD-Nice (referencia) | `cimenta-sdd` (propuesto) |
|---|---|---|---|
| Fuente de verdad de la spec | `openspec/specs/` propio | `specs/<dominio>.md` por dominio | `docs/` existente — **no se duplica** |
| Agentes especializados | No | 23, para T-SQL / C# / Flutter | ~20, para Python / Postgres / React |
| Ciclo auditoría → corrección | No | Sí, máx. 3 ciclos | Sí, máx. 3 ciclos |
| Orquestador con modos | No | Comandos que invocan agentes | Orquestador con 3 modos de ejecución |
| Integración con Claude Code | Slash commands genéricos | Pensado para Cursor; Claude solo planifica | Nativo: subagentes, skills, hooks |
| Conoce las reglas de CIMENTA | No | No | Sí — son su razón de existir |

### Lo que se toma de SDD-Nice y lo que no

**Se toma** —es su mejor material, probado en un equipo real—:

- El pipeline de cinco fases con **gate humano entre cada una**, y los dos comandos de soporte.
- La **máquina de estados** con dueño explícito por transición (`SPEC PENDIENTE` → `LISTO PARA EJECUTAR` → `EN REVISIÓN` → `LISTO PARA PR` → `ARCHIVADO`, más `REQUIERE CAMBIOS`, `REQUIERE DECISIÓN`, `RIESGOSO`).
- Los **veredictos de auditor** (`APROBADO` / `REQUIERE CAMBIOS` / `RIESGOSO·BLOQUEAR`) y el agente `corrector-revision` que cierra el ciclo.
- Las **stop conditions por comando**: condiciones explícitas que detienen el flujo en vez de dejarlo degradar.
- La **escalera de decisión** anti-sobreingeniería: YAGNI → nativo de la plataforma → reuso → cambio mínimo → objeto nuevo. Con una precedencia que encaja exacto con este proyecto: *el cambio mínimo nunca autoriza tocar un invariante registrado*.
- El **registro de evolución** (`_evolucion.md`) y el agente `meta-sdd` que detecta patrones repetidos ≥3 y propone mejoras al propio toolkit.
- La skill **abogado del diablo**: pasada adversarial sobre spec y design antes de aprobarlos.
- El principio de **agencia real**: en un artefacto, ningún objeto inanimado «hace» algo. No «el sistema valida el presupuesto», sino «`evaluar_disponibilidad` devuelve `BLOQUEADA`».

**No se toma** —copiarlo sería cargo cult—:

| Elemento de Nice | Por qué no aplica aquí |
|---|---|
| `git-api` + `git-frontend` + `git-mobile` | Nice tiene cuatro repos. CIMENTA es **un monorepo**. Un solo agente de entrega. |
| Agentes de T-SQL, C#, Flutter, ASP.NET MVC | Otro stack por completo. |
| Stored procedures con lógica de negocio | **Prohibido aquí**: las reglas viven en `dominio/`, puro, sin ORM. Un SP con reglas rompe el ADR del dominio puro. |
| `sdd.config.yaml` con targets e instancias | Resuelve multi-repo y multi-DB. CIMENTA es single-tenant, un repo, una base. Sobra la indirección. |
| Separación «Claude planifica / Cursor implementa» | Aquí Claude Code hace ambos lados. La separación se mantiene como **roles de agente**, no como herramientas distintas. |
| `.cursor/rules/*.mdc` | Claude Code no los lee. El equivalente nativo son skills precargadas por agente y hooks. |

---

## 2 · Las primitivas de Claude Code y sus límites

Antes del diseño, los hechos técnicos que lo condicionan. Verificados contra la documentación oficial, no asumidos.

| Primitiva | Dónde vive | Para qué la usamos |
|---|---|---|
| **Subagente** | `.claude/agents/<nombre>.md` | Cada agente especializado. Frontmatter: `tools`, `disallowedTools`, `model`, `effort`, `skills`, `memory`, `permissionMode`, `maxTurns`. |
| **Skill / comando slash** | `.claude/skills/<nombre>/SKILL.md` | Los comandos del pipeline y los paquetes de convenciones. Frontmatter: `description`, `argument-hint`, `arguments`, `allowed-tools`, `disable-model-invocation`, `context: fork`. |
| **Hook** | `.claude/settings.json` | Guardrails que **bloquean** en vez de advertir: `PreToolUse` sobre `Write`/`Edit`, `UserPromptSubmit` para activar una skill en cada turno. |
| **`skills:` en un agente** | frontmatter del agente | Precarga las convenciones del stack en el contexto del agente, sin que tenga que descubrirlas. Es el mecanismo documentado para esto. |
| **`tools: Agent(a, b)`** | frontmatter del agente | Restringe qué subagentes puede desplegar un coordinador. |

### Tres límites que cambian el diseño

**1. Un subagente no puede preguntarle al usuario.** `AskUserQuestion` se elimina siempre del conjunto de herramientas de un subagente. Consecuencia directa: **el orquestador tiene que ser el hilo principal**, no un subagente. Un «agente orquestador» que detecte una ambigüedad no podría escalarla; solo podría devolver texto y esperar que alguien lo lea. Por eso el orquestador de CIMENTA son los comandos del pipeline ejecutándose en la sesión principal, y `/escalar` es el único que puede abrir la pregunta.

**2. Los subagentes no hablan entre sí.** Reportan al hilo principal y punto. El ciclo auditor → corrector → reauditoría no es una conversación entre agentes: es el orquestador recibiendo un veredicto, despachando al corrector con los hallazgos, y volviendo a despachar al auditor.

**3. El paralelismo rinde entre 3 y 5 agentes.** Más allá, el coste de coordinación se come la ganancia. Esto decide dónde paralelizamos: **auditorías sí** (son de solo lectura, independientes entre sí, y son tres o cuatro), **implementación no** (toca los mismos archivos).

---

## 3 · El pipeline

Cinco comandos de pipeline y dos de soporte, como se pidió. Cada uno con su gate: el estado no avanza solo.

```
                 ┌──── /escalar ────┐   (desde cualquier fase)
                 │                  ▼
/definir  →  /diseñar  →  /ejecutar  →  /revisar  →  /completar
   │            │             │            │             │
 spec.md     design.md     impl.md     impl.md+       delta.md
                                      veredictos      + PR

/avance  ─── lee el estado de todo, no lo modifica ───
```

### Los cinco del pipeline

| Comando | Cuándo | Qué hace | Por qué existe | Produce |
|---|---|---|---|---|
| `/sdd-definir TKT-xxx` | Al tomar un ticket | Lee el ticket, la historia y las reglas implicadas. Escribe la spec: user story, alcance MoSCoW, criterios de aceptación Gherkin con **su escenario de rechazo**, invariantes en riesgo, non-goals. Pasada adversarial obligatoria. | Sin spec, cada quien interpreta el requerimiento distinto | `_index.md`, `spec.md` |
| `/sdd-disenar TKT-xxx` | Tras aprobar la spec | Plan técnico: qué capa toca, qué archivos, en qué orden, cómo se verifica cada paso. Corre la escalera de decisión por objeto. Pasada adversarial obligatoria. | Fuerza pensar antes de codear; evita retrabajo | `design.md` |
| `/sdd-ejecutar TKT-xxx` | Tras aprobar el design | Despacha a los desarrolladores y testers que el design exija. Los tests nacen con el código. Cierra con auditorías. | Los tests nacen con el código; después nadie los escribe | `impl.md` |
| `/sdd-revisar TKT-xxx` | Tras la implementación | Verifica criterio por criterio, corre la suite, despacha los auditores, ejecuta el ciclo de corrección. | Nadie aprueba su propio código | `impl.md` + veredictos |
| `/sdd-completar TKT-xxx` | Tras revisión aprobada | Genera el delta (añadido / modificado / eliminado), archiva aprendizajes, actualiza la documentación afectada, prepara el PR. | Sin cierre formal, el conocimiento del ticket desaparece | `delta.md`, PR |

### Los dos de soporte

| Comando | Cuándo | Qué hace | Por qué existe |
|---|---|---|---|
| `/sdd-avance [TKT-xxx]` | En cualquier momento | Reporte de progreso: qué artefactos existen, qué estado tiene cada ticket vivo, qué falta, qué está bloqueado. No modifica nada. | Visibilidad sin leer todos los artefactos |
| `/sdd-escalar TKT-xxx` | Alcance creció, invariante estorba, riesgo nuevo | Pausa el ticket, cambia a `REQUIERE DECISIÓN`, formula la pregunta concreta con sus opciones y espera. | El desarrollador no decide lo que no le corresponde |

**Disparadores obligatorios de `/escalar`** —se escala, no se asume—: el alcance crece más de 30 % respecto al design · un invariante registrado estorba al cambio pedido · la escalera de decisión obliga a crear un objeto nuevo no previsto · tres ciclos de corrección sin cerrar hallazgos · cualquier auditor devuelve `RIESGOSO` · aparece una regla de negocio que el PRD no tiene.

Ese último es la traducción directa de la regla del proyecto: **no inventes reglas de negocio**.

### Estados

| Estado | Sale hacia | Quién lo mueve |
|---|---|---|
| `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` |
| `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | **el usuario**, explícitamente |
| `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` |
| `EN REVISIÓN` | `LISTO PARA PR` · `REQUIERE CAMBIOS` · `REQUIERE DECISIÓN` · `RIESGOSO` | auditores |
| `REQUIERE CAMBIOS` | `EN REVISIÓN` | `corrector-revision`, máx. 3 ciclos |
| `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` |
| `REQUIERE DECISIÓN` · `RIESGOSO` | estado previo | **el usuario** |

Dos transiciones tienen dueño humano a propósito. Un pipeline donde el agente aprueba su propio diseño no es un pipeline, es un monólogo.

---

## 4 · Modos de ejecución del orquestador

La pregunta del encargo —«si se puede trabajar las tareas en loop o debe ser de una por una»— se responde con tres modos explícitos. El orquestador propone uno y el usuario confirma; no se elige solo.

| Modo | Invocación | Qué hace | Cuándo |
|---|---|---|---|
| **Secuencial** (por defecto) | `/sdd-ejecutar TKT-020` | Un ticket, gate humano al terminar. | Siempre que el ticket toque reglas de negocio, migraciones o seguridad. |
| **Lote** | `/sdd-ejecutar TKT-011..TKT-014 --lote` | Encadena tickets del mismo módulo. Avanza solo mientras todos los gates salgan verdes; se detiene en el primer `REQUIERE DECISIÓN`, `RIESGOSO` o auditoría fallida y reporta dónde paró. | Tickets contiguos, del mismo módulo, sin reglas nuevas. Típicamente la Épica 0. |
| **Abanico** | `/sdd-revisar TKT-020 --paralelo` | Despliega las auditorías en paralelo (arquitectura, seguridad, SQL, código) y consolida los veredictos. | **Solo lectura.** Nunca para implementar. |

**La regla que gobierna los tres:** el paralelismo se aplica a lo que *lee*, nunca a lo que *escribe*. Dos agentes implementando sobre los mismos archivos producen conflictos que ningún linter detecta. Cuatro auditores leyendo el mismo diff no se estorban.

**Límite de lote:** un ticket es una unidad de trabajo. Si un lote acumula más de ~400 líneas de cambio o cruza más de dos módulos, el orquestador lo parte y lo dice.

---

## 5 · Convenciones de código investigadas, por lenguaje

Esto es el paso que el encargo pide antes de crear los agentes: *cómo debe escribirse el código para que sea refactorizado, óptimo y eficiente en cada lenguaje del stack*. Cada bloque se convierte en una skill que los agentes precargan.

> **Advertencia sobre la investigación pública.** Gran parte de lo que se encuentra en la red sobre FastAPI recomienda `async def` y `AsyncSession` por defecto, y sobre Postgres recomienda tablas en **plural**. Las dos cosas **contradicen decisiones ya cerradas de este proyecto** ([ADR-013](../docs/adr/20260919-sqlalchemy-sincrono.md) y la convención de `snake_case` singular). Donde la práctica general choca con una decisión registrada, **gana la decisión registrada**. Esto no es terquedad: es la razón por la que existen los ADRs, y es exactamente el tipo de cosa que un agente «bien informado» rompe sin darse cuenta.

### 5.1 · Python — capa `dominio/`

El código más estricto del proyecto, porque es el que contiene el valor.

- **`Decimal` siempre.** `float` prohibido en cualquier firma. Se construye desde `str`, nunca desde `float`. Cuantización explícita con `ROUND_HALF_UP` y escala declarada; nunca redondeo implícito.
- **Cero imports de framework.** Ni FastAPI, ni SQLAlchemy, ni Pydantic. `import-linter` falla el pipeline si se cruza la frontera.
- **Funciones puras** que reciben objetos de valor y devuelven objetos de resultado. Sin efectos secundarios, sin I/O, sin reloj: si una regla necesita la fecha, se le pasa.
- **Objetos de valor como `@dataclass(frozen=True, slots=True)`**, con validación en `__post_init__`. `slots=True` no es microoptimización: impide añadir atributos por accidente.
- **Los rechazos de negocio son valores de retorno, no excepciones.** Una regla devuelve `ResultadoEvaluacion`; quien decide el código HTTP es la capa API. Excepciones solo para lo que es un error de programa.
- **Cada regla lleva su identificador** en el docstring: `"""Implementa RN-03. Sin efectos secundarios."""`. Es lo que ata el código a la especificación y lo que permite verificar la trazabilidad en CI.
- **Tipado total**, `mypy --strict`. `from __future__ import annotations`. Nada de `Any` sin comentario que lo justifique.
- **Ruff** con, como mínimo: `E,F,W` · `B` (bugbear) · `UP` (pyupgrade) · `SIM` · `RUF` · `ANN` · `TRY` · `PL`. Más una regla propia o un hook que bloquee `float` en `dominio/`.

### 5.2 · Python — capas `aplicacion/`, `api/`, `infraestructura/`

- **Rutas `def`, nunca `async def`.** Una llamada bloqueante dentro de una corrutina congela el bucle entero y ningún linter lo detecta. Esta es la trampa número uno del stack.
- **El caso de uso abre la transacción y orquesta. No decide reglas.** Si aparece un `if` de negocio en `aplicacion/`, está en la capa equivocada.
- **La bitácora se escribe en la misma transacción que el cambio.** No es un `after_commit`, no es un hook, no es un `BackgroundTask`.
- **Pydantic v2 con la API v2:** `model_config = ConfigDict(from_attributes=True)`, `model_validate`, `model_dump`. `from_orm` y `.dict()` están deprecados.
- **El dinero viaja como cadena en JSON.** Pydantic v2 ya serializa `Decimal` como cadena en modo JSON y lo declara `type: string` en el esquema — *verificado contra Context7*. Lo que hay que vigilar no es añadir un serializador, sino que **nadie lo sobrescriba**: un `PlainSerializer(float)` en un campo de dinero reintroduce el flotante por la puerta de atrás, y pasa desapercibido porque el tipo Python sigue siendo `Decimal`.
- **SQLAlchemy 2.0 moderno:** `DeclarativeBase`, `Mapped[...]` con `mapped_column`, `select()` en estilo 2.0. Nada de `Query` heredado.
- **`naming_convention` en el `MetaData`** (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`). Sin esto, Alembic genera diffs ruidosos y restricciones con nombres automáticos que nadie puede referenciar en una migración posterior.
- **Bloqueo pesimista explícito** con `with_for_update()` donde el ADR lo exige; no confiar en el nivel de aislamiento por defecto.
- **El contrato de error es el contrato.** `409` violación de regla, `422` error de forma, `403` falta de permiso. Nunca un `dict` suelto con un mensaje.

### 5.3 · PostgreSQL y Alembic

- **`NUMERIC` con escala declarada** para todo importe. `DOUBLE PRECISION` prohibido.
- **`snake_case` singular** para tablas y columnas. Contradice la recomendación habitual de plural; aquí manda la convención del proyecto.
- **Restricciones con nombre explícito**, siempre. Una restricción anónima no se puede eliminar limpiamente en una migración futura.
- **Los invariantes que puede sostener la base, los sostiene la base.** Disparador que rechaza `UPDATE`/`DELETE` sobre la línea base congelada y sobre la bitácora; `CHECK` para rangos; `EXCLUDE` o único parcial donde corresponda. Una regla implementada solo en Python se salta con un `psql`.
- **Tres roles**: migración (DDL), aplicación (DML), solo lectura. Las pruebas se conectan con **el de aplicación** — con el propietario, las pruebas de permisos quedan verdes sin verificar nada.
- **Migraciones reversibles y revisadas a mano.** `--autogenerate` es un punto de partida: no detecta renombrados, los emite como `drop` + `add`, que en producción es pérdida de datos.
- **Nada de lógica de negocio en la base.** Sin procedimientos almacenados de reglas. Los disparadores solo protegen invariantes estructurales.
- Índice por cada llave foránea que se use en filtro, y por las columnas de la consulta del semáforo.

### 5.4 · TypeScript y React 19

- **Los tipos del cliente se generan del OpenAPI.** Prohibido escribir a mano un tipo que espeje un modelo del backend, y prohibido un esquema Zod que espeje un modelo de Pydantic. Zod valida formularios, no respuestas.
- **`decimal.js` para todo importe.** Ningún `Number()` sobre un campo de dinero, ni para mostrarlo.
- **Tailwind v4 es CSS-first:** la configuración vive en el CSS con `@theme`, no hay `tailwind.config.ts`. Es el error más común al migrar desde v3.
- **TanStack Query**: claves de caché jerárquicas y tipadas en un único módulo (`['obra', obraId, 'semaforo']`), `staleTime` explícito por recurso, invalidación por prefijo. Nada de refetch manual disperso.
- **Cuatro estados por vista, no dos:** cargando, vacío, error, y —propio de este dominio— **bloqueado**. Una requisición bloqueada no es un error: es un resultado legítimo que la interfaz debe saber mostrar con su excedente y su ruta de autorización.
- **TypeScript estricto**, `any` prohibido; `unknown` + estrechamiento donde haga falta.
- Componentes shadcn/ui como base; no reimplementar primitivas accesibles a mano.

### 5.5 · Pruebas

- **Nunca SQLite.** Los tests levantan PostgreSQL con testcontainers, construyen el esquema con `alembic upgrade head` —nunca `create_all()`— y se conectan con el rol de aplicación.
- **El nombre del test lleva el escenario**: `test_hdu002_esc04_requisicion_excede_importe_presupuestado`. Un verificador en CI falla si un escenario de la especificación se queda sin test.
- **Ningún criterio cubre solo el camino feliz.** Cada regla necesita su escenario de rechazo. En CIMENTA el valor del sistema está en lo que rechaza.
- **Prueba de concurrencia donde hay bloqueo**: dos transacciones simultáneas contra el mismo presupuesto deben dejar pasar una sola. Es la prueba que distingue un control presupuestal real de uno decorativo.
- **Anti-test-teatro**: un test que no puede fallar no es un test. En rutas críticas —reglas de dinero, límites, congelado—, mutación manual mínima: cambiar un operador o un umbral y confirmar que algún test se pone rojo.
- Frontend: Vitest para componente, Playwright para los flujos de las historias.

### 5.6 · Seguridad

- **Autorización por obra, no solo por rol.** El riesgo número uno de este modelo de datos es el IDOR: un usuario de la obra A leyendo o escribiendo sobre la obra B porque el `obra_id` viajó en el cuerpo y nadie lo contrastó contra su asignación.
- **Sesión con estado en el servidor.** Cookie con identificador opaco contra la tabla `sesion`. Ni JWT ni cookie firmada autocontenida: quitar un rol tiene que surtir efecto en la petición siguiente.
- **CSRF por doble envío**, y cookies `HttpOnly`, `Secure`, `SameSite`.
- **`pwdlib[argon2]` con Argon2id.** `passlib` no.
- **Archivos:** URL prefirmadas, el tipo se lee **de los bytes**, nunca de la extensión ni de lo que declare el cliente; `SVG` prohibido; un adjunto se anula con motivo, nunca se borra.
- **Sin secretos en el repositorio.** `pydantic-settings` y variables de entorno; `pip-audit` en el pipeline.
- Errores que no filtran trazas ni estructura interna al cliente.

---

## 6 · Catálogo de agentes

Veintiuno. Cada uno hace **una** cosa: un agente que hace dos hace ambas peor.

La columna **Fase** indica cuándo se construye: **A** = necesario para empezar a trabajar tickets; **B** = se añade cuando el proyecto llegue a esa superficie.

**Nueve están construidos**: `analista-dominio`, `arquitecto-tecnico`, `desarrollador-dominio`, `desarrollador-sql`, `tester-backend`, `auditor-arquitectura`, `auditor-seguridad`, `corrector-revision`, `git-entrega`. El resto se nombra en los comandos aunque no exista todavía; qué hace el orquestador mientras tanto está en [metodologia §13](metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe).

**Qué modelo usa cada uno** —y por qué barato para escribir, caro para auditar— está en [metodologia §14](metodologia.md#14--enrutamiento-de-modelo).

### 6.1 · Planeación y análisis

| Agente | Cuándo lo despacha el orquestador | Qué hace | Por qué existe | Fase |
|---|---|---|---|---|
| `analista-dominio` | Antes de `/sdd-definir` | Lee el PRD, el glosario, las historias y el modelo de datos. Devuelve qué reglas `RN-xx`, qué invariantes y qué escenarios toca el ticket, citando el documento. Solo lectura. | Sin el estado real de partida, la spec asume en vez de describir — y en este dominio el vocabulario engaña | A |
| `arquitecto-tecnico` | `/sdd-disenar` | Escribe `design.md`: capa por capa, orden de implementación, verificación de cada paso. Corre la escalera de decisión por objeto y registra en qué peldaño paró. Decide si la decisión merece un ADR. | Fuerza pensar antes de codear y acota el alcance antes de que lo acote el cansancio | A |
| `revisor-impacto` | Antes de cerrar `design.md` | Lista todo lo que depende de lo que se va a tocar. Verifica que ningún módulo hable con otro por fuera de su interfaz de aplicación publicada. | Evita romper lo que nadie recordaba que dependía de ahí; y la regla de fronteras se viola por omisión, no por maldad | A |

### 6.2 · Backend

Cuatro desarrolladores, no uno, porque las cuatro capas tienen reglas incompatibles entre sí. Un solo «desarrollador backend» con las cuatro en el contexto las mezcla.

| Agente | Cuándo | Qué hace | Por qué existe | Fase |
|---|---|---|---|---|
| `desarrollador-dominio` | Hay reglas de negocio en alcance | Escribe `dominio/`: objetos de valor, reglas puras, resultados. `Decimal`, cero imports, docstring con `RN-xx`. | Es la capa donde está el valor y la que más fácil se contamina. Merece un agente que no sepa hacer otra cosa | A |
| `desarrollador-aplicacion` | Hay caso de uso en alcance | Escribe `aplicacion/`: abre transacción, orquesta repositorios y reglas, escribe la bitácora en la misma transacción, aplica el bloqueo pesimista. **No decide reglas.** | La frontera entre orquestar y decidir se borra sola si el mismo agente hace las dos | A |
| `desarrollador-api` | Hay endpoints en alcance | Escribe `api/`: rutas `def`, DTO Pydantic v2, códigos de estado, contrato de error, OpenAPI. | Rutas `async` y mensajes de error sueltos son los dos errores que este stack produce por defecto | A |
| `desarrollador-sql` | Hay esquema, migración o consulta en alcance | Escribe migraciones Alembic, DDL, disparadores, vistas, índices, roles y las consultas no triviales (la del semáforo). | El esquema sostiene 26 invariantes. Escribirlo «de paso» mientras se escribe el modelo es como se pierden la mitad | A |

### 6.3 · Frontend

| Agente | Cuándo | Qué hace | Por qué existe | Fase |
|---|---|---|---|---|
| `disenador-ui-ux` | Hay interfaz nueva en alcance | Define la pantalla antes de implementarla: jerarquía, estados (cargando, vacío, error, **bloqueado**), accesibilidad, qué pasa sin conexión. Entrega una especificación de interfaz, no código. | Un bloqueo presupuestal mal presentado se percibe como un fallo del sistema. El diseño de los estados de rechazo *es* el producto | A |
| `desarrollador-react` | Hay interfaz en alcance | Implementa componentes, hooks y consultas TanStack con los tipos generados del OpenAPI y `decimal.js`. | El stack tiene reglas propias —Tailwind v4 sin config, tipos generados, dinero sin `Number`— que un agente genérico no conoce | A |

### 6.4 · Pruebas

| Agente | Cuándo | Qué hace | Por qué existe | Fase |
|---|---|---|---|---|
| `tester-backend` | Después de implementar backend | Genera pytest con testcontainers: nombre del test con el escenario, happy path **y** rechazo por cada regla, concurrencia donde hay bloqueo, rol de aplicación. | Los tests que se escriben «después, si da tiempo» no se escriben | A |
| `tester-api` | Hay endpoints en alcance | Pruebas de contrato: forma de la respuesta, `409`/`422`/`403`, autenticación, CSRF, permisos por obra. | Un contrato de API se rompe en silencio si nadie lo prueba tras cada cambio | A |
| `tester-frontend` | Después de implementar interfaz | Vitest de componente y Playwright de los flujos de la historia, incluidos los de rechazo. | Los tests de interfaz son los primeros que se omiten bajo presión | B |
| `desarrollador-tdd` | El guard TDD está activo, o el ticket es corrección de error | Ciclo rojo / verde / refactor. En correcciones: el test que reproduce el fallo se commitea **antes** del arreglo. | Es la DoD declarada del proyecto para corrección de error; sin agente, se cumple de palabra | A |

### 6.5 · Auditoría y corrección

Ninguno de estos modifica archivos. Emiten veredicto con evidencia citable —archivo y línea—, y arrancan en `REQUIERE CAMBIOS`: la carga de la prueba cae sobre el `APROBADO`.

| Agente | Cuándo | Qué audita | Por qué existe | Fase |
|---|---|---|---|---|
| `auditor-arquitectura` | Siempre | Las 16 reglas que ninguna implementación puede romper: pureza del dominio, fronteras entre módulos, `Decimal` en todas las capas, rutas `def`, inmutabilidad de la línea base, inventario de solo-anexado sin columna de existencia, bitácora en la misma transacción, archivos fuera de PostgreSQL, sesión con estado. | **Este agente no tiene equivalente en ningún toolkit genérico.** Es el que sabe qué hace distinto a CIMENTA, y el de mayor valor del catálogo | A |
| `auditor-sql` | Hay migración o DDL | Reversibilidad, idempotencia, `NUMERIC`, restricciones nombradas, índices, disparadores, permisos por rol, migración destructiva sin plan. | El esquema aprobado sin auditar llega a producción con errores que no se reproducen en local | A |
| `auditor-codigo` | Hay Python o TypeScript | Tipado, manejo de errores, casos borde, complejidad, código muerto, duplicación, Ruff y mypy limpios. | El mismo que escribió el código no puede auditarlo | A |
| `auditor-seguridad` | Hay endpoint, entrada externa, archivo o sesión | OWASP: autorización por obra (IDOR), inyección, secretos, sesión y CSRF, URL prefirmadas, tipo leído de los bytes, dependencias con CVE. | Es lo más fácil de omitir bajo presión y lo más caro de remediar después | A |
| `auditor-docs` | El cambio altera comportamiento | Que la documentación afectada se actualice en el mismo cambio; que ningún identificador citado sea inexistente; que cada escenario tenga test. Corre `verificar_docs.py`. | En este proyecto la documentación **es** el entregable, y se valida en CI | A |
| `corrector-revision` | Un auditor devolvió `REQUIERE CAMBIOS` | Aplica exactamente los hallazgos señalados y devuelve a reauditoría. Nada más: no refactoriza de paso. | Sin corrector, el ciclo auditoría→arreglo se rompe y el ticket se queda a medias | A |

> **Qué hace un auditor cuando devuelve `RIESGOSO`:** detiene el flujo entero, no solo su paso. Y `corrector-revision` **no actúa** sobre `RIESGOSO` — eso va a `/sdd-escalar`.

### 6.6 · Entrega y proceso

| Agente | Cuándo | Qué hace | Por qué existe | Fase |
|---|---|---|---|---|
| `git-entrega` | Al abrir y al cerrar un ticket | Crea o verifica la rama, revisa que no entren secretos ni archivos fuera de alcance, commitea con el formato del proyecto, abre el PR enlazado al ticket y marca el origen del PR (`agent`, `agent+human-review`). | El repositorio tiene su formato de rama y su atribución; y el origen del PR es una métrica declarada del proyecto | A |
| `ingeniero-ci` | Se toca el pipeline | Mantiene las compuertas: Ruff, mypy, import-linter, pip-audit, pytest con testcontainers, markdownlint, Vale, lychee, los verificadores propios. | Un guardrail que no corre en CI es una recomendación | A |
| `meta-sdd` | Al completar cada ticket | Agrupa las observaciones de `_evolucion.md` por tema, detecta patrones repetidos ≥3 y **propone** mejoras al toolkit. Nunca las aplica solo. | Sin revisión del proceso, el toolkit se fosiliza y deja de reflejar la realidad | A |
| `generador-onboarding` | Alguien nuevo, o módulo desconocido | Recorrido pedagógico de un módulo: qué hace, cómo fluye, dónde están los riesgos. | El onboarding sin guía cuesta tiempo de todo el equipo | B |

### 6.7 · Lo que el encargo pedía y aquí se resuelve distinto

Tres desviaciones conscientes respecto de la lista del encargo. Cada una tiene su motivo:

| Se pidió | Aquí | Motivo |
|---|---|---|
| `git-back` y `git-front` separados | Un solo `git-entrega` | CIMENTA es un monorepo. Dos agentes git sobre el mismo repositorio compiten por el índice de git y producen estados a medias. |
| «Desarrollador SQL que escribe SPs» | `desarrollador-sql` **sin procedimientos de negocio** | Las reglas viven en `dominio/`, puro. Un SP con lógica rompe el ADR del dominio puro y deja la regla fuera del alcance de `import-linter` y de los tests de dominio. |
| Un «desarrollador backend» | Cuatro, uno por capa | La arquitectura tiene cuatro capas con reglas que se contradicen entre sí. Un agente con las cuatro en contexto las mezcla — que es justo lo que la arquitectura existe para impedir. |

Y cuatro agentes que **el encargo no pedía y el proyecto necesita**: `auditor-arquitectura` (las 16 reglas propias), `auditor-docs` (la documentación es el entregable y se valida en CI), `desarrollador-dominio` separado (la capa de valor), `analista-dominio` (el glosario tiene términos que no significan lo que parecen).

---

## 7 · Quién despacha a quién

El orquestador es el hilo principal ejecutando el comando. Cada comando declara qué agentes puede desplegar; fuera de esa lista, no.

```
/sdd-definir      analista-dominio ──► [spec.md] ──► abogado-del-diablo (skill)
                                                        │
                                                   GATE humano

/sdd-disenar      arquitecto-tecnico ──► [design.md] ──► revisor-impacto
                                                              │
                                                     abogado-del-diablo
                                                              │
                                                        GATE humano

/sdd-ejecutar     desarrollador-tdd (si aplica)
                  ├─ desarrollador-dominio
                  ├─ desarrollador-aplicacion      (secuencial: tocan los mismos archivos)
                  ├─ desarrollador-sql
                  ├─ desarrollador-api
                  ├─ disenador-ui-ux ──► desarrollador-react
                  └─ tester-backend · tester-api · tester-frontend
                                   │
                            git-entrega (rama)

/sdd-revisar      ┌─ auditor-arquitectura ┐
                  ├─ auditor-seguridad    │  en paralelo — solo lectura
                  ├─ auditor-sql          │
                  ├─ auditor-codigo       │
                  └─ auditor-docs         ┘
                                   │
                        ¿REQUIERE CAMBIOS? ──► corrector-revision ──► reauditar (máx. 3)
                        ¿RIESGOSO?         ──► /sdd-escalar

/sdd-completar    [delta.md] ──► auditor-docs ──► git-entrega (PR) ──► meta-sdd
```

---

## 8 · Skills

Dos familias: las que gobiernan el proceso y las que llevan las convenciones.

### 8.1 · De proceso

| Skill | Qué hace | Origen |
|---|---|---|
| `abogado-del-diablo` | Pasada adversarial sobre spec y design: reta supuestos, marca `(asumido)`, busca el contraejemplo. Máximo cinco objeciones, cada una accionable. Si no hay objeción real, lo dice en una línea en vez de inventar fricción. | Portada de SDD-Nice. Encaja exacto con la sección «falsa completitud» de las convenciones del proyecto |
| `caveman` | Compresión de la comunicación. Ya disponible en el entorno. | Pedida en el encargo — con una salvedad, abajo |
| `skill-creator` | Crear y afinar las skills propias. Ya disponible. | Anthropic |
| `code-review` · `security-review` | Revisión del diff y revisión de seguridad. Ya disponibles. | Claude Code |

### 8.2 · De convenciones (se precargan por agente con `skills:`)

`conv-dominio-python` · `conv-backend-fastapi` · `conv-sql-postgres` · `conv-frontend-react` · `conv-pruebas` · `conv-seguridad` · `conv-documentacion`

Es el contenido de la sección 5 de este documento, partido para que cada agente cargue **solo lo suyo**. Un agente de dominio que carga las convenciones de React tiene ruido de contexto que degrada lo que produce.

### 8.3 · Sobre `caveman` — una salvedad que hay que decidir

El encargo pide activar `caveman` en cada interacción. Funciona y ahorra tokens, pero hay un riesgo concreto en **este** proyecto: la documentación es el entregable, se valida con `Vale` con estilo Microsoft, y los artefactos SDD —spec, design, delta, ADR, criterios Gherkin— son prosa que alguien va a leer y revisar. Comprimirlos degrada justo lo que se está entregando.

**Propuesta:** `caveman` se aplica a la **conversación** —mis respuestas en el chat, los reportes de avance, los veredictos— y **nunca** a los artefactos escritos a disco: `spec.md`, `design.md`, `delta.md`, ADRs, docstrings, documentación y mensajes de commit. Se activa con un hook `UserPromptSubmit` y la regla de exclusión vive en el propio toolkit.

### 8.4 · Sobre `superpowers` — no usarla como pipeline

Está disponible y es buena, pero es *otra* metodología completa (plan → spec → TDD → verificación). Correrla junto a `cimenta-sdd` da dos pipelines compitiendo por el mismo turno. **Recomendación:** no activarla como flujo. Si interesa alguna de sus piezas —el ciclo TDD, la depuración por causa raíz—, se absorbe la idea en nuestros agentes, no la skill entera.

---

## 9 · Guardrails: hooks que bloquean

Lo que el proyecto declara como innegociable se verifica con un hook, no con una recomendación en un Markdown. Un guardrail que depende de que el agente se acuerde no es un guardrail.

| Hook | Dispara en | Bloquea |
|---|---|---|
| `veto-float-dominio` | `PreToolUse` sobre `Write`/`Edit` en `backend/cimenta/*/dominio/**` | `float` en una firma, o cualquier `import` de framework |
| `veto-sqlite-tests` | `PreToolUse` sobre `Write`/`Edit` en `tests/**` | `sqlite`, `create_all(` |
| `veto-ruta-async` | `PreToolUse` sobre `Write`/`Edit` en `*/api/**` | `async def` en un decorador de ruta |
| `exige-test-de-escenario` | `PreToolUse` sobre `Write` de un módulo con reglas | Implementar una regla `RN-xx` sin su test de rechazo hermano |
| `activa-caveman` | `UserPromptSubmit` | — (inyecta la preferencia cada turno) |

Los cuatro primeros son la traducción directa de cuatro reglas del `CLAUDE.md` que hoy solo existen como texto.

---

## 10 · Estructura de archivos

```
.claude/
├── agents/                      9 construidos de 21
├── skills/
│   ├── sdd-definir/SKILL.md     los 7 comandos del pipeline
│   ├── sdd-disenar/  …
│   ├── conv-dominio-python/     los 7 paquetes de convenciones
│   └── abogado-del-diablo/
├── hooks/                       los scripts de los guardrails
└── settings.json                registro de hooks y permisos

sdd/
├── 00-propuesta-toolkit.md      este documento
├── metodologia.md               el núcleo: estados, escalera, gates, DoD
├── plantillas/                  _index · spec · design · impl · delta
├── tickets/TKT-xxx/             un directorio por ticket, versionado
└── _evolucion.md                observaciones que alimentan a meta-sdd
```

Los artefactos por ticket se versionan: son la trazabilidad del proyecto y lo que `meta-sdd` lee para proponer mejoras.

---

## 11 · Orden de construcción

Construir veintiún agentes antes del primer ticket es el mismo error que escribir una spec de doce criterios de una pasada: parece completo y no lo es, porque todavía no se ha visto ninguno trabajar.

| Paso | Qué se construye | Para qué | Estado |
|---|---|---|---|
| 1 | `sdd/metodologia.md` + plantillas | El núcleo. Sin él los comandos no tienen contra qué escribir | **Hecho** |
| 2 | Las 7 skills de convenciones | El contenido que cada agente carga, solo el de su capa | **Hecho** |
| 3 | Los 7 comandos del pipeline | El orquestador | **Hecho** |
| 4 | Los 9 agentes mínimos | Suficiente para correr TKT-001 de principio a fin | **Hecho** |
| 5 | **Rodar TKT-001 completo** y ajustar con lo aprendido | Un toolkit que no se ha usado es una hipótesis | Siguiente |
| 6 | Los agentes restantes de fase A | Ya con evidencia de qué falta de verdad | Pendiente |
| 7 | Hooks que bloquean (`float` en dominio, `sqlite` en tests, `async def` en rutas) | Cuando ya se sabe qué se rompe en la práctica | Pendiente |
| 8 | Fase B | Cuando el proyecto llegue a esa superficie | Pendiente |

> El hook de `caveman` sí está puesto desde el principio: no es un guardrail de código, es una preferencia de comunicación, y no hace falta evidencia de uso para activarla.

---

## 12 · Decisiones tomadas · 2026-10-01

1. **`caveman` solo comprime la conversación.** Mis respuestas, reportes de avance y veredictos. Nunca `spec.md`, `design.md`, `delta.md`, ADRs, docstrings, documentación ni mensajes de commit.
2. **Los artefactos por ticket viven en `sdd/tickets/` y se versionan.** Entran al PR; son la trazabilidad del proyecto y la materia prima de `meta-sdd`.
3. **Se construye el núcleo y los 9 agentes mínimos, y se rueda TKT-001 antes de seguir.** Un toolkit que no se ha usado es una hipótesis.

---

## Referencias

- [SDD-Nice](https://github.com/) — toolkit interno consultado en `C:\GitHub\SDD-Nice`, solo lectura
- [Claude Code · Subagentes](https://code.claude.com/docs/en/sub-agents)
- [Claude Code · Comandos slash y skills](https://code.claude.com/docs/en/slash-commands)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Postgres best practices I wish every app developer knew](https://www.bytebase.com/blog/postgres-best-practices-i-wish-app-developers-knew/)
- [Best Practices for Alembic and SQLAlchemy](https://medium.com/@pavel.loginov.dev/best-practices-for-alembic-and-sqlalchemy-73e4c8a6c205)
- [shadcn/ui · Tailwind v4](https://ui.shadcn.com/docs/tailwind-v4)
- [Claude Code Multi-Agent Orchestration · Tembo](https://www.tembo.io/blog/claude-code-multi-agent-orchestration)
- [Best Practices with Claude Code Subagents · PubNub](https://www.pubnub.com/blog/best-practices-claude-code-subagents-part-two-from-prompts-to-pipelines/)
