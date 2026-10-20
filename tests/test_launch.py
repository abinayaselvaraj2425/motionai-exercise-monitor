"""Check useful startup failures without creating a server or opening a browser."""
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from backend import launch


class LaunchTests(unittest.TestCase):
    def test_old_and_other_installations_are_not_reused(self):
        self.assertEqual(launch.classify_server({'app':'motionai','version':'1.1.0'}),'outdated')
        self.assertEqual(launch.classify_server({'app':'motionai','api_version':2,'installation_id':'another-folder'}),'other-motionai')
        self.assertEqual(launch.classify_server({'app':'motionai','api_version':2,'installation_id':launch.installation_id()}),'motionai')

    def test_old_server_provides_restart_instructions(self):
        with patch.object(launch,'configure_local_runtime'),patch.object(launch,'preflight',return_value=None),patch.object(launch,'existing_server',return_value='outdated'),patch('sys.stderr',new=io.StringIO()) as output:
            self.assertEqual(launch.main([]),1)
            self.assertIn('Ctrl+C',output.getvalue())
            self.assertIn('START_APP.bat',output.getvalue())

    def test_installed_assets_pass_preflight(self):
        self.assertIsNone(launch.preflight())

    def test_missing_files_report_which_assets_to_restore(self):
        with patch.object(launch,'ROOT',launch.ROOT / 'tests' / 'missing-installation-fixture'):
            message=launch.preflight()
            self.assertIn('pose_landmarker_lite.task',message)
            self.assertIn('Extract the full release',message)

    def test_missing_dependencies_provide_install_action(self):
        with patch.object(launch.importlib.util,'find_spec',return_value=None):
            self.assertIn('Run INSTALL.bat',launch.preflight())

    def test_occupied_port_does_not_launch_second_server(self):
        with patch.object(launch,'configure_local_runtime'),patch.object(launch,'preflight',return_value=None),patch.object(launch,'existing_server',return_value='occupied'),patch('sys.stderr',new=io.StringIO()) as output:
            self.assertEqual(launch.main([]),1)
            self.assertIn('Port 3000 is in use',output.getvalue())

    def test_running_app_is_reused(self):
        with patch.object(launch,'configure_local_runtime'),patch.object(launch,'preflight',return_value=None),patch.object(launch,'existing_server',return_value='motionai'),patch('sys.stdout',new=io.StringIO()) as output:
            self.assertEqual(launch.main([]),0)
            self.assertIn('already running',output.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
