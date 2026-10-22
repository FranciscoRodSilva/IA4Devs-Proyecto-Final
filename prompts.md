> Detalla en esta sección los prompts principales utilizados durante la creación del proyecto, que justifiquen el uso de asistentes de código en todas las fases del ciclo de vida del desarrollo. Esperamos un máximo de 3 por sección, principalmente los de creación inicial o  los de corrección o adición de funcionalidades que consideres más relevantes.
Puedes añadir adicionalmente la conversación completa como link o archivo adjunto si así lo consideras


## Índice

1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)
7. [Pull requests](#7-pull-requests)
8. [Entrega 2 · Código funcional](#8-entrega-2--código-funcional)

---

## 1. Descripción general del producto

**Prompt 1:** *(Gemini 3.1 Pro)*

```
Ayudame a generar las pregusntas correctas a un cliente para poder crear un sistema SaaS con el que pueda constriur desde 0 con Spec-Driven Development, debemos hacer las pregusntas a un cliente el cual tiene una constructora y no tiene un sistema para poder gestionarlo, como dato el cliente se mostro interesando en un sistema que le ofrecieron llamado "Diazar Business Intelligence" debemos poder ofreserle algo muy similar y tratar que con estas preguntas podamos lograr capturar todo lo que vaya a cubrir su necesidad.
```

*Este prompt generó el cuestionario (`Cuestionario_Requerimientos_SaaS_Construccion.docx`) que después se le envió realmente al cliente de la constructora. Sus respuestas son la fuente principal de todo el proyecto.*

**Prompt 1.1:** *(Gemini 3.1 Pro)*

```
Asume el rol de Product Owner experto en sistemas SaaS , queremos que se definan los objetivos y prioridades del proyecto así como las funciones prioritarias para el negocio, dicho esto necesito que revises a detalle el documento que se generó del cuestionario para la entrevista con dueño del negocio y me digas si es suficiente y cubre lo indispensable para iniciar el proyecto desde 0.
```

**Prompt 2:** *(Claude Code · Opus 5 · sesión "SaaS construcción: documentación técnica")*

```
@"D:\Documentos\Pako\Cuestionario_Requerimientos_SaaS_Construccion.docx"
Vamos a desarrollar un producto de software de inicio a fin, integrando IA en todas las fases: desde la idea y documentación, hasta el código, testing y despliegue. El objetivo es que apliques todo lo aprendido en el máster en un proyecto real y funcional.

Primero iremos por la Entrega 1 que es la Documentación técnica: Ficha del proyecto, descripción, arquitectura, modelo de datos, historias de usuario, tickets de trabajo.

El archivo principal de contexto es el cuestionario que se le hizo al cliente para ver sus necesidades que es Cuestionario_Requerimientos_SaaS_Construccion.docx

Qué incluye:

1.-Ficha del proyecto: nombre, descripción, URL del repo o ZIP (Lo que se genere del proyecto lo vamos a guardar en la siguiente ruta "D:\Documentos\LIDR\Proyecto Final" de manera local por el momento posteriormente una vez que se termine con todos los pasos aquí descritos y que todo este en orden se subirá a "https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final.git" creando una rama llamada Entrega1)

2.-Descripción general del producto: objetivo, características, funcionalidades (Para esto te hare llegar unos archivos para que los analices muy bien y veas lo que se nos pide estos archivos los vas a encontrar en la siguiente dirección de la carpeta "D:\Documentos\LIDR\Proyecto Final\Doc de contexto")

3.-Arquitectura del sistema y modelo de datos (Una vez hecho el análisis del contexto del paso anterior hay que proponer cual es la mejor arquitectura para backend, frontend y base de datos que vayamos a usar en el proyecto, ten en cuenta que se tiene preferencia de usar React para el front y se quiere trabajar con python)

4.-Historias de usuario y tickets de trabajo (Una vez que tengamos completo el paso 2 basado en esto ayúdame a planificar entre 3 y 5 historias de usuario must-have (las imprescindibles) y 1-2 should-have las imprescindibles, también quiero que mee crees los tickets de trabajo realmente necesarios para iniciar el proyecto desde 0 para esto hay que apoyarse en la documentación cuando lleguemos a esta paso solicitame los archivos para que obtengas el contexto de como vamos a trabajar)

5.-Stack tecnológico elegido (En base a los pasos anteriores especialmente el 3 hay que proponer cual es la mejor Stack tecnológico que se puede utilizar para crear el proyecto)

Qué NO incluye todavía:
*Código. Esta entrega es 100% documentación.
*No propongas criterios de aceptación y que solo se acepte si cumple con los criterios descritos y que siempre sean los green no solo propangas el happy path se deben evaluar los errores.

Vamos a ir paso por paso cuando completes un paso dime revisamos los resultados y después te dire como y cuando pasar al siguiente paso.

Ten en cuenta que para el sistema queremos usar la metodología de SDD Spec-Driven Development.
```

*Primer prompt de la sesión de Claude Code. Fija el alcance completo de la Entrega 1 (los 5 pasos: ficha, descripción, arquitectura+modelo de datos, historias+tickets, stack) y la metodología SDD. De aquí salió el `README.md` con la ficha del proyecto.*

**Prompt 3:** *(Claude Code · Opus 5 · misma sesión)*

```
@"...Módulo 4\📄 La planificación cambia nuevos paradigmas 🔴.docx" @"...Módulo 4\📄 Anatomía de un backlog AI-ready 🔴.docx" @"...Módulo 4\📄 Estimación asistida por IA 🔴.docx" @"...Módulo 4\📄 PM tools + IA en 2026 🔴.docx" @"...Módulo 4\📄 Planificación ágil continua 🔴.docx" @"...Módulo 5\Documentación efectiva con IA.docx" @"...Módulo 5\📄 El déficit documental en la era IA 🔴.docx" @"...Módulo 5\📄 Arquitectura documentada ADRs + diagramas C4 con IA 🔴.docx" @"...Módulo 5\📄 Documentación de API y código 🔴.docx" @"...Módulo 5\📄 Testing de documentación en CI y docs para LLMs 🔴.docx"
continua con el paso 2, te voy a pasar archivos de contexto de como se va a manejar la documentacion y planificacion para que se tenga el contexto de como se quiere  trabajar en el sistema para tener todo preparado
```

*Arranca el Paso 2 aportando el material de los Módulos 4 y 5 del máster (planificación, backlog AI-ready, ADRs, C4). Generó `docs/01-descripcion-producto.md` (PRD), `docs/glosario.md` y `docs/convenciones.md`.*

---

## 2. Arquitectura del Sistema

### **2.1. Diagrama de arquitectura:**

**Prompt 1:** *(Claude Code · Opus 5 · sesión "SaaS construcción: documentación técnica")*

```
continua con el paso 3
```

*No fueron necesarios mas Prompt debido a que le habai especificado todo en los pasos anteriores*

*Confirmación breve tras cerrar el Paso 2. Dispara `docs/02-arquitectura.md` completo: drivers arquitectónicos, las tres vistas C4, contextos delimitados y los tres diagramas de secuencia de flujos clave.*

### **2.2. Descripción de componentes principales:**

**Prompt 1:** el mismo de 2.1 — *"continua con el paso 3"*, que define los 9 contextos delimitados, sus capas y sus dependencias.

**Prompt 2:** *(Claude Code · sesión "SaaS construcción: documentación técnica" · auditoría final)*

```
Revisa que todo este correcto y congruente en cuanto a lo que se refiere a la entrega que este todo completo y no contenga errores
```

*Auditoría de cierre de toda la Entrega 1. Sobre arquitectura, encontró y corrigió dos contradicciones reales: el flujo seguía describiendo el control presupuestal por partida (invalidado por `PA-01`, que lo movió a obra + tipo de partida) y sumaba la nómina al "consumido" por partida (invalidado por `PA-10`).*

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

*No hubo un prompt dedicado en exclusiva a la estructura de ficheros. La estructura del backend (`backend/cimenta/<modulo>/api · aplicacion · dominio · infraestructura`) se definió como parte del Paso 5 (stack tecnológico) — ver el Prompt 1 de la sección 2.4, que es el mismo que disparó esa parte del trabajo.*

### **2.4. Infraestructura y despliegue**

**Prompt 1:** *(Claude Code · sesión "SaaS construcción: documentación técnica")*

```
continua con el paso 5
```

*Arranca el Paso 5: stack tecnológico, `CLAUDE.md`, estructura de carpetas del backend y la sección de stack de `llms.txt`.*

**Prompt 2:** *(Claude Code · sesión "Revisión del stack tecnológico")*

```
Ahora vamos a revisar el stack tecnologico documentado para el proyecto es el mejor que se epuede usar ? tiene buena quimica trabajndo en conjunto y nos  aportara una aplicacion segura y robusta ?
```

*Arranca una sesión dedicada a auditar el stack ya elegido antes de dar la Entrega 1 por cerrada: compatibilidad entre piezas, seguridad y robustez.*

**Prompt 3:** *(Claude Code · sesión "CIMENTA Entrega 1 auditoría")*

```
No hay internet en la obra una vez qeu haya se deben actualizar los datos , actualiza ADR-011
```

*Introduce el requisito de captura sin conexión en obra. Generó `RNF-18`, el ADR-015 (captura diferida sin conexión) y la actualización del ADR-011.*

### **2.5. Seguridad**

**Prompt 1:** *(Claude Code · sesión "Revisión del stack tecnológico")*

```
aplica todo, empieza por la sección de seguridad
```

*Orden de aplicar las correcciones detectadas en la revisión de stack, empezando por seguridad. De aquí salió la sección de seguridad del PRD, el ADR de sesión con estado en servidor (ADR-014) y el endurecimiento de la autenticación (Argon2id, CSRF por doble envío).*

### **2.6. Tests**

*Esta entrega es 100% documentación: no hay tests de código todavía. Lo más cercano son los verificadores de documentación en CI (`tools/verificar_docs.py`, `tools/extraer_mermaid.py`), que nacieron del mismo prompt de auditoría citado en 2.2 (*"Revisa que todo este correcto y congruente..."*) al detectar que esas comprobaciones solo vivían en el scratchpad de la sesión y había que llevarlas al repositorio.*

---

### 3. Modelo de Datos

**Prompt 1:** *(Claude Code · sesión "SaaS construcción: documentación técnica")*

```
PA-01 es (b), PA-02 son dos cosas distintas, PA-03  se captura, PA-04 La nomina se hace corte los dias jueves se paga lo trabajado del dia viernes al jueves aun que se trabajen en obras distintas si se tiene que tner cuando y donde se trabajo el empleado, PA-05 es intencional porque no lo pueden acreditar y para ustedes es costo real esto puede pasar solo een algunas obras, PA-06 b, PA-07 se pone como parcialmente entregada y se reprograma el faltante hasta que la entreguen, PA-08 Es la c
```

*Respuestas del cliente a las 8 preguntas abiertas del PRD (`PA-01`…`PA-08`). Es el cambio de mayor impacto en el modelo de datos: introdujo la entidad `jornada`, dividió `explosion_partida` en `explosion_presupuesto`/`presupuesto_control`, movió el control presupuestal a nivel obra y elevó los invariantes de 14 a 18.*

**Prompt 2:** *(Claude Code · misma sesión)*

```
PA-10 si  y PA-11 basta por el momento
```

*Cierra las dos últimas preguntas abiertas del modelo (nómina sin repartir a partida; rendimiento observado por obra e insumo), dejando las 11 preguntas del PRD resueltas.*

**Prompt 3:** *(Claude Code · sesión "CIMENTA Entrega 1 auditoría")*

```
P1.a  ( A )
P1.b  ( B )              ← solo si P1.a = A
P1.c  ( A )                            ← confirmar con Dirección
P2    ( A )
P2.duda-cliente: conceptos no-M2 dentro de una partida → ( aceptable )
P5    ( C )
P6    ( B )
P6.política: subir un tope ya capturado → ( permitido con autorización )
P3    ( confirmo: personal)
P4    ( A )
```

*Segunda ronda de preguntas abiertas, ya en la auditoría de cierre. Estas decisiones (P1-P6) redefinieron la fórmula de `consumido`, el cálculo de avance físico, `m2_contrato` y la corrección de `presupuesto_control`, con impacto directo en tablas, invariantes y CTEs del modelo de datos.*

---

### 4. Especificación de la API

*En esta entrega (Entrega 1, 100% documentación, sin código ni despliegue) no se generó una especificación de API independiente — no hay OpenAPI/Swagger ni un documento de contrato de endpoints dedicado. Los contratos de API (incluido el contrato de error estructurado que usan todos los rechazos de reglas de negocio) se diseñaron como parte de `docs/02-arquitectura.md` §7.3, y el framework (FastAPI) quedó decidido en `docs/06-stack-tecnologico.md`. Cuando exista una entrega con código, esta sección se completará con los prompts que generen la especificación de la API en firme.*

---

### 5. Historias de Usuario

**Prompt 1:** *(Claude Code · sesión "SaaS construcción: documentación técnica")*

```
continua con el paso 4,  -Ejemplo de historias en gherkin:
Título de la Historia de Usuario: HDU-001 - Captura de personal

*Como* dueño *quiero* poder dar de alta, baja o realizar algún cambio en el personal que contrato *para* que pueda tener una base de datos de mi personal actualizada y fiable.

**Escenario 1: Apertura de formulario Empleados**
- **Dado que** el usuario quiere hacer alguna alta en el personal
- **Cuando** hace clic en el botón de +
- **Entonces** se abre la interfaz del formulario para llenar los datos del nuevo personal
- **Y** se posiciona el cursor sobre el primer campo a capturar.

**Escenario 2: Selección de puestos**
- **Dado que** el usuario quiere asignar un puesto
- **Cuando** hace click en el dropdown de puestos
- **Entonces** se abre el listado de los puestos activos previamente capturados en el formulario de puestos
- **Y** al seleccionar uno asignar al usuario.
y usa el contexto de los archivos para ver como crear los TKTs y lo demas
```

*Arranca el Paso 4, fijando el formato Gherkin en español (`HDU-XXX`, Dado que/Cuando/Entonces/Y) con un ejemplo real. Generó simultáneamente `docs/04-historias-usuario.md` y `docs/05-tickets-trabajo.md` (ver sección 6).*

**Prompt 2:** *(Claude Code · misma sesión)*

```
Antes de continuar con el paso 5 dale una revisada mas a fondo para las historias de usaurio que sean lo mas realistas y suficientes para cubrir necesidsades reales
```

*Pide una auditoría de suficiencia antes de cerrar. Encontró tres huecos de cadena (nada emitía la orden de compra, nada daba de alta personal, nada creaba obras/proveedores) y pasó de 7 a 9 historias (89 escenarios).*

**Prompt 3:** *(Claude Code · misma sesión)*

```
Revisaste si hay Historias Relacionadas y si las hay que realmente lo esten ?
```

*El borrador no tenía sección de historias relacionadas. Esta pregunta hizo construir 20 relaciones tipadas con evidencia, y detectó un riesgo real de doble conteo de mano de obra que derivó en la nueva regla `RN-22`.*

---

### 6. Tickets de Trabajo

**Prompt 1:** el mismo de la sección 5 — *"continua con el paso 4, [...] y usa el contexto de los archivos para ver como crear los TKTs y lo demas"*, que pide explícitamente generar los tickets junto con las historias. Disparó `docs/05-tickets-trabajo.md`.

**Prompt 2:** *(Claude Code · sesión "Revisión del stack tecnológico")*

```
confirma el RPO/RTO con Dirección General y asigna TKT-058 a un sprint
```

*Cierra un punto pendiente de planificación de sprints: fija el objetivo de recuperación ante desastres y ubica el ticket correspondiente en el sprint 7.*

**Prompt 3:** *(Claude Code · sesión "CIMENTA Entrega 1 auditoría")*

```
para sesion aparte pero dejalo documentado como pendiente
```

*Decide dejar fuera de esta sesión la descomposición de los tickets de captura sin conexión (surgida de `RNF-18`/ADR-015), pero exige documentarlo. Creó la sección "Pendiente de descomponer · captura sin conexión" en el backlog.*

---

### 7. Pull Requests

**Prompt 1:** *(Claude Code · sesión "Publicar en repositorio GitHub")*

```
Puedes publicar en GitHub en el Repositorio destino
```

*Primer prompt de la sesión de publicación. El asistente detecta que el repositorio destino es público y que `Doc de contexto/` contiene datos sensibles reales (nómina con nombres y salarios, presupuestos con precios unitarios de obra), y antes de hacer push resuelve cómo excluirla (`.gitignore`) sin perder la trazabilidad documental.*

**Prompt 2:** *(Claude Code · misma sesión)*

```
Crear PR y hacer Merge con produccion
```

*Con la rama `Entrega1` ya subida, pide crear el pull request hacia la rama por defecto (`Produccion`) y fusionarlo. Con este prompt se crea y se mergea el PR #1.*

---

## 8. Entrega 2 · Código funcional

*Prompts de la Entrega 2, todos ejecutados desde Claude Code (Sonnet 5.5). Recogen el feedback de la Entrega 1, la construcción del toolkit SDD y el arranque del primer ticket.*

**Prompt 1:** *(Claude Code · Sonnet 5.5 · ajustes tras el feedback de la Entrega 1)*

```
Hemos recibido feedback de la primer entrega y vamos a realizar los ajustes y recomendaciones que se nos dieron para poder implementar de manera optima la entrega 2 para ello primero debemos ajustar los siguientes puntos:

1.En cuanto a la documentación en la parte de Especificación de la API se nos dice lo siguiente: Se anuncia que el OpenAPI se generará desde el código, pero aún no hay un listado de
endpoints ni un borrador de la especificación. Hay que mejorar esto para generar un listado de propuesta de los endpoints necesarios para la implementación. En la parte de Tickets de trabajo se nos dice lo siguiente: Muy bien detallados para la fundación y las dos primeras historias; para el resto solo hay un
resumen y queda un bloque declarado como pendiente. Hay que detallar todos los Tickets de la misma manera que se hicieron en las dos primeras historias.

2.El problema y el alcance del MVP, se nos menciona que el caso de uso está clarísimo. Sí, y el alcance es el punto a vigilar. Has sabido recortar bien: dejaste fuera tesorería, facturación, el
portal para proveedores y, para la versión 1.1, los traspasos, el recálculo por alza de precio y los
anticipos. Aun así, el MVP que describes sigue incluyendo compras, almacén, destajo, la nómina
completa con créditos y pagos agrupados, el tablero y el expediente documental. Tu propio plan de
sprints lo reconoce: el sexto sprint va sobrecargado y el trabajo sin conexión aún no está estimado.
Te propongo definir un hilo vertical que sea indiscutiblemente tu MVP: importar la línea base, levantar
una requisición, que se bloquee o se autorice, recibir el material y ver el semáforo. La nómina, el
destajo con su fondo de garantía y el trabajo sin conexión pasarían a una segunda fase, con datos
simulados mientras tanto. Tus reglas de dominio ya están escritas, así que añadirlas después sale
barato. Hay que aplicar la propuesta que se nos hizo.

3.La arquitectura los ajustes que se nos mencionan aquí son los siguientes: 
Cierra una especificación OpenAPI mínima (o su borrador) con los endpoints del hilo vertical, porque
será el mejor contexto para tu agente al escribir código. Y alinea las cifras del README.md (decisiones,
requisitos, invariantes) con las de los demás documentos, y la rama de la entrega con la rama por
defecto del repositorio, porque a quien revisa le generan dudas.

4.La IA en tu ciclo de desarrollo, en esta parte se nos menciona lo siguiente:
Prioriza dejar bien definidas la implementación y las pruebas, y añade una frase concreta sobre el uso de
IA en despliegue y mantenimiento. Con eso llegarás con holgura a la meta de al menos cuatro de las seis
fases.

-Pruebas: Cada escenario de las historias debe tener su test y
un verificador en CI lo comprueba. Es muy buen
puente para que la IA genere los tests.
-Despliegue: Tienes planteados el CI, el respaldo y la
observabilidad, pero falta decir dónde entra la IA
(por ejemplo, en el pipeline, el Docker o los scripts
de restauración).
-Mantenimiento: Docs-as-code, verificadores propios y revisión
humana de los PR del agente. Falta concretar la
revisión automatizada de pull requests.

5.Próximos pasos: Estos son los próximos pasos que se nos recomiendan antes de empezar la entrega 2

1. Define el hilo vertical del MVP — elige el recorrido que quieres demostrar (línea base, requisición,
bloqueo, entrada de material, semáforo) y mueve la nómina, el destajo y el modo sin conexión a una
segunda fase, con datos simulados.

2. Añade una especificación OpenAPI mínima — enumera los endpoints de ese hilo con sus esquemas
y su contrato de error; tu agente la usará como contrato al generar el backend y los tipos del cliente.

3. Termina los tickets del hilo y añade wireframes — detalla los tickets de compras, almacén y tablero
al mismo nivel que los dos primeros, y esboza las pantallas clave. Eso adelanta el diseño y la
experiencia de usuario de la entrega final.

El archivo que nos dieron fue el adjunto te lo paso para que tengas mas claro los puntos y los objetivos de lo que queremos lograr con estos ajustes y optimizaciones.

Si tienes alguna duda o sugerencia o algo no te quedo claro no dudes en preguntar.
```

*Aplica el feedback de la Entrega 1: define el hilo vertical del MVP (línea base → requisición → bloqueo o autorización → entrada de material → semáforo), mueve nómina, destajo y captura sin conexión a la fase 2, y pide el borrador OpenAPI, los tickets detallados y los wireframes.*

**Prompt 2:** *(Claude Code · Sonnet 5.5 · diseño del toolkit SDD)*

```
Ahora vamos a revisar lo de la metodología SDD y si es necesaria la instalación de OpenSpec para poder llevar esto acabo y personalizarla conforme a lo que el proyecto necesita y se lo mejor para este o si podemos crear el propio nuestro ya que se requiere que tenga exista un Orquestador que es el que va desplegar los agentes que deben entrar a trabajar y se pueda decidir si se puede trabajar las tareas en loop o debe ser de una por una, este debe ser el workflow que se debe manejar por medio de comandos en el pipeline desde el inicio hasta el fin:

1.Antes que nada se debe definir y este lo que debe de hacer es:
-Escribe la spec: user story, alcance, criterios de aceptación
-Existe por que sin spec, cada quien interpreta el requerimiento distinto

2.Despues diseñar ya que el spec se apruebe lo que debe hacer es:
-Genera el plan técnico: qué tocar, en qué orden, cómo verificar
-Existe por que fuerza pensar antes de codear; evita retrabajo

3.Posterior mente ejecutar tras el design aprobado lo que debe de hacer es:
-Implementa el ticket y genera los tests en paralelo
-Existe por que Los tests nacen con el código; después nadie los escribe

4.Despues revisar Tras la implementación lo que debe de hacer es:
-Verifica spec cumplida, corre tests, audita código y seguridad
-Existe por que Nadie aprueba su propio código

5.Y por ultimo completar Tras revisión aprobada lo que debe de hacer es:
-Genera el delta, archiva aprendizajes y prepara el PR
-Existe por que Sin cierre formal, el conocimiento del ticket desaparece


Tambien debe ser capaz de tener comandos de soporte y control los cuales son:

1.El avance el cual se puede ejecutar en cualquier momento y lo que debe de hacer es:
-Reporte de progreso: qué está hecho y qué queda
-Existe por que da Visibilidad sin leer todos los artefactos

2.escalar cuando o Si el alcance creció o hay riesgo y lo que debe de hacer es:
-Pausa el ticket y pide decisión antes de continuar
-Existe por que El desarrollador no decide lo que no le corresponde

La creación de agentes deben ser agentes que sean especializados en cada una de las tareas que el orquestador va asignar, aquí hay que explorar según lo que requiere el proyecto y que agentes especializados se deben crear debe haber distintos agentes tanto para front, backend, web, UI/UX desing, SecDevOps, auditores y de git, por ejemplo en el back end debe haber:
-Desarrollador SQL que cuando se necesite crear código en la base de datos Escribe SPs, vistas, tablas e índices en Postgres SQL.
-Desarrollador API que debe Implementar controllers, endpoints, DTOs en el Cliente de API seleccionado
-Tester SQL que prueba el código que genero el desarrollador que todo este correcto y funcione
-Testter API que prueba el código que genero el desarrollador que todo este correcto y funcione
-Auditor de código SQL que Audita: idempotencia, TRY/CATCH, permisos, índices y que todo este dentro de las convenciones definidas para la genera ración de código SQL en postgres
-Auditor de seguridad, experto en Revisa OWASP: injection, IDOR, secrets, auth en Endpoints o SQL con input externo
-Corrector de Revision si es que los auditores devuelve REQUIERE CAMBIOS el cual aplica los fixes señalados y devuelve el código a re-auditoría, Sin corrector, el ciclo auditoría→fix se rompe
Y revisar si se necesita alguno mas o se este omitiendo alguno que lo requiera el proyecto.
-Git back que Al iniciar o cerrar con backend/SQL debe Crea/verifica ramas, commit y push en los repos API y SQL 
Para el Frontend deben existir por ejemplo:
-Desarrollador React especializado en Vite el cual Implementa componentes, hooks, stores Zustand y queries TanStack siguiendo las reglas del proyecto.
-Desarrollador de diseño UI/UX que según las convenciones establecidas para la mejoría de código genere el desing que debe implementar junto con el Desarrollador React
-Tester frontend que Después de implementar frontend este debe Generar tests Vitest de componente y specs Playwright E2E
-Auditor de código JS/TS/Python Audita seguridad, contratos, patrones y casos borde
-Git Front que Al iniciar o cerrar con frontend haga la Creación/verificación ramas, commit y push en el repo React
Para los Tester debe haber un desarrollador de TDD que cuando el Guard este activo lo que debe hacer es Ciclo Red / Green / Refactor: test que falla → implementa mínimo → refactoriza
-Al cierre es decir cuando se complete de debe tener un agente de meta-sdd que debe agrupar observaciones de _sdd_evolution.md por cluster de Tema; detecta patrones ≥ 3 y propone mejoras al toolkit

Estos son solo unos ejemplos de algunos de los agentes que mínimo deben crearse pero se debe explorar muy bien si hace falta alguno mas para poder implementarlos en donde se tengan las convenciones de las mejores practicas de como se debe trabajar y como cada uno de los agentes especializados sean los mejores en su campo, el primer paso antes de generar los agentes debemos identificar e investigar las mejores convenciones de generar el código que sea un código refactorizado y que sea  lo mas optimo y eficiente posible para cada uno de los lenguajes que se van a utilizar en el proyecto una vez que tengas las mejores practicas y mejores convenciones según lo que se encuentre de información en la red se debe arrojar un listado de los agentes que se necesitan en el proyecto y el o los orquestadores para poder ponerlos a trabajar de una manera armoniosa y en sincronía.

Se deben investigar skills que nos puedan ser útiles para el desarrollo como por ejemplo una que se debe instar y de debe activar en cada interacción debe ser caveman
```

*Define el toolkit SDD propio del proyecto (en lugar de instalar OpenSpec): el pipeline de cinco fases con sus dos comandos de control, el orquestador, los agentes especializados por capa, las convenciones por stack y la skill `caveman` activa en cada turno.*

**Prompt 3:** *(Claude Code · Sonnet 5.5 · arranque del primer ticket de código)*

```
Entrega 2: Código funcional: Backend, frontend y BD conectados. El flujo principal operativo (aunque no esté 100% completo primero la fase 1).
Qué incluye:
-Scaffolds de tu arquitectura (frontend, backend y base de datos conectados).
-El flujo principal del proyecto casi completo.
-Primeras funcionalidades operativas.

Empieza por definir el TKT-001 /sdd-definir TKT-001
```

*Abre la Entrega 2 y lanza la primera fase del pipeline SDD (`/sdd-definir`) sobre el ticket de fundación TKT-001, con el objetivo de dejar frontend, backend y base de datos conectados.*

