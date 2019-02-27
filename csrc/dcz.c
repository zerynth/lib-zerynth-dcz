// #define ZERYNTH_PRINTF 1
#include "zerynth.h"


//DCZ header is structured as a 4 uint32_t fields
// - size: in bytes, length of dcz table
// - version: increasing number of update
// - entries: number of resources in dcz
// - fletcher: a fletcher checksum
// - cardinality: the number of dczones (fixed at provisioning)
typedef struct _dcz_header{
    uint32_t chksum;
    uint32_t size;
    uint32_t version;
    uint16_t entries;
    uint16_t cardinality;
} DCZHeader;

typedef struct _dcz_entry {
    uint8_t tag[16];        //Entry name: max 16 bytes, the unused bytes are all zeroed
    uint32_t addr[8];       //Addresses for multiple zones
    uint32_t size;          //Size of data for the current zone
    uint8_t format[4];      //Format of data, non zero terminated: "bin","str","cbor","json", "custom"
    uint32_t chksum;        //checksum of the resource
    uint8_t encrypted;     //request for encryption
    uint16_t is_encrypted;  //flag for actual encryption
} DCZEntry;

uint32_t _fletcher32(uint8_t *buf, uint32_t len){
    uint16_t sum1 = 0;
    uint16_t sum2 = 0;
    uint16_t e=0;
    int i,sz;
    sz=len;
    if(len%2!=0) sz = len-1;  //account for odd bytes len

    for(i=0;i<sz;i+=2){
        e = buf[i]|(buf[i+1]<<8);
        sum1 = (sum1+e)%0xffff;
        sum2 = (sum1+sum2)%0xffff;
        // printf("%i] %i %i e %x sum1 %x sum2 %x\n",i,buf[i],buf[i+1],e,sum1,sum2);
    }

    if(sz!=len) {
        //add last byte
        sum1 = (sum1 + buf[sz])%0xffff;
        sum2 = (sum1+sum2)%0xffff;
        // printf("%i] e %x sum1 %x sum2 %x\n",i,buf[sz],sum1,sum2);
    }
    return (sum2<<16)|sum1;
}

C_NATIVE(_dcz_decode_header)
{
    NATIVE_UNWARN();
    uint8_t *buf;
    uint32_t len;
    *res = MAKE_NONE();
    if (parse_py_args("s", nargs, args, &buf, &len) != 1) {
        return ERR_TYPE_EXC;
    }

    DCZHeader dch;
    memcpy(&dch,buf,sizeof(DCZHeader));

    PList *tpl = plist_new(5,NULL);
    PLIST_SET_ITEM(tpl,0,pinteger_new(dch.size));
    PLIST_SET_ITEM(tpl,1,pinteger_new(dch.version));
    PLIST_SET_ITEM(tpl,2,pinteger_new(dch.entries));
    PLIST_SET_ITEM(tpl,3,pinteger_new(dch.chksum));
    PLIST_SET_ITEM(tpl,4,pinteger_new(dch.cardinality));

    *res = tpl;
    return ERR_OK;
}
C_NATIVE(_dcz_encode_header)
{
    NATIVE_UNWARN();
    uint8_t *buf;
    uint32_t len;
    uint32_t sz,version,entries;
    *res = MAKE_NONE();
    if (parse_py_args("siii", nargs, args, &buf, &len,&sz,&version,&entries) != 4) {
        return ERR_TYPE_EXC;
    }

    DCZHeader dch={0};
    memcpy(&dch,buf,sizeof(DCZHeader));  //fill dch, this way we fill cardinality with correct value
    dch.size=sz;
    dch.version=version;
    dch.entries=entries;
    memcpy(buf,&dch,sizeof(DCZHeader));
    //calc checksum
    dch.chksum = _fletcher32(buf+4,len-4);
    memcpy(buf,&dch,sizeof(DCZHeader));

    *res = args[0];
    return ERR_OK;
}

