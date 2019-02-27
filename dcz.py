"""
.. module:: dcz

**************************
Device Configuration Zones
**************************

This module define the :class:`DCZ` class to simplify the management of provisioned device resources.

In the lifecycle of an IoT device is of the utter importance to have a strategy for the management of firmware independent resources
such as certificates, private keys, configuration files, etc...
These resources must be written into the device memory when the device is mass programmed and they usually change when the devices is first provisioned 
(i.e. when the device needs to store WiFi credentials). The management of these resources must be as safe as possible both in terms
of robustness to error (i.e. corruption of memory) and security (i.e. credentials must always be stored at least in some encrypted fashion).

The Device Configuration Zones provided by Zerynth are regions of storage with the following properties:

    * versioning: each resource can be replicated in up to 8 versioned slots in order to make the firmware always able to revert to the previous configuration, or recover from memory corruption
    * encryption: an encryption mechanism is provided by the VM in order to store some sensitive data in an encryted way
    * error checking: each DCZ and each DCZ resource is augmented with a checksum to immediately spot corruption or tampering of data
    * serialization: resources included in a DCZ can be serialized and deserialized transparently with modules in the standard library (i.e. json and cbor) or by custom modules


The DCZ module works best when used with the Zerynth toolchain related commands, but can also be used standalone.

Device Confguration Zones are implemented as flash regions starting at specific addresses and containing:

    * a checksum of the entire zone
    * the size in bytes of the region
    * the version number of the region
    * the number of resources in the region
    * the number of DCZ regions (replication number)
    * a list of entries with the name, location, address and format of each provisioned resource

Up to 8 DCZ can be handled by this module. DCZs are stored like these: ::

       
     |    DCZ 0 @ 0x310000       |            |    DCZ 1 @ 0x311000       |
     -----------------------------            -----------------------------
     | Checksum     : 0xABCD1234 |            | Checksum     : 0xABCD1234 |
     | Size         : 80         |            | Size         : 80         |
     | Version      : 0          |            | Version      : 0          |
     | Resources    : 1          |            | Resources    : 1          |
     | Replication  : 2          |            | Replication  : 2          |
     | --------------------------|            | --------------------------|
     | Entry        : 0          |            | Entry        : 0          |
     | Name         : cert       |            | Name         : cert       |
     | Address      : 0x320000   |            | Address      : 0x330000   |
     | checksum     : 0x2345BCDE |            | checksum     : 0x2345BCDE |
     | format       : bin        |            | format       : bin        |
     | size         : 1024       |            | size         : 1024       |
     | --------------------------|            | --------------------------|

The above configuration has a replication factor of 2 (all resources are replicated twice), both the DCZs have
the same version and contain an entry to a resource named "cert" (most probably a certificate). The certificate
managed by DCZ 0 can be found at address 0x320000 while the certificate copy managed by DCZ 1 can be found at 0x330000.

If during the lifecyle of the device the certificate must be changed or renewed, the new version of the resource can be saved
increasing its version number, reaching a state like this: ::

     |    DCZ 0 @ 0x310000       |            |    DCZ 1 @ 0x311000       |
     -----------------------------            -----------------------------
     | Checksum     : 0xABCD1234 |            | Checksum     : 0xFFFF0000 |
     | Size         : 80         |            | Size         : 80         |
     | Version      : 0          |            | Version      : 1          |
     | Resources    : 1          |            | Resources    : 1          |
     | Replication  : 2          |            | Replication  : 2          |
     | --------------------------|  =======>  | --------------------------|
     | Entry        : 0          |            | Entry        : 0          |
     | Name         : cert       |            | Name         : cert       |
     | Address      : 0x320000   |            | Address      : 0x330000   |
     | checksum     : 0x2345BCDE |            | checksum     : 0xAAAABBBB |
     | format       : bin        |            | format       : bin        |
     | size         : 1024       |            | size         : 1120       |
     | --------------------------|            | --------------------------|


The DCZs now store two different resources named "cert" but with different version number, size and checksum.
If something goes wrong during certificate renewal, the device can always go back to the previous version of the DCZ
and try again.

Increasing versions of resources are stored modulo the replication factor. In the case above, all odd numbered versions
will be handled by DCZ 1 while even numbered versions will be handled by DCZ 0.

At provisioning time, resources can be tagged as encrypted in the DCZ entries. Such resources are stored as a plaintext and are
automatically encrypted by the VM the first time the DCZ module is initialized (usually at end of line testing). This is
not the best possible security measure, but is a good alternative with respect to storing resources in the clear when a 
suitable secure storage hardware is not present.


DCZ module makes no assumption on the flash layout of the device, therefore when deciding addresses for DCZs and resources
the following criteria should be taken into consideration:

    * choose addresses that are not in VM or bytecode areas
    * choose addresses in such a way to accomodate the size of the resources in a non overlapping way (the size of a DCZ is 16 bytes plus 64 for each indexed resource)
    * flash memories are often segmented in sectors that must be completely erased before writing to them. Organize resource and DCZs addresses in such a way that they do not share the same sector! Failing to do so will delete resources or DCZs when modifying the ones sharing the sector. The sector size may vary, consult the device flash layout map to choose correctly


    """




