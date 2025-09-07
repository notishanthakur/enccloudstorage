from stegano import lsb
msg = lsb.reveal("profile_stego.png")
print("Hidden message:", msg)
