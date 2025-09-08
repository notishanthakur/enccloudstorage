# Privacy-Preserving Cloud Storage with Searchable Encryption and Steganographic Key Management

## Introduction
To build a secure cloud storage system where files are AES-encrypted before upload, keyword search works over encrypted indexes (privacy-preserving), and all user keys + index mappings are stored steganographically in the user’s profile picture which is delivered once and stored locally — eliminating repeated key transmission and minimizing interception risk.

## Need
Even with encrypted files, cloud systems remain vulnerable when keys or searchable indexes are exposed, or when keys are transmitted with files. Attackers can intercept keys during transit or compromise DBs to retrieve keys. This project prevents those attack vectors by: <br>
• Never transmitting keys during regular operations. <br>
• Hiding keys + encrypted index mapping inside profile pictures (steganography). <br>
• Requiring client-side extraction of keys, so intercepted files are useless without the local stego image and extraction routine. <br>

## Requirements
Ensure python3.8+ is already installed <br><br>
`pip install pycryptodome`
<br>
`pip install stegano`
<br>
`apt-get install python3-tk`
<br><br>
Will be added in a requirements file later

## How to run?
1. Clone the repository <br>
`git clone https://github.com/notishanthakur/enccloudstorage`
2. Go to the directory <br>
`cd enccloudstorage`
3. Install Requirements as stated above (for now, manually)
4. Run the script <br>
`python3 GUI_demo.py` or `python GUI_demo.py`
## WorkFlow
### Steps
1. Give user an option to upload file to cloud storage <br>
(Here a file named report.txt with content "Patient record: Diabetes treatment plan" is generated) <br>
2. Encrypt the file and save as report.enc, key is stored as a variable for now <br>
(File is uploaded to the server and the server sends a blob id) <br>
3. Extract keywords from files and encrypt those keywords using SHA256 and create a hashmap of (encrypted keywords:blob id) <br>
(To implement NLP based extraction) <br>
(Instead of using blob id to create hashmap we just use report.enc) <br>
3. Now using stegano, we make a json of the key, hashmap and hide that behind profile.jpg and store that as profile_stegano.jpg (on client side) <br>
(Can be seen using reveal.py) <br>
4. User gets an option to search for the keyword <br>
5. The keyword is encrypted using SHA256 <br>
6. Json is extracted from profile_stegano.jpg <br>
(Here we just use the index_map variable) <br>
7. If encrypted keyword is found in the hashmap, the file is called from server and then decrypted at client using the aes key obtained <br>
(Here we just get the filename and then decryption is done) <br>
8. The file is then shown to the user <br>
(Here we just display the content) <br>

### Diagrams
<b>First Upload</b>
<img width="946" height="571" alt="First Upload" src="https://github.com/user-attachments/assets/a5f9f499-aadb-401c-a7fc-facc8373ab6d" />
<br>
<b>Retrieving</b>
<img width="946" height="571" alt="Retrieving" src="https://github.com/user-attachments/assets/17cdbb20-3749-4794-92f1-3f2d7704f436" />


### Changelog
1. Added GUI using tkinter
2. Using png instead of jpg

### Roadmap

  ~~1. Prepare initial CLI demo interface~~ <br>
  ~~2. Convert CLI to GUI~~ <br>
  
  3. Transfer codebase from tkinter to webapp deployable stack <br>
  4. Make the program robust by expanding user-selectable options <br>
  5. Implementation of NLP api <br>
  6. Initial deployment using local DB <br>
  7. White Box Testing <br>
  8. Code Cleanup and Frontend Designing <br>
  9. Black Box Testing <br>
  10. Deploying online using Vercel and Azure Blob <br>

## Please star the repository and contribute💫
