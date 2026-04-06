import logging

from celery import shared_task

logger = logging.getLogger(__name__)

_LOCK_EXPIRE = 55 * 60  # 55 minutos — expira antes da próxima execução horária


def _acquire_lock(cache, lock_key: str) -> bool:
    """Tenta adquirir lock no Redis. Retorna True se bem-sucedido."""
    return cache.add(lock_key, "1", _LOCK_EXPIRE)


@shared_task
def process_pending_withdrawals():
    """
    Hourly task: attempt to process any withdrawal still in PENDING state.

    Uses a Redis lock to prevent concurrent executions (e.g. if a task
    runs longer than the beat interval).
    """
    from django.core.cache import cache

    from .models import Withdrawal
    from .services import process_withdrawal

    lock_key = "lock:process_pending_withdrawals"
    if not _acquire_lock(cache, lock_key):
        logger.warning("process_pending_withdrawals: already running, skipping")
        return "Skipped (lock held)"

    try:
        pending_ids = list(
            Withdrawal.objects.filter(status=Withdrawal.Status.PENDING)
            .values_list("id", flat=True)
        )

        processed = 0
        for wid in pending_ids:
            result = process_withdrawal(str(wid))
            if result:
                processed += 1

        logger.info("process_pending_withdrawals: processed %d withdrawals", processed)
        return f"Processed {processed} withdrawals"
    finally:
        cache.delete(lock_key)


@shared_task
def poll_processing_withdrawals():
    """
    Every 15 minutes: query Mercado Pago for the status of PROCESSING withdrawals
    and mark them as COMPLETED or FAILED.

    A withdrawal stays PROCESSING after _send_pix_transfer() creates the transfer
    in MP. This task closes the loop by polling the MP transfer endpoint until
    MP confirms settlement or rejection.
    """
    from django.core.cache import cache

    from .models import Withdrawal
    from .services import poll_transfer_status

    lock_key = "lock:poll_processing_withdrawals"
    if not _acquire_lock(cache, lock_key):
        logger.warning("poll_processing_withdrawals: already running, skipping")
        return "Skipped (lock held)"

    try:
        processing_ids = list(
            Withdrawal.objects.filter(status=Withdrawal.Status.PROCESSING)
            .exclude(mp_transfer_id="")
            .values_list("id", flat=True)
        )

        polled = 0
        for wid in processing_ids:
            poll_transfer_status(str(wid))
            polled += 1

        logger.info("poll_processing_withdrawals: polled %d withdrawals", polled)
        return f"Polled {polled} withdrawals"
    finally:
        cache.delete(lock_key)
