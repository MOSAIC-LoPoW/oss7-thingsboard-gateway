#!/usr/bin/env python

import argparse
import platform
import socket
import subprocess
import traceback
from enum import Enum
import jsonpickle
import json
import serial
import time
from datetime import datetime
from threading import Timer
import signal
import sys
import binascii
from yapsy.PluginManager import PluginManagerSingleton

from d7a.alp.command import Command
from d7a.alp.interface import InterfaceType
from d7a.alp.operations.responses import ReturnFileData
from d7a.d7anp.addressee import Addressee, IdType
from d7a.sp.configuration import Configuration
from d7a.sp.qos import ResponseMode, QoS
from d7a.system_files.dll_config import DllConfigFile
from d7a.system_files.system_file_ids import SystemFileIds
from d7a.system_files.system_files import SystemFiles
from modem.modem import Modem

from thingsboard import Thingsboard

import logging

class DataPointType(Enum):
  attribute = 0
  telemetry = 1

class Gateway:
  def __init__(self):
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--device", help="serial device /dev file modem", default="/dev/ttyACM0")
    argparser.add_argument("-r", "--rate", help="baudrate for serial device", type=int, default=115200)
    argparser.add_argument("-v", "--verbose", help="verbose", default=False, action="store_true")
    argparser.add_argument("-t", "--token", help="Access token for the TB gateway", required=True)
    argparser.add_argument("-tb", "--thingsboard", help="Thingsboard hostname/IP", default="localhost")
    argparser.add_argument("-p", "--plugin-path", help="path where plugins are stored", default="")
    argparser.add_argument("-bp", "--broker-port", help="mqtt broker port",
                           default="1883")
    argparser.add_argument("-l", "--logfile", help="specify path if you want to log to file instead of to stdout",
                           default="")
    argparser.add_argument("-k", "--keep-data", help="Save data locally when Thingsboard is disconnected and send it when connection is restored.",
                           default=True)
    argparser.add_argument("-b", "--save-bandwidth", help="Send data in binary format to save bandwidth", action="store_true")
    argparser.add_argument("-sf", "--skip-system-files", help="Do not read system files on boot", action="store_true")

    self.bridge_count = 0
    self.next_report = 0
    self.config = argparser.parse_args()
    self.log = logging.getLogger()

    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    if self.config.logfile == "":
      handler = logging.StreamHandler()
    else:
      handler = logging.FileHandler(self.config.logfile)

    handler.setFormatter(formatter)
    self.log.addHandler(handler)
    self.log.setLevel(logging.INFO)
    if self.config.verbose:
      self.log.setLevel(logging.DEBUG)

    self.tb = Thingsboard(self.config.thingsboard, self.config.token, self.on_mqtt_message, persistData=self.config.keep_data)

    if self.config.plugin_path != "":
      self.load_plugins(self.config.plugin_path)

    self.modem = Modem(self.config.device, self.config.rate, self.on_command_received, self.config.save_bandwidth)
    connected = self.modem.connect()
    while not connected:
      try:
        self.log.warning("Not connected to modem, retrying ...")
        time.sleep(1)
        connected = self.modem.connect()
      except KeyboardInterrupt:
        self.log.info("received KeyboardInterrupt... stopping")
        self.tb.disconnect()
        exit(-1)
      except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        trace = "".join(lines)
        self.log.error("Exception while connecting modem: \n{}".format(trace))

    # switch to continuous foreground scan access profile
    self.modem.execute_command(
      Command.create_with_write_file_action_system_file(DllConfigFile(active_access_class=0x01)), timeout_seconds=1)

    if self.config.save_bandwidth:
      self.log.info("Running in save bandwidth mode")
      if self.config.plugin_path is not "":
        self.log.warning("Save bandwidth mode is enabled, plugin files will not be used")

    # update attribute containing git rev so we can track revision at TB platform
    git_sha = subprocess.check_output(["git", "describe", "--always"]).strip()
    ip = self.get_ip()
    self.tb.sendGwAttributes({'UID': self.modem.uid, 'git-rev': git_sha, 'IP': ip, 'save bw': str(self.config.save_bandwidth)})

    self.log.info("Running on {} with git rev {} using modem {}".format(ip, git_sha, self.modem.uid))

    # read all system files on the local node to store as attributes on TB
    if not self.config.skip_system_files:
      self.log.info("Reading all system files ...")
      for file in SystemFiles().files.values():
        self.modem.execute_command_async(
          Command.create_with_read_file_action_system_file(file)
        )

  def load_plugins(self, plugin_path):
    self.log.info("Searching for plugins in path %s" % plugin_path)
    manager = PluginManagerSingleton.get()
    manager.setPluginPlaces([plugin_path])
    manager.collectPlugins()

    for plugin in manager.getAllPlugins():
      self.log.info("Loading plugin '%s'" % plugin.name)

  def on_command_received(self, cmd):
    try:
      if self.config.save_bandwidth:
        self.log.info("Command received: binary ALP (size {})".format(len(cmd)))
      else:
        self.log.info("Command received: {}".format(cmd))

      ts = int(round(time.time() * 1000))

      # publish raw ALP command to incoming ALP topic, we will not parse the file contents here (since we don't know how)
      # so pass it as an opaque BLOB for parsing in backend
      if self.config.save_bandwidth:
        self.tb.sendGwAttributes({'alp': binascii.hexlify(bytearray(cmd)), 'last_seen': str(datetime.now().strftime("%y-%m-%d %H:%M:%S"))})
        return

      self.tb.sendGwAttributes({'alp': jsonpickle.encode(cmd), 'last_seen': str(datetime.now().strftime("%y-%m-%d %H:%M:%S"))})

      node_id = self.modem.uid # overwritten below with remote node ID when received over D7 interface
      # parse link budget (when this is received over D7 interface) and publish separately so we can visualize this in TB
      if cmd.interface_status != None and cmd.interface_status.operand.interface_id == 0xd7:
        interface_status = cmd.interface_status.operand.interface_status
        node_id = '{:x}'.format(interface_status.addressee.id)
        linkBudget = interface_status.link_budget
        rxLevel = interface_status.rx_level
        lastConnect = "D7-" + interface_status.get_short_channel_string()
        self.tb.sendDeviceTelemetry(node_id, ts, {'lb': linkBudget, 'rx': rxLevel})
        self.tb.sendDeviceAttributes(node_id, {'last_conn': lastConnect, 'last_gw': self.modem.uid})

      # store returned file data as attribute on the device
      for action in cmd.actions:
        if type(action.operation) is ReturnFileData:
          data = ""
          if action.operation.file_data_parsed is not None:
            if not self.config.save_bandwidth:
              # for known system files we transmit the parsed data
              data = jsonpickle.encode(action.operation.file_data_parsed)
              file_id = "File {}".format(action.operand.offset.id)
              self.tb.sendGwAttributes({file_id: data})
          else:
            # try if plugin can parse this file
            parsed_by_plugin = False
            if not self.config.save_bandwidth:
              for plugin in PluginManagerSingleton.get().getAllPlugins():
                for name, value, datapoint_type in plugin.plugin_object.parse_file_data(action.operand.offset, action.operand.length, action.operand.data):
                  parsed_by_plugin = True
                  if isinstance(value, int) or isinstance(value, float):
                    self.tb.sendDeviceTelemetry(node_id, ts, {name: value})
                  else:
                    self.tb.sendDeviceAttributes(node_id, {name: value})

            if not parsed_by_plugin:
              # unknown file content, just transmit raw data
              data = jsonpickle.encode(action.operand)
              filename = "File {}".format(action.operand.offset.id)
              if action.operation.systemfile_type != None:
                filename = "File {} ({})".format(SystemFileIds(action.operand.offset.id).name, action.operand.offset.id)
              self.tb.sendDeviceAttributes(node_id, {filename: data})


    except:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
      trace = "".join(lines)
      self.log.error("Exception while processing command: \n{}".format(trace))

  def on_mqtt_message(self, client, config, msg):
    try:
      payload = json.loads(msg.payload)
      uid = payload['device']
      method = payload['data']['method']
      request_id = payload['data']['id']
      self.log.info("Received RPC command of type {} for {} (request id {})".format(method, uid, request_id))
      # if uid != self.modem.uid:
      #   self.log.info("RPC command not for this modem ({}), skipping".format(self.modem.uid))
      #   return

      if method == "execute-alp-async":
        try:
          cmd = payload['data']['params']
          self.log.info("Received command through RPC: %s" % cmd)

          self.modem.execute_command_async(cmd)
          self.log.info("Executed ALP command through RPC")

          # TODO when the command is writing local files we could read them again automatically afterwards, to make sure the digital twin is updated
        except Exception as e:
          self.log.exception("Could not deserialize: %s" % e)
      elif method == "alert":
        # TODO needs refactoring so different methods can be supported in a plugin, for now this is very specific case as an example
        self.log.info("Alert (payload={})".format(msg.payload))
        if msg.payload != "true" and msg.payload != "false":
          self.log.info("invalid payload, skipping")
          return

        file_data = 0
        if msg.payload == "true":
          file_data = 1

        self.log.info("writing alert file")
        self.modem.execute_command_async(
          Command.create_with_write_file_action(
            file_id=0x60,
            offset=4,
            data=[file_data],
            interface_type=InterfaceType.D7ASP,
            interface_configuration=Configuration(
              qos=QoS(resp_mod=ResponseMode.RESP_MODE_ALL),
              addressee=Addressee(
                access_class=0x11,
                id_type=IdType.NOID
              )
            )
          )
        )

      else:
        self.log.info("RPC method not supported, skipping")
        return
    except:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
      trace = "".join(lines)
      msg_info = "no msg info (missing __dict__ attribute)"  # TODO because of out of date paho??
      if hasattr(msg, '__dict__'):
        msg_info = str(msg.__dict__)

      self.log.error("Exception while processing MQTT message: {} callstack:\n{}".format(msg_info, trace))


  def run(self):
    self.log.info("Started")
    keep_running = True
    while keep_running:
      try:
        if platform.system() == "Windows":
          time.sleep(1)
        else:
          signal.pause()
      except KeyboardInterrupt:
        self.log.info("received KeyboardInterrupt... stopping processing")
        self.tb.disconnect()
        keep_running = False

      self.report_stats()

  def keep_stats(self):
    self.bridge_count += 1

  def report_stats(self):
    if self.next_report < time.time():
      if self.bridge_count > 0:
        self.log.info("bridged %s messages" % str(self.bridge_count))
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
