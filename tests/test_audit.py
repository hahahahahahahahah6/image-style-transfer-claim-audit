import unittest
from image_style_transfer_claim_audit import phrases

class PhraseOracle(unittest.TestCase):
    def test_exact_lists(self):
        self.assertEqual(phrases.STYLETRANSFER, ('style transfer', 'neural style transfer', 'artistic style transfer', 'image style transfer', 'photo style transfer', 'arbitrary style transfer', 'real time style transfer', 'fast style transfer', 'turn photos into paintings', 'turns photos into paintings', 'turn your photos into paintings', 'photo to painting', 'photos to paintings', 'image to painting', 'turn images into paintings', 'turns images into paintings', 'paint your photos', 'paints your photos', 'in the style of van gogh', 'van gogh style', 'in the style of picasso', 'picasso style', 'in the style of monet', 'monet style', 'apply a style to an image', 'applies a style to an image', 'apply the style of one image to another', 'applies the style of one image to another', 'transfer the style of one image to another', 'transfers the style of one image to another', 'style of a reference image', 'restyle your photos', 'restyles your photos', 'restyle images', 'stylize your photos', 'stylizes your photos', 'stylize images', 'stylizes images', 'stylized images', 'stylised images', 'pencil sketch effect', 'pencil sketch filter', 'oil painting effect', 'oil painting filter', 'watercolor effect', 'cartoon effect', 'cartoonize your photos', 'cartoonizes your photos', 'turn photos into cartoons', 'turns photos into cartoons'))
        self.assertEqual(phrases.NOSTYLETRANSFER, ('no style transfer', 'does not do style transfer', 'does not perform style transfer', 'does not support style transfer', 'without style transfer', 'no neural style transfer', 'does not stylize images', 'does not stylize photos', 'no stylization', 'does not apply styles to images', 'no artistic style transfer', 'does not turn photos into paintings', 'does not restyle images', 'no image style transfer', 'does not transfer styles', 'does not support artistic styles', 'no photo to painting', 'does not cartoonize photos', 'no pencil sketch effect', 'does not generate stylized images', 'no oil painting effect', 'style transfer not supported', 'stylization not supported', 'no style transfer support'))
        self.assertEqual(phrases.GENERIC_NAMES, ('stylize', 'style_transfer', 'transfer_style', 'apply_style', 'apply_style_transfer', 'neural_style_transfer', 'artistic_style_transfer', 'adain', 'stylize_image', 'stylize_photo', 'stylise', 'stylise_image', 'style_image', 'restyle', 'restyle_image', 'cartoonize', 'cartoonise', 'oil_paint', 'oil_painting', 'pencil_sketch', 'stylization', 'apply_artistic_style', 'transfer_artistic_style', 'style_mixing'))

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from image_style_transfer_claim_audit.audit import audit, claims, has_evidence, main

URL = 'https://tfhub.dev/google/magenta/arbitrary-image-stylization-v1-256/2'
GOOD = {
 'cv_stylization': 'import cv2\ncv2.stylization(image)',
 'cv_pencil': 'import cv2\ncv2.pencilSketch(image)',
 'cv_oil': 'import cv2\ncv2.xphoto.oilPainting(image)',
 'cv_from': 'from cv2 import pencilSketch as sketch\nsketch(image)',
 'cv_alias': 'import cv2 as c\nc.pencilSketch(image)',
 'hub_load': f'import tensorflow_hub as hub\nm=hub.load({URL!r})\nm(content, style)',
 'hub_layer': f'import tensorflow_hub as hub\nm=hub.KerasLayer({URL!r})\nm(content, style)',
 'hub_chain': f'import tensorflow_hub as hub\nhub.load({URL!r})(content, style)',
 'hub_from': f'from tensorflow_hub import load as get\nm=get({URL!r})\nm(content, style)',
 'hub_keyword': f'import tensorflow_hub as hub\nm=hub.load(handle={URL!r})\nm(content, style)',
 'fast': 'from transformer_net import TransformerNet\nm=TransformerNet()\nm(content)',
 'fast_chain': 'from neural_style.transformer_net import TransformerNet\nTransformerNet().forward(content)',
 'fast_alias': 'from transformer_net import TransformerNet as T\nm=T()\nm(content)',
 'annotated': f'import tensorflow_hub as hub\nm: object=hub.load({URL!r})\nm(content, style)',
 'with': f'import tensorflow_hub as hub\nwith hub.load({URL!r}) as m:\n m(content, style)',
 'async_with': f'import tensorflow_hub as hub\nasync def run():\n async with hub.load({URL!r}) as m:\n  m(content, style)',
 'generic_from': 'from effects import stylize as render\nrender(image)',
}
for generic in phrases.GENERIC_NAMES:
    GOOD['generic_' + generic] = 'x.' + generic + '(image)'
