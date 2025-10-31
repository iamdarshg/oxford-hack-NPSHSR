import asyncio
import aiohttp
import random
import string
import hashlib
from concurrent.futures import ThreadPoolExecutor

# Pre-compute characters for faster random generation
VALID_CHARS = string.ascii_letters + string.digits + "-_"
CHARS_LEN = len(VALID_CHARS)

def generate_random_video_id():
    # Use system random for better performance
    return ''.join(random.SystemRandom().choices(VALID_CHARS, k=11))

async def check_thumbnail(session, video_id, semaphore):
    # Use semaphore to limit concurrent connections
    async with semaphore:
        url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        try:
            async with session.head(url, timeout=2) as resp:  # Add timeout
                return resp.status == 200, video_id
        except:
            return False, video_id

async def generate_valid_youtube_links(n=100, batch_size=50, max_concurrent=20):
    valid_ids = set()
    # Configure client session with optimized settings
    conn = aiohttp.TCPConnector(limit=max_concurrent, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=10)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        while len(valid_ids) < n:
            # Generate video IDs in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                video_ids = list(executor.map(lambda _: generate_random_video_id(), range(batch_size)))
            
            # Create tasks with semaphore
            tasks = [check_thumbnail(session, vid, semaphore) for vid in video_ids]
            
            # Gather results with timeout
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, tuple):  # Filter out exceptions
                        valid, vid = result
                        if valid and len(valid_ids) < n and vid not in valid_ids:
                            valid_ids.add(vid)
                            print(f"Found {len(valid_ids)} / {n}: https://www.youtube.com/watch?v={vid}")
            except asyncio.TimeoutError:
                continue
            
            # Increase batch size dynamically if success rate is low
            if len(valid_ids) < n/4:
                batch_size = min(batch_size * 2, 200)
    
    return list(valid_ids)

def map_hashes_to_video(user_hash, receiver_hash, video_list):
    # Use faster string concatenation
    combined = ''.join((user_hash, receiver_hash))
    # Pre-encode string
    combined_bytes = combined.encode('utf-8')
    combined_hash = hashlib.sha256(combined_bytes).digest()  # Use digest() instead of hexdigest()
    # Use faster integer conversion
    hash_int = int.from_bytes(combined_hash[:8], byteorder='big')
    return video_list[hash_int % len(video_list)]

if __name__ == "__main__":
    n = 100  # Number of videos to generate
    user_hash = "exampleUserHash123"
    receiver_hash = "exampleReceiverHash456"

    # Configure event loop with optimized settings
    loop = asyncio.new_event_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=4))
    asyncio.set_event_loop(loop)
    
    video_list = loop.run_until_complete(generate_valid_youtube_links(n))
    loop.close()

    mapped_video = map_hashes_to_video(user_hash, receiver_hash, video_list)
    print("\nMapped video for given user and receiver hashes:")
    print(mapped_video)