"""Origen de una petición (TKT-057, ciclo de corrección 1, auditoría de seguridad F003): `origen_de(request)`.

Sin Docker: un doble mínimo de `Request` con `.client` (un objeto con `.host`, o `None`). El límite por
origen (`RNF-04`, `CA-6`) cuenta fallos por cubeta, no por dirección: una dirección IPv4 es su propia
cubeta, y una IPv6 se agrupa en su prefijo /64, porque quien tiene un /64 dispone de 2^64 direcciones
y con una por intento esquivaría el tope de veinte. Sin cliente, la cubeta es el texto fijo
«desconocido»: nunca `None`, que dejaba la petición sin límite.

`origen_de` vive en `cimenta.identidad.api.dependencias` y aún no existe: el símbolo se importa dentro de
cada caso, así cada uno falla por sí solo (`ImportError`) y la recolección no se cae.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any

import pytest

CUBETA_SIN_CLIENTE = "desconocido"


@dataclass(frozen=True)
class ClienteDeMentira:
    """Lo único que `origen_de` lee del cliente: su `host`."""

    host: str


@dataclass(frozen=True)
class PeticionDeMentira:
    """Un doble mínimo de `starlette.requests.Request`: solo `.client`."""

    client: ClienteDeMentira | None


def peticion_desde(host: str | None) -> Any:
    return PeticionDeMentira(client=None if host is None else ClienteDeMentira(host))


def cubeta_64(host: str) -> str:
    """El prefijo /64 de una dirección IPv6, escrito como lo hace `ipaddress`."""
    return str(ipaddress.ip_network(f"{host}/64", strict=False))


def test_tkt057_ca06_origen_de_ipv4_se_devuelve_tal_cual() -> None:
    """CA-6 · RNF-04 · F003 — una IPv4 es su propia cubeta: `203.0.113.7` sigue siendo `203.0.113.7`."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde("203.0.113.7")) == "203.0.113.7"


@pytest.mark.parametrize(
    "host", ["2001:db8::1", "2001:db8::ffff", "2001:db8:0:0:aaaa:bbbb:cccc:dddd"]
)
def test_tkt057_ca06_origen_de_dos_ipv6_del_mismo_64_comparten_cubeta(host: str) -> None:
    """CA-6 · RNF-04 · F003 — cualquier dirección de `2001:db8::/64` cae en la cubeta `2001:db8::/64`."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde(host)) == "2001:db8::/64"
    assert origen_de(peticion_desde(host)) == cubeta_64(host)


def test_tkt057_ca07_origen_de_ipv6_de_otro_64_cae_en_otra_cubeta() -> None:
    """CA-7 · RNF-04 · F003 — el prefijo vecino `2001:db8:0:1::/64` no comparte cubeta con `2001:db8::/64`."""
    from cimenta.identidad.api.dependencias import origen_de

    propia = origen_de(peticion_desde("2001:db8::1"))
    vecina = origen_de(peticion_desde("2001:db8:0:1::1"))

    assert vecina == "2001:db8:0:1::/64"
    assert vecina != propia


def test_tkt057_ca06_origen_de_ipv6_en_otra_notacion_cae_en_la_misma_cubeta() -> None:
    """CA-6 · RNF-04 · F003 — la notación larga y la corta de la misma dirección dan una sola cubeta."""
    from cimenta.identidad.api.dependencias import origen_de

    corta = origen_de(peticion_desde("2001:db8::1"))
    larga = origen_de(peticion_desde("2001:0DB8:0000:0000:0000:0000:0000:0001"))

    assert larga == corta == "2001:db8::/64"


def test_tkt057_ca06_origen_de_ipv4_mapeada_en_ipv6_se_desenvuelve() -> None:
    """CA-6 · RNF-04 · F003 — `::ffff:203.0.113.7` es la IPv4 `203.0.113.7`, no un /64 de direcciones mapeadas.

    Un servidor de pila doble entrega así a los clientes IPv4; si no se desenvolviera, todos los
    clientes IPv4 del mundo compartirían una sola cubeta `::/64`.
    """
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde("::ffff:203.0.113.7")) == "203.0.113.7"


def test_tkt057_ca06_origen_de_sin_cliente_es_la_cubeta_fija_y_nunca_none() -> None:
    """CA-6 · RNF-04 · F003 — `request.client is None` da «desconocido»: una cubeta que también se bloquea."""
    from cimenta.identidad.api.dependencias import origen_de

    cubeta = origen_de(peticion_desde(None))

    assert cubeta is not None
    assert cubeta == CUBETA_SIN_CLIENTE


@pytest.mark.parametrize("host", ["testclient", "no-es-una-direccion"])
def test_tkt057_ca06_origen_de_un_host_que_no_es_una_direccion_se_devuelve_sin_tocar(
    host: str,
) -> None:
    """CA-6 · RNF-04 · F003 — un host que no parsea (el `testclient` de Starlette) no lanza y vuelve igual."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde(host)) == host


# --------------------------------------------------------------------------- casos de borde
#
# Cobertura de casos de borde pedida por la auditoría de código del ciclo 2. No son rojo: el
# comportamiento ya existe en `origen_de` y estos casos nacen en verde a propósito, para fijarlo
# antes de que cambien los tipos de `abrir_sesion` (`origen_ip: str`). Cada uno se verificó contra la
# implementación actual; si alguno cayera, sería una regresión de `origen_de`, no un falso rojo.


@pytest.mark.parametrize("host", ["fe80::1%eth0", "FE80::1%eth0"])
def test_tkt057_ca06_origen_de_ipv6_con_identificador_de_zona_cae_en_su_64_sin_lanzar(
    host: str,
) -> None:
    """CA-6 · RNF-04 · F003 (borde) — `fe80::1%eth0` y `FE80::1%eth0` dan la cubeta `fe80::/64`, sin excepción."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde(host)) == "fe80::/64"


@pytest.mark.parametrize("host", ["::", "::1"])
def test_tkt057_ca06_origen_de_no_especificada_y_bucle_local_caen_en_la_cubeta_cero(
    host: str,
) -> None:
    """CA-6 · RNF-04 · F003 (borde) — `::` y `::1` caen en `::/64`."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde(host)) == "::/64"


def test_tkt057_ca06_origen_de_host_vacio_se_devuelve_vacio_sin_lanzar() -> None:
    """CA-6 · RNF-04 · F003 (borde) — un host vacío no parsea y vuelve tal cual, como `""`."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde("")) == ""


def test_tkt057_ca06_origen_de_ipv4_mapeada_en_notacion_hexadecimal_se_desenvuelve() -> None:
    """CA-6 · RNF-04 · F003 (borde) — `::ffff:0a00:0001` es la IPv4 `10.0.0.1`."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde("::ffff:0a00:0001")) == "10.0.0.1"


def test_tkt057_ca06_origen_de_direccion_6to4_se_agrupa_como_ipv6_corriente() -> None:
    """CA-6 · RNF-04 · F003 (borde) — `2002:c000:0204::1` (6to4) no se desenvuelve: cubeta `2002:c000:204::/64`."""
    from cimenta.identidad.api.dependencias import origen_de

    assert origen_de(peticion_desde("2002:c000:0204::1")) == "2002:c000:204::/64"


def test_tkt057_ca06_origen_de_cadena_larga_sin_parsear_vuelve_igual() -> None:
    """CA-6 · RNF-04 · F003 (borde) — un host basura de 5000 caracteres no lanza y vuelve intacto."""
    from cimenta.identidad.api.dependencias import origen_de

    host = "x" * 5000

    assert origen_de(peticion_desde(host)) == host
