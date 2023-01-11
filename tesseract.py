import cv2

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract

class Tesseract():
    lib_path=''
    def __init__(self, lib_path=None) :
        if lib_path:
            pytesseract.pytesseract.tesseract_cmd = lib_path
    # 识别图片中的字符串
    def recongnize(self,img):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        return pytesseract.image_to_string(img_rgb,lang='chi_sim')

    # 识别图片中的字符串
    def recongnize_num(self,img):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        return pytesseract.image_to_string(img_rgb,lang='chi_sim')