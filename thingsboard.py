import logging
import paho.mqtt.client as mqtt

class Thingsboard():
    def __init__(self, broker, token, mqttCallback):
        self.log = logging.getLogger(__name__)

        self.connected_to_mqtt = False
        self.mqttCallback = mqttCallback
        self.connectMqtt(broker, token)

        self.GATEWAY_ATTRIBUTES_TOPIC = "v1/gateway/attributes"
        self.GATEWAY_TELEMETRY_TOPIC = "v1/gateway/telemetry"
        self.DEVICE_ATTRIBUTES_TOPIC = "v1/devices/me/attributes"
        self.DEVICE_TELEMETRY_TOPIC = "v1/devices/me/telemetry"

    def connectMqtt(self, broker, token):
        self.mq = mqtt.Client()
        self.mq.username_pw_set(token)
        self.mq.on_connect = self.onMqttConnect()
        self.mq.on_message = self.mqttCallback
        self.mq.connect(broker, 1883, 1)
        self.mq.loop_start()
        while not self.connected_to_mqtt: pass  # busy wait until connected
        self.log.info("Connected to MQTT broker")

    def onMqttConnect(self):
        self.connected_to_mqtt = True
        self.log.debug("MQTT connect done")

    def sendGwAttributes(self, values):
        msg = str(values)
        self.mq.publish(self.DEVICE_ATTRIBUTES_TOPIC, msg, 1)
        self.log.debug("Attributes sent to gateway")

    def sendGwTelemetry(self, values):
        msg = str(values)
        self.mq.publish(self.DEVICE_TELEMETRY_TOPIC, msg, 1)
        self.log.debug("Attributes sent to gateway")

    def sendDeviceAttributes(self, device, values):
        msg = "{{'{}': {}}}".format(device, values)
        self.mq.publish(self.GATEWAY_ATTRIBUTES_TOPIC, msg, 1)
        self.log.debug("Attributes sent to device")

    def sendDeviceTelemetry(self, device, timestamp, values):
        msg = "{{'{}': [{{'ts': {}, 'values': {}}}]}}".format(device, timestamp, values)
        self.mq.publish(self.GATEWAY_TELEMETRY_TOPIC, msg, 1)
        self.log.debug("Telemetry sent to device")

    def __del__(self):
        try:
            self.mq.loop_stop()
            self.mq.disconnect()
        except:
            pass