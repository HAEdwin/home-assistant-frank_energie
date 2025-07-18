# pylint: disable=import-error
"""Coordinator implementation for Frank Energie integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from python_frank_energie import FrankEnergie
from python_frank_energie.exceptions import (
    RequestException,
    AuthException,
    FrankEnergieException,
)
from python_frank_energie.models import PriceData, MonthSummary, Invoices, MarketPrices

from .const import DATA_ELECTRICITY, DATA_GAS, DATA_MONTH_SUMMARY, DATA_INVOICES

LOGGER = logging.getLogger(__name__)


class FrankEnergieData(TypedDict):
    """Data structure for Frank Energie coordinator data.

    Contains pricing data for electricity and gas, plus optional
    authenticated user data for month summary and invoices.
    """

    DATA_ELECTRICITY: PriceData
    DATA_GAS: PriceData
    DATA_MONTH_SUMMARY: MonthSummary | None
    DATA_INVOICES: Invoices | None


class FrankEnergieCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    api: FrankEnergie

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: FrankEnergie,
    ) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.entry = entry
        self.api = api
        self.site_reference = entry.data.get("site_reference", None)

        super().__init__(
            hass,
            LOGGER,
            name="Frank Energie coordinator",
            update_interval=timedelta(minutes=60),
        )

    async def _async_update_data(self) -> FrankEnergieData:
        """Get the latest data from Frank Energie."""
        LOGGER.debug("Fetching Frank Energie data")

        # We request data for today up until the day after tomorrow.
        # This is to ensure we always request all available data.
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)

        # Fetch data for today and tomorrow separately,
        # because the gas prices response only contains data for the first day of the query
        try:
            prices_today = await self.__fetch_prices_with_fallback(today, tomorrow)
            prices_tomorrow = await self.__fetch_prices_with_fallback(
                tomorrow, day_after_tomorrow
            )

            data_month_summary = None
            data_invoices = None

            # Only try to get authenticated data if we have a site reference
            if self.api.is_authenticated and self.site_reference:
                try:
                    data_month_summary = await self.api.month_summary(
                        self.site_reference
                    )
                    data_invoices = await self.api.invoices(self.site_reference)
                except (RequestException, FrankEnergieException) as ex:
                    LOGGER.warning(
                        "Failed to fetch month summary or invoices (%s), "
                        "continuing without this data",
                        ex,
                    )
            elif self.api.is_authenticated:
                LOGGER.info(
                    "No site reference available, skipping user-specific month summary and invoices"
                )
        except UpdateFailed as err:
            # Check if we still have data to work with, if so,
            # return this data. Still log the error as warning
            if (
                self.data
                and self.data[DATA_ELECTRICITY].get_future_prices()
                and self.data[DATA_GAS].get_future_prices()
            ):
                LOGGER.warning(str(err))
                return self.data
            # Re-raise the error if there's no data from future left
            raise err
        except (RequestException, FrankEnergieException) as ex:
            LOGGER.error("Request failed with error: %s", ex)

            # Check for specific GraphQL validation errors
            if "validation error" in str(ex).lower():
                LOGGER.error(
                    "GraphQL validation error - this may indicate an API change "
                    "or authentication issue"
                )
                # Trigger reauth if this looks like an authentication problem
                if self.api.is_authenticated:
                    LOGGER.info(
                        "Attempting to renew authentication tokens due to validation error"
                    )
                    try:
                        await self.__try_renew_token()
                        raise UpdateFailed(
                            "Authentication renewed, retry needed"
                        ) from ex
                    except AuthException:
                        # Token renewal failed, trigger reauth flow
                        raise ConfigEntryAuthFailed(
                            "Token renewal failed, reauth required"
                        ) from ex

            if str(ex).startswith("user-error:"):
                raise ConfigEntryAuthFailed from ex

            raise UpdateFailed(ex) from ex

        except AuthException as ex:
            LOGGER.debug("Authentication tokens expired, trying to renew them (%s)", ex)
            await self.__try_renew_token()
            # Tell we have no data, so update coordinator tries again with renewed tokens
            raise UpdateFailed(ex) from ex

        return {
            DATA_ELECTRICITY: prices_today.electricity + prices_tomorrow.electricity,
            DATA_GAS: prices_today.gas + prices_tomorrow.gas,
            DATA_MONTH_SUMMARY: data_month_summary,
            DATA_INVOICES: data_invoices,
        }

    async def __fetch_prices_with_fallback(
        self, start_date: date, end_date: date
    ) -> MarketPrices:
        if not self.api.is_authenticated:
            LOGGER.debug("API not authenticated, fetching public prices")
            return await self.api.prices(start_date, end_date)

        # Try to get user-specific prices first (only if we have a site reference)
        if self.site_reference:
            try:
                user_prices = await self.api.user_prices(
                    start_date, self.site_reference
                )

                if (
                    len(user_prices.gas.all) > 0
                    and len(user_prices.electricity.all) > 0
                ):
                    # If user_prices are available for both gas and electricity return them
                    LOGGER.debug("Successfully retrieved user-specific prices")
                    return user_prices
                else:
                    LOGGER.info(
                        "Incomplete user prices received, falling back to public prices"
                    )
                    public_prices = await self.api.prices(start_date, end_date)

                    # Use public prices if no user prices are available
                    if len(user_prices.gas.all) == 0:
                        LOGGER.info(
                            "No gas prices found for user, using public gas prices"
                        )
                        user_prices.gas = public_prices.gas

                    if len(user_prices.electricity.all) == 0:
                        LOGGER.info(
                            "No electricity prices found for user, using public electricity prices"
                        )
                        user_prices.electricity = public_prices.electricity

                    return user_prices

            except (RequestException, FrankEnergieException) as ex:
                LOGGER.warning(
                    "Failed to fetch user-specific prices (%s), falling back to public prices",
                    ex,
                )
                # If user prices fail (e.g., due to GraphQL validation errors), use public prices
                return await self.api.prices(start_date, end_date)

            except (AttributeError, ValueError, TypeError) as ex:
                LOGGER.error(
                    "Data parsing error fetching user prices (%s), falling back to public prices",
                    ex,
                )
                # For data parsing errors, try public prices as last resort
                return await self.api.prices(start_date, end_date)
        else:
            LOGGER.info("No site reference available, using public prices")
            return await self.api.prices(start_date, end_date)

    async def __try_renew_token(self):

        try:
            LOGGER.debug("Attempting to renew authentication token")
            updated_tokens = await self.api.renew_token()

            data = {
                CONF_ACCESS_TOKEN: updated_tokens.authToken,
                CONF_TOKEN: updated_tokens.refreshToken,
            }
            self.hass.config_entries.async_update_entry(self.entry, data=data)

            LOGGER.info("Successfully renewed authentication token")

        except (AuthException, RequestException, FrankEnergieException) as ex:
            LOGGER.error("Failed to renew token: %s. Starting user reauth flow", ex)
            raise ConfigEntryAuthFailed from ex
        except (AttributeError, ValueError, TypeError) as ex:
            LOGGER.error(
                "Data parsing error during token renewal: %s. Starting user reauth flow",
                ex,
            )
            raise ConfigEntryAuthFailed from ex
