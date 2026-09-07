"""Sensor platform for Hiconics inverter and battery."""
# ... Keep your existing imports and helper functions ...

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hiconics sensors from entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    known_keys = set()

    def _create_entities():
        new_entities = []

        # 1. Standard polling telemetry
        data = coordinator.data or {}
        data_list = data.get("dataList", [])

        for item in data_list:
            key = item.get("key")
            if not key or key in known_keys:
                continue
            known_keys.add(key)
            new_entities.append(HiconicsSensor(coordinator, entry, item))

        # 2. Pre-create TOU Settings (C40 to C75) so they exist immediately
        tou_keys = [f"C{i}" for i in range(40, 76)]
        for key in tou_keys:
            if key not in known_keys:
                known_keys.add(key)
                new_entities.append(HiconicsExtraSensor(coordinator, entry, key))

        # 3. Any other on-demand extra data
        extra_data = getattr(coordinator, "extra_data", {})
        for key in extra_data:
            if not key or key in known_keys:
                known_keys.add(key)
                new_entities.append(HiconicsExtraSensor(coordinator, entry, key))

        if new_entities:
            async_add_entities(new_entities)

    _create_entities()
    entry.async_on_unload(coordinator.async_add_listener(_create_entities))

# ... Keep the rest of your HiconicsSensor and HiconicsExtraSensor class logic ...