@native_c("_dcz_decode_header",[
    "csrc/dcz.c"
    ],
    [],
    [])
def _decode_header(hbuf):
    pass

@native_c("_dcz_decode_entry",[
    "csrc/dcz.c"
    ],
    [],
    [])
def _decode_entry(hbuf):
    pass

@native_c("_dcz_encode_header",[
    "csrc/dcz.c"
    ],
    [],
    [])
def _encode_header(hbuf,sz,version,entries):
    pass

@native_c("_dcz_encode_entry",[
    "csrc/dcz.c"
    ],
    [],
    [])
def _encode_entry(hbuf,index,entry):
    pass

@native_c("_dcz_fletcher32",[
    "csrc/dcz.c"
    ],
    [],
    [])
def fletcher32(buf):
    pass


HEADER_SIZE = 16
ENTRY_SIZE = 64

new_exception(DCZChecksumError,Exception)
new_exception(DCZNoResourceError,Exception)
new_exception(DCZMissingSerializerError,Exception)

class DCZ():
    """
=========
DCZ class
=========
    
.. class:: DCZ(mapping, serializers={})

    Create an instance of the DCZ class providing the following arguments:

    * :samp:`mapping`, a list of addresses where the various DCZ versions start (in ascending order of version). A max of 8 addresses can be given.
    * :samp:`serializers`, a dict mapping format names to serialization/deserialization modules.

    Format names are strings of at most 4 bytes, while serialization modules must provide a :samp:`.loads(bytes)` and :samp:`.dumps(obj)` to be used.

    To use json and cbor: ::

        import json
        import cbor
        from dcz import dcz

        dc = dcz.DCZ([0x310000,0x311000],{"json":json,"cbor":cbor})
   
    After creation, the DCZ instance contain a :samp:`latest_version` field containing the highest available version of the stored DCZs.

.. note:: All methods expecting an optional version number will operate the :samp:`latest_version` if no version is given,
    otherwise they will operate on the DCZ slot correspondent to the given version modulo the replication number.

    """
    def __init__(self,mapping,serializers={}):
        self.addr = mapping
        self.modulo = len(mapping)
        self.deserializers = serializers
        self.latest_version = 0
        self.init()

    def init(self):
        # retrieve both headers
        self.dcz_size = []
        self.dcz_chksum = []
        self.dcz_version = []
        self.dcz_entries = []
        self.dcz_valid = [False]*self.modulo
        v=-1
        vp=-1
        cardinality=0
        for i in range(self.modulo):
            size0, version0, entries0, chksum0, cardinality = self.get_header(i)
            self.dcz_size.append(size0)
            self.dcz_chksum.append(chksum0)
            self.dcz_version.append(version0)
            self.dcz_entries.append(entries0)
            self.dcz_valid[i]=self.check_dcz(i)
            if version0>v:
                v = version0
                vp = i
        self.latest_version = v
        self.cardinality = cardinality

    def finalize(self):
        """
.. method:: finalize()

    This method scans all the DCZs and all the resources. For each DCZ it calculates the checksum and checks it against
    the one in the DCZ. If they do not match the DCZ is marked as invalid. For each resource of valid DCZs that is marked
    as requiring encryption, the resource is read (in binary format), encrypted, stored back to its address and marked as encrypted.

    This method is suggested to be run at end of line testing for each device that requires encrypted resources.

        """
        # finalize all tables
        for i in range(self.modulo):
            entries = self.dcz_entries[i]
            if not self.check_dcz(i):
                # skip broken dcz
                self.dcz_valid[i]=False
                continue
            self.dcz_valid[i]=True
            for j in range(entries):
                entry = self.get_entry(j,i)  # entry j for table i
                if entry[5] and not entry[6]: #requires encryption but is not encrypted!
                    resource_addr = entry[1][i]
                    bin = self.get_zone(resource_addr,entry[2]) #read resource
                    chk = entry[4]
                    #encrypt
                    __vmctrl(3,0,chk,bin)
                    entry[5]=1
                    entry[6]=1
                    self.save_entry(entry,bin)


    def handle_version(self,version,default):
        if version is None:
            version = default
        return version%self.modulo


    def load_resource(self,resource,version=None,check=False,deserialize=True,decrypt=True):
        """
.. method:: load_resource(resource,version=None,check=False,deserialize=True,decrypt=True)

    This is the method of choice to retrieve resources.
    It scans the DCZ identified by :samp:`version` and all its entries to find the one with the same name
    specified by the parameter :samp:`resource`.
    If the :samp:`check` parameter is :samp:`True`, the :samp:`DCZChecksumError` is raised if the entry checksum in the DCZ
    is not the same as the calculated checksum of the resource data.

    When :samp:`deserialize` is :samp:`True` an attempt to deserialize the resource data is made by passing it
    to the :samp:`.loads` method of the appropriate deserializer. The deserializer module is choosen by matching
    the resource format with the key of the :samp:`dcz.serializers`. If no deserializers can be found, :samp:`DCZMissingSerializerError`
    is raised. If deserialization is successful, the deserialized resource is returned.
    When :samp:`deserialize` is :samp:`False`, the binary representation of the resource is returned.

    If no resource with name :samp:`resource` can be found, :samp:`DCZNoResourceError` is raised.
 
        """
        version = self.handle_version(version,self.latest_version)
        for i in range(self.dcz_entries[version]):
            entry = self.get_entry(i,version)
            if entry[0]==resource:
                # let's get binary data
                fmt = entry[3]
                chk = entry[4]
                enc = entry[5]
                is_enc = entry[6]
                buf = self.load_entry(entry)
                # let's decrypt
                if enc and is_enc:
                    __vmctrl(4,0,chk,buf)
                # let's calculate checksum
                if check:
                    chksum = fletcher32(buf)
                    if chk!=chksum:
                        # ouch, corruption!
                        raise DCZChecksumError
                if not deserialize:
                    if enc and is_enc and not decrypt:
                        #encrypt back
                        __vmctrl(3,0,chk,buf)
                    return buf
                else:
                    # let's deserialize
                    if fmt=="bin":
                        return buf
                    else:
                        if fmt not in self.deserializers:
                            # ouch, no deserializer given
                            raise DCZMissingSerializerError
                        dds = self.deserializers[fmt]
                        return dds.loads(buf)
        else:
            raise DCZNoResourceError


    def save_resource(self,resource,data,version=None,format="bin",serialize=True):
        """
.. method:: save_resource(resource,version=None,format="bin",serialize=True)

    This is method is used to update resources.

    It scans the DCZ identified by :samp:`version` and all its entries to find the one with the same name
    specified by the parameter :samp:`resource`. If :samp:`version` is not present, the DCZ matching the modulo operation with the replication
    number is selected and promoted to the new version.

    When :samp:`serialize` is :samp:`True` an attempt to serialize the resource data is made by passing it
    to the :samp:`.dumps` method of the appropriate serializer. The serializer module is choosen by matching
    the :samp:`format` with the key of the :samp:`dcz.serializers`. If no serializers can be found, :samp:`DCZMissingSerializerError`
    is raised. If serialization is successful, the serialized resource is saved and the DCZ updated accordingly.
    When a resource is marked for encryption, the resource is automatically encrypted and stored.

    If no resource with name :samp:`resource` can be found, :samp:`DCZNoResourceError` is raised.

    Return a tuple with the resource address and the DCZ address
 
        """
        new_version = None
        if version is not None:
            new_version = version
        version = self.handle_version(version,self.latest_version)
        if new_version is None:
            new_version = self.dcz_version[version]
        index = -1
        if len(format)>4:
            raise ValueError
        if len(resource)>16:
            raise ValueError
        if serialize:
            if format=="bin":
                bin = bytearray(data)
            elif format not in self.deserializers:
                raise DCZMissingSerializerError
            else:
                ss = self.deserializers[format]
                bin = ss.dumps(data)
        else:
            bin=data
    
        chksum = fletcher32(bin)

        for i in range(self.dcz_entries[version]):
            entry = self.get_entry(i,version)
            if entry[0]==resource:
                # found!
                index = i
                entry[2]=len(bin)
                entry[3]=format
                entry[4]=chksum
                break
        else:
            raise DCZNoResourceError

        if entry[5]:
            #encrypt
            __vmctrl(3,0,chksum,bin)
            entry[6]=1
        return self.save_entry(entry,bin,new_version)

    def get_header(self,version=None):
        """
.. method:: get_header(version=None)

        Return a list containing the DCZ header:

            * size
            * version
            * number of indexed resources
            * checksum
            * replication number

        """
        version = self.handle_version(version,self.latest_version)
        addr = self.addr[version]
        hbuf = self.get_zone(addr,HEADER_SIZE)
        return _decode_header(hbuf)

    def get_entry(self,i,version=None):
        """
.. method:: get_entry(i,version=None)

        Return the *ith* entry in the DCZ indentified by :samp:`version`

        An entry is a list with:

            * the name of the resource
            * the list of all possible addresses of the resource
            * the size of the resource
            * the format of the resource
            * the checksum of the resource
            * a flag to 1 if encryption is required
            * a flag to 1 if encryption has been performed
            * the index of the entry in the DCZ
            * the index of the DCZ

        
        """
        version = self.handle_version(version,self.latest_version)
        addr = self.addr[version]
        addr= addr+HEADER_SIZE+ENTRY_SIZE*i
        hbuf = self.get_zone(addr,ENTRY_SIZE)
        ee = _decode_entry(hbuf)
        ee.append(i)
        ee.append(version)
        return ee

    def load_entry(self,entry):
        """
.. method:: load_entry(entry)
    
    Return the raw binary data of the resource in :samp:`entry` as present on the flash (without decryption). An :samp:`entry` retrieved with :method:`get_entry` must be given in order to identify the resource.

    This method is exposed for custom usage of DCZ, but :method:`load_resource` is recommended.

        """
        version = entry[-1]
        resource_addr = entry[1][version]
        sz = entry[2]
        return self.get_zone(resource_addr,sz)


    def save_entry(self,entry,bin,new_version=None):
        """
.. method:: save_entry(entry,bin,new_version=None)
    
    Save data in :samp:`bin` as is (no encryption step) to the resource pointed by :samp:`entry` and update the corresponding DCZ. If :samp:`new_version` is given
    the corresponding DCZ will be updated and its version number set to :samp:`new_version`. If not given, the corresponding DCZ will be the one identified
    by :samp:`entry`.

    Return the saved resource address and the address of the modified DCZ

        """
        version = entry[-1]
        index = entry[-2]
        if new_version is None:
            new_version=version
            version = self.handle_version(version,version)
        else:
            version = self.handle_version(new_version,version)
        resource_addr = entry[1][version]
        self.set_zone(resource_addr,bin)
        # free some mem
        bin=None
        # load dcz
        addr = self.addr[version]
        dczbin,chksum = self.get_dcz(version)
        pos = addr+HEADER_SIZE+index*ENTRY_SIZE
        # modify dcz
        _encode_entry(dczbin,index,entry)
        _encode_header(dczbin,len(dczbin),new_version,self.dcz_entries[version])
        # save dcz
        self.set_zone(addr,dczbin)
        # reload dcz
        size0, version0, entries0, chksum0, cardinality = self.get_header(version)
        self.dcz_size[version]=size0
        self.dcz_version[version]=version0
        self.dcz_chksum[version]=chksum0
        self.dcz_entries[version]=entries0
        if new_version>self.latest_version:
            self.latest_version=new_version
        return resource_addr, addr

    def search_entry(self,resource,version=None):
        """
.. method:: search_entry(resource,version=None)
    
    Search for a resource named :samp:`resource` in all DCZ and return a tuple with:

    * resource address
    * resource size
    * resource format
    * resource checksum
    * encryption status

    If no resource exists, :samp:`DCZNoResourceError` is raised
    

        """
        version = self.handle_version(version,self.latest_version)
        for i in range(self.dcz_entries[version]):
            entry = self.get_entry(i,version)
            if entry[0]==resource:
                return entry[1][version],entry[2],entry[3],entry[4],entry[6]
        else:
            raise DCZNoResourceError

    def get_dcz(self,version=None):
        version = self.handle_version(version,self.latest_version)
        addr = self.addr[version]
        sz = HEADER_SIZE+self.dcz_entries[version]*ENTRY_SIZE
        dczbin = self.get_zone(addr,sz)
        chksum = fletcher32(dczbin[4:])
        return dczbin, chksum

    def check_dcz(self,version=None):
        """
.. method:: check_dcz(version=None)

    Return True if the DCZ identified by :samp:`version` is valid. It reads the DCZ from memory, calculates the checksum and check it against the stored one.
        """
        version = self.handle_version(version,self.latest_version)
        dczbin, chksum = self.get_dcz(version)
        size0, version0, entries0, chksum0, cardinality = self.get_header(version)
        return chksum0==chksum

    def is_valid_dcz(self,version=None):
        """
.. method:: is_valid_dcz(version=None)

    Return True if the DCZ identified by :samp:`version` is valid. It looks up validity from the checks done after init.
        """
        version = self.handle_version(version,self.latest_version)
        return self.dcz_valid[version]

    def get_zone(self,addr,size,buf=None):
        if buf is None:
            buf=bytearray(size)
        zonebin = __read_flash(addr,size,buf)
        return zonebin

    def set_zone(self,addr,data):
        __write_flash(addr,data)

    def dump(self,version=None,entries=False):
        """
.. method:: dump(version=None,entries=False)

    Print information about DCZs. If :samp:`version` is not given, all DCZs are printed, otherwise only the specific :samp:`version`.
    If :samp:`entries` is given, additional information about each entry is given.

        """
        ll = self.latest_version%self.modulo
        if version is not None:
            vi=version%self.modulo
            ve=vi+1
        else:
            version = self.handle_version(version,self.latest_version)
            vi=0
            ve=self.modulo
        for v in range(vi,ve):
            print("DCZ",v,"@",hex(self.addr[v]))
            print("==========")
            print("| Version:  ",self.dcz_version[v])
            print("| Entries:  ",self.dcz_entries[v])
            print("| Size:     ",self.dcz_size[v])
            print("| Checksum: ",hex(self.dcz_chksum[v]))
            print("| Valid:    ",self.dcz_valid[v])
            print("| Zones:    ",self.cardinality)
            print("| Current:  ",str(ll==v))
            if not self.dcz_valid[v] or not entries:
                continue
            for j in range(self.dcz_entries[v]):
                entry = self.get_entry(j,v)
                print("|")
                print("|----> Entry:     ",j)
                print("|      Resource:  ",entry[0])
                print("|      Address:   ",hex(entry[1][v]))
                print("|      Size:      ",entry[2])
                print("|      Format:    ",entry[3])
                print("|      Checksum:  ",hex(entry[4]))
                print("|      Encryption:",entry[5])
                print("|      Encrypted: ",entry[6])
            print("----------")

    def versions(self):
        """
.. method:: versions()

        Return the list of DCZ versions

        """
        return self.dcz_version

    def resources(self):
        """
.. method:: resources()

        Return the list of resource names

        """
        res = [None]*self.dcz_entries[0]
        for i in range(self.dcz_entries[0]):
            entry = self.get_entry(i,0)
            res[i]=entry[0]
        return res


    def next_version(self):
        """
.. method:: next_version()

        Return the next version greater than all current versions

        """
        return self.latest_version+1

