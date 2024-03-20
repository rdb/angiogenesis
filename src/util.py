class RingList(list):
    def __getitem__(self, i):
        return list.__getitem__(self, i % len(self))

    def __setitem__(self, i, v):
        return list.__setitem__(self, i % len(self), v)
