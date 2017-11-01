from bitstring import ConstBitStream
from yapsy.IPlugin import IPlugin

class ParseSensorFilePlugin(IPlugin):
  def parse_file_data(self, file_offset, data):
    # filter on the file ID for instance
    if file_offset.id == 64:
      # parse the data
      s = ConstBitStream(bytes=bytearray(data))
      sensor_value = s.read("int:16")
      return 'my-sensor', sensor_value
    return None, None