# Reglas de negocio en un dominio sin dependencias

## Estado

Aceptado

## Contexto y problema

El PRD define 25 reglas de negocio (`RN-01` … `RN-25`), y el principio no negociable 6 exige que ninguna funcionalidad se implemente sin criterios de aceptación que cubran también los caminos de error. El Paso 4 va a producir escenarios Gherkin donde cada regla tiene, como mínimo, un escenario de éxito y uno de rechazo.

La pregunta es dónde vive el código de esas reglas.

Si una regla se escribe dentro de un controlador HTTP, la única forma de probarla es levantar el servidor y hacer una petición. Eso implica que cada escenario de rechazo arrastra serialización, autenticación, enrutado y base de datos. Los tests se vuelven lentos y frágiles, y —lo más grave— un fallo no distingue entre "la regla está mal" y "algo del entorno falló". Con 25 reglas y varios escenarios cada una, esa fricción decide si la suite se ejecuta o se ignora.

Hay un segundo motivo, específico de cómo se va a construir este proyecto: buena parte del backlog lo van a implementar agentes. Un agente al que se le pide *"modifica RN-03"* necesita poder localizar RN-03. Si la regla está repartida entre un controlador, un servicio y una consulta, el agente reconstruye el comportamiento a partir de fragmentos, y lo que no encuentra lo inventa.

## Opciones consideradas

* Dominio puro: reglas en clases y funciones sin dependencias de framework, ORM ni HTTP
* Reglas en la capa de servicios, con acceso al ORM
* Reglas en los controladores
* Motor de reglas configurable en base de datos

## Decisión

Se elige el **dominio puro**. Cada módulo tiene cuatro capas —`api`, `aplicacion`, `dominio`, `infraestructura`— y la dependencia apunta siempre hacia dentro: la infraestructura conoce al dominio, el dominio no conoce a nadie.

Las reglas viven en `dominio/`, escritas en Python sin importar el framework web ni el ORM. Reciben datos ya cargados y devuelven un resultado; no consultan ni escriben.

```python
# dominio/reglas.py
def evaluar_disponibilidad(presupuestado, consumido, solicitado) -> ResultadoEvaluacion:
    """Implementa RN-03. Sin efectos secundarios."""
```

La capa `aplicacion` es la que abre la transacción, carga los datos, llama a la regla y persiste el resultado. La regla decide; la aplicación orquesta.

**Convención de trazabilidad:** cada regla lleva su identificador `RN-xx` en el docstring y en el nombre del test que la cubre. Eso hace que la correspondencia especificación ↔ código sea localizable con una búsqueda de texto, tanto para una persona como para un agente.

Se descarta el **motor de reglas configurable** por desproporción: 25 reglas conocidas y estables no justifican una capa de configuración, y los motores centralizados acaban siendo el vertedero de toda la lógica que nadie sabe dónde poner.

## Consecuencias

**Positivas**

* Cada escenario Gherkin del Paso 4 se traduce a un test unitario que corre en milisegundos, sin base de datos ni servidor.
* Un fallo de test señala la regla, no el entorno.
* Las reglas se leen sin conocer el framework, lo que las hace revisables por alguien que entienda el negocio pero no el stack.
* Un agente que tiene que tocar `RN-07` encuentra un archivo, no un rastro repartido.

**Negativas o costes aceptados**

* Más archivos y más indirección que poner la condición en el controlador. Es el coste conocido de esta separación y se acepta a cambio de la verificabilidad.
* La capa `aplicacion` tiene que cargar los datos que la regla necesita antes de invocarla, lo que a veces implica una consulta explícita donde el ORM habría hecho una carga perezosa. Es deliberado: las cargas perezosas dentro de una regla la volverían dependiente de la persistencia.

**Cuándo revisar esta decisión**

* Si una regla requiriera consultar datos durante su evaluación —y no solo antes—, habría que revisar si el corte de capas es el correcto para ese caso.
