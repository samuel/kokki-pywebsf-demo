#!/usr/bin/env python

import logging
import sys
from kokki import *

logging.basicConfig(level=logging.DEBUG if len(sys.argv) > 1 and sys.argv[1] == "-v" else logging.INFO)

with Kitchen() as kit:
    kit.add_cookbook_path("cookbooks")
    kit.update_config({
        "foo.content": "Hello",
    })
    kit.include_recipe("twitbook.foo")
    kit.run()
