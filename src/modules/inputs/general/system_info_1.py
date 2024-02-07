"""
https://psutil.readthedocs.io/en/latest/#

This should probably not be executed inside a docker container?!

#### Available Types

- CPU:  Current system-wide CPU utilization as a percentage.
Generated fields:
```json
{
    "cpu_utilized_percent": 35
}
```
- MEMORY:   Statistics about system memory usage in gb.
Generated fields:
```json
{
    "memory_total": 15.952,
    "memory_available": 7.929,
    "memory_percent_used": 50.3,
    "memory_used": 8.023
}
```
- DISK:     All mounted disk partitions and according statistics in gb (not supported for tagging).
Generated data object:
```json
{
    "fields": {"disk_total": 930.948,
               "disk_free": 497.845,
               "disk_used": 433.103,
               "disk_used_percent": 46,
               "disk_type": "NTFS",
               "disk_mount": "C:\\\\"},
    "tags": {"disk_device": "C:\\\\"}
}
```
"""
from dataclasses import dataclass, field
import os
import datetime
import time
from threading import Thread
from typing import Dict, Any, Tuple

# Internal imports.
from models.validations import OneOf, Range
from modules.base.base import send_data
from modules.inputs.base.base import AbstractVariableModule, AbstractTagModule, models

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = False
"""Is this module public?"""
__description__: str = "This module collects metrics from the system it is running on."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = ["psutil==5.8.0"]
"""Define your requirements here."""


def bytes_to(byte, to: str = "g") -> float:
    """
    Convert bytes to megabytes, etc.

    :param byte: The bytes you want to convert.
    :param to: The multiple you want to convert to.

    :returns: The converted value.
    """
    a = {'k': 1, 'm': 2, 'g': 3, 't': 4, 'p': 5, 'e': 6}
    return round(byte / (1024 ** a.get(to, 3)), 3)


def _get_cpu_percent() -> Tuple[dict, dict]:
    """
    Return a float representing the current system-wide CPU utilization as a percentage.
    When interval is > 0.0 compares system CPU times elapsed before and after the interval (blocking).
    When interval is 0.0 or None compares system CPU times elapsed since last call or module import,
    returning immediately. That means the first time this is called it will return a meaningless 0.0 value
    which you are supposed to ignore. In this case it is recommended for accuracy that this function be called
    with at least 0.1 seconds between calls. When percpu is True returns a list of floats representing the
    utilization as a percentage for each CPU. First element of the list refers to first CPU, second element
    to second CPU and so on. The order of the list is consistent across calls.

    Usage:

    psutil.cpu_percent(interval=1)
    2.0

    :returns: The generated fields and tags.
    """
    fields = {'cpu_utilized_percent': psutil.cpu_percent(None)}
    return fields, {}


def _get_memory() -> Tuple[dict, dict]:
    """
    Return statistics about system memory usage as a named tuple including the following fields, expressed in bytes.

    Main metrics:

    total: total physical memory (exclusive swap).
    available: the memory that can be given instantly to processes without the system going into swap.
    This is calculated by summing different memory values depending on the platform and it is supposed to be
    used to monitor actual memory usage in a cross platform fashion.
    percent: (total - available) / total * 100.

    Other metrics:

    used: memory used, calculated differently depending on the platform and designed for informational
    purposes only. total - free does not necessarily match used.
    free: memory not being used at all (zeroed) that is readily available; note that this doesn’t reflect the
    actual memory available (use available instead). total - used does not necessarily match free.
    active (UNIX): memory currently in use or very recently used, and so it is in RAM.
    inactive (UNIX): memory that is marked as not used.
    buffers (Linux, BSD): cache for things like file system metadata.
    cached (Linux, BSD): cache for various things.
    shared (Linux, BSD): memory that may be simultaneously accessed by multiple processes.
    slab (Linux): in-kernel data structures cache.
    wired (BSD, macOS): memory that is marked to always stay in RAM. It is never moved to disk.

    MEMORY
    ------
    Total      :    9.7G
    Available  :    4.9G
    Percent    :    49.0
    Used       :    8.2G
    Free       :    1.4G
    Active     :    5.6G
    Inactive   :    2.1G
    Buffers    :  341.2M
    Cached     :    3.2G

    Usage:

    psutil.virtual_memory()
    svmem(total=10367352832, available=6472179712, percent=37.6, used=8186245120, free=2181107712, active=4748992512,
    inactive=2758115328, buffers=790724608, cached=3500347392, shared=787554304, slab=199348224)

    :returns: The generated fields and tags.
    """
    memory = psutil.virtual_memory()

    fields = {}
    for name in memory._fields:
        value = getattr(memory, name)
        if name != 'percent':
            value = bytes_to(value)
        else:
            name = 'percent_used'
        if name in ['total', 'percent_used', 'available', 'used']:
            fields["memory_" + name] = value
    return fields, {}


