import logging
import paho.mqtt.client as mqtt
from threading import Timer
from datetime import datetime

logger = logging.getLogger(__name__)

class Thingsboard():
    def __init__(self, broker, token, mqttCallbackFunction, persistData=True, heartbeat_interval_seconds=5):
        self.gwReportTimeout = heartbeat_interval_seconds
        self.log = logger
        self.connected_to_mqtt = False
        self.broker = broker
        self.token = token
        self.mqttCallback = mqttCallbackFunction
        self.persistData = persistData
        if self.persistData:
            self.gw_telemetry_queue = []
            self.gw_attributes_queue = []
            self.device_telemetry_queue = []
            self.device_attributes_queue = []
            #TODO: set maximum queue sizes?

        try:
            self.connectMqtt()
        except:
            self.log.warning("Can't connect to MQTT broker")

        self.start_report_timer()

        self.GATEWAY_ATTRIBUTES_TOPIC = "v1/gateway/attributes"
        self.GATEWAY_TELEMETRY_TOPIC = "v1/gateway/telemetry"
        self.GATEWAY_RPC_TOPIC = "v1/gateway/rpc"
        self.DEVICE_ATTRIBUTES_TOPIC = "v1/devices/me/attributes"
        self.DEVICE_TELEMETRY_TOPIC = "v1/devices/me/telemetry"

        self.log.info("ThingsBoard GW started")

    #TODO: Handle RPC commands from TB

    def connectMqtt(self):
        self.mq = mqtt.Client()
        self.mq.username_pw_set(self.token)
        self.mq.on_connect = self.onMqttConnect
        self.mq.on_disconnect = self.onMqttDisconnect
        self.mq.on_message = self.mqttCallback
        self.mq.subscribe("v1/gateway/rpc", qos=1)
        try:
            self.mq.connect(self.broker, 1883, 1)
            self.mq.loop_start()
            while not self.connected_to_mqtt: pass  # busy wait until connected
        except:
            self.log.warning("Failed to connect MQTT broker")
            self.connected_to_mqtt = False
            raise

    def onMqttConnect(self, client, userdata, flags_dict, rc):
        self.connected_to_mqtt = True
        self.log.info("MQTT broker connected")
        if self.persistData and self.checkQueue():
            self.flushQueues()

    def onMqttDisconnect(self, client, userdata, rc):
        self.connected_to_mqtt = False
        self.log.warning("MQTT broker disconnected")

    def sendGwAttributes(self, values):
        if self.connected_to_mqtt:
            msg = str(values)
            self.mq.publish(self.DEVICE_ATTRIBUTES_TOPIC, msg, qos=1)
            self.log.debug("Attributes sent to TB gateway")
        else:
            self.gw_attributes_queue.append(values)
            self.log.info("MQTT disconnected, attributes added to queue")

    def sendGwTelemetry(self, values):
        if self.connected_to_mqtt:
            msg = str(values)
            self.mq.publish(self.DEVICE_TELEMETRY_TOPIC, msg, qos=1)
            self.log.debug("Attributes sent to TB gateway")
        elif self.persistData:
            self.gw_telemetry_queue.append(values)
            self.log.info("MQTT disconnected, telemetry added to queue")

    def sendDeviceAttributes(self, device, values):
        if self.connected_to_mqtt:
            msg = "{{'{}': {}}}".format(device, values)
            self.mq.publish(self.GATEWAY_ATTRIBUTES_TOPIC, msg, qos=1)
            self.log.debug("Attributes sent to TB device")
        else:
            self.device_attributes_queue.append([device, values])
            self.log.info("MQTT disconnected, attributes added to queue")

    def sendDeviceTelemetry(self, device, timestamp, values):
        if self.connected_to_mqtt:
            msg = "{{'{}': [{{'ts': {}, 'values': {}}}]}}".format(device, timestamp, values)
            self.mq.publish(self.GATEWAY_TELEMETRY_TOPIC, msg, qos=1)
            self.log.debug("Telemetry sent to TB device")
        elif self.persistData:
            self.device_telemetry_queue.append([device, timestamp, values])
            self.log.info("MQTT disconnected, telemetry added to queue")

    def checkQueue(self):
        if not self.device_telemetry_queue and not self.gw_telemetry_queue and not self.device_attributes_queue and not self.gw_attributes_queue:
            return False
        else: return True

    def flushQueues(self):
        for msg in self.gw_telemetry_queue: self.sendGwTelemetry(msg)
        self.gw_telemetry_queue = []
        for msg in self.device_telemetry_queue: self.sendDeviceTelemetry(msg[0], msg[1], msg[2])
        self.device_telemetry_queue = []
        for msg in self.gw_attributes_queue: self.sendGwAttributes(msg)
        self.gw_attributes_queue = []
        for msg in self.device_attributes_queue: self.sendDeviceAttributes(msg[0], msg[1])
        self.device_attributes_queue = []
        self.log.info("Queued messages sent to Thingsboard")

    def start_report_timer(self):
        self.report_timer = Timer(self.gwReportTimeout, self.gwReport, ())
        self.report_timer.start()

    def gwReport(self):
        self.sendGwAttributes({'last_seen': str(datetime.now().strftime("%y-%m-%d %H:%M:%S"))})
        if self.connected_to_mqtt is False:
            try:
                self.connectMqtt()
            except:
                self.log.debug("Could not connect to MQTT broker...")
        self.start_report_timer()

    def disconnect(self):
        self.log.info("Disconnecting from ThingsBoard")
        self.mq.loop_stop()
        self.report_timer.cancel()
        self.mq.disconnect()

