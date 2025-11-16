from PIL import Image
from io import BytesIO

def create_thumbnail(image_bytes, size=(250,250)):
    img = Image.open(BytesIO(image_bytes))
    img.thumbnail(size)
    
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
