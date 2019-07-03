#!/usr/bin/env python3

import logging
import coloredlogs
import time
logging.basicConfig(filename='output.log',
                    filemode='w',
                    format = '%(asctime)s - %(message)s')


logger = logging.getLogger(__name__)

coloredlogs.install(level='DEBUG')


