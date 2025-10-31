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


def build_cumulative_freqs():
    # Uniform frequency for bytes 0-255
    freqs = [1] * 256
    cum_freqs = [0]
    for f in freqs:
        cum_freqs.append(cum_freqs[-1] + f)
    return cum_freqs


def encode_file(input_path, output_path):
    cum_freqs = build_cumulative_freqs()
    total = cum_freqs[-1]

    encoder = RangeEncoder()
    with open(input_path, 'rb') as f:
        while True:
            byte = f.read(1)
            if not byte:
                break
            symbol = byte[0]
            encoder.encode_symbol(symbol, cum_freqs[symbol], 1, total)

    compressed = encoder.finish()
    with open(output_path, 'wb') as f:
        f.write(compressed)


def decode_file(input_path, output_path):
    cum_freqs = build_cumulative_freqs()
    with open(input_path, 'rb') as f:
        compressed = f.read()
    decoder = RangeDecoder(compressed)

    with open(output_path, 'wb') as f:
        # Decode until end of file condition (simplified by fixed length)
        # In real use, you'd encode original file length or EOF symbol
        for _ in range(1024 * 1024):  # decode up to 1MB for example
            symbol = decoder.decode_symbol(cum_freqs)
            f.write(bytes([symbol]))


# Example usage:
# encode_file('input.bin', 'compressed.bin')
# decode_file('compressed.bin', 'recovered.bin')
