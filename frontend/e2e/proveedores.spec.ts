import { randomBytes, randomInt } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { sembrarOrdenParcial } from "./sembrar-orden";

/**
 * Flujos de extremo a extremo del catálogo de proveedores de TKT-032a (CA-11 y CA-8), contra el backend y la
 * base reales. Los dos corren como Compras, el único rol que opera el catálogo. `preparacion-global.ts` siembra
 * el usuario y la obra y deja en el entorno del proceso:
 *
 * - `CIMENTA_HUMO_CORREO` y `CIMENTA_HUMO_CONTRASENA`: el usuario de Compras de humo.
 * - `CIMENTA_HUMO_LB_OBRA_ID`: la obra de humo, contra la que se siembra la orden de TC-E2.
 *
 * Ninguna credencial vive en este archivo.
 *
 * Riesgo de la obra de humo compartida. Playwright corre con `workers: 1` y en orden alfabético de archivo:
 * `humo`, `linea-base`, `obras` y este spec, que es el último. `linea-base.spec.ts` congela la línea base de
 * esa misma obra (`CIMENTA_HUMO_LB_OBRA_ID`) y fija un tope de MUROS de 0.01, así que este spec la encuentra
 * `CONGELADA` y con ese tope. No depende de ese estado: la orden la siembra el sembrador local por SQL,
 * sin pasar por la evaluación del presupuesto, y solo necesita que la obra exista. Si un día este spec corre
 * antes que `linea-base.spec.ts`, la obra estará en `BORRADOR` y el flujo es el mismo; lo que no se admite es
 * que otro spec la borre o la cierre. Tampoco se debe sembrar una segunda orden en ella con un folio fijo:
 * el folio lleva sufijo aleatorio por corrida (`uq_orden_compra_folio`).
 *
 * La base de humo es acumulativa: cada corrida deja dos proveedores. Por eso cada nombre lleva el prefijo
 * `E2E-` y un sufijo aleatorio, y cada RFC es único por corrida. Como la lista pide páginas de 50 y la base
 * puede crecer más allá de la primera, todo se busca por RFC y nunca se confía en que el proveedor nuevo
 * aparezca sin filtrar. El RFC cumple el patrón del servidor, que exige tres letras al principio (`[A-ZÑ&]{3,4}`):
 * `EEE`, seis dígitos al azar y tres caracteres hexadecimales en mayúsculas. Con `E2E` el servidor lo
 * rechazaría con `422`, porque el `2` no es una letra.
 */

function variableObligatoria(nombre: string): string {
  const valor = process.env[nombre];
  if (valor === undefined || valor === "") {
    throw new Error(`Falta ${nombre}: la fija la preparación global (e2e/preparacion-global.ts).`);
  }
  return valor;
}

async function iniciarSesionComoCompras(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page).toHaveURL(/\/inicio-sesion$/);
  await page.getByLabel("Correo").fill(variableObligatoria("CIMENTA_HUMO_CORREO"));
  await page.getByLabel("Contraseña").fill(variableObligatoria("CIMENTA_HUMO_CONTRASENA"));
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByRole("button", { name: "Salir" })).toBeVisible();
}

/** `E2E-` y 8 hexadecimales en mayúsculas: nunca choca con otra corrida ni con un proveedor real. */
function nombreDeEstaCorrida(): string {
  return `E2E-${randomBytes(4).toString("hex").toUpperCase()}`;
}

/** Tres letras, seis dígitos al azar y tres hexadecimales en mayúsculas: cumple `^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$`. */
function rfcDeEstaCorrida(): string {
  const digitos = String(randomInt(0, 1_000_000)).padStart(6, "0");
  const hexadecimales = randomBytes(2).toString("hex").toUpperCase().slice(0, 3);
  return `EEE${digitos}${hexadecimales}`;
}

async function abrirProveedores(page: Page): Promise<void> {
  const menu = page.getByRole("navigation", { name: "Secciones" });
  await menu.getByRole("link", { name: "Proveedores", exact: true }).click();
  await expect(page).toHaveURL(/\/compras\/proveedores$/);
  await expect(page.getByRole("heading", { name: "Proveedores", exact: true })).toBeVisible();
}

/** Abre el formulario de alta, captura nombre y RFC con los días propuestos por omisión y pulsa «Guardar». */
async function capturarAlta(page: Page, nombre: string, rfc: string): Promise<void> {
  await page.getByRole("button", { name: "Dar de alta un proveedor" }).click();
  const formulario = page.getByRole("dialog", { name: "Alta de proveedor" });
  await expect(formulario).toBeVisible();
  await formulario.getByLabel("Nombre", { exact: true }).fill(nombre);
  await formulario.getByLabel("RFC", { exact: true }).fill(rfc);
  await formulario.getByRole("button", { name: "Guardar" }).click();
}

