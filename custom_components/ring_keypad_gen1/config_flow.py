"""Config and options flow for Ring Keypad (1st Gen)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ALARM_ENTITY,
    CONF_KEYPAD_DEVICE,
    DEFAULT_OPTIONS,
    DOMAIN,
    INDICATOR_MAX,
    OPT_CODE_TIMEOUT,
    OPT_IND_ARMED_AWAY,
    OPT_IND_ARMED_HOME,
    OPT_IND_ARMING,
    OPT_IND_DISARMED,
    OPT_IND_PENDING,
    OPT_SILENT_STATUS,
    OPT_TRIGGERED_SOUND,
    TRIGGERED_SOUND_OPTIONS,
)


class RingKeypadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick the keypad and the alarm panel it controls."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_KEYPAD_DEVICE])
            self._abort_if_unique_id_configured()
            device = dr.async_get(self.hass).async_get(user_input[CONF_KEYPAD_DEVICE])
            if device is None:
                errors[CONF_KEYPAD_DEVICE] = "device_not_found"
            else:
                title = device.name_by_user or device.name or "Ring Keypad"
                return self.async_create_entry(
                    title=title, data=user_input, options=dict(DEFAULT_OPTIONS)
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_KEYPAD_DEVICE): DeviceSelector(
                    DeviceSelectorConfig(
                        filter=[{"integration": "zwave_js", "manufacturer": "Ring"}]
                    )
                ),
                vol.Required(CONF_ALARM_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="alarm_control_panel")
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return RingKeypadOptionsFlow()


def _ind() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=-1, max=INDICATOR_MAX, step=1, mode=NumberSelectorMode.BOX
        )
    )


class RingKeypadOptionsFlow(OptionsFlow):
    """Sound and indicator options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Number selectors return floats; store whole numbers.
            cleaned = {
                k: (int(v) if isinstance(v, float) else v)
                for k, v in user_input.items()
            }
            return self.async_create_entry(data=cleaned)

        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    OPT_SILENT_STATUS, default=current[OPT_SILENT_STATUS]
                ): BooleanSelector(),
                vol.Required(
                    OPT_TRIGGERED_SOUND, default=str(current[OPT_TRIGGERED_SOUND])
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=TRIGGERED_SOUND_OPTIONS,
                        translation_key="triggered_sound",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    OPT_CODE_TIMEOUT, default=current[OPT_CODE_TIMEOUT]
                ): NumberSelector(
                    NumberSelectorConfig(min=2, max=30, step=1, unit_of_measurement="s")
                ),
                vol.Required(
                    OPT_IND_DISARMED, default=current[OPT_IND_DISARMED]
                ): _ind(),
                vol.Required(
                    OPT_IND_ARMED_HOME, default=current[OPT_IND_ARMED_HOME]
                ): _ind(),
                vol.Required(
                    OPT_IND_ARMED_AWAY, default=current[OPT_IND_ARMED_AWAY]
                ): _ind(),
                vol.Required(OPT_IND_ARMING, default=current[OPT_IND_ARMING]): _ind(),
                vol.Required(OPT_IND_PENDING, default=current[OPT_IND_PENDING]): _ind(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
