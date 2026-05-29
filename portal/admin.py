"""Admin surfaces — the reviewer's window onto applications and documents.

Applications expose their guarded FSM (``start_review``, ``approve``,
``reject``) as change-page actions via ``FSMAdminMixin``; the transitions'
own ``permission=`` still gates who may decide (``FSM_ADMIN_FORCE_PERMIT`` in
settings lets the buttons render for permitted reviewers).
"""

from collections.abc import Mapping
from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django_fsm import has_transition_perm
from django_fsm.admin import FSMAdminMixin

from portal.models import (
    Application,
    BorrowerProfile,
    Document,
    DocumentAnalysis,
    ExpenseLine,
    HelpOffice,
    IncomeLine,
    Simulation,
)


@admin.register(HelpOffice)
class HelpOfficeAdmin(admin.ModelAdmin):
    list_display = ["name", "city"]
    search_fields = ["name", "city"]


@admin.register(BorrowerProfile)
class BorrowerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "help_office", "phone_verified", "created_at"]
    list_filter = ["phone_verified", "help_office"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["user", "help_office"]


class IncomeLineInline(admin.TabularInline):
    model = IncomeLine
    extra = 0


class ExpenseLineInline(admin.TabularInline):
    model = ExpenseLine
    extra = 0


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ["reference", "state", "purpose", "property_price", "user", "created_at"]
    list_filter = ["state", "purpose", "region", "property_type", "property_usage"]
    search_fields = ["reference", "user__username"]
    date_hierarchy = "created_at"
    readonly_fields = ["state", "reference", "created_at", "updated_at"]
    list_select_related = ["user"]
    inlines = [IncomeLineInline, ExpenseLineInline]


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ["state", "kind", "original_filename", "uploaded_at"]
    can_delete = False
    show_change_link = True


@admin.register(Application)
class ApplicationAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ["state"]
    list_display = ["reference", "state", "user", "employment_status", "submitted_at", "decided_at"]
    list_filter = ["state", "employment_status", "submitted_at", "decided_at"]
    search_fields = ["reference", "last_name", "national_number", "user__username"]
    date_hierarchy = "created_at"
    readonly_fields = ["user", "reference", "simulation", "created_at", "updated_at", "submitted_at", "decided_at"]
    list_select_related = ["user", "simulation"]
    inlines = [DocumentInline]

    def _apply_fsm_transition(  # ty: ignore[invalid-method-override]
        self,
        *,
        obj: Application,
        transition_name: str,
        request: HttpRequest,
        kwargs: Mapping[str, Any] | None = None,
    ) -> bool:
        # The mixin only hides buttons by permission; the POST path runs the
        # transition without rechecking it, so a forged POST could otherwise
        # decide an application without the decide permission. Re-enforce it.
        transition_method = getattr(obj, transition_name, None)
        if not callable(transition_method) or not has_transition_perm(transition_method, request.user):
            self.message_user(request, "You are not allowed to run that transition.", level=messages.ERROR)
            raise PermissionDenied
        return super()._apply_fsm_transition(obj=obj, transition_name=transition_name, request=request, kwargs=kwargs)


class DocumentAnalysisInline(admin.StackedInline):
    model = DocumentAnalysis
    extra = 0
    can_delete = False
    readonly_fields = [
        "detected_kind",
        "summary",
        "extracted_fields",
        "mismatches",
        "is_stub",
        "model_used",
        "created_at",
    ]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "kind", "state", "application", "uploaded_at"]
    list_filter = ["state", "kind", "uploaded_at"]
    search_fields = ["original_filename", "application__reference"]
    date_hierarchy = "uploaded_at"
    readonly_fields = ["state", "uploaded_at"]
    list_select_related = ["application"]
    inlines = [DocumentAnalysisInline]


@admin.register(DocumentAnalysis)
class DocumentAnalysisAdmin(admin.ModelAdmin):
    list_display = ["document", "detected_kind", "is_stub", "model_used", "created_at"]
    list_filter = ["is_stub", "detected_kind"]
    search_fields = ["document__original_filename"]
    readonly_fields = ["created_at"]
    list_select_related = ["document"]
