import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class Mqtt:
    def __init__(self, broker, port = 1883, subscription_topic=None, mqtt_callback=None):
        self.broker = broker
        self.port = port
        self.mqtt_callback = mqtt_callback
        self.connected_to_mqtt = False
        self.subscription_topic = subscription_topic
        try:
            self.connect_mqtt()
        except:
            logger.warning("Can't connect to MQTT broker")

    def connect_mqtt(self):
        self.mq = mqtt.Client()
        self.mq.on_connect = self.on_mqtt_connect
        self.mq.on_disconnect = self.on_mqtt_disconnect
        try:
            self.mq.connect(self.broker, self.port)
            if self.subscription_topic is not None and self.mqtt_callback is not None:
                self.mq.on_message = self.on_mqtt_message
                self.mq.subscribe(self.subscription_topic, qos=1)
            self.mq.loop_start()
            while not self.connected_to_mqtt: pass  # busy wait until connected
        except:
            logger.warning("Failed to connect MQTT broker")
            self.connected_to_mqtt = False
            raise

    def on_mqtt_connect(self, client, userdata, flags_dict, rc):
        self.connected_to_mqtt = True
        logger.info("Connected to MQTT broker at %s", self.broker)

    def on_mqtt_disconnect(self, client, userdata, rc):
        self.connected_to_mqtt = False
        logger.warning("MQTT broker disconnected")

    def on_mqtt_message(self, client, config, msg):
        self.mqtt_callback(client, config, msg)

    def publish_message(self, topic, message):
        self.mq.publish(topic, message)

    def disconnect(self):
        self.mq.loop_stop()
        self.mq.disconnect()
