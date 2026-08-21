from django.core.management.base import BaseCommand
from forums.models import Forum, generate_forum_id


class Command(BaseCommand):
    help = 'Generate forum_id for forums that dont have one'

    def handle(self, *args, **options):
        forums_without_id = Forum.objects.exclude(forum_id__regex=r'^[A-Z]{2}[0-9]{4}$')
        count = 0

        for forum in forums_without_id:
            forum.forum_id = generate_forum_id()
            forum.save()
            count += 1
            self.stdout.write(self.style.SUCCESS(f'Forum "{forum.name}" now has ID: {forum.forum_id}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully generated IDs for {count} forums'))
