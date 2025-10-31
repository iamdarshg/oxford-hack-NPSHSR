from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from messengersecret.models import Message, Contact

User = get_user_model()


class Command(BaseCommand):
    help = 'Backfill Contact rows from existing Message records'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for m in Message.objects.exclude(receiver__isnull=True).exclude(receiver__exact=''):
            sender = User.objects.filter(username=m.sender).first()
            receiver = User.objects.filter(username=m.receiver).first()
            if sender and receiver:
                c1, ok1 = Contact.objects.get_or_create(user=sender, contact=receiver)
                c2, ok2 = Contact.objects.get_or_create(user=receiver, contact=sender)
                if ok1 or ok2:
                    created += (1 if ok1 else 0) + (1 if ok2 else 0)
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f'Backfill complete: created {created} contact rows, skipped {skipped} messages'))
