# Convenciones de documentación y planificación

> **Qué es este documento.** Las reglas de trabajo del proyecto CIMENTA, derivadas del material de los Módulos 4 (planificación) y 5 (documentación) del máster. No es teoría: es lo que este repositorio hace y contra lo que se revisa cada entrega.
>
> **Por qué existe.** Porque el cuello de botella se invirtió. Escribir código dejó de ser lo caro; lo caro es revisar código equivocado, y el código sale equivocado cuando la especificación era ambigua. Un agente de IA no pregunta ante la ambigüedad: **inventa**. Todo lo que sigue son contramedidas contra eso.

---

## 1. El principio rector

> La documentación ya no es solo para humanos. Es el contexto con el que los agentes de IA trabajan sobre el sistema.

De ahí se derivan tres consecuencias operativas que este proyecto asume:

**La ambigüedad ahora es cara.** En la era pre-IA una historia vaga se aclaraba en el daily. Ahora puede estar implementada de la peor forma plausible antes de que alguien se dé cuenta.

**La IA genera el borrador; el humano valida el significado.** La forma es barata, el significado no. Una especificación con formato perfecto que describe mal el negocio es peor que no tener nada, porque nadie la cuestiona.

**Lo que no está escrito, se inventa.** Por eso este proyecto tiene un [glosario de dominio](glosario.md) y por eso todo supuesto se marca explícitamente.

---

## 2. Docs-as-code

La documentación vive en el repositorio, pasa por revisión y se valida automáticamente. No hay Confluence, no hay PDF de arquitectura, no hay carpeta compartida.

Una documentación es **viva** —y no estática— si cumple las tres:

1. **La fuente de verdad está en el repo.** No existe en ningún sistema externo sin sincronizar.
2. **Se actualiza en el mismo cambio que la provoca.** El PR que cambia el código actualiza la documentación afectada.
3. **Se valida automáticamente.** Si se desactualiza, algo en CI se queja.

### Las cuatro capas

Mezclarlas en el mismo sitio es el origen de la mayoría de los problemas de mantenimiento. Cada una tiene audiencia y ritmo propios.

| Capa | Dónde vive | Audiencia | Ritmo de cambio |
|---|---|---|---|
| **Producto** | `docs/01-descripcion-producto.md`, `docs/glosario.md` | Cliente, equipo, agentes | Lento — cambia con el negocio |
| **Arquitectura** | `docs/02-arquitectura.md`, `docs/adr/`, diagramas | Equipo técnico + agentes | Lento — cambia con decisiones técnicas |
| **API** | Borrador `docs/api/openapi.yaml` en diseño; OpenAPI generado desde el código en ejecución, comparado contra el borrador en CI | Frontend, integradores, agentes | Medio — cambia con cada release |
| **Código** | Docstrings en el propio código | Equipo + agentes en modo agéntico | Rápido — cambia con cada PR relevante |

El anti-patrón que este proyecto evita explícitamente: un único `README.md` de 800 líneas. El README es un índice, no un contenedor.

---

## 3. Estructura del repositorio

