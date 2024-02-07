"""
The given host is pinged using [ICMP](https://en.wikipedia.org/wiki/Internet_Control_Message_Protocol)
with the following library: https://pypi.org/project/icmplib/

The result is added as fields (if `add_additional_info` is true) and looks like the following:

- address:                  The IP address of the host that responded to the request.
- min_round_trip_time_ms:   The minimum round-trip time in milliseconds.
- avg_round_trip_time_ms:   The average round-trip time in milliseconds.
- max_round_trip_time_ms:   The maximum round-trip time in milliseconds.
- round_trip_times_ms:      The list of round-trip times expressed in milliseconds.
                            The results are not rounded unlike other properties.
- packets_sent:             The number of requests transmitted to the remote host
- packets_received:         The number of ICMP responses received from the remote host.
- packet_loss:              Packet loss occurs when packets fail to reach their destination.
                            Returns a float between 0 and 1 (all packets are lost).
- jitter_ms:                The jitter in milliseconds, defined as the variance of the latency of packets flowing
                            through the network.
- is_alive:                 Indicates whether the host is reachable.

If `add_additional_info` is false, just the `is_alive` field is added.
"""
from dataclasses import dataclass, field
from threading import Thread
from typing import Dict, Any
import time
import datetime

# Internal imports.
import config
from models.validations import Range
from modules.base.base import send_data
from modules.inputs.base.base import AbstractVariableModule, AbstractTagModule, models

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module sends ICMP Echo Request packets to a network host and returns the response."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = ["icmplib==3.0.3"]
"""Define your requirements here."""


def unpack_host_object(host_object, add_additional_info: bool = True, address: str = ""):
    """
    Makes the host object from the icmp library to a dictionary.

    :param host_object: The host object to be converted to a dictionary.
    If none is given, a default dictionary is returned.
    :param add_additional_info: Do you want to add additional info about the ping request.
    :param address: The host address defined in the configuration.

    :return: A dictionary containing the unpacked host object.
    """
    fields = {}
    try:
        if not host_object:
            fields["is_alive"] = False
            if add_additional_info:
                fields["jitter_ms"] = 0.0
                fields["packet_loss"] = 0.0
                fields["packets_received"] = 0
                fields["packets_sent"] = 0
                fields["round_trip_times_ms"] = []
                fields["max_round_trip_time_ms"] = 0.0
                fields["avg_round_trip_time_ms"] = 0.0
                fields["min_round_trip_time_ms"] = 0.0
                fields["address"] = address
        else:
            fields["is_alive"] = host_object.is_alive
            if add_additional_info:
                fields["jitter_ms"] = host_object.jitter
                fields["packet_loss"] = host_object.packet_loss
                fields["packets_received"] = host_object.packets_received
                fields["packets_sent"] = host_object.packets_sent
                fields["round_trip_times_ms"] = host_object.rtts
                fields["max_round_trip_time_ms"] = host_object.max_rtt
                fields["avg_round_trip_time_ms"] = host_object.avg_rtt
                fields["min_round_trip_time_ms"] = host_object.min_rtt
                fields["address"] = host_object.address
    except Exception as e:
        pass
    finally:
        return fields