async function darDeAltaProveedor(page: Page, nombre: string, rfc: string): Promise<void> {
  await capturarAlta(page, nombre, rfc);
  await expect(page.getByRole("dialog", { name: "Alta de proveedor" })).toBeHidden();
}

/** Busca por RFC y espera a que la lista conteste a esa búsqueda: nunca se mira la lista sin filtrar (ver la cabecera). */
async function buscarPorRfc(page: Page, rfc: string): Promise<void> {
  await page.getByLabel("Buscar por nombre o RFC").fill(rfc);
  const respuesta = page.waitForResponse(
    (r) => r.request().method() === "GET" && r.url().includes("/api/v1/proveedores") && r.url().includes(`q=${rfc}`),
  );
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await respuesta;
}

type EtiquetaDeFiltro = "Activos" | "Desactivados" | "Dados de baja" | "Todos";

async function filtrarPorEstado(page: Page, etiqueta: EtiquetaDeFiltro): Promise<void> {
  await page.getByRole("combobox", { name: "Estado" }).selectOption({ label: etiqueta });
}

function filaDeProveedor(page: Page, rfc: string) {
  return page.getByRole("row").filter({ hasText: rfc });
}

/** El estado es la tercera celda de la fila (Nombre, RFC, Estado): se compara exacto, no por contener. */
function estadoDeFila(fila: ReturnType<typeof filaDeProveedor>) {
  return fila.getByRole("cell").nth(2);
}

/**
 * Espera la lista vacía con su texto. No basta `toHaveCount(0)` sobre las filas: mientras la lista se vuelve a
 * pedir solo hay un esqueleto, y esa espera pasaría antes de que el servidor conteste.
 */
async function esperarListaVacia(page: Page): Promise<void> {
  await expect(page.getByText("No hay proveedores con este filtro")).toBeVisible();
}

async function desactivarConMotivo(page: Page, nombre: string, motivo: string): Promise<void> {
  const captura = page.getByRole("dialog", { name: `Desactivar a ${nombre}` });
  await expect(captura).toBeVisible();
  await captura.getByRole("textbox", { name: "Motivo" }).fill(motivo);
  await captura.getByRole("button", { name: "Confirmar desactivación" }).click();
  await expect(captura).toBeHidden();
}

