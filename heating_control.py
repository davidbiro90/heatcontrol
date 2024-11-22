import time
import requests
import logging

# Beállítások
HASS_URL = "http://supervisor/core/api"
HASS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1Yzc5ZGY1NzZhMmY0MjVlYWEwMThkZjEzZGNmYmZiZiIsImlhdCI6MTczMjMwODk2OCwiZXhwIjoyMDQ3NjY4OTY4fQ.b3GZBZeYMGUfH229G5RucTnSrLJYMV2ruYAbLkeqkus"  # Hozz létre egy tokent a Home Assistant-ban!

# Naplózás beállítása
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HeatingControl")

class HeatingControl:
    def __init__(self, heater_entity, inside_temp_sensor, outside_temp_sensor, update_interval=130):
        self.heater_entity = heater_entity
        self.inside_temp_sensor = inside_temp_sensor
        self.outside_temp_sensor = outside_temp_sensor
        self.update_interval = update_interval
        self.hysteresis_offset = 0.5  # 0.5°C puffertartomány

    def get_state(self, entity):
        """Lekéri egy entitás állapotát a Home Assistant API-n keresztül."""
        url = f"{HASS_URL}/states/{entity}"
        headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            state = response.json().get("state")
            logger.debug(f"Entitás állapot lekérve: {entity} -> {state}")
            return state
        else:
            logger.error(f"Hiba a(z) {entity} állapotának lekérésekor: {response.status_code}")
            return None

    def set_state(self, entity, action):
        """Egy entitás állapotának módosítása (be- vagy kikapcsolás)."""
        url = f"{HASS_URL}/services/homeassistant/{action}"
        headers = {"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
        data = {"entity_id": entity}
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            logger.info(f"{entity} sikeresen {action}.")
        else:
            logger.error(f"Hiba a(z) {entity} {action} műveletekor: {response.status_code}")

    def calculate_target_temperature(self):
        """Kiszámítja a célhőmérsékletet a külső hőmérséklet alapján."""
        base_temp = 22.0
        outside_temp = float(self.get_state(self.outside_temp_sensor) or 0)
        temp_adjustment = (0.0 - outside_temp) * 0.1
        new_target_temp = max(20.0, min(23.0, base_temp + temp_adjustment))
        logger.info(f"Külső hőmérséklet: {outside_temp}°C, Alap célhőmérséklet: {base_temp}°C, Számított célhőmérséklet: {new_target_temp}°C")
        return new_target_temp

    def calculate_score(self):
        """Kiszámítja a pontszámot a belső és külső hőmérséklet alapján."""
        inside_temp = float(self.get_state(self.inside_temp_sensor) or 21.0)
        outside_temp = float(self.get_state(self.outside_temp_sensor) or 5.0)
        inside_score = self.interpolate_score(inside_temp, [18, 19, 20, 21, 22, 23], [7, 5, 3, 1, 0, -5])
        outside_score = self.interpolate_score(outside_temp, [0, 5, 10, 15], [7, 5, 3, 1, -3])
        score = inside_score * 0.6 + outside_score * 0.4
        logger.info(f"Pontszám: {score} (Belső: {inside_temp}°C, Külső: {outside_temp}°C, Belső pontszám: {inside_score}, Külső pontszám: {outside_score})")
        return score

    def interpolate_score(self, temp, thresholds, scores):
        """Lineáris interpolációval pontszámot számít a hőmérséklet alapján."""
        for i in range(len(thresholds) - 1):
            if thresholds[i] <= temp < thresholds[i + 1]:
                slope = (scores[i + 1] - scores[i]) / (thresholds[i + 1] - thresholds[i])
                return scores[i] + slope * (temp - thresholds[i])
        return scores[0] if temp < thresholds[0] else scores[-1]

    def adjust_target_temperature(self, target_temp, score):
        """A pontszám alapján finomhangolja a célhőmérsékletet."""
        adjustment = 0
        if score > 7:
            adjustment = 0.5
        elif 3 < score <= 7:
            adjustment = 0.3
        elif 0 < score <= 3:
            adjustment = 0.1
        elif -3 <= score <= 0:
            adjustment = -0.1
        elif -7 <= score < -3:
            adjustment = -0.3
        elif score < -7:
            adjustment = -0.5

        adjusted_target_temp = max(20.0, min(23.0, target_temp + adjustment))
        logger.info(f"Pontszám alapján módosított célhőmérséklet: {adjusted_target_temp}°C (Eredeti: {target_temp}°C, Módosítás: {adjustment}°C)")
        return adjusted_target_temp

    def control_heating(self):
        """A fűtési logika vezérlése."""
        while True:
            target_temp = self.calculate_target_temperature()
            score = self.calculate_score()
            adjusted_target_temp = self.adjust_target_temperature(target_temp, score)
            inside_temp = float(self.get_state(self.inside_temp_sensor) or 21.0)

            # Fűtés vezérlése
            if inside_temp < adjusted_target_temp - self.hysteresis_offset:
                self.set_state(self.heater_entity, "turn_on")
                logger.info(f"Fűtés bekapcsolva! Belső hőmérséklet: {inside_temp}°C, Célhőmérséklet: {adjusted_target_temp}°C, Pontszám: {score}")
            elif inside_temp >= adjusted_target_temp:
                self.set_state(self.heater_entity, "turn_off")
                logger.info(f"Fűtés kikapcsolva! Belső hőmérséklet: {inside_temp}°C, Célhőmérséklet: {adjusted_target_temp}°C, Pontszám: {score}")

            time.sleep(self.update_interval)

if __name__ == "__main__":
    hc = HeatingControl(
        heater_entity="switch.futesvezerlorele_kazan_rele",
        inside_temp_sensor="sensor.konyhamozgas_bme680_konyha_temperature",
        outside_temp_sensor="sensor.wh2650a_indoor_temperature",
        update_interval=130
    )
    logger.info("Heating Control elindult.")
    hc.control_heating()