#!/usr/bin/python3

# use ble-serial to expose the BT UART:
# ble-serial  -vvv -d 2B:80:03:B4:76:0A -r 6e400001-b5a3-f393-e0a9-e50e24dcca9e -w 6e400002-b5a3-f393-e0a9-e50e24dcca9e

"""
tx frame:
=========

<0x7a> <0? *1> <length *2> <address *3> <cmd hi> <cmd lo> [<payload>] <crc hi> <crc lo> <0xa7>

*1 = probably hi byte of length - always 0 in app
*2 = length of entire frame - 4 bytes (start and end sentinels and crc)
*3 = address. starts at 0, updated by calling command 0x0301

Command is a 16 bit number.

0x0001 - read data 1 - no payload
0x0002 - read data 2 - no payload
0x0003 - read data 3 - no payload
0x0301 - set address- 1 byte payload = new address
0x0302 - set *string part 1 - 10 byte payload
0x0303 - set *string part 2 - 10 byte payload

*string = called from changeName function, so probably name...
converter to gb18030 charset, 0 padded to 20 bytes, first 10 bytes sent in 0x0302, remainder with 0x0303

rx_frame:
=========

<0xa7> <0? *1> <length *2> <address *3> <cmd hi> <cmd lo> [<payload>] <crc hi> <crc lo> <0x7a>

*1, *2, *3 - all skipped by app parser, but I asume them to be the same as the tx_frame
    so far in all tests *2 has been the length

crc is also skipped by the app, but so far it has always tested correct too

cmd is the same command as this is a response to

payload is described by example in the decode functions below

so far, the following payload types have been used.

8 bit integer, one byte, only seen unsigned use
16 bit integer, hi byte first, unsigned (with offset as described in payload decode for negative values)
* cell voltages sometimes have a bogus high bit - no idea why, and i can not figure out how the app filters it...
fixed length strings (always 0 padded, but no confirmation if always 0 terminated!)


Bitfields (untested decode from source)

All bitfields are handled lsb..msb
Alerts are 2 bit fields:
00 = none
01 = minor
10 = medium
11 = severe

bmsFault1 (bits, lsb.. msb):
ShortCircuit
?
MCBDisconnection
CellVoltageistoolow
Thevoltagesamplingcableisdisconnected
?
?
AFEFault

bmsFault2 (bits, lsb.. msb):
NTCDisconnection
ADCFault
CellFault
?
?
?
?
?

bmsAlert1 (2bit pairs, lsb..msb):
CellOV
CellUV
PackOV
PackUV

bmsAlert2 (2bit pairs, lsb..msb):
ChargingOC
DischargingOC
ChargingOT
ChargingUT

bmsAlert3 (2bit pairs, lsb..msb):
DischargingOT
DischargingUT
AmbientOT
AmbientUT

bmsAlert4 (2bit pairs, lsb..msb):
PCBOT
PCBUT
LowSOC
ExcessiveVoltagegapAlarm

bmsStatus (bits, lsb.. msb):
charge 1=closure 0=disconnect
discharge 1=closure 0=disconnect
(next two bits as an integer) type 0 = idle, 1 = Charging, 2 = Discharging, 3 = Feedback

"""



from dumper import dump
cfg_tty = '/dev/pts/2'

# from CRC16 in app
def crc16(data : bytearray, offset , length):
    if data is None or offset < 0 or offset > len(data)- 1 and offset+length > len(data):
        return 0
    crc = 0xFFFF
    for i in range(0, length):
        #print("%02x %d" % (data[offset + i], crc))
        crc ^= data[offset + i]
        for j in range(0,8):
            if (crc & 1) > 0:
                crc = (crc >> 1) ^ 40961
            else:
                crc = crc >> 1
    return crc & 0xFFFF

# manual test crc
#t = [0, 5, 0, 0, 1]
#c = crc16(t, 0, 5)
#print("%d %d" % (c >> 8, c & 0xff))
# 12, 229

# I am too lazy to do this properly - just use a global buffer and offset
rb = bytearray()
rbo = 0

# read byte
def get8():
    global rb, rbo
    if rbo >= len(rb):
        print("READ BEYOND END OF BUFFER!")
        return undef
    i = rb[rbo]
    rbo = rbo + 1
    return i

def get16():
    i = get8()
    i *= 256
    i += get8()
    return i

