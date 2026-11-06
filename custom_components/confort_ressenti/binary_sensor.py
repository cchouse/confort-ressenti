from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import PieceEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    for sub_id, rt in entry.runtime_data.items():
        async_add_entities([ChauffageEnService(rt)], config_subentry_id=sub_id)


class ChauffageEnService(PieceEntity, BinarySensorEntity):
    """Le circuit de chauffage est-il en service ? (eau au-dessus du seuil haut, avec hystérésis)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, rt) -> None:
        super().__init__(rt, "chauffage")

    @property
    def available(self) -> bool:
        return self.rt.chauffage is not None

    @property
    def is_on(self) -> bool | None:
        return self.rt.chauffage

    @property
    def extra_state_attributes(self):
        return {"eau": self.rt.eau}