def _get_disk_usage(part) -> Tuple[dict, dict]:
    """
    Return disk usage statistics about the partition which contains the given path as a named tuple including total,
    used and free space expressed in bytes, plus the percentage usage. OSError is raised if path does not exist.
    Starting from Python 3.3 this is also available as shutil.disk_usage (see BPO-12442).

    List all mounted disk partitions a-la "df -h" command.

    Device               Total     Used     Free  Use %      Type  Mount
    /dev/sdb3            18.9G    14.7G     3.3G    77%      ext4  /
    /dev/sda6           345.9G    83.8G   244.5G    24%      ext4  /home
    /dev/sda1           296.0M    43.1M   252.9M    14%      vfat  /boot/efi
    /dev/sda2           600.0M   312.4M   287.6M    52%   fuseblk  /media/Recovery

    Usage:

    psutil.disk_partitions()
    [sdiskpart(device='/dev/sda3', mountpoint='/', fstype='ext4', opts='rw,errors=remount-ro', maxfile=255, maxpath=4096),
     sdiskpart(device='/dev/sda7', mountpoint='/home', fstype='ext4', opts='rw', maxfile=255, maxpath=4096)]

    psutil.disk_usage('/')
    sdiskusage(total=21378641920, used=4809781248, free=15482871808, percent=22.5)

    :param part: The device to be requested.
    :returns: The generated fields and tags.
    """
    fields = {}
    tags = {}
    if os.name == 'nt':
        if 'cdrom' not in part.opts or part.fstype != '':
            # skip cd-rom drives with no disk in it; they may raise
            # ENOENT, pop-up a Windows GUI error for a non-ready
            # partition or just hang.
            usage = psutil.disk_usage(part.mountpoint)

            tags["disk_device"] = part.device
            fields["disk_total"] = bytes_to(usage.total)
            fields["disk_free"] = bytes_to(usage.free)
            fields["disk_used"] = bytes_to(usage.used)
            fields["disk_used_percent"] = int(usage.percent)
            fields["disk_type"] = part.fstype
            fields["disk_mount"] = part.mountpoint
    return fields, tags


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
    description: str = "This module collects metrics from the system it is running on in a defined interval."
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
        type: str = field(
            metadata=dict(description="Type of the metric you want to monitor (CPU, MEMORY, DISK).",
                          required=False,
                          validate=OneOf(['CPU', 'MEMORY', 'DISK'])),
            default="CPU")
        interval: float = field(
            metadata=dict(description="The request interval in seconds.",
                          required=False,
                          validate=Range(min=0, max=1000)),
            default=10)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        :returns: True if the import was successful.
        """
        try:
            global psutil
            import psutil
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "type": ['CPU', 'MEMORY', 'DISK']
        }

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.
        VariableModules normally start a subscription.

        :returns: True if successfully connected, otherwise false.
        """
        Thread(target=self._request_metrics,
               daemon=True,
               name="PSUTIL_Input_Module_{0}".format(self.configuration.id)).start()
        return True

    def _request_metrics(self):
        """
        Request the single metric functions to get the system information.
        """
        start_time = datetime.datetime.now()
        while self.active:
            try:
                if self.configuration.type == "MEMORY":
                    fields, tags = _get_memory()
                    self._data_change(models.Data(measurement=self.configuration.measurement,
                                                  fields=fields,
                                                  tags=tags))
                elif self.configuration.type == "CPU":
                    fields, tags = _get_cpu_percent()
                    self._data_change(models.Data(measurement=self.configuration.measurement,
                                                  fields=fields,
                                                  tags=tags))
                elif self.configuration.type == "DISK":
                    for part in psutil.disk_partitions(all=False):
                        fields, tags = _get_disk_usage(part)
                        if fields:
                            self._data_change(
                                models.Data(measurement=self.configuration.measurement,
                                            fields=fields,
                                            tags=tags))
                else:
                    # Should never be the case since we already validate at config level.
                    self.logger.critical("Unknown type '{0}'.".format(self.configuration.type))
                    break
            except Exception as e:
                self.logger.error("Something unexpected went wrong while requesting system metrics: {0}."
                                  .format(str(e)))
            # This should prevent shifting a little.
            required_time = datetime.datetime.now() - start_time
            if self.configuration.interval > float(required_time.seconds):
                time.sleep(self.configuration.interval - float(required_time.seconds))
            start_time = datetime.datetime.now()

    @send_data
    def _data_change(self, data: models.Data):
        """
        Is just called by the _data_change function.
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
    description: str = "This module collects metrics from the system it is running on if requested."
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
        type: str = field(
            metadata=dict(description="Type of the metric you want to monitor (CPU, MEMORY).",
                          required=False,
                          validate=OneOf(['CPU', 'MEMORY'])),
            default="CPU")

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        :returns: True if the import was successful.
        """
        try:
            global psutil
            import psutil
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    @staticmethod
    def get_config_data(input_module_instance=None) -> Dict[str, Any]:
        """
        Retrieve options for selected configuration parameters of this module.

        :param input_module_instance: If it is a variable or tag module, provide the input_module_instance
        if it is required for this module.
        :returns: A dictionary containing the parameter as key and a list of options as value.
        """
        return {
            "type": ['CPU', 'MEMORY']
        }

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        if self.configuration.type == "MEMORY":
            fields, tags = _get_memory()
        elif self.configuration.type == "CPU":
            fields, tags = _get_cpu_percent()
        else:
            raise Exception("Unknown type '{0}'.".format(self.configuration.type))
        return fields | tags
