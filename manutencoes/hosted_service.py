import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from threading import Event, Lock, Thread

from django.conf import settings
from django.core.mail import send_mail
from django.db import close_old_connections, transaction
from django.utils import timezone


logger = logging.getLogger(__name__)


@dataclass
class ResultadoEnvioAvisos:
    encontrados: int = 0
    enviados: int = 0
    falhas: int = 0


def enviar_avisos_revisao(data_base=None):
    from .models import Manutencao

    data_base = data_base or timezone.localdate()
    data_limite = data_base + timedelta(days=_dias_antecedencia())
    resultado = ResultadoEnvioAvisos()

    # Todas as revisões de hoje até o limite que ainda não foram avisadas (e não só as do dia exato):
    # assim uma revisão cadastrada em cima da hora, ou um dia com o site fora do ar, não fica sem aviso.
    # Cada manutenção é avisada uma vez só; ao mudar a data da revisão, o aviso volta a valer (Manutencao.save).
    manutencoes_ids = list(
        Manutencao.objects
        .filter(
            data_proxima_manutencao__range=(data_base, data_limite),
            email_aviso_revisao_enviado=False,
        )
        .values_list('id', flat=True)
    )
    resultado.encontrados = len(manutencoes_ids)

    for manutencao_id in manutencoes_ids:
        try:
            with transaction.atomic():
                manutencao = (
                    Manutencao.objects
                    .select_for_update()
                    .select_related('veiculo__cliente')
                    .get(pk=manutencao_id)
                )

                # Confere de novo com o registro travado: pode ter mudado desde a busca acima
                if (
                    manutencao.email_aviso_revisao_enviado
                    or manutencao.data_proxima_manutencao is None
                    or not data_base <= manutencao.data_proxima_manutencao <= data_limite
                ):
                    continue

                _enviar_email_manutencao(manutencao)
                manutencao.email_aviso_revisao_enviado = True
                manutencao.save(update_fields=['email_aviso_revisao_enviado'])
                resultado.enviados += 1
        except Exception:
            logger.exception('Falha ao enviar aviso de revisão da manutenção %s.', manutencao_id)
            resultado.falhas += 1

    return resultado


class AvisoRevisaoHostedService:
    def __init__(self):
        self._lock = Lock()
        self._stop_event = Event()
        self._thread = None
        self._ultima_execucao = None

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = Thread(
                target=self._executar_loop,
                name='aviso-revisao-email-service',
                daemon=True,
            )
            self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _executar_loop(self):
        logger.info('Serviço de aviso de revisão por e-mail iniciado.')

        while not self._stop_event.is_set():
            try:
                agora = timezone.localtime()
                proxima_execucao = self._proxima_execucao(agora)
                segundos_espera = max(0, (proxima_execucao - agora).total_seconds())

                if self._stop_event.wait(segundos_espera):
                    break

                data_execucao = timezone.localdate()
                close_old_connections()
                resultado = enviar_avisos_revisao(data_base=data_execucao)
                self._ultima_execucao = data_execucao

                logger.info(
                    'Avisos de revisão processados: encontrados=%s enviados=%s falhas=%s.',
                    resultado.encontrados,
                    resultado.enviados,
                    resultado.falhas,
                )
            except Exception:
                logger.exception('Erro inesperado no serviço de aviso de revisão por e-mail.')
                self._stop_event.wait(30 * 60)
            finally:
                close_old_connections()

    def _proxima_execucao(self, agora):
        horario = _horario_envio()
        fuso = timezone.get_current_timezone()
        hoje = agora.date()
        execucao_hoje = timezone.make_aware(datetime.combine(hoje, horario), fuso)

        if self._ultima_execucao == hoje:
            return timezone.make_aware(datetime.combine(hoje + timedelta(days=1), horario), fuso)

        if agora >= execucao_hoje:
            return agora

        return execucao_hoje


def _enviar_email_manutencao(manutencao):
    cliente = manutencao.veiculo.cliente
    if not cliente.email:
        raise ValueError(f'Cliente {cliente.pk} não possui e-mail cadastrado.')

    send_mail(
        subject=getattr(settings, 'AVISO_REVISAO_EMAIL_ASSUNTO', 'Lembrete de revisão do veículo'),
        message=_montar_mensagem(manutencao),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[cliente.email],
        fail_silently=False,
    )


def _montar_mensagem(manutencao):
    cliente = manutencao.veiculo.cliente
    veiculo = manutencao.veiculo
    data_revisao = manutencao.data_proxima_manutencao.strftime('%d/%m/%Y')

    return (
        f'Olá, {cliente.nome}.\n\n'
        f'A próxima revisão do veículo {veiculo.marca} {veiculo.modelo} '
        f'({veiculo.placa}) está prevista para {data_revisao}.\n\n'
        'Entre em contato conosco para agendar o melhor horário.\n\n'
        'Atenciosamente,\n'
        'FlowMigao'
    )


def _horario_envio():
    valor = getattr(settings, 'AVISO_REVISAO_EMAIL_HORARIO_ENVIO', '08:00')

    if isinstance(valor, time):
        return valor

    try:
        hora, minuto = str(valor).split(':')[:2]
        return time(hour=int(hora), minute=int(minuto))
    except (TypeError, ValueError):
        logger.warning(
            'Horário de envio de aviso de revisão inválido (%s). Usando 08:00.',
            valor,
        )
        return time(hour=8, minute=0)


def _dias_antecedencia():
    valor = getattr(settings, 'AVISO_REVISAO_EMAIL_DIAS_ANTECEDENCIA', 7)

    try:
        return int(valor)
    except (TypeError, ValueError):
        logger.warning(
            'Dias de antecedência para aviso de revisão inválido (%s). Usando 7.',
            valor,
        )
        return 7


_servico_aviso_revisao = AvisoRevisaoHostedService()


def iniciar_servico_aviso_revisao():
    _servico_aviso_revisao.start()
