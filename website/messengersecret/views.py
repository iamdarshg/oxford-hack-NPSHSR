from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import Message, UserProfile, Contact
from django.db.models import Q
from django.db.utils import OperationalError
import datetime
from .encoding import encoding, decoding
import logging
import base64
import threading

logger = logging.getLogger(__name__)

# Placeholder encode and decode functions - user to implement
def encode_message(message, sender_hash, receiver_hash):
    """
    Message encoding function that uses sender and receiver hashes.
    Takes the message and both user hashes into account for encoding.
    """
    # Use both hashes to create a unique encoding context
    encoded_message=encoding(message, sender_hash, receiver_hash)
    
    return encoded_message

def decode_message(message, sender_hash, receiver_hash):
    """
    Message decoding function that uses sender and receiver hashes.
    Takes the encoded message and both user hashes to decode.
    """
    # Use both hashes in the same way as encoding
    decoded_message=decoding(message, sender_hash, receiver_hash)
    
    return decoded_message

@login_required
def chat_view(request, contact_email=None):
    """P2P chat view - show conversation with specific contact or contact list"""

    # Handle GET requests with email parameter (from the start conversation form)
    if request.method == 'GET' and 'email' in request.GET:
        email_param = request.GET.get('email', '').strip()
        if email_param:
            return redirect('chat_with_user', contact_email=email_param)

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
        receiver = request.POST.get('receiver', '').strip()

        # Determine if this is message send (from contact chat) or contact add (from start conversation)
        if content and receiver:
            # Message send from contact chat
            receiver_username = receiver
            receiver_user = User.objects.filter(username=receiver_username).first()

            if not receiver_user:
                messages.error(request, f"User '{receiver_username}' not found.")
                return redirect('chat')

            if receiver_user == request.user:
                messages.error(request, "You cannot send messages to yourself.")
                return redirect('chat')

            # Get or create user profile for current user
            sender_profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Get or create user profile for receiver
            receiver_profile, created = UserProfile.objects.get_or_create(user=receiver_user)

            # Ensure explicit Contact records exist for both directions
            try:
                Contact.objects.get_or_create(user=request.user, contact=receiver_user)
                Contact.objects.get_or_create(user=receiver_user, contact=request.user)
            except Exception:
                # If contact creation fails, still proceed
                logger.exception('Failed to create Contact rows for %s <-> %s', request.user.username, receiver_user.username)

            # Create message immediately with plain text
            msg = Message.objects.create(
                sender=request.user.username,
                receiver=receiver_user.username,
                sender_hash=sender_profile.user_hash,
                receiver_hash=receiver_profile.user_hash,
                content=content,  # Plain text initially
                is_encrypted=False  # Will be updated by background thread
            )

            # Check for encryption bypass
            bypass_encryption = request.POST.get('bypass_encryption') == 'on'
            if not bypass_encryption:
                # Start background thread for complex encryption
                def encrypt_message_background(message_id, plain_text, sender_hash, receiver_hash):
                    try:
                        encoded_bytes = encode_message(plain_text, sender_hash, receiver_hash)
                        encrypted_content = base64.b64encode(encoded_bytes).decode('ascii')
                        # Update the message with encrypted content
                        Message.objects.filter(id=message_id).update(
                            content=encrypted_content,
                            is_encrypted=True
                        )
                        logger.info(f"Background encryption completed for message {message_id}")
                    except Exception as e:
                        logger.error(f"Background encryption failed for message {message_id}: {e}")

                # Start encryption thread
                encryption_thread = threading.Thread(
                    target=encrypt_message_background,
                    args=(msg.id, content, sender_profile.user_hash, receiver_profile.user_hash)
                )
                encryption_thread.daemon = True  # Don't keep app alive if main thread dies
                encryption_thread.start()

            messages.success(request, f"Message sent to {receiver_user.username}!")
            return redirect('chat_with_user', contact_email=receiver_user.username)

        elif receiver_email:
            # Contact add from start conversation form
            # Find receiver by email or username
            receiver_user = User.objects.filter(email=receiver_email).first()
            if not receiver_user:
                # Fallback to username if no email match
                receiver_user = User.objects.filter(username=receiver_email).first()

            if not receiver_user:
                messages.error(request, f"User '{receiver_email}' not found.")
                return redirect('chat')

            if receiver_user == request.user:
                messages.error(request, "You cannot add yourself as a contact.")
                return redirect('chat')

            # Ensure explicit Contact records exist for both directions
            try:
                Contact.objects.get_or_create(user=request.user, contact=receiver_user)
                Contact.objects.get_or_create(user=receiver_user, contact=request.user)
            except Exception:
                # If contact creation fails, still proceed
                logger.exception('Failed to create Contact rows for %s <-> %s', request.user.username, receiver_user.username)

            messages.success(request, f"Contact {receiver_user.username} added successfully!")
            # Redirect to the conversation
            return redirect('chat_with_user', contact_email=receiver_user.username)

        else:
            messages.error(request, "Invalid request.")
            return redirect('chat')

    # Prefer explicit Contact relations (new, reliable method)
    try:
        contact_user_qs = Contact.objects.filter(user=request.user).values_list('contact_id', flat=True)
        contacts = list(User.objects.filter(id__in=contact_user_qs))
    except OperationalError:
        # The Contact table may not exist yet (migrations not applied).
        # Fall back to deriving contacts from Message records so the app stays usable
        contacts = []

    # Backwards-compatible fallback: derive contacts from Message records if no explicit contacts
    if not contacts:
        sent_usernames = Message.objects.filter(sender=request.user.username).values_list('receiver', flat=True)
        received_usernames = Message.objects.filter(receiver=request.user.username).values_list('sender', flat=True)
        contact_usernames = set(sent_usernames) | set(received_usernames)
        contact_usernames.discard(request.user.username)
        contacts = list(User.objects.filter(username__in=contact_usernames))

    # Get messages for P2P conversation
    if contact:
        conversation_messages = Message.objects.filter(
            (Q(sender=request.user.username) & Q(receiver=contact.username)) |
            (Q(sender=contact.username) & Q(receiver=request.user.username))
        ).order_by('timestamp')

        decoded_messages = []
        for msg in conversation_messages:
            if msg.is_encrypted:
                try:
                    # Decode base64 to bytes first, then decode the encrypted content
                    encrypted_bytes = base64.b64decode(msg.content.encode('ascii'))
                    decoded_content = decode_message(encrypted_bytes, msg.sender_hash, msg.receiver_hash)
                except Exception as e:
                    # If decoding fails, show error message
                    decoded_content = f"[Encryption decoding failed: {str(e)}]"
                    logger.exception(f"Failed to decode encrypted message: {e}")
            else:
                decoded_content = msg.content
            decoded_messages.append({
                'id': msg.id,
                'sender': msg.sender,
                'receiver': msg.receiver,
                'content': decoded_content,
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
