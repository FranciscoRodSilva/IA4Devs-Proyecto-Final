# Captura diferida sin conexión, acotada a dos flujos de campo

## Estado

Aceptado · **ampliado el 2026-10-01 por [ADR-016](20261001-almacenamiento-de-objetos.md)**, que añade una octava regla: la evidencia fotográfica **no viaja en la cola**. Las siete reglas de abajo siguen vigentes sin cambios.

## Contexto y problema

**En la obra no hay internet** (`PA-13`, respondida el 2026-09-19). Los datos se sincronizan cuando el dispositivo recupera conexión.

Es el supuesto implícito más caro que quedaba en la especificación: toda ella da por hecho que hay servidor al otro lado. Dos de los seis roles trabajan precisamente donde no lo hay:

- El **residente** mide los m² ejecutados de pie en el departamento 312 y recibe material contra remisión.
- **Almacén** da entrada al material en el momento en que llega el camión.

Los otros cuatro —Dirección General, Director de Proyectos, Compras y Administración— operan desde oficina.

El problema no es técnico sino de garantías. El producto existe para **impedir** gasto fuera de presupuesto, y esa garantía se apoya en `RN-03` evaluada con bloqueo de fila contra el estado del servidor ([ADR-004](20260918-bloqueo-pesimista-presupuesto.md)). Un cliente sin conexión no puede evaluar nada: no ve el consumido real, no puede tomar un bloqueo y no sabe qué han capturado los demás. Si se le permitiera decidir, el principio no negociable 3 —*los límites bloquean, no advierten*— quedaría convertido en un aviso que se descubre horas después.

A la vez, negar la captura en campo devuelve al cliente a apuntar en papel y teclear en la oficina, que es el doble trabajo y la pérdida de trazabilidad que el producto existe para eliminar. Y una medición tecleada seis horas más tarde ya no responde *cuándo* se midió.

## Opciones consideradas

* Captura diferida acotada: aplicación web instalable, caché de lectura persistida y cola local solo para los flujos que no consumen presupuesto
* Aplicación nativa o híbrida (Capacitor, React Native) con base de datos local completa
* Local-first con replicación y resolución automática de conflictos (CRDT, ElectricSQL)
* Captura en papel y digitación posterior en oficina

## Decisión

Se elige la **captura diferida acotada**, sobre la misma aplicación de página única de [ADR-011](20260918-frontend-react-spa.md), con service worker, caché de lectura persistida y una cola local.

Siete reglas la definen. Ninguna es opcional: juntas son lo que impide que el modo sin conexión se convierta en una puerta trasera a las reglas de negocio.

**1 · Solo se difieren dos flujos, y son los que no consumen presupuesto.** `avance` de destajo y `entrada_almacen`. Todo lo demás —requisición, autorización, emisión de orden, nómina, congelado de línea base— exige conexión y falla explícitamente sin ella.

La frontera no es arbitraria: es exactamente la línea de `RN-03`. Una requisición capturada sin conexión tendría que darse por permitida sin haber podido evaluarse, y eso es lo que el producto existe para impedir.

**2 · No se autentica sin conexión.** La cola queda atada al usuario de la última sesión válida y **solo sube con una sesión válida en el momento de sincronizar**. Si la sesión caducó o el rol se retiró, la cola no entra y el usuario ve por qué.

Esto preserva `RNF-01` intacto: el permiso se comprueba cuando se escribe en el servidor, que es el único momento en que importa. Sin conexión no se escribe nada en el servidor, por definición.

**3 · El identificador lo genera el cliente, y la sincronización es idempotente.** Las claves primarias ya son UUID generados por la aplicación (modelo de datos §2), así que una fila nace con su identidad definitiva en el dispositivo. El endpoint de sincronización es idempotente sobre ese identificador: reenviar lo mismo tras una conexión que se cortó a medias no duplica nada.

**4 · El servidor no relaja ninguna regla.** Lo encolado entra por **los mismos casos de uso** que lo capturado en línea, con las mismas validaciones, los mismos invariantes y la misma bitácora. Una entrada que excede lo ordenado vuelve con el contrato de error de `RN-07` y su solicitud de autorización, exactamente igual que si se hubiera capturado conectado.

