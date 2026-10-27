import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { servidorPruebas } from "./servidor";

// Sin globales de Vitest: la limpieza del DOM entre pruebas se pide a mano.
beforeAll(() => servidorPruebas.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  servidorPruebas.resetHandlers();
});
afterAll(() => servidorPruebas.close());
