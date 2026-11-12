"""Test the Foscam camera platform."""

from unittest.mock import patch

from homeassistant.components.foscam.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_mock_foscam_camera
from .const import ENTRY_ID, VALID_CONFIG

from tests.common import MockConfigEntry


async def test_stop_ptz(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test stopping PTZ movement calls the camera session."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)
        mock_foscam_camera.ptz_stop_run.return_value = (0, {})
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        camera_entity_id = entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, ENTRY_ID
        )
        assert camera_entity_id is not None

        await hass.services.async_call(
            DOMAIN,
            "stop_ptz",
            {ATTR_ENTITY_ID: camera_entity_id},
            blocking=True,
        )

        mock_foscam_camera.ptz_stop_run.assert_called_once_with()
