from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Send a test email to verify SMTP configuration.'

    def add_arguments(self, parser):
        parser.add_argument('recipient', help='Email address to send the test to')

    def handle(self, *args, **options):
        recipient = options['recipient']
        self.stdout.write(f'Sending test email to {recipient} via {settings.EMAIL_HOST} ...')
        try:
            send_mail(
                subject='CLM One — SMTP test',
                message='If you received this, outbound email is working correctly.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f'Sent. Check {recipient}.'))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Failed: {exc}'))
            raise SystemExit(1)