test("hdu004_esc02 · recorrido del catálogo", async ({ page }) => {
  // HDU-004 esc. 2, 3 y 12 · CA-11. Alta, lista, alta repetida, desactivación con motivo y filtros.
  const nombre = nombreDeEstaCorrida();
  const rfc = rfcDeEstaCorrida();
  await iniciarSesionComoCompras(page);
  await abrirProveedores(page);

  // Alta: el proveedor entra ACTIVO y se ve en la lista al buscarlo por su RFC.
  await darDeAltaProveedor(page, nombre, rfc);
  await buscarPorRfc(page, rfc);
  const fila = filaDeProveedor(page, rfc);
  await expect(fila).toHaveCount(1);
  await expect(fila).toContainText(nombre);
  await expect(estadoDeFila(fila)).toHaveText("Activo");

  // El mismo RFC otra vez: el servidor responde 409 RFC_DUPLICADO y el formulario nombra al proveedor existente.
  await capturarAlta(page, `${nombre} bis`, rfc);
  const formulario = page.getByRole("dialog", { name: "Alta de proveedor" });
  await expect(formulario).toBeVisible();
  const conflicto = formulario.getByRole("region");
  await expect(conflicto.getByText(`Ya existe un proveedor con el RFC ${rfc}.`)).toBeVisible();
  await expect(conflicto.getByText("Proveedor existente", { exact: true })).toBeVisible();
  await expect(conflicto.getByText(`${nombre} · ${rfc}`, { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(formulario).toBeHidden();

  // Ninguna fila repetida: el servidor no creó el segundo proveedor.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Proveedores", exact: true })).toBeVisible();
  await buscarPorRfc(page, rfc);
  await expect(fila).toHaveCount(1);
  await expect(fila).toContainText(nombre);
  await expect(page.getByRole("row").filter({ hasText: `${nombre} bis` })).toHaveCount(0);

  // Desactivar con motivo: la fila deja de verse con el filtro por omisión (Activos).
  await fila.getByRole("button", { name: `Desactivar ${nombre}` }).click();
  await desactivarConMotivo(page, nombre, "Entregas tardías en la prueba de humo");
  await esperarListaVacia(page);
  await expect(fila).toHaveCount(0);

  // Y aparece al filtrar «Desactivados», con su estado y sin «Desactivar»: lo que sigue es editar o dar de baja.
  await filtrarPorEstado(page, "Desactivados");
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Desactivado");
  await expect(fila.getByRole("button", { name: `Desactivar ${nombre}` })).toHaveCount(0);
  await expect(fila.getByRole("button", { name: `Dar de baja ${nombre}` })).toBeVisible();
});

test("hdu004_esc12 · baja bloqueada por una orden PARCIAL real", async ({ page }) => {
  // El sembrador (uv run) puede tardar hasta 120 s (spawnSync de sembrar-orden.ts); el tiempo por omisión de Playwright es 30 s.
  test.setTimeout(150_000);
  // HDU-004 esc. 12 · CA-8 y CA-11. La orden PARCIAL la siembra `herramientas.semilla_orden_proveedor_local`
  // contra el RFC del proveedor recién dado de alta; la baja la rechaza el servidor real con 409.
  const nombre = nombreDeEstaCorrida();
  const rfc = rfcDeEstaCorrida();
  const obraId = variableObligatoria("CIMENTA_HUMO_LB_OBRA_ID");
  const correo = variableObligatoria("CIMENTA_HUMO_CORREO");
  await iniciarSesionComoCompras(page);
  await abrirProveedores(page);
  await darDeAltaProveedor(page, nombre, rfc);

  // Con el proveedor ya dado de alta, el spec siembra una orden PARCIAL contra su RFC con sembrarOrdenParcial.
  const orden = sembrarOrdenParcial({ rfc, obraId, correo });

  await buscarPorRfc(page, rfc);
  const fila = filaDeProveedor(page, rfc);
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Activo");

  // Dar de baja: el servidor responde 409 PROVEEDOR_CON_ORDENES_ABIERTAS y la pantalla lo pinta como bloqueo.
  await fila.getByRole("button", { name: `Dar de baja ${nombre}` }).click();
  const captura = page.getByRole("dialog", { name: `Dar de baja a ${nombre}` });
  await expect(captura).toBeVisible();
  await captura.getByRole("textbox", { name: "Motivo" }).fill("Baja pedida en la prueba de humo");
  await captura.getByRole("button", { name: "Confirmar baja" }).click();
  await expect(captura).toBeHidden();

  const bloqueo = page.getByRole("region", { name: "No se puede completar" });
  await expect(bloqueo).toBeVisible();
  await expect(bloqueo.getByText("PROVEEDOR_CON_ORDENES_ABIERTAS", { exact: true })).toBeVisible();
  await expect(
    bloqueo.getByText(
      `${nombre} tiene 1 orden pendiente de recibir; se puede desactivar para órdenes nuevas conservando las existentes.`,
    ),
  ).toBeVisible();

  // La orden, con su folio y su estado reales: una sola fila, porque el proveedor es nuevo.
  const tablaDeOrdenes = bloqueo.getByRole("table", { name: "Órdenes pendientes" });
  const filasDeOrdenes = tablaDeOrdenes.getByRole("row").filter({ has: page.getByRole("cell") });
  await expect(filasDeOrdenes).toHaveCount(1);
  await expect(filasDeOrdenes.first().getByRole("cell").nth(0)).toHaveText(/^OC-\S+$/);
  await expect(filasDeOrdenes.first().getByRole("cell").nth(1)).toHaveText("PARCIAL");
  await expect(filasDeOrdenes.first().getByRole("cell").nth(0)).toHaveText(orden.folio);

  // Es un bloqueo y no un error; y solo trae las acciones del contrato: desactivar y cerrar.
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(bloqueo.getByRole("button")).toHaveText(["Desactivar el proveedor", "Cerrar"]);

  // El proveedor sigue ACTIVO: la baja no ocurrió.
  await expect(estadoDeFila(fila)).toHaveText("Activo");

  // «Desactivar el proveedor» abre la captura de motivo de ese proveedor y lo desactiva, no lo da de baja.
  await bloqueo.getByRole("button", { name: "Desactivar el proveedor" }).click();
  await desactivarConMotivo(page, nombre, "Se desactiva en lugar de dar de baja: tiene una orden pendiente");
  await expect(bloqueo).toBeHidden();

  // Sin BAJA: no aparece al filtrar «Dados de baja»; sí al filtrar «Desactivados».
  await filtrarPorEstado(page, "Dados de baja");
  await esperarListaVacia(page);
  await expect(fila).toHaveCount(0);

  await filtrarPorEstado(page, "Desactivados");
  await expect(fila).toHaveCount(1);
  await expect(estadoDeFila(fila)).toHaveText("Desactivado");
});
