# Sesión con estado en servidor, en lugar de credencial autocontenida

## Estado

Aceptado

## Contexto y problema

[ADR-009](20260918-fastapi.md) aceptó un coste explícito al elegir FastAPI sobre Django: *"hay que construir a mano lo que Django regala: autenticación, gestión de sesión"*. Esta decisión es la primera mitad de esa factura.

El sistema tiene seis roles y uno de ellos —Dirección General— es el único que puede levantar un bloqueo de presupuesto (`RN-03`, `RN-04`). La credencial de sesión es, por tanto, la llave de la operación más consecuente del producto. Y hay una regla que depende por completo de cómo se guarde: [arquitectura §7.1](../02-arquitectura.md#71-autorización) exige que **nadie autorice su propia solicitud** y que el permiso efectivo sea la unión de los roles del usuario. Los roles cambian: alguien entra a Compras, alguien deja de estar en Dirección, alguien se va de la empresa.

La pregunta es dónde vive la verdad sobre quién es alguien y qué puede hacer: en el servidor, o en la credencial que el navegador presenta.

El documento de stack ya descartaba JWT, pero con un argumento que no se sostenía solo: decía que la sesión en servidor *"es más fácil de invalidar"* sin que existiera ninguna tabla donde vivieran esas sesiones. Una cookie firmada sin estado —la opción por omisión de casi todos los frameworks— tiene exactamente el mismo problema de revocación que el JWT que se descartaba por tenerlo.

## Opciones consideradas

* Sesión con estado: tabla `sesion` e identificador opaco en la cookie
* Cookie firmada autocontenida, con los datos del usuario dentro
* JWT en cabecera `Authorization`

## Decisión

Se elige la **sesión con estado**. Existe la tabla `sesion` ([modelo de datos §10](../03-modelo-datos.md#10-identidad-y-auditoría)) y la cookie transporta un identificador opaco contra ella, `HttpOnly`, `Secure` y `SameSite=Lax`.

* **La revocación es inmediata y es el requisito, no un extra.** Desactivar a un usuario, quitarle el rol de Dirección General o cerrarle la sesión surte efecto en la petición siguiente, porque el permiso se resuelve leyendo la base de datos. Con una credencial autocontenida, el usuario conserva lo que la credencial dice que tiene hasta que caduca. Para un permiso que autoriza sobregiros, esa ventana convierte el control en un trámite.
* **Las otras dos opciones son la misma opción.** Un JWT y una cookie firmada difieren en el formato y en dónde viajan; las dos trasladan al cliente la verdad sobre quién es. Revocarlas exige una lista de revocación consultada en cada petición, que es una tabla de sesiones con pasos de más y con una firma que ya no aporta nada.
* **Lo que el JWT compra, aquí no se usa.** Un token sin estado sirve para que varios servicios validen sin consultar a un tercero. Hay un servicio, un despliegue ([ADR-008](20260918-despliegue-single-tenant.md)) y una base de datos que la petición va a consultar de todas formas.
* **La sesión es además un dato de auditoría.** Quién entró, desde dónde y cuándo es información del mismo tipo que la bitácora. Una credencial autocontenida no deja rastro de haber existido.

**`SameSite=Lax` y no `Strict`.** `Strict` protege algo más, a cambio de que un enlace externo a una requisición —un correo, un mensaje— llegue sin cookie y el usuario aparezca desconectado sin entender por qué. La protección contra peticiones cruzadas se resuelve donde corresponde, con un token de doble envío en toda operación que muta estado (`RNF-05`), que es defensa en profundidad y no depende del comportamiento de un navegador concreto.

## Consecuencias

**Positivas**

* Quitar un permiso surte efecto de verdad, que es lo que `RN-04` necesita para que la respuesta a *"quién autorizó esto"* signifique algo.
* Cerrar sesión es escribir una fecha, no esperar una caducidad.
* Queda registro de las sesiones abiertas y de su origen, sin trabajo adicional.

**Negativas o costes aceptados**

* **Una lectura más por petición.** Es una búsqueda por clave primaria en una tabla pequeña, sobre una conexión que la petición ya iba a usar. A decenas de operaciones por hora no es medible.
* **Hay una tabla más que mantener**, con su purga por antigüedad. La purga es un trabajo periódico trivial y las filas se cierran escribiendo `revocada_en`, nunca borrándolas.
* El sistema no puede validar una sesión sin base de datos. Es coherente con un despliegue único: sin base de datos no puede hacer nada más tampoco.

**Cómo se verifica**

* Una prueba desactiva a un usuario que tiene sesión abierta y comprueba que su siguiente petición responde `401`. Es el escenario que distingue esta decisión de las descartadas, y sin él la diferencia solo existe sobre el papel.

**Cuándo revisar esta decisión**

* Si el sistema dejara de ser un despliegue único y varios servicios tuvieran que validar credenciales sin consultar a un tercero.
* Si se incorporara inicio de sesión federado, donde el proveedor de identidad impone su propio formato de credencial.
