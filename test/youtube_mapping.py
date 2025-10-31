import random
import string
import requests
import hashlib

def generate_random_video_id():
    chars = string.ascii_letters + string.digits + "-_"
    return ''.join(random.choice(chars) for _ in range(11))

def is_thumbnail_available(video_id):
    url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    response = requests.head(url)
    return response.status_code == 200

def generate_valid_youtube_links_without_api(n=100):
    valid_links = set()
    print("Generating valid YouTube video links based on thumbnail existence. This may take some time...")
    while len(valid_links) < n:
        vid_id = generate_random_video_id()
        if is_thumbnail_available(vid_id):
            link = f"https://www.youtube.com/watch?v={vid_id}"
            if link not in valid_links:
                valid_links.add(link)
                print(f"Found {len(valid_links)} / {n}: {link}")
    return list(valid_links)

def map_hashes_to_video(user_hash, receiver_hash, video_list):
    combined = user_hash + receiver_hash
    combined_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    hash_int = int(combined_hash, 16)
    video_index = hash_int % len(video_list)
    return video_list[video_index]

if __name__ == "__main__":
    # Step 1: Generate 100 valid YouTube links (approximate, without official API)
    video_list = generate_valid_youtube_links_without_api(100)

    # Step 2: Map user and receiver hashes to a video
    user_hash = "exampleUserHash123"
    receiver_hash = "exampleReceiverHash456"
    mapped_video = map_hashes_to_video(user_hash, receiver_hash, video_list)
    
    print("\nMapped video for given user and receiver hashes:")
    print(mapped_video)
