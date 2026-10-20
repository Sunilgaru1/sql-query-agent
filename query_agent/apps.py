from django.apps import AppConfig


class QueryAgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "query_agent"
    verbose_name = "Text-to-SQL Query Agent"
