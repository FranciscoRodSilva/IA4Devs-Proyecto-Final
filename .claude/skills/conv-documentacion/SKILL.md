---
name: conv-documentacion
description: Convenciones de documentación de CIMENTA — docs-as-code, actualizar en el mismo cambio, identificadores RN/RNF/PA/HDU/TKT/INV que deben existir, ADR en formato MADR, Mermaid, verificadores de CI. Cárgala antes de escribir o auditar documentación.
---

# Convenciones · documentación

> En este proyecto **la documentación es el entregable** y se valida en CI. Un enlace roto rompe el pipeline igual que un test.

## 1 · Las tres condiciones de documentación viva

1. La fuente de verdad está **en el repositorio**. Nada en un sistema externo sin sincronizar.
2. Se actualiza **en el mismo cambio que la provoca**. El PR que cambia comportamiento actualiza la documentación afectada — no en un ticket aparte, no «después».
3. Se valida **automáticamente**. Si se desactualiza, algo en CI se queja.

## 2 · Las cuatro capas, sin mezclar

| Capa | Dónde | Ritmo |
|---|---|---|
| Producto | `docs/01-descripcion-producto.md`, `docs/glosario.md` | Lento |
| Arquitectura | `docs/02-arquitectura.md`, `docs/adr/` | Lento |
| API | OpenAPI generado del código | Medio |
| Código | Docstrings | Rápido |

Una decisión técnica en la capa de producto es un error, igual que una regla de negocio que aparece por primera vez en la de arquitectura. Si al escribir arquitectura surge una regla que el PRD no tiene: **se sube al PRD antes de continuar**, o se escala.

El README es un índice, no un contenedor.

## 3 · Identificadores

`RN-xx` reglas · `RNF-xx` requisitos no funcionales · `PA-xx` preguntas abiertas · `Fx.y` funcionalidades · `HDU-xxx` historias · `TKT-xxx` tickets · `INV-xx` invariantes · ADR por fecha.

**Citar un identificador que no existe rompe el pipeline.** `tools/verificar_docs.py` los comprueba todos, junto con enlaces relativos, anclas internas, el índice de ADRs, los rangos de tickets del plan de sprints, la suma de puntos y la numeración de escenarios.

Antes de dar por terminado cualquier cambio en documentación:

```bash
python tools/verificar_docs.py
python tools/extraer_mermaid.py
```

## 4 · Lo que se asume, se marca

Todo lo que no tiene evidencia clara en la documentación fuente se marca **`(asumido)`** y se recoge en las preguntas abiertas. Nunca se asume en silencio.

**No se inventan reglas de negocio.** Si algo no está en el PRD, se pregunta.

## 5 · Escenarios Gherkin

En español, formato `Dado / Cuando / Entonces`, numerados y contiguos por historia. Cada Definition of Done declara el número real de escenarios de su historia — si no cuadra, es que alguien añadió uno y no actualizó el criterio de cierre, y el verificador lo detecta.

**Camino feliz y al menos un escenario de rechazo por cada regla implicada.** Un escenario como «Escenario: el control de presupuesto funciona» no es un escenario: es un marcador de posición que va a explotar en revisión.

## 6 · ADR

Se escribe uno cuando alguien que llegara hoy se preguntaría *«¿por qué lo hicieron así?»* **y** hubo opciones descartadas. Si no hay alternativa descartada, es un aprendizaje, no un ADR.

- Formato **MADR**: Estado · Contexto y problema · Opciones consideradas · Decisión · Consecuencias.
- Nombre `docs/adr/YYYYMMDD-slug.md`. Fecha, no número secuencial: aguanta mejor decisiones concurrentes en ramas distintas.
- Entrada en el índice `docs/adr/README.md` — el verificador falla si falta.
- No se escribe desde cero: se transcribe a MADR una decisión ya tomada. El razonamiento lo aporta quien decidió.

## 7 · Prosa

- Se valida con `markdownlint-cli2`, `Vale` con estilo Microsoft y `lychee`.
- Voz activa, actor nombrado. Nada de «el sistema valida»: `evaluar_disponibilidad` devuelve `BLOQUEADA`.
- El vocabulario del dominio —*tablaroca*, *destajo*, *perfacinta*, *antepecho*, *cajillo*, *plafón*, *redimix*— está declarado en el vocabulario aceptado de Vale, tomado del [glosario](../../../docs/glosario.md). No se traduce ni se sustituye por sinónimos.
- **`caveman` nunca comprime documentación.** Esto es el entregable y lo lee una persona.

## 8 · Diagramas

Mermaid por defecto, dentro del Markdown. Se validan con `tools/extraer_mermaid.py` — un diagrama con error de sintaxis no se ve como un diagrama roto en GitHub, se ve como un bloque de error en medio del documento.

## 9 · Docstrings

- Cada regla lleva su identificador: `"""Implementa RN-03. Sin efectos secundarios."""`
- `interrogate` vigila que las funciones públicas estén documentadas.
- El docstring dice **qué garantiza y qué asume**, no repite la firma.

## 10 · Al auditar documentación de un cambio

- [ ] La documentación afectada se actualizó en **este mismo** cambio
- [ ] `python tools/verificar_docs.py` en verde
- [ ] Ningún identificador citado que no exista
- [ ] Si el cambio cerró una decisión con alternativas: hay ADR y está en el índice
- [ ] Si el cambio añadió escenarios: el conteo del Definition of Done cuadra
- [ ] Ningún supuesto nuevo sin `(asumido)` y sin su pregunta abierta
- [ ] Los fragmentos de código son ejecutables
