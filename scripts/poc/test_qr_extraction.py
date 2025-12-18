import argparse
import asyncio
import tempfile
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode
from PIL import Image
import os
import aiohttp

async def get_url(url:str):
    response = None    
    code = None
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            code = response.status
            response = await response.read()
            
    print(f"   URL Response code: {code}, Fetched {len(response)} bytes from {url}")
    string = response.decode('utf-8')
    return string

async def analyze_qr_code(image_path:str):
    
    # Check if the file exists for a robust sample
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at '{image_path}'")
        print("Please place a barcode or QR code image in the script's directory.")
    else:
        # Open the image using Pillow
        img = Image.open(image_path)

        # Decode the barcodes/QR codes in the image
        decoded_objects = decode(img)

        # Process and print the detected objects
        if not decoded_objects:
            print("No barcode or QR code detected in the image.")
        else:
            print(f"Detected {len(decoded_objects)} barcode(s):")
            for obj in decoded_objects:
                print(f"* Type: {obj.type}")
                # The data is returned as bytes, decode to utf-8 string
                data = obj.data.decode('utf-8')
                print(f"  Data: {data}")
                print(f"  Location: {obj.rect}")
                content = await get_url(data)  # Fetch content from the URL
                print("  Fetched Content Preview:")
                print(content[:200])  # Print first 200 characters of the content
                print("-" * 20)

async def analyze_qr_code_in_pdf(pdf_path:str):
    with tempfile.TemporaryDirectory() as path:
        images = convert_from_path(pdf_path, output_folder=path, fmt="png")
        for i, image in enumerate(images):
            # Decode barcodes/QR codes from the image
            decoded_objects = decode(image)

            if decoded_objects:
                print(f"\n--- Page {i + 1} ---")
                for obj in decoded_objects:
                    print(f"*  Type: {obj.type}")
                    data = obj.data.decode('utf-8')
                    print(f"   Data: {data}") # Decode bytes to string
                    print(f"   Location: {obj.rect}")
                    content = await get_url(data)  # Fetch content from the URL
                    print("  Fetched Content Preview:")
                    print(content[:200])  # Print first 200 characters of the content
            else:
                print(f"\n--- Page {i + 1} ---")
                print("No barcodes or QR codes found.")

if __name__ == "__main__":
    
    print("Testing QR code extraction from image...")
    path = "./scripts/poc/sample_documents/receipts/VALDES_251216_image.jpg"
    asyncio.run(analyze_qr_code(path))

    # You can replace the above path with any image file path containing a barcode or QR code
    path_pdf = "./scripts/poc/sample_documents/receipts/VALDES_251216_114858.pdf"
    print("\nTesting with PDF file...")
    asyncio.run(analyze_qr_code_in_pdf(path_pdf))