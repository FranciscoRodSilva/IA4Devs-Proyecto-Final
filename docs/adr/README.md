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

## Plantilla

Ver [`template.md`](template.md).
