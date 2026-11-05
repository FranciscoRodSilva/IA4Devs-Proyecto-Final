# Registro de decisiones de arquitectura

Decisiones técnicas significativas de CIMENTA, en formato **MADR** (*Markdown Any Decision Records*).

## Criterio para escribir un ADR

> Si alguien llegara hoy al proyecto y viera esto, ¿se preguntaría *"por qué lo hicieron así"*?

Si la respuesta es sí, hay un ADR pendiente. No se documentan todas las decisiones, solo las que alguien podría deshacer o cuestionar por desconocer el contexto.

## Convención de nombres

`YYYYMMDD-slug.md` — fecha, no número secuencial. Es más robusto cuando hay decisiones concurrentes en ramas distintas.

## Estados

`Propuesto` · `Aceptado` · `Rechazado` · `Obsoleto` · `Sustituido por <ADR>`

## Índice

| Fecha | Decisión | Estado | Afecta a |
|---|---|---|---|
| 2026-09-18 | [Monolito modular en lugar de microservicios](20260918-monolito-modular.md) | Aceptado | Todo el backend |
| 2026-09-18 | [PostgreSQL como motor de base de datos](20260918-postgresql.md) | Aceptado | Persistencia |
| 2026-09-18 | [Reglas de negocio en un dominio sin dependencias](20260918-dominio-puro.md) | Aceptado | Todos los módulos |
| 2026-09-18 | [Bloqueo pesimista para la evaluación presupuestal](20260918-bloqueo-pesimista-presupuesto.md) | Aceptado | compras, presupuesto |
| 2026-09-18 | [Libro mayor de solo-anexado para el inventario](20260918-ledger-inventario.md) | Aceptado | almacén, analítica |
| 2026-09-18 | [Línea base como copia inmutable](20260918-snapshot-linea-base.md) | Aceptado | presupuesto |
| 2026-09-18 | [Contrato de error estructurado para reglas de negocio](20260918-contrato-error-negocio.md) | Aceptado | API, SPA |
| 2026-09-18 | [Despliegue de un solo inquilino con `empresa_id`](20260918-despliegue-single-tenant.md) | Aceptado | Persistencia, despliegue |
| 2026-09-18 | [FastAPI como capa HTTP, en lugar de Django](20260918-fastapi.md) | Aceptado | Backend |
| 2026-09-18 | [SQLAlchemy 2.0 con separación dominio/persistencia](20260918-sqlalchemy-data-mapper.md) | Aceptado | Persistencia, dominio |
| 2026-09-18 | [Aplicación de página única con React, sin metaframework](20260918-frontend-react-spa.md) | Aceptado | Frontend, despliegue |
| 2026-09-18 | [Trazabilidad escenario ↔ test por convención verificada](20260918-trazabilidad-escenario-test.md) | Aceptado | Testing, CI |
| 2026-09-19 | [SQLAlchemy síncrono con rutas `def`](20260919-sqlalchemy-sincrono.md) | Aceptado | Backend, persistencia, testing |
| 2026-09-19 | [Sesión con estado en servidor](20260919-sesion-con-estado.md) | Aceptado | identidad, API, SPA |
| 2026-09-19 | [Captura diferida sin conexión, acotada a dos flujos de campo](20260919-captura-diferida-sin-conexion.md) | Aceptado | SPA, avance, almacén · **ampliado por ADR-016** |
| 2026-10-01 | [Almacenamiento de objetos compatible con S3](20261001-almacenamiento-de-objetos.md) | Aceptado | archivos, despliegue, SPA |
| 2026-10-15 | [Fuentes de mano de obra y avance simuladas en la fase 1](20261015-fuentes-simuladas-analitica.md) | Aceptado · temporal | analítica, configuración |
| 2026-10-17 | [Interfaz publicada en un único archivo y fronteras verificadas con import-linter](20261017-interfaz-publicada-y-contrato-de-fronteras.md) | Aceptado | Todo el backend · contrato `dominio-sin-framework` sustituido por ADR-021 |
| 2026-10-17 | [Roles de PostgreSQL y migraciones: quién crea cada rol y quién migra](20261017-roles-postgresql-y-migraciones.md) | Aceptado | Base de datos, migraciones y pruebas de integración |
| 2026-10-19 | [Tipos numéricos base con aritmética exacta y redondeo explícito](20261019-tipos-numericos-base.md) | Aceptado | Todos los módulos |
| 2026-10-19 | [El dominio importa solo la biblioteca estándar y `tipos_base`, verificado con un contrato propio de import-linter](20261019-lista-blanca-del-dominio.md) | Aceptado | Todo el backend · sustituye el contrato `dominio-sin-framework` de ADR-018 |
| 2026-10-20 | [El caso de uso lanza la excepción de las reglas, y el contrato y la raíz de composición viven fuera de `cimenta/`](20261020-contrato-de-error-y-raiz-de-composicion.md) | Aceptado | Todo el backend |
| 2026-10-21 | [Sesión y autorización por rol como dependencias de FastAPI](20261021-sesion-y-autorizacion-por-dependencia.md) | Aceptado | Todo el backend |
| 2026-10-29 | [Política del verificador de escenarios: fase 2, retiro y lista de historias activas](20261029-politica-del-verificador-de-escenarios.md) | Aceptado | Testing, CI · completa [ADR-012](20260918-trazabilidad-escenario-test.md) |
| 2026-10-29 | [Severidad en la auditoría de dependencias: el aviso de GitHub leído en OSV, con fallo cerrado](20261029-severidad-en-la-auditoria-de-dependencias.md) | Aceptado | CI, dependencias |
| 2026-10-29 | [Vale para la prosa en español, con estilo propio mínimo en lugar del estilo Microsoft](20261029-vale-para-prosa-en-espanol.md) | Aceptado | Documentación, CI |
| 2026-10-29 | [Revisión automatizada de pull requests en un flujo aparte, con una única excepción de secretos](20261029-revision-automatizada-de-pr-con-unica-excepcion-de-secretos.md) | Aceptado | CI, seguridad, flujo de revisión |
| 2026-10-30 | [Protección de `Produccion` con una aprobación humana requerida y fusión con omisión de la persona dueña](20261030-proteccion-de-produccion-y-fusion-con-omision.md) | Aceptado | Repositorio, CI, flujo de fusión |
| 2026-10-30 | [El límite de intentos se cuenta sobre `intento_acceso`, con una marca de credenciales verificadas](20261030-limite-de-intentos-sobre-intento-acceso.md) | Aceptado | Identidad, API, base de datos |
| 2026-11-01 | [Los conjuntos cerrados se declaran con `CHECK` con nombre, no con `ENUM`](20261101-catalogos-cerrados-por-check.md) | Aceptado | Base de datos, migraciones, presupuesto · `accion_bitacora` conserva su `ENUM` |
| 2026-11-01 | [La inmutabilidad de la línea base la impone el motor, con disparadores que rechazan con un `SQLSTATE` propio](20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) | Aceptado | Base de datos, migraciones, presupuesto · completa [la copia física](20260918-snapshot-linea-base.md) |
| 2026-11-02 | [Los datos reales de arranque van en la migración, y los sintéticos o con credencial, en una herramienta de base local](20261102-semilla-en-migracion-y-herramienta-local.md) | Aceptado | Base de datos, migraciones, operación · TKT-010 |
| 2026-11-02 | [Lectura posicional del catálogo de conceptos y conversión de `float` con `repr`](20261102-lectura-posicional-del-catalogo.md) | Aceptado | presupuesto · TKT-013 |
| 2026-11-02 | [El destino de prueba es una VPS con un Compose por entorno, un Caddy único y la migración por túnel SSH](20261102-destino-de-prueba-en-vps.md) | Aceptado · temporal | Despliegue, base de datos, operación · TKT-070 |
| 2026-11-03 | [Clave de insumo por descripción normalizada, lectura de APU por rótulos y cuadre por suma](20261103-clave-de-insumo-y-lectura-de-apu.md) | Aceptado | presupuesto · TKT-014b |
| 2026-11-03 | [Explosión por tipo de partida: promedios ponderados y rechazo todo o nada](20261103-explosion-por-tipo-de-partida.md) | Aceptado | presupuesto · TKT-016a |
| 2026-11-05 | [Preparación de importación en una columna `jsonb`](20261105-preparacion-de-importacion-en-jsonb.md) | Aceptado | presupuesto · TKT-015a |
| 2026-11-05 | [Trabajos en dos pasos: el API gobierna el latido, un proceso hijo parsea y un barrido de arranque cierra lo interrumpido](20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md) | Aceptado | presupuesto, servidor, trabajos · TKT-015b · excepción del `lifespan` a [ADR-013](20260919-sqlalchemy-sincrono.md) · retoma la alternativa de [ADR-022](20261020-contrato-de-error-y-raiz-de-composicion.md) |
| 2026-11-05 | [El concepto es único por obra; su cantidad y su precio viven en el concepto de partida](20261105-concepto-unico-y-concepto-de-partida.md) | Aceptado | presupuesto · TKT-072 · completa [la copia física](20260918-snapshot-linea-base.md) |

## Plantilla

Ver [`template.md`](template.md).
