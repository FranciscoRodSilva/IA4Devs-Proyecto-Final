---
name: abogado-del-diablo
description: Pasada adversarial sobre una spec o un design de CIMENTA — reta supuestos, marca lo asumido, busca el contraejemplo y el modo de falla. Obligatoria dentro de /sdd-definir y /sdd-disenar; útil ante cualquier artefacto que parezca completo.
---

# Abogado del diablo

Reta el artefacto activo. **No lo reescribe: lo objeta.**

## Por qué existe

Una lista de doce criterios generada de una pasada *parece* exhaustiva y no lo es. El modelo no sabe lo que no sabe del negocio real — la regla que solo conoce quien lleva años en la obra, el archivo que arrastra un `#REF!` desde hace meses. Este paso existe para que algo cuestione el resultado antes de que lo apruebe quien lo escribió.

## Antes de objetar

1. Lee [`sdd/_evolucion.md`](../../../sdd/_evolucion.md): si una fricción ya apareció antes, cítala. El aprendizaje del equipo influye en cada artefacto nuevo.
2. Lee el [glosario](../../../docs/glosario.md). Buena parte de las objeciones reales en este proyecto nacen de usar un término del dominio con el significado que parece tener.

## Qué buscar

**En una spec:**

- Un criterio que solo cubre el camino feliz. **Cada regla implicada necesita su rechazo** — y en CIMENTA el valor está en lo que el sistema rechaza.
- Un rechazo que verifica el estado pero no **el dato**: comprobar `BLOQUEADA` sin comprobar el excedente deja pasar una regla que calcula mal.
- Una afirmación sin evidencia en el PRD, el glosario o los archivos del cliente → márcala `(asumido)`.
- Una regla de negocio que el artefacto da por sentada y **ningún `RN-xx` respalda** → esto no es una objeción, es un `/sdd-escalar`.
- Un Must que esconde dos Must. Señal: su criterio no cabe en un solo escenario, o toca más de dos módulos.
- Un invariante que el cambio rompe y la spec no menciona.
- Concurrencia: ¿qué pasa si dos personas hacen esto a la vez?
- Dinero: ¿dónde cae el centavo al prorratear? ¿Qué escala, qué redondeo?
- Estados nulos: ¿qué muestra esto cuando todavía no hay datos? Si la respuesta es «cero», probablemente debería ser `NULL`.

**En un design:**

- Un objeto nuevo que paró en el peldaño 5 sin haber descartado de verdad los cuatro anteriores. ¿Lo resuelve una restricción de PostgreSQL? ¿Existe ya algo que lo cubre?
- Un paso del orden de implementación **sin verificación**. No es un paso, es un deseo.
- Una frontera entre módulos que el diseño cruza sin decirlo.
- Un plan de pruebas sin caso de rechazo, o sin concurrencia donde hay bloqueo.
- Una migración sin reversa, o destructiva sin plan.
- Falsa agencia: «el sistema valida», «la línea base se protege». ¿Qué función, qué disparador, qué contrato?
- La pregunta incómoda: **¿qué pasa si esto falla a medias?** Transacción abierta, archivo subido sin registro, cola sincronizada a medias.

## Cómo objetar

- **Máximo cinco objeciones por severidad.** Más que eso y nadie las atiende.
- Cada una **accionable**: qué está mal y qué habría que hacer. «Esto es ambiguo» no sirve; «CA-3 no dice qué pasa si `alcance_destajo` es cero → añadir escenario o marcarlo fuera de alcance» sí.
- **Si no hay objeción real, dilo en una línea.** No inventes fricción para parecer riguroso: un abogado del diablo que siempre encuentra cinco cosas se ignora a la tercera vez.

## Salida

```
[abogado del diablo · <spec|design>]

1. [Alta]  <objeción> → <acción>
2. [Media] <objeción> → <acción>
3. [Baja]  <objeción> → <acción>

Veredicto: <N> objeciones · <M> requieren escalar
```

Lo que se hace con cada una se registra en la sección «Pasada adversarial» del artefacto. Las descartadas también, con el motivo — si no, la siguiente pasada las vuelve a levantar.
