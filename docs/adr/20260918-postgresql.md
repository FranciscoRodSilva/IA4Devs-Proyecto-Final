# PostgreSQL como motor de base de datos

## Estado

Aceptado

## Contexto y problema

Esta decisión se toma en el Paso 3 y no en el Paso 5 —donde vive el resto del stack— porque varias decisiones estructurales de la arquitectura y del modelo de datos se apoyan en garantías concretas del motor. Elegirlo después sería elegirlo tras haberlo asumido.

Lo que el dominio exige del motor:

**Aritmética decimal exacta.** Importes, cantidades y rendimientos no admiten coma flotante. Los archivos del cliente ya arrastran ruido (`2755187.2112`) y el sistema no puede añadir más. Una desviación de redondeo en una explosión de 27 insumos sobre 4,900 conceptos es perfectamente visible.

**Bloqueo de fila explícito.** El principio 3 exige que la evaluación presupuestal sea atómica frente a concurrencia. Hace falta `SELECT … FOR UPDATE`.

**Restricciones declarativas ricas.** Trece invariantes del modelo de datos se declaran en el esquema porque un invariante que solo vive en el código se rompe el día que alguien escribe por otra vía. Hacen falta `CHECK`, índices únicos parciales y restricciones diferidas.

**Permisos por tabla.** La bitácora tiene que ser de solo-anexado, garantizado por el motor y no por disciplina.

## Opciones consideradas

* PostgreSQL
* SQLite
* MySQL / MariaDB
* MongoDB u otro motor documental

## Decisión

Se elige **PostgreSQL** porque:

* `NUMERIC` es decimal exacto de precisión arbitraria, no una aproximación.
* `SELECT … FOR UPDATE` da el bloqueo pesimista que necesita la evaluación presupuestal.
* Soporta `CHECK`, índices únicos parciales, restricciones diferidas y disparadores: los trece invariantes se declaran, no se confían.
* Los permisos por tabla permiten conceder `INSERT`/`SELECT` sobre la bitácora sin `UPDATE` ni `DELETE`.
* `JSONB` cubre los campos genuinamente sin esquema —contexto de autorizaciones, estados anterior y posterior de la bitácora— sin renunciar a lo relacional en el resto.
* Si el tablero llegara a necesitarlas, las vistas materializadas están disponibles sin cambiar de motor.

**SQLite** se descarta pese a su comodidad: su tipado dinámico no ofrece decimal exacto —almacena como texto o flotante según el caso— y su modelo de escritura única no acompaña el requisito de concurrencia, aunque hoy la carga sea baja. El riesgo no es el volumen, es la corrupción silenciosa de importes.

**MySQL** tiene `DECIMAL` correcto pero un soporte de `CHECK` históricamente irregular y sin índices únicos parciales, que son dos de los mecanismos con los que se declaran los invariantes.

**Un motor documental** se descarta por la naturaleza del dominio: es intensamente relacional —jerarquía de cinco niveles, explosión de insumos, amortización de anticipos— y transaccional. Sería trabajar contra el modelo.

## Consecuencias

**Positivas**

* Los invariantes de negocio críticos son inviolables desde cualquier vía de acceso.
* La consulta del semáforo se resuelve con SQL estándar y CTEs, sin capa de agregación adicional.
* Ecosistema maduro en Python, sea cual sea el ORM que elija el Paso 5.

**Negativas o costes aceptados**

* Requiere un servidor de base de datos, frente a un archivo local. Coste operativo real pero pequeño.
* El desarrollo local necesita PostgreSQL disponible; no se usará SQLite en tests para "ir más rápido", porque probaría contra garantías distintas de las de producción.

**Cuándo revisar esta decisión**

* No se prevé. Un cambio de motor implicaría reescribir los invariantes declarativos, que son parte del diseño y no un detalle de implementación.
