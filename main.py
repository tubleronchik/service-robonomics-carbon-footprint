#!/usr/bin/env python3
from cmath import log
from random import seed
import typing as tp
import robonomicsinterface as RI
import yaml
import hashlib
import logging
import sys
import os
import threading
import ast
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
import time

from utils.coefficients import coefficients


logger = logging.getLogger(__name__)
logger.propagate = False
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

TWIN_ID = 5
COEFFICIENT = 0.475  # default coefficient if no geo set


class FootprintService:
    def __init__(self) -> None:
        with open("./config/config.yaml") as f:
            self.config = yaml.safe_load(f)
        self.interface = RI.RobonomicsInterface(self.config["robonomics"]["seed"])
        self.statemine_keypair = Keypair.create_from_mnemonic(
            self.config["statemine"]["seed"],
            ss58_format=self.config["statemine"]["ss58_format"],
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
        interface = RI.RobonomicsInterface(self.config["robonomics"]["seed"])
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

    def data_parser(self, data: tp.List[tp.Tuple[int, str]]) -> float:
        power_usage = 0
        for device in data:
            device_info = ast.literal_eval(device[1])
            if device_info["geo"] not in coefficients:
                power_usage += float(device_info["power_usage"]) * COEFFICIENT
            else:
                power_usage += (
                    float(device_info["power_usage"]) * coefficients[device_info["geo"]]
                )
        co2_tons = self.convert_to_CO2tons(power_usage)
        return co2_tons

    def convert_to_CO2tons(self, power: float) -> float:
        co2_tons = power / (10 ** 6)
        return co2_tons

    def calculating_burning_tons(self, co2_tons: float) -> None:
        total_burned = self.synchronize_burned()
        not_burned = co2_tons - total_burned
        logger.info(f"Total not burned: {not_burned} tons")
        tons = int(not_burned)
        if tons > 0:
            with open("./config/burned", "w") as f:
                f.write(f"{time.time()}: {total_burned + tons}")
            if self.burning_tokens(tons):
                logger.info(
                    f"Recording total burned tons to datalog.. Total CO2 tons: {total_burned + tons}."
                )
                self.interface.record_datalog(f"burned: {total_burned + tons}")

    def synchronize_burned(self) -> int:
        try:
            with open("./config/burned") as f:
                burned_real = f.readline().split(": ")[1]
        except FileNotFoundError:
            burned_real = 0
        last_datalog = self.interface.fetch_datalog(self.interface.define_address())
        if last_datalog is not None:
            last_datalog = last_datalog[1]
            if last_datalog.startswith("burned"):
                burned_recorded = int(last_datalog.split(": ")[1])
        else:
            burned_recorded = 0
        return max(int(burned_real), burned_recorded)

    def statemine_connect(self) -> SubstrateInterface:
        interface = SubstrateInterface(
            url=self.config["statemine"]["endpoint"],
            ss58_format=self.config["statemine"]["ss58_format"],
            type_registry_preset="substrate-node-template",
            type_registry={
                "types": {
                    "Record": "Vec<u8>",
                    "Parameter": "Bool",
                    "<T as frame_system::Config>::AccountId": "AccountId",
                    "RingBufferItem": {
                        "type": "struct",
                        "type_mapping": [
                            ["timestamp", "Compact<u64>"],
                            ["payload", "Vec<u8>"],
                        ],
                    },
                    "RingBufferIndex": {
                        "type": "struct",
                        "type_mapping": [
                            ["start", "Compact<u64>"],
                            ["end", "Compact<u64>"],
                        ],
                    },
                }
            },
        )
        return interface

    def burn_call(self, substrate: SubstrateInterface, co2_tonns: float) -> tp.Any:
        call = substrate.compose_call(
            call_module="Assets",
            call_function="burn",
            call_params={
                "id": self.config["statemine"]["token_id"],
                "who": {"Id": self.statemine_keypair.ss58_address},
                "amount": str(co2_tonns),
            },
        )

        return call

    def burning_tokens(self, co2_tonns: int) -> None:
        substrate = self.statemine_connect()
        extrinsic = substrate.create_signed_extrinsic(
            call=self.burn_call(substrate, co2_tonns), keypair=self.statemine_keypair
        )
        try:
            receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            logger.info(
                f"{co2_tonns} tokens was successfully burned in block {receipt.block_hash}"
            )
            return True
        except SubstrateRequestException as e:
            logger.warning(
                f"Something went wrong during extrinsic submission to Statemine: {e}"
            )
            return False

    def get_last_data(self) -> None:
        threading.Timer(self.config["service"]["interval"], self.get_last_data).start()
        twins_list = self.get_twins_list()
        last_devices_data = []
        if twins_list is not None:
            for device in twins_list:
                address = device[1]
                data = self.interface.fetch_datalog(address)
                if data is not None:
                    last_devices_data.append(data)
        logger.info(f"Last data from all devices: {last_devices_data}")
        co2_tons = self.data_parser(last_devices_data)
        self.calculating_burning_tons(co2_tons)


if __name__ == "__main__":
    m = FootprintService()
    threading.Thread(target=m.get_last_data).start()
    
