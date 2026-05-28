"""Admin surfaces — the reviewer's window onto applications and documents."""

from django.contrib import admin

from portal.models import Application, Document, DocumentAnalysis, HelpOffice, Simulation


@admin.register(HelpOffice)
class HelpOfficeAdmin(admin.ModelAdmin):
    list_display = ["name", "city"]
    search_fields = ["name", "city"]


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ["reference", "state", "purpose", "property_price", "user", "created_at"]
    list_filter = ["state", "purpose", "region"]
    search_fields = ["reference"]
    readonly_fields = ["state", "reference", "created_at", "updated_at"]


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ["state", "kind", "original_filename", "uploaded_at"]
    can_delete = False
    show_change_link = True


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["reference", "state", "user", "submitted_at", "decided_at"]
    list_filter = ["state"]
    search_fields = ["reference", "last_name", "national_number"]
    readonly_fields = ["state", "reference", "simulation", "created_at", "updated_at", "submitted_at", "decided_at"]
    inlines = [DocumentInline]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "kind", "state", "application", "uploaded_at"]
    list_filter = ["state", "kind"]
    readonly_fields = ["state", "uploaded_at"]


@admin.register(DocumentAnalysis)
class DocumentAnalysisAdmin(admin.ModelAdmin):
    list_display = ["document", "detected_kind", "is_stub", "model_used", "created_at"]
    list_filter = ["is_stub", "detected_kind"]
    readonly_fields = ["created_at"]
