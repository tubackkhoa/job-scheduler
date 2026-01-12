import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import asyncio
import logging

# Import the PluginManager and extract_package_files
from plugin_manager import PluginManager, extract_package_files


class TestPluginManager(unittest.TestCase):
    def setUp(self):
        # Clear registered plugins before each test to avoid conflicts
        for name, plugin in list(PluginManager.manager.list_name_plugin()):
            PluginManager.manager.unregister(plugin, name)
        # Use an in-memory SQLite for tests
        self.db_url = "sqlite:///:memory:"
        self.pm = PluginManager(
            self.db_url, module_paths=["tests.plugins"], plugin_path="test_plugins"
        )

    @patch("plugin_manager.glob.glob")
    @patch("plugin_manager.zipfile.ZipFile")
    @patch("plugin_manager.tarfile.open")
    @patch("plugin_manager.shutil.rmtree")
    @patch("plugin_manager.shutil.move")
    @patch("plugin_manager.os.remove")
    @patch("plugin_manager.os.path.isdir")
    @patch("plugin_manager.os.listdir")
    @patch("plugin_manager.os.rmdir")
    def test_extract_package_files_zip(
        self,
        mock_rmdir,
        mock_listdir,
        mock_isdir,
        mock_remove,
        mock_move,
        mock_rmtree,
        mock_tar_open,
        mock_zipfile,
        mock_glob,
    ):

        # Setup mock returns
        test_dir = "/fake_dir"
        mock_glob.side_effect = [
            ["/fake_dir/fake.whl"],  # archives found
            [],  # no dist-info after extraction
            [],  # no flatten entries
        ]
        mock_isdir.return_value = False
        mock_listdir.return_value = []
        # Mock ZipFile context manager
        mock_zipfile.return_value.__enter__.return_value.extractall = MagicMock()

        result = extract_package_files(test_dir)
        self.assertTrue(result)
        mock_zipfile.return_value.__enter__.return_value.extractall.assert_called_once_with(
            test_dir
        )
        mock_remove.assert_called_once_with("/fake_dir/fake.whl")

    @patch("plugin_manager.subprocess.run")
    @patch("plugin_manager.extract_package_files")
    def test_download_package_success(self, mock_extract, mock_run):
        mock_run.return_value.returncode = 0
        mock_extract.return_value = True

        result = self.pm.download_package("example", "1.2.3")
        self.assertTrue(result)
        mock_run.assert_called_once()
        mock_extract.assert_called_once()

    @patch("plugin_manager.subprocess.run")
    @patch("plugin_manager.extract_package_files")
    def test_download_package_fail(self, mock_extract, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error"
        mock_extract.return_value = False

        result = self.pm.download_package("example", "1.2.3")
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
        mock_import_module.return_value = module_mock

        package = "some.module.DummyPlugin"
        plugin = PluginManager.load_plugin(package, override=False)
        self.assertEqual(plugin, DummyPlugin)

    @patch("plugin_manager.importlib.import_module", side_effect=ImportError("fail"))
    def test_load_plugin_fail(self, mock_import_module):
        package = "bad.module.Plugin"
        with self.assertRaises(RuntimeError):
            PluginManager.load_plugin(package, override=False)

    @patch("plugin_manager.PluginManager._active_job_cache", {1: '{"key":"value"}'})
    @patch("plugin_manager.PluginManager.get_plugin_instance")
    def test_run_plugin_job_success(self, mock_get_plugin):
        class DummyPlugin:
            def config(self, json):
                self.config_obj = json
                return json

            async def run(self, config, logger):
                return "success"

        dummy_plugin = DummyPlugin()
        mock_get_plugin.return_value = dummy_plugin

        result = PluginManager.run_plugin_job("some.plugin", 1)
        self.assertEqual(result, "success")

    @patch("plugin_manager.PluginManager.get_plugin_instance", return_value=None)
    def test_run_plugin_job_no_plugin(self, mock_get_plugin):
        result = PluginManager.run_plugin_job("no.plugin", 1)
        self.assertIsNone(result)

    def test_get_plugin_names(self):
        # register dummy plugins for test
        pm = self.pm
        pm.manager.register(object(), "pkg1")
        pm.manager.register(object(), "pkg2")
        names = PluginManager.get_plugin_names()
        self.assertIn("pkg1", names)
        self.assertIn("pkg2", names)

    def test_unload_plugin(self):
        pm = self.pm
        dummy_plugin = object()
        pm.manager.register(dummy_plugin, "pkg1")
        self.assertIn("pkg1", PluginManager.get_plugin_names())
        PluginManager.unload_plugin("pkg1")
        self.assertNotIn("pkg1", PluginManager.get_plugin_names())

    # Add more tests for add_job_instance, reload_all_jobs, activate_job, deactivate_job, etc.
    # These require more setup with database mocking or actual test DB.


if __name__ == "__main__":
    unittest.main()