**5 · Los conflictos los resuelve una persona, nunca el sistema.** No hay fusión automática. Un elemento rechazado queda marcado en la cola con el contrato de error que lo explica, y el usuario decide: corregir, descartar o escalar.

**6 · La sincronización es FIFO y se detiene en el primer conflicto.** Continuar tras un rechazo produciría estados dependientes inválidos: una segunda recepción parcial cuyo saldo dependía de la primera se evaluaría contra un saldo que nunca existió.

**7 · Todo dato servido de caché dice de cuándo es.** Una pantalla que muestra el semáforo de hace dos días sin decirlo convierte la métrica `MS-1` —*antigüedad del dato de costo real ≤ 24 h*— en una afirmación falsa en la cara del usuario.

### Por qué no las otras

**La aplicación nativa o híbrida** daría más capacidad sin conexión y acceso a cámara y almacenamiento sin las limitaciones del navegador. Se descarta por el criterio **C4** del [stack §1](../06-stack-tecnologico.md#1-cómo-se-eligió): hay un desarrollador. Añadiría una segunda cadena de compilación, un segundo artefacto, firma y distribución en dos tiendas, y una superficie de despliegue que nadie va a mantener. La aplicación web instalable cubre el caso real —captura de un formulario corto con conexión intermitente— sin nada de eso.

**Local-first con resolución automática** resuelve el problema equivocado. Los CRDT resuelven conflictos de **datos** concurrentes: dos personas editando el mismo texto. Aquí los conflictos son de **regla de negocio** —una entrada que excede lo ordenado, una medición duplicada para la misma área y semana— y ninguna estructura de datos sabe decidir si el proveedor entregó de más o si el residente midió dos veces. Fusionar automáticamente produciría un estado consistente y equivocado, que es peor que un conflicto visible.

**El papel y la digitación posterior** es la opción de coste cero y hay que nombrarla porque es lo que el cliente hace hoy. Se descarta porque conserva los dos defectos que motivan el producto: el dato se captura dos veces, y la hora de la medición se pierde. Si el cliente prefiriera esta vía, `RNF-18` desaparece y esta decisión con él.

## Consecuencias

**Positivas**

* El residente y el almacén capturan donde ocurren los hechos, que es donde el dato es fiable.
* La garantía central del producto no se toca: `RN-03` sigue siendo una evaluación de servidor con bloqueo de fila, sin excepciones ni modos especiales.
* La cola es una lista corta de formularios, no una réplica de la base de datos. No hay esquema que mantener en dos sitios.

**Negativas o costes aceptados**

* **El diseño para móvil deja de estar fuera de alcance.** Quien captura sin conexión lo hace de pie, con una mano, en un departamento en obra gris. El non-goal *"no optimiza para móvil"* de TKT-008 cae con esta decisión, y las pantallas de captura de avance y de recepción pasan a diseñarse para pantalla pequeña.
* **Lo encolado vive solo en el dispositivo.** Si se pierde el teléfono antes de sincronizar, se pierden esas capturas. Se mitiga sincronizando en cuanto hay señal y avisando de la antigüedad de la cola, no se elimina.
* `RNF-15` —semáforo en menos de dos segundos— no aplica a los datos servidos de caché, que responden de inmediato pero pueden ser viejos. La regla 7 es lo que impide que eso engañe.
* El paquete tiene que seguir siendo pequeño. [ADR-011](20260918-frontend-react-spa.md) ya lo anticipaba como disparador de revisión; ahora es una restricción con motivo.
* Hay un service worker que versionar y desplegar. Una versión antigua sirviendo código viejo es un modo de fallo nuevo, y se cierra invalidando la caché al detectar versión nueva del API.

**Cuándo revisar esta decisión**

* Si apareciera la necesidad de **levantar requisiciones sin conexión**. No sería un cambio de frontend: obligaría a reabrir `RN-03` y a decidir qué significa un presupuesto que se puede sobregirar mientras nadie mira. Es una decisión de producto, no de arquitectura.
* Si la obra llegara a tener conexión estable, todo esto se puede desactivar sin tocar el servidor: la cola queda vacía y la sincronización no tiene nada que subir.
