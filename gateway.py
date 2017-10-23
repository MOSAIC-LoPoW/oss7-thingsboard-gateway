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

from d7a.alp.command import Command
from d7a.system_files.system_files import SystemFiles
from modem.modem import Modem


class Gateway:
  def __init__(self):
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--device", help="serial device /dev file modem",
                           default="/dev/ttyACM0")
    argparser.add_argument("-r", "--rate", help="baudrate for serial device", type=int, default=115200)
    argparser.add_argument("-v", "--verbose", help="verbose", default=False, action="store_true")
    argparser.add_argument("-b", "--broker", help="mqtt broker hostname",
                           default="localhost")
    self.bridge_count = 0
    self.next_report = 0
    self.mq = None
    self.mqtt_topic_incoming_alp = ""
    self.mqtt_topic_outgoing_alp = ""
    self.connected_to_mqtt = False

    self.config = argparser.parse_args()
    self.modem = Modem(self.config.device, self.config.rate, self.on_command_received, show_logging=self.config.verbose)
    self.connect_to_mqtt()

    # update attribute containing git rev so we can track revision at TB platform
    git_sha = subprocess.check_output(["git", "describe", "--always"]).strip()
    ip = self.get_ip()
    # TODO ideally this should be associated with the GW device itself, not with the modem in the GW
    # not clear how to do this using TB-GW
    self.publish_to_topic("/gateway-info", jsonpickle.json.dumps({
      "git-rev": git_sha,
      "ip": ip,
      "device": self.modem.uid
    }))

    print("Running on {} with git rev {}".format(ip, git_sha))


  def on_command_received(self, cmd):
    print("Command received: {}".format(cmd))

    # publish raw ALP command to incoming ALP topic, we will not parse the file contents here (since we don't know how)
    # so pass it as an opaque BLOB for parsing in backend
    self.publish_to_topic(self.mqtt_topic_incoming_alp, jsonpickle.encode(cmd))

    # parse link budget (when this is received over D7 interface) and publish separately so we can visualize this in TB
    if cmd.interface_status != None and cmd.interface_status.operand.interface_id == 0xd7:
      interface_status = cmd.interface_status.operand.interface_status
      node_id = '{:x}'.format(interface_status.addressee.id)
      self.publish_to_topic("/link-budget", jsonpickle.json.dumps({
        "gateway": self.modem.uid,
        "node": node_id,
        "link_budget": interface_status.link_budget,
        "timestamp": str(datetime.now())
      }))


  def connect_to_mqtt(self):
    self.connected_to_mqtt = False

    self.mq = mqtt.Client("", True, None, mqtt.MQTTv31)
    self.mq.on_connect = self.on_mqtt_connect
    self.mq.on_message = self.on_mqtt_message
    self.mqtt_topic_incoming_alp = "/DASH7/incoming/{}".format(self.modem.uid)
    self.mqtt_topic_outgoing_alp = "/DASH7/outgoing/{}".format(self.modem.uid)
    self.mq.connect(self.config.broker, 1883, 60)
    self.mq.loop_start()
    while not self.connected_to_mqtt: pass  # busy wait until connected
    print("Connected to MQTT broker on {}, sending to topic {} and subscribed to topic {}".format(
      self.config.broker,
      self.mqtt_topic_incoming_alp,
      self.mqtt_topic_outgoing_alp
    ))

  def on_mqtt_connect(self, client, config, flags, rc):
    self.mq.subscribe(self.mqtt_topic_outgoing_alp)
    self.connected_to_mqtt = True

  def on_mqtt_message(self, client, config, msg):
    print("on_message")  # TODO

  def publish_to_topic(self, topic, msg):
    if not self.connected_to_mqtt:
      print("not connected to MQTT, skipping")
      return

    self.mq.publish(topic, msg)



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
      except serial.SerialException:
        time.sleep(1)
        print("resetting serial connection...")
        self.setup_modem()
        return
      except KeyboardInterrupt:
        print("received KeyboardInterrupt... stopping processing")
        keep_running = False

      self.report_stats()

  def keep_stats(self):
    self.bridge_count += 1

  def report_stats(self):
    if self.next_report < time.time():
      if self.bridge_count > 0:
        print("bridged %s messages" % str(self.bridge_count))
        self.bridge_count = 0
      self.next_report = time.time() + 15  # report at most every 15 seconds

  def get_ip(self):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
      # doesn't even have to be reachable
      s.connect(('10.255.255.255', 1))
      IP = s.getsockname()[0]
    except:
      IP = '127.0.0.1'
    finally:
      s.close()
    return IP


if __name__ == "__main__":
  Gateway().run()
