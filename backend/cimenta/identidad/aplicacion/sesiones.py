"""Casos de uso de sesión de identidad (TKT-006): `abrir_sesion`, `validar_sesion` y
`cerrar_sesion_vigente`. Cada caso de uso abre su propia
transacción con `fabrica_sesiones().begin()`: el repositorio no confirma, y el rechazo se lanza
siempre fuera del bloque, para que la fila de `intento_acceso` quede confirmada (TC-27).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, UsuarioAutenticado
from cimenta.identidad.dominio.acceso import credenciales_aceptadas
from cimenta.identidad.dominio.correo import normalizar_correo
from cimenta.identidad.dominio.limite_intentos import EstadoLimite, evaluar_limite
from cimenta.identidad.dominio.vigencia import EstadoSesion, evaluar_vigencia
from cimenta.identidad.infraestructura import repositorio
from contrato_error import LimiteIntentosExcedido, SesionInvalida

_registro = structlog.get_logger("cimenta.identidad")

MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_SESION_CADUCADA = "La sesión caducó. Inicia sesión de nuevo."
MENSAJE_SESION_REVOCADA = "La sesión ya no es válida. Inicia sesión de nuevo."
MENSAJE_CREDENCIALES_INVALIDAS = "El correo o la contraseña no son correctos."
MENSAJE_LIMITE_INTENTOS = (
    "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo."
)


def _microsegundos(instante: datetime, ahora: datetime) -> int:
    return (instante - ahora) // timedelta(microseconds=1)


def _estado_del_limite(
    sesion_bd: Session,
    configuracion: ConfiguracionIdentidad,
    *,
    correo: str,
    origen_ip: str,
    ahora: datetime,
) -> EstadoLimite:
    """RNF-04. Lee los fallos y convierte los instantes a microsegundos relativos a `ahora`;
    la decisión es de `evaluar_limite`."""
    desde = ahora - 2 * configuracion.limite_ventana
    fallos_cuenta = repositorio.fallos_de_correo(sesion_bd, correo, desde=desde, hasta=ahora)
    ultimo_exito = repositorio.ultimo_exito_de_correo(sesion_bd, correo, hasta=ahora)
    fallos_origen = repositorio.fallos_de_origen(sesion_bd, origen_ip, desde=desde, hasta=ahora)
    return evaluar_limite(
        fallos_cuenta=[_microsegundos(f, ahora) for f in fallos_cuenta],
        ultimo_exito_cuenta=None if ultimo_exito is None else _microsegundos(ultimo_exito, ahora),
        fallos_origen=[_microsegundos(f, ahora) for f in fallos_origen],
        umbral_cuenta=configuracion.limite_fallos_cuenta,
        umbral_origen=configuracion.limite_fallos_origen,
        ventana=configuracion.limite_ventana // timedelta(microseconds=1),
    )


def _asentar_rechazo_por_bloqueo(
    sesion_bd: Session, *, correo: str, origen_ip: str, ahora: datetime
) -> None:
    """RNF-04: asienta el intento rechazado por bloqueo, sin credenciales verificadas, para que no
    cuente como fallo ni engorde los índices parciales."""
    repositorio.insertar_intento(
        sesion_bd,
        email=correo,
        usuario_id=None,
        exitoso=False,
        credenciales_verificadas=False,
        ocurrido_en=ahora,
        origen_ip=origen_ip,
    )


def _bloquear_si_el_fallo_dispara_el_limite(
    sesion_bd: Session,
    configuracion: ConfiguracionIdentidad,
    *,
    usuario_id: uuid.UUID,
    correo: str,
    origen_ip: str,
    ahora: datetime,
) -> None:
    """RNF-04: tras un fallo con credenciales verificadas de una cuenta real, recalcula el estado y,
    si ese fallo dispara el límite de la cuenta, fija `bloqueado_hasta`."""
    nuevo_estado = _estado_del_limite(
        sesion_bd, configuracion, correo=correo, origen_ip=origen_ip, ahora=ahora
    )
    if nuevo_estado.disparo_cuenta is not None:
        repositorio.fijar_bloqueado_hasta(
            sesion_bd,
            usuario_id,
            ahora
            + timedelta(microseconds=nuevo_estado.disparo_cuenta)
            + configuracion.limite_ventana,
        )


def abrir_sesion(
    contexto: ContextoIdentidad,
    *,
    correo_escrito: str,
    contrasena: str,
    origen_ip: str,
    agente_usuario: str | None,
) -> UsuarioAutenticado:
    """M2 · RNF-03 · RNF-04. Comprueba el bloqueo antes de buscar la credencial y de Argon2; si no
    hay bloqueo, verifica exactamente un hash, exista o no el correo. Una sola transacción que se
    confirma antes de lanzar el 401 o el 429: lanzar dentro del bloque desharía la fila."""
    configuracion = contexto.configuracion
    correo = normalizar_correo(correo_escrito)
    abierta: UsuarioAutenticado | None = None
    reintentar_en_s = 0
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        repositorio.bloquear_correo(sesion_bd, correo)
        # Con el candado ya tomado, el reloj no puede ir por detrás de la fila de un intento
        # anterior: otra transacción pudo escribirla justo antes de soltar el mismo candado.
        ahora = contexto.reloj()
        estado = _estado_del_limite(
            sesion_bd, configuracion, correo=correo, origen_ip=origen_ip, ahora=ahora
        )
        if estado.bloqueado:
            _asentar_rechazo_por_bloqueo(sesion_bd, correo=correo, origen_ip=origen_ip, ahora=ahora)
            reintentar_en_s = estado.reintentar_en_s
        else:
            credencial = repositorio.buscar_credencial(sesion_bd, correo)
            hash_a_verificar = (
                credencial.password_hash
                if credencial is not None
                else contexto.contrasenas.hash_de_descarte
            )
            coincide = contexto.contrasenas.verificar(contrasena, hash_a_verificar)
            aceptadas = credenciales_aceptadas(
                existe=credencial is not None,
                activo=credencial is not None and credencial.activo,
                coincide=coincide,
            )
            repositorio.insertar_intento(
                sesion_bd,
                email=correo,
                usuario_id=credencial.id if credencial is not None else None,
                exitoso=aceptadas,
                credenciales_verificadas=True,
                ocurrido_en=ahora,
                origen_ip=origen_ip,
            )
            if aceptadas and credencial is not None:
                sesion_id = uuid.uuid4()
                expira_en = ahora + configuracion.caducidad_absoluta
                repositorio.insertar_sesion(
                    sesion_bd,
                    sesion_id=sesion_id,
                    usuario_id=credencial.id,
                    ahora=ahora,
                    expira_en=expira_en,
                    origen_ip=origen_ip,
                    agente_usuario=agente_usuario,
                )
                repositorio.marcar_ultimo_acceso(sesion_bd, credencial.id, ahora)
                abierta = UsuarioAutenticado(
                    usuario_id=credencial.id,
                    sesion_id=sesion_id,
                    nombre=credencial.nombre,
                    email=credencial.email,
                    roles=repositorio.roles_de(sesion_bd, credencial.id),
                    expira_en=expira_en,
                    expira_por_inactividad_en=ahora + configuracion.caducidad_inactividad,
                )
            elif credencial is not None:
                _bloquear_si_el_fallo_dispara_el_limite(
                    sesion_bd,
                    configuracion,
                    usuario_id=credencial.id,
                    correo=correo,
                    origen_ip=origen_ip,
                    ahora=ahora,
                )
    if reintentar_en_s > 0:
        raise LimiteIntentosExcedido(
            mensaje=MENSAJE_LIMITE_INTENTOS, reintentar_en_s=reintentar_en_s
        )
    if abierta is None:
        raise SesionInvalida(
            motivo="CREDENCIALES_INVALIDAS", mensaje=MENSAJE_CREDENCIALES_INVALIDAS
        )
    return abierta


def validar_sesion(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> UsuarioAutenticado:
    """M5 · M6 · M7 · RNF-01. Lee la sesión, el usuario y los roles en cada petición, sin caché.
    Si sigue vigente desliza ultima_actividad con una guarda contra un cierre concurrente."""
    ahora = contexto.reloj()
    inactividad = contexto.configuracion.caducidad_inactividad
    estado: EstadoSesion | None = None
    autenticado: UsuarioAutenticado | None = None
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio.leer_sesion(sesion_bd, sesion_id)
        if fila is not None:
            estado = evaluar_vigencia(
                ahora=ahora,
                expira_en=fila.expira_en,
                vence_por_inactividad_en=fila.ultima_actividad + inactividad,
                revocada=fila.revocada_en is not None,
                usuario_activo=fila.usuario_activo,
            )
            if estado is EstadoSesion.VIGENTE and not repositorio.tocar_sesion(
                sesion_bd, sesion_id, ahora
            ):
                estado = EstadoSesion.REVOCADA
            if estado is EstadoSesion.VIGENTE:
                autenticado = UsuarioAutenticado(
                    usuario_id=fila.usuario_id,
                    sesion_id=sesion_id,
                    nombre=fila.nombre,
                    email=fila.email,
                    roles=repositorio.roles_de(sesion_bd, fila.usuario_id),
                    expira_en=fila.expira_en,
                    expira_por_inactividad_en=ahora + inactividad,
                )
    if estado is None:
        raise SesionInvalida(motivo="SIN_SESION", mensaje=MENSAJE_SIN_SESION)
    if estado is EstadoSesion.CADUCADA:
        raise SesionInvalida(motivo="SESION_CADUCADA", mensaje=MENSAJE_SESION_CADUCADA)
    if autenticado is None:
        raise SesionInvalida(motivo="SESION_REVOCADA", mensaje=MENSAJE_SESION_REVOCADA)
    return autenticado


def registrar_rechazo_de_origen(
    contexto: ContextoIdentidad,
    *,
    correo_escrito: str,
    origen_ip: str,
    metodo: str,
    ruta: str,
) -> None:
    """M4 · CA-11 esc. 3 · CA-R2. Asienta el rechazo anónimo de `POST /sesion` sin par CSRF válido:
    una fila de `intento_acceso` con el correo normalizado, sin usuario y sin verificar credenciales.
    No lee el usuario ni verifica ninguna contraseña. Transacción propia; la línea técnica sale ya
    fuera del bloque, con la transacción confirmada."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        repositorio.insertar_intento(
            sesion_bd,
            email=normalizar_correo(correo_escrito),
            usuario_id=None,
            exitoso=False,
            credenciales_verificadas=False,
            ocurrido_en=contexto.reloj(),
            origen_ip=origen_ip,
        )
    _registro.warning("origen_no_verificado", metodo=metodo, ruta=ruta)


def cerrar_sesion_vigente(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> None:
    """M4: escribe revocada_en; nunca borra la fila. Si un cierre concurrente ganó, no hace nada."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        repositorio.revocar_sesion(sesion_bd, sesion_id, contexto.reloj())
