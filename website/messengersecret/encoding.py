import requests
import numpy as np
from PIL import Image
import io
import lzma
import random

class ImageSteganography:
    def __init__(self):
        # List of sample cat image URLs
        self.cat_urls = [
            "https://cataas.com/cat",
            "https://api.thecatapi.com/v1/images/search",
            "https://placekitten.com/800/600"
        ]

    def _get_random_cat_image(self):
        """Fetch a random cat image from the internet"""
        try:
            url = random.choice(self.cat_urls)
            response = requests.get(url, timeout=5)
            return Image.open(io.BytesIO(response.content))
        except:
            # Fallback to creating a default image if download fails
            return Image.new('RGB', (800, 600), 'white')

    def encode_message(self, message: str) -> bytes:
        """Encode a message into an image using LSB steganography and compress it"""
        # Convert message to binary
        binary_message = ''.join(format(ord(char), '08b') for char in message)
        binary_message += '00000000'  # Add delimiter

        # Get carrier image
        image = self._get_random_cat_image()
        pixels = np.array(image)

        if len(binary_message) > pixels.size:
            raise ValueError("Message too large for the image")

        # Flatten the pixel array
        flat_pixels = pixels.flatten()

        # Encode message using LSB
        for i in range(len(binary_message)):
            flat_pixels[i] = (flat_pixels[i] & ~1) | int(binary_message[i])

        # Reshape back to original dimensions
        encoded_pixels = flat_pixels.reshape(pixels.shape)
        
        # Convert back to image
        encoded_image = Image.fromarray(encoded_pixels)
        
        # Save to bytes and compress
        img_byte_arr = io.BytesIO()
        encoded_image.save(img_byte_arr, format='PNG')
        compressed_data = lzma.compress(img_byte_arr.getvalue())
        
        return compressed_data

    def decode_message(self, compressed_data: bytes) -> str:
        """Decode a message from a compressed steganographic image"""
        # Decompress the image
        img_data = lzma.decompress(compressed_data)
        image = Image.open(io.BytesIO(img_data))
        
        # Convert to numpy array
        pixels = np.array(image)
        flat_pixels = pixels.flatten()

        # Extract LSBs
        binary_message = ''
        for pixel in flat_pixels:
            binary_message += str(pixel & 1)
            # Check for delimiter
            if len(binary_message) >= 8 and binary_message[-8:] == '00000000':
                break

        # Convert binary to string
        message = ''
        for i in range(0, len(binary_message)-8, 8):
            message += chr(int(binary_message[i:i+8], 2))
            
        return message

encoding = ImageSteganography().encode_message
decoding = ImageSteganography().decode_message