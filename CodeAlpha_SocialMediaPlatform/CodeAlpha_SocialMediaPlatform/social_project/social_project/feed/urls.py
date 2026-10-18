from django.urls import path
from . import views

urlpatterns = [
    path('', views.feed_view, name='feed'),
    path('signup/', views.signup, name='signup'),
    path('settings/', views.settings_view, name='settings'),
    path('follow-request/<int:request_id>/<str:action>/', views.handle_follow_request, name='handle_follow_request'),
    path('inbox/', views.inbox_view, name='inbox'),
    path('inbox/<str:username>/', views.chat_view, name='chat'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('profile/<str:username>/edit', views.edit_profile, name="edit_profile"),
    path('like/<int:post_id>/', views.like_post, name='like_post'),
    path('comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('delete-post/<int:post_id>/', views.delete_post, name='delete_post'),
]