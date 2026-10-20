from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from query_agent.exceptions import (
    AgentError,
    ConfigurationError,
    QueryRepairExhaustedError,
    UnsafeSQLError,
)
from query_agent.serializers import QueryRequestSerializer
from query_agent.services import TextToSQLAgent


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "service": "text-to-sql-agent"})


class QueryAgentView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        serializer = QueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = TextToSQLAgent().run(serializer.validated_data["question"])
        except ConfigurationError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except UnsafeSQLError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except QueryRepairExhaustedError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except AgentError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_200_OK)


class SchemaView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        try:
            schema = TextToSQLAgent().introspect_schema()
        except ConfigurationError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({"schema": schema})
