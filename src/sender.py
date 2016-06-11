import os
import socket
import sys
from time import time
import struct

TEST_MODE = True

class Packet(object):
	def __init__(self, sequenceLen, bufSize):
		self.sequenceLength = sequenceLen
		self.sequenceSize = pow(2, self.sequenceLength)
		self.bufferSize = bufSize
		self.formatStr = "!I" + str(self.sequenceLength) + "s" + str(bufSize) + "ss"
		self.sequenceNumber = 0

	def decimalToBinary(self, decimalNumber):
		if(decimalNumber < 2):
			return str(decimalNumber)
		return self.decimalToBinary(decimalNumber /2) + str(decimalNumber%2)

	def pack(self, buf):
		if(TEST_MODE):
			print "SequenceNumber", self.sequenceNumber, "is Packed"
		size = len(buf)
		sequenceString = self.decimalToBinary(self.sequenceNumber)
		if len(sequenceString) < self.sequenceLength:
			sequenceString = ('0' * (self.sequenceLength-len(sequenceString))) + sequenceString
		checksum = self.makeChecksum(size, sequenceString + buf)
		p = struct.pack(self.formatStr, size, sequenceString, buf, checksum)
		self.sequenceNumber = (self.sequenceNumber +1) % self.sequenceSize
		return p, size

	def makeChecksum(self, size, buf):
		sumtp = 0
		ptr = 0
		while(ptr < len(buf)):
			sumtp += ord(buf[ptr])
			ptr += 1
		checksum = struct.unpack("ssss", struct.pack("!I", sumtp))
		return checksum[3]

class SenderWindowManager(object):
	def __init__(self, sequenceLength, time):
		self.sequenceSize = pow(2, sequenceLength)
		self.windowSize = self.sequenceSize /2
		self.sequenceArray = [False] * self.sequenceSize
		self.packetArray = [ ]
		self.timerArray = [ ]
		self.windowStart = 0
		self.windowEnd = self.windowSize
		self.lastSequence = 0
		self.timer = time

	def needMorePacket(self):
		return self.lastSequence != self.windowEnd

	def pushPacket(self, pack):
		self.packetArray.append(pack)
		self.timerArray.append(time())
		self.lastSequence = (self.lastSequence +1) % self.sequenceSize

	def moveWindow(self):
		while(self.sequenceArray[self.windowStart]):
			self.windowStart = (self.windowStart +1) % self.sequenceSize
			self.windowEnd = (self.windowEnd +1) % self.sequenceSize
			self.sequenceArray[self.windowEnd] = False
			self.packetArray.pop(0)
			self.timerArray.pop(0)
		
	def receiveAck(self, ack):
		ackNumber = self.binaryToDecimal(ack)
		if(TEST_MODE):
			print "Receive Ack Number", ackNumber
		self.sequenceArray[ackNumber] = True

	def binaryToDecimal(self, binaryString):
		return int(binaryString, 2)
		
	def packetToResend(self):
		currentTime = time()
		result = [ ]
		index = 0
		while( index < len(self.timerArray) ):
			if( self.timer < (currentTime - self.timerArray[index]) ):
				print "WindowNumber", index, "'s Packet was resended"
				result.append(self.packetArray[index])
				self.timerArray[index] = currentTime
			index += 1
		return result

	def existBuffer(self):
		return len(self.packetArray) != 0

BUFFER_SIZE = 1024 		#bits
SEQUENCE_LENGTH = 4 	#bits
TIMER = 2				#seconds
CHECK_TERM = 0.01 		#seconds

if __name__ != "__main__":
	sys.exit()
if len(sys.argv) < 3:
	print "[Dest IP Addr] [Dest Port] [File Path]"
	sys.exit()

serverIP = sys.argv[1]
serverPort = int(sys.argv[2])
filePath = sys.argv[3]
server = (serverIP, serverPort)

try:
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	fileSize = os.stat(filePath).st_size
	sock.sendto(filePath, server)
	sock.sendto(str(fileSize), server)
	
	sock.settimeout(30)
	try:
		key,addr = sock.recvfrom(1)
	except socket.timeout as e:
		print "Receiver didn't respond"
		sys.exit()

	print "Receiver Connected..."
	print "Receiver address:", addr[0]
	startTime = time()	
	with open(filePath, "rb") as f:
		transferred = 0
		sock.settimeout(CHECK_TERM)
		data = f.read(BUFFER_SIZE)
		manager = SenderWindowManager(SEQUENCE_LENGTH, TIMER)
		pack = Packet(SEQUENCE_LENGTH, BUFFER_SIZE)
		while(data or manager.existBuffer()):
			while(data and manager.needMorePacket()):
				packet, size = pack.pack(data)
				sock.sendto(packet, server)
				manager.pushPacket(packet)
				transferred += size
				print transferred, "/", fileSize, \
				"(Current size / Total size),", \
				round(float(transferred)/fileSize*100, 2), "%"
				data = f.read(BUFFER_SIZE)
			try:
				ack, addr = sock.recvfrom(SEQUENCE_LENGTH)
				manager.receiveAck(ack)
				manager.moveWindow()				
			except socket.timeout as e:
				pass
			pList = manager.packetToResend()
			while(len(pList) != 0):
				sock.sendto(pList.pop(0), server)
	endTime = time()
	print "Completed..."
	print "Time elapsed :", str(endTime - startTime)

except socket.error as e:
	print e
	sys.exit()
