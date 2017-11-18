from bitstring import ConstBitStream
from yapsy.IPlugin import IPlugin

from gateway import DataPointType


class ParseSensorFilePlugin(IPlugin):
  def parse_file_data(self, file_offset, data):
    # filter on the file ID for instance
    if file_offset.id == 64:
      # parse the data, in this example we are assuming the file data contains 2 sensor values of type int8
      # note this is a generator function, so multiple values can be returned
      s = ConstBitStream(bytes=bytearray(data))
      sensor_value = s.read("int:8")
      yield 'my-sensorvalue1', sensor_value, DataPointType.telemetry
      sensor_value = s.read("int:8")
      yield 'my-sensorvalue2', sensor_value, DataPointType.telemetry

    return