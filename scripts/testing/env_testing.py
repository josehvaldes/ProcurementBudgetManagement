import uuid
import requests
import time
import json
import sys
import argparse

from shared.config.settings import get_settings
settings = get_settings()

print("{settings.service_bus_host_name=}", settings.service_bus_host_name)
print("{settings.service_bus_topic_name=}", settings.service_bus_topic_name)


