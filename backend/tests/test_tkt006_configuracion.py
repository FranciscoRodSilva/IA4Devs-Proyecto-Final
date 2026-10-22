"""Configuración y contraseñas de identidad (TKT-006, entrega A).

Este archivo crece por filas. Fila 1: TC-18, en su parte de dependencias. Fila 3: TC-13 a TC-17
(configuración por omisión, desde el entorno, valores inválidos, hash Argon2id y hash de descarte).

Sin Docker: ningún caso pide una *fixture* que abra la base. Solo se leen `pyproject.toml`,
`uv.lock` y el código de `cimenta/identidad/`. Los símbolos de producción se importan dentro de
cada caso, para que cada uno falle por su cuenta y la recolección no se caiga.
"""

import re
import tomllib
from datetime import timedelta
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
IDENTIDAD = BACKEND / "cimenta" / "identidad"
PROHIBIDOS_EN_EL_CODIGO = ("passlib", "bcrypt", "hashlib")
PROHIBIDOS_EN_LAS_DEPENDENCIAS = ("passlib", "bcrypt")

# Costes baratos de Argon2 para que cada derivación tarde milisegundos. La fila 4 la llevará a
# `conftest.py` para las pruebas con base; aquí vive como constante propia del archivo.
ENTORNO_DE_PRUEBA = {
    "CIMENTA_ARGON2_TIEMPO": "1",
    "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
    "CIMENTA_ARGON2_PARALELISMO": "1",
}
VARIABLES = (
    "CIMENTA_SESION_CADUCIDAD_MINUTOS",
    "CIMENTA_SESION_INACTIVIDAD_MINUTOS",
    "CIMENTA_ARGON2_TIEMPO",
    "CIMENTA_ARGON2_MEMORIA_KIB",
    "CIMENTA_ARGON2_PARALELISMO",
)
PARAMETROS_DEL_HASH = re.compile(r"\$m=\d+,t=\d+,p=\d+\$")


def normalizar_nombre(nombre: str) -> str:
    """Nombre de paquete según PEP 503: sin distinguir mayúsculas, guiones, puntos ni guiones bajos."""
    return re.sub(r"[-_.]+", "-", nombre).lower()


def nombre_y_extras(requisito: str) -> tuple[str, frozenset[str]]:
    """Separa `pwdlib[argon2]>=0.3` en el nombre normalizado y el conjunto de extras."""
    coincidencia = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[([^\]]*)\])?", requisito)
    assert coincidencia is not None, f"requisito ilegible en pyproject.toml: {requisito!r}"
    extras = coincidencia.group(2) or ""
    return (
        normalizar_nombre(coincidencia.group(1)),
        frozenset(normalizar_nombre(e) for e in extras.split(",") if e.strip()),
    )


def test_tkt006_ca15_sin_passlib_ni_hash_generico() -> None:
    """TC-18 · CA-15 esc. 2 — pwdlib[argon2] está declarada y fijada; no hay passlib, bcrypt ni hashlib.

    Parte de dependencias (fila 1). Falla por el contenido de `pyproject.toml` y `uv.lock`,
    no por una importación.
    """
    proyecto = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    declaradas = dict(nombre_y_extras(r) for r in proyecto["project"]["dependencies"])

    assert "pwdlib" in declaradas, (
        f"pyproject.toml no declara pwdlib entre sus dependencias: {sorted(declaradas)}"
    )
    assert "argon2" in declaradas["pwdlib"], (
        f"pwdlib se declara sin el extra argon2: extras {sorted(declaradas['pwdlib'])}"
    )
    for prohibido in PROHIBIDOS_EN_LAS_DEPENDENCIAS:
        assert prohibido not in declaradas, f"pyproject.toml declara {prohibido}"

    bloqueo = tomllib.loads((BACKEND / "uv.lock").read_text(encoding="utf-8"))
    fijados = {normalizar_nombre(p["name"]) for p in bloqueo["package"]}
    for esperado in ("pwdlib", "argon2-cffi"):
        assert esperado in fijados, f"uv.lock no fija el paquete {esperado}"
    assert "passlib" not in fijados, "uv.lock fija passlib"

    infractores = {
        f"{archivo.relative_to(BACKEND).as_posix()}: {palabra}"
        for archivo in IDENTIDAD.rglob("*.py")
        for palabra in PROHIBIDOS_EN_EL_CODIGO
        if re.search(rf"\b{palabra}\b", archivo.read_text(encoding="utf-8"), re.IGNORECASE)
    }
    assert not infractores, f"cimenta/identidad usa un hash que no es pwdlib: {sorted(infractores)}"