BAD = {
 'bare_cv': 'import cv2', 'bare_hub': 'import tensorflow_hub',
 'lone_hub': f'import tensorflow_hub as hub\nm=hub.load({URL!r})',
 'wrong_url': "import tensorflow_hub as hub\nm=hub.load('other')\nm(content, style)",
 'lone_fast': 'from transformer_net import TransformerNet\nm=TransformerNet()',
 'unbound': 'import tensorflow_hub as hub\nm(content, style)',
 'other_bound': 'import transformer_net\nm=Other()\nm(content)',
 'detail': 'import cv2\ncv2.detailEnhance(image)',
 'edge': 'import cv2\ncv2.edgePreservingFilter(image)',
 'generation': 'from diffusers import StableDiffusionImg2ImgPipeline\np=StableDiffusionImg2ImgPipeline()\np(image)',
 'color': 'x.colorize(image)', 'inpaint': 'x.inpaint(image)',
 'upscale': 'x.upscale(image)', 'denoise': 'x.denoise(image)',
 'resize': 'x.resize(image)', 'crop': 'x.crop(image)',
 'filter': 'import cv2\ncv2.filter2D(image)\ncv2.GaussianBlur(image)',
 'subprocess': "import subprocess\nsubprocess.run(['style-transfer', 'image'])",
 'shadow': 'from effects import stylize\ndef stylize(x): pass\nstylize(image)',
 'shadow_method': 'class X:\n def stylize(self): pass\nx.stylize(image)',
 'shadow_alias': 'from effects import stylize as s\ndef s(x): pass\ns(image)',
 'shadow_module': 'import cv2\nclass cv2: pass\ncv2.pencilSketch(image)',
 'shadow_binding': 'import cv2\ncv2=Other()\ncv2.pencilSketch(image)',
 'bare_name': 'stylize(image)', 'reference': 'from effects import stylize\nstylize',
 'string': "s='x.stylize(image)'\n# x.stylize(image)",
 'css': "css='body {color: red}'", 'syntax': 'x.stylize(',
 'no_gate': 'TransformerNet()(image)',
}

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main(['audit', str(self.root), *args])
        return code, out.getvalue()

    def test_good(self):
        self.write('README.md', 'style transfer')
        self.write('app.py', GOOD['cv_stylization'])
        self.assertEqual(self.cli()[0], 0)
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_bad(self):
        self.write('README.md', 'style transfer')
        self.write('app.py', 'pass')
        code, output = self.cli()
        self.assertEqual(code, 2)
        self.assertIn('documented-image-style-transfer-claim-false HIGH', output)

    def test_test_only(self):
        self.write('README.md', 'style transfer')
        self.write('tests/helper.py', GOOD['cv_stylization'])
        self.assertEqual(self.cli()[0], 0)
        self.assertEqual(self.cli('--fail-on', 'medium')[0], 2)
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')

    def test_denial(self):
        self.write('README.md', 'no style transfer')
        self.write('app.py', GOOD['cv_stylization'])
        code, output = self.cli()
        self.assertEqual(code, 2)
        self.assertIn('documented-no-image-style-transfer-claim-false HIGH', output)

    def test_no_claim(self):
        self.write('README.md', 'A utility.')
        self.assertEqual(self.cli()[0], 0)

    def test_no_source(self):
        self.write('README.md', 'style transfer')
        self.assertEqual(self.cli()[0], 2)
        self.write('README.md', 'no style transfer')
        self.assertEqual(self.cli()[0], 0)

    def test_fences(self):
        for fence in ('```', '~~~', '   ````'):
            self.assertEqual(claims(fence+'\nstyle transfer\n'+fence), (False, False))
        self.assertEqual(claims('    ```\nstyle transfer\n    ```'), (True, False))

    def test_inline(self):
        self.assertEqual(claims('`style transfer`'), (True, False))

    def test_normalization(self):
        self.assertEqual(claims("doesn't do STYLE-TRANSFER"), (False, True))
        self.assertEqual(claims('style\ntransfer'), (True, False))
        self.assertEqual(claims('style\n\ntransfer'), (False, False))
        self.assertEqual(claims('xstyle transferx'), (False, False))
        self.assertEqual(claims('no style transfer. We stylize images.'), (True, True))

    def test_split_modules(self):
        self.write('README.md', 'style transfer')
        self.write('a.py', GOOD['hub_load'].rsplit('\n', 1)[0])
        self.write('b.py', 'm(content, style)')
        self.assertEqual(self.cli()[0], 2)

    def test_exclusions(self):
        self.write('README.md', 'style transfer')
        for name in ('fixtures/a.py', 'docs/a.py', 'examples/a.py'):
            self.write(name, GOOD['cv_stylization'])
        self.assertEqual(audit(self.root)['evidence']['production'], [])
        for name in ('test_a.py', 'a_test.py'):
            self.write(name, GOOD['cv_stylization'])
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')

    def test_symlinks(self):
        self.write('README.md', 'style transfer')
        source = self.write('fixtures/a.py', GOOD['cv_stylization'])
        (self.root/'linked.py').symlink_to(source)
        (self.root/'linked').symlink_to(source.parent, target_is_directory=True)
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_docs_and_ignore(self):
        self.write('nested/docs/guide.md', 'style transfer')
        self.write('other.md', 'no style transfer')
        self.assertEqual(self.cli()[0], 2)
        self.assertEqual(self.cli('--ignore', 'nested', '--ignore', 'unused')[0], 0)

    def test_json(self):
        self.write('README.md', 'style transfer')
        code, output = self.cli('--json')
        data = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(data['verdict'], 'FAIL')
        self.assertIsInstance(data['findings'][0]['message'], str)

    def test_errors(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', str(self.root/'missing')]), 1)
            for args in ([], ['audit', '--bad'], ['audit', '--fail-on', 'MEDIUM']):
                with self.assertRaises(SystemExit) as exc:
                    main(args)
                self.assertEqual(exc.exception.code, 1)

    def test_version_and_module_entry(self):
        result = subprocess.run([sys.executable, '-m', 'image_style_transfer_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '0.1.0')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(SystemExit) as exc:
                main(['--version'])
        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), '0.1.0')

    def test_route_constants(self):
        self.assertEqual(phrases.OPENCV_NAMES, ('stylization', 'pencilSketch'))
        self.assertEqual(phrases.OPENCV_XPHOTO_NAMES, ('oilPainting',))
        self.assertEqual(phrases.OPENCV_IMPORT, 'cv2')
        self.assertEqual(phrases.MAGENTA_NAMES, ('load', 'KerasLayer'))
        self.assertEqual(phrases.MAGENTA_URL, 'arbitrary-image-stylization')
        self.assertEqual(phrases.MAGENTA_IMPORT, 'tensorflow_hub')
        self.assertEqual(phrases.FAST_NAMES, ('TransformerNet',))
        self.assertEqual(phrases.FAST_IMPORTS, ('transformer_net', 'neural_style'))


def evidence_test(source, expected):
    def test(self):
        self.assertEqual(has_evidence(source), expected, source)
    return test

for label, source in GOOD.items():
    setattr(AuditTests, 'test_evidence_' + label, evidence_test(source, True))
for label, source in BAD.items():
    setattr(AuditTests, 'test_not_evidence_' + label, evidence_test(source, False))

if __name__ == '__main__':
    unittest.main()
