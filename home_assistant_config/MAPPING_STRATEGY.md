# MAPPING STRATEGY: CONNECTING YOUR HOME TO REHOBOAM
#
# This document explains how to map your new "Zone" packages to the LED panel.
#
# CONCEPT
# -------
# Instead of mapping every single light bulb to an LED (which would require hundreds of LEDs),
# we map "Aggregated Status" or "Critical Services" to the 16 available LEDs.
#
# AVAILABLE LEDS: 16 (Indices 0-15)
# LAYOUT:
#   - Top Row (R1-R8 / 0-7): Critical Infrastructure (Network, Servers, NAS)
#   - Bottom Row (S1-S8 / 8-15): "Services" & "Zones"
#
# PROPOSED MAPPING PLAN
# ---------------------
#
# [TOP ROW - INFRASTRUCTURE]
# LED 0:  Ethernet In (Uplink)
# LED 1:  Rehoboam (System Health)
# LED 2:  Pi-hole (DNS Blocking Activity)
# LED 3:  Pi-Drive (NAS Storage Health)
# LED 4:  Mac Mini (Server Health)
# LED 5:  Network Switch 1
# LED 6:  Router / Eero
# LED 7:  Network Switch 2
#
# [BOTTOM ROW - ZONES & UTILITIES]
# LED 8:  Exterior (Health = All doors locked? / Activity = Motion detected)
# LED 9:  First Floor (Health = Climate OK? / Activity = Lights changing)
# LED 10: Second Floor (Health = Climate OK? / Activity = Lights changing)
# LED 11: Basement (Health = No Leaks? / Activity = Motion/Utility usage)
# LED 12: Studios (Health = Sonal & Griffin Studios OK)
# LED 13: Municipal (Health = Garbage Pickup Today? / Activity = Snow Plows Active)
# LED 14: Water (Health = Leak Check / Activity = Flow Rate)
# LED 15: Energy/Other (Future use)
#
# HOW TO CONFIGURE THIS
# ---------------------
# In 'packages/rehoboam/rack_config.yaml', you simply map the LED to the
# group sensor you created in your zone package.
#
# EXAMPLE: MAPPING LED 8 TO EXTERIOR
#
# input_text:
#   led8_name: "Exterior"
#   led8_ha_availability_entity: "binary_sensor.all_exterior_doors_locked"  <-- Green if locked
#   led8_event_entities: "binary_sensor.exterior_occupancy"                 <-- Pulse if motion
#
# NEXT STEPS FOR YOU
# ------------------
# 1. Open the 'packages/zones/*.yaml' files.
# 2. Uncomment the 'entities' sections and fill in your actual entity IDs
#    (e.g., light.porch, binary_sensor.back_door).
# 3. Create a "Group" or "Template Sensor" that represents the Summary of that zone.
# 4. Update 'packages/rehoboam/rack_config.yaml' to point to those summaries.
