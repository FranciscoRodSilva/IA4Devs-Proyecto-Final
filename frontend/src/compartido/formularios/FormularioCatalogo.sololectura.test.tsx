import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { type Mock, describe, expect, test, vi } from "vitest";
import { z } from "zod";
import type { ResultadoApi } from "@/api/cliente";
import { type CampoCatalogo, FormularioCatalogo, type PropsFormularioCatalogo } from "./FormularioCatalogo";

// TKT-012b · fila B1 · CA-15 · TC-64. La edición de una obra muestra el código y el tipo de contrato solo de lectura:
// con su valor, sin que se puedan cambiar y sin que viajen al servidor. Archivo aparte para no tocar las pruebas de
// TKT-008 y TKT-012a (CA-R5, TC-INV-6).

// El esquema de edición no exige los campos de solo lectura: lo que no se puede cambiar no se valida ni se envía.
const esquemaEdicion = z.object({
  codigo: z.string().optional(),
  nombre: z.string().min(1, "El nombre es obligatorio."),
  modalidad: z.enum(["ALFA", "BETA"]).optional(),
});

type Nombres = "codigo" | "nombre" | "modalidad";

interface RespuestaEdicion {
  id: string;
}

type Props = PropsFormularioCatalogo<typeof esquemaEdicion, RespuestaEdicion>;

const CODIGO = "AP-058-25";
const NOMBRE = "Union Square F2";
const NOMBRE_NUEVO = "Union Square Fase 2";
const RESPUESTA: RespuestaEdicion = { id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d" };

const OPCIONES = [
  { valor: "ALFA", etiqueta: "Opción alfa" },
  { valor: "BETA", etiqueta: "Opción beta" },
] as const;

const ok = <T,>(datos: T): ResultadoApi<T> => ({ ok: true, datos });

function camposDe(soloLecturaCodigo: boolean | undefined, soloLecturaModalidad: boolean | undefined): ReadonlyArray<CampoCatalogo<Nombres>> {
  // `undefined` es «no declarado»: es el caso de todos los formularios anteriores a esta fila.
  return [
    { nombre: "codigo", etiqueta: "Código", ...(soloLecturaCodigo === undefined ? {} : { soloLectura: soloLecturaCodigo }) },
    { nombre: "nombre", etiqueta: "Nombre" },
    {
      nombre: "modalidad",
      etiqueta: "Modalidad",
      tipo: "desplegable",
      opciones: OPCIONES,
      ...(soloLecturaModalidad === undefined ? {} : { soloLectura: soloLecturaModalidad }),
    },
  ];
}

interface OpcionesArnes {
  soloLecturaCodigo?: boolean;
  soloLecturaModalidad?: boolean;
}

/** El mismo montaje que el de TKT-008: «+» abre el formulario, que arranca con los valores de una obra existente. */
function abrir({ soloLecturaCodigo, soloLecturaModalidad }: OpcionesArnes = {}) {
  const alGuardar = vi.fn<Props["alGuardar"]>(async () => ok(RESPUESTA));
  const campos = camposDe(soloLecturaCodigo, soloLecturaModalidad);

  function Arnes() {
    const [abierto, setAbierto] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setAbierto(true)}>
          +
        </button>
        <FormularioCatalogo<typeof esquemaEdicion, RespuestaEdicion>
          abierto={abierto}
          titulo="Editar obra"
          esquema={esquemaEdicion}
          campos={campos}
          valoresIniciales={{ codigo: CODIGO, nombre: NOMBRE, modalidad: "BETA" }}
          alGuardar={alGuardar}
          alGuardado={vi.fn<Props["alGuardado"]>()}
          alBloqueo={vi.fn<Props["alBloqueo"]>()}
          alAccion={vi.fn<Props["alAccion"]>()}
          alCerrar={() => setAbierto(false)}
        />
      </>
    );
  }

  render(<Arnes />);
  return { alGuardar, usuario: userEvent.setup() };
}

type Usuario = ReturnType<typeof userEvent.setup>;

async function abrirFormulario(usuario: Usuario) {
  await usuario.click(screen.getByRole("button", { name: "+" }));
  await screen.findByRole("textbox", { name: "Nombre" });
}

const campoCodigo = () => screen.getByRole("textbox", { name: "Código" });
const campoNombre = () => screen.getByRole("textbox", { name: "Nombre" });
const campoModalidad = () => screen.getByRole("combobox", { name: "Modalidad" });
const botonGuardar = () => screen.getByRole("button", { name: "Guardar" });

/** No se puede editar: `readonly` o `disabled`, lo que el formulario elija; lo que importa es que la persona no pueda cambiarlo. */
function noEsEditable(control: HTMLElement): boolean {
  return control.hasAttribute("readonly") || control.hasAttribute("disabled");
}

