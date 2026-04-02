import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def process_pending_withdrawals():
    """
    Hourly task: attempt to process any withdrawal still in PENDING state.
    """
    from .models import Withdrawal
    from .services import process_withdrawal

    pending_ids = list(
        Withdrawal.objects.filter(status=Withdrawal.Status.PENDING).values_list("id", flat=True)
    )

    processed = 0
    for wid in pending_ids:
        result = process_withdrawal(str(wid))
        if result:
            processed += 1

    logger.info("process_pending_withdrawals: processed %d withdrawals", processed)
    return f"Processed {processed} withdrawals"
