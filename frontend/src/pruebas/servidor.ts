import { setupServer } from "msw/node";

/** Doble del servidor para las pruebas de cliente (M10). Sin manejadores por omisión. */
export const servidorPruebas = setupServer();
