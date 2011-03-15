#!/usr/bin/env python

import logging
import sys
from kokki import *

logging.basicConfig(level=logging.DEBUG if len(sys.argv) > 1 and sys.argv[1] == "-v" else logging.INFO)

with Environment() as env:
    Execute("saywoo",
        command = "echo WOOOooooooooooOOOOOOOOOOOoooooooo",
        action = "nothing")

    File("/tmp/foo",
        mode = 0600,
        content = "bar\n",
        notifies = [("run", env.resources["Execute"]["saywoo"], True)])

    env.run()
