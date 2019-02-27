################################################################################
# Device Configuration Zones
#
# Created by Zerynth Team 2015 CC
# Authors: D. Mazzei, G. Baldi,
###############################################################################

import streams
import json
# import the DCZ module
from dcz import dcz

streams.serial()

try:

    # this example can run on an ESP32 device without modification
    # otherwise change the addresses both in mapping and in dcz.yml

    # there will be 2 DCZs at the following addresses
    mapping =  [0x310000,0x311000]
    # let's create a DCZ instance that knows how to serialize and deserialize json
    dc = dcz.DCZ(mapping, serializers={"json":json})
    # before using it, DCZ instance must be init'ed
    dc.init()
    # if it is the first time the device runs, let's call finalize to encrypt resources if needed
    dc.finalize()

    # ok, print out the status
    dc.dump(entries=True)

    # get the list of resource names
    resources = dc.resources()

    # load them all and print their values
    for name in resources:
        print("Resource",name)
        resource = dc.load_resource(name,check=True)  # the result is a Python object!
        binary_resource = dc.load_resource(name,check=True,deserialize=False)
        binary_resource_encrypted = dc.load_resource(name,check=True,deserialize=False,decrypt=False)
        print("Deserialized:",resource)
        print("Binary:      ","".join([hex(x,"") for x in binary_resource]))
        print("Encrypted:   ","".join([hex(x,"") for x in binary_resource_encrypted]))

    # get the next version
    next_version = dc.next_version()
    # now update a resource
    print("=======================")
    print("Updating DCZ to version",next_version)
    print("=======================")

    if "test" not in resource:
      resource["test"]=0
    resource["test"]=resource["test"]+1

    print("Saving ",name)
    dc.save_resource(name,resource,format="json",version=next_version)

    print("Yes! Reset the device and see the DCZ get updated again and again...")
    while(True):
        sleep(1000)

except Exception as e:
    print(e)
