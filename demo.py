import os, hashlib, json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from stegano import lsb

def pad(data: bytes) -> bytes:
    """Pad plaintext to be multiple of 16 bytes (AES block size)."""
    return data + b"\0" * (AES.block_size - len(data) % AES.block_size)

def encrypt_file(filename, key):
    """Encrypt file contents with AES."""
    with open(filename, "rb") as f:
        plaintext = f.read()
    cipher = AES.new(key, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(plaintext))
    return cipher.iv + ciphertext  # prepend IV

def decrypt_file(ciphertext, key):
    """Decrypt AES-encrypted file contents."""
    iv = ciphertext[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(ciphertext[AES.block_size:])
    return plaintext.rstrip(b"\0")

#to use NLP api to simplify extracting keywords
def extract_keywords(text):
    """Simple keyword extractor (split by space)."""
    words = text.lower().split()
    stopwords = {"the", "a", "an", "is", "and", "of", "to", "in"}
    return [w.strip(",.!?") for w in words if w not in stopwords]

def hash_keyword(word):
    """Hash keyword with SHA-256."""
    return hashlib.sha256(word.encode()).hexdigest()

#create file/ later to implement read content from files
demo_text = "Patient record: Diabetes treatment plan" 
with open("report.txt", "w") as f: 
    f.write(demo_text)
print("Original file content:", demo_text)

#aes256
aes_key = get_random_bytes(32)
ciphertext = encrypt_file("report.txt", aes_key)
with open("report.enc", "wb") as f:
    f.write(ciphertext)
print("\nFile encrypted → saved as report.enc")

#to upload file to server and receive blob id, which is stored with keys behind pfp
#here we just store the filename instead of blob id
#keyword and index
keywords = extract_keywords(demo_text)
index_map = {hash_keyword(w): "report.enc" for w in keywords}

print("\nExtracted keywords:", keywords)
print("Encrypted index (hashes):", list(index_map.keys()))


#stegano hiding behind pfp
payload = {"aes_key": aes_key.hex(), "index": index_map}
payload_str = json.dumps(payload)
#using only profile.jpg/ later to implement random image generation/selection option
stego_image = lsb.hide("profile.jpg", payload_str)
stego_image.save("profile_stego.png")
print("\nAES key + index embedded inside profile_stego.png")

#Searching for keyword
print("Enter word to search: ")
search_word = input().strip()
search_token = hash_keyword(search_word)
print(f"\nSearching for '{search_word}' → token:", search_token)

#searching in index dictionary/hashmap
if search_token in index_map:
    enc_file = index_map[search_token]
    print("Match found →", enc_file)

    #extracting key
    hidden_payload = lsb.reveal("profile_stego.png")
    recovered = json.loads(hidden_payload)
    recovered_key = bytes.fromhex(recovered["aes_key"])

    #here the encrypted file is called from server using blob id (azure blob storage)

    #decrypting file
    with open(enc_file, "rb") as f:
        enc_data = f.read()
    decrypted_text = decrypt_file(enc_data, recovered_key).decode()

    print("\nDecrypted file content:", decrypted_text)
else:
    print("No match found.")