```
IA4Devs-Proyecto-Final/
├── .claude/                        Agentes, skills, hooks y comandos del pipeline SDD
├── .editorconfig                   Codificación y finales de línea por tipo de archivo
├── .gitattributes                  Normalización de finales de línea: LF en el repositorio
├── .env.example                    Plantilla de variables de entorno con valores de desarrollo evidentes; `.env` no se versiona
├── compose.yaml                    PostgreSQL local (TKT-003); MinIO llega con TKT-059
├── README.md                       Índice + ficha del proyecto. Nunca contenido extenso
├── llms.txt                        Mapa del proyecto para agentes IA
├── CLAUDE.md                       Instrucciones de proyecto para el copiloto (Paso 5)
├── Doc de contexto/                Fuente del cliente. Solo lectura, no se versiona
├── backend/                        Proyecto uv del backend: pyproject.toml, uv.lock, el paquete cimenta/ y, fuera de él, contrato_error/, servidor/, migraciones/, herramientas/, tipos_base/ y tests/
├── frontend/                       Proyecto npm del frontend: package.json, TypeScript y ESLint
├── sdd/                            Pipeline SDD: metodología, plantillas y un directorio por ticket
├── tools/                          Verificadores de la documentación y sus pruebas
└── docs/
    ├── convenciones.md             Este documento
    ├── arranque-local.md           Requisitos, arranque local y verificadores
    ├── glosario.md                 Lenguaje ubicuo del dominio
    ├── 01-descripcion-producto.md  PRD — capa Specify de SDD
    ├── 02-arquitectura.md          Capa Plan — Paso 3
    ├── 03-modelo-datos.md          Capa Plan — Paso 3
    ├── 04-historias-usuario.md     Capa Tasks — Paso 4
    ├── 05-tickets-trabajo.md       Capa Tasks — Paso 4
    ├── 06-stack-tecnologico.md     Decisiones de stack — Paso 5
    ├── 07-especificacion-api.md    Endpoints, convenciones y contrato de error
    ├── 08-wireframes.md            Bocetos de baja fidelidad de las pantallas del hilo vertical
    ├── api/
    │   └── openapi.yaml            Borrador OpenAPI 3.1 de la fase 1: el contrato del agente
    └── adr/
        ├── README.md               Índice de decisiones
        ├── template.md             Plantilla MADR
        └── YYYYMMDD-slug.md        Un archivo por decisión
```

---

## 4. Spec-Driven Development

La especificación es el artefacto del que se deriva todo lo demás. Nada se implementa sin una especificación previa que lo justifique.

| Fase SDD | Pregunta | Artefacto en este repo |
|---|---|---|
| **Constitution** | ¿Qué principios no se negocian? | Principios no negociables del `README.md` |
| **Specify** | ¿Qué y por qué? *(nunca el cómo)* | `docs/01-descripcion-producto.md` |
| **Plan** | ¿Cómo se construye? | `docs/02-arquitectura.md`, `docs/03-modelo-datos.md`, `docs/06-stack-tecnologico.md`, ADRs |
| **Tasks** | ¿En qué orden y con qué criterio de *hecho*? | `docs/04-historias-usuario.md`, `docs/05-tickets-trabajo.md` |

**La regla de capas.** Una decisión técnica en la capa *Specify* es un error, igual que una regla de negocio nueva que aparece por primera vez en la capa *Plan*. Si al escribir arquitectura surge una regla de negocio no documentada, se sube al PRD antes de continuar.

---

## 5. Backlog AI-ready

### La pirámide

```
PRD              Visión, alcance MVP, métricas de éxito
 └── EPIC        Bloque grande de capacidad. Una hipótesis de producto
      └── HISTORIA DE USUARIO   Comportamiento observable. INVEST. Cabe en un sprint
           └── TICKET           Unidad de trabajo técnico para alguien (humano o agente)
                └── CRITERIO DE ACEPTACIÓN   Cómo se verifica. Testeable. Sin ambigüedad
```

**El nivel correcto para dar trabajo a un agente es la historia, no el épico.** Pedirle a un agente que implemente un épico completo es la forma más rápida de quemar tokens y obtener algo aproximado.

### INVEST como filtro de entrada

No como aspiración: como puerta. Una historia que falla dos o más de los seis criterios vuelve a refinamiento, sin negociación.

| | Criterio | Qué significa aquí |
|---|---|---|
| **I** | Independiente | Se puede construir sin esperar a otra historia |
| **N** | Negociable | Describe el qué, no impone el cómo |
| **V** | Valiosa | Un rol de §4 del PRD obtiene algo que hoy no tiene |
| **E** | Estimable | El equipo puede darle un número sin investigar antes |
| **S** | Pequeña | Cabe en un sprint; 1-2 días humano-equivalente |
| **T** | Testeable | Sus criterios de aceptación se pueden ejecutar |

> La IA no rescata historias vagas: las amplifica.

