from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase


class SubtitleEncodingTests(SimpleTestCase):
    @patch('converter.views._request_translation_batch', return_value=['Hello world.'])
    def test_gb18030_chinese_subtitle_translates_to_english(self, translate):
        subtitle = '1\n00:00:01,000 --> 00:00:03,000\n你好，世界。\n'
        upload = SimpleUploadedFile('chinese.srt', subtitle.encode('gb18030'))

        response = self.client.post('/converter/', {
            'subtitle': upload,
            'target_language': 'en',
            'translation_mode': 'translated',
            'format': 'srt',
            'custom_filename': 'english-result',
        }, secure=True, HTTP_HOST='mail.cenship.xyz')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Hello world.', response.content.decode('utf-8-sig'))
        self.assertIn('english-result.srt', response['Content-Disposition'])
        translate.assert_called_once()
        self.assertIn('你好，世界。', translate.call_args.args[0])
