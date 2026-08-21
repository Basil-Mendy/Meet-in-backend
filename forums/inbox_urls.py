from django.urls import path
from .inbox_views import (
    InboxOverviewView,
    InboxFavoritesView,
    InboxRecipientLookupView,
    InboxMessagesView,
    InboxSendView,
    InboxConversationView,
)

urlpatterns = [
    path("overview/", InboxOverviewView.as_view(), name="inbox-overview"),
    path("favorites/", InboxFavoritesView.as_view(), name="inbox-favorites"),
    path("recipients/lookup/", InboxRecipientLookupView.as_view(), name="inbox-recipient-lookup"),
    path("messages/", InboxMessagesView.as_view(), name="inbox-messages"),
    path("send/", InboxSendView.as_view(), name="inbox-send"),
    path("conversation/", InboxConversationView.as_view(), name="inbox-conversation"),
]
