import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import os
import sys

# Ensure src is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.loginctl_api import list_seats, seat_status, get_current_assignments

class TestLoginctlAPI(unittest.TestCase):

    @patch('subprocess.run')
    def test_list_seats_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="seat0\nseat1\n",
            returncode=0
        )
        seats = list_seats()
        self.assertEqual(seats, ["seat0", "seat1"])
        mock_run.assert_called_once_with(
            ["loginctl", "list-seats", "--no-legend"],
            capture_output=True,
            text=True,
            check=True
        )

    @patch('subprocess.run')
    def test_list_seats_empty(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=0
        )
        seats = list_seats()
        self.assertEqual(seats, [])

    @patch('subprocess.run')
    def test_list_seats_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "loginctl")
        seats = list_seats()
        self.assertEqual(seats, [])

    @patch('subprocess.run')
    def test_seat_status_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="seat0\n  ├─/sys/devices/pci0000:00/0000:00:02.0/drm/card0\n  └─/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1/1-1:1.0/input/input0",
            returncode=0
        )
        status = seat_status("seat0")
        self.assertEqual(status["name"], "seat0")
        self.assertEqual(len(status["devices"]), 2)
        self.assertEqual(status["devices"][0]["syspath"], "/sys/devices/pci0000:00/0000:00:02.0/drm/card0")
        self.assertEqual(status["devices"][1]["syspath"], "/sys/devices/pci0000:00/0000:00:14.0/usb1/1-1/1-1:1.0/input/input0")

    @patch('subprocess.run')
    def test_seat_status_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "loginctl")
        status = seat_status("seat1")
        self.assertEqual(status, {"name": "seat1", "devices": []})

    @patch('src.core.loginctl_api.list_seats')
    @patch('src.core.loginctl_api.seat_status')
    @patch('os.path.exists')
    def test_get_current_assignments_empty_seats(self, mock_exists, mock_seat_status, mock_list_seats):
        # The core of the issue: list_seats returns []
        mock_list_seats.return_value = []
        mock_exists.return_value = False

        assignments = get_current_assignments()

        self.assertEqual(assignments, {})
        mock_seat_status.assert_not_called()

    @patch('src.core.loginctl_api.list_seats')
    @patch('src.core.loginctl_api.seat_status')
    @patch('os.path.exists')
    def test_get_current_assignments_only_seat0(self, mock_exists, mock_seat_status, mock_list_seats):
        mock_list_seats.return_value = ["seat0"]
        mock_exists.return_value = False

        assignments = get_current_assignments()

        self.assertEqual(assignments, {})
        mock_seat_status.assert_not_called()

    @patch('src.core.loginctl_api.list_seats')
    @patch('src.core.loginctl_api.seat_status')
    @patch('os.path.exists')
    def test_get_current_assignments_with_seat1(self, mock_exists, mock_seat_status, mock_list_seats):
        mock_list_seats.return_value = ["seat0", "seat1"]
        mock_seat_status.return_value = {
            "name": "seat1",
            "devices": [{"syspath": "/sys/devices/pci1"}]
        }
        mock_exists.return_value = False

        assignments = get_current_assignments()

        self.assertEqual(assignments, {"/sys/devices/pci1": "seat1"})
        mock_seat_status.assert_called_once_with("seat1")

    @patch('src.core.loginctl_api.list_seats')
    @patch('src.core.loginctl_api.seat_status')
    @patch('os.path.exists')
    def test_get_current_assignments_with_rules(self, mock_exists, mock_seat_status, mock_list_seats):
        mock_list_seats.return_value = ["seat0"]
        mock_exists.return_value = True

        rules_content = 'DEVPATH=="/devices/pci2", ENV{ID_SEAT}=="seat2"\n'

        with patch('builtins.open', mock_open(read_data=rules_content)):
            assignments = get_current_assignments()

        self.assertEqual(assignments, {"/sys/devices/pci2": "seat2"})

if __name__ == '__main__':
    unittest.main()
