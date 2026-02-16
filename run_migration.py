#!/usr/bin/env python
import os
import sys
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Run makemigrations with input
try:
    call_command('makemigrations')
except:
    pass
