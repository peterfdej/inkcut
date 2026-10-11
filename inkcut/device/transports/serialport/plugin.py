# -*- coding: utf-8 -*-
"""
Copyright (c) 2017-2019, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file LICENSE, distributed with this software.

Created on Jul 12, 2015

@author: jrm
"""
import serial
import traceback
from atom.atom import set_default
from atom.api import List, Instance, Enum, Bool, Int, Str
from inkcut.core.api import Plugin, Model, log
from inkcut.device.plugin import DeviceTransport
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, connectionDone
from twisted.internet.serialport import SerialPort
from serial.tools.list_ports import comports

from inkcut.device.transports.raw.plugin import RawFdTransport, RawFdProtocol

#: Reverse key values
SERIAL_PARITIES = {v: k for k, v in serial.PARITY_NAMES.items()}


class SerialConfig(Model):
    #: Available serial ports
    ports = List()

    #: Serial port config
    port = Str().tag(config=True)
    baudrate = Int(9600).tag(config=True)
    bytesize = Enum(serial.EIGHTBITS, serial.SEVENBITS, serial.SIXBITS,
                    serial.FIVEBITS).tag(config=True)
    parity = Enum(*serial.PARITY_NAMES.values()).tag(config=True)
    stopbits = Enum(serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE,
                    serial.STOPBITS_TWO).tag(config=True)
    xonxoff = Bool().tag(config=True)
    rtscts = Bool().tag(config=True)
    dsrdtr = Bool().tag(config=True)

    # -------------------------------------------------------------------------
    # Defaults
    # -------------------------------------------------------------------------
    def _default_ports(self):
        return comports()

    def _default_parity(self):
        return 'None'

    def _default_port(self):
        if self.ports:
            return self.ports[0].device
        return ""

    def refresh(self):
        self.ports = self._default_ports()


class SerialTransport(RawFdTransport):

    #: Default config
    config = Instance(SerialConfig, ()).tag(config=True)

    #: Connection port
    connection = Instance(SerialPort)

    #: Whether a serial connection spools depends on the device (configuration)
    always_spools = set_default(False)

    def connect(self):
        config = self.config
        self.device_path = config.port
        try:
            #: Save a reference
            self.protocol.transport = self

            #: Make the wrapper
            self._protocol = RawFdProtocol(self, self.protocol)

            self.connection = SerialPort(
                self._protocol,
                config.port,
                reactor,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                parity=SERIAL_PARITIES[config.parity],
                stopbits=config.stopbits,
                xonxoff=config.xonxoff,
                rtscts=config.rtscts
            )

            # Twisted is missing this
            if config.dsrdtr:
                try:
                    self.connection._serial.dsrdtr = True
                except AttributeError as e:
                    log.warning("{} | dsrdtr is not supported {}".format(
                        config.port, e))

            log.debug("{} | opened".format(config.port))
        except Exception as e:
            #: Make sure to log any issues as these tracebacks can get
            #: squashed by twisted
            log.error("{} | {}".format(config.port, traceback.format_exc()))
            raise

    def disconnect(self):
        if self.connection:
            log.debug("-- {} | closed by request".format(self.device_path))

            connection = self.connection

            try:
                # Remove the Windows serial events from the reactor
                connection.reactor.removeEvent(
                    connection._overlappedRead.hEvent
                )
                connection.reactor.removeEvent(
                    connection._overlappedWrite.hEvent
                )

                # Close the underlying pySerial port
                if connection._serial.is_open:
                    connection._serial.close()

            except Exception:
                log.error(
                    "{} | error closing serial port:\n{}".format(
                        self.device_path,
                        traceback.format_exc()
                    )
                )

            self.connection = None

        self.connected = False

    def query_size(self):
        """Query the plotter work area using the OH; command."""

        import serial

        config = self.config
        port = config.port

        log.debug("PNC QUERY: closing Inkcut serial connection")
        self.disconnect()

        ser = None

        try:
            log.debug("PNC QUERY: opening %s with pySerial", port)

            ser = serial.Serial(
                port=port,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                parity=SERIAL_PARITIES[config.parity],
                stopbits=config.stopbits,
                timeout=1,
                xonxoff=config.xonxoff,
                rtscts=config.rtscts,
                dsrdtr=config.dsrdtr
            )

            log.debug("PNC QUERY: pySerial opened")

            ser.reset_input_buffer()

            log.debug("PNC QUERY: sending OH;")

            ser.write(b"OH;")
            ser.flush()

            response = ser.read_until(b"\r")

            log.debug("PNC QUERY: RAW RESPONSE = %r", response)

            if not response:
                raise IOError("No response from plotter to OH;")

            response = response.decode("ascii").strip()

            log.debug("PNC QUERY: RESPONSE = %s", response)

            values = [int(x.strip()) for x in response.split(",")]

            if len(values) != 4:
                raise ValueError(
                    "Unexpected OH response: {!r}".format(response)
                )

            log.debug("PNC QUERY: RESULT = %s", values)

            return values

        finally:
            if ser is not None:
                ser.close()
                log.debug("PNC QUERY: pySerial closed")



class SerialPlugin(Plugin):
    """ Plugin for handling serial port communication

    """

    # -------------------------------------------------------------------------
    # SerialPlugin API
    # -------------------------------------------------------------------------
