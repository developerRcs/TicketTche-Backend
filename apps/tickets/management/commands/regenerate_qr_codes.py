"""
Management command: regenerate_qr_codes

Regenerates all ticket QR codes using the new HMAC-SHA256 signing scheme.
Must be run ONCE after deploying the FINDING-002 security fix.

Usage:
    python manage.py regenerate_qr_codes
    python manage.py regenerate_qr_codes --batch-size 50
    python manage.py regenerate_qr_codes --dry-run
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Regenerate all ticket QR codes using the new HMAC-SHA256 signing key (run once after security patch)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of tickets to process per batch (default: 100)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count tickets without regenerating",
        )

    def handle(self, *args, **options):
        from apps.tickets.models import Ticket

        qs = Ticket.objects.exclude(status=Ticket.Status.CANCELLED)
        total = qs.count()

        if options["dry_run"]:
            self.stdout.write(f"[DRY RUN] Would regenerate QR codes for {total} tickets.")
            return

        self.stdout.write(f"Regenerating QR codes for {total} tickets...")

        batch_size = options["batch_size"]
        updated = 0
        errors = 0

        ids = list(qs.values_list("id", flat=True))
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            for ticket in Ticket.objects.filter(id__in=batch_ids):
                try:
                    # Delete old QR file from storage before regenerating
                    if ticket.qr_code:
                        ticket.qr_code.delete(save=False)
                    ticket.generate_qr_code()
                    ticket.save(update_fields=["qr_code"])
                    updated += 1
                except Exception as exc:
                    errors += 1
                    self.stderr.write(f"  ERROR ticket {ticket.id}: {exc}")

            self.stdout.write(f"  {min(i + batch_size, total)}/{total} processed...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated: {updated}, Errors: {errors}. "
                "Users must re-download their tickets to get new QR codes."
            )
        )
