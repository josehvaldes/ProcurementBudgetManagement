import tempfile
from pdf2image import convert_from_path
from pyzbar.pyzbar import decode
from PIL import Image
import os
import io
from shared.models.qr_info import QRInfo


async def validate_url(url:str)-> bool:
    pass

async def get_qr_info_from_bytes(raw_bytes_image:bytes)-> list[QRInfo]:
    qr_list = []
    img = Image.open(io.BytesIO(raw_bytes_image))

    # Decode the image
    decoded_objects = decode(img)

    for obj in decoded_objects:
        data = obj.data.decode('utf-8')
        qr = QRInfo(data=data, location=(obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height))
        qr_list.append(qr)

    return qr_list

async def get_qr_info_from_image(image_path:str)-> list[QRInfo]:
    qr_list = []
    # Check if the file exists for a robust sample
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at '{image_path}'")
        print("Please place a barcode or QR code image in the script's directory.")
        return []
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
                # The data is returned as bytes, decode to utf-8 string
                data = obj.data.decode('utf-8')

                qr = QRInfo(data=data, location=(obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height))
                qr_list.append(qr)
    return qr_list


async def get_qr_info_from_pdf(pdf_path:str)-> list[QRInfo]:
    qr_list = []
    with tempfile.TemporaryDirectory() as path:
        images = convert_from_path(pdf_path, output_folder=path, fmt="png")
        for i, image in enumerate(images):
            # Decode barcodes/QR codes from the image
            decoded_objects = decode(image)
            if decoded_objects:
                for obj in decoded_objects:
                    data = obj.data.decode('utf-8')
                    qr = QRInfo(data=data, location=(obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height))
                    qr_list.append(qr)
            else:
                print("No barcodes or QR codes found.")
    return qr_list