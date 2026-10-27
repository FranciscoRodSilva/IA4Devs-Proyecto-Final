// PROVISIONAL (TKT-008, PA-T1). Tipos del contrato de error generados del borrador
// docs/api/openapi.yaml, porque el OpenAPI que publica FastAPI todavía no declara los
// esquemas de error. Se retira cuando el servidor los publique con responses= en cada
// ruta (ticket futuro, antes de TKT-061). Generado por `npm run tipos:generar`.
// No se edita a mano: `npm run tipos:verificar` lo detecta.

export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** @description Salida documentada de un rechazo. El cliente la pinta como botón sin conocerla de antemano. **Se filtran por los roles de quien llama**: nunca se ofrece una acción que le respondería `403`. Por eso `acciones` puede llegar vacía aunque el rechazo tenga salida para otro rol. Excepción: `REINTENTAR` de una `CONCURRENCIA` no se filtra, porque repite la operación que quien llama acaba de invocar y que `api/` ya autorizó por su rol (TKT-005). */
        Accion: {
            /**
             * @description `VER_SOLICITUD_AUTORIZACION` (`GET` a la solicitud que nació con el bloqueo de `RN-03`) y `SOLICITAR_AUTORIZACION` (`POST /solicitudes-autorizacion`, solo tras el rechazo de `RN-07`) son claves distintas.
             * @example VER_SOLICITUD_AUTORIZACION
             * @example SOLICITAR_AUTORIZACION
             * @example REPROGRAMAR
             * @example REINTENTAR
             */
            clave: string;
            /** @enum {string} */
            metodo: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
            /** @description Ruta absoluta del API, con el prefijo `/api/v1`. */
            ruta: string;
        };
        /**
         * Format: decimal
         * @description Cantidad con signo, `NUMERIC(14,4)`. Solo los movimientos del libro mayor llevan signo.
         * @example -20.0000
         */
        Cantidad: string;
        /**
         * Format: decimal
         * @example 0.0000
         */
        CantidadNoNegativa: string;
        /**
         * @description **Catálogo cerrado** (TKT-005). Un `409` que no viola una `RN-xx` lleva uno de estos códigos, nunca una regla inventada. Ampliarlo exige cambiar este borrador en el mismo PR que añade el caso que lo produce.
         * @enum {string}
         */
        CodigoConflicto: "CODIGO_OBRA_DUPLICADO" | "RFC_DUPLICADO" | "FOLIO_REMISION_DUPLICADO" | "OBRA_CON_HISTORIAL" | "ESTADO_NO_PERMITE_OPERACION" | "IMPORTACION_EN_CURSO" | "IMPORTACION_CON_ERRORES" | "REEMPLAZO_NO_CONFIRMADO" | "SIN_LINEA_BASE_CONGELADA" | "SIN_PRESUPUESTO_CONTROL" | "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR" | "YA_RESUELTA" | "SOLICITUD_SIN_EFECTO" | "SOLICITUD_NO_APLICABLE" | "ORDEN_YA_EMITIDA" | "ORDEN_YA_CERRADA" | "ORDEN_NO_ADMITE_ENTRADAS" | "SIN_SALDO_PENDIENTE" | "PROVEEDOR_INACTIVO" | "PROVEEDOR_CON_ORDENES_ABIERTAS" | "ARCHIVO_NO_SUBIDO" | "ARCHIVO_NO_DISPONIBLE" | "ARCHIVO_TAMANO_DISTINTO" | "ARCHIVO_HASH_DISTINTO" | "ARCHIVO_TIPO_NO_PERMITIDO" | "ARCHIVO_CADUCADO";
        /** @description `consumido = requisiciones_vivas + comprometido + ejercido` (modelo de datos §15). Solo fuentes `REAL`. */
        ConsumidoDesglose: {
            requisiciones_vivas: components["schemas"]["Importe"];
            comprometido: components["schemas"]["Importe"];
            ejercido: components["schemas"]["Importe"];
            total: components["schemas"]["Importe"];
        };
        /** @description Detalle de `RN-07`. */
        DetalleExcedeOrdenado: {
            orden_compra_id: components["schemas"]["Uuid"];
            folio_orden: string;
            renglones: {
                orden_compra_renglon_id: components["schemas"]["Uuid"];
                insumo: string;
                unidad?: components["schemas"]["Unidad"];
                cantidad_ordenada: components["schemas"]["CantidadNoNegativa"];
                cantidad_recibida: components["schemas"]["CantidadNoNegativa"];
                saldo_pendiente: components["schemas"]["CantidadNoNegativa"];
                cantidad_entrante: components["schemas"]["CantidadNoNegativa"];
                excedente: components["schemas"]["CantidadNoNegativa"];
            }[];
        };
        /** @description Detalle de `RN-03`, por importe y, si aplica, por insumo. */
        DetalleExcedePresupuesto: {
            /**
             * @description Código y nombre para mostrar.
             * @example AP-058-25 · Union Square F2
             */
            obra: string;
            /** @example MUROS */
            tipo_partida: string;
            presupuestado?: components["schemas"]["Importe"];
            consumido?: components["schemas"]["Importe"];
            consumido_desglose?: components["schemas"]["ConsumidoDesglose"];
            disponible: components["schemas"]["Importe"];
            solicitado: components["schemas"]["Importe"];
            excedente: components["schemas"]["Importe"];
            /**
             * @description Solo excesos reales. La falta de línea base o de tope no es `RN-03`: es `CONFLICTO` `SIN_LINEA_BASE_CONGELADA` o `SIN_PRESUPUESTO_CONTROL`.
             * @enum {string}
             */
            causa?: "EXCEDE_IMPORTE" | "EXCEDE_VOLUMEN" | "INSUMO_NO_PRESUPUESTADO";
            insumos?: {
                insumo_id: components["schemas"]["Uuid"];
                insumo: string;
                unidad: components["schemas"]["Unidad"];
                /** @description `false` si el insumo no está en la explosión de la partida: disponible cero, no ilimitado (HDU-002 esc. 8). */
                presupuestado_en_partida: boolean;
                cantidad_presupuestada: components["schemas"]["CantidadNoNegativa"];
                cantidad_consumida: components["schemas"]["CantidadNoNegativa"];
                cantidad_disponible: components["schemas"]["Cantidad"];
                cantidad_solicitada: components["schemas"]["CantidadNoNegativa"];
                excedente: components["schemas"]["CantidadNoNegativa"];
            }[];
            requisicion_id?: components["schemas"]["Uuid"];
            folio?: string;
            solicitud_autorizacion_id?: components["schemas"]["Uuid"];
        };
        /** @description Cifras y referencias del rechazo. Importes y cantidades siempre como cadena. */
        DetalleGenerico: {
            [key: string]: unknown;
        };
        /** @description Detalle de `RN-06`. */
        DetalleOrdenConSaldo: {
            orden_compra_id: components["schemas"]["Uuid"];
            folio_orden: string;
            estado: components["schemas"]["EstadoOrdenCompra"];
            renglones_con_saldo: {
                orden_compra_renglon_id: components["schemas"]["Uuid"];
                insumo: string;
                saldo_pendiente: components["schemas"]["CantidadNoNegativa"];
                fecha_compromiso: components["schemas"]["Fecha"];
            }[];
        };
        /** @description Venció `lock_timeout` o `statement_timeout` (`RNF-16`). Código `409`, con cabecera `Retry-After` y la acción `REINTENTAR`, que no se filtra por los roles de quien llama: repite la operación ya autorizada. Nada se persistió. No lleva `regla`: no se violó ninguna, y asentarlo como `RN-03` contaminaría la consulta de excepciones. */
        ErrorConcurrencia: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            tipo: "CONCURRENCIA";
            /** @enum {string} */
            codigo: "BLOQUEO_VENCIDO" | "TIEMPO_EJECUCION_VENCIDO";
            mensaje: string;
            detalle: {
                espera_maxima_ms?: number;
            };
            acciones: components["schemas"]["Accion"][];
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Cualquier `409`. El cliente lo distingue por `tipo`. */
        ErrorConflicto: components["schemas"]["ErrorReglaNegocio"] | components["schemas"]["ErrorConflictoEstado"] | components["schemas"]["ErrorConcurrencia"];
        /** @description Conflicto de estado o de unicidad que no es violación de una regla `RN-xx`: código duplicado, transición inválida, solicitud ya resuelta, archivo que no coincide. Código `409`. Misma forma que `REGLA_NEGOCIO` con `codigo` en lugar de `regla`. */
        ErrorConflictoEstado: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            tipo: "CONFLICTO";
            codigo: components["schemas"]["CodigoConflicto"];
            mensaje: string;
            detalle: components["schemas"]["DetalleGenerico"];
            acciones: components["schemas"]["Accion"][];
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Código `429`. Misma respuesta por cuenta que por origen, para no revelar qué cuentas existen. */
        ErrorLimiteIntentos: {
            /**
             * @constant
             * @enum {string}
             */
            tipo: "LIMITE_INTENTOS";
            mensaje: string;
            reintentar_en_s: number;
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Código `404`. */
        ErrorNoEncontrado: {
            /**
             * @constant
             * @enum {string}
             */
            tipo: "NO_ENCONTRADO";
            /** @example requisicion */
            recurso: string;
            mensaje: string;
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Falta de permiso. Código `403`. **Nunca incluye cifras del recurso** (HDU-006 esc. 12). Con usuario autenticado se asienta en la bitácora como `DENEGAR`, en una transacción propia porque no hay cambio que acompañar. Las denegaciones anónimas —CSRF o credenciales en el inicio de sesión— van a `intento_acceso` y al registro técnico, no a la bitácora. */
        ErrorPermiso: {
            /**
             * @constant
             * @enum {string}
             */
            tipo: "PERMISO";
            /**
             * @description `ROL_INSUFICIENTE` lo decide `api/`; `AUTO_RESOLUCION` —nadie resuelve lo suyo— y `NO_ES_SOLICITANTE` los decide `dominio/`; `ORIGEN_NO_VERIFICADO` es el token CSRF ausente o distinto.
             * @enum {string}
             */
            motivo: "ROL_INSUFICIENTE" | "AUTO_RESOLUCION" | "NO_ES_SOLICITANTE" | "ORIGEN_NO_VERIFICADO";
            mensaje: string;
            roles_requeridos: components["schemas"]["Rol"][];
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Violación de una regla del PRD. Código `409`. Es exactamente el contrato de arquitectura §7.3 más `correlacion_id` (`RNF-13`). */
        ErrorReglaNegocio: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            tipo: "REGLA_NEGOCIO";
            regla: components["schemas"]["ReglaId"];
            mensaje: string;
            /** @description Las cifras del rechazo. Todo importe y cantidad como cadena. */
            detalle: components["schemas"]["DetalleExcedePresupuesto"] | components["schemas"]["DetalleExcedeOrdenado"] | components["schemas"]["DetalleOrdenConSaldo"] | components["schemas"]["DetalleGenerico"];
            acciones: components["schemas"]["Accion"][];
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Código `401`. */
        ErrorSesion: {
            /**
             * @constant
             * @enum {string}
             */
            tipo: "SESION";
            /**
             * @description `CREDENCIALES_INVALIDAS` no distingue correo inexistente de contraseña errónea.
             * @enum {string}
             */
            motivo: "SIN_SESION" | "SESION_CADUCADA" | "SESION_REVOCADA" | "CREDENCIALES_INVALIDAS";
            mensaje: string;
            correlacion_id: components["schemas"]["Uuid"];
        };
        /** @description Error de forma. Código `422`. Sustituye al cuerpo por omisión de FastAPI (`detail` con `loc`), que no cumple el contrato (TKT-005). */
        ErrorValidacion: {
            /**
             * @constant
             * @enum {string}
             */
            tipo: "VALIDACION";
            mensaje: string;
            errores: {
                /** @description Ruta del campo en el cuerpo o en la consulta, p. ej. `renglones[1].cantidad`. */
                campo: string;
                /** @enum {string} */
                codigo: "OBLIGATORIO" | "FORMATO" | "NO_POSITIVO" | "FUERA_DE_RANGO" | "FECHA_ANTERIOR_A_VIGENTE" | "VALOR_NO_PERMITIDO" | "DEMASIADO_LARGO";
                mensaje: string;
                regla?: components["schemas"]["ReglaId"];
            }[];
            correlacion_id: components["schemas"]["Uuid"];
        };
        /**
         * @description Derivado de las cantidades, salvo `CANCELADA`.
         * @enum {string}
         */
        EstadoOrdenCompra: "ABIERTA" | "PARCIAL" | "CERRADA" | "CANCELADA";
        /**
         * Format: date
         * @description Fecha de negocio sin hora (remisión, compromiso de entrega). Es `DATE` en el esquema.
         * @example 2026-10-22
         */
        Fecha: string;
        /**
         * Format: decimal
         * @description Importe en pesos, `NUMERIC(18,4)`. Cadena decimal, nunca número JSON. Puede ser negativo (ajustes, desviación). El servidor responde siempre con cuatro decimales.
         * @example 45000.0000
         * @example -2000.0000
         */
        Importe: string;
        /**
         * @description Identificador de regla del PRD §8.
         * @example RN-03
         */
        ReglaId: string;
        /**
         * @description Los seis roles del PRD §4. Un usuario puede acumular varios.
         * @enum {string}
         */
        Rol: "DIRECCION_GENERAL" | "DIRECTOR_PROYECTOS" | "RESIDENTE" | "COMPRAS" | "ALMACEN" | "ADMINISTRACION";
        /** @enum {string} */
        Unidad: "M2" | "ML" | "PZA" | "KG" | "CAJA" | "SACO" | "ROLLO" | "JORNAL";
        /**
         * Format: uuid
         * @example 7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e
         */
        Uuid: string;
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
