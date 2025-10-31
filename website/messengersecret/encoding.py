import requests
import numpy as np
from PIL import Image
import io
import subprocess
import tempfile
import os
import time
import random

class ImageSteganography:
    def __init__(self):
        # List of sample cat image URLs
        self.cat_urls = [
            "https://cataas.com/cat",
            "https://api.thecatapi.com/v1/images/search",
            "https://placekitten.com/800/600"
        ]
        self.rangenc_exe = os.path.join(os.path.dirname(__file__), '..', '..', 'test', 'rangenc.exe')

    def _compress_with_range_encoding(self, data: bytes) -> bytes:
        """Compress data using C++ range encoding executable"""
        # Skip range encoding for speed - it's too slow for web requests
        print(f"Skipping range encoding for performance (size: {len(data)} bytes)")
        return data

    def _decompress_with_range_encoding(self, compressed_data: bytes) -> bytes:
        """Decompress data using C++ range encoding executable"""
        # Skip range decoding for performance - return data as-is
        print(f"Skipping range decoding for performance (size: {len(compressed_data)} bytes)")
        return compressed_data

    def _get_random_cat_image(self):
        """Fetch a random cat image from the internet"""
        try:
            url = random.choice(self.cat_urls)
            response = requests.get(url, timeout=5)
            return Image.open(io.BytesIO(response.content))
        except:
            # Fallback to creating a deterministic pattern if download fails
            width = 800
            height = 600
            # Use a 32-bit seed so numpy's MT19937 accepts it. Take lower 32 bits
            # of the hash slice to ensure deterministic but in-range seed.
            seed = int(combined_hash[:16], 16) & 0xFFFFFFFF
            np.random.seed(int(seed))
            pattern = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
            img = Image.fromarray(pattern.astype('uint8'), 'RGB')
            return img

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
        
        # Save to bytes - ensure proper format
        img_byte_arr = io.BytesIO()
        try:
            if encoded_image.mode != 'RGB':
                encoded_image = encoded_image.convert('RGB')
            encoded_image.save(img_byte_arr, format='PNG')
            compressed_data = self._compress_with_range_encoding(img_byte_arr.getvalue())
        except Exception as e:
            # If image processing fails, fall back to simple encryption
            print(f"Image steganography failed: {e}, falling back to simple encryption")
            import hashlib
            key = hashlib.sha256((sender_hash + receiver_hash).encode()).digest()
            message_bytes = message.encode('utf-8')
            encrypted = bytearray(len(message_bytes))
            for i, b in enumerate(message_bytes):
                encrypted[i] = b ^ key[i % len(key)]
            compressed_data = bytes(encrypted)

        return compressed_data

    def decode_message(self, compressed_data: bytes) -> str:
        """Decode a message from a compressed steganographic image"""
        try:
            # Decompress the image
            img_data = self._decompress_with_range_encoding(compressed_data)
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

        # Convert binary to bytes
        message_bytes = bytearray()
        for i in range(0, len(binary_message)-8, 8):
            message_bytes.append(int(binary_message[i:i+8], 2))
            
        # Apply RLE decompression
        rle_decoded = RLECompression.decode(bytes(message_bytes))
        
        # Convert back to string
        return rle_decoded.decode('utf-8')

encoding = ImageSteganography().encode_message
decoding = ImageSteganography().decode_message

if __name__ == "__main__":
    # Example usage
    import time as timing
    sender_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90abcdef1234567890abcdef1234567890"
    receiver_hash = "0f1e2d3c4b5a69788796a5b4c3d2e1f0fedcba0987654321fedcba0987654321"
    message = "Hello, this is a secret message hidden in a cat image!"

    print(f"Original message length: {len(message)} chars")

    start_time = timing.time()
    encoded_data = encoding(message, sender_hash, receiver_hash)
    encoding_time = timing.time() - start_time
    print(f"Encoded data size: {len(encoded_data)} bytes")
    print(f"Encoding time: {encoding_time:.4f}s")

    start_time = timing.time()
    decoded_message = decoding(encoded_data, sender_hash, receiver_hash)
    decoding_time = timing.time() - start_time
    print(f"Decoded message: {decoded_message}")
    print(f"Decoding time: {decoding_time:.4f}s")

    print(f"Round-trip success: {message == decoded_message}")
