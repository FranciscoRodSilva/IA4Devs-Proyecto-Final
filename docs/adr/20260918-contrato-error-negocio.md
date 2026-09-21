# Contrato de error estructurado para reglas de negocio

## Estado

Aceptado

## Contexto y problema

En CIMENTA el valor del sistema está en buena medida en lo que **rechaza**: compras que exceden el presupuesto, recepciones mayores a lo ordenado, pagos sin validación de avance, pedidos que superan el tope de consignación. El rechazo no es un caso excepcional, es una funcionalidad de primera clase.

Eso impone dos exigencias sobre la respuesta HTTP:

**La interfaz tiene que poder explicar por qué.** Cuando Compras ve su requisición bloqueada, necesita ver el disponible real, el excedente y de qué partida se trata. Con un `403` y un mensaje de texto, la interfaz solo puede mostrar la frase; para construir una pantalla útil tendría que interpretar cadenas o volver a pedir los datos.

**El rechazo tiene que ofrecer salida.** RN-03 no rechaza la requisición: la bloquea y abre una solicitud de autorización. La respuesta tiene que comunicar esa bifurcación, no solo la negativa.

Hay una tercera exigencia que viene del Paso 4: los criterios de aceptación en Gherkin van a afirmar cosas como *"la respuesta indica el disponible real y el excedente"*. Sin una forma estable, cada escenario tendría que verificar texto libre.

## Opciones consideradas

* Contrato estructurado propio, uniforme para todas las violaciones de regla
* Códigos HTTP y mensaje de texto
* RFC 9457 (*Problem Details for HTTP APIs*)
* Excepción por regla, cada una con su forma

## Decisión

Se adopta un **contrato estructurado uniforme**, inspirado en RFC 9457 pero con campos propios del dominio:

```json
{
  "tipo": "REGLA_NEGOCIO",
  "regla": "RN-03",
  "mensaje": "La requisición excede el presupuesto de control disponible del tipo de partida MUROS.",
  "detalle": {
    "obra": "AP-058-25 · Union Square F2",
    "tipo_partida": "MUROS",
    "presupuestado": "45000.0000",
    "consumido": "33000.0000",
    "disponible": "12000.0000",
    "solicitado": "15000.0000",
    "excedente": "3000.0000"
  },
  "acciones": [
    { "clave": "SOLICITAR_AUTORIZACION", "metodo": "POST", "ruta": "/requisiciones/1042/autorizacion" }
  ]
}
```

Se devuelve con código `409 Conflict` — el estado actual del recurso impide la operación — reservando `422` para errores de forma de la petición y `403` para falta de permiso. Son tres situaciones distintas y conviene que se distingan.

Cuatro decisiones dentro del contrato:

**`regla` es el identificador del PRD.** El error es trazable desde la respuesta HTTP hasta la especificación y hasta el test que lo cubre. Un agente que recibe este error sabe qué regla leer.

**`detalle` lleva las cifras, no una frase.** La interfaz no recalcula ni interpreta.

**`acciones` convierte el bloqueo en bifurcación.** No es un callejón sin salida: es una negativa con salida documentada, descubrible por el cliente sin conocimiento previo.

**Los importes viajan como cadena.** `45000.0000` y no `45000.0`. Un número JSON pasa por el flotante de doble precisión de JavaScript, y el principio de exactitud decimal no admite que el importe se degrade en el transporte.

Se descarta **RFC 9457 puro** porque su campo `type` es una URI pensada para documentación pública y aquí sobra; se conserva su idea central —error legible por máquina con detalle estructurado— y se adapta al dominio.

Se descarta **una excepción por regla** porque produciría 21 formas distintas que la interfaz tendría que tratar por separado.

## Consecuencias

**Positivas**

* La interfaz construye pantallas de bloqueo útiles a partir de datos, sin interpretar texto.
* Los escenarios Gherkin de rechazo verifican campos concretos, no cadenas.
* Añadir una regla nueva no obliga a tocar el manejo de errores del cliente.
* La trazabilidad regla ↔ especificación ↔ test ↔ respuesta HTTP es directa.

**Negativas o costes aceptados**

* Cada regla tiene que construir su `detalle`, que es trabajo específico por regla y no se puede generalizar.
* El contrato es propio: un integrador externo tendría que aprenderlo. Aceptable, no hay consumidores externos.
* Importes como cadena obligan al cliente a convertir explícitamente. Es deliberado: hace visible una conversión que de otro modo ocurriría en silencio y con pérdida.

**Cuándo revisar esta decisión**

* Si apareciera un consumidor externo de la API, convendría alinear el contrato con RFC 9457 completo para no inventar un estándar propio.