def test_tkt006_ca08_configuracion_por_omision() -> None:
    """TC-13 · CA-8 esc. 4 · PA-T2 — sin variables, 12 h de caducidad, 30 min de inactividad y costes sin fijar."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    configuracion = ConfiguracionIdentidad.desde_entorno({})

    assert configuracion.caducidad_absoluta == timedelta(hours=12)
    assert configuracion.caducidad_inactividad == timedelta(minutes=30)
    assert configuracion.argon2_tiempo is None
    assert configuracion.argon2_memoria_kib is None
    assert configuracion.argon2_paralelismo is None


def test_tkt006_ca08_configuracion_desde_el_entorno() -> None:
    """TC-14 · CA-8 esc. 4 — cada variable llena su campo, con el tipo y la unidad correctos."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    configuracion = ConfiguracionIdentidad.desde_entorno(
        {
            "CIMENTA_SESION_CADUCIDAD_MINUTOS": "90",
            "CIMENTA_SESION_INACTIVIDAD_MINUTOS": "10",
            "CIMENTA_ARGON2_TIEMPO": "1",
            "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
            "CIMENTA_ARGON2_PARALELISMO": "1",
        }
    )

    assert configuracion.caducidad_absoluta == timedelta(minutes=90)
    assert configuracion.caducidad_inactividad == timedelta(minutes=10)
    assert configuracion.argon2_tiempo == 1
    assert configuracion.argon2_memoria_kib == 8192
    assert configuracion.argon2_paralelismo == 1
    for entero in (
        configuracion.argon2_tiempo,
        configuracion.argon2_memoria_kib,
        configuracion.argon2_paralelismo,
    ):
        assert type(entero) is int


def test_tkt006_ca08_configuracion_una_variable_no_arrastra_a_las_otras() -> None:
    """TC-14 (complemento) · CA-8 esc. 4 — con una sola variable, las demás conservan su valor por omisión."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    configuracion = ConfiguracionIdentidad.desde_entorno(
        {"CIMENTA_SESION_INACTIVIDAD_MINUTOS": "10"}
    )

    assert configuracion.caducidad_inactividad == timedelta(minutes=10)
    assert configuracion.caducidad_absoluta == timedelta(hours=12)
    assert configuracion.argon2_tiempo is None
    assert configuracion.argon2_memoria_kib is None
    assert configuracion.argon2_paralelismo is None


@pytest.mark.parametrize("valor", ["0", "-5", "abc", "1.5", "", " 30", "１２"])
@pytest.mark.parametrize("variable", VARIABLES)
def test_tkt006_ca08_configuracion_rechaza_valores_invalidos(variable: str, valor: str) -> None:
    """TC-15 · CA-8 · PA-T8 — un valor que no es un entero positivo en ASCII detiene el arranque.

    El mensaje nombra la variable y muestra el valor con `repr`, para que quien despliega lo corrija.
    """
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    with pytest.raises(ValueError) as excepcion:
        ConfiguracionIdentidad.desde_entorno({variable: valor})

    mensaje = str(excepcion.value)
    assert variable in mensaje
    assert repr(valor) in mensaje


def test_tkt006_ca15_hash_argon2id_con_los_parametros_configurados() -> None:
    """TC-16 · CA-15 esc. 1 — el hash es Argon2id con los costes del entorno; solo la contraseña correcta verifica."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))

    derivado = contrasenas.derivar("Clave-1")

    assert derivado.startswith("$argon2id$v=19$m=8192,t=1,p=1$")
    assert "Clave-1" not in derivado
    assert contrasenas.verificar("Clave-1", derivado) is True
    assert contrasenas.verificar("Clave-2", derivado) is False


