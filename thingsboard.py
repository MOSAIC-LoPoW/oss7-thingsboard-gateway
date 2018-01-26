import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class Thingsboard():
    def __init__(self, broker, token, mqttCallbackFunction, persistData=True):
        self.log = logger
        self.connected_to_mqtt = False
        self.broker = broker
        self.token = token
        self.mqttCallback = mqttCallbackFunction
        self.persistData = persistData
        if self.persistData:
            self.gw_telemetry_queue = []
            self.device_telemetry_queue = []
            #TODO: set maximum queue sizes

        self.connectMqtt()

        self.GATEWAY_ATTRIBUTES_TOPIC = "v1/gateway/attributes"
        self.GATEWAY_TELEMETRY_TOPIC = "v1/gateway/telemetry"
        self.DEVICE_ATTRIBUTES_TOPIC = "v1/devices/me/attributes"
        self.DEVICE_TELEMETRY_TOPIC = "v1/devices/me/telemetry"
        self.log.info("ThingsBoard GW started")

    def connectMqtt(self):
        self.mq = mqtt.Client()
        self.mq.username_pw_set(self.token)
        self.mq.on_connect = self.onMqttConnect
        self.mq.on_disconnect = self.onMqttDisconnect
        self.mq.on_message = self.mqttCallback
        try:
            self.mq.connect(self.broker, 1883, 1)
            self.mq.loop_start()
            while not self.connected_to_mqtt: pass  # busy wait until connected
            if self.persistData and self.checkQueue():
                for msg in self.gw_telemetry_queue: self.sendGwTelemetry(msg)
                self.gw_telemetry_queue = []
                for msg in self.device_telemetry_queue: self.sendDeviceTelemetry(msg[0], msg[1], msg[2])
                self.device_telemetry_queue = []
                self.log.info("Queued messages sent to Thingsboard")
        except:
            self.log.warning("Failed to connect MQTT broker")
            self.connected_to_mqtt = False
            raise

    def onMqttConnect(self, client, userdata, flags_dict, rc):
        self.connected_to_mqtt = True
        self.log.info("MQTT broker connected")

    def onMqttDisconnect(self, client, userdata, rc):
        self.connected_to_mqtt = False
        self.log.warning("MQTT broker disconnected")

    def sendGwAttributes(self, values):
        msg = str(values)
        self.mq.publish(self.DEVICE_ATTRIBUTES_TOPIC, msg, qos=1)
        self.log.debug("Attributes sent to TB gateway")

    def sendGwTelemetry(self, values):
        if self.connected_to_mqtt:
            msg = str(values)
            self.mq.publish(self.DEVICE_TELEMETRY_TOPIC, msg, qos=1)
            self.log.debug("Attributes sent to TB gateway")
        elif self.persistData:
            self.gw_telemetry_queue.append(values)
            self.log.info("MQTT disconnected, telemetry added to queue")

    def sendDeviceAttributes(self, device, values):
        msg = "{{'{}': {}}}".format(device, values)
        self.mq.publish(self.GATEWAY_ATTRIBUTES_TOPIC, msg, qos=1)
        self.log.debug("Attributes sent to TB device")

    def sendDeviceTelemetry(self, device, timestamp, values):
        if self.connected_to_mqtt:
            msg = "{{'{}': [{{'ts': {}, 'values': {}}}]}}".format(device, timestamp, values)
            self.mq.publish(self.GATEWAY_TELEMETRY_TOPIC, msg, qos=1)
            self.log.debug("Telemetry sent to TB device")
        elif self.persistData:
            self.device_telemetry_queue.append([device, timestamp, values])
            self.log.info("MQTT disconnected, telemetry added to queue")

    def checkQueue(self):
        if len(self.device_telemetry_queue) == 0 and len(self.gw_telemetry_queue) == 0:
            return False
        else: return True

    def disconnect(self):
        self.log.info("Disconnecting from ThingsBoard")
        self.mq.loop_stop()
        self.mq.disconnect()
