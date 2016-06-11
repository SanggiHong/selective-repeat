import os
import socket
import sys
import struct
from time import time
import random

TEST_MODE = True

class Packet(object):
	def __init__(self, sequenceLen, bufSize):
		self.sequenceLength = sequenceLen
		self.sequenceSize = pow(2, self.sequenceLength)
		self.bufferSize = bufSize
		self.formatStr = "!I" + str(self.sequenceLength) + "s" + str(self.bufferSize) + "ss"
		self.sequenceNumber = 0
		self.size = sequenceLen + bufSize + 5
	
	def unpack(self, pack):
		result = struct.unpack(self.formatStr, pack)
		#size = result[0]
		#sequenceString = result[1]
		#buffer = result[2]
		#checksum = result[3]
		check = self.isValidChecksum(result[1] + result[2], result[3])
		if(TEST_MODE):
			if(random.randrange(0,50) == 1):
				check = False
		return result[1], result[0], result[2], check

	def isValidChecksum(self, buf, checksum):
		sumtp = 0
		ptr = 0
		while(ptr < len(buf)):
			sumtp += ord(buf[ptr])
			ptr += 1
		result = struct.unpack("ssss", struct.pack("!I", sumtp))
		return result[3] == checksum
		
class ReceiverWindowManager(object):
	def __init__(self, sequenceLength):
		self.sequenceSize = pow(2, sequenceLength)
		self.windowSize = self.sequenceSize /2
		self.sequenceArray = [False] * self.sequenceSize
		self.bufferArray = [None] * self.windowSize
		self.sizeArray = [0] * self.windowSize
		self.windowStart = 0
		self.windowEnd = self.windowSize

	def receivePacket(self, sequence, size, buf):
		sequenceNumber = self.binaryToDecimal(sequence)
		if(TEST_MODE):
			print "Receive Packet; Sequence Number", sequenceNumber
		if(self.isValidSequenceNumber(sequenceNumber)):
			index = self.sequenceToWindowIndex(sequenceNumber)
			if(self.sequenceArray[sequenceNumber] is False):
				if(TEST_MODE):
					print "is Accepted WindowNumber is", index
				self.bufferArray[index] = buf
				self.sizeArray[index] = size
				self.sequenceArray[sequenceNumber] = True
		return sequence

	def moveWindow(self):
		result = []
		while(self.sequenceArray[self.windowStart]):
			self.windowStart = (self.windowStart +1) % self.sequenceSize
			self.windowEnd = (self.windowEnd +1) % self.sequenceSize
			self.sequenceArray[self.windowEnd] = False
			result.append( (self.sizeArray.pop(0), self.bufferArray.pop(0)) )
			self.sizeArray.append(0)
			self.bufferArray.append(None)
		return result

	def sequenceToWindowIndex(self, sequenceNumber):
		ptr = self.windowStart
		index = 0
		while(ptr != sequenceNumber):
			ptr = (ptr +1) % self.sequenceSize
			index += 1
		return index

	def binaryToDecimal(self, binaryString):
		return int(binaryString, 2)

	def isValidSequenceNumber(self, sequenceNumber):
		if(self.windowStart < self.windowEnd):
			if(self.windowStart <= sequenceNumber and sequenceNumber < self.windowEnd):
				return True
			return False
		if(self.windowEnd < self.windowStart):
			if(sequenceNumber < self.windowEnd or self.windowStart <= sequenceNumber):
				return True
			return False


UDP_IP = ""
UDP_PORT = 5005
BUFFER_SIZE = 1024
SEQUENCE_LENGTH = 4

if __name != "__main__":
	sys.exit()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print "Ready for Sender..."

try:
	filePath, addr = sock.recvfrom(1472)
	print "FileName :", filePath
	fileSize, addr = sock.recvfrom(1472)
	print "FileSize :", fileSize
	fileSize = int(fileSize)
	sock.sendto("1", addr)

	print "Transfer Start..."
	startTime = time()
	with open(filePath, "wb") as f:
		received = 0
		manager = ReceiverWindowManager(SEQUENCE_LENGTH)
		pack = Packet(SEQUENCE_LENGTH, BUFFER_SIZE)
		while (received < fileSize):
			packet, addr = sock.recvfrom(pack.size)
			sequence, size, buf, isChecksumValid = pack.unpack(packet)
			if(not isChecksumValid):
				continue
			ack = manager.receivePacket(sequence, size, buf)
			sock.sendto(str(ack), addr)
			bufToWrite = manager.moveWindow()
			while(len(bufToWrite) != 0):
				tup = bufToWrite.pop(0)
				f.write(tup[1])
				received += tup[0]
				print received, "/", fileSize,\
				"(Current size / Total size)",\
				round(float(received)/fileSize*100, 2), "%"
	endTime = time()
	print "Completed..."
	print "Time elapsed :", str(endTime - startTime)
except socket.error as e:
	print e
	sys.exit()
