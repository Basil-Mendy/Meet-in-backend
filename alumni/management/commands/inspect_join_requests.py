from django.core.management.base import BaseCommand
from alumni.models import SchoolJoinRequest

class Command(BaseCommand):
    help = 'Print recent SchoolJoinRequest records'

    def handle(self, *args, **options):
        qs = SchoolJoinRequest.objects.select_related('user','forum').order_by('-requested_at')[:20]
        for jr in qs:
            user_email = jr.user.email if jr.user and getattr(jr.user, 'email', None) else str(jr.user_id)
            forum_name = jr.forum.name if jr.forum else str(jr.forum_id)
            self.stdout.write(f"{jr.id} | {user_email} | {forum_name} | {jr.status} | {jr.requested_at.isoformat()}")
        self.stdout.write('TOTAL: %s' % SchoolJoinRequest.objects.count())
