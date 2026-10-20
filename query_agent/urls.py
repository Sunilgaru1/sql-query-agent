from django.urls import path

from query_agent.views import HealthView, QueryAgentView, SchemaView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("query/", QueryAgentView.as_view(), name="query-agent"),
    path("schema/", SchemaView.as_view(), name="schema"),
]
