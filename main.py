#!/usr/bin/env python3
import typing as tp
import robonomicsinterface as RI
import yaml
import hashlib
import logging
import sys
import os
import threading
import ast

from utils.coefficients import coefficients


logger = logging.getLogger(__name__)
logger.propagate = False
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

TWIN_ID = 2
COEFFICIENT = 1  # default coefficient if no geo set


class FootprintService:
    def __init__(self) -> None:
        with open(
            f"{os.path.realpath(__file__)[:-len(__file__)]}config/config.yaml"
        ) as f:
            self.config = yaml.safe_load(f)
        self.interface = RI.RobonomicsInterface(
            self.config["robonomics"]["robonomics_seed"]
        )
        threading.Thread(target=self.launch_listener, name="LaunchListener").start()

    def on_launch(self, data: tp.Tuple[str, str, bool]) -> None:
        """
        Add account to the existing Digital Tween
        """
        device_address = data[0]
        twins_list = self.get_twins_list()
        if twins_list is None:
            twins_list = []
        topic_num = len(twins_list)
        for topic in twins_list:
            if topic[1] == device_address:
                logger.info(f"Topic with address {device_address} is exists")
                break
        else:
            name = hashlib.sha256(bytes(topic_num)).hexdigest()
            params = {"id": TWIN_ID, "topic": f"0x{name}", "source": device_address}
            hash = self.interface.custom_extrinsic("DigitalTwin", "set_source", params)
            logger.info(f"Created topic with extrinsic hash: {hash}")

    def launch_listener(self) -> None:
        interface = RI.RobonomicsInterface(self.config["robonomics"]["robonomics_seed"])
        subscriber = RI.Subscriber(
            interface, RI.SubEvent.NewLaunch, self.on_launch, interface.define_address()
        )

    def get_twins_list(self) -> tp.List[tp.Tuple[str, str]]:
        """
        Get list of devices in Digital Twin.
        @return: List of tuples with topic and device address
        """
        twin = self.interface.custom_chainstate("DigitalTwin", "DigitalTwin", TWIN_ID)
        twins_list = twin.value
        return twins_list

    def get_last_data(self) -> None:
        threading.Timer(
            self.config["service"]["service_interval"], self.get_last_data
        ).start()
        twins_list = self.get_twins_list()
        last_devices_data = []
        if twins_list is not None:
            for device in twins_list:
                address = device[1]
                data = self.interface.fetch_datalog(address)
                last_devices_data.append(data)
        logger.info(last_devices_data)
        used_power = self.data_parser(last_devices_data)

    def data_parser(self, data) -> float:
        power_usage = 0
        for device in data:
            device_info = ast.literal_eval(device[1])
            if device_info["geo"] not in coefficients:
                power_usage += float(device_info["power_usage"]) * COEFFICIENT
        logger.info(power_usage)
        return power_usage


if __name__ == "__main__":
    m = FootprintService()
    threading.Thread(target=m.get_last_data).start()
