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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ClaveTipoPartida
         * @enum {string}
         */
        ClaveTipoPartida: "MUROS" | "PLAFONES_Y_CAJILLOS" | "ENCHAPES" | "GENERALES";
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
        /**
         * Motivo
         * @description Cuerpo de la congelación: el motivo es obligatorio y se guarda sin espacios en los extremos.
         */
        Motivo: {
            /** Motivo */
            motivo: string;
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
}
