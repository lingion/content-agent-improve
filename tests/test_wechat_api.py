import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.publish.wechat_api import _append_footer_qr, _resolve_local_path, _upload_body_images

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
IMAGES_DIR = Path(__file__).resolve().parents[1] / "data" / "images"
QR_FILENAME = "wechat-footer-qr.png"


class WeChatBodyImageTests(unittest.TestCase):
    def test_resolves_loopback_and_relative_image_urls(self):
        image_dir = Path(__file__).resolve().parents[1] / "data" / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / "wechat-path-test.png"
        image_path.write_bytes(b"test")
        try:
            for url in (
                "http://127.0.0.1:8918/api/images/wechat-path-test.png",
                "http://localhost:8918/api/images/wechat-path-test.png",
                "/api/images/wechat-path-test.png",
            ):
                self.assertEqual(os.path.normcase(str(image_path)), os.path.normcase(_resolve_local_path(url)))
            self.assertIsNone(_resolve_local_path("https://example.com/api/images/wechat-path-test.png"))
        finally:
            image_path.unlink(missing_ok=True)

    @patch("agent.publish.wechat_api.upload_body_image_from_url")
    def test_upload_replaces_only_src_and_preserves_image_markup(self, upload):
        upload.return_value = "https://mmbiz.qpic.cn/example/0"
        html = (
            '<figure><img alt="具体效果" '
            'src="http://127.0.0.1:8918/api/images/example.png" '
            'style="max-width:100%;border-radius:6px;">'
            '<figcaption>具体效果说明</figcaption></figure>'
        )

        rewritten, count = _upload_body_images("token", html)

        self.assertEqual(1, count)
        self.assertIn('src="https://mmbiz.qpic.cn/example/0"', rewritten)
        self.assertIn('alt="具体效果"', rewritten)
        self.assertIn('style="max-width:100%;border-radius:6px;"', rewritten)
        self.assertIn("<figcaption>具体效果说明</figcaption>", rewritten)

    @patch("agent.publish.wechat_api.upload_body_image_from_url", side_effect=RuntimeError("upstream failed"))
    def test_upload_failure_stops_missing_image_draft(self, _upload):
        html = '<img src="http://127.0.0.1:8918/api/images/example.png">'
        with self.assertRaisesRegex(RuntimeError, "已停止创建缺图草稿"):
            _upload_body_images("token", html)


class FooterQrTests(unittest.TestCase):
    def setUp(self):
        self.qr_path = IMAGES_DIR / QR_FILENAME
        self.had_qr = self.qr_path.exists()
        if not self.had_qr:
            shutil.copy(FIXTURES_DIR / QR_FILENAME, self.qr_path)

    def tearDown(self):
        if not self.had_qr:
            self.qr_path.unlink(missing_ok=True)

    def test_footer_qr_appended_at_end_of_body(self):
        html = "<p>正文最后一段</p>"
        result = _append_footer_qr(html)
        # 不变量：二维码永远出现在正文末尾（追加，非前置）
        self.assertTrue(result.endswith("扫码关注，第一时间获取最新内容</p>"))
        self.assertTrue(result.startswith("<p>正文最后一段</p>"))
        self.assertIn('src="/api/images/wechat-footer-qr.png"', result)

    def test_footer_qr_missing_file_is_noop(self):
        qr_path = IMAGES_DIR / QR_FILENAME
        backup = IMAGES_DIR / (QR_FILENAME + ".bak")
        qr_path.rename(backup)
        try:
            result = _append_footer_qr("<p>正文</p>")
            self.assertEqual("<p>正文</p>", result)
        finally:
            backup.rename(qr_path)

    @patch("agent.publish.wechat_api.upload_body_image_from_url")
    def test_footer_qr_uploaded_with_body_images(self, upload):
        upload.return_value = "https://mmbiz.qpic.cn/example/qr"
        html = _append_footer_qr("<p>正文</p>")
        rewritten, count = _upload_body_images("token", html)
        # 二维码与正文图片走同一条上传链路，替换为微信素材地址
        self.assertEqual(1, count)
        self.assertIn('src="https://mmbiz.qpic.cn/example/qr"', rewritten)


if __name__ == "__main__":
    unittest.main()