def do0001():
    # 0 - onlineStatus
    i = get8();
    print("onlineStatus %d" % i)
    # 1 - batteriesSeriesNumber
    i = get8();
    print("batteriesSeriesNumber %d" % i)
    for j in range(0, i):
        # 2, 3 - cellVoltage (mV)
        k = get16()
        k = k & 0x7fff # i have no idea where/how this is being filtered in their app - but this gives the correct number
        print("cellVoltage (mV) %d" % k)
    # 4 - maxCellNumber
    i = get8();
    print("maxCellNumber %d" % i)
    # 5,6 - maxCellVoltage
    i = get16();
    print("maxCellVoltage %d" % i)
    # 7 - minCellNumber
    i = get8();
    print("minCellNumber %d" % i)
    # 8,9 - minCellVoltage
    i = get16();
    print("minCellVoltage %d" % i)
    # 10,11 - totalCurrent ( x / 100 - 300 )
    i = get16();
    print("totalCurrent %f (%d)" % ((i / 100.0) - 300.0, i))
    # 12, 13 - soc (x / 100)
    i = get16();
    print("soc %f (%d)" % ((i / 100.0), i))
    # 14, 15 - soh (x / 100)
    i = get16();
    print("soh %f (%d)" % ((i / 100.0), i))
    # 16, 17 - actualCapacity (x / 100)
    i = get16();
    print("actualCapacity %f (%d)" % ((i / 100.0), i))
    # 18, 19 - surplusCapacity (x / 100)
    i = get16();
    print("surplusCapacity %f (%d)" % ((i / 100.0), i))
    # 20, 21 - nominalCapacity (x / 100)
    i = get16();
    print("nominalCapacity %f (%d)" % ((i / 100.0), i))
    # 22 - batteriesTemperatureNumber
    i = get8();
    print("batteriesTemperatureNumber %d" % i)
    for j in range(0, i):
        # 23, 24 - cellTemperature (x - 50)
        k = get16()
        k = k & 0x7fff # i have no idea where/how this is being filtered in their app - but this gives the correct number
        print("cellTemperature %d" % (k - 50))
    # 25, 26 - environmentalTemperature
    i = get16();
    print("environmentalTemperature %d" % (i - 50))
    # 25, 26 -pcbTemperature
    i = get16();
    print("pcbTemperature %d" % (i - 50))
    # 27 - maxTemperatureCellNumber
    i = get8();
    print("maxTemperatureCellNumber %d" % i)
    # 28 - maxTemperatureCellValue
    i = get8();
    i = i & 0x7fff
    print("maxTemperatureCellValue %d" % (i - 50))
    # 29 - minTemperatureCellNumber
    i = get8();
    print("minTemperatureCellNumber %d" % i)
    # 30 - minTemperatureCellValue
    i = get8();
    print("minTemperatureCellValue %d" % (i - 50))
    # 31 bmsFault1
    i = get8();
    print("bmsFault1 %d" % i)
    # 32 bmsFault2
    i = get8();
    print("bmsFault2 %d" % i)
    # 33 bmsAlert1
    i = get8();
    print("bmsAlert1 %d" % i)
    # 34 bmsAlert2
    i = get8();
    print("bmsAlert2 %d" % i)
    # 35 bmsAlert3
    i = get8();
    print("bmsAlert3 %d" % i)
    # 36 bmsAlert4
    i = get8();
    print("bmsAlert4 %d" % i)
    # 37, 38 u.cycleIndex
    i = get16();
    print("u.cycleIndex %d" % i)
    # 39, 40 totalVoltage ( x / 100)
    i = get16();
    print("u.totalVoltage %f" % (i / 100.0))
    # 41 bmsStatus
    i = get8();
    print("bmsStatus %d" % i)
    # 42, 43 - totalChargingCapacity
    i = get16();
    print("totalChargingCapacity %d" % i)
    # 44, 45 - totalDischargeCapacity
    i = get16();
    print("totalDischargeCapacity %d" % i)
    # 46, 47 - totalRechargeTime
    i = get16();
    print("totalRechargeTime %d" % i)
    # 48, 49 - totaldischargeTime
    i = get16();
    print("totaldischargeTime %d" % i)
    # 50 - batteryType
    i = get8()
    print("batteryType %d" % i)
    print("END %d %d" % (rbo, len(rb)))