**Cómo se aplican la I y la S aquí, porque literalmente ninguna historia las pasaría.** Las nueve historias de CIMENTA declaran relaciones *Bloquea / Bloqueada por*, y dos de ellas valen 13 puntos. Con la lectura estricta, ocho de nueve volverían a refinamiento y el filtro dejaría de decir nada.

- **I · Independiente** se lee como independencia de **valor y de despliegue**, no de construcción. Una historia pasa si entrega algo observable por sí sola aunque necesite que otra exista primero. HDU-006 es el caso claro: se apoya en HDU-001 pero entrega un tablero utilizable sin esperar a sus cuatro fuentes.
- **S · Pequeña** se lee como **cabe en un sprint**, que es el criterio operativo. El "1-2 días humano-equivalente" describe el tamaño típico, no el máximo: una historia de 13 puntos pasa si su descomposición en tickets es conocida y cada ticket sí es pequeño.

Lo que **no** se relaja: una historia cuyas dependencias no estén declaradas con evidencia en la matriz de relaciones, o cuya descomposición nadie sepa hacer, sí vuelve a refinamiento.

### Criterios de aceptación en Gherkin

Formato `Given / When / Then`, porque es directamente traducible a tests: un agente lee el escenario y genera la prueba sin un paso intermedio de interpretación.

**La regla dura de este proyecto:** cada historia cubre el camino feliz **y** al menos un escenario de rechazo por cada regla de negocio implicada. Una historia que solo describe el happy path no está especificada.

Esto no es preferencia de estilo. En CIMENTA el valor del sistema está precisamente en lo que debe **rechazar**: compras que exceden el presupuesto, recepciones mayores a lo ordenado, pagos sin validación de avance, pedidos que superan el tope de consignación. Especificar solo el éxito es no especificar el producto.

```gherkin
# ✅ Ejecutable
Escenario: Requisición que excede el presupuesto del tipo de partida
  Dado que el tipo de partida "MUROS" de la obra "Union Square F2" tiene $12,000 disponibles
  Cuando Compras levanta una requisición por $15,000 contra ese tipo de partida
  Entonces la requisición queda en estado "BLOQUEADA"
  Y se genera una solicitud de autorización dirigida a Dirección General
  Y la respuesta indica el disponible real y el excedente: $3,000

# ❌ Placeholder que va a explotar en revisión
Escenario: El control de presupuesto funciona
```

### "AI as poke-holes"

El patrón correcto no es pedirle a la IA que escriba los criterios desde cero — eso produce lo genérico. Es al revés:

1. El humano escribe los criterios del camino feliz. Cuatro a seis, tres minutos.
2. Se le pasa la historia a la IA pidiendo **edge cases, supuestos implícitos, escenarios faltantes y dependencias no mencionadas**.
3. De los 10-15 candidatos que devuelve, la mayoría es ruido. Se conservan los 3-5 reales.
4. El refinamiento deja de ser leer la historia juntos y pasa a ser discutir los huecos que la IA marcó.

### La trampa de la falsa completitud

Una lista de 12 criterios generados por IA **parece** exhaustiva. No lo es: el modelo no sabe lo que no sabe del negocio real —la regla que solo conoce quien lleva años en la obra, el archivo que arrastra un `#REF!` desde hace meses.

Contramedidas obligatorias en este proyecto:

- Todo criterio generado por IA es **un borrador**, nunca un entregable.
- Todo lo que no tiene evidencia clara en la documentación fuente se marca **(asumido)** y se recoge en la sección de preguntas abiertas.
- Ningún criterio se acepta sin contrastarlo contra los archivos reales del cliente.

### Anatomía de una historia

El orden no es decorativo: **el agente lee de arriba a abajo**. Si el contexto técnico va primero, decide sobre técnica antes de entender el producto.

```markdown
## HU-XX · Título

**Como** <rol del PRD §4>
**quiero** <capacidad>
**para** <valor>

### Criterios de aceptación
Escenarios Gherkin: camino feliz + rechazo por cada regla de negocio implicada

### Reglas de negocio implicadas
RN-03, RN-04 — enlazadas al catálogo del PRD §8

### Non-goals
Lo que esta historia explícitamente NO hace

### Definition of Done
La plantilla que corresponda al tipo de trabajo

### Contexto técnico        ← siempre al final
Archivos, modelos y endpoints relevantes
```

