# Despliegue de un solo inquilino con `empresa_id` desde el día uno

## Estado

Aceptado

## Contexto y problema

El proyecto nació del cuestionario *"Requerimientos SaaS de Construcción"*, y la palabra SaaS sugiere que varias constructoras comparten la plataforma. Conviene decidirlo explícitamente porque la multi-tenencia es de las decisiones más caras de retroajustar: afecta a cada tabla, a cada consulta y a todo el modelo de autorización.

Los hechos:

**El cliente es una empresa.** Toda la documentación fuente pertenece a Constructora Celsius. Los archivos llevan literalmente `EMPRESA: Celsius` en su encabezado. No hay segundo cliente ni se ha planteado.

**El alcance del PRD es una empresa con varias obras.** La partición natural de los datos es la **obra**, no la empresa. Casi toda consulta filtra por obra.

**Retroajustar la multi-tenencia es caro; anticiparla del todo también.** Implementar aislamiento real —seguridad a nivel de fila, enrutado por inquilino, gestión de suscripciones— para un solo cliente es construir una infraestructura que nadie usa, y esa infraestructura hay que probarla y mantenerla.

## Opciones consideradas

* Un inquilino por despliegue, con `empresa_id` presente en el esquema
* Multi-tenencia completa desde el principio, con seguridad a nivel de fila
* Sin concepto de empresa: la obra como raíz de todo

## Decisión

Se elige el **despliegue de un solo inquilino con `empresa_id` presente desde el día uno**.

Concretamente:

* `empresa` existe como entidad y `obra.empresa_id` es una clave foránea obligatoria.
* Cada despliegue atiende a **una** empresa. No hay enrutado por inquilino ni aislamiento a nivel de fila.
* El modelo de autorización trabaja sobre roles y obras, no sobre empresas.

La decisión es deliberadamente intermedia. Tener `empresa_id` desde el principio cuesta prácticamente nada —una tabla y una columna— y convierte la futura migración a multi-inquilino en **un cambio de política de acceso, no en una reescritura del esquema**. Sin esa columna, activar la multi-tenencia obligaría a migrar cada tabla, cada consulta y cada índice.

Se descarta **no tener concepto de empresa** porque los propios datos del cliente la nombran, y porque sin ella el camino de migración desaparece.

Se descarta la **multi-tenencia completa** por el principio de no construir hoy lo que no se necesita hoy: aislamiento entre inquilinos, planes, facturación y enrutado son un producto en sí mismo, y hay un solo cliente.

> Conviene nombrarlo sin rodeos: **CIMENTA es hoy un sistema de gestión desplegado para una empresa, no una plataforma multi-inquilino**. El nombre del cuestionario no debería llevar a nadie a suponer lo contrario al leer el código.

## Consecuencias

**Positivas**

* El esquema, las consultas y la autorización se mantienen simples.
* La ruta de migración está preservada: activar la multi-tenencia sería añadir seguridad a nivel de fila sobre `empresa_id` y enrutado, sin tocar el modelo.
* No se prueba ni se mantiene aislamiento que nadie usa.

**Negativas o costes aceptados**

* Atender a una segunda constructora exigiría un despliegue nuevo, con su propia base de datos y su operación.
* `empresa_id` está en el esquema y no se usa para filtrar. Es coste de espacio despreciable y podría confundir a quien lo lea; este ADR es la explicación.

**Cuándo revisar esta decisión**

* En cuanto aparezca una segunda empresa cliente. En ese momento se compara el coste de multiplicar despliegues frente al de implementar aislamiento a nivel de fila; con dos o tres clientes suele ganar el despliegue separado, a partir de ahí no.
