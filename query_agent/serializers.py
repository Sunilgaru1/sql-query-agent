from rest_framework import serializers


class QueryRequestSerializer(serializers.Serializer):
    question = serializers.CharField(
        min_length=3,
        max_length=2000,
        trim_whitespace=True,
        help_text="Natural-language question to translate into SQL.",
    )
