import os

from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunServerCommand,
)


class Command(RunServerCommand):
    def handle(self, *args, **options):
        # Added linebreak to split server output on autoreload.
        print("\nK8S CURRENTLY RUNNING", os.environ.get("ENVIRONMENT"))
        return super().handle(*args, **options)

    def check(self, *args, **kwargs):
        # Needed to overwrite misleading "Performing system checks" output.
        self.stdout.write("\u001b[2AGotta go fast- skipping all checks!")
        self.stdout.write(self.style.WARNING("System checks skipped."))

    def check_migrations(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Migration checks skipped."))
