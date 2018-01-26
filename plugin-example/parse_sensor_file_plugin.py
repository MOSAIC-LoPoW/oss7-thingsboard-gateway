from bitstring import ConstBitStream
from yapsy.IPlugin import IPlugin

from gateway import DataPointType


class ParseSensorFilePlugin(IPlugin):
  def parse_file_data(self, file_offset, length, data):
    # filter on the file ID for instance
    if file_offset.id == 64:
        # parse the data, in this example we are assuming the file data contains a temperature value in decicelsius
        # stored as int16, as transmitted by the sensor examples of OSS-7
        s = ConstBitStream(bytes=bytearray(data))
        sensor_value = s.read("uintbe:16") / 10.0
        yield 'temperature', sensor_value, DataPointType.telemetry
        # note this is a generator function, so multiple values can be returned

    return
