"""Ajustes del servidor, leídos del entorno y validados antes de arrancar (TKT-057, fila 11).

RNF-07: ningún secreto vive en el repositorio ni en un valor por omisión, así que la contraseña del
rol de aplicación no tiene omisión y su ausencia rechaza el arranque. CA-15 esc. 1 y 2: el servidor
solo recibe la contraseña de aplicación; las de migración y de lectura no tienen campo aquí. CA-14
y RNF-06: el origen del almacén se valida con el formato de un origen https sin ruta (http solo en
`localhost` y `127.0.0.1`, para MinIO local), para que la variable no pueda inyectar directivas en la
política de contenido ni abrirla a un origen sin cifrar.

Un mapa explícito (`cargar_ajustes(mapa)`) no lee `os.environ`: así las pruebas no dependen del
entorno del proceso. `cargar_ajustes(None)` sí lee el entorno del proceso.
"""

import re
from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

PREFIJO_VARIABLES = "CIMENTA_"
PATRON_ORIGEN = (
    r"https://[A-Za-z0-9.-]+(:[0-9]{1,5})?|http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?"
)


class ConfiguracionInvalida(RuntimeError):
    """El arranque se detiene: falta una variable obligatoria o una tiene un valor inválido.

    El mensaje nombra las variables afectadas y nunca sus valores (RNF-07).
    """


class AjustesServidor(BaseSettings):
    """Ajustes del proceso. Cada campo se lee de la variable `CIMENTA_` + su nombre en mayúsculas.

    RNF-07: `SecretStr` oculta la contraseña en `repr`, en `str` y en `model_dump_json`.
    """

    model_config = SettingsConfigDict(
        env_prefix=PREFIJO_VARIABLES,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    db_contrasena_aplicacion: SecretStr
    almacen_origen: str | None = None

    @field_validator("almacen_origen")
    @classmethod
    def validar_almacen_origen(cls, valor: str | None) -> str | None:
        """CA-14 · RNF-06 — solo un origen https sin ruta (http solo en localhost), para no inyectar la política."""
        if valor is None or re.fullmatch(PATRON_ORIGEN, valor):
            return valor
        raise ValueError("debe ser un origen https sin ruta (http solo en localhost)")


class _AjustesDesdeMapa(AjustesServidor):
    """Ajustes construidos desde un mapa explícito: solo cuentan los argumentos, nunca `os.environ`."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def cargar_ajustes(entorno: Mapping[str, str] | None) -> AjustesServidor:
    """Carga los ajustes o detiene el arranque con `ConfiguracionInvalida` (CA-15, CA-16, CA-14).

    Con `None` lee el entorno del proceso. Con un mapa, usa solo sus claves; una variable vacía
    cuenta como ausente (CA-16).
    """
    if entorno is None:
        try:
            # mypy exige el campo obligatorio en __init__; pydantic-settings lo toma del entorno.
            return AjustesServidor()  # type: ignore[call-arg]
        except ValidationError as error:
            raise ConfiguracionInvalida(_mensaje(error)) from None

    valores: dict[str, Any] = {}
    for campo in AjustesServidor.model_fields:
        valor = entorno.get(PREFIJO_VARIABLES + campo.upper())
        if valor:
            valores[campo] = valor
    try:
        return _AjustesDesdeMapa(**valores)
    except ValidationError as error:
        raise ConfiguracionInvalida(_mensaje(error)) from None


def _mensaje(error: ValidationError) -> str:
    """Nombra las variables afectadas, ordenadas, y nunca sus valores.

    `error.errors()` conserva el valor de entrada (`input`): aquí solo se lee `loc`.
    """
    variables = sorted({PREFIJO_VARIABLES + str(e["loc"][0]).upper() for e in error.errors()})
    return (
        f"Configuración incompleta o inválida: {', '.join(variables)}. "
        "Defínelas en el entorno; las claves están en .env.example."
    )
