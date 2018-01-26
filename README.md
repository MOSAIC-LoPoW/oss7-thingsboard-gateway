# Introduction

The goal of this project is to integrate a [DASH7](http://www.dash7-alliance.org/) gateway running [OSS-7](http://mosaic-lopow.github.io/dash7-ap-open-source-stack/)
 with the [ThingsBoard](https://github.com/thingsboard/thingsboard) platform. This allows to use the Thingsboard platform for data collection, visualization and device management
 of the GW, but also of the DASH7 nodes in the network. All nodes can be visualized on a dashboard with their link budget, and file data received from nodes is stored 
 inside the platform resulting in a digital twin.

# Installation

The following assumes you are installing this on a raspberry pi 3 running raspbian, but other Linux systems should work similarly.
This also assumes that you have a ThingsBoard instance running somewhere where you have access to. This might be the live demo environment provided by ThingsBoard.
See the Thingsboard [getting started guide](https://thingsboard.io/docs/getting-started-guides/helloworld/)

- clone the repository, including the submodules: `$ git clone --recurse-submodules https://github.com/MOSAIC-LoPoW/oss7-thingsboard-gateway.git`
- install the requirements: `$ sudo pip2 install -r requirements.txt`
- attach a module running [OSS-7](http://mosaic-lopow.github.io/dash7-ap-open-source-stack/) gateway firmware to the pi using for example usb. Below we assume the device is reachable through /dev/ttyACM0
- add a device in the ThingsBoard dashboard, and copy it's access token
- start the gateway script:
    ```
    $ cd /home/pi/oss7-thingsboard-gateway/ 
    $ PYTHONPATH="lib/pyd7a" python2 gateway.py -d /dev/ttyACM0 -t <your access token>
    2018-01-26 12:02:34,247 thingsboard  INFO     MQTT broker connected
    2018-01-26 12:02:34,247 thingsboard  INFO     ThingsBoard GW started
    2018-01-26 12:02:34,247 root         INFO     Searching for plugins in path plugin-example/
    2018-01-26 12:02:34,249 root         INFO     Loading plugin 'Parse sensor file'
    2018-01-26 12:02:34,250 modem.modem  INFO     starting read thread
    2018-01-26 12:02:34,280 modem.modem  INFO     Sending command of size 17
    2018-01-26 12:02:34,280 modem.modem  INFO     Waiting for response (max 60 s)
    2018-01-26 12:02:34,309 modem.modem  INFO     Received response for sync execution
    2018-01-26 12:02:34,309 modem.modem  INFO     cmd with tag 4 done
    2018-01-26 12:02:34,333 modem.modem  INFO     connected to /dev/ttyACM0, node UID 433731340047002d running D7AP v1.1, application "gatewa" with git sha1 a01358e
    2018-01-26 12:02:34,341 root         INFO     Running on 143.129.37.14 with git rev 1594543 using modem 433731340047002d
    ...
    
    ```
- if you start another node running sensor firmware you should see packets being received on the gateway console:
    ```
    2018-01-26 12:04:46,826 root         INFO     Command received: Command with tag 21 (executing)
        actions:
                action: ReturnFileData: file-id=64, offset=0, length=2, data=[0, 0]
        interface status: interface-id=215, status=unicast=False, nls=False, retry=False, missed=False, fifo_token=170, rx_level=13, seq_nr=0, target_rx_level=80, addressee=ac=1, id_type=IdType.UID, id=0x4237343400240035L, response_to=exp=3 mant17, link_budget=23, channel_header=coding=ChannelCoding.PN9, class=ChannelClass.NORMAL_RATE, band=ChannelBand.BAND_868, channel_index=0
    ```
- the sensor device as well as the gateway modem device should appear in the `devices` tab in the ThingsBoard web interface, and the telemetery data is recorded and can be visualized
- if you want to run this as daemon and start when the pi boots (optional):
    ```
    $ sudo ln -s /home/pi/oss7-thingsboard-gateway/init.d/d7-gateway /etc/init.d/d7-gateway
    $ sudo mkdir /etc/d7-gateway && sudo cp etc/d7-gateway.conf /etc/d7-gateway/d7-gateway.conf
    $ sudo update-rc.d d7-gateway defaults
    $ service d7-gateway start
    ```
    Make sure to configure your access token in the d7-gateway.conf file. The config file is passed to the script as command line parameters,
    so all parameters available (check with `--help`) can be specified there. 

# Plug-ins

The gateway can be extended with plug-ins which enable parsing the raw file data into a (set of) readable attribute or telemetry name and value,
which can be visualized directly in the TB platform. An example is present in `plugin-example` and this can be enabled by starting the gateway
by supplying `-p plugin-example` where this is referring to the path containing the plug-in. The plug-in path can be stored outside of the
 tree of this project, to keep things separated. 