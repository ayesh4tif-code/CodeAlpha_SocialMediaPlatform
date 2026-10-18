from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from .models import Post, Comment, Profile, Message, FollowRequest
from .forms import ProfileUpdateForm, UserUpdateForm


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            login(request, user)
            return redirect("feed")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def feed_view(request):
    query = request.GET.get("q", "")

    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        content = request.POST.get("content")
        image = request.FILES.get("image")
        post_type = "image" if image else "thought"
        if content or image:
            Post.objects.create(
                user=request.user, 
                content=content or "", 
                image=image, 
                post_type=post_type
            )
            return redirect("feed")

    user_profile, _ = Profile.objects.get_or_create(user=request.user)
    followed_users = [p.user for p in user_profile.follows.all()] + [request.user]

    if query:
        posts = Post.objects.filter(
            Q(content__icontains=query) | Q(user__username__icontains=query)
        ).order_by("-created_at")
    else:
        posts = Post.objects.filter(
            Q(user__in=followed_users) | Q(user__profile__is_private=False)
        ).distinct().order_by("-created_at")

    suggested_users = User.objects.exclude(
        id__in=[u.id for u in followed_users]
    )[:5]

    return render(request, "feed/feed.html", {
        "posts": posts, 
        "query": query, 
        "suggested_users": suggested_users
    })


@login_required
def profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=profile_user)
    user_profile, _ = Profile.objects.get_or_create(user=request.user)

    is_following = profile in user_profile.follows.all()
    has_requested = FollowRequest.objects.filter(sender=request.user, receiver=profile_user).exists()
    
    if request.method == "POST" and "toggle_follow" in request.POST:
        if is_following:
            user_profile.follows.remove(profile)
        else:
            if profile.is_private:
                if has_requested:
                    FollowRequest.objects.filter(sender=request.user, receiver=profile_user).delete()
                else:
                    FollowRequest.objects.create(sender=request.user, receiver=profile_user)
            else:
                user_profile.follows.add(profile)
        return redirect("profile", username=username)

    if request.method == "POST" and request.user == profile_user:
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return redirect("profile", username=username)

    can_see_posts = (request.user == profile_user) or is_following or (not profile.is_private)
    posts = profile_user.posts.all().order_by("-created_at") if can_see_posts else []

    followers = profile.followed_by.all()
    following = profile.follows.all()

    u_form = UserUpdateForm(instance=request.user) if request.user == profile_user else None
    p_form = ProfileUpdateForm(instance=profile) if request.user == profile_user else None

    context = {
        "profile_user": profile_user,
        "profile": profile,
        "posts": posts,
        "is_following": is_following,
        "has_requested": has_requested,
        "can_see_posts": can_see_posts,
        "followers": followers,
        "following": following,
        "u_form": u_form,
        "p_form": p_form,
    }
    return render(request, "feed/profile.html", context)


@login_required
def settings_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        profile.is_private = "is_private" in request.POST
        profile.dark_mode = "dark_mode" in request.POST
        profile.save()
        return redirect("settings")

    pending_requests = FollowRequest.objects.filter(receiver=request.user)
    return render(request, "feed/settings.html", {"profile": profile, "pending_requests": pending_requests})


@login_required
def handle_follow_request(request, request_id, action):
    freq = get_object_or_404(FollowRequest, id=request_id, receiver=request.user)
    if action == "accept":
        sender_profile = freq.sender.profile
        sender_profile.follows.add(request.user.profile)
        freq.delete()
    elif action == "decline":
        freq.delete()
    return redirect("settings")


@login_required
def inbox_view(request):
    user = request.user
    conversations = User.objects.filter(
        Q(sent_messages__recipient=user) | Q(received_messages__sender=user)
    ).distinct().exclude(id=user.id)
    return render(request, "feed/inbox.html", {"conversations": conversations})


@login_required
def chat_view(request, username):
    other_user = get_object_or_404(User, username=username)
    if request.method == "POST":
        body = request.POST.get("body")
        if body:
            Message.objects.create(sender=request.user, recipient=other_user, body=body)
            return redirect("chat", username=username)

    messages = Message.objects.filter(
        Q(sender=request.user, recipient=other_user) |
        Q(sender=other_user, recipient=request.user)
    ).order_by("timestamp")
    
    Message.objects.filter(sender=other_user, recipient=request.user, is_read=False).update(is_read=True)

    return render(request, "feed/chat.html", {"other_user": other_user, "messages": messages})


@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user in post.likes.all():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"liked": liked, "count": post.likes.count()})

    return redirect("feed")


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == "POST":
        content = request.POST.get("content")
        if content:
            Comment.objects.create(post=post, user=request.user, content=content)
    return redirect("feed")


@login_required
def edit_profile(request, username):
    edit_user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=edit_user)

    if request.user != edit_user:
        return redirect("profile", username=request.user.username)

    if request.method == "POST":
        u_form = UserUpdateForm(request.POST, instance=edit_user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return redirect("profile", username=edit_user.username)
    else:
        u_form = UserUpdateForm(instance=edit_user)
        p_form = ProfileUpdateForm(instance=profile)

    return render(
        request,
        "feed/edit_profile.html",
        {
            "u_form": u_form,
            "p_form": p_form,
            "profile": profile,
            "user": edit_user,
        }
    )


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.user == request.user:
        post.delete()
    return redirect(request.META.get('HTTP_REFERER', 'feed'))