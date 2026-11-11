// Generado por `npm run tipos:generar` del OpenAPI que publica FastAPI
// (servidor.fabrica.crear_aplicacion, sin servidor en marcha). No se edita a mano:
// `npm run tipos:verificar` falla si este archivo difiere de lo que se generaría.

export interface paths {
    "/api/v1/sesion/csrf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Obtener Token Csrf
         * @description M1: emite un token nuevo en cada petición, en cookie legible por JavaScript y en el cuerpo.
         */
        get: operations["obtener_token_csrf"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sesion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Obtener Sesion Actual
         * @description M5: la sesión de quien llama, ya validada contra la tabla.
         */
        get: operations["obtener_sesion_actual"];
        put?: never;
        /**
         * Iniciar Sesion
         * @description M2 · RNF-03 · CA-12: abre una sesión, fija la cookie opaca y rota el token CSRF. Sin `max_age`: la caducidad la decide el servidor.
         */
        post: operations["iniciar_sesion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sesion/cierre": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cerrar Sesion
         * @description M4 · CA-12: revoca la sesión (nunca la borra), expira la cookie y rota el token CSRF. Exige el par CSRF (CA-9).
         */
        post: operations["cerrar_sesion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lineas-base/{linea_base_id}/congelacion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Congelar Linea Base
         * @description RN-01: congela la línea base `BORRADOR` y devuelve la línea base ya congelada.
         */
        post: operations["congelar_linea_base"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/obras/{obra_id}/lineas-base": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Lineas Base
         * @description RN-01: las versiones de línea base de la obra, la más reciente primero.
         */
        get: operations["listar_lineas_base"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lineas-base/{linea_base_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Obtener Linea Base
         * @description RN-01: una línea base con sus totales por tipo de partida.
         */
        get: operations["obtener_linea_base"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lineas-base/{linea_base_id}/conceptos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Conceptos Linea Base
         * @description RN-01: una página de los conceptos copiados a la línea base; vacía en `BORRADOR`.
         */
        get: operations["listar_conceptos_linea_base"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lineas-base/{linea_base_id}/explosion": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Obtener Explosion Insumos
         * @description RN-24: la explosión de insumos congelada; vacía en `BORRADOR`.
         */
        get: operations["obtener_explosion_insumos"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lineas-base/{linea_base_id}/presupuesto-control": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Presupuesto Control
         * @description RN-03: una fila por tipo de partida con su venta, su sugerido y su tope; vacía en `BORRADOR`.
         */
        get: operations["listar_presupuesto_control"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Capturar Presupuesto Control
         * @description RN-03, RN-04: captura o recaptura el tope de control y devuelve la fila ya guardada.
         */
        put: operations["capturar_presupuesto_control"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/obras": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Obras
         * @description Las obras, por código, con filtro repetible por estado y paginación.
         */
        get: operations["listar_obras"];
        put?: never;
        /**
         * Crear Obra
         * @description RN-25, PA-02, PA-18: da de alta una obra en `PLANEACION` y la devuelve ya guardada.
         */
        post: operations["crear_obra"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/obras/{obra_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Obtener Obra
         * @description Una obra con su línea base vigente, si la hay.
         */
        get: operations["obtener_obra"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * CapturaPresupuestoControl
         * @description Cuerpo de la captura del tope (RN-03): lo que no declara se ignora.
         */
        CapturaPresupuestoControl: {
            /**
             * Importe Tope
             * Format: decimal
             */
            importe_tope: string;
            /** Motivo */
            motivo?: string | null;
            /**
             * Confirmar Superior A Venta
             * @default false
             */
            confirmar_superior_a_venta: boolean;
        };
        /**
         * ClaveTipoPartida
         * @enum {string}
         */
        ClaveTipoPartida: "MUROS" | "PLAFONES_Y_CAJILLOS" | "ENCHAPES" | "GENERALES";
        /** ConceptoLineaBase */
        ConceptoLineaBase: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Codigo */
            codigo: string;
            /** Descripcion */
            descripcion: string;
            unidad: components["schemas"]["Unidad"];
            /**
             * Cantidad
             * Format: decimal
             */
            cantidad: string;
            /**
             * Precio Unitario
             * Format: decimal
             */
            precio_unitario: string;
            /**
             * Importe
             * Format: decimal
             */
            importe: string;
            /** Nivel */
            nivel: string;
            /** Area */
            area: string;
            tipo_partida: components["schemas"]["TipoPartida"];
        };
        /** CredencialesInicio */
        CredencialesInicio: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Contrasena */
            contrasena: string;
        };
        /**
         * EstadoLineaBase
         * @enum {string}
         */
        EstadoLineaBase: "BORRADOR" | "CONGELADA" | "SUPERSEDIDA";
        /**
         * EstadoObra
         * @enum {string}
         */
        EstadoObra: "PLANEACION" | "ACTIVA" | "SUSPENDIDA" | "CERRADA";
        /** ExplosionInsumos */
        ExplosionInsumos: {
            /**
             * Linea Base Id
             * Format: uuid
             */
            linea_base_id: string;
            /** Renglones */
            renglones: components["schemas"]["RenglonExplosion"][];
            /**
             * Importe Total
             * Format: decimal
             */
            importe_total: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ImporteDeTipoPartida */
        ImporteDeTipoPartida: {
            tipo_partida: components["schemas"]["TipoPartida"];
            /**
             * Importe Venta
             * Format: decimal
             */
            importe_venta: string;
        };
        /** InsumoResumen */
        InsumoResumen: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Codigo */
            codigo: string;
            /** Descripcion */
            descripcion: string;
            unidad: components["schemas"]["Unidad"];
        };
        /** LineaBase */
        LineaBase: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Obra Id
             * Format: uuid
             */
            obra_id: string;
            /** Version */
            version: number;
            estado: components["schemas"]["EstadoLineaBase"];
            /**
             * Importe Venta
             * Format: decimal
             */
            importe_venta: string;
            /** Congelada En */
            congelada_en?: string | null;
            congelada_por?: components["schemas"]["UsuarioResumen"] | null;
            /** Motivo */
            motivo?: string | null;
            /** Por Tipo Partida */
            por_tipo_partida: components["schemas"]["ImporteDeTipoPartida"][];
        };
        /** ListaConceptosLineaBase */
        ListaConceptosLineaBase: {
            /** Elementos */
            elementos: components["schemas"]["ConceptoLineaBase"][];
            paginacion: components["schemas"]["MetaPagina"];
        };
        /** ListaObras */
        ListaObras: {
            /** Elementos */
            elementos: components["schemas"]["Obra"][];
            paginacion: components["schemas"]["MetaPagina"];
        };
        /** MetaPagina */
        MetaPagina: {
            /** Pagina */
            pagina: number;
            /** Tamano Pagina */
            tamano_pagina: number;
            /** Total */
            total: number;
        };
        /**
         * Motivo
         * @description Cuerpo de la congelación: el motivo es obligatorio y se guarda sin espacios en los extremos.
         */
        Motivo: {
            /** Motivo */
            motivo: string;
        };
        /** Obra */
        Obra: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Codigo */
            codigo: string;
            /** Nombre */
            nombre: string;
            /** Domicilio */
            domicilio: string;
            /**
             * Tipo Contrato
             * @enum {string}
             */
            tipo_contrato: "PRECIO_ALZADO_MAXIMO_GARANTIZADO";
            /**
             * Retencion Destajo Pct
             * Format: decimal
             */
            retencion_destajo_pct: string;
            /**
             * Fondo Garantia Pct
             * Format: decimal
             */
            fondo_garantia_pct: string;
            /** Iva Acreditable */
            iva_acreditable: boolean;
            /** Umbral Alerta Pct */
            umbral_alerta_pct: string | null;
            estado: components["schemas"]["EstadoObra"];
            /** Linea Base Vigente Id */
            linea_base_vigente_id: string | null;
            /**
             * Creado En
             * Format: date-time
             */
            creado_en: string;
            /**
             * Actualizado En
             * Format: date-time
             */
            actualizado_en?: string;
        };
        /**
         * ObraNueva
         * @description Cuerpo del alta de obra: lo que no declara (`estado`, `empresa_id`…) se ignora.
         */
        ObraNueva: {
            /** Codigo */
            codigo: string;
            /** Nombre */
            nombre: string;
            /** Domicilio */
            domicilio: string;
            /**
             * Tipo Contrato
             * @constant
             * @enum {string}
             */
            tipo_contrato: "PRECIO_ALZADO_MAXIMO_GARANTIZADO";
            /**
             * Retencion Destajo Pct
             * Format: decimal
             */
            retencion_destajo_pct: string;
            /**
             * Fondo Garantia Pct
             * Format: decimal
             */
            fondo_garantia_pct: string;
            /** Iva Acreditable */
            iva_acreditable: boolean;
            /** Umbral Alerta Pct */
            umbral_alerta_pct?: string | null;
        };
        /** PresupuestoControl */
        PresupuestoControl: {
            tipo_partida: components["schemas"]["TipoPartida"];
            /**
             * Importe Venta
             * Format: decimal
             */
            importe_venta: string;
            /**
             * Importe Sugerido
             * Format: decimal
             */
            importe_sugerido: string;
            /** Importe Tope */
            importe_tope: string | null;
            capturado_por?: components["schemas"]["UsuarioResumen"] | null;
            /** Capturado En */
            capturado_en?: string | null;
            actualizado_por?: components["schemas"]["UsuarioResumen"] | null;
            /** Actualizado En */
            actualizado_en?: string | null;
            /** Motivo Ultimo Cambio */
            motivo_ultimo_cambio?: string | null;
        };
        /** RenglonExplosion */
        RenglonExplosion: {
            tipo_partida: components["schemas"]["TipoPartida"];
            insumo: components["schemas"]["InsumoResumen"];
            /**
             * Cantidad Presupuestada
             * Format: decimal
             */
            cantidad_presupuestada: string;
            /**
             * Rendimiento Congelado
             * Format: decimal
             */
            rendimiento_congelado: string;
            /**
             * Costo Unitario
             * Format: decimal
             */
            costo_unitario: string;
            /**
             * Importe Costo
             * Format: decimal
             */
            importe_costo: string;
        };
        /**
         * Rol
         * @description Los seis roles del PRD §4 (esquema `Rol` del borrador). Un usuario puede acumular varios.
         * @enum {string}
         */
        Rol: "DIRECCION_GENERAL" | "DIRECTOR_PROYECTOS" | "RESIDENTE" | "COMPRAS" | "ALMACEN" | "ADMINISTRACION";
        /** TipoPartida */
        TipoPartida: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            clave: components["schemas"]["ClaveTipoPartida"];
            /** Nombre */
            nombre: string;
        };
        /** TokenCsrf */
        TokenCsrf: {
            /** Token */
            token: string;
        };
        /**
         * Unidad
         * @enum {string}
         */
        Unidad: "M2" | "ML" | "PZA" | "KG" | "CAJA" | "SACO" | "ROLLO" | "JORNAL";
        /** UsuarioActual */
        UsuarioActual: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nombre */
            nombre: string;
            /** Email */
            email: string;
            /** Roles */
            roles: components["schemas"]["Rol"][];
            sesion: components["schemas"]["VigenciaSesion"];
        };
        /**
         * UsuarioResumen
         * @description Lo mínimo de un usuario que otro módulo muestra: su identificador y su nombre visible (P-8).
         *
         *     No expone correo, rol ni sesión. Se publica en `cimenta.identidad.interfaz`.
         */
        UsuarioResumen: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Nombre */
            nombre: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** VigenciaSesion */
        VigenciaSesion: {
            /**
             * Expira En
             * Format: date-time
             */
            expira_en: string;
            /**
             * Expira Por Inactividad En
             * Format: date-time
             */
            expira_por_inactividad_en: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    obtener_token_csrf: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenCsrf"];
                };
            };
        };
    };
    obtener_sesion_actual: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsuarioActual"];
                };
            };
        };
    };
    iniciar_sesion: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CredencialesInicio"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsuarioActual"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cerrar_sesion: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    congelar_linea_base: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                linea_base_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Motivo"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineaBase"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    listar_lineas_base: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                obra_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineaBase"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    obtener_linea_base: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                linea_base_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineaBase"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    listar_conceptos_linea_base: {
        parameters: {
            query?: {
                tipo_partida_id?: string | null;
                nivel?: string | null;
                q?: string | null;
                pagina?: number;
                tamano_pagina?: number;
            };
            header?: never;
            path: {
                linea_base_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ListaConceptosLineaBase"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    obtener_explosion_insumos: {
        parameters: {
            query?: {
                tipo_partida_id?: string | null;
            };
            header?: never;
            path: {
                linea_base_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExplosionInsumos"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    listar_presupuesto_control: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                linea_base_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PresupuestoControl"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    capturar_presupuesto_control: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                linea_base_id: string;
                tipo_partida_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CapturaPresupuestoControl"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PresupuestoControl"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    listar_obras: {
        parameters: {
            query?: {
                estado?: components["schemas"]["EstadoObra"][] | null;
                pagina?: number;
                tamano_pagina?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ListaObras"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    crear_obra: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ObraNueva"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Obra"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    obtener_obra: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                obra_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Obra"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