C_NATIVE(_dcz_decode_entry)
{
    NATIVE_UNWARN();
    uint8_t *buf;
    uint32_t len;
    int i,sz=0;
    *res = MAKE_NONE();
    if (parse_py_args("s", nargs, args, &buf, &len) != 1) {
        return ERR_TYPE_EXC;
    }

    DCZEntry dce;
    memcpy(&dce,buf,sizeof(DCZEntry));

    PList *tpl = plist_new(7,NULL);
    for(i=0;i<16;i++){
        if(dce.tag[i]==0) break;
        sz++;
    }
    PList *addrs = plist_new(8,NULL);
    for(i=0;i<8;i++){
        PLIST_SET_ITEM(addrs,i,pinteger_new(dce.addr[i]));
    }
    PLIST_SET_ITEM(tpl,0,pstring_new(sz,dce.tag));
    PLIST_SET_ITEM(tpl,1,addrs);
    PLIST_SET_ITEM(tpl,2,pinteger_new(dce.size));
    sz=0;
    for(i=0;i<4;i++){
        if(dce.format[i]==0) break;
        sz++;
    }
    PLIST_SET_ITEM(tpl,3,pstring_new(sz,dce.format));
    PLIST_SET_ITEM(tpl,4,pinteger_new(dce.chksum));
    PLIST_SET_ITEM(tpl,5,pinteger_new(dce.encrypted));
    PLIST_SET_ITEM(tpl,6,pinteger_new(dce.is_encrypted));

    *res = tpl;
    return ERR_OK;
}

C_NATIVE(_dcz_encode_entry)
{
    NATIVE_UNWARN();
    uint8_t *buf;
    uint32_t len;
    uint32_t index,dummy,pos;
    int i,sz=0;
    *res = MAKE_NONE();
    if (parse_py_args("si", nargs-1, args, &buf, &len,&index) != 2) {
        return ERR_TYPE_EXC;
    }
    PObject *o = args[2];
    // printf("type %i %i\n",PTYPE(o),PSEQUENCE_ELEMENTS(o));
    if (PTYPE(o)!=PLIST || PSEQUENCE_ELEMENTS(o)<7) return ERR_TYPE_EXC;



    DCZEntry dce={0};
    pos = sizeof(DCZHeader)+index*sizeof(DCZEntry);
    //fill dce
    memcpy(&dce,buf+pos,sizeof(DCZEntry));

    //modify dce
    PString *rname = PLIST_ITEM(o,0);
    memcpy(dce.tag,PSEQUENCE_BYTES(rname),PSEQUENCE_ELEMENTS(rname));
    PList* addrs = PLIST_ITEM(o,1);
    for(i=0;i<8;i++){
        dummy = INTEGER_VALUE(PLIST_ITEM(addrs,i));
        dce.addr[i]=dummy;
    }
    dummy = INTEGER_VALUE(PLIST_ITEM(o,2));
    dce.size=dummy;
    dummy = INTEGER_VALUE(PLIST_ITEM(o,4));
    dce.chksum=dummy;
    rname = PLIST_ITEM(o,3);
    memcpy(dce.format,PSEQUENCE_BYTES(rname),PSEQUENCE_ELEMENTS(rname));
    dummy = INTEGER_VALUE(PLIST_ITEM(o,6));  //is_encrypted
    if (dce.encrypted && dummy) dce.is_encrypted=1;

    //write dce
    memcpy(buf+pos,&dce,sizeof(DCZEntry));

    *res = args[0];
    return ERR_OK;
}


C_NATIVE(_dcz_fletcher32)
{
    NATIVE_UNWARN();
    uint8_t *buf;
    uint32_t len;
    uint32_t result;
    *res = MAKE_NONE();
    if (parse_py_args("s", nargs, args, &buf, &len) != 1) {
        return ERR_TYPE_EXC;
    }
    // printf("res %x\n",result);
    result = _fletcher32(buf,len);

    *res = pinteger_new(result);
    return ERR_OK;
}

