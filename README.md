# CIMENTA

**Control Integral de Materiales, Estimaciones, Nómina y Tesorería de obra.**

> Proyecto Final — Máster IA4Devs (LIDR)
> **Entrega 1 · Documentación técnica** (sin código)

---

## Índice

| # | Sección | Estado | Paso |
|---|---------|--------|------|
| 0 | [Ficha del proyecto](#0-ficha-del-proyecto) | ✅ Completo | Paso 1 |
| 1 | [Descripción general del producto](docs/01-descripcion-producto.md) | ✅ Completo | Paso 2 |
| 2 | [Arquitectura del sistema](docs/02-arquitectura.md) | ✅ Completo | Paso 3 |
| 3 | [Modelo de datos](docs/03-modelo-datos.md) | ✅ Completo | Paso 3 |
| 4 | [Historias de usuario](docs/04-historias-usuario.md) | ✅ Completo | Paso 4 |
| 5 | [Tickets de trabajo](docs/05-tickets-trabajo.md) | ✅ Completo | Paso 4 |
| 6 | [Stack tecnológico](docs/06-stack-tecnologico.md) | ✅ Completo | Paso 5 |

**Documentación transversal**

| Documento | Qué contiene |
|---|---|
| [Glosario del dominio](docs/glosario.md) | Lenguaje ubicuo: *concepto*, *partida*, *destajo*, *explosión de insumos*, *rendimiento* |
| [Convenciones](docs/convenciones.md) | Cómo se documenta y planifica: docs-as-code, SDD, backlog AI-ready, ADRs, estimación |
| [Decisiones de arquitectura](docs/adr/README.md) | 15 ADRs en formato MADR |
| [`llms.txt`](llms.txt) | Mapa del proyecto para agentes de IA |
| [`CLAUDE.md`](CLAUDE.md) | Instrucciones de proyecto para el copiloto: reglas que no se pueden romper, comandos, convenciones |
| [`tools/`](tools/README.md) | Verificadores de la documentación: enlaces, anclas, identificadores, conteos y diagramas |

> **La Entrega 1 está completa.** Los cinco pasos cerrados y las doce preguntas de la especificación funcional respondidas por el cliente — la última, `PA-13`, confirmó que **en la obra no hay internet** y trajo `RNF-18` y [ADR-015](docs/adr/20260919-captura-diferida-sin-conexion.md). Ese hallazgo deja **un bloque de backlog sin descomponer**, declarado en [`05-tickets-trabajo.md`](docs/05-tickets-trabajo.md#pendiente-de-descomponer--captura-sin-conexión): los escenarios de captura sin conexión, sus tickets y la replanificación de sprints. Sigue abierta `PA-12` —cuánta captura es aceptable rehacer si se pierde la base de datos—, que apareció al declarar los requisitos no funcionales: no condiciona el diseño, sino el precio de la infraestructura, y se responde antes del sprint 7.

---

## 0. Ficha del proyecto

### 0.1. Autor

**Juan Francisco Rodriguez Silva**

### 0.2. Nombre del proyecto

**CIMENTA** — plataforma SaaS de control de costos y operación de obra.

El nombre evoca *cimentar*: poner la base sobre la que se sostiene la obra. Funciona además como acrónimo de los dominios que el sistema gobierna: **C**ontrol **I**ntegral de **M**ateriales, **E**stimaciones, **N**ómina y **T**esorería de obr**A**.

### 0.3. Descripción breve del proyecto

CIMENTA es un SaaS de control de costos y operación para constructoras de subcontrato especializado —tablaroca, plafones y acabados— que trabajan bajo contratos **a precio alzado máximo garantizado**. En ese esquema el ingreso está fijado desde la firma, así que el único margen que la empresa puede defender es el costo; hoy ese costo vive disperso en hojas de Excel y solo se conoce cuando ya se gastó.

El sistema congela el presupuesto de venta como **línea base inmutable**, sobre ella Dirección captura un **presupuesto de control** interno —el costo tope por obra y tipo de partida—, y a partir de ahí gobierna con reglas duras todo el gasto que se imputa a cada obra:

- **Compras** con requisición bloqueada automáticamente cuando excede el volumen o el importe de control del tipo de partida, liberable solo con autorización explícita de Dirección General.
- **Almacén** con entradas validadas contra remisión del proveedor, recepciones parciales con saldo pendiente, traspasos de sobrantes entre obras y baja documentada de mermas.
- **Proveedores** con catálogo, corte semanal de facturación en jueves para pago en sábado, control de anticipos y su amortización, y **tope de deuda por consignación** por proveedor.
- **Subcontratistas** por destajo, con estimación de avance auditada por el residente y validada por el Director de Proyectos, y fondo de garantía del 5 % liberable solo contra área entregada y cobrada.
- **Nómina semanal** por cuadrillas y roles de oficio, con tiempo extra, créditos activos (préstamos e Infonavit) descontados automáticamente y pagos agrupados cuando un líder de cuadrilla cobra por terceros sin cuenta bancaria.
- **Trabajos extra** fuera de contrato, ruteados por el flujo de autorización real de la empresa y costeados aparte sin contaminar la línea base.

Todo desemboca en el entregable central: un tablero de **Costo Real vs. Costo Presupuestado por obra, en tiempo real**, con alerta anticipada cuando un insumo clave sube de precio y recálculo del costo proyectado de la obra restante. Ese dato —hoy inexistente— es lo que permite a la dirección saber si está ganando o perdiendo dinero antes de que se acabe el presupuesto, no después.

### 0.4. URL del proyecto

No aplica en esta entrega. La **Entrega 1 es 100 % documentación**, sin código ni despliegue. La URL de la aplicación desplegada se añadirá en entregas posteriores.

### 0.5. URL del repositorio

| | |
|---|---|
| **Repositorio destino** | https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final |
| **Rama de esta entrega** | `Entrega1` |
| **Ubicación local actual** | `D:\Documentos\LIDR\Proyecto Final` |
| **Estado** | 🟢 Documentación completa y publicada. `Doc de contexto/` queda fuera del repositorio por contener datos personales y precios del cliente — ver [Fuentes de contexto](#fuentes-de-contexto). |

---

## Contexto del cliente

| Campo | Valor |
|---|---|
| **Sector** | Construcción — subcontrato especializado en tablaroca, plafones y acabados |
| **Obras de referencia** | `AP-058-25` · Union Square Fase 2 — y ENITI Torre 5, una segunda obra que valida que el modelo generaliza |
| **Tipo de contrato** | Precio alzado máximo garantizado |
| **Facturación al cliente final** | Estimaciones de avance físico **semanales** |
| **Herramienta actual** | Excel (presupuestos, explosión de insumos, nómina) |
| **Dolor principal** | No existe visibilidad de costo real por obra; las desviaciones se detectan cuando el presupuesto ya se agotó |

### Fuentes de contexto

Toda la especificación se deriva de documentación real del cliente, no de supuestos. Los archivos fuente viven en `Doc de contexto/`, **carpeta que no se versiona**: la nómina lleva nombres y salarios de trabajadores reales, y los presupuestos, precios unitarios de obras en curso. Este repositorio es público y `RNF-07` prohíbe publicarlos. La tabla documenta qué aportó cada uno; los archivos se entregan aparte a quien deba auditar la trazabilidad.

| Archivo | Aporta |
|---|---|
| `Cuestionario_Requerimientos_SaaS_Construccion.docx` | **Fuente principal.** Reglas de negocio, flujos de autorización y dolores declarados por el cliente en 7 bloques temáticos |
| `AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx` | Estructura real de un presupuesto de venta con precios unitarios |
| `AP-058-25 CATALOGO DE CONCEPTOS TABLAROCA fase 2 union.xlsx` | Catálogo de conceptos: jerarquía de desglose de trabajo |
| `AP-058-25 ... EXPLOSION DE INSUMOS ...xlsx` (2 archivos) | Explosión de insumos: base actual para autorizar compras |
| `Presupuesto Base Tablaroca Eniti T5 AP 2.xlsx` | Presupuesto base de otra obra: valida que el modelo generalice |
| `NOMINA FASE II.xlsx` | Estructura real de nómina semanal: roles, cuadrillas, descuentos |

---

## Metodología

El proyecto se desarrolla con **SDD — Spec-Driven Development**: la especificación es el artefacto ejecutable del que se derivan el plan técnico, las tareas y finalmente el código. Nada se implementa sin una especificación previa que lo justifique y sin criterios de aceptación verificables.

Las reglas operativas completas —docs-as-code, backlog AI-ready, formato de criterios de aceptación, DoD por tipo de trabajo, ADRs y estimación— están en [`docs/convenciones.md`](docs/convenciones.md).

Los 5 pasos de la Entrega 1 corresponden a las fases canónicas de SDD:

| Paso de la entrega | Artefacto SDD | Pregunta que responde |
|---|---|---|
| 1. Ficha del proyecto | *Constitution* | ¿Qué principios y restricciones no se negocian? |
| 2. Descripción del producto | **Specify** | ¿Qué y por qué? (nunca el cómo) |
| 3. Arquitectura + Modelo de datos | **Plan** | ¿Cómo se construye? |
| 4. Historias de usuario + Tickets | **Tasks** | ¿En qué orden y con qué criterio de "hecho"? |
| 5. Stack tecnológico | *Plan · decisiones* | ¿Con qué herramientas y por qué esas? |

### Principios no negociables

Estas son las restricciones que ninguna decisión posterior del proyecto puede romper:

1. **La línea base es inmutable.** El presupuesto de venta se congela al firmar. Toda desviación se mide contra ella; nada la reescribe.
2. **Todo gasto tiene dueño.** El 100 % de las compras se etiqueta al centro de costos de una obra específica. No existe almacén central ni gasto sin obra.
3. **Los límites bloquean, no advierten.** Cuando una operación excede lo presupuestado o un tope configurado, el sistema la detiene y exige autorización explícita; no la deja pasar con una advertencia.
4. **Trazabilidad completa.** Toda autorización, excepción y movimiento de inventario queda registrado con actor, momento y motivo. El sistema debe poder responder *quién autorizó qué y por qué*.
5. **El costo real se conoce hoy, no al cierre.** Cualquier funcionalidad que retrase la visibilidad del costo real por obra contradice el objetivo del producto.
6. **La especificación precede al código.** Ninguna funcionalidad se implementa sin historia de usuario y criterios de aceptación que cubran también los caminos de error, no solo el happy path.

---

## Alcance de la Entrega 1

**Incluye:** ficha del proyecto, descripción general del producto, arquitectura del sistema, modelo de datos, historias de usuario, tickets de trabajo y stack tecnológico.

**No incluye:** código, tests ni despliegue. Esta entrega es 100 % documentación.

### Lo entregado, en cifras

| | |
|---|---|
| Reglas de negocio | 25, con trazabilidad a su origen documental |
| Requisitos no funcionales | 18, de los que 14 se verifican en CI |
| Preguntas planteadas al cliente | 13 · **12 resueltas**; `PA-12` abierta, sobre objetivos de recuperación |
| Invariantes declarados en base de datos | 22 |
| Historias de usuario | 9 · **6 *must-have* y 3 *should-have*** |
| Escenarios de aceptación | 137, cerca de la mitad de rechazo, error o borde |
| Tickets de trabajo | 58, en 8 sprints |
| Decisiones de arquitectura (ADR) | 15 |

> **Sobre el número de historias.** El enunciado pedía entre 3 y 5 *must-have* y 1-2 *should-have*. Se entregan **6 y 3**. La razón está documentada en la [auditoría de suficiencia](docs/04-historias-usuario.md#auditoría-de-suficiencia): el conjunto más pequeño dejaba tres huecos de cadena —nada emitía la orden de compra, nada daba de alta el personal, nada creaba obras ni proveedores— que habrían aparecido como bloqueos en pleno sprint. Si la entrega exige ceñirse al conteo, la vía limpia es bajar HDU-003 y HDU-004 a *should-have*; el producto ya no funcionaría de extremo a extremo con solo las *must*.