**Los non-goals duelen porque parecen redundantes. No lo son.** Sin ellos, un agente al que se le pide un endpoint entrega además el refactor del módulo, la documentación y una optimización de consultas: un PR de 800 líneas en lugar de 150.

---

## 6. Definition of Done por tipo de trabajo

Una única DoD para todo es un anti-patrón: demasiado genérica para guiar y demasiado específica para lo que no encaja.

**Funcionalidad nueva**

- [ ] Cubre todos los escenarios Gherkin, incluidos los de rechazo
- [ ] Al menos un test por escenario
- [ ] La cobertura del módulo no baja
- [ ] Validación de entradas y salidas
- [ ] Documentación de API actualizada
- [ ] PR enlazado al ticket
- [ ] Revisión de al menos un humano, no solo de agentes

**Corrección de error**

- [ ] Test que reproduce el fallo, commiteado **antes** del arreglo
- [ ] Arreglo mínimo y enfocado, sin refactors no relacionados
- [ ] El test pasa
- [ ] Análisis breve en el ticket: por qué se introdujo y si CI podría haberlo detectado

**Refactor**

- [ ] La cobertura no baja
- [ ] Comportamiento observable inalterado: mismos contratos, mismos endpoints
- [ ] El PR explica la motivación arquitectónica
- [ ] No mezclado con cambios funcionales

**Documentación**

- [ ] Revisado por un humano, no solo por IA
- [ ] Los fragmentos de código son ejecutables
- [ ] Sin enlaces rotos
- [ ] Versionado en el repo

**Spike / investigación**

- [ ] Hallazgos, alternativas y recomendación documentados
- [ ] ADR creado si la investigación cierra una decisión
- [ ] Decisión explícita: continuar, pivotar o cancelar

---

## 7. Estimación

| Unidad | Cuándo | Cuándo no |
|---|---|---|
| **Story points (Fibonacci 1, 2, 3, 5, 8, 13)** | Planificación de sprint | — |
| **Tallas de camiseta (S, M, L, XL)** | Roadmap, épicos, discovery | — |
| **Horas** | Reporte externo | **Nunca** como unidad interna |

Las horas dejaron de funcionar: cuando un agente tarda 3 minutos y la persona que revisa tarda 25, la unidad mezcla trabajo cognitivo humano con trabajo de máquina y ya no mide nada.

### Las tres trampas

**Optimismo por contagio.** Una historia que la IA generó en tres segundos *se siente* pequeña. Es sesgo de fluidez cognitiva: lo que se procesa fácil parece simple.
→ Separar generación y estimación por tiempo e interlocutor.

**Falsa precisión.** "3.5 puntos" suena sofisticado, pero el modelo promedia patrones de su dataset, no mide este código.
→ Redondear siempre a la escala discreta. La IA sugiere el bucket, nunca el decimal.

**Homogeneización.** Si se pide "descompón este PRD en historias", todas salen con la misma forma y el mismo tono, lo que enmascara que unas son CRUD trivial y otras esconden concurrencia o integraciones frágiles.
→ Clasificar por complejidad **antes** de pedir criterios de aceptación.

### La IA como par, no como árbitro

Sirve como un participante más del planning poker. El valor no está en su número: está en la conversación que se abre cuando su estimación difiere de la del equipo. O la IA está leyendo complejidad oculta, o el equipo tiene contexto que ella no tiene. En ambos casos emerge información.

**Anti-patrón:** usar la IA para zanjar desacuerdos. No sabe más que el equipo sobre su propio sistema.

### Buffer

**30-40 %**, no el 10-15 % clásico. No es pesimismo: los PR generados por agente requieren revisión más cuidadosa, el volumen de código sube y con él los defectos, y las herramientas cambian cada pocas semanas.

> Una estimación sin discusión vale menos que la ausencia de estimación. El número es el subproducto de la conversación.

---

## 8. Decisiones de arquitectura: ADR

