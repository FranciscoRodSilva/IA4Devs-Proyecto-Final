# El límite de intentos se cuenta sobre `intento_acceso`, con una marca de credenciales verificadas

## Estado

Aceptado

## Contexto y problema

`RNF-04` exige limitar los intentos de inicio de sesión. Sin límite, el inicio de sesión es el punto más barato de saturar de todo el sistema, porque cada intento obliga al servidor a verificar una contraseña con Argon2. El límite tiene que bloquear por cuenta y por origen, el bloqueo tiene que ser temporal, y la respuesta no puede revelar qué cuentas existen: el borrador de la API responde igual a una cuenta real que a un correo inexistente, y un bloqueo por un correo inexistente dura lo mismo que uno real.

El estado del límite tiene que sobrevivir a un reinicio del proceso y valer igual para todos los procesos que atienden la aplicación. La tabla `intento_acceso` ya registra cada intento desde TKT-006, incluidos los de correos que no existen.

El problema de fondo es distinguir un fallo de contraseña de un rechazo por bloqueo. Un intento rechazado porque la cuenta está bloqueada no es un fallo de credenciales: si contara, cada intento durante el bloqueo lo alargaría, y quien insiste no sale nunca del bloqueo. Sin una marca en la fila, la tabla no dice cuál de los dos casos es cada intento, y reconstruirlo exige recorrer la cadena de bloqueos anteriores hasta encontrar un hueco de calma. Un atacante que no hace pausas nunca deja ese hueco, así que la lectura crece sin cota con cada intento.

## Opciones consideradas

* **`slowapi` en memoria por origen, y `bloqueado_hasta` por cuenta.** Se descarta. El recuento de `slowapi` vive en la memoria de un proceso: se pierde al reiniciar y no se comparte entre procesos. Además, un correo inexistente no tiene fila de `usuario`, así que no hay dónde guardar su `bloqueado_hasta`, y esa diferencia de trato revela qué cuentas existen.
* **Recuento sobre `intento_acceso` sin columna nueva.** Se descarta. Distinguir un fallo de un rechazo por bloqueo obliga a reconstruir la cadena de bloqueos anteriores, y esa lectura no tiene cota: un atacante que no se detiene hace crecer sin límite lo que cada intento debe leer.
* **Recuento sobre `intento_acceso` con la columna `credenciales_verificadas`.** Se elige.

## Decisión

Se elige el **recuento sobre `intento_acceso` con la columna `credenciales_verificadas`** porque:

* Un fallo es una fila con `exitoso = false` y `credenciales_verificadas = true`. Un rechazo por bloqueo, o por token CSRF ausente en el inicio de sesión, lleva `credenciales_verificadas = false` y nunca cuenta. Con esa marca el cálculo es exacto y lee, como mucho, unas decenas de filas.
* La ventana y la duración del bloqueo son el mismo lapso, `CIMENTA_LIMITE_MINUTOS`, que vale 15 minutos por omisión. Si fueran distintos, los fallos que abrieron un bloqueo seguirían dentro de la ventana cuando el bloqueo venciera, y un solo fallo nuevo volvería a disparar otro. Con el mismo lapso, al vencer el bloqueo todos esos fallos salen de la ventana y el siguiente bloqueo exige fallos nuevos.
* Los umbrales por omisión son 5 fallos por cuenta y 20 por origen, configurables con `CIMENTA_LIMITE_FALLOS_CUENTA` y `CIMENTA_LIMITE_FALLOS_ORIGEN`.
* Un intento contra una cuenta bloqueada se rechaza antes de buscar la credencial. Durante el bloqueo, ni la contraseña correcta entra ni se verifica ningún hash.
* El bloqueo de aviso por correo, con `pg_advisory_xact_lock`, serializa los intentos simultáneos contra una misma cuenta sin una tabla de bloqueos. Funciona igual para un correo inexistente, que no tiene fila de `usuario` sobre la que bloquear.
* El origen no se serializa. Bloquearlo pondría en fila, durante Argon2, a toda una oficina que comparte dirección.

`usuario.bloqueado_hasta` se escribe para las cuentas reales como reflejo del cálculo, y no decide nada.

## Consecuencias

**Positivas**

* La consulta de fallos mira solo las dos ventanas de `2M` hacia atrás, sobre tres índices parciales de `intento_acceso`: fallos verificados por correo, fallos verificados por origen y éxitos por correo. Son parciales porque los rechazos por bloqueo no cuentan y no deben engordar el rango que se lee.
* Un correo inexistente y una cuenta real tienen el mismo cálculo, la misma duración y el mismo cuerpo de `429`.
* El límite no depende de memoria de proceso: sobrevive a reinicios y vale para todos los procesos.

**Negativas o costes aceptados**

* El origen no se serializa. Con peticiones simultáneas desde un mismo origen, el límite de 20 puede superarse en tantos fallos como peticiones haya en vuelo a la vez. Se acepta y queda documentado aquí.
* Detrás de un proxy, todos los clientes comparten origen y el límite por origen deja de distinguirlos. Su tratamiento queda para TKT-058.
* Un bloqueo de aviso que espera más de `lock_timeout` (5 segundos) termina en error del servidor. Se acepta; si aparece en el registro, tendrá su propio ticket.
* La columna no tiene `DEFAULT`: toda inserción en `intento_acceso` tiene que declarar si verificó las credenciales. Es lo buscado, porque ningún intento queda sin clasificar.
* `intento_acceso` crece también con los rechazos anónimos, y un atacante puede alimentarla sin coste. La tabla crece sin purga: el rol de aplicación no puede borrar filas (invariante 20), y cada rechazo anónimo por origen no verificado inserta una fila sin pagar el coste de Argon2. Se mantienen las filas, y una política de retención y purga con un rol distinto del de aplicación es condición de salida a producción (criterio técnico de TKT-058).
* `intento_acceso.origen_ip` y `sesion.origen_ip` guardan la cubeta del origen y no la dirección real: una IPv6 se agrupa por /64 (`2001:db8::/64`), `::ffff:a.b.c.d` se guarda como la IPv4 y un servidor sin cliente (por ejemplo, un socket Unix tras un proxy) usa la cubeta fija `desconocido`. Se pierde precisión forense a cambio de que una persona con un /64 no pueda esquivar el límite rotando de dirección. Quien disponga de un /48 o de un /32 puede repartirse entre cubetas; el límite por cuenta sigue acotándola. Con la cubeta `desconocido`, veinte fallos de cualquier persona bloquean a todas las demás durante la ventana, y es la misma situación de proxy que TKT-058 debe resolver antes de exponer el servicio.
* `bloqueado_hasta` es un reflejo y no una decisión: quien lea esa columna no debe usarla para decidir si una cuenta está bloqueada.

**Cuándo revisar esta decisión**

* Si el límite por origen bloquea a usuarios legítimos de una misma red en producción, se revisa la clave del origen, en TKT-058.
* Si la consulta de fallos aparece en el registro de consultas lentas pese a los tres índices parciales, se revisa el recuento antes de añadir más índices.
* Si se exige un bloqueo que sobreviva a la purga de `intento_acceso`, el mecanismo cambia y esta decisión se sustituye.
