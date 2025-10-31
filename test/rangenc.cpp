#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <algorithm>
#include <thread>

class RangeEncoder {
public:
    uint64_t low = 0;
    uint64_t high = 0xFFFFFFFFULL;
    int pending_bits = 0;
    std::vector<uint8_t> output;
    uint8_t buffer = 0;
    int bits_in_buffer = 0;

    void write_bit(int bit) {
        buffer = (buffer << 1) | bit;
        bits_in_buffer++;
        if (bits_in_buffer == 8) {
            output.push_back(buffer);
            buffer = 0;
            bits_in_buffer = 0;
        }
    }

    void flush_bits() {
        if (bits_in_buffer > 0) {
            buffer <<= (8 - bits_in_buffer);
            output.push_back(buffer);
            buffer = 0;
            bits_in_buffer = 0;
        }
    }

    void encode_symbol(int symbol, uint32_t cum_freq, uint32_t freq, uint32_t total) {
        uint64_t range = high - low + 1;
        high = low + (range * (cum_freq + freq) / total) - 1;
        low = low + (range * cum_freq / total);

        while (true) {
            if (high < 0x80000000ULL) {
                write_bit_0();
            } else if (low >= 0x80000000ULL) {
                write_bit_1();
                low -= 0x80000000ULL;
                high -= 0x80000000ULL;
            } else if (0x40000000ULL <= low && low < 0x80000000ULL && 0x80000000ULL <= high && high < 0xC0000000ULL) {
                pending_bits++;
                low -= 0x40000000ULL;
                high -= 0x40000000ULL;
            } else {
                break;
            }

            low <<= 1;
            high = (high << 1) + 1;
        }
    }

    void write_bit_0() {
        write_bit(0);
        for (int i = 0; i < pending_bits; ++i) write_bit(1);
        pending_bits = 0;
    }

    void write_bit_1() {
        write_bit(1);
        for (int i = 0; i < pending_bits; ++i) write_bit(0);
        pending_bits = 0;
    }

    std::vector<uint8_t> finish() {
        pending_bits++;
        if (low < 0x40000000ULL) {
            write_bit_0();
        } else {
            write_bit_1();
        }
        flush_bits();
        return output;
    }
};

class RangeDecoder {
public:
    uint64_t low = 0;
    uint64_t high = 0xFFFFFFFFULL;
    uint64_t code = 0;
    const std::vector<uint8_t>& input;
    size_t input_pos = 0;
    uint8_t buffer = 0;
    int bits_in_buffer = 0;

    RangeDecoder(const std::vector<uint8_t>& data) : input(data) {
        for (int i = 0; i < 32; ++i) {
            code = (code << 1) | read_bit();
        }
    }

    int read_bit() {
        if (bits_in_buffer == 0) {
            if (input_pos < input.size()) {
                buffer = input[input_pos++];
                bits_in_buffer = 8;
            } else {
                return 0;
            }
        }
        int bit = (buffer >> 7) & 1;
        buffer = (buffer << 1) & 0xFF;
        bits_in_buffer--;
        return bit;
    }

    int decode_symbol(const std::vector<uint32_t>& cum_freqs) {
        uint32_t total = cum_freqs.back();
        uint64_t range = high - low + 1;
        uint64_t value = ((code - low + 1) * total - 1) / range;

        // Binary search for symbol
        auto it = std::lower_bound(cum_freqs.begin(), cum_freqs.end(), value);
        int symbol = it - cum_freqs.begin() - 1;

        // Update range
        high = low + (range * cum_freqs[symbol + 1] / total) - 1;
        low = low + (range * cum_freqs[symbol] / total);

        while (true) {
            if (high < 0x80000000ULL) {
                // pass
            } else if (low >= 0x80000000ULL) {
                low -= 0x80000000ULL;
                high -= 0x80000000ULL;
                code -= 0x80000000ULL;
            } else if (0x40000000ULL <= low && low < 0x80000000ULL && 0x80000000ULL <= high && high < 0xC0000000ULL) {
                low -= 0x40000000ULL;
                high -= 0x40000000ULL;
                code -= 0x40000000ULL;
            } else {
                break;
            }
            low <<= 1;
            high = (high << 1) + 1;
            code = (code << 1) | read_bit();
        }

        return symbol;
    }
};

std::vector<uint32_t> build_cumulative_freqs(const std::vector<uint32_t>& freqs) {
    std::vector<uint32_t> cum_freqs;
    cum_freqs.push_back(0);
    for (uint32_t f : freqs) {
        cum_freqs.push_back(cum_freqs.back() + f);
    }
    return cum_freqs;
}

