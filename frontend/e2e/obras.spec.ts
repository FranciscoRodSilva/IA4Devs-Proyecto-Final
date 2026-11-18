import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

/**
 * Flujo de extremo a extremo del alta de obra de TKT-012a (CA-13), contra el backend y la base reales.
 * El usuario con rol DIRECTOR_PROYECTOS lo siembra `preparacion-global.ts` y deja su correo y su
 * contraseña en el entorno (`CIMENTA_HUMO_DP_CORREO` y `CIMENTA_HUMO_DP_CONTRASENA`): ninguna credencial
 * vive en este archivo.
 *
 * La base de humo es acumulativa: cada corrida deja su obra. Por eso cada código lleva el prefijo
 * `E2E-` y un sufijo aleatorio de 8 hexadecimales: nunca choca con otra corrida ni con una obra real.
 * La lista pide la primera página de 200 obras ordenadas por código; tras unas 200 corridas sobre la
 * misma base, una obra nueva podría quedar fuera de esa página. Si ocurre, se reinicia la base de humo
 * (`docker compose down -v`, migrar y volver a sembrar). Es un riesgo conocido del diseño, de impacto bajo.
 */

function credencialesDeDirector(): { correo: string; contrasena: string } {
  const correo = process.env.CIMENTA_HUMO_DP_CORREO;
  const contrasena = process.env.CIMENTA_HUMO_DP_CONTRASENA;
  if (correo === undefined || contrasena === undefined) {
    throw new Error("Faltan CIMENTA_HUMO_DP_CORREO y CIMENTA_HUMO_DP_CONTRASENA: los fija la preparación global.");
  }
  return { correo, contrasena };
}

async function iniciarSesionComoDirector(page: Page): Promise<void> {
  const { correo, contrasena } = credencialesDeDirector();
  await page.goto("/");
  await expect(page).toHaveURL(/\/inicio-sesion$/);
  await page.getByLabel("Correo").fill(correo);
  await page.getByLabel("Contraseña").fill(contrasena);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByRole("button", { name: "Salir" })).toBeVisible();
}

/** En mayúsculas porque el servidor normaliza el código (D-1): lo que se escribe es lo que se lista. */
function codigoDeEstaCorrida(): string {
  return `E2E-${randomBytes(4).toString("hex").toUpperCase()}`;
}

async function abrirObras(page: Page): Promise<void> {
  const menu = page.getByRole("navigation", { name: "Secciones" });
  await menu.getByRole("link", { name: "Obras", exact: true }).click();
  await expect(page).toHaveURL(/\/obras$/);
  await expect(page.getByRole("heading", { name: "Obras", exact: true })).toBeVisible();
}

/** Abre el formulario, captura la obra con los valores propuestos por omisión y pulsa «Guardar». */
async function darDeAltaObra(page: Page, codigo: string, nombre: string): Promise<void> {
  await page.getByRole("button", { name: "Dar de alta una obra" }).click();
  const formulario = page.getByRole("dialog", { name: "Alta de obra" });
  await expect(formulario).toBeVisible();
  await formulario.getByLabel("Código").fill(codigo);
  await formulario.getByLabel("Nombre").fill(nombre);
  await formulario.getByLabel("Domicilio").fill("Calle de la prueba 1, Ciudad de México");
  await formulario.getByRole("button", { name: "Guardar" }).click();
}

test("hdu001_esc02 · alta de obra de punta a punta", async ({ page }) => {
  const codigo = codigoDeEstaCorrida();
  await iniciarSesionComoDirector(page);
  await abrirObras(page);

  await darDeAltaObra(page, codigo, `Obra de prueba ${codigo}`);

  await expect(page.getByRole("dialog", { name: "Alta de obra" })).toBeHidden();
  const fila = page.getByRole("row").filter({ hasText: codigo });
  await expect(fila).toHaveCount(1);
  await expect(fila).toContainText("Planeación");
});

test("hdu001_esc03 · el mismo código otra vez", async ({ page }) => {
  const codigo = codigoDeEstaCorrida();
  await iniciarSesionComoDirector(page);
  await abrirObras(page);
  await darDeAltaObra(page, codigo, `Obra de prueba ${codigo}`);
  await expect(page.getByRole("dialog", { name: "Alta de obra" })).toBeHidden();
  await expect(page.getByRole("row").filter({ hasText: codigo })).toHaveCount(1);

  await darDeAltaObra(page, codigo, `Otra obra con el mismo código ${codigo}`);

  const formulario = page.getByRole("dialog", { name: "Alta de obra" });
  await expect(formulario).toBeVisible();
  await expect(formulario.getByText(`Ya existe una obra con el código ${codigo}.`)).toBeVisible();
  await expect(formulario.getByRole("button", { name: "Ver la obra" })).toBeVisible();

  await formulario.getByRole("button", { name: "Ver la obra" }).click();
  await expect(formulario).toBeHidden();
  await expect(page.getByRole("row").filter({ hasText: codigo })).toHaveCount(1);
});

/*
 * Mantenimiento de obras de TKT-012b (CA-18, TC-81). Usa las dos obras que sembró `preparacion-global.ts`,
 * cada una con un código único por corrida: M1, `ACTIVA` con su línea base congelada, y M2, `PLANEACION`
 * con su línea base `BORRADOR` (tiene historial). Son dos obras porque «Eliminar» solo se ofrece en
 * `PLANEACION` y suspender exige `ACTIVA`. Cada prueba usa la suya y no depende de la otra.
 */

