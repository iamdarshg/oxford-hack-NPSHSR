from PIL import Image

def image_to_bitstream(image_path):
    # Open the image and convert to grayscale
    img = Image.open(image_path).convert('L')  # 'L' mode is grayscale

    # Threshold to binary (black and white)
    threshold = 128
    binary_img = img.point(lambda p: 1 if p > threshold else 0)

    # Get pixel data as a flat list
    pixels = list(binary_img.getdata())

    # Convert pixel list to a bitstream string '0'/'1'
    bitstream = ''.join(str(bit) for bit in pixels)
    return bitstream

bitstream = image_to_bitstream(".jpg")
print(bitstream[:64])  # Print first 64 bits
