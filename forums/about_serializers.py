"""Serializers for Forum About tab and document uploads"""
from rest_framework import serializers
from .models import Forum, ForumDocument, ForumSettings, BankAccount


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            'id', 'account_holder_name', 'account_number',
            'bank_name', 'bank_code', 'is_verified', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_verified']


class ForumDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ForumDocument
        fields = [
            'id', 'title', 'file', 'file_type', 'uploaded_by',
            'uploaded_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'uploaded_by']

    def get_uploaded_by_name(self, obj):
        return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}" if obj.uploaded_by else "Unknown"


class ForumSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForumSettings
        fields = [
            'id', 'visibility', 'join_mode', 'payment_rules',
            'rules_regulations', 'objectives', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ForumAboutSerializer(serializers.ModelSerializer):
    """Complete Forum information for About tab"""
    settings = ForumSettingsSerializer(required=False)
    documents = ForumDocumentSerializer(many=True, required=False)
    bank_account = BankAccountSerializer(required=False)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Forum
        fields = [
            'id', 'forum_id', 'name', 'slogan', 'motto', 'description',
            'address', 'email', 'phone', 'profile_picture', 'logo',
            'objectives_rules', 'is_verified', 'is_completed', 'is_searchable',
            'created_at', 'created_by', 'created_by_name',
            'settings', 'documents', 'bank_account'
        ]
        read_only_fields = [
            'id', 'forum_id', 'is_verified', 'is_completed',
            'created_at', 'created_by', 'created_by_name'
        ]

    def get_created_by_name(self, obj):
        return f"{obj.created_by.first_name} {obj.created_by.last_name}" if obj.created_by else "Unknown"
