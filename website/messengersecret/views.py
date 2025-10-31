from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import Message
import datetime

# Placeholder encode and decode functions - user to implement
def encode_message(message):
    """
    Placeholder for message encoding function.
    Implement your encoding logic here (e.g., encryption, base64, etc.)
    """
    return message  # Currently returns unchanged

def decode_message(message):
    """
    Placeholder for message decoding function.
    Implement your decoding logic here (matches the encoding above)
    """
    return message  # Currently returns unchanged

@login_required
def chat_view(request):
    """Main chat view to display messages and handle sending"""
    if request.method == 'POST':
        sender = request.POST.get('sender', '').strip()
        content = request.POST.get('content', '').strip()

        # Use authenticated user's username instead of anonymous
        if not sender:
            sender = request.user.username

        if content:
            # Encode the message before saving
            encoded_content = encode_message(content)
            message = Message.objects.create(sender=sender, content=encoded_content)
            messages.success(request, "Message sent!")

        return redirect('chat')

    # Get all messages and decode them for display
    all_messages = Message.objects.order_by('timestamp')
    decoded_messages = []
    for msg in all_messages:
        decoded_messages.append({
            'id': msg.id,
            'sender': msg.sender,
            'content': decode_message(msg.content),
            'timestamp': msg.timestamp
        })

    context = {
        'messages': decoded_messages,
        'user': request.user,
    }
    return render(request, 'messengersecret/chat.html', context)

@login_required
def clear_messages(request):
    """View to clear all messages"""
    if request.method == 'POST':
        Message.objects.all().delete()
        messages.success(request, "All messages cleared!")
    return redirect('chat')

def landing_view(request):
    """Landing page for non-authenticated users"""
    if request.user.is_authenticated:
        return redirect('chat')
    return render(request, 'messengersecret/landing.html')

def signup_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('chat')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Auto-login after registration
            messages.success(request, f"Welcome to Secret Messenger, {user.username}!")
            return redirect('chat')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        form = UserCreationForm()

    return render(request, 'messengersecret/signup.html', {'form': form})

def login_view(request):
    """Handle user login"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                return redirect('chat')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'messengersecret/login.html', {'form': form})

@login_required
def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('landing')