def test_tkt006_ca15_derivar_dos_veces_da_hashes_distintos() -> None:
    """TC-16 (complemento) · CA-15 esc. 1 — cada hash lleva su propia sal, y ambos verifican."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))

    primero = contrasenas.derivar("Clave-1")
    segundo = contrasenas.derivar("Clave-1")

    assert primero != segundo
    assert contrasenas.verificar("Clave-1", primero) is True
    assert contrasenas.verificar("Clave-1", segundo) is True


@pytest.mark.parametrize(
    "entorno",
    [
        pytest.param(ENTORNO_DE_PRUEBA, id="costes_de_prueba"),
        pytest.param({}, id="costes_por_omision"),
    ],
)
def test_tkt006_ca03_hash_de_descarte_con_los_mismos_parametros(entorno: dict[str, str]) -> None:
    """TC-17 · CA-3 esc. 3 — el hash de descarte cuesta lo mismo que uno real y no verifica nada.

    Si sus parámetros fueran otros, un correo inexistente respondería en un tiempo distinto de uno
    existente y el inicio de sesión revelaría qué correos están registrados.
    """
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(entorno))

    descarte = contrasenas.hash_de_descarte
    real = contrasenas.derivar("Clave-1")
    parametros_del_descarte = PARAMETROS_DEL_HASH.search(descarte)
    parametros_del_real = PARAMETROS_DEL_HASH.search(real)

    assert descarte.startswith("$argon2id$")
    assert parametros_del_descarte is not None, (
        f"el hash de descarte no trae parámetros: {descarte!r}"
    )
    assert parametros_del_real is not None, f"el hash real no trae parámetros: {real!r}"
    assert parametros_del_descarte.group(0) == parametros_del_real.group(0)
    assert contrasenas.verificar("cualquiera", descarte) is False
    assert contrasenas.verificar("Clave-1", descarte) is False


# Hashes guardados que `pwdlib` no reconoce como Argon2: texto libre, vacío, la forma de otro algoritmo y un
# Argon2 truncado que ya no cumple la forma de un hash codificado. Todos hacen lanzar `UnknownHashError`.
HASHES_QUE_NO_SON_ARGON2 = [
    pytest.param("sin-hash", id="texto_libre"),
    pytest.param("", id="vacio"),
    pytest.param("$2b$12$" + "a" * 53, id="forma_de_bcrypt"),
    pytest.param("$pbkdf2-sha256$29000$c2FsdA$aGFzaA", id="forma_de_pbkdf2"),
    pytest.param("$argon2id$v=19$m=8192", id="argon2_truncado"),
]


@pytest.mark.parametrize("hash_guardado", HASHES_QUE_NO_SON_ARGON2)
def test_tkt006_ca03_verificar_un_hash_que_no_es_argon2_devuelve_falso(hash_guardado: str) -> None:
    """Revisión ciclo 1 · F3 · CA-3 esc. 2 y 3 — rechazo: un hash guardado que no es Argon2 no verifica ni lanza.

    `pwdlib` lanza `UnknownHashError` cuando ningún hasher reconoce el hash. Si el adaptador lo deja
    pasar, `POST /api/v1/sesion` responde 500 solo para esa cuenta y 401 para las demás, y el inicio de
    sesión revela qué cuentas tienen el hash dañado. El adaptador debe devolver `False`, no lanzar.
    """
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))

    assert contrasenas.verificar("cualquiera", hash_guardado) is False


def test_tkt006_ca03_verificar_un_hash_argon2_correcto_sigue_distinguiendo() -> None:
    """Revisión ciclo 1 · F3 · CA-3, CA-15 — salvaguarda: tras tolerar hashes ajenos, uno Argon2 real sigue verificando.

    Nace en verde a propósito: fija que corregir el hallazgo no vuelve a `verificar` un «siempre falso»
    (la contraseña correcta da `True` y la errónea `False`).
    """
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))
    derivado = contrasenas.derivar("Clave-1")

    assert contrasenas.verificar("Clave-1", derivado) is True
    assert contrasenas.verificar("Clave-2", derivado) is False
