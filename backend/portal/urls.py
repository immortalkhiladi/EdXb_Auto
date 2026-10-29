from django.urls import path

from .tools import TOOLS
from .views import admin_api, auth, common, documents, process, tools

urlpatterns = [
    path("health", common.health),
    path("linkedin-updates", common.linkedin_updates),
    path("auth/csrf", auth.csrf),
    path("auth/login", auth.login_view),
    path("auth/logout", auth.logout_view),
    path("auth/me", auth.me),
    path("auth/mfa/setup", auth.mfa_setup),
    path("auth/mfa/verify", auth.mfa_verify),
    path("auth/change-password", auth.change_password),
    path("auth/forgot-password", auth.forgot_password),
    path("auth/reset-password", auth.reset_password),
    *[path(f"process/{slug}", process.make_view(slug)) for slug in TOOLS],
    path("documents", documents.list_documents),
    path("documents/<str:document_id>", documents.document_detail),
    path("documents/<str:document_id>/view", documents.view_document),
    path("documents/<str:document_id>/download", documents.download_document),
    path("admin/documents", admin_api.admin_documents),
    path("admin/users", admin_api.admin_users),
    path("admin/users/<str:user_id>", admin_api.admin_user_patch),
    path("admin/tool-access", admin_api.admin_tool_access),
    path("admin/audit-logs", admin_api.audit_logs),
    path("admin/overview", admin_api.overview),
    path("tools", tools.list_tools),
    path("tools/<str:slug>/frame", tools.tool_frame),
]