function codigoDeObraDeMantenimiento(obra: "M1" | "M2"): string {
  const codigo = process.env[`CIMENTA_HUMO_MANT_${obra}_CODIGO`];
  if (codigo === undefined || codigo === "") {
    throw new Error(`Falta CIMENTA_HUMO_MANT_${obra}_CODIGO: lo fija la preparación global.`);
  }
  return codigo;
}

/** La fila de la obra en la lista, por su código. */
function filaDeObra(page: Page, codigo: string) {
  return page.getByRole("row").filter({ hasText: codigo });
}

/** El estado es la tercera celda de la fila (Código, Nombre, Estado): se compara exacto, no por contener. */
function estadoDeFila(fila: ReturnType<typeof filaDeObra>) {
  return fila.getByRole("cell").nth(2);
}

test("hdu001_esc20 · ca18 · editar el nombre, suspender y reactivar una obra activa", async ({ page }) => {
  const codigo = codigoDeObraDeMantenimiento("M1");
  const nombreNuevo = `Obra M1 editada ${codigo}`;
  await iniciarSesionComoDirector(page);
  await abrirObras(page);
  const fila = filaDeObra(page, codigo);
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Activa");

  // Editar: el código se muestra y no se edita; el nombre nuevo aparece en la lista sin recargar la página.
  await fila.getByRole("button", { name: `Editar ${codigo}` }).click();
  const edicion = page.getByRole("dialog", { name: "Editar obra" });
  await expect(edicion).toBeVisible();
  await expect(edicion.getByLabel("Código")).toHaveValue(codigo);
  await expect(edicion.getByLabel("Código")).toHaveAttribute("readonly", "");
  await edicion.getByLabel("Nombre").fill(nombreNuevo);
  await edicion.getByRole("button", { name: "Guardar" }).click();
  await expect(edicion).toBeHidden();
  await expect(fila).toContainText(nombreNuevo);
  await expect(estadoDeFila(fila)).toHaveText("Activa");

  // Suspender con motivo: la fila pasa a «Suspendida» y ofrece «Reactivar» en lugar de «Suspender».
  await fila.getByRole("button", { name: `Suspender ${codigo}` }).click();
  const suspension = page.getByRole("dialog", { name: "Suspender la obra" });
  await expect(suspension).toBeVisible();
  await suspension.getByLabel("Motivo").fill("Pausa por falta de acceso al predio");
  await suspension.getByRole("button", { name: "Suspender obra" }).click();
  await expect(suspension).toBeHidden();
  await expect(estadoDeFila(fila)).toHaveText("Suspendida");
  await expect(fila.getByRole("button", { name: `Reactivar ${codigo}` })).toBeVisible();
  await expect(fila.getByRole("button", { name: `Suspender ${codigo}` })).toHaveCount(0);

  // Reactivar con motivo: vuelve a «Activa» y conserva el nombre editado.
  await fila.getByRole("button", { name: `Reactivar ${codigo}` }).click();
  const reactivacion = page.getByRole("dialog", { name: "Reactivar la obra" });
  await expect(reactivacion).toBeVisible();
  await reactivacion.getByLabel("Motivo").fill("Se restableció el acceso al predio");
  await reactivacion.getByRole("button", { name: "Reactivar obra" }).click();
  await expect(reactivacion).toBeHidden();
  await expect(estadoDeFila(fila)).toHaveText("Activa");
  await expect(fila.getByRole("button", { name: `Suspender ${codigo}` })).toBeVisible();

  // La lista que devuelve el servidor, no solo la que quedó en memoria: nombre nuevo y estado activo.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Obras", exact: true })).toBeVisible();
  await expect(fila).toHaveCount(1);
  await expect(fila).toContainText(nombreNuevo);
  await expect(estadoDeFila(fila)).toHaveText("Activa");
});

test("hdu001_esc20 · ca18 · eliminar una obra con historial queda bloqueado y la obra sigue en la lista", async ({
  page,
}) => {
  const codigo = codigoDeObraDeMantenimiento("M2");
  await iniciarSesionComoDirector(page);
  await abrirObras(page);
  const fila = filaDeObra(page, codigo);
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Planeación");

  await fila.getByRole("button", { name: `Eliminar ${codigo}` }).click();
  const confirmacion = page.getByRole("dialog", { name: `¿Eliminar la obra ${codigo}?` });
  await expect(confirmacion).toBeVisible();
  await confirmacion.getByRole("button", { name: "Confirmar baja" }).click();
  await expect(confirmacion).toBeHidden();

  // El rechazo es un bloqueo de negocio con su mensaje y su código, no un error genérico.
  const bloqueo = page.getByRole("region", { name: "No se puede completar" });
  await expect(bloqueo).toBeVisible();
  await expect(bloqueo.getByText("OBRA_CON_HISTORIAL", { exact: true })).toBeVisible();
  await expect(bloqueo.getByText(`La obra ${codigo} tiene historial y no se puede eliminar.`)).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  // Solo las acciones que trae el contrato para una obra en planeación (D-2): cerrar, no suspender.
  await expect(bloqueo.getByRole("button")).toHaveCount(1);
  await expect(bloqueo.getByRole("button", { name: "Cerrar", exact: true })).toBeVisible();
  await expect(bloqueo.getByRole("button", { name: "Suspender" })).toHaveCount(0);

  // La obra no se borró: sigue en la lista, en el mismo estado.
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Planeación");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Obras", exact: true })).toBeVisible();
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Planeación");
});
