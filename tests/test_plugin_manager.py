from unittest import IsolatedAsyncioTestCase
import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
import logging

# Import the PluginManager and extract_package_files
from models import DAO
from package_downloader import download_package, extract_package_files
from plugin_manager import PluginManager


logger = logging.getLogger(__name__)


class TestPluginManager(IsolatedAsyncioTestCase):
    def setUp(self):

        self.db_url = "sqlite+aiosqlite:///:memory:"

        engine = create_async_engine(self.db_url, echo=False)

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        self.pm = PluginManager(
            DAO(session_factory),
            module_paths=["tests.plugins"],
            plugin_path="plugins",
        )

    @patch("package_downloader.subprocess.run")
    @patch("package_downloader.extract_package_files")
    def test_download_package_success(self, mock_extract, mock_run):
        mock_run.return_value.returncode = 0
        mock_extract.return_value = True

        result = download_package(logger, self.pm.plugin_path, "example", "1.2.3")
        self.assertTrue(result)
        mock_run.assert_called_once()
        mock_extract.assert_called_once()

    @patch("package_downloader.subprocess.run")
    @patch("package_downloader.extract_package_files")
    def test_download_package_fail(self, mock_extract, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error"
        mock_extract.return_value = False

        result = download_package(logger, self.pm.plugin_path, "example", "1.2.3")
        self.assertFalse(result)
        mock_extract.assert_not_called()

    def test_get_job_scheduler_id(self):
        job_id = 123
        expected = f"job-scheduler.job.{job_id}"
        self.assertEqual(PluginManager.get_job_scheduler_id(job_id), expected)

    @patch("plugin_manager.importlib.import_module")
    def test_load_plugin_success(self, mock_import_module):
        class DummyPlugin:
            pass

        module_mock = MagicMock()
        module_mock.DummyPlugin = DummyPlugin
        module_mock.__file__ = "/tmp/dummy_plugin.py"
        mock_import_module.return_value = module_mock

        package = "some.module.DummyPlugin"
        plugin = self.pm.load_plugin(package, override=False)
        self.assertEqual(plugin, DummyPlugin)

    @patch("plugin_manager.importlib.import_module", side_effect=ImportError("fail"))
    def test_load_plugin_fail(self, mock_import_module):
        package = "bad.module.Plugin"
        with self.assertRaises(RuntimeError):
            self.pm.load_plugin(package, override=False)

    @patch("plugin_manager.PluginManager.get_plugin_instance")
    async def test_run_plugin_job_success(self, mock_get_plugin):
        class DummyPlugin:
            def config(self, ctx, json):
                self.config_obj = json
                return json

            def env(self):
                return {}

            async def run(self, ctx, config, logger, render_fn):
                return "success"

        dummy_plugin = DummyPlugin()
        mock_get_plugin.return_value = dummy_plugin

        result = await self.pm.run_plugin_job("some.plugin", 1)
        self.assertEqual(result, "success")

    @patch("plugin_manager.PluginManager.get_plugin_instance", return_value=None)
    async def test_run_plugin_job_no_plugin(self, mock_get_plugin):
        result = await self.pm.run_plugin_job("no.plugin", 1)
        self.assertIsNone(result)

    def test_get_plugin_names(self):
        # register dummy plugins for test
        pm = self.pm
        pm.manager.register(object(), "pkg1")
        pm.manager.register(object(), "pkg2")
        names = self.pm.get_plugin_names()
        self.assertIn("pkg1", names)
        self.assertIn("pkg2", names)

    def test_unload_plugin(self):
        pm = self.pm
        dummy_plugin = object()
        pm.manager.register(dummy_plugin, "pkg1")
        self.assertIn("pkg1", self.pm.get_plugin_names())
        self.pm.unload_plugin("pkg1")
        self.assertNotIn("pkg1", self.pm.get_plugin_names())

    # Add more tests for add_job_instance, reload_all_jobs, activate_job, deactivate_job, etc.
    # These require more setup with database mocking or actual test DB.


if __name__ == "__main__":
    unittest.main()
