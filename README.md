# CIMENTA

**Control Integral de Materiales, Estimaciones, Nómina y Tesorería de obra.**

> Proyecto Final — Máster IA4Devs (LIDR)
> **Entrega 2 en curso** · base: Entrega 1, documentación técnica ajustada tras la revisión del 2026-10-14

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
| 7 | [Especificación de la API](docs/07-especificacion-api.md) · [borrador OpenAPI](docs/api/openapi.yaml) | ✅ Completo · fase 1 | Ajuste 2026-10-15 |
| 8 | [Wireframes](docs/08-wireframes.md) | ✅ Completo · fase 1 | Ajuste 2026-10-15 |

**Documentación transversal**

| Documento | Qué contiene |
|---|---|
| [Glosario del dominio](docs/glosario.md) | Lenguaje ubicuo: *concepto*, *partida*, *destajo*, *explosión de insumos*, *rendimiento* |
| [Convenciones](docs/convenciones.md) | Cómo se documenta y planifica: docs-as-code, SDD, backlog AI-ready, ADRs, estimación |
| [Decisiones de arquitectura](docs/adr/README.md) | 23 ADRs en formato MADR |
| [`llms.txt`](llms.txt) | Mapa del proyecto para agentes de IA |
| [`CLAUDE.md`](CLAUDE.md) | Instrucciones de proyecto para el copiloto: reglas que no se pueden romper, comandos, convenciones |
| [`tools/`](tools/README.md) | Verificadores de la documentación: enlaces, anclas, identificadores, conteos y diagramas |
| [Arranque local](docs/arranque-local.md) | Requisitos, arranque del backend y del frontend, verificadores y lo que todavía no arranca |
| [Estructura del repositorio](docs/convenciones.md#3-estructura-del-repositorio) | Directorios `backend/`, `frontend/`, `tools/`, `sdd/` y `.claude/`, y los archivos de configuración de la raíz |

> **La Entrega 1 está completa y ajustada.** Los cinco pasos están cerrados y el cliente respondió las doce preguntas de la especificación funcional. La revisión de LIDR del **2026-10-14** dejó tres ajustes, atendidos el **2026-10-15** (detalle en [Ajustes tras la revisión](#ajustes-tras-la-revisión-de-la-entrega-1)): el MVP pasa a ser un **hilo vertical** en dos fases, hay especificación de la API con borrador OpenAPI, y los 69 tickets están detallados al mismo nivel, sin ningún bloque pendiente de descomponer. Una revisión posterior de los propios ajustes, el **2026-10-17**, corrigió las inconsistencias que habrían frenado la implementación —el ciclo de dependencias del `consumido`, el destajo contado dos veces, claves entre módulos— y convirtió en preguntas al cliente (`PA-16`…`PA-22`) las reglas que se estaban asumiendo. El cliente respondió esas siete preguntas el mismo día, y sus respuestas ya están propagadas a reglas, modelo, historias, tickets y API. Siguen abiertas cuatro: `PA-12`, `PA-14` y `PA-15`, que no condicionan el diseño, y `PA-23` (modo de redondeo de los importes), que hace falta antes de TKT-016 ([PRD §10](docs/01-descripcion-producto.md#preguntas-abiertas)).

---

## Entrega 2 · Código funcional

La Entrega 2 construye el hilo vertical por tickets con el pipeline SDD. Hoy están archivados los de la fundación: estructura del repositorio, esqueleto del backend, PostgreSQL con identidad, tipos base decimales, contrato de error, autenticación por rol, bitácora y el cliente web (andamiaje, inicio de sesión con armazón por rol, y componentes reutilizables).

**Lo que funciona de extremo a extremo:** iniciar y cerrar sesión. El cliente React llama al API de FastAPI, que valida la contraseña con Argon2id contra PostgreSQL y guarda la sesión en la tabla `sesion`. Tras iniciar sesión aparece el armazón con la navegación del rol. Las pantallas de negocio de la fase 1 llegan con los tickets siguientes, así que sus rutas son marcadores. El límite de intentos y la verificación CSRF (TKT-057) y los usuarios reales (TKT-010) aún no existen: **esta versión es solo para pruebas locales**.

### Cómo ejecutar el proyecto

**Requisitos:** Git, [uv](https://docs.astral.sh/uv/), Node.js 24, Docker Desktop y Chromium o Firefox. El detalle y las versiones están en [`docs/arranque-local.md`](docs/arranque-local.md).

**1. Variables de entorno y base de datos.** Desde la raíz del repositorio:

```bash
cp .env.example .env
docker compose up -d db
```

`.env.example` solo trae valores de desarrollo y las credenciales del usuario de prueba. No hay ningún secreto real en el repositorio, y `.env` está ignorado por git.

**2. Backend.** Desde `backend/`:

```bash
uv sync --locked --python 3.14
uv run --env-file ../.env alembic upgrade head
uv run --env-file ../.env python -m herramientas.contrasenas_roles
```

**3. Sembrar el usuario de prueba.** Desde `backend/`. El script lee las credenciales de `.env` y se niega a escribir si la base no es local.

```bash
PYTHONPATH=. uv run --env-file ../.env python ../frontend/e2e/sembrar_usuario_humo.py
```

En Windows PowerShell:

```powershell
$env:PYTHONPATH = "."; uv run --env-file ../.env python ../frontend/e2e/sembrar_usuario_humo.py
```

Es idempotente: si el usuario ya existe, le restablece la contraseña.

**4. Arrancar el API.** Desde `backend/`, en una terminal que se queda abierta:

```bash
uv run --env-file ../.env fastapi dev
```

Queda en `http://127.0.0.1:8000`, con el contrato publicado en `/docs`.

**5. Arrancar el cliente.** Desde `frontend/`, en otra terminal:

```bash
npm ci
npm run dev
```

**6. Probar.** Abre **`http://localhost:5173`**, con `localhost` y no `127.0.0.1`: la cookie de sesión es `Secure` y solo Chromium y Firefox la aceptan en `http://localhost`.

| Credencial de prueba | Valor |
|---|---|
| Correo | `prueba.compras@cimenta.test` |
| Contraseña | `Cimenta-Prueba-2026` |
| Rol | `COMPRAS` |

Pruebas manuales sugeridas: entrar con esas credenciales y ver el armazón con la navegación de Compras; cerrar sesión; entrar con una contraseña incorrecta y ver el rechazo del formulario; reducir la ventana al ancho de un teléfono y abrir el menú.

### Pruebas automáticas

```bash
# Desde backend/ (requiere Docker en marcha)
uv run pytest

# Desde frontend/
npm test
npm run e2e   # humo de Playwright: inicia sesión, ve el armazón y cierra sesión
```

`npm run e2e` siembra su propio usuario, `humo.compras@cimenta.test`, con una contraseña aleatoria en cada corrida, y no interfiere con el usuario de prueba manual.

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
| **Rama de esta entrega** | `Produccion`, la rama por defecto. El estado revisado el 2026-10-14 queda fijado con la etiqueta `entrega-1`. La antigua rama `Entrega1` está archivada: se quedó atrás de `Produccion` y no contiene `C8` |
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
| Ajuste · API y wireframes | *Plan · contrato* | ¿Qué expone el sistema y cómo se ve? |

### Principios no negociables

Estas son las restricciones que ninguna decisión posterior del proyecto puede romper:

1. **La línea base es inmutable.** El presupuesto de venta se congela al firmar. Toda desviación se mide contra ella; nada la reescribe.
2. **Todo gasto tiene dueño.** El 100 % de las compras se etiqueta al centro de costos de una obra específica. No existe almacén central ni gasto sin obra.
3. **Los límites bloquean, no advierten.** Cuando una operación excede lo presupuestado o un tope configurado, el sistema la detiene y exige autorización explícita; no la deja pasar con una advertencia.
4. **Trazabilidad completa.** Toda autorización, excepción y movimiento de inventario queda registrado con actor, momento y motivo. El sistema debe poder responder *quién autorizó qué y por qué*.
5. **El costo real se conoce hoy, no al cierre.** Cualquier funcionalidad que retrase la visibilidad del costo real por obra contradice el objetivo del producto.
6. **La especificación precede al código.** Ninguna funcionalidad se implementa sin historia de usuario y criterios de aceptación que cubran también los caminos de error, no solo el happy path.

---

## Ajustes tras la revisión de la Entrega 1

La revisión de LIDR del **2026-10-14** dio *luz amarilla: avanzar ajustando*. Cada punto, con dónde quedó atendido:

| Punto de la revisión | Ajuste | Dónde |
|---|---|---|
| **Especificación de la API a medias**: no había listado de endpoints ni borrador | Listado completo por módulo, convenciones y contrato de error, más un borrador OpenAPI 3.1 de la fase 1 que el agente implementa y que CI compara contra el OpenAPI publicado (TKT-061) | [`07-especificacion-api.md`](docs/07-especificacion-api.md) · [`api/openapi.yaml`](docs/api/openapi.yaml) |
| **Tickets a medias**: solo resumen desde HDU-003 y un bloque pendiente | Los 69 tickets tienen el detalle de TKT-011…TKT-024. El bloque pendiente ya no existe: se descompuso en TKT-059 y TKT-063…TKT-069, y en 20 escenarios nuevos | [`05-tickets-trabajo.md`](docs/05-tickets-trabajo.md) · [`04-historias-usuario.md`](docs/04-historias-usuario.md) |
| **Alcance del MVP**: definir un hilo vertical y pasar nómina, destajo y modo sin conexión a una segunda fase con datos simulados | La **fase 1** es el hilo línea base → requisición → bloqueo o autorización → orden → entrada → semáforo. La **fase 2** trae personal, destajo, nómina, captura sin conexión y evidencia. Mientras tanto, la mano de obra y el avance llegan de un adaptador simulado, rotulado y excluido del disponible de `RN-03` | [PRD §7](docs/01-descripcion-producto.md#7-alcance-mvp-y-evolución) · [ADR-017](docs/adr/20261015-fuentes-simuladas-analitica.md) · [plan de sprints](docs/05-tickets-trabajo.md#plan-de-sprints) |
| **Arquitectura**: cerrar un OpenAPI mínimo, alinear las cifras del README y la rama de entrega con la rama por defecto | Las cifras de arriba son las de los documentos. La entrega vive en `Produccion`, la rama por defecto, y el estado revisado queda con la etiqueta `entrega-1` | [Lo entregado, en cifras](#lo-entregado-en-cifras) · [§0.5](#05-url-del-repositorio) |
| **IA en el ciclo**: concretar pruebas, despliegue y mantenimiento | Las seis fases, con lo que hace la IA y quién la verifica: tests escritos antes que el código desde cada escenario; la IA escribe el Dockerfile, el pipeline y los scripts de restauración, y una persona ejecuta el ensayo; revisión automatizada de cada PR con Claude Code, que comenta y no aprueba (TKT-062) | [convenciones §12](docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo) · [stack §10](docs/06-stack-tecnologico.md#10-infraestructura) |
| **Próximos pasos**: tickets del hilo y wireframes | Los tickets de compras, almacén y tablero están detallados, y hay bocetos de las diez pantallas del hilo con sus estados de rechazo | [`08-wireframes.md`](docs/08-wireframes.md) |

## Alcance de la Entrega 1

**Incluye:** ficha del proyecto, descripción general del producto, arquitectura del sistema, modelo de datos, historias de usuario, tickets de trabajo, stack tecnológico y, tras la revisión, especificación de la API y wireframes.

**No incluye:** código, tests ni despliegue. Esta entrega es 100 % documentación.

### Lo entregado, en cifras

| | |
|---|---|
| Reglas de negocio | 25, con trazabilidad a su origen documental |
| Requisitos no funcionales | 19 |
| Preguntas planteadas al cliente | 23 · **19 resueltas**, siete de ellas el 2026-10-17; abiertas `PA-12`, `PA-14`, `PA-15` y `PA-23`, ninguna bloqueante del arranque |
| Invariantes declarados en base de datos | 38 |
| Historias de usuario | 9 · **6 *must-have* (fase 1, el hilo vertical) y 3 *should-have* (fase 2)** · 79 SP |
| Escenarios de aceptación | 162, cerca de la mitad de rechazo, error o borde, cada uno con su fase |
| Tickets de trabajo | 69, todos detallados con criterios técnicos y *non-goals*, en 11 sprints: 7 de fase 1 y 4 de fase 2 |
| Especificación de la API | 70 operaciones de fase 1 en el borrador OpenAPI 3.1, validado; las de fase 2, listadas con su ticket |
| Wireframes | 10 pantallas del hilo vertical |
| Decisiones de arquitectura (ADR) | 21 |

Estas cifras las comprueba [`tools/verificar_docs.py`](tools/README.md) contra los documentos, salvo las de API y wireframes.

> **Sobre el número de historias.** El enunciado pedía entre 3 y 5 *must-have* y 1-2 *should-have*. Se entregan **6 y 3**. La razón está documentada en la [auditoría de suficiencia](docs/04-historias-usuario.md#auditoría-de-suficiencia): el conjunto más pequeño dejaba tres huecos de cadena —nada emitía la orden de compra, nada daba de alta el personal, nada creaba obras ni proveedores— que habrían aparecido como bloqueos en pleno sprint. Si la entrega exige ceñirse al conteo, la vía limpia es bajar HDU-003 y HDU-004 a *should-have*; el producto ya no funcionaría de extremo a extremo con solo las *must*. Tras el corte en fases, las seis *must* son exactamente el hilo vertical de la fase 1: quitar cualquiera lo cortaría.
