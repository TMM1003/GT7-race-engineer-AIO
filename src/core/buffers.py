from collections import deque


class RingBuffer:
    def __init__(self, size=3000):
        self.buf = deque(maxlen=size)

    def append(self, item):
        self.buf.append(item)

    def values(self):
        return list(self.buf)
