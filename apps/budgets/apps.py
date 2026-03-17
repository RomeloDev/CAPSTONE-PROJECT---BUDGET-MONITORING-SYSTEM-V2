from django.apps import AppConfig


class BudgetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.budgets'

    def ready(self):
        # Import signal handlers so Django can register them.
        import apps.budgets.signals  # noqa: F401
