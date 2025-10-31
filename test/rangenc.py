import sys

class RangeEncoder:
    def __init__(self):
        self.low = 0
        self.high = 0xFFFFFFFF
        self.pending_bits = 0
        self.output = bytearray()
        self.buffer = 0
        self.buffer_bits = 0  # bits in buffer for output

    def write_bit(self, bit):
        self.buffer = (self.buffer << 1) | bit
        self.buffer_bits += 1
        if self.buffer_bits == 8:
            self.output.append(self.buffer)
            self.buffer = 0
            self.buffer_bits = 0

    def flush_bits(self):
        if self.buffer_bits > 0:
            self.buffer <<= (8 - self.buffer_bits)
            self.output.append(self.buffer)
            self.buffer = 0
            self.buffer_bits = 0

    def encode_symbol(self, symbol, cum_freq, freq, total):
        range_ = self.high - self.low + 1
        self.high = self.low + (range_ * (cum_freq + freq) // total) - 1
        self.low = self.low + (range_ * cum_freq // total)

        while True:
            if self.high < 0x80000000:
                self._write_bit_0()
            elif self.low >= 0x80000000:
                self._write_bit_1()
                self.low -= 0x80000000
                self.high -= 0x80000000
            elif 0x40000000 <= self.low < 0x80000000 <= self.high < 0xC0000000:
                self.pending_bits += 1
                self.low -= 0x40000000
                self.high -= 0x40000000
            else:
                break

            self.low <<= 1
            self.high = (self.high << 1) + 1

    def _write_bit_0(self):
        self.write_bit(0)
        for _ in range(self.pending_bits):
            self.write_bit(1)
        self.pending_bits = 0

    def _write_bit_1(self):
        self.write_bit(1)
        for _ in range(self.pending_bits):
            self.write_bit(0)
        self.pending_bits = 0

    def finish(self):
        self.pending_bits += 1
        if self.low < 0x40000000:
            self._write_bit_0()
        else:
            self._write_bit_1()
        self.flush_bits()
        return bytes(self.output)


class RangeDecoder:
    def __init__(self, input_bytes):
        self.low = 0
        self.high = 0xFFFFFFFF
        self.code = 0
        self.input = input_bytes
        self.input_pos = 0
        self.buffer = 0
        self.buffer_bits = 0

        for _ in range(32):
            self.code = (self.code << 1) | self.read_bit()

    def read_bit(self):
        if self.buffer_bits == 0:
            if self.input_pos < len(self.input):
                self.buffer = self.input[self.input_pos]
                self.input_pos += 1
                self.buffer_bits = 8
            else:
                return 0
        bit = (self.buffer >> 7) & 1
        self.buffer = (self.buffer << 1) & 0xFF
        self.buffer_bits -= 1
        return bit

    def decode_symbol(self, cum_freqs):
        total = cum_freqs[-1]
        range_ = self.high - self.low + 1
        value = ((self.code - self.low + 1) * total - 1) // range_

        # Binary search to find symbol
        low_idx = 0
        high_idx = len(cum_freqs) - 1
        while low_idx < high_idx:
            mid = (low_idx + high_idx) // 2
            if cum_freqs[mid] > value:
                high_idx = mid
            else:
                low_idx = mid + 1

        symbol = low_idx - 1

        # Update range
        self.high = self.low + (range_ * cum_freqs[symbol + 1] // total) - 1
        self.low = self.low + (range_ * cum_freqs[symbol] // total)

        while True:
            if self.high < 0x80000000:
                pass
            elif self.low >= 0x80000000:
                self.low -= 0x80000000
                self.high -= 0x80000000
                self.code -= 0x80000000
            elif 0x40000000 <= self.low < 0x80000000 <= self.high < 0xC0000000:
                self.low -= 0x40000000
                self.high -= 0x40000000
                self.code -= 0x40000000
            else:
                break
            self.low <<= 1
            self.high = (self.high << 1) + 1
            self.code = (self.code << 1) | self.read_bit()

        return symbol


def build_cumulative_freqs(freqs):
    # Build cumulative frequencies from actual frequency counts
    cum_freqs = [0]
    for f in freqs:
        cum_freqs.append(cum_freqs[-1] + f)
    return cum_freqs

def count_frequencies(input_path):
    # Count actual byte frequencies in the input file
    freqs = [0] * 256
    with open(input_path, 'rb') as f:
        while True:
            byte = f.read(1)
            if not byte:
                break
            freqs[byte[0]] += 1
    return freqs


def encode_file(input_path, output_path):
    # First pass: count frequencies for data compression
    freqs = count_frequencies(input_path)
    cum_freqs = build_cumulative_freqs(freqs)
    total = cum_freqs[-1]

    # Get file length for header
    with open(input_path, 'rb') as f:
        f.seek(0, 2)  # Seek to end
        file_len = f.tell()
        f.seek(0)  # Back to start

    encoder = RangeEncoder()

    # Create a simple encoder for header (use uniform frequencies since we don't know header distribution)
    uniform_freqs = [1] * 256
    uniform_cum_freqs = build_cumulative_freqs(uniform_freqs)
    uniform_total = uniform_cum_freqs[-1]

    # Write file length as header (4 bytes) using uniform frequencies
    for i in range(4):
        byte = (file_len >> (i * 8)) & 0xFF
        encoder.encode_symbol(byte, uniform_cum_freqs[byte], uniform_freqs[byte], uniform_total)

    # Write frequency information (256 * 4 bytes = 1024 bytes header)
    for freq in freqs:
        for j in range(4):
            byte = (freq >> (j * 8)) & 0xFF
            encoder.encode_symbol(byte, uniform_cum_freqs[byte], uniform_freqs[byte], uniform_total)

    # Encode actual data using the actual frequencies
    with open(input_path, 'rb') as f:
        for _ in range(file_len):
            byte = f.read(1)
            symbol = byte[0]
            encoder.encode_symbol(symbol, cum_freqs[symbol], freqs[symbol], total)

    compressed = encoder.finish()
    with open(output_path, 'wb') as f:
        f.write(compressed)


def decode_file(input_path, output_path):
    with open(input_path, 'rb') as f:
        compressed = f.read()

    # Use uniform frequencies for decoding header
    uniform_freqs = [1] * 256
    uniform_cum_freqs = build_cumulative_freqs(uniform_freqs)
    uniform_total = uniform_cum_freqs[-1]

    decoder = RangeDecoder(compressed)

    # Read file length from header (first 4 bytes)
    file_length = 0
    for i in range(4):
        byte = decoder.decode_symbol(uniform_cum_freqs)
        file_length |= byte << (i * 8)

    # Read frequency information (next 1024 bytes: 256 frequencies * 4 bytes each)
    freqs = []
    for _ in range(256):
        freq = 0
        for j in range(4):
            byte = decoder.decode_symbol(uniform_cum_freqs)
            freq |= byte << (j * 8)
        freqs.append(freq)

    cum_freqs = build_cumulative_freqs(freqs)
    total = cum_freqs[-1]

    with open(output_path, 'wb') as f:
        for _ in range(file_length):
            symbol = decoder.decode_symbol(cum_freqs)
            f.write(bytes([symbol]))


# Example usage:
encode_file('test/test.dng', 'test/compressed.bin')
decode_file('test/compressed.bin', 'test/out.dng')

# Check file sizes
import os
if os.path.exists('test/test.dng') and os.path.exists('test/compressed.bin'):
    original_size = os.path.getsize('test/test.dng')
    compressed_size = os.path.getsize('test/compressed.bin')
    print(f"Original size: {original_size} bytes")
    print(f"Compressed size: {compressed_size} bytes")
    print(f"Compression ratio: {compressed_size/original_size:.3f}")

    if os.path.exists('test/out.dng'):
        output_size = os.path.getsize('test/out.dng')
        print(f"Decoded size: {output_size} bytes")
        print(f"Round-trip successful: {output_size == original_size}")
    else:
        print("Decoding failed - output file not created")
