"""Utilidades compartidas de las pruebas TKT-014 (lector de APU)."""

from __future__ import annotations

from decimal import Decimal

from cimenta.presupuesto.dominio.catalogo import ValorCelda


def hoja_apu_sintetica(
    *,
    codigo: ValorCelda = "P-001",
    unidad_cab: str = "M2",
    fecha: str = "2025-09-01",
    analista: str = "Analista Prueba",
    pu_cabecera: ValorCelda = Decimal("158.93"),
    pie: ValorCelda | None = None,
    siroc: bool = False,
    celdas_rotas: dict[tuple[int, str], ValorCelda] | None = None,
) -> list[tuple[int, tuple[ValorCelda, ...]]]:
    """Construye filas en memoria con la disposición medida en E-1 (TKT-014a)."""
    pie_valor = pie if pie is not None else (Decimal("160.205") if siroc else Decimal("158.93"))
    pu_c = pu_cabecera

    cuerpo: list[tuple[int, tuple[ValorCelda, ...]]] = [
        (1, ("ANALISTA:", analista)),
        (2, ("CODIGO:", None, codigo)),
        (3, ("UNIDAD:", None, unidad_cab)),
        (4, ("FECHA:", None, fecha)),
        (5, ("P.U:", None, pu_c)),
        (6, ("MATERIAL ", None, None, "UNIDAD", "COSTO", "REND.", "CARGO")),
        (7, ("SACO",)),
        (8, ("MATERIAL UNO", None, None, "PZA", Decimal("10"), Decimal("2"), Decimal("20"))),
        (9, ("MATERIAL DOS", None, None, "KG", Decimal("5"), Decimal("1.5"), Decimal("7.5"))),
        (10, ("MANO DE OBRA",)),
        (11, ("CUADRILLA X", None, None, "JORNAL", Decimal("1000"), Decimal("10"), Decimal("100"))),
        (
            12,
            ("COSTO DIRECTO", None, None, "MATERIAL Y MANO DE OBRA", None, None, Decimal("127.5")),
        ),
        (13, ("CARGOS PORCENTUALES ", None, None, "%")),
        (
            14,
            (
                "HERRAMIENTA MENOR",
                None,
                None,
                Decimal("0.01"),
                Decimal("127.5"),
                None,
                Decimal("1.275"),
            ),
        ),
    ]
    if siroc:
        cuerpo.append(
            (
                15,
                (
                    "SIROC",
                    None,
                    None,
                    Decimal("0.01"),
                    Decimal("127.5"),
                    None,
                    Decimal("1.275"),
                ),
            )
        )
    offset = 1 if siroc else 0
    cuerpo.extend(
        [
            (15 + offset, ("CARGOS VIATICOS Y HOSPEDAJE", None, None, "%")),
            (
                16 + offset,
                (
                    "OFICIAL TABLAROQUERO",
                    None,
                    None,
                    Decimal("0"),
                    Decimal("0"),
                    None,
                    Decimal("0"),
                ),
            ),
            (
                17 + offset,
                (
                    "AYUDANTE TABLAROQUERO",
                    None,
                    None,
                    Decimal("0"),
                    Decimal("0"),
                    None,
                    Decimal("0"),
                ),
            ),
            (
                18 + offset,
                (
                    "INDIRECTOS",
                    None,
                    None,
                    Decimal("0.08"),
                    Decimal("128.775"),
                    None,
                    Decimal("10.302"),
                ),
            ),
            (
                19 + offset,
                (
                    "UTILIDAD ",
                    None,
                    None,
                    Decimal("0.12"),
                    Decimal("128.775"),
                    None,
                    Decimal("15.453"),
                ),
            ),
            (
                20 + offset,
                ("IVA ", None, None, Decimal("0.16"), Decimal("27.5"), None, Decimal("4.4")),
            ),
            (21 + offset, (None, None, None, "PRECIO UNITARIO ", None, None, pie_valor)),
        ]
    )
    filas = cuerpo
    if celdas_rotas:
        columnas = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}
        corregidas: list[tuple[int, tuple[ValorCelda, ...]]] = []
        for numero, fila in filas:
            lista = list(fila)
            for (fila_n, col), valor in celdas_rotas.items():
                if fila_n != numero:
                    continue
                idx = columnas[col]
                while len(lista) <= idx:
                    lista.append(None)
                lista[idx] = valor
            corregidas.append((numero, tuple(lista)))
        return corregidas
    return filas


def fila_apu(numero: int, *valores: ValorCelda) -> tuple[int, tuple[ValorCelda, ...]]:
    return (numero, valores)
