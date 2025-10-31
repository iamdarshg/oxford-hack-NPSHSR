# Range Encoding for File Compression

Range encoding (also known as arithmetic coding) is a powerful data compression technique that can achieve optimal compression ratios, especially for files with highly skewed probability distributions like grayscale images.

## How Range Encoding Works

Range encoding represents a sequence of symbols by a single number within an interval between 0 and 1. Here's how it works:

1. **Initial Range**: Start with the interval [0, 1)
2. **Symbol Processing**: For each symbol:
   - Divide the current interval proportionally based on symbol probabilities
   - Select the subinterval corresponding to the current symbol
   - This becomes the new working interval

### Example with Grayscale Images (GRFiles)

Consider a grayscale image where:
- Each pixel is represented by a value from 0-255
- Some pixel values appear more frequently than others

```
Initial range: [0, 1)
For pixel value 128 with probability 0.3:
New range = [0.4, 0.7) (example)
```

## Why Range Encoding is Efficient for GRFiles

1. **Adaptive Probability Models**
   - Grayscale images often have local areas of similar values
   - Range encoder can adapt to changing statistics
   - Achieves better compression than fixed-probability models

2. **Continuous Range**
   - Unlike Huffman coding, range encoding isn't limited to whole bits
   - Can represent probabilities more precisely
   - Especially effective for skewed distributions common in images

3. **Context Modeling**
   - Can use neighboring pixels to predict current pixel
   - Improves compression by exploiting spatial correlations
   - Particularly effective for smooth gradients in grayscale images

## Implementation Details

Our implementation in `rangenc.py` uses:
- 32-bit arithmetic for range boundaries
- Frequency tables for symbol probabilities
- Underflow handling for long sequences

Key components:
```python
class RangeEncoder:
    def __init__(self):
        self.low = 0
        self.high = 0xFFFFFFFF  # Full 32-bit range
```

## Compression Performance

For typical grayscale images:
- Uncompressed: 8 bits per pixel
- Range encoded: 4-6 bits per pixel (typical)
- Additional savings with context modeling

### Best Use Cases

1. Medical imaging (X-rays, CT scans)
2. Scientific data with gradual variations
3. Depth maps and height fields
4. Texture maps with smooth gradients

## Usage Example

To compress a grayscale file:
1. Read the input file as bytes
2. Build frequency table from pixel values
3. Apply range encoding with context modeling
4. Write compressed output

## Advanced Features

1. **Streaming Operation**
   - Can encode/decode without full file in memory
   - Useful for large images or real-time processing

2. **Error Resilience**
   - Optional synchronization markers
   - Recovery from bit errors in compressed stream

3. **Progressive Transmission**
   - Send most significant bits first
   - Allows preview while downloading

## Performance Optimization

To achieve maximum compression:
1. Use adaptive probability models
2. Implement context modeling
3. Balance precision vs speed in arithmetic
4. Consider SIMD operations for encoding/decoding

## Memory Usage

The implementation maintains:
- Current range bounds (8 bytes)
- Frequency tables (~1KB typical)
- Small input/output buffers
- Optional context model state

## Limitations and Considerations

1. **Computational Complexity**
   - More CPU-intensive than simple methods
   - Each symbol requires multiple multiplications

2. **Error Propagation**
   - Single bit errors can corrupt subsequent data
   - Use synchronization markers for robustness

3. **Patent Status**
   - Original arithmetic coding patents expired
   - Range encoding variants are freely usable

## Further Reading

1. Range Encoding: An Algorithm for Removing Redundancy from a Digitized Message
2. Arithmetic Coding for Data Compression
3. Practical Implementations of Arithmetic Coding

Remember: Range encoding is particularly effective when combined with good probability modeling and context prediction, making it ideal for grayscale image compression where pixel values are often highly correlated with their neighbors.