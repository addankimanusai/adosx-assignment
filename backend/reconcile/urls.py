from django.urls import path
from reconcile.views import DisagreementsView, OrgListView

urlpatterns = [
    path("orgs/", OrgListView.as_view(), name="org-list"),
    path("disagreements/", DisagreementsView.as_view(), name="disagreements"),
]
