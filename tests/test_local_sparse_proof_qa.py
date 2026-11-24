import unittest, tempfile, hashlib
from pathlib import Path
from PIL import Image, ImageDraw
from cloud_proof_report import proof_capture
from monitor import article_id
class LocalSparseProofTests(unittest.TestCase):
    def test_accepted_sparse_jpeg_survives_second_gate(self):
        url='https://hapijournal.com/example'
        row={'id':article_id(url),'url':url,'headline':'Planning ministry launches new strategy','source':'Hapi native news RSS'}
        feeds=[{'name':row['source'],'allowed_article_hosts':['hapijournal.com','www.hapijournal.com']}]
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'verified.jpg'
            def capture(u,publisher,target):
                im=Image.new('RGB',(800,500),'white')
                draw=ImageDraw.Draw(im)
                draw.rectangle((0,0,799,80),fill=(15,32,65))
                draw.rectangle((30,120,740,145),fill=(33,48,74))
                im.save(target,'JPEG',quality=20,optimize=True)
                self.assertGreaterEqual(target.stat().st_size,3000)
                self.assertLess(target.stat().st_size,8000)
                return {'ok':True,'actual_url':url,'title':row['headline'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
            self.assertEqual(proof_capture(row,feeds,dest,capture=capture)['status'],'verified')
if __name__=='__main__':unittest.main()