Se escribe un ADR cuando la respuesta a esta pregunta es *sí*:

> Si alguien llegara hoy al proyecto y viera esto, ¿se preguntaría *"por qué lo hicieron así"*?

No se documentan todas las decisiones, solo las que alguien podría deshacer o cuestionar por desconocer el contexto.

**Formato:** MADR (*Markdown Any Decision Records*). Se elige sobre el formato Nygard original porque su estructura explícita de opciones con pros y contras es mucho más útil cuando quien la rellena es un agente.

**Nomenclatura:** `docs/adr/YYYYMMDD-slug.md`. Fecha, no número secuencial: es más robusto cuando hay decisiones concurrentes en ramas distintas.

**Secciones:** Estado · Contexto y problema · Opciones consideradas · Decisión · Consecuencias.

**Flujo eficiente:** no escribir el ADR desde cero, sino transcribir a MADR una decisión ya tomada. Pegar la discusión real —el hilo, la descripción del PR— y pedir que se estructure. La IA extrae y ordena los argumentos mejor de lo que se redactan desde una página en blanco. El razonamiento real, eso sí, lo aporta quien tomó la decisión.

### Diagramas

**Mermaid por defecto.** Diagramas como texto dentro del Markdown, que GitHub renderiza nativamente. Cero fricción: se editan en el mismo PR que el código.

**Structurizr DSL solo si hace falta.** El criterio es pragmático: si el Mermaid del documento explica suficientemente la arquitectura a alguien que llega nuevo, no hace falta más. Se justifica cuando hay más de tres o cuatro contenedores no triviales o se necesitan vistas C4 coordinadas desde un único modelo. **Se decide en el Paso 3**, con la arquitectura ya definida.

---

## 9. Documentación para agentes

**[`llms.txt`](../llms.txt)** en la raíz: el equivalente a `robots.txt` para agentes de IA. Describe en pocas líneas qué es el proyecto, dónde está cada documento y qué reglas no puede romper ninguna implementación. Coste cero y reduce alucinaciones cuando un agente externo genera código para el proyecto. Creado en el Paso 3; su sección de stack se completa en el Paso 5.

**`CLAUDE.md`** en la raíz: instrucciones de proyecto para el copiloto — convenciones de código, comandos, qué no tocar. Es la capa de *instrucciones*; los docstrings son la capa de *conocimiento*. Juntas hacen que un agente en el turno 50 de una sesión larga entienda lo mismo que en el turno 1. Se crea en el **Paso 5**: sin stack definido, las convenciones de código y los comandos estarían vacíos.

**Context7 MCP** ya está conectado en este entorno. Su función es inyectar documentación versionada y actualizada de las librerías del stack, en lugar de que el modelo genere código desde un conocimiento de corte que puede tener meses. Se usará sistemáticamente al implementar contra las librerías que se elijan en el Paso 5.

---

## 10. Validación de documentación en CI

Si el código sin tests es deuda técnica, la documentación sin validación es **deuda documental** — y es silenciosa: el enlace roto que nadie detecta, la terminología inconsistente que llega al lector sin pasar por revisión.

| Capa | Herramienta | Qué detecta |
|---|---|---|
| **Sintaxis Markdown** | `markdownlint-cli2` | Encabezados inconsistentes, listas mal indentadas, enlaces vacíos |
| **Prosa** | `Vale` con estilo Microsoft | Voz pasiva, términos vagos, inconsistencia terminológica |
| **Enlaces** | `lychee` | URLs muertas, anclas inexistentes |
| **Cobertura de docstrings** | `interrogate` | Funciones públicas sin documentar |
| **Fronteras entre módulos** | `import-linter` | Un módulo que importa el dominio o la infraestructura de otro |
| **Consistencia de la documentación** | [`tools/verificar_docs.py`](../tools/README.md) | Enlaces y anclas rotos, identificadores inexistentes, conteos descuadrados |
| **Diagramas** | [`tools/extraer_mermaid.py`](../tools/README.md) | Un diagrama Mermaid con sintaxis inválida |
| **Escenarios sin test** | [`tools/verificar_escenarios.py`](../tools/verificar_escenarios.py) | Un escenario de la especificación que ningún test cubre |

Dos ajustes de criterio:

- **`warning` en local, `error` en CI.** Vale produce muchos avisos en la primera pasada; no se bloquea el pipeline hasta haber limpiado la línea base.
- **`lychee` también en cron semanal**, no solo en cada PR: los enlaces externos se rompen sin que nadie toque la documentación.

**Vocabulario del proyecto.** El dominio está lleno de términos que cualquier linter marcaría como errores: *tablaroca*, *destajo*, *perfacinta*, *antepecho*, *cajillo*, *plafón*, *redimix*, *CIMENTA*. Se declaran en el vocabulario aceptado de Vale, tomándolos del [glosario](glosario.md).

> **Adaptación a Python, resuelta en el Paso 5.** El material del máster ejemplifica esta capa sobre un stack TypeScript. La equivalencia completa está en [`06-stack-tecnologico.md` §9](06-stack-tecnologico.md#9-documentación): `TSDoc + TypeDoc` → **docstrings + mkdocstrings sobre MkDocs Material**; `typedoc --validation.notDocumented` → **interrogate**; `adonis-autoswagger` → **OpenAPI nativo de FastAPI**. **Scalar se conserva** sin cambios, porque consume la especificación OpenAPI y es independiente del lenguaje.

---

## 11. Métricas honestas

Aplica desde el momento en que haya código.

**Velocity sirve para planificar, nunca como indicador de rendimiento.** Con IA es trivial inflarla llenando el sprint de historias generadas y completadas con mínimo aporte humano: la velocidad sube y el valor entregado no necesariamente.

**Marcar el origen de cada PR** — `human`, `human+copilot`, `agent`, `agent+human-review` — y reportar la calidad segmentada por origen. Si los PR de agentes tienen tres veces más defectos, la velocity total está mintiendo.

**Para medir productividad real, mirar outcomes**: frecuencia de despliegue, lead time, tiempo de recuperación, tasa de fallos en cambios. No story points.

---

## 12. La IA en el ciclo de desarrollo

El máster pide que la IA esté presente en al menos cuatro de las seis fases. En CIMENTA está en las seis, y en cada una con el mismo reparto: **la IA produce el borrador y una comprobación automática o una persona decide si vale.** Una fase en la que la IA genera y nadie verifica no cuenta como fase con IA. Cuenta como fase sin control.

| Fase | Qué hace la IA | Con qué contexto | Quién o qué lo verifica |
|---|---|---|---|
| **Análisis** | Busca casos límite, supuestos implícitos y escenarios faltantes en cada historia ([§5, *AI as poke-holes*](#ai-as-poke-holes)) | PRD, glosario, archivos del cliente | El cliente responde las `PA-xx`; lo no respaldado se marca **(asumido)** |
| **Diseño** | Redacta ADR a partir de la discusión real, diagramas Mermaid y el borrador OpenAPI | Arquitectura, modelo de datos, ADR previos | `verificar_docs.py`, `extraer_mermaid.py`, `openapi-spec-validator` y revisión humana |
| **Implementación** | Implementa un ticket cada vez dentro de sus *non-goals*, con Context7 para las librerías del stack | `CLAUDE.md`, `llms.txt`, el ticket, la historia, `docs/api/openapi.yaml` | `import-linter`, mypy, Ruff, la prueba de contrato de TKT-061 y la revisión del PR |
| **Pruebas** | Escribe **primero** los tests de cada escenario de la historia, con el nombre `test_hdu00X_escNN_…`, y después el código que los pone en verde | Los escenarios Given/When/Then, el contrato de error, los wireframes para los recorridos de Playwright | El verificador de escenarios sin test falla el pipeline ([ADR-012](adr/20260918-trazabilidad-escenario-test.md)); una persona comprueba en la revisión que el test de rechazo **afirma el rechazo** y no solo que la respuesta llega |
| **Despliegue** | Escribe el `Dockerfile` multietapa, los *workflows* de GitHub Actions y los scripts de respaldo, restauración y verificación de hash de los objetos | Stack §10, `RNF-10`, `RNF-11`, `RNF-19`, ADR-008 | El pipeline los ejecuta en cada PR. **El ensayo de restauración lo ejecuta y mide una persona** (`RNF-11`, TKT-058): la IA puede escribir el script, no dar por buena la restauración |
| **Mantenimiento** | **Revisa automáticamente cada pull request** con Claude Code en GitHub Actions (TKT-062) contra las reglas de `CLAUDE.md`, el ticket enlazado y sus *non-goals*, y deja comentarios en línea. Prioriza las alertas de Dependabot y de `pip-audit`. Diagnostica errores de Sentry a partir del identificador de correlación | `CLAUDE.md`, el diff, el ticket, el registro técnico | **La revisión automática comenta, nunca aprueba ni fusiona.** La aprobación es humana y obligatoria (DoD §6). La etiqueta de origen del PR alimenta las métricas de §11 |

### Qué revisa la revisión automatizada de PR

No es una revisión genérica de estilo, que ya hacen Ruff y ESLint. Es una lista cerrada con lo que este proyecto **no puede** dejar pasar y que ningún linter detecta entero:

1. Un `float` o un `number` de JSON en cualquier camino por el que pase dinero.
2. Una ruta `async def`, o una llamada bloqueante dentro de una corrutina ([ADR-013](adr/20260919-sqlalchemy-sincrono.md)).
3. Una regla de negocio fuera de `dominio/` —en un controlador de `api/`, en un caso de uso o en un modelo del ORM—, o un `dominio/` que importa framework u ORM.
4. Un cálculo de `consumido` que no sea la consulta única del [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo).
5. Un escenario de rechazo de la historia sin su test, o un test de rechazo que no comprueba el contrato de error.
6. Un `UPDATE` o `DELETE` sobre la bitácora, el libro mayor o la línea base congelada.
7. Un cambio de comportamiento sin la documentación afectada en el mismo PR (§2).
8. Trabajo que el ticket declara como *non-goal*, o fuera de su alcance.
9. Un importe simulado que entra en el `consumido` de `RN-03`, o un ticket de fase 1 que adelanta trabajo de fase 2 (regla 17 de `CLAUDE.md`, [ADR-017](adr/20261015-fuentes-simuladas-analitica.md)).
10. Un cliente que evalúa una regla: que decide con el disponible o el saldo en caché, o que da por aceptado lo que encoló sin conexión (regla 10 de `CLAUDE.md`, [ADR-015](adr/20260919-captura-diferida-sin-conexion.md)).
11. Todo PR que toca `docs/api/openapi.yaml`. Se señala siempre, tenga o no un defecto: el borrador es el contrato que se implementa, y cambiarlo es una decisión que la persona que aprueba tiene que ver explícitamente.

Varios puntos los cubre también, en todo o en parte, una comprobación automática: el 1, el 2, la mitad del 3 que es un `dominio/` con importaciones prohibidas, y el 6, con el linter, `import-linter` y las pruebas de permisos de la base; la mitad del 5 que es un escenario sin test, con el verificador de [ADR-012](adr/20260918-trazabilidad-escenario-test.md); la mitad del 9 que es lo simulado en el `consumido`, con el test de HDU-006 esc. 15 y el arranque que rechaza el adaptador simulado en producción; y el 11, con la prueba de contrato de TKT-061. Si la revisión de la IA y esa comprobación discrepan, manda la comprobación. Para la IA queda lo que exige leer intención: los puntos 4, 7, 8 y 10, y las otras mitades del 3, del 5 y del 9 —una regla escondida en un controlador, un test de rechazo que no afirma el rechazo, un ticket que adelanta la fase 2—.

> **Por qué la IA revisa y no aprueba.** Un agente que escribe el código y otro que lo aprueba forman un circuito sin nadie dentro. La revisión automática existe para que la persona que aprueba llegue al PR con los once puntos ya mirados y dedique su atención al significado, que es lo único que la IA no puede validar.
