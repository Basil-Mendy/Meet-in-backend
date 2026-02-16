import string
import random
from django.core.management.base import BaseCommand
from forums.models import Forum


class Command(BaseCommand):
    help = 'Generate forum_id for forums that dont have one'

    def handle(self, *args, **options):
        forums_without_id = Forum.objects.filter(forum_id__isnull=True) | Forum.objects.filter(forum_id='')
        count = 0

        for forum in forums_without_id:
            # Generate unique forum_id
            while True:
                forum_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
                if not Forum.objects.filter(forum_id=forum_id).exists():
                    break
            
            forum.forum_id = forum_id
            forum.save()
            count += 1
            self.stdout.write(self.style.SUCCESS(f'✓ Forum "{forum.name}" now has ID: {forum_id}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully generated IDs for {count} forums'))