std::vector<uint32_t> count_frequencies(const std::string& input_path) {
    std::ifstream file(input_path, std::ios::binary | std::ios::ate);
    if (!file) {
        throw std::runtime_error("Cannot open input file");
    }
    uint32_t file_size = file.tellg();
    file.seekg(0);

    size_t num_threads = std::thread::hardware_concurrency();
    if (num_threads == 0) num_threads = 4;  // fallback

    size_t chunk_size = file_size / num_threads;
    if (chunk_size < 1024) chunk_size = file_size;  // small file, one thread

    std::vector<std::vector<uint32_t>> local_freqs(num_threads, std::vector<uint32_t>(256, 0));
    std::vector<std::thread> threads;

    for (size_t i = 0; i < num_threads; ++i) {
        size_t start = i * chunk_size;
        size_t end = (i == num_threads - 1) ? file_size : (i + 1) * chunk_size;

        threads.emplace_back([&, i, start, end]() {
            std::ifstream loc_file(input_path, std::ios::binary);
            if (!loc_file) return;  // error, but ignore
            loc_file.seekg(start);
            size_t bytes_to_read = end - start;
            char byte;
            size_t count = 0;
            while (count < bytes_to_read && loc_file.read(&byte, 1)) {
                local_freqs[i][static_cast<uint8_t>(byte)]++;
                count++;
            }
        });
    }

    for (auto& t : threads) t.join();

    std::vector<uint32_t> freqs(256, 0);
    for (const auto& lf : local_freqs) {
        for (size_t j = 0; j < 256; ++j) freqs[j] += lf[j];
    }

    // Add 1 to avoid 0 probabilities
    for (auto& f : freqs) f++;
    return freqs;
}

void encode_file(const std::string& input_path, const std::string& output_path) {
    auto freqs = count_frequencies(input_path);
    auto cum_freqs = build_cumulative_freqs(freqs);
    uint32_t total = cum_freqs.back();

    // Get file length
    std::ifstream in_file(input_path, std::ios::binary | std::ios::ate);
    if (!in_file) {
        throw std::runtime_error("Cannot open input file");
    }
    uint32_t file_len = in_file.tellg();
    in_file.seekg(0);
    in_file.close();

    RangeEncoder encoder;

    // Uniform frequencies for header
    std::vector<uint32_t> uniform_freqs(256, 1);
    auto uniform_cum_freqs = build_cumulative_freqs(uniform_freqs);
    uint32_t uniform_total = uniform_cum_freqs.back();

    // Write file length (4 bytes) using uniform
    for (int i = 0; i < 4; ++i) {
        uint8_t byte = (file_len >> (i * 8)) & 0xFF;
        encoder.encode_symbol(byte, uniform_cum_freqs[byte], uniform_freqs[byte], uniform_total);
    }

    // Write frequencies (256 * 4 bytes)
    for (uint32_t freq : freqs) {
        for (int j = 0; j < 4; ++j) {
            uint8_t byte = (freq >> (j * 8)) & 0xFF;
            encoder.encode_symbol(byte, uniform_cum_freqs[byte], uniform_freqs[byte], uniform_total);
        }
    }

    // Encode data
    std::ifstream in(input_path, std::ios::binary);
    char byte;
    while (in.read(&byte, 1)) {
        int symbol = static_cast<uint8_t>(byte);
        encoder.encode_symbol(symbol, cum_freqs[symbol], freqs[symbol], total);
    }
    in.close();

    auto compressed = encoder.finish();

    std::ofstream out(output_path, std::ios::binary);
    if (!out) {
        throw std::runtime_error("Cannot open output file");
    }
    out.write(reinterpret_cast<const char*>(compressed.data()), compressed.size());
    out.close();
}

void decode_file(const std::string& input_path, const std::string& output_path) {
    std::ifstream in(input_path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("Cannot open input file");
    }
    std::vector<uint8_t> compressed((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    in.close();

    // Uniform for header
    std::vector<uint32_t> uniform_freqs(256, 1);
    auto uniform_cum_freqs = build_cumulative_freqs(uniform_freqs);
    uint32_t uniform_total = uniform_cum_freqs.back();

    RangeDecoder decoder(compressed);

    // Read file length
    uint32_t file_length = 0;
    for (int i = 0; i < 4; ++i) {
        int byte = decoder.decode_symbol(uniform_cum_freqs);
        file_length |= byte << (i * 8);
    }

    // Read frequencies
    std::vector<uint32_t> freqs(256);
    for (auto& freq : freqs) {
        freq = 0;
        for (int j = 0; j < 4; ++j) {
            int byte = decoder.decode_symbol(uniform_cum_freqs);
            freq |= byte << (j * 8);
        }
    }

    auto cum_freqs = build_cumulative_freqs(freqs);
    uint32_t total = cum_freqs.back();

    std::ofstream out(output_path, std::ios::binary);
    if (!out) {
        throw std::runtime_error("Cannot open output file");
    }
    for (uint32_t i = 0; i < file_length; ++i) {
        int symbol = decoder.decode_symbol(cum_freqs);
        out.write(reinterpret_cast<const char*>(&symbol), 1);
    }
    out.close();
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " encode input output | decode input output" << std::endl;
        return 1;
    }
    std::string mode = argv[1];
    std::string input = argv[2];
    std::string output = argv[3];

    if (mode == "encode") {
        encode_file(input, output);
    } else if (mode == "decode") {
        decode_file(input, output);
    } else {
        std::cerr << "Invalid mode. Use 'encode' or 'decode'." << std::endl;
        return 1;
    }

    return 0;
}
