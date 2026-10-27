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
         * @description M2 · RNF-03: abre una sesión y fija la cookie opaca. Sin `max_age`: la caducidad la decide el servidor.
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
         * @description M4: revoca la sesión (nunca la borra) y expira la cookie.
         */
        post: operations["cerrar_sesion"];
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
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * Rol
         * @description Los seis roles del PRD §4 (esquema `Rol` del borrador). Un usuario puede acumular varios.
         * @enum {string}
         */
        Rol: "DIRECCION_GENERAL" | "DIRECTOR_PROYECTOS" | "RESIDENTE" | "COMPRAS" | "ALMACEN" | "ADMINISTRACION";
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
}
