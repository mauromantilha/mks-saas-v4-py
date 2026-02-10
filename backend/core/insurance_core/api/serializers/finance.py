from rest_framework import serializers

class InstallmentPreviewSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    due_date = serializers.DateField()
    original_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    new_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    delta = serializers.DecimalField(max_digits=14, decimal_places=2)