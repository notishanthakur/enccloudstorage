import os, hashlib, json
from tkinter import Tk, Button, Label, Text, filedialog, Entry, END
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from stegano import lsb


def pad(data: bytes) -> bytes:
    return data + b"\0" * (AES.block_size - len(data) % AES.block_size)

def encrypt_file(filename, key):
    with open(filename, "rb") as f:
        plaintext = f.read()
    cipher = AES.new(key, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(plaintext))
    return cipher.iv + ciphertext

def decrypt_file(ciphertext, key):
    iv = ciphertext[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(ciphertext[AES.block_size:])
    return plaintext.rstrip(b"\0")

def extract_keywords(text):
    words = text.lower().split()
    stopwords = {"the", "a", "an", "is", "and", "of", "to", "in"}
    return [w.strip(",.!?") for w in words if w not in stopwords]

def hash_keyword(word):
    return hashlib.sha256(word.encode()).hexdigest()

aes_key = None
index_map = {}
enc_file = "report.enc"
profile_img = "profile.png"
stego_img = "profile_stego.png"
demo_text = "Patient record: Diabetes treatment plan"
found=False

def step_encrypt():
    global aes_key
    aes_key = get_random_bytes(32)
    with open("report.txt", "w") as f:
        f.write(demo_text)
    ciphertext = encrypt_file("report.txt", aes_key)
    with open(enc_file, "wb") as f:
        f.write(ciphertext)
    output.insert(END, "Step 1: File encrypted → report.enc created\n")

def step_keywords():
    global index_map
    keywords = extract_keywords(demo_text)
    index_map = {hash_keyword(w): enc_file for w in keywords}
    output.insert(END, f"Step 2: Extracted keywords: {keywords}\n")
    output.insert(END, f"Encrypted index (hashes): {list(index_map.keys())}\n\n")

def step_embed():
    payload = {"aes_key": aes_key.hex(), "index": index_map}
    payload_str = json.dumps(payload)
    stego_image = lsb.hide(profile_img, payload_str)
    stego_image.save(stego_img)
    output.insert(END, "Step 3: AES key + index embedded inside profile_stego.png\n\n")

def step_reveal():
    hidden_payload = lsb.reveal(stego_img)
    output.insert(END, "Step 4: Data hidden in image:\n")
    output.insert(END, hidden_payload + "\n\n")

def step_search():
    global found
    search_word = search_entry.get().strip().lower()
    if not search_word:
        output.insert(END, "Please enter a keyword to search.\n")
    search_token = hash_keyword(search_word)
    if search_token in index_map:
        output.insert(END, f"Step 5: Match found for '{search_word}' → {index_map[search_token]}\n\n")
        found=True
    else:
        output.insert(END, f"No match found for '{search_word}'\n\n")

def step_decrypt():
    global found
    if(not(found)):
        output.insert(END, "Cannot Decrypt\n")
        return
    hidden_payload = lsb.reveal(stego_img)
    recovered = json.loads(hidden_payload)
    recovered_key = bytes.fromhex(recovered["aes_key"])
    with open(enc_file, "rb") as f:
        enc_data = f.read()
    decrypted_text = decrypt_file(enc_data, recovered_key).decode()
    output.insert(END, "Step 6: File decrypted → content is:\n")
    output.insert(END, decrypted_text + "\n\n")

#gui
root = Tk()
root.title("Privacy-Preserving Cloud Storage Demo")
root.geometry("800x600")

Label(root, text="Keyword Search:").pack()
search_entry = Entry(root, width=30)
search_entry.pack()

Button(root, text="Encrypt File", command=step_encrypt).pack(pady=3)
Button(root, text="Show Keywords + Index", command=step_keywords).pack(pady=3)
Button(root, text="Embed in Profile Picture", command=step_embed).pack(pady=3)
Button(root, text="Reveal Hidden Data", command=step_reveal).pack(pady=3)
Button(root, text="Search Keyword", command=step_search).pack(pady=3)
Button(root, text="Decrypt File", command=step_decrypt).pack(pady=3)

Label(root, text="Output:").pack()
output = Text(root, height=25, width=100)
output.pack()

root.mainloop()
