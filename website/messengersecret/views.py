from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import Message, UserProfile
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
def chat_view(request, contact_email=None):
    """P2P chat view - show conversation with specific contact or contact list"""
    contact = None
    if contact_email:
        # Try to find user by email or username for backward compatibility
        contact = User.objects.filter(email=contact_email).first()
        if not contact:
            # Fallback to username if no email match
            contact = User.objects.filter(username=contact_email).first()

        if not contact:
            messages.error(request, f"User with email '{contact_email}' not found.")
            return redirect('chat')

        if contact == request.user:
            messages.error(request, "You cannot start a conversation with yourself.")
            return redirect('chat')

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        receiver_email = request.POST.get('receiver_email', '').strip()

        if content and receiver_email:
            # Find receiver by email or username
            receiver_user = User.objects.filter(email=receiver_email).first()
            if not receiver_user:
                # Fallback to username if no email match
                receiver_user = User.objects.filter(username=receiver_email).first()

            if not receiver_user:
                messages.error(request, f"User with email '{receiver_email}' not found.")
                return redirect('chat')

            if receiver_user == request.user:
                messages.error(request, "You cannot send messages to yourself.")
                return redirect('chat')

            # Get or create user profile for current user
            sender_profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Get or create user profile for receiver
            receiver_profile, created = UserProfile.objects.get_or_create(user=receiver_user)

            # Encode the message
            encoded_content = encode_message(content)

            # Create P2P message with hashes
            Message.objects.create(
                sender=request.user.username,
                receiver=receiver_user.username,
                sender_hash=sender_profile.user_hash,
                receiver_hash=receiver_profile.user_hash,
                content=encoded_content
            )
            messages.success(request, f"Message sent to {receiver_user.email or receiver_user.username}!")

            # Redirect to the conversation
            return redirect('chat_with_user', email=receiver_user.email or receiver_user.username)

        elif not content:
            messages.error(request, "Please enter a message.")
        elif not receiver_email:
            messages.error(request, "Please enter the recipient's email address.")

    # Get user's contacts (users they've messaged with) - for privacy
    sent_messages = Message.objects.filter(sender=request.user.username).values_list('receiver', flat=True).distinct()
    received_messages = Message.objects.filter(receiver=request.user.username).values_list('sender', flat=True).distinct()
    contact_usernames = set(sent_messages) | set(received_messages)
    contact_usernames.discard(request.user.username)  # Remove self

    # Get contact objects
    contacts = []
    for username in contact_usernames:
        user = User.objects.filter(username=username).first()
        if user:
            contacts.append(user)

    # Get messages for P2P conversation
    if contact:
        conversation_messages = Message.objects.filter(
            ((Message.sender == request.user.username) & (Message.receiver == contact.username)) |
            ((Message.sender == contact.username) & (Message.receiver == request.user.username))
        ).order_by('timestamp')

        decoded_messages = []
        for msg in conversation_messages:
            decoded_messages.append({
                'id': msg.id,
                'sender': msg.sender,
                'receiver': msg.receiver,
                'content': decode_message(msg.content),
                'timestamp': msg.timestamp,
                'sender_hash': msg.sender_hash,
                'receiver_hash': msg.receiver_hash
            })

        context = {
            'messages': decoded_messages,
            'contact': contact,
            'user': request.user,
            'contacts': contacts,
            'is_p2p': True
        }
    else:
        # No contact selected - show contact list and email input form
        context = {
            'messages': [],
            'contact': None,
            'user': request.user,
            'contacts': contacts,
            'is_p2p': False
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
            # Create user profile with hash
            UserProfile.objects.create(user=user)
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
