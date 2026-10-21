"""Constants for the AVA Flows Controller (Unofficial) integration."""
from datetime import timedelta

DOMAIN = "ava_flows_controller"

DEFAULT_PORT = 3000
# The Brain reports its serial number (its permanent ID) on this port.
DEVICEINFO_PORT = 3003
# Internal project id used by the AVA OS API (not the display name).
PROJECT = "home"
ZEROCONF_TYPE = "_ava._tcp.local."

SCAN_INTERVAL = timedelta(minutes=5)
# While the Brain can't be reached, check (and look for it) this often.
RETRY_INTERVAL = timedelta(minutes=1)
# Search the Brain's subnet at most this often.
SUBNET_SCAN_INTERVAL = timedelta(minutes=5)
# Show a Repair in Home Assistant after the Brain has been missing this long.
REPAIR_AFTER = timedelta(minutes=10)
REQUEST_TIMEOUT = 10
PROBE_TIMEOUT = 1.5

CONF_BRAIN_TYPE = "brain_type"
CONF_OS_VERSION = "os_version"
CONF_FIRMWARE = "firmware"
CONF_SERIAL = "serial"

# Options
CONF_FLOWS = "flows"              # recipe keys the user chose as buttons
CONF_KNOWN_FLOWS = "known_flows"  # every recipe key that existed when options were saved
CONF_ADD_NEW = "add_new_flows"    # automatically add flows created later in AVA OS
CONF_UNCHECKED = "unchecked_flows"  # recipe keys the user turned off
CONF_INCLUDE_HIDDEN = "include_hidden"
CONF_INCLUDE_DISABLED = "include_disabled"
CONF_CLEAN_NAMES = "clean_poweroff_names"  # rename AVA's "Name (2) (2)" power-off flows
CONF_SIDEBAR = "show_sidebar_panel"  # show the AVA Flows page in the sidebar

# Services
SERVICE_RENAME = "rename_flow"
SERVICE_EXPORT = "export_flows"
ATTR_NAME = "name"
ATTR_BRAIN = "brain"
ATTR_SAVE_FILE = "save_file"

# Dashboard card, served by the integration itself
CARD_URL = "/ava_flows_controller/ava-flows-card.js"

# Sidebar page
PANEL_URL_PATH = "ava-flows"
PANEL_TITLE = "AVA Flows"
PANEL_ICON = "mdi:play-circle-outline"
