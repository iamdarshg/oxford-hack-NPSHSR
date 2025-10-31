from django.shortcuts import render, redirect
from django.contrib import messages
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

def chat_view(request):
    """Main chat view to display messages and handle sending"""
    if request.method == 'POST':
        sender = request.POST.get('sender', '').strip()
        content = request.POST.get('content', '').strip()

        if not sender:
            sender = "Anonymous"

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
    }
    return render(request, 'messengersecret/chat.html', context)

def clear_messages(request):
    """View to clear all messages"""
    if request.method == 'POST':
        Message.objects.all().delete()
        messages.success(request, "All messages cleared!")
    return redirect('chat')
