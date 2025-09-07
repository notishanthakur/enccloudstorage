### Requirements
pip install pycryptodome
<br>
pip install stegano

### WorkFlow

Generate a file named report.txt with content "Patient record: Diabetes treatment plan" 
1. Encrypt the file and save as report.enc, key is stored as a variable for now 
(file is uploaded to the server and the server sends a blob id)
2. Extract keywords from files and encrypt those keywords using SHA256 and create a hashmap of (encrypted keywords:blob id)
(to implement NLP based extraction)
(instead of using blob id to create hashmap we just use report.enc)
3. Now using stegano, we make a json of the key, hashmap and hide that behind profile.jpg and store that as profile_stegano.jpg (on client side)
(can be seen using reveal.py)
4. User gets an option to search for the keyword
5. keyword is encrypted using SHA256 
6. json is extracted from profile_stegano.jpg
(here we just use the index_map variable)
7. if encrypted keyword is found in the hashmap, the file is called from server and then decrypted at client using the aes key obtained
(here we just get the filename and then decryption is done)
8. the file is then shown to the user
(here we just display the content)
