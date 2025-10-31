import requests
import numpy as np
from PIL import Image
import io
import subprocess
import tempfile
import os
import time
import random
import hashlib

# Run Length Encoding implementation
class RLECompression:
    @staticmethod
    def encode(data: bytes) -> bytes:
        if not data:
            return b''
            
        result = []
        count = 1
        current = data[0]
        
        for byte in data[1:]:
            if byte == current:
                count += 1
            else:
                result.extend([count.to_bytes(1, 'big'), bytes([current])])
                current = byte
                count = 1
                
        result.extend([count.to_bytes(1, 'big'), bytes([current])])
        return b''.join(result)

    @staticmethod
    def decode(data: bytes) -> bytes:
        if not data:
            return b''
            
        result = []
        i = 0
        
        while i < len(data):
            count = data[i]
            byte = data[i + 1]
            result.extend([byte] * count)
            i += 2
            
        return bytes(result)

class ImageSteganography:
    def __init__(self):
        # List of sample cat image URLs with parameters for deterministic selection
        self.cat_urls = [
            "https://cataas.com/cat/says/{text}",  # Can add text based on hash
            "https://placekitten.com/{width}/{height}",  # Can vary dimensions
            "https://robohash.org/{seed}?set=set4"  # Deterministic robot cats based on seed
        ]
        self.rangenc_exe = os.path.join(os.path.dirname(__file__), '..', '..', 'test', 'rangenc.exe')

    def _compress_with_range_encoding(self, data: bytes) -> bytes:
        """Compress data using C++ range encoding executable"""
        start_time = time.time()

        with tempfile.NamedTemporaryFile(delete=False, suffix='.in') as input_file:
            input_file.write(data)
            input_path = input_file.name

        output_path = input_path + '.compressed'

        try:
            # Run range encoding compression
            result = subprocess.run(
                [self.rangenc_exe, 'encode', input_path, output_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(f"Range encoding failed: {result.stderr}")

            # Read compressed data
            with open(output_path, 'rb') as f:
                compressed_data = f.read()

            compression_time = time.time() - start_time
            original_size = len(data)
            compressed_size = len(compressed_data)
            ratio = compressed_size / original_size if original_size > 0 else 0

            print(f"Range encoding: {original_size} -> {compressed_size} bytes ({ratio:.2%}, {compression_time:.4f}s)")

            return compressed_data

        except FileNotFoundError:
            print("rangenc.exe not found, falling back to no compression")
            return data
        finally:
            # Clean up temp files
            for path in [input_path, output_path]:
                try:
                    os.unlink(path)
                except:
                    pass

    def _decompress_with_range_encoding(self, compressed_data: bytes) -> bytes:
        """Decompress data using C++ range encoding executable"""
        start_time = time.time()

        with tempfile.NamedTemporaryFile(delete=False, suffix='.compressed') as input_file:
            input_file.write(compressed_data)
            input_path = input_file.name

        output_path = input_path + '.decompressed'

        try:
            # Run range encoding decompression
            result = subprocess.run(
                [self.rangenc_exe, 'decode', input_path, output_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                raise RuntimeError(f"Range decoding failed: {result.stderr}")

            # Read decompressed data
            with open(output_path, 'rb') as f:
                decompressed_data = f.read()

            decompression_time = time.time() - start_time
            compressed_size = len(compressed_data)
            decompressed_size = len(decompressed_data)
            ratio = decompressed_size / compressed_size if compressed_size > 0 else 0

            print(f"Range decoding: {compressed_size} -> {decompressed_size} bytes ({ratio:.2%}, {decompression_time:.4f}s)")

            return decompressed_data

        except FileNotFoundError:
            print("rangenc.exe not found, treating data as uncompressed")
            return compressed_data
        finally:
            # Clean up temp files
            for path in [input_path, output_path]:
                try:
                    os.unlink(path)
                except:
                    pass

    def _get_deterministic_cat_image(self, sender_hash: str, receiver_hash: str):
        """Fetch a cat image deterministically based on user hashes"""
        # Combine hashes to create a deterministic seed
        combined_hash = hashlib.sha256((sender_hash + receiver_hash).encode()).hexdigest()
        
        # Use first 8 chars of hash for image selection and parameters
        selector = int(combined_hash[:8], 16)
        
        # Choose URL based on hash
        url_index = selector % len(self.cat_urls)
        base_url = self.cat_urls[url_index]
        
        try:
            if url_index == 0:  # cataas.com
                # Use hash subset as text
                text = combined_hash[8:16]
                url = base_url.format(text=text)
            elif url_index == 1:  # placekitten
                # Use hash to generate dimensions (ensuring reasonable sizes)
                width = 400 + (int(combined_hash[16:20], 16) % 400)
                height = 300 + (int(combined_hash[20:24], 16) % 300)
                url = base_url.format(width=width, height=height)
            else:  # robohash
                url = base_url.format(seed=combined_hash[:32])
            
            response = requests.get(url, timeout=5)
            return Image.open(io.BytesIO(response.content))
        except:
            # Fallback to creating a deterministic pattern if download fails
            width = 800
            height = 600
            seed = int(combined_hash[:16], 16)
            np.random.seed(seed)
            pattern = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
            return Image.fromarray(pattern)

    def encode_message(self, message: str, sender_hash: str, receiver_hash: str) -> bytes:
        """Encode a message into an image using LSB steganography and compress it"""
        # First apply RLE compression to the message
        message_bytes = message.encode('utf-8')
        rle_compressed = RLECompression.encode(message_bytes)
        
        # Convert compressed message to binary
        binary_message = ''.join(format(b, '08b') for b in rle_compressed)
        binary_message += '00000000'  # Add delimiter

        # Get carrier image based on user hashes
        image = self._get_deterministic_cat_image(sender_hash, receiver_hash)
        pixels = np.array(image)

        if len(binary_message) > pixels.size:
            raise ValueError("Message too large for the image")

        # Flatten the pixel array
        flat_pixels = pixels.flatten()

        # Encode message using LSB
        # Use 0xFE mask (254) instead of Python's ~1 which yields -2 and
        # can cause upcasts/overflow when mixed with numpy uint8 values.
        for i in range(len(binary_message)):
            bit = int(binary_message[i])
            # Ensure we operate on integers to avoid numpy dtype surprises
            val = (int(flat_pixels[i]) & 0xFE) | bit
            flat_pixels[i] = val

        # Reshape back to original dimensions
        encoded_pixels = flat_pixels.reshape(pixels.shape)
        
        # Convert back to image
        encoded_image = Image.fromarray(encoded_pixels)
        
        # Save to bytes and compress
        img_byte_arr = io.BytesIO()
        encoded_image.save(img_byte_arr, format='PNG')
        compressed_data = self._compress_with_range_encoding(img_byte_arr.getvalue())

        return compressed_data

    def decode_message(self, compressed_data: bytes, sender_hash: str, receiver_hash: str) -> str:
        """Decode a message from a compressed steganographic image"""
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
