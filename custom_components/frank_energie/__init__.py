# pylint: disable=import-error
"""The Frank Energie component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from python_frank_energie import FrankEnergie
from python_frank_energie.exceptions import AuthException, RequestException

from .const import CONF_COORDINATOR, DOMAIN
from .coordinator import FrankEnergieCoordinator

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Frank Energie component from a config entry."""

    # For backwards compatibility, set unique ID
    if entry.unique_id is None or entry.unique_id == "frank_energie_component":
        hass.config_entries.async_update_entry(entry, unique_id=str("frank_energie"))

    # Select site-reference, or find first one that has status 'IN_DELIVERY' if not set
    if (
        entry.data.get("site_reference") is None
        and entry.data.get(CONF_ACCESS_TOKEN) is not None
    ):
        api = FrankEnergie(
            clientsession=async_get_clientsession(hass),
            auth_token=entry.data.get(CONF_ACCESS_TOKEN, None),
            refresh_token=entry.data.get(CONF_TOKEN, None),
        )
        try:
            me = await api.me()
        except Exception as ex:
            # Log the specific error for debugging
            _LOGGER.error(
                "Failed to retrieve user information from Frank Energie API: %s", ex
            )
            _LOGGER.debug("Error details:", exc_info=True)

            # If this is an authentication error, trigger a reauth flow
            if isinstance(ex, (AuthException, RequestException)):
                if (
                    "validation error" in str(ex).lower()
                    or "unauthorized" in str(ex).lower()
                ):
                    _LOGGER.warning(
                        "Authentication appears to be invalid, please reconfigure the integration"
                    )
                    # Don't raise the error here, let the coordinator handle it during first refresh
                    return False

            # For other errors, still fail setup but with a more informative message
            raise ConnectionError(
                f"Unable to connect to Frank Energie API: {ex}"
            ) from ex

        # The newer version of the library has changed the Me object structure
        # For now, we'll log the successful authentication and continue without site-specific setup
        # The coordinator can still fetch public prices even without a site reference
        _LOGGER.info("Successfully authenticated with Frank Energie API")
        _LOGGER.debug(
            "User info retrieved: %s",
            me.email if hasattr(me, "email") else "Unknown user",
        )

        # Continue with setup - the coordinator will handle fetching prices
        # If user prices aren't available, it will fall back to public prices

    # Initialise the coordinator and save it as domain-data
    api = FrankEnergie(
        clientsession=async_get_clientsession(hass),
        auth_token=entry.data.get(CONF_ACCESS_TOKEN, None),
        refresh_token=entry.data.get(CONF_TOKEN, None),
    )
    frank_coordinator = FrankEnergieCoordinator(hass, entry, api)

    # Fetch initial data, so we have data when entities subscribe and set up the platform
    await frank_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_COORDINATOR: frank_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
