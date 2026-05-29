"""Seed the help offices a borrower picks from during onboarding.

The choose-office step is required and its dropdown is populated from the
``HelpOffice`` table, so a database with no offices leaves a signed-up visitor
unable to finish onboarding. Nothing else populated the table, so a fresh
deploy shipped an empty dropdown. Seed a small set here so any freshly-migrated
database (deploy, CI, a new developer's) can complete the journey.
"""

from django.db import migrations

_OFFICES = [
    {"name": "Central", "city": "Brussels", "address": "Rue de la Loi 1, 1000 Brussels"},
    {"name": "Flanders North", "city": "Antwerp", "address": "Meir 24, 2000 Antwerp"},
    {"name": "Ghent Office", "city": "Ghent", "address": "Korenmarkt 10, 9000 Ghent"},
    {"name": "Wallonia South", "city": "Namur", "address": "Place d'Armes 5, 5000 Namur"},
]


def seed_offices(apps, schema_editor):
    HelpOffice = apps.get_model("portal", "HelpOffice")
    for office in _OFFICES:
        HelpOffice.objects.get_or_create(name=office["name"], city=office["city"], defaults=office)


def unseed_offices(apps, schema_editor):
    HelpOffice = apps.get_model("portal", "HelpOffice")
    for office in _OFFICES:
        HelpOffice.objects.filter(name=office["name"], city=office["city"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0002_alter_expenseline_options_alter_incomeline_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_offices, unseed_offices),
    ]
