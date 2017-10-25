#!/usr/bin/env python

import argparse
import socket
import subprocess

from datetime import datetime
import jsonpickle
import serial
import time

import paho.mqtt.client as mqtt
import signal

import struct

from d7a.alp.command import Command
from d7a.alp.operations.responses import ReturnFileData
from d7a.system_files.system_file_ids import SystemFileIds
from d7a.system_files.system_files import SystemFiles
from modem.modem import Modem


class BackendExample:
  def __init__(self):
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-v", "--verbose", help="verbose", default=False, action="store_true")
    argparser.add_argument("-b", "--broker", help="mqtt broker hostname",
                           default="localhost")
    self.mq = None
    self.connected_to_mqtt = False

    self.config = argparser.parse_args()
    self.connect_to_mqtt()

  def connect_to_mqtt(self):
    self.connected_to_mqtt = False

    self.mq = mqtt.Client("", True, None, mqtt.MQTTv31)
    self.mq.on_connect = self.on_mqtt_connect
    self.mq.on_message = self.on_mqtt_message
    self.mq.connect(self.config.broker, 1883, 60)
    self.mq.loop_start()
    while not self.connected_to_mqtt: pass  # busy wait until connected
    print("Connected to MQTT broker on {}".format(
      self.config.broker,
    ))

  def on_mqtt_connect(self, client, config, flags, rc):
    self.mq.subscribe("/tb")
    self.connected_to_mqtt = True

  def on_mqtt_message(self, client, config, msg):
    # msg contains already parsed command in ALP in JSON
    print("ALP Command received from TB: {}".format(msg.payload))
    try:
      obj = jsonpickle.json.loads(msg.payload)
    except:
      print("Payload not valid JSON, skipping") # TODO issue with TB rule filter, to be fixed
      return

    gateway = obj["deviceId"]
    cmd = jsonpickle.decode(jsonpickle.json.dumps(obj["alp"]))
    node_id = gateway  # overwritten below with remote node ID when received over D7 interface
    # get remote node id (when this is received over D7 interface)
    if cmd.interface_status != None and cmd.interface_status.operand.interface_id == 0xd7:
      node_id = '{:x}'.format(cmd.interface_status.operand.interface_status.addressee.id)

    # look for returned file data which we can parse, in this example file 64
    for action in cmd.actions:
      if type(action.operation) is ReturnFileData and action.operand.offset.id == 64:
        value = struct.unpack("L", bytearray(action.operand.data))[0] # parse binary payload (adapt to your needs)
        print("node {} sensor value {}".format(node_id, value))


  def __del__(self):
    try:
      self.mq.loop_stop()
      self.mq.disconnect()
    except:
      pass

  def run(self):
    print("Started")
    keep_running = True
    while keep_running:
      try:
        signal.pause()
      except KeyboardInterrupt:
        print("received KeyboardInterrupt... stopping processing")
        keep_running = False


if __name__ == "__main__":
  BackendExample().run()
