# Metodología · El núcleo de `cimenta-sdd`

> **Qué es este documento.** Las reglas del proceso, no del producto. Lo que todo comando y todo agente del toolkit da por sentado.
>
> **Qué no es.** No repite las reglas de negocio ni las de arquitectura: esas viven en [`docs/`](../docs/) y en [`CLAUDE.md`](../CLAUDE.md). Este documento gobierna *cómo se trabaja*, no *qué se construye*.
>
> El diseño y su porqué: [`00-propuesta-toolkit.md`](00-propuesta-toolkit.md).

---

## 1 · El reparto de papeles

| Papel | Quién | Qué puede hacer |
|---|---|---|
| **Orquestador** | El hilo principal ejecutando un comando `/sdd-*` | Leer el estado, despachar agentes, actualizar artefactos, **preguntarle al usuario** |
| **Agente especializado** | Un subagente de `.claude/agents/` | Una sola cosa, dentro de su alcance, y reportar |
| **Usuario** | La persona | Aprobar el design, resolver lo escalado, aprobar el PR |

**El orquestador es el único que puede preguntar.** Un subagente no tiene `AskUserQuestion`: si encuentra una ambigüedad solo puede devolverla por escrito. Por eso ningún agente decide nada que no le corresponda — devuelve el hallazgo y el orquestador escala.

**Ningún agente aprueba su propio trabajo.** El que escribe no audita; el que audita no corrige; el que corrige vuelve a auditoría.

---

## 2 · Prerrequisito: no se arranca sin documentos

Un ticket no entra a `/sdd-definir` sin estas tres fuentes. No se asume lo que no está escrito.

| Fuente | Condición | Qué aporta |
|---|---|---|
| El ticket en [`docs/05-tickets-trabajo.md`](../docs/05-tickets-trabajo.md) | Siempre | Alcance, non-goals, DoD del tipo |
| La historia en [`docs/04-historias-usuario.md`](../docs/04-historias-usuario.md) | Siempre | Escenarios Gherkin, reglas implicadas |
| El modelo y la arquitectura | Si toca datos o fronteras | Invariantes en riesgo |
| Especificación de interfaz | Si hay pantalla nueva | La produce `disenador-ui-ux` antes de implementar |

Si falta cualquiera de los obligatorios → **STOP**. Se pide, no se rellena. Si el implementador tendría que *adivinar* algo, el ticket está incompleto.

---

## 3 · Los estados