class VariableModule(AbstractVariableModule):
    """
    A variable module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module sends ICMP Echo Request packets to a network host in a defined interval " \
                       "and returns the response."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        address: str = field(
            metadata=dict(description="The address of the server (without https or https).",
                          required=False,
                          dynamic=True),
            default="127.0.0.1")
        count: int = field(
            metadata=dict(description="The number of ping performed.",
                          required=False,
                          validate=Range(min=0, max=10)),
            default=1)
        interval: float = field(
            metadata=dict(description="The interval in seconds between sending each packet.",
                          required=False,
                          validate=Range(min=0, max=1000)),
            default=10)
        timeout: float = field(
            metadata=dict(description="The maximum waiting time for receiving a reply in seconds.",
                          required=False,
                          validate=Range(min=0, max=100)),
            default=2)
        add_additional_info: bool = field(
            metadata=dict(description="Add additional information about the ping request.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        Import here the third party requirements as follows:
          global package
          import package

        :returns: True if the import was successful.
        """
        try:
            global icmplib
            import icmplib
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully started, otherwise false.
        """
        Thread(target=self._subscribe,
               daemon=False,
               name="ICMP_Variable_Module_Loop_{0}".format(self.configuration.id)).start()
        return True

    def _subscribe(self):
        """
        This method creates a new loop requesting the endpoint in the given interval
        """
        # The start time of the execution. Needed for the try to implement a non-shifting execution routine.
        start_time = datetime.datetime.now()
        while self.active:
            try:
                try:
                    host_object = icmplib.ping(address=self._dyn(self.configuration.address, data_type="str"),
                                               count=self.configuration.count,
                                               interval=self.configuration.interval,
                                               timeout=self.configuration.timeout,
                                               id=None,
                                               source=None,
                                               family=None,
                                               privileged=True)
                    fields = unpack_host_object(host_object, add_additional_info=self.configuration.add_additional_info)
                except Exception as e:
                    self.logger.error("Could not ping address: {0}".format(str(e)), exc_info=config.EXC_INFO)
                    fields = unpack_host_object(None, add_additional_info=self.configuration.add_additional_info,
                                                address=self.configuration.address)

                data = models.Data(measurement=self.configuration.measurement, fields=fields)
                self._data_change(data)
                # This should prevent shifting a little.
                required_time = datetime.datetime.now() - start_time
                if self.configuration.interval > float(required_time.seconds):
                    time.sleep(self.configuration.interval - float(required_time.seconds))
                else:
                    self.logger.warning("The interval '{0}' s is to short for the request. "
                                        "The required time is '{1}' s."
                                        .format(str(self.configuration.interval), str(required_time)))
                start_time = datetime.datetime.now()
            except Exception as e:
                self.logger.error("Something unexpected went wrong while requesting: {0}"
                                  .format(str(e)), exc_info=config.EXC_INFO)

    @send_data
    def _data_change(self, data: models.Data):
        """
        Send the data.
        """
        return data


class TagModule(AbstractTagModule):
    """
    A tag module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module sends ICMP Echo Request packets to a network host if requested " \
                       "and returns the response."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the module.
        """
        address: str = field(
            metadata=dict(description="The address of the server (without https or https).",
                          required=False,
                          dynamic=True),
            default="127.0.0.1")
        count: int = field(
            metadata=dict(description="The number of ping performed.",
                          required=False,
                          validate=Range(min=0, max=10)),
            default=1)
        timeout: float = field(
            metadata=dict(description="The maximum waiting time for receiving a reply in seconds.",
                          required=False,
                          validate=Range(min=0, max=100)),
            default=2)
        add_additional_info: bool = field(
            metadata=dict(description="Add additional information about the ping request.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        self.previous_status: Dict[str, int] = {}
        """The previous status of the request to `host:port+path`."""

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        Import here the third party requirements as follows:
          global package
          import package

        :returns: True if the import was successful.
        """
        try:
            global icmplib
            import icmplib
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        try:
            host_object = icmplib.ping(address=self._dyn(self.configuration.address, data_type="str"),
                                       count=self.configuration.count,
                                       interval=self.configuration.interval,
                                       timeout=self.configuration.timeout,
                                       id=None,
                                       source=None,
                                       family=None,
                                       privileged=True)
            fields = unpack_host_object(host_object, add_additional_info=self.configuration.add_additional_info)
        except Exception as e:
            self.logger.error("Could not ping address: {0}".format(str(e)), exc_info=config.EXC_INFO)
            fields = unpack_host_object(None, add_additional_info=self.configuration.add_additional_info,
                                        address=self.configuration.address)
        return fields if fields else {}
