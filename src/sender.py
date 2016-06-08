import os
import socket
import sys
from time import time
import struct

class Packet(object):
	def __init__(self, crcLen, bufSize):
		self.crcLength = crcLen
		self.crcSize = pow(2, self.crcLength)
		self.formatStr = "!I" + str(self.crcLength) + "s" + str(bufSize) + "s"
		self.crcNumber = 0

	def decimalToBinary(self, decimalNumber):
		if(decimalNumber < 2):
			return str(decimalNumber)
		return self.decimalToBinary(decimalNumber /2) + str(decimalNumber%2)

	def pack(self, buf):
		size = len(buf)
		crcString = self.decimalToBinary(self.crcNumber)
		if len(crcString) < self.crcLength:
			crcString = ('0' * (self.crcLength-len(crcString))) + crcString
		p = struct.pack(self.formatStr, size, crcString, buf)
		self.crcNumber = (self.crcNumber +1) % self.crcSize
		return p, size

class SenderWindowManager(object):
	def __init__(self, crcLength, time):
		self.crcSize = pow(2, crcLength)
		self.windowSize = self.crcSize /2
		self.crcArray = [False] * self.crcSize
		self.packetArray = [ ]
		self.timerArray = [ ]
		self.windowStart = 0
		self.windowEnd = self.windowSize
		self.lastCRC = 0
		self.timer = time

	def needMorePacket(self):
		return self.lastCRC != self.windowEnd

	def pushPacket(self, pack):
		self.packetArray.append(pack)
		self.timerArray.append(time())
		self.lastCRC = (self.lastCRC +1) % self.crcSize

	def moveWindow(self):
		while(self.crcArray[self.windowStart]):
			self.windowStart = (self.windowStart +1) % self.crcSize
			self.windowEnd = (self.windowEnd +1) % self.crcSize
			self.crcArray[self.windowEnd] = False
			self.packetArray.pop(0)
			self.timerArray.pop(0)
		
	def receiveAck(self, ack):
		ackNumber = self.binaryToDecimal(ack)
		self.crcArray[ackNumber] = True

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

BUFFER_SIZE = 1024
CRC_LENGTH = 4
TIMER = 1
CHECK_TERM = 0.01

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
		manager = SenderWindowManager(CRC_LENGTH, TIMER)
		pack = Packet(CRC_LENGTH, BUFFER_SIZE)
		while(data  or manager.existBuffer()):
			while(manager.needMorePacket() and data):
				packet, size = pack.pack(data)
				sock.sendto(packet, server)
				manager.pushPacket(packet)
				transferred += size
				print transferred, "/", fileSize, \
				"(Current size / Total size),", \
				round(float(transferred)/fileSize*100, 2), "%"
				data = f.read(BUFFER_SIZE)
			try:
				ack, addr = sock.recvfrom(CRC_LENGTH)
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