def do0002():
    global rb
    global rbo
    # 0 .. 23 = software
    s = rb[rbo:rbo+24]
    print("software '%s'" % (str(s)))
    rbo = rbo + 24
    # 24 .. 47 = hardware
    s = rb[rbo:rbo+24]
    print("hardware '%s'" % (str(s)))
    rbo = rbo + 24
    # 48 .. 71 = pcb
    s = rb[rbo:rbo+24]
    print("pcb '%s'" % (str(s)))
    rbo = rbo + 24
    # 72 .. 95 = pack (bluetooth name)
    s = rb[rbo:rbo+24]
    print("pack '%s'" % (str(s)))
    rbo = rbo + 24
    print("END %d %d" % (rbo, len(rb)))

def do0003():
    # 0 = chargeMOS
    i = get8()
    print("chargeMOS %d" % i)
    # 1 = dischargeMOS
    i = get8()
    print("dischargeMOS %d" % i)
    # 2 = DO1
    i = get8()
    print("DO1 %d" % i)
    # 3 = DO2
    i = get8()
    print("DO2 %d" % i)

# UNTESTED

def do0301():    
    # 0 = result code (1 = success, anything else = fail)
    i = get8()
    print("ret %d" % i)
    
# 0302 is ignored by app
    
def do0303():    
    # 0 = result code (1 = success, anything else = fail)
    i = get8()
    print("ret %d" % i)
    

# handle an rx buffer
def dorx():
    global rb
    print("RX: ")
    if len(rb) < 8:
        print("TOO SHORT")
        return
    # end sentinel?
    if rb[len(rb) - 1] != 0xa7:
        print("INVALID END CHAR %02x" % b[len(rb) - 1])
        return
    # crc (last 2 bytes before
    i = rb[len(rb) - 3] * 256 + rb[len(rb) - 2]
    print("CRC: 0x%04x" % i)
    crc = crc16(rb, 1, len(rb) - 4)
    print("RX CRC: 0x%04x" % crc)
    if i != crc:
        print("BAD CRC")
        return
    # 0 = start sentinel
    i = get8()
    if i != 0x7a:
        print("INVALID START CHAR %02x" % i)
        return
    # 1 = unknwon - probably high byte of length
    i = get8()
    # 2 = length
    i = get8()
    print("Length: %d" % i)
    if len(rb) != i + 4:
        print("INVALID LENGTH (%d / %d)" % (i, len(rb)))
        return
    # 4 = unknown - probably address
    i = get8()
    # 5,6 = command
    i = get16()
    print("command: 0x%04x" % i)
    if i == 0x0001:
        return do0001()
    if i == 0x0002:
        return do0002()
    if i == 0x0003:
        return do0003()
    print("BAD COMMAND: 0x%04x" % i)

def tx(cmd, payload):
    # <0x7a> <0? *1> <length *2> <address *3> <cmd hi> <cmd lo> [<payload>] <crc hi> <crc lo> <0xa7>
    b = bytearray([0, 0, 0, 0, 0]);
    cmd = cmd & 0xffff
    b[3] = cmd >> 8
    b[4] = cmd & 0xff
    if payload is not None:
        b = b + payload
    b[1] = len(b)
    crc = crc16(b, 0, len(b))
    #c = bytearray([crc>>8, crc&0xff, 0xa7])
    #b.append(crc)
    b.append(crc>>8)
    b.append(crc&0xff)
    b.append(0xa7)
    b = bytearray([0x7a])+b
    dump(b)
    global f
    f.write(b)

f=open(cfg_tty, "r+b", 0)

# test commands
tx(0x0001, None)
#tx(0x0002, None)
#tx(0x0003, None)

# NOT GOING TO PLAY WITH 0x03.. commands, as they set things, and i am not sure what the durability of such changes are

rbl = -1
while True:
    b = f.read(1)
    #dump(b)
    dne = False
    for i in b:
        print("%03d: %02x (%d)" % (len(rb), i, i))
        if len(rb) == 0 and i != 0x7a:
            print("skip bad start char %02x" % i)
            continue
        if len(rb) == 2:
            rbl = i
        rb.append(i)
        #print("%03d: %02x (%d) %d %d %d" % (len(rb), i, i, rbl, i == 0xa7, len(rb) == rbl + 4))
        if i == 0xa7 and len(rb) == rbl + 4:
            dne = True
            break
    if dne:
        break

f.close()

dorx()