| Estado | Sale hacia | Qué lo dispara | Quién lo mueve |
|---|---|---|---|
| `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` produce `design.md` | Orquestador |
| `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | el usuario aprueba el diseño | **Usuario** |
| `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` produce `impl.md` | Orquestador |
| `EN REVISIÓN` | `LISTO PARA PR` | todas las auditorías `APROBADO` | Auditores |
| `EN REVISIÓN` | `REQUIERE CAMBIOS` | auditoría con hallazgos accionables | Auditores |
| `EN REVISIÓN` | `REQUIERE DECISIÓN` · `RIESGOSO` | bloqueo | Auditores → escala |
| `REQUIERE CAMBIOS` | `EN REVISIÓN` | `corrector-revision` arregla y se reaudita (máx. 3 ciclos) | Orquestador |
| `REQUIERE DECISIÓN` · `RIESGOSO` | estado previo | el usuario responde | **Usuario** |
| `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` produce `delta.md` y abre el PR | Orquestador |

El estado vive en `_index.md`. Quien lo mueve escribe la fila en el Log, con fecha y motivo.

Dos transiciones tienen dueño humano a propósito. Un pipeline donde el agente aprueba su propio diseño no es un pipeline.

---

## 4 · Los veredictos de auditoría

| Veredicto | Significado | Qué pasa después |
|---|---|---|
| `APROBADO` | Sin hallazgos críticos ni mayores, **con evidencia de qué se descartó y por qué** | Avanza |
| `REQUIERE CAMBIOS` | Hallazgos accionables | `corrector-revision`, luego reauditar |
| `RIESGOSO` | Bloqueo: violación de regla innegociable, riesgo de pérdida de datos, o decisión de negocio implícita | **Detiene el flujo entero**, no solo ese paso → `/sdd-escalar` |

**Postura de arranque: `REQUIERE CAMBIOS`.** La carga de la prueba cae sobre el `APROBADO`, no sobre el rechazo. Cero hallazgos en la primera pasada es bandera roja: significa que hay que verificar que el checklist se aplicó punto por punto, no que el código esté limpio.

**Evidencia citable, siempre.** Cada hallazgo nombra archivo y línea —`compras/dominio/disponibilidad.py:42`, no «en la validación»— y el modo de falla concreto, no «podría ser problemático». Un `APROBADO` sin decir qué se revisó y por qué se descartó no es un veredicto, es una opinión.

**Continuidad entre ciclos.** Cada hallazgo lleva identificador (`F001`, `F002`…). Al reauditar, cada uno se clasifica `Resuelto` / `Persiste` / `Nuevo`.

**`corrector-revision` solo actúa sobre `REQUIERE CAMBIOS`.** Nunca sobre `RIESGOSO`.

---

## 5 · La escalera de decisión

Antes de proponer cualquier objeto nuevo en `design.md`, se recorre en orden y **se para en el primer peldaño que resuelve**:

1. **YAGNI** — ¿el ticket lo necesita? Si no es Must ni lo exige un Must, no se construye.
2. **Nativo de la plataforma** — ¿lo resuelve algo que ya ofrecen PostgreSQL, FastAPI, Pydantic, SQLAlchemy o React sin objeto nuevo? Una restricción `CHECK` antes que una validación nueva; un disparador antes que una comprobación en tres sitios.
3. **Reuso** — ¿existe ya una regla, un repositorio, un endpoint, un componente que lo cubre?
4. **Cambio mínimo** — ¿basta modificar mínimamente algo existente?
5. **Solo entonces** — objeto nuevo, lo más pequeño posible.

El peldaño donde paró y por qué se registra en `design.md`.

> **Precedencia dura.** El peldaño 4 **nunca** autoriza tocar un invariante registrado. Si el cambio mínimo choca con uno de los 26 invariantes del modelo de datos o con una de las 16 reglas de `CLAUDE.md`, la escalera se rompe y se **escala**.

---

## 6 · Los criterios de aceptación

Formato Gherkin, en español, directamente traducible a un test.

**La regla dura del proyecto: ningún criterio cubre solo el camino feliz.** Cada regla de negocio implicada necesita su escenario de rechazo. En CIMENTA el valor del sistema está en lo que rechaza — compras que exceden el presupuesto, recepciones mayores a lo ordenado, pagos sin validación de avance. Especificar solo el éxito es no especificar el producto.

**Cómo se generan — patrón «poke-holes», nunca de una pasada.** Una lista de doce criterios generada de golpe *parece* exhaustiva y no lo es: el modelo no sabe lo que no sabe del negocio real.

1. Escribir el camino feliz del Must principal.
2. Con eso como contexto, generar candidatos: casos borde, supuestos implícitos, escenarios faltantes, dependencias, y riesgos de seguridad no mencionados.
3. Filtrar a los reales. Los descartados no se documentan.
4. Todo lo que se apoye en un supuesto sin evidencia se marca **`(asumido)`** y se replica en «Preguntas abiertas». Nunca se asume en silencio dentro de un criterio.

**Trazabilidad.** Cada escenario cita su historia y su número: `HDU-002 esc. 4`. El test que lo cubre lleva ese identificador en el nombre.

---

## 7 · MoSCoW

| Nivel | Regla operativa |
|---|---|
| **Must** | Bloqueante. Cada Must tiene ≥1 criterio `[M]`. `/sdd-revisar` **jamás** aprueba con un Must incumplido |
| **Should** | Esperado pero negociable. Se recorta **vía `/sdd-escalar`**, con la decisión registrada. Nunca en silencio |
| **Could** | Solo si sale gratis. No bloquea ni justifica retraso. Un Could no hecho ni se reporta |
| **Won't** | Fuera de alcance explícito. Si se necesita, es otro ticket |

**Sesgo a recortar, no a expandir.** Generar más texto es barato; cada ítem de más infla el Must. Si algo puede vivir en su propio ticket, no entra aquí ni como Could: se anota en `_index.md` como ticket futuro sugerido.

---

## 8 · Definition of Done por tipo

El tipo del ticket decide qué exige el cierre, además del genérico (criterios cumplidos, tests en verde, auditorías aprobadas, documentación afectada actualizada en el mismo cambio).

| Tipo | Exigencia adicional |
|---|---|
| **Funcionalidad** | Ningún Should o Could implementado sin su criterio correspondiente en la spec |
| **Corrección de error** | El test que reproduce el fallo se commitea **antes** del arreglo. `impl.md` incluye el análisis de por qué se introdujo y si CI podría haberlo detectado. Arreglo mínimo, sin refactores de paso |
| **Refactor** | Prohibido cambiar comportamiento observable. Todo criterio es de regresión. La cobertura no baja. No se mezcla con cambios funcionales |
| **Documentación** | Revisión humana, no solo de agentes. Fragmentos ejecutables. Sin enlaces rotos |
| **Spike** | No cierra con código de producción: cierra con hallazgos, alternativas y recomendación. ADR si la investigación cierra una decisión |

---

## 9 · Cuándo se escala, sin excepción

- Ambigüedad en el alcance, o más de una lectura válida del ticket.
- **Un invariante registrado estorba al cambio pedido.** Eliminarlo o modificarlo nunca es decisión del agente.
- **Aparece una regla de negocio que el PRD no tiene.** No se inventa: se pregunta.
- El alcance crece más de 30 % respecto al design.
- La escalera de decisión obliga a crear un objeto nuevo no trivial que la spec no previó.
- Tres ciclos de corrección sin cerrar hallazgos críticos o mayores.
- Cualquier auditor devuelve `RIESGOSO`.
- Hay decisión de negocio implícita, no técnica.

---

## 10 · Agencia real

Todo artefacto nombra el actor concreto de cada acción. Los modelos asignan verbos humanos a objetos inanimados para no tener que nombrar a nadie, y eso produce specs que no se pueden ejecutar.

| ✗ Falsa agencia | ✓ Actor real |
|---|---|
| «el sistema valida el presupuesto» | «`evaluar_disponibilidad` devuelve `BLOQUEADA` con el excedente» |
| «la línea base se protege» | «el disparador `trg_linea_base_inmutable` rechaza el `UPDATE`» |
| «el avance se calcula» | «`porcentaje_avance` divide entre `alcance_destajo`» |
| «la arquitectura exige» | «`import-linter` falla el contrato `dominio-sin-framework`» |

Si en un criterio, una fila de `design.md` o un aprendizaje un objeto inanimado «hace» algo, se sustituye por la función, el disparador o el contrato exacto que lo ejecuta. Sin actor nombrado, la línea no es accionable.

---

## 11 · Orden de carga del contexto

De lo más estable a lo más volátil. Cargar fuera de alcance es ruido que degrada lo que se produce.

1. `CLAUDE.md` y este documento — invariantes.
2. **Solo** las convenciones del stack en alcance. Un ticket de dominio no carga `conv-frontend-react`.
3. Los artefactos del ticket: `_index.md` siempre; `spec.md` para diseñar; `spec.md` + `design.md` para ejecutar; todo para completar.
4. El mensaje del usuario.

---

## 12 · Artefactos

Un directorio por ticket en `sdd/tickets/tkt-xxx/`, versionado.

| Artefacto | Lo crea | Lo leen | Plantilla |
|---|---|---|---|
| `_index.md` | `/sdd-definir` | todos — es el hub, se lee primero | [plantillas/\_index.md](plantillas/_index.md) |
| `spec.md` | `/sdd-definir` | diseño, implementación, revisión | [plantillas/spec.md](plantillas/spec.md) |
| `design.md` | `/sdd-disenar` | implementación, revisión | [plantillas/design.md](plantillas/design.md) |
| `impl.md` | `/sdd-ejecutar` | revisión, cierre | [plantillas/impl.md](plantillas/impl.md) |
| `delta.md` | `/sdd-completar` | el PR, `meta-sdd` | [plantillas/delta.md](plantillas/delta.md) |

Cada artefacto abre con enlaces de navegación. Rutas relativas, con `/`.

---

## 13 · El catálogo de agentes, y qué hacer cuando uno no existe

El toolkit se construye por fases: los comandos nombran el agente **correcto** para cada paso, aunque todavía no esté escrito. El catálogo completo y su porqué están en [`00-propuesta-toolkit.md` §6](00-propuesta-toolkit.md#6--catálogo-de-agentes).

| Construido | Pendiente |
|---|---|
| `analista-dominio` · `arquitecto-tecnico` · `desarrollador-dominio` · `desarrollador-sql` · `tester-backend` · `auditor-arquitectura` · `auditor-seguridad` · `corrector-revision` · `git-entrega` | `revisor-impacto` · `desarrollador-aplicacion` · `desarrollador-api` · `disenador-ui-ux` · `desarrollador-react` · `tester-api` · `tester-frontend` · `desarrollador-tdd` · `auditor-sql` · `auditor-codigo` · `auditor-docs` · `ingeniero-ci` · `meta-sdd` |

**Regla de sustitución.** Si un comando nombra un agente que aún no existe en `.claude/agents/`, el orquestador:

1. **Hace ese trabajo él mismo**, cargando con la herramienta `Skill` la convención correspondiente —`conv-sql-postgres` para lo que haría `auditor-sql`, `conv-documentacion` para `auditor-docs`, y así.
2. **Lo dice en el reporte**, nombrando el agente ausente. Un paso hecho por sustitución no se presenta como si lo hubiera hecho el especialista.
3. **Anota una fila en [`_evolucion.md`](_evolucion.md)** con tema `agente`. Si el mismo agente ausente aparece tres veces, `meta-sdd` lo levantará como patrón y toca construirlo.

Lo que **nunca** se hace es saltarse el paso. Que `auditor-sql` no exista no convierte en opcional auditar una migración.

## 14 · Enrutamiento de modelo

El modelo se elige por la **naturaleza de la tarea**, no por su importancia. Pagar razonamiento caro donde no hay nada que razonar es desperdicio; ahorrarlo donde sí lo hay sale más caro todavía.

| Agente | Modelo | Esfuerzo | Por qué |
|---|---|---|---|
| `arquitecto-tecnico` | `opus` | alto | Decide la arquitectura del ticket y corre la escalera de decisión. Un error aquí lo paga toda la implementación |
| `auditor-arquitectura` | `opus` | alto | Es el último filtro de las 16 reglas innegociables |
| `auditor-seguridad` | `opus` | alto | Lo más fácil de omitir y lo más caro de remediar en producción |
| `desarrollador-dominio` | `sonnet` | alto | Implementa un diseño ya aprobado: ejecuta, no decide |
| `desarrollador-sql` | `sonnet` | alto | Igual — y el auditor revisa lo que produce |
| `tester-backend` | `sonnet` | alto | Volumen y rigor, sin decisión arquitectónica |
| `analista-dominio` | `sonnet` | medio | Extraer y citar documentación. Es recuperación, no razonamiento |
| `corrector-revision` | `sonnet` | medio | Aplica hallazgos ya diagnosticados por otro |
| `git-entrega` | `haiku` | bajo | Ramas, diff, commit, PR. Mecánico y verificable por comando |

**El principio económico: barato para escribir, caro para auditar.** Los desarrolladores ejecutan un diseño que ya pasó por un modelo fuerte y un gate humano; los auditores son el filtro que decide si algo llega a producción. Invertir al revés —escribir con el modelo caro y auditar con el barato— rompe además la regla de que nadie aprueba su propio trabajo, porque deja la última palabra en el eslabón más débil.

**Cuándo subir un escalón:** un ticket que toca reglas de dinero, concurrencia o permisos justifica subir `desarrollador-dominio` o `desarrollador-sql` a `opus`. Se decide en `/sdd-disenar` y se anota en `design.md`, no se improvisa.

## 15 · Disciplina de contexto

`caveman` comprime **la conversación**: respuestas, reportes de avance, veredictos.

**Nunca comprime lo que se escribe a disco**: `spec.md`, `design.md`, `impl.md`, `delta.md`, ADRs, docstrings, documentación de `docs/` ni mensajes de commit. Eso es el entregable, pasa por `Vale` y lo lee una persona.
