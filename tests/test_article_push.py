"""push 层测试：用本地 bare repo 当 origin，不发网络请求。"""
import json
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import agent.publish.article_store as store


class PushTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name) / "work"
        self.workspace.mkdir()
        self.bare = Path(self._tmp.name) / "remote.git"

        def git(*args, cwd=None):
            subprocess.run(["git", *args], cwd=cwd or self.workspace,
                           capture_output=True, check=True)

        git("init", "--bare", str(self.bare))
        git("init")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("checkout", "-b", "main")
        (self.workspace / "README.md").write_text("x")
        git("add", ".")
        git("commit", "-m", "init")
        git("remote", "add", "origin", str(self.bare))
        git("push", "-u", "origin", "main")

        import os
        self._cwd = os.getcwd()
        os.chdir(self.workspace)
        self.addCleanup(os.chdir, self._cwd)
        env_patch = unittest.mock.patch.dict("os.environ", {"ARTICLE_REPO_TOKEN": ""}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def test_push_creates_commit_with_articles(self):
        store.build_article_dir("推送文", "wechat", "tech", "a", 8, "内容", "2026-08-30T09:00:00+08:00")
        result = store.push_to_articles("feat: add 推送文")
        self.assertTrue(result["ok"], result.get("error", ""))
        log = subprocess.run(["git", "log", "--oneline", "-2"], cwd=self.workspace,
                             capture_output=True, text=True).stdout
        self.assertIn("推送文", log)

    def test_push_no_changes_is_ok(self):
        result = store.push_to_articles()
        self.assertTrue(result["ok"])

    def test_failure_enqueues_message(self):
        store.build_article_dir("失败文", "wechat", "tech", "a", 8, "内容", "2026-08-30T09:00:00+08:00")
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        with unittest.mock.patch.object(store.subprocess, "run", return_value=failed):
            result = store.push_to_articles("feat: broken")
        self.assertFalse(result["ok"])
        queue = json.loads(store.PUSH_QUEUE_PATH.read_text(encoding="utf-8"))
        self.assertIn("feat: broken", queue)

    def test_retry_queue_drains(self):
        store.PUSH_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        store.PUSH_QUEUE_PATH.write_text(json.dumps(["feat: queued"]), encoding="utf-8")
        result = store.retry_push_queue()
        self.assertTrue(result["ok"])
        self.assertEqual(json.loads(store.PUSH_QUEUE_PATH.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
