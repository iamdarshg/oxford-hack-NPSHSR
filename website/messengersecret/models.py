from django.db import models
from django.contrib.auth.models import User
import hashlib
import os

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_hash = models.CharField(max_length=64, unique=True)  # SHA256 hash

    def save(self, *args, **kwargs):
        if not self.user_hash:
            # Generate hash using username + secret salt
            secret_salt = os.environ.get('SECRET_KEY', 'default_salt')
            self.user_hash = hashlib.sha256(f"{self.user.username}:{secret_salt}".encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} (hash: {self.user_hash[:8]}...)"

class Message(models.Model):
    sender = models.CharField(max_length=100)  # Keep as char for backward compatibility
    receiver = models.CharField(max_length=100, null=True, blank=True)  # P2P receiver
    sender_hash = models.CharField(max_length=64, null=True, blank=True)
    receiver_hash = models.CharField(max_length=64, null=True, blank=True)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        recipient = f" -> {self.receiver}" if self.receiver else " (room)"
        return f"{self.sender}{recipient}: {self.content[:50]}"