/** El valor con que `alGuardar` fue llamado la primera vez; falla con un mensaje claro si no se llamó. */
function valoresEnviados(alGuardar: Mock<Props["alGuardar"]>): Record<string, unknown> {
  const llamada = alGuardar.mock.calls[0];
  if (llamada === undefined) throw new Error("alGuardar no se llamó");
  return { ...llamada[0] };
}

describe("TKT-012b · FormularioCatalogo · campos de solo lectura", () => {
  test("tkt012b_ca15 · TC-64 · un campo soloLectura se muestra con su valor y no es editable", async () => {
    const { usuario } = abrir({ soloLecturaCodigo: true });
    await abrirFormulario(usuario);

    // La persona ve el código de la obra que edita…
    expect(campoCodigo()).toHaveValue(CODIGO);
    // …y el campo se presenta como no editable a quien lo lee con tecnología de apoyo.
    expect(noEsEditable(campoCodigo())).toBe(true);
    // Los demás campos siguen siendo editables.
    expect(noEsEditable(campoNombre())).toBe(false);
  });

  test("tkt012b_ca15 · TC-64 · rechazo: teclear en un campo soloLectura no cambia su valor", async () => {
    const { usuario } = abrir({ soloLecturaCodigo: true });
    await abrirFormulario(usuario);

    await usuario.type(campoCodigo(), "XYZ-999");

    expect(campoCodigo()).toHaveValue(CODIGO);
  });

  test("tkt012b_ca15 · TC-64 · un campo soloLectura no viaja al alGuardar aunque se intente editarlo", async () => {
    const { alGuardar, usuario } = abrir({ soloLecturaCodigo: true });
    await abrirFormulario(usuario);

    await usuario.type(campoCodigo(), "XYZ-999");
    await usuario.clear(campoNombre());
    await usuario.type(campoNombre(), NOMBRE_NUEVO);
    await usuario.click(botonGuardar());

    await waitFor(() => expect(alGuardar).toHaveBeenCalledTimes(1));
    const enviados = valoresEnviados(alGuardar);
    // La clave no está: no basta con que valga `undefined`, el servidor no debe recibir un `codigo` nulo.
    expect(enviados).not.toHaveProperty("codigo");
    // Lo editable sí viaja, y con lo escrito.
    expect(enviados).toHaveProperty("nombre", NOMBRE_NUEVO);
  });

  test("tkt012b_ca15 · TC-64 · un desplegable soloLectura muestra su opción, no cambia y no viaja", async () => {
    const { alGuardar, usuario } = abrir({ soloLecturaModalidad: true });
    await abrirFormulario(usuario);

    // Se muestra la etiqueta de la opción que trae el registro, no un valor vacío.
    expect(campoModalidad()).toHaveDisplayValue("Opción beta");
    expect(noEsEditable(campoModalidad())).toBe(true);

    await usuario.selectOptions(campoModalidad(), "Opción alfa");
    expect(campoModalidad()).toHaveDisplayValue("Opción beta");

    await usuario.click(botonGuardar());

    await waitFor(() => expect(alGuardar).toHaveBeenCalledTimes(1));
    expect(valoresEnviados(alGuardar)).not.toHaveProperty("modalidad");
  });

  test("tkt012b_ca15 · TC-64 · los dos campos soloLectura a la vez salen del envío y el resto viaja", async () => {
    const { alGuardar, usuario } = abrir({ soloLecturaCodigo: true, soloLecturaModalidad: true });
    await abrirFormulario(usuario);

    await usuario.click(botonGuardar());

    await waitFor(() => expect(alGuardar).toHaveBeenCalledTimes(1));
    expect(valoresEnviados(alGuardar)).toEqual({ nombre: NOMBRE });
  });

  // CA-R5 · TC-INV-6 · por omisión nada cambia: un formulario sin la opción se comporta como siempre.
  test.each([
    ["sin declarar la opción", undefined],
    ["con soloLectura: false", false],
  ])("tkt012b_ca15 · TC-INV-6 · %s el campo sigue editable y viaja", async (_descripcion, valor) => {
    const { alGuardar, usuario } = abrir({ soloLecturaCodigo: valor, soloLecturaModalidad: valor });
    await abrirFormulario(usuario);

    expect(noEsEditable(campoCodigo())).toBe(false);
    expect(noEsEditable(campoModalidad())).toBe(false);

    await usuario.clear(campoCodigo());
    await usuario.type(campoCodigo(), "AP-060-25");
    await usuario.selectOptions(campoModalidad(), "Opción alfa");
    await usuario.click(botonGuardar());

    await waitFor(() => expect(alGuardar).toHaveBeenCalledTimes(1));
    expect(alGuardar).toHaveBeenCalledWith({ codigo: "AP-060-25", nombre: NOMBRE, modalidad: "ALFA" });
  });
});
