"""Translate Variant objects into the JSON shape the brief specifies."""

from rest_framework import serializers


class VariantSerializer(serializers.Serializer):
    """The five fields the brief exposes, keyed by their VCF column names."""

    CHROM = serializers.CharField(source="chrom")
    POS = serializers.IntegerField(source="pos")
    ID = serializers.CharField(source="id", allow_null=True)
    REF = serializers.CharField(source="ref")
    ALT = serializers.CharField(source="alt")

class VariantWriteSerializer(serializers.Serializer):
    """Shape of an incoming variant. Domain rules live in vcf_core.validation."""

    CHROM = serializers.CharField()
    POS = serializers.IntegerField()
    ID = serializers.CharField()
    REF = serializers.CharField()
    ALT = serializers.CharField()
