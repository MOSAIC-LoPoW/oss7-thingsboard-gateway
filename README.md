# Introduction

The goal of this project is to integrate a [DASH7](http://www.dash7-alliance.org/) gateway running [OSS-7](http://mosaic-lopow.github.io/dash7-ap-open-source-stack/)
 with the ThingsBoard IoT Gateway and ThingsBoard platform. This allows to use the Thingsboard platform for data collection, visualization and device management
 of the GW, but also of the DASH7 nodes in the network. All nodes can be visualized on a dashboard with their link budget, and file data received from nodes is stored 
 inside the platform resulting in a digital twin.

# Installation

The following assumes you are installing this on a raspberry pi 3 running raspbian, but other Linux systems should work similarly.
This also assumes that you have a ThingsBoard instance running somewhere where you have access to. This might be the live demo environment.
See the Thingsboard [getting started guide](https://thingsboard.io/docs/getting-started-guides/helloworld/)

- clone the repository, including the submodules: `$ git clone --recurse-submodules https://github.com/MOSAIC-LoPoW/oss7-thingsboard-gateway.git`
- make sure you have all the dependencies of pyd7a installed:
    ```
    $ cd lib/pyd7a
    $ sudo pip install -r requirements.txt
    ```
- install a local MQTT broker: `$ sudo aptitude install mosquitto`
- install thingsboard-gateway on your pi as described [here](https://thingsboard.io/docs/iot-gateway/install/rpi/)
- in the `/etc/tb-gateway/conf/tb-gateway.yml` file set the mqtt enabled option to true, since we will be integrating with thingsboard-gateway using MQTT.
    ```
    mqtt:
      enabled: true
      configuration: mqtt-config.json
    ```
- the MQTT configuration file is part of this repository, since it contains specific topic names which are used specifically by the gateway script.
To enable this we will remove the file from `/etc/tb-gateway/conf/` and a link to this file like this
    ```
    $ sudo rm /usr/share/tb-gateway/conf/mqtt-config.json
    $ sudo ln -s /home/pi/oss7-thingsboard-gateway/tb-gateway-conf/mqtt-config.json /etc/tb-gateway/conf/mqtt-config.json
    
    ```
- restart using `sudo service tb-gateway restart` and monitor the log file for errors using `tail -f /var/log/tb-gateway/tb-gateway.log` to make sure the configuration is valid
- attach a module running [OSS-7](http://mosaic-lopow.github.io/dash7-ap-open-source-stack/) gateway firmware to the pi using for example usb. Below we assume the device is reachable through /dev/ttyACM0

- start the gateway script:
    ```
    $ cd /home/pi/oss7-thingsboard-gateway/ 
    $ PYTHONPATH="lib/pyd7a" python2 gateway.py -d /dev/ttyACM0
    connected to /dev/ttyACM0, node UID 41303039002f002a running D7AP v1.1, application "gatewa" with git sha1 94f10de
    Connected to MQTT broker on localhost, sending to topic /DASH7/incoming/41303039002f002a and subscribed to topic /DASH7/outgoing/41303039002f002a
    Started
    ```
- if you start another node running sensor firmware you should see packets being received on the gateway console:
    ```
    Command received: Command with tag 25 (executing)
        actions:
                action: ReturnFileData: file-id=64, size=1, offset=0, length=8, data=[21, 24, 1, 0, 0, 0, 0, 0]
        interface status: interface-id=215, status=unicast=False, nls=False, retry=False, missed=False, fifo_token=190, rx_level=24, seq_nr=0, target_rx_level=80, addressee=ac=1, id_type=IdType.UID, id=0x42373436001a0042L, response_to=exp=0 mant0, link_budget=34, channel_header=coding=ChannelCoding.PN9, class=ChannelClass.NORMAL_RATE, band=ChannelBand.BAND_868, channel_index=0
    ```
- the sensor device as well as the gateway modem device should appear in the `devices` tab in the ThingsBoard web interface, and the telemetery data is recorded and can be visualized
- make sure the gateway is started on boot using the init script:
    ```
    $ sudo ln -s /home/pi/oss7-thingsboard-gateway/init.d/d7-gateway /etc/init.d/d7-gateway
    $ sudo update-rc.d d7-gateway defaults
    $ service d7-gateway start
    ```
